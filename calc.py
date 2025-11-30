import itertools
from collections import defaultdict, deque

def is_single_bit_change(state_a, state_b):
    """2つの状態が1ビットのみ異なるかチェックする (S=1遷移の条件)"""
    if len(state_a) != len(state_b): return False
    # 異なるビットの数を数える
    diff = sum(1 for a, b in zip(state_a, state_b) if a != b)
    return diff == 1

def build_euler_graph_variable_s(N, S):
    """
    Nビット系、Sステップ遷移の補助グラフを構築する。
    ノード: S-1ステップの遷移パス
    辺: Sステップの遷移パス
    """
    if S < 1:
        raise ValueError("ステップ数 S は 1 以上である必要があります。")

    all_states = [''.join(p) for p in itertools.product('01', repeat=N)]
    mutable_edges = defaultdict(deque)
    total_s_transitions = 0
    # start_node はグラフ内の任意のノードとして初期化
    start_node = None 

    # ----------------------------------------------------------------------
    # Sステップ遷移の生成とグラフ構築
    # ----------------------------------------------------------------------

    if S == 1:
        # S=1 の場合、ノードは単一の状態 A です。補助グラフは Q_N そのもの。
        start_paths = [[s] for s in all_states]
        s_minus_1_length = 1
    else:
        # S>=2 の場合、S-1パスを再帰的に生成します。
        s_minus_1_length = S 
        start_paths = []
         
        # 単一ビット変化がS-1回連続する全てのパスを生成
        def generate_s_minus_1_paths(current_path):
            if len(current_path) == s_minus_1_length:
                start_paths.append(current_path)
                return
             
            last_state = current_path[-1]
            for next_state in all_states:
                # 1ビット変化の制約
                if is_single_bit_change(last_state, next_state):
                    generate_s_minus_1_paths(current_path + [next_state])

        for s in all_states:
            generate_s_minus_1_paths([s])


    for path_list in start_paths:
        # ノード (S-1パス) の文字列表現
        start_node_str = "->".join(path_list)
         
        if start_node is None:
            start_node = start_node_str

        last_state = path_list[-1]
         
        # 最後の状態から1ステップ進んでSステップ遷移（辺）を完成させる
        for next_state in all_states:
            if is_single_bit_change(last_state, next_state):
                 
                # Sステップ遷移 (辺) の文字列
                transition_str = start_node_str + "->" + next_state
                 
                # 次のノード (S-1パス) の文字列 (先頭を外し末尾を追加)
                if S == 1:
                    # S=1の時、次のノードは単一状態 (next_state)
                    end_node_str = next_state
                else:
                    # S>=2の時、次のノードは (B->C->...->X)
                    end_node = path_list[1:] + [next_state]
                    end_node_str = "->".join(end_node)
                 
                # 補助グラフに辺を追加
                mutable_edges[start_node_str].append((end_node_str, transition_str))
                total_s_transitions += 1
                 
    if start_node is None and total_s_transitions > 0:
        # ノードが作成されたが、start_nodeがNoneのままの場合
        start_node = next(iter(mutable_edges.keys()))

    return mutable_edges, total_s_transitions, start_node

