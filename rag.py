import sqlite3
import sqlite_vec
import struct
from typing import List, Tuple
import os
import numpy as np

# --- 設定 ---
DB_PATH = "./rag_vec0_only_db.sqlite"
VECTOR_DIM = 4
VEC_TABLE = "vec_items" 

TOP_K = 2 # ベクトル検索で取得するシードチャンク数 (TEXTとIMAGEそれぞれからN件取得)

# =============================================================================
# --- 検索クエリ定義 ---
# =============================================================================

# @brief RAGルールに基づき、単一SQLクエリでコンテキストを取得する
#         - ステップ1: TEXTからN件、IMAGEからN件を取得し、距離順で上位N件の構造を特定
#         - ステップ2: 特定された構造のTEXTは全て、IMAGEはステップ1で取得したN件を最終結果とする
RETRIEVAL_QUERY = f"""
WITH SeedText AS (
    -- ステップ 1a: TEXTからN件を取得
    SELECT 
        id, 
        filename, 
        chapter, 
        section, 
        item, 
        type,
        text,
        distance
    FROM {VEC_TABLE}
    WHERE embedding MATCH :query_embed AND type = 'TEXT'
    LIMIT :top_k
),
SeedImage AS (
    -- ステップ 1b: IMAGEからN件を取得
    SELECT 
        id, 
        filename, 
        chapter, 
        section, 
        item, 
        type,
        text,
        distance
    FROM {VEC_TABLE}
    WHERE embedding MATCH :query_embed AND type = 'IMAGE'
    LIMIT :top_k
),
TopNStructureKeys AS (
    -- ステップ 1c: TEXTとIMAGEのシードを結合し、distance順に並び替えて上位N件の構造キーを特定
    SELECT DISTINCT
        filename,
        chapter,
        section,
        item
    FROM (
        SELECT filename, chapter, section, item, distance FROM SeedText
        UNION ALL
        SELECT filename, chapter, section, item, distance FROM SeedImage
    )
    ORDER BY distance
    LIMIT :top_k
),
FinalTextChunks AS (
    -- ステップ 2a: 特定された構造キーを持つ全てのTEXTチャンクをオリジナルテーブルから取得
    SELECT
        T1.id,
        T1.filename,
        T1.chapter,
        T1.section,
        T1.item,
        T1.type,
        T1.text
    FROM {VEC_TABLE} AS T1
    JOIN TopNStructureKeys AS K ON 
        T1.filename = K.filename AND
        T1.chapter = K.chapter AND
        T1.section = K.section AND
        T1.item = K.item
    WHERE T1.type = 'TEXT'
),
FinalImageChunks AS (
    -- ステップ 2b: 特定された構造キーを持つ、かつステップ1で取得されたIMAGEチャンクを再取得
    -- (IMAGEチャンクはSeedImageに限定される)
    SELECT
        S.id,
        S.filename,
        S.chapter,
        S.section,
        S.item,
        S.type,
        S.text
    FROM SeedImage AS S -- SeedImage (ステップ1で取得したN件のIMAGE) の結果を元にする
    JOIN TopNStructureKeys AS K ON 
        S.filename = K.filename AND
        S.chapter = K.chapter AND
        S.section = K.section AND
        S.item = K.item
)
-- 最終 SELECT: TEXTチャンクとIMAGEチャンクを結合し、ID順にソート
SELECT id, filename, chapter, section, item, type, text FROM FinalTextChunks

UNION ALL

SELECT id, filename, chapter, section, item, type, text FROM FinalImageChunks;
"""


# =============================================================================
# --- ユーティリティ関数 ---
# =============================================================================

## @brief ベクトルをsqlite-vec形式のBLOBにシリアライズする
def serialize_vector(vector: List[float]) -> bytes:
    """
    floatのリスト、またはNumPy配列（float32）をコンパクトな「raw bytes」形式にシリアライズします。
    """
    if isinstance(vector, np.ndarray):
        if vector.dtype != np.float32:
            vector = vector.astype(np.float32)
        return vector.tobytes()
        
    format_string = f"<{len(vector)}f"
    return struct.pack(format_string, *vector)


