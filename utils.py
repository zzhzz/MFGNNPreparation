import re
import json
from config import experiment


def skip_space(text, effect_line=False):
    cnt = 0
    std_str = ''
    comment = False
    for line in text:
        if line.startswith('/*'):
            comment = True
        if comment:
            if line.find('*/') != -1:
                comment = False
                continue
            else:
                continue

        if line.find('//') != -1:
            pos = line.find('//')
            line = line[:pos]
        line = line.strip()
        line = line.replace('\t', '')
        if line.startswith('#'):
            continue
        line = line.replace(' ', '')
        if(len(line) > 0):
            cnt += 1
        std_str += line
    if effect_line:
        return cnt
    return std_str


def deduplication(prob_dir, code_list, labels):
    data_list = [[] for _ in range(len(labels))]
    for code_file in code_list:
        submission_name = code_file[:code_file.find('.')]
        if experiment == 'codechef': 
            label = ''.join(submission_name.split('_')[1:])
        else:
            label = ''.join(submission_name.split('_')[1:-1])
        data_list[labels.index(label)].append(code_file)

    result_list = []
    for dlist in data_list:
        hash_set = set()
        for code_file in dlist:
            with open(prob_dir + code_file, 'r') as fh:
                std_src = list(fh)
            std_str = skip_space(std_src)
            if std_str not in hash_set:
                hash_set.add(std_str)
                result_list.append(code_file)
    return result_list


def gen_dataflow(cfg):
    n_block = len(cfg['blocks'])
    graph = [[] for _ in range(n_block)]
    indegree = [0 for _ in range(n_block)]
    for edge in cfg['cfg_edges']:
        if experiment != 'promise':
            rel, t = edge
            u, v = rel
        else:
            u, v, t = edge
        indegree[v] += 1
        graph[u].append(v)
    entry = list(filter(lambda x: indegree[x] == 0, range(n_block)))[0]
    df_edges = set()
    node_count = {}  # for loop-use variable
    def dfs(block_id, state):
        node_count[block_id] += 1
        cur_block = cfg['blocks'][block_id]
        for ast in cur_block:
            for u in ast['use']:
                if u in state.keys():
                    df_edges.add((state[u], block_id))
            for d in ast['def']:
                state[d] = block_id
            for u in ast['use']:
                if u in state.keys():
                    df_edges.add((state[u], block_id))
                else:
                    df_edges.add((entry, block_id))  # function call, define on the parameters
        for adj in graph[block_id]:
            if node_count[adj] <= 3:
                cur_state = json.loads(json.dumps(state))  # create new dict to save state
                dfs(adj, cur_state)

    for u in range(n_block):
        node_count[u] = 0
    dfs(entry, dict())
    for edge in df_edges:
        u, v = edge
        cfg['cfg_edges'].append(((u, v), 3))