def find_single_euler_circuit_variable_s(N, S, start_state_str='0' * 4):
    """
    Nビット系、Sステップの全パターンをオイラー閉路探索の原理で強制的に
    連続シーケンスに分割し、残りのパターンを0にする。

    :param start_state_str: 最初のSステップ遷移の始点となる状態 (例: '0000')
    """
    if S <= 0:
        raise ValueError("Sは1以上の整数である必要があります。")

    mutable_edges, total_count, _ = build_euler_graph_variable_s(N, S)

    if total_count == 0:
        return 0, 0, 0, 0
     
    # ----------------------------------------------------------------------
    # 1. 探索の最初の始点を特定
    # ----------------------------------------------------------------------
     
    # ユーザーが指定した状態 (start_state_str) を先頭に持つ S-1 パス (ノード) を探す。
    target_start_node = None
     
    # ノード (S-1 パス) は 'A->B->C' の形式
    for node_str in mutable_edges.keys():
        path_states = node_str.split('->')
        # Sに関わらず、辺の始点状態はノードの先頭状態 (path_states[0])
        if path_states[0] == start_state_str: # <--- 修正箇所 (path_states[0]を使用)
            target_start_node = node_str
            break

    if target_start_node is None:
        # 該当するノードが存在しない場合 (N, S の設定ミス等) は、
        # 既存の任意のノードを始点にするか、エラーとする
        # ここでは、既存の任意のノードを始点とします。
        start_node = next(iter(mutable_edges.keys()))
        print(f"⚠️ 指定された開始状態 ({start_state_str}) を先頭とするノードが見つからなかったため、任意のノード ({start_node}) から開始します。")
    else:
        start_node = target_start_node
     
    # ----------------------------------------------------------------------
    # 2. グラフの性質判定
    # ----------------------------------------------------------------------
     
    is_euler_circuit_guaranteed = (S >= 2) or (S == 1 and N % 2 == 0)
     
    # ----------------------------------------------------------------------
    # 3. オイラー路探索 (Hierholzer's Algorithmの応用)
    # ----------------------------------------------------------------------
     
    final_sequences = []

    # 最初の探索は指定されたノードから開始
    current_start_node = start_node
     
    while True:
        # 未処理の辺を持つ任意のノードを始点として選択 (最初の1回のみ指定されたノードを使う)
        if not current_start_node:
            current_start_node = next(iter(k for k, v in mutable_edges.items() if v), None)

        if current_start_node is None:
            break

        current_circuit_s = [] # Sステップ遷移のパス
        stack = [current_start_node]
         
        while stack:
            current_node = stack[-1] 
             
            # 現在のノードから出る辺があるかチェック
            if mutable_edges.get(current_node):
                # 次の辺（Sステップ遷移）を取り出す
                next_node, transition_str = mutable_edges[current_node].pop()
                 
                stack.append(next_node)
                current_circuit_s.append(transition_str)
            else:
                # 閉路または終点に到達
                stack.pop()
         
        if current_circuit_s:
            final_sequences.append(current_circuit_s[::-1])

        # 最初の探索が終了したら、次は任意のノードから開始
        current_start_node = None
     
    # ----------------------------------------------------------------------
    # 4. 結果の整形と出力
    # ----------------------------------------------------------------------
     
    overall_continuous_count = sum(len(seq) for seq in final_sequences)
    remaining_count = total_count - overall_continuous_count
     
    print(f"--- N={N}ビット、S={S}ステップ、全パターン強制接続 ---")
    print(f"全パターン数 ({S}ステップ遷移の総数): **{total_count}**")
    print(f"💡 開始状態: **{start_state_str}**")

    print(f"\n## 👑 遷移シーケンス ({len(final_sequences)}個のシーケンス)")
     
    if is_euler_circuit_guaranteed:
        print("✅ **オイラー閉路が存在する（入次数=出次数）。理論上1つのシーケンスでカバーされます。**")
    elif S == 1 and N % 2 != 0:
        print(f"⚠️ **S=1かつN={N}（奇数）の場合、補助グラフ（$Q_N$）はオイラー閉路を持ちません。**")
        print("   全遷移をカバーするために複数のパスに分解されています。")
     
    # シーケンスの出力を簡略化（最初の1つのみパスを表示）
    for idx, seq in enumerate(final_sequences[:min(3, len(final_sequences))]):
         
        # シーケンスの状態遷移パスを作成
        if not seq: continue
         
        # -----------------------------------------------------------
        # 【修正】 全てのSで、単一閉路の場合に指定開始状態から始まるようシーケンスを回転
        # -----------------------------------------------------------
        # 単一閉路で回収された場合のみ回転させる
        if len(final_sequences) == 1:
            start_transition_index = -1
            
            # Sステップ遷移の最初の状態 (A->B->...->X の A) が start_state_str と一致するものを探す
            for i, transition in enumerate(seq):
                if transition.split('->')[0] == start_state_str:
                    start_transition_index = i
                    break

            if start_transition_index != -1:
                # 見つかった場合はシーケンスを回転
                seq = seq[start_transition_index:] + seq[:start_transition_index]
        # -----------------------------------------------------------
        
        # 最初のSステップ遷移のパスを取得 (A->B->C...->X)
        path_parts = seq[0].split('->')
        final_path = path_parts[:-1] # 最初のS-1ステップまで

        # 全てのSステップ遷移の終端状態を追加
        for transition in seq:
            final_path.append(transition.split('->')[-1])
         
        path_str = " -> ".join(final_path)

        print(f"  --- シーケンス {idx+1} ({len(seq)}パターン) ---")
        print(f"  **{path_str}**")
         
        # S=2 遷移の表示
        for t_idx, transition in enumerate(seq):
             print(f"    {t_idx+1:03d}. {transition}")
             
    if len(final_sequences) > 3:
        print(f"\n  ... ({len(final_sequences) - 3}個のシーケンスを省略)")

    print(f"\n--- 最終結果 ---")
    print(f"連続遷移として組み込まれたパターン総数: **{overall_continuous_count}**")
    print(f"残りの非連続なパターン数: **{remaining_count}**")
     
    if remaining_count == 0:
        print("\n✅ **残りの非連続パターン数は 0 です。** (全てのSステップ遷移が回収されました)")
         
    return total_count, overall_continuous_count, remaining_count, len(final_sequences)

# --------------------------------------------------------------------------
# 使用例: N=4ビット, S=2ステップ (デ・ブラン的なケース)
# --------------------------------------------------------------------------
N_BITS_EXAMPLE_1 = 4
STEP_S_EXAMPLE_1 = 2 
START_STATE = '0000' # ここを開始したい状態に変更
print("==============================================")
print(f"実行: N={N_BITS_EXAMPLE_1}, S={STEP_S_EXAMPLE_1}, 開始状態={START_STATE}")
total_1, continuous_1, remaining_1, seq_count_1 = find_single_euler_circuit_variable_s(N_BITS_EXAMPLE_1, STEP_S_EXAMPLE_1, START_STATE)