# =============================================================================
## @brief データベースの初期化、vec0仮想テーブルの作成、データの挿入を行う
def setup_database(db: sqlite3.Connection, dummy_data: List[Tuple], vec_dim: int):
    """
    RAGに必要な全てのデータを格納するvec0仮想テーブルを作成し、データを挿入します。
    """
    cursor = db.cursor()
    db.enable_load_extension(True)
    sqlite_vec.load(db) 
    db.enable_load_extension(False)
    print(f"SQLite Version: {db.execute('SELECT sqlite_version()').fetchone()[0]}")
    print(f"sqlite-vec Version: {db.execute('SELECT vec_version()').fetchone()[0]}")
    print("-" * 30)

    # 1. vec0仮想テーブルの作成 (全てのRAGメタデータを含む)
    print(f"1. VIRTUAL TABLE {VEC_TABLE} (vec0) を作成 (全RAGデータを含む)...")
    try:
        db.execute(f"""
            CREATE VIRTUAL TABLE {VEC_TABLE} USING vec0(
                id INTEGER,
                filename TEXT,
                chapter TEXT,
                section TEXT,
                item TEXT,
                type TEXT, 
                text TEXT,
                embedding float[{vec_dim}]
            );
        """)
        print("✅ vec0仮想テーブル作成完了。")
    except sqlite3.OperationalError as e:
        print(f"⚠ テーブル作成エラー (既に存在している可能性): {e}")

    # 2. データの挿入
    print("\n🚀 データの挿入...")
    with db:
        for data in dummy_data:
            vector = data[-1]
            serialized_vector = serialize_vector(vector)
            insert_data = data[:-1] + (serialized_vector,)
             
            cursor.execute(f"""
                INSERT INTO {VEC_TABLE}(id, filename, chapter, section, item, type, text, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, insert_data)
             
        print(f"✅ {len(dummy_data)} 個のアイテムが挿入されました。")


# =============================================================================
# --- RAG検索関数 ---
# =============================================================================

## @brief ベクトル検索と文脈拡張を行い、RAG用のコンテキストを取得する
def retrieve_chunks_for_rag(
    db: sqlite3.Connection, 
    query_vector: List[float], 
    k: int
) -> str:
    """
    RAGルールに基づき、コンテキストを取得し、整形されたテキストを返します。
    """
    cursor = db.cursor()
    serialized_query = serialize_vector(query_vector)
     
    print(f"\n🔍 RAG統合検索 (K={k}, 新しい構造拡張ロジック)...")
     
    params = {
        'query_embed': serialized_query,
        'top_k': k
    }

    # 単一SQLクエリを実行
    cursor.execute(RETRIEVAL_QUERY, params)
    context_data = cursor.fetchall()

    if not context_data:
        print("関連性の高いチャンクは見つかりませんでした。")
        return ""

    # --- データの整形と表示 ---
    combined_context = []
     
    for row in context_data:
        # row: (id, filename, chapter, section, item, type, text)
        chunk_id, filename, chapter, section, item, chunk_type, text = row
         
        # type='IMAGE' の場合は画像タグを追加
        if chunk_type == 'IMAGE':
             text = f"[Image: {filename}/{chapter}/{section}/{item} - {text}]" 

        header = f"  [ID:{chunk_id} | {filename} / Ch:{chapter} Sec:{section} Item:{item} | Type:{chunk_type}]"
        combined_context.append(f"{header}\n{text}\n")

    final_context_text = "\n---\n".join(combined_context)

    print(f"   ✅ 取得した合計チャンク数: {len(context_data)}")
    print("\n--- LLMに渡す最終コンテキスト ---")
    print(final_context_text)
     
    return final_context_text


# =============================================================================
# --- メイン実行ブロック ---
# =============================================================================

if __name__ == "__main__":
     
    # 💡 構造 B は IMAGE で、ID 4, 5, 6 の3つが同じ構造を持つようにする
    dummy_data: List[Tuple] = [
        # 構造 A (TEXT): 3つのチャンクが同じ構造メタデータを持つ 
        # (距離: 0.1, 0.2, 0.3)
        (1, "docA", "1", "1.1", "A", "TEXT", "エネルギー技術に焦点を当てています。", [0.1, 0.1, 0.1, 0.1]),
        (2, "docA", "1", "1.1", "A", "TEXT", "太陽光発電システム（PV）の効率とコスト削減が主要なトピックです。", [0.2, 0.2, 0.2, 0.2]),
        (3, "docA", "1", "1.1", "A", "TEXT", "PVセルの製造工程における最新の改善点について詳細に説明されています。", [0.3, 0.3, 0.3, 0.3]),
         
        # 構造 B (IMAGE): 3つのチャンクが同じ構造を持ち、そのうち2つ（ID 4, 5）がクエリに近い
        # (距離: 0.81, 0.90, 0.99)
        (4, "docB", "2", "2.1", "B", "IMAGE", "量子コンピュータの基礎理論の図。", [0.81, 0.81, 0.81, 0.81]), 
        (5, "docB", "2", "2.1", "B", "IMAGE", "量子ビット（Qubit）のコヒーレンス維持を示すグラフ。", [0.90, 0.90, 0.90, 0.90]), 
        (6, "docB", "2", "2.1", "B", "IMAGE", "量子誤り訂正技術に関する図。", [0.99, 0.99, 0.99, 0.99]), 
    ]

    # 検索クエリベクトル (ターゲット: ID=2 (TEXT) と ID=4, 5 (IMAGE) に近い)
    query_vector = [0.25, 0.25, 0.25, 0.25]
     
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"既存のデータベースファイル {DB_PATH} を削除しました。")
     
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
         
        setup_database(conn, dummy_data, VECTOR_DIM)
         
        # TOP_K=2 に設定
        retrieved_context = retrieve_chunks_for_rag(
            db=conn, 
            query_vector=query_vector, 
            k=TOP_K
        )
         
    except sqlite3.Error as e:
        print(f"\n❌ データベース操作エラー: {e}")
         
    finally:
        if conn:
            conn.close()
            print("\n--------------------------------")
            print("データベース接続を閉じました。")