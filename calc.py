import itertools
from collections import defaultdict, deque

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
    current_path = [start_node]
    circuit = []
    
    while current_path:
        u = current_path[-1]
        
        if graph[u]:
            v, edge_data = graph[u].popleft()
            current_path.append(v)
            circuit.append((u, v, edge_data))
        else:
            circuit_segment = []
            while current_path and not graph[current_path[-1]]:
                w = current_path.pop()
                if circuit:
                    last_edge = circuit.pop()
                    circuit_segment.append(last_edge)
                
            # 閉路の再挿入 (逆順にpopしたため)
            circuit.extend(circuit_segment[::-1])
            
            if not current_path and circuit:
                # 最後の閉路セグメントの始点ノードを circuit に追加 (オイラー閉路の終点と始点を一致させる)
                circuit.append((circuit[0][0], circuit[0][1], circuit[0][2])) # 最後の辺の始点と終点が一致
                
    # 閉路は (u, v, edge_data) のリスト。最後の (u, v) は最初と重複しているため削除
    if circuit and circuit[-1][0] == circuit[0][0]:
        circuit.pop() 
        
    return circuit

def find_single_euler_circuit_variable_s(N, S, start_state_str='0' * 4):
    """
    ビット変化パターンで重複を排除し、オイラー閉路を構成する代表辺を選択し、閉路を出力する。
    """
    if S <= 0:
        raise ValueError("Sは1以上の整数である必要があります。")

    # 1. 完全グラフの構築
    mutable_edges_full, total_count_full, start_node_initial = build_euler_graph_variable_s(N, S)

    if total_count_full == 0:
        return 0, 0, 0, 0
    
    # 2. ビット変化パターンによる辺のグループ化と代表辺の選択
    # Key: ビット変化シーケンス, Value: 採用した状態遷移の接続情報 (始点ノード, 終点ノード, 遷移文字列)
    unique_bit_change_patterns = {} 
    
    # Key: 始点ノード (S-1パス), Value: deque([(終点ノード, 遷移文字列), ...])
    euler_edges_for_unique_patterns = defaultdict(deque)
    
    unique_patterns_count = 0
    total_edges_adopted = 0

    # 既存の全遷移 (mutable_edges_full) を巡回
    for start_node_str, edges_deque in mutable_edges_full.items():
        # 破壊しないようリストに変換してループ
        for end_node_str, transition_str in list(edges_deque): 
            
            transition_states = transition_str.split('->')
            bit_change_key = get_bit_change_sequence(transition_states)
            
            if bit_change_key not in unique_bit_change_patterns:
                # 初めて見つかったビット変化パターンを記録し、
                # その辺を「オイラー閉路用グラフ」の辺として採用する。
                
                # 採用した辺を新しいグラフに追加
                euler_edges_for_unique_patterns[start_node_str].append((end_node_str, transition_str))
                
                # パターンの情報（ここでは、採用した辺の情報を保持）
                unique_bit_change_patterns[bit_change_key] = (start_node_str, end_node_str, transition_str)
                unique_patterns_count += 1
                total_edges_adopted += 1
            # else:
            # 既に同じビット変化パターンの辺が採用されているため、この辺は破棄される。

    # 3. 採用された辺のみを持つグラフでオイラー閉路を探索
    
    # 探索の開始ノードの決定
    start_node_final = start_node_initial
    if not euler_edges_for_unique_patterns:
        print("オイラー閉路を構成するための辺がありません。")
        return total_count_full, 0, 0, 0
        
    if start_node_final not in euler_edges_for_unique_patterns and start_node_final in mutable_edges_full:
        # 開始ノードが採用した辺の始点ではない場合、採用された辺を持つ任意のノードから開始
        start_node_final = next(iter(euler_edges_for_unique_patterns.keys()))

    print(f"--- N={N}ビット、S={S}ステップ、オイラー閉路構成による重複排除 ---")
    print(f"全Sステップ遷移の総数: **{total_count_full}**")
    print(f"ユニークなビット変化パターン数（採用された辺の数）: **{unique_patterns_count}**")
    
    # オイラー閉路の探索実行
    euler_circuit = find_euler_circuit(euler_edges_for_unique_patterns, start_node_final)
    
    # 4. 結果の整形と出力
    
    print(f"\n## 👑 採用されたビット変化パターンに基づくシーケンス")
    
    final_sequences_list = []
    
    if euler_circuit:
        print(f"**✅ オイラー閉路（デ・ブルイジン列）が発見されました。**")
        print(f"閉路の長さ: **{len(euler_circuit)}** (採用されたユニークパターン数と一致)")
        
        # 閉路を構成する辺のデータ (遷移文字列) のリストを生成
        sequence_transitions = [edge_data for u, v, edge_data in euler_circuit]
        
        # 修正: リストをそのまま追加するのではなく、要素を拡張して追加する
        final_sequences_list.extend(sequence_transitions) 
        total_continuous_count = len(final_sequences_list)
        
    else:
        print(f"**❌ オイラー閉路は発見されませんでした。**")
        print("（ビット変化パターンで重複排除した結果、グラフの接続性が失われたため）")
        print(f"代わりに、採用されたユニークな辺（{total_edges_adopted}個）をリストとして出力します。")
        
        # 閉路が見つからなかった場合、採用された辺を全て出力する
        for bit_change_key in unique_bit_change_patterns:
            start_node_str, end_node_str, transition_str = unique_bit_change_patterns[bit_change_key]
            final_sequences_list.append(transition_str)
            
        total_continuous_count = len(final_sequences_list)
        
    print(f"\n💡 開始ノード: **{start_node_final}** (S-1パス)")
    
    # =========================================================================
    # 【追加】ひとつなぎのシーケンス文字列の表示
    # =========================================================================
    if final_sequences_list:
        # 最初のSステップ遷移を取得 (例: '0000->0001->0011')
        first_transition_states = final_sequences_list[0].split('->')
        
        # 連結シーケンスの初期状態として、最初の遷移のS-1状態までを含める
        # 例: S=2なら最初の2状態 '0000->0001' を初期状態とする
        if S == 1:
             # S=1 の場合、一つ目の状態 '0000' のみ
             connected_sequence = first_transition_states[0]
        else:
             # S > 1 の場合、S個の状態 (S-1パス) を取得
             connected_sequence = "->".join(first_transition_states[:-1])

        # 2番目以降の遷移から、最後の1状態のみを抽出して連結する
        # 例: 2番目の遷移 '0001->0011->1011' から '1011' のみを取得
        for transition_str in final_sequences_list:
            last_state = transition_str.split('->')[-1]
            connected_sequence += "->" + last_state

        print("\n## 🔗 連結されたひとつなぎのシーケンス")
        print(f"（合計 {total_continuous_count * S} 状態、または {total_continuous_count * (S - 1) + 1} 状態）")
        
        if len(connected_sequence) > 200:
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
print(f"実行: N={N_BITS_EXAMPLE_1}, S={STEP_S_EXAMPLE_1}, オイラー閉路構成で重複排除")
total_1, unique_1, remaining_1, seq_count_1 = find_single_euler_circuit_variable_s(N_BITS_EXAMPLE_1, STEP_S_EXAMPLE_1, START_STATE)