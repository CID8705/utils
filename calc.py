import itertools
from collections import defaultdict, deque
import copy # グラフをコピーするために使用

# LSB (右端) からのビット位置を返すヘルパー関数
def get_lsb_bit_index(N, i):
    """MSB側インデックスiからLSB側インデックスを計算 (LSB=0)"""
    return N - 1 - i

def is_single_bit_change(state_a, state_b):
    """2つの状態が1ビットのみ異なるかチェックする (S=1遷移の条件)"""
    if len(state_a) != len(state_b): return False
    diff = sum(1 for a, b in zip(state_a, state_b) if a != b)
    return diff == 1

def format_transition_bit_change(state_a, state_b):
    """
    遷移A->Bにおける、変化したビットの位置と変化内容をLSB基準で表示する。
    例: '0000' -> '0001' (N=4) の場合、'0ビット目が0から1へ変化'
    """
    if len(state_a) != len(state_b):
        return f"状態長不一致: {state_a} -> {state_b}"

    N = len(state_a)
    
    for i in range(N):
        bit_index = get_lsb_bit_index(N, i)
        bit_a = state_a[i]
        bit_b = state_b[i]

        if bit_a != bit_b:
            return f"{bit_index}ビット目が{bit_a}から{bit_b}へ変化"
             
    return "変化なし"

def get_bit_change_sequence(path_states):
    """
    状態のリスト [A, B, C, ...] から、ビット変化の連鎖 [Delta(A->B), Delta(B->C), ...] を生成する。
    連鎖の各要素: '{LSBインデックス}:{変化元->変化後}'
    """
    N = len(path_states[0])
    change_sequence = []
    
    for i in range(len(path_states) - 1):
        state_a = path_states[i]
        state_b = path_states[i+1]
        
        change_key = ""
        
        for j in range(N):
            if state_a[j] != state_b[j]:
                k = get_lsb_bit_index(N, j) 
                change_key = f"{k}:{state_a[j]}->{state_b[j]}"
                break
         
        if not change_key:
            change_key = "NoChange"
         
        change_sequence.append(change_key)
         
    return "->".join(change_sequence)
# =========================================================================

def build_euler_graph_variable_s(N, S):
    """
    Nビット系、Sステップ遷移の補助グラフ（デ・ブルイジングラフ）を構築する。
    """
    if S < 1:
        raise ValueError("ステップ数 S は 1 以上である必要があります。")

    all_states = [''.join(p) for p in itertools.product('01', repeat=N)]
    mutable_edges = defaultdict(deque)
    total_s_transitions = 0
    start_node = None 

    # S-1パスの生成（ノードの定義）
    s_minus_1_length = S if S > 1 else 1
    start_paths = []
    
    if S == 1:
        start_paths = [[s] for s in all_states]
    else:
        # S > 1 の場合のノード (S-1パス) 生成
        def generate_s_minus_1_paths(current_path):
            if len(current_path) == s_minus_1_length:
                start_paths.append(current_path)
                return
             
            last_state = current_path[-1]
            for next_state in all_states:
                if is_single_bit_change(last_state, next_state):
                    generate_s_minus_1_paths(current_path + [next_state])

        for s in all_states:
            generate_s_minus_1_paths([s])

    # Sステップ遷移の生成（辺の定義）
    for path_list in start_paths:
        start_node_str = "->".join(path_list)
        if start_node is None:
            start_node = start_node_str

        last_state = path_list[-1]
        
        for next_state in all_states:
            if is_single_bit_change(last_state, next_state):
                
                transition_states = path_list + [next_state] # A->B->...->X の状態リスト
                transition_str = "->".join(transition_states)
                
                if S == 1:
                    end_node_str = next_state
                else:
                    end_node = path_list[1:] + [next_state]
                    end_node_str = "->".join(end_node)
                 
                # 補助グラフに辺を追加 (始点ノード, (終点ノード, 遷移文字列))
                mutable_edges[start_node_str].append((end_node_str, transition_str))
                total_s_transitions += 1
                 
    if start_node is None and total_s_transitions > 0:
        start_node = next(iter(mutable_edges.keys()))

    return mutable_edges, total_s_transitions, start_node

# =========================================================================
# 階層的ディクショナリを用いたオイラー閉路探索（ヒエホルツァーのアルゴリズム）
# =========================================================================
def find_euler_circuit(graph, start_node):
    """
    Hierholzerのアルゴリズムを使用してオイラー閉路を探索する。
    graphは defaultdict(deque) 形式: {始点: deque([(終点, 辺のデータ), ...]), ...}
    """
    # 探索に使用するため、グラフをコピーして非破壊的に処理する
    temp_graph = {k: deque(v) for k, v in graph.items()}
    
    current_path = [start_node]
    circuit = []
    
    # グラフが空または開始ノードに辺がない場合は終了
    if not temp_graph or start_node not in temp_graph and any(temp_graph.values()):
        return []

    while current_path:
        u = current_path[-1]
        
        if u in temp_graph and temp_graph[u]:
            v, edge_data = temp_graph[u].popleft()
            current_path.append(v)
            circuit.append((u, v, edge_data))
        else:
            # 閉路を抽出してメインの閉路に組み込む
            # u (最後のノード) が含まれる閉路セグメントを抽出
            closed_segment = []
            
            # current_pathから閉路を構成するノードを取り出す
            segment_start_node = None
            if len(current_path) > 1:
                # 最後のノード u が出次数0の場合、uが閉路の終点
                segment_end_node = current_path.pop() 
                # segment_end_node に繋がる最後の辺 (u_prev, u) を探す
                
                for i in range(len(circuit) - 1, -1, -1):
                    u_prev, v, edge_data = circuit[i]
                    if v == segment_end_node:
                        # 閉路のセグメントの始点が見つかった
                        segment_start_node = u_prev
                        # 閉路セグメントを circuit から切り離す
                        closed_segment = circuit[i:] 
                        circuit = circuit[:i]
                        break
                        
                # 閉路セグメントを circuit に戻す
                circuit.extend(closed_segment)
                
                # 次の探索を開始するノード (出次数 > 0 のノード) を見つける
                while current_path:
                    check_node = current_path[-1]
                    if check_node in temp_graph and temp_graph[check_node]:
                        break
                    current_path.pop()
                    
            elif len(current_path) == 1 and not (u in temp_graph and temp_graph[u]):
                # グラフ全体が辺を使い切ったか、開始ノードで止まった
                break

    # 最終チェック: 全ての辺が使用されたか確認 (オイラー閉路の必須条件)
    # ただし、Hierholzerのアルゴリズムの簡略化バージョンでは、部分閉路しか見つけられない場合もあるため、
    # ここでは見つかった閉路の辺数のみをチェックする。
    
    # 閉路の辺のリスト (u, v, edge_data) を返す
    return circuit

def is_eulerian(edges, total_edges, all_nodes):
    """
    グラフがオイラーグラフの条件を満たすかチェックする。
    （辺の総数が一致し、全ノードで入次数=出次数、かつ強連結）
    """
    in_degree = defaultdict(int)
    out_degree = defaultdict(int)
    
    for u, v, _ in edges:
        out_degree[u] += 1
        in_degree[v] += 1
        
    # 1. 辺の総数が一致しているか
    if len(edges) != total_edges:
        return False, "辺の総数が不一致"
        
    # 2. 全ノードで入次数 = 出次数か (全ノードが探索されたか)
    for node in all_nodes:
        if in_degree[node] != out_degree[node]:
            return False, f"ノード {node} で入次数({in_degree[node]}) != 出次数({out_degree[node]})"
            
    # 3. 強連結性の確認は、オイラー閉路探索（find_euler_circuit）に任せる
    # （find_euler_circuit が全ての辺を使い切れば強連結性も満たされる）
    return True, ""


# =========================================================================
# 【修正箇所】バックトラックによる探索関数を追加
# =========================================================================

def find_euler_circuit_by_search(patterns_list, pattern_to_edges_map, all_nodes, 
                                 current_selection_index, current_euler_edges, total_unique_patterns, start_node_initial):
    """
    再帰的なDFSによるバックトラック探索。
    patterns_list の各パターンに対し、辺の候補から一つを選択し、オイラー閉路をチェックする。
    """
    # 終了条件: 全てのユニークパターンについて辺の選択が完了した
    if current_selection_index == total_unique_patterns:
        
        # 4. 採用された辺でオイラー閉路を探索
        # defaultdict(deque) に変換
        final_euler_edges = defaultdict(deque)
        total_edges_adopted = 0
        for u, v, edge_data in current_euler_edges:
            final_euler_edges[u].append((v, edge_data))
            total_edges_adopted += 1
            
        # オイラー閉路の探索実行
        euler_circuit = find_euler_circuit(final_euler_edges, start_node_initial)
        
        # 辺の総数がユニークパターン数と一致し、閉路がその長さと一致するか
        if len(euler_circuit) == total_edges_adopted:
            # 成功: オイラー閉路が見つかった
            return euler_circuit
        else:
            # 失敗: 接続性が失われ、閉路が形成できなかった
            return None 

    # 探索対象のパターンキー
    pattern_key = patterns_list[current_selection_index]
    # そのパターンに該当する全ての辺の候補リスト [(start_node_str, end_node_str, transition_str), ...]
    candidate_edges = pattern_to_edges_map[pattern_key]

    # 各候補辺について試行
    for u, v, transition_str in candidate_edges:
        
        # 選択した辺を一時的にグラフに追加
        current_euler_edges.append((u, v, transition_str))
        
        # 次のパターンへ再帰
        result_circuit = find_euler_circuit_by_search(patterns_list, pattern_to_edges_map, all_nodes, 
                                                     current_selection_index + 1, current_euler_edges, 
                                                     total_unique_patterns, start_node_initial)
        
        if result_circuit is not None:
            # 閉路が見つかった
            return result_circuit
            
        # バックトラック: 辺の選択を元に戻す
        current_euler_edges.pop()

    return None # このパターンのどの辺を選んでも閉路が見つからなかった

# =========================================================================
# メイン処理関数 (探索ロジックに置き換え)
# =========================================================================

def find_single_euler_circuit_variable_s(N, S, start_state_str='0' * 4):
    """
    バックトラック探索を用いて、オイラー閉路を構成する代表辺を選択し、閉路を出力する。
    """
    if S <= 0:
        raise ValueError("Sは1以上の整数である必要があります。")

    # 1. 完全グラフの構築
    mutable_edges_full, total_count_full, start_node_initial = build_euler_graph_variable_s(N, S)

    if total_count_full == 0:
        return 0, 0, 0, 0
    
    # 2. ビット変化パターンによる辺のグループ化
    # Key: ビット変化シーケンス, Value: 全ての候補辺のリスト [(始点, 終点, 遷移文字列), ...]
    pattern_to_edges_map = defaultdict(list)
    all_nodes = set()
    
    for start_node_str, edges_deque in mutable_edges_full.items():
        all_nodes.add(start_node_str)
        for end_node_str, transition_str in edges_deque: 
            all_nodes.add(end_node_str)
            
            transition_states = transition_str.split('->')
            bit_change_key = get_bit_change_sequence(transition_states)
            
            # 候補辺として全ての情報をリストに格納
            pattern_to_edges_map[bit_change_key].append((start_node_str, end_node_str, transition_str))

    unique_patterns_count = len(pattern_to_edges_map)
    patterns_list = list(pattern_to_edges_map.keys())
    
    print(f"--- N={N}ビット、S={S}ステップ、オイラー閉路構成による重複排除 ---")
    print(f"全Sステップ遷移の総数: **{total_count_full}**")
    print(f"ユニークなビット変化パターン数: **{unique_patterns_count}**")
    
    # 3. バックトラック探索によるオイラー閉路の探索実行
    print("\n## 🔍 バックトラック探索開始...")
    
    # 開始ノードを、採用する辺のいずれかの始点ノードにする
    start_node_final = start_node_initial
    
    euler_circuit = find_euler_circuit_by_search(
        patterns_list,                  # 探索するパターンキーのリスト
        pattern_to_edges_map,           # パターンごとの全候補辺のマップ
        all_nodes,                      # 全ノードの集合
        0,                              # 現在のパターンインデックス
        [],                             # 現在選択された辺のリスト (最初は空)
        unique_patterns_count,          # ユニークパターンの総数
        start_node_final                # 探索開始ノード
    )
    
    total_edges_adopted = unique_patterns_count
    
    # 4. 結果の整形と出力
    final_sequences_list = []
    
    if euler_circuit:
        print(f"**✅ オイラー閉路（デ・ブルイジン列）が発見されました。**")
        print(f"閉路の長さ: **{len(euler_circuit)}** (採用されたユニークパターン数と一致)")
         
        # 閉路を構成する辺のデータ (遷移文字列) のリストを生成
        sequence_transitions = [edge_data for u, v, edge_data in euler_circuit]
        final_sequences_list.extend(sequence_transitions) 
        total_continuous_count = len(final_sequences_list)
         
    else:
        print(f"**❌ オイラー閉路は発見されませんでした。**")
        print("（全ての辺の組み合わせを試しましたが、グラフの接続性を保つ辺の選択肢が存在しませんでした）")
        total_continuous_count = 0 

    print(f"\n💡 開始ノード: **{start_node_final}** (S-1パス)")
    
    # ... (後続の出力処理は変更なし) ...
    # =========================================================================
    # 【追加】ひとつなぎのシーケンス文字列の表示
    # =========================================================================
    if final_sequences_list:
        # 最初のSステップ遷移を取得 (例: '0000->0001->0011')
        first_transition_states = final_sequences_list[0].split('->')
        
        # 連結シーケンスの初期状態として、最初の遷移のS-1状態までを含める
        if S == 1:
             # S=1 の場合、一つ目の状態 '0000' のみ
             connected_sequence = first_transition_states[0]
        else:
             # S > 1 の場合、S個の状態 (S-1パス) を取得
             connected_sequence = "->".join(first_transition_states[:-1])

        # 2番目以降の遷移から、最後の1状態のみを抽出して連結する
        for transition_str in final_sequences_list:
            last_state = transition_str.split('->')[-1]
            connected_sequence += "->" + last_state

        print("\n## 🔗 連結されたひとつなぎのシーケンス")
        print(f"（合計 {len(connected_sequence.split('->'))} 状態）")
         
        if len(connected_sequence) > 200:
             print(f"> {connected_sequence[:200]}...")
        else:
             print(f"> {connected_sequence}")
    # =========================================================================


    print(f"\n--- シーケンスの詳細 ({total_continuous_count}ステップ) ---")

    output_limit = 50
    for t_idx, transition_str in enumerate(final_sequences_list):
        if t_idx >= output_limit:
            print(f"\n  ... ({total_continuous_count - output_limit}個のステップを省略)")
            break
             
        # transition_str は文字列として扱われることを確認
        transition_states = transition_str.split('->')
        bit_change_key = get_bit_change_sequence(transition_states)
         
        state_a_for_bit_change = transition_states[-2] if S > 1 else transition_states[0]
        state_b_for_bit_change = transition_states[-1]
         
        bit_change_detail = format_transition_bit_change(state_a_for_bit_change, state_b_for_bit_change)
         
        print(f"  {t_idx+1:03d}. {transition_str} (パターンID: {bit_change_key}) (最終変化: {bit_change_detail})")

    print(f"\n--- 最終結果 ---")
    print(f"採用されたユニークなビット変化パターン総数: **{total_edges_adopted}**")
    print(f"オイラー閉路長: **{len(euler_circuit) if euler_circuit else 0}**")
         
    return total_count_full, total_edges_adopted, total_edges_adopted - (len(euler_circuit) if euler_circuit else 0), 1


# --------------------------------------------------------------------------
# 使用例: N=4ビット, S=2ステップ
# --------------------------------------------------------------------------
N_BITS_EXAMPLE_1 = 4
STEP_S_EXAMPLE_1 = 2 
START_STATE = '0000' 
print("==============================================")
print(f"実行: N={N_BITS_EXAMPLE_1}, S={STEP_S_EXAMPLE_1}, オイラー閉路構成で重複排除 (探索あり)")
total_1, unique_1, remaining_1, seq_count_1 = find_single_euler_circuit_variable_s(N_BITS_EXAMPLE_1, STEP_S_EXAMPLE_1, START_STATE)