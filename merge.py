from collections import deque
from config import experiment
import numpy as np

def bfs(tr, num, tree_id):
    q = deque([(0, 2)])  # (node_id, depth), the root node of block at depth 1
    indexes, depths = [0] * (num-1), [0] * num
    while q:
        u, dep = q.popleft()
        depths[u] = dep
        for idx, v in enumerate(tr[u], 1):
            indexes[v[0]] = idx
            q.append((v[1], dep + 1))
    if tree_id != -1:
        indexes = indexes + [tree_id + 1]
    return indexes, depths


def merge_ast(block_list, func_names, token_map):
    blocks = []
    for block_id, block in enumerate(block_list):
        nodes, edges, indexes, depths, calling = [token_map['Stmt']], [], [], [1], []
        mask = [len(ast['labels']) for ast in block]
        for ast_id, ast in enumerate(block):
            ast_n = len(ast['labels'])
            if ast_n == 0:
                continue
            pre_base = sum(mask[0:ast_id]) + 1
            for node in ast['labels']:
                nodes.append(token_map[node])
            assert len(ast['labels']) == len(ast['edges']) + 1, '%d %d' % (len(ast['labels']), len(ast['edges']))
            indegree = [0 for _ in range(ast_n)]
            tr = [[] for _ in range(ast_n)]
            for eid, edge in enumerate(ast['edges']):
                u, v = edge
                tr[u].append((eid, v))
                indegree[v] += 1
                id_u, id_v = u + pre_base, v + pre_base
                edges.append((id_u, id_v))
            index, depth = bfs(tr, ast_n, ast_id)
            indexes.extend(index)
            depths.extend(depth)
            root = list(filter(lambda x: indegree[x] == 0, range(ast_n)))[0] # for python 3, find root of tree
            edges.append((0, root + pre_base)) # connect tree to the block's tree
            for relation in ast['calls']:
                name = relation
                if name in func_names.keys():
                    calling.append(name)
        blocks.append((nodes, edges, indexes, depths, calling))
    return blocks


def merge(func_list, label, token_map):
    func_names = {}
    idx = 0
    for func_cfg in func_list:
        name = func_cfg['func_name']
        if name not in func_names.keys():
            func_names[func_cfg['func_name']] = idx
            idx += 1

    func_nodes = [None for _ in range(len(func_names))]
    for func_cfg in func_list:
        block_edges, block_nodes, cfg_map_edges, block_indexes, block_depth, block_call = [], [], [], [], [], []

        # distinguish entry and end node by degree
        n_blocks = len(func_cfg['blocks'])
        entry, end = -1, -1
        indegree = [0 for _ in range(n_blocks)]
        outdegree = [0 for _ in range(n_blocks)]

        for edge in func_cfg['cfg_edges']:
            if len(edge) == 2:
                u, v, t = edge[0][0], edge[0][1], edge[1]
            else:
                u, v, t = edge
            indegree[v] += 1
            outdegree[u] += 1

        for nd in range(n_blocks):
            if indegree[nd] == 0 and outdegree[nd] != 0:
                entry = nd
            if indegree[nd] != 0 and outdegree[nd] == 0:
                end = nd

        blocks = merge_ast(func_cfg['blocks'], func_names, token_map)

        # combine the function-level CFG block together, in order to process parallel
        base_id = [len(x[0]) for x in blocks]
        for block_id, block in enumerate(blocks):
            nodes, edges, indexes, depths, calling = block
            pre_base = sum(base_id[0:block_id])
            for eid, edge in enumerate(edges):
                u, v = edge
                block_edges.append((u + pre_base, v + pre_base))
                block_indexes.append(indexes[eid])
            for node_id, node in enumerate(nodes):
                cfg_map_edges.append((block_id, node_id + pre_base))
                block_nodes.append(node)
                block_depth.append(depths[node_id])
            for callee in calling:
                # which block calls which function
                block_call.append((block_id, callee))

        # temporarily result, have a break
        item = {
            'name': func_cfg['func_name'],
            'ast_nodes': block_nodes,
            'ast_edges': block_edges,
            'ast_index': block_indexes,
            'ast_depth': block_depth,
            'mapping_relation': cfg_map_edges,
            'entry': entry,
            'end': end,
            'calling': block_call,
            'edges': func_cfg['cfg_edges'],
            'n': n_blocks
        }
        func_nodes[func_names[item['name']]] = item

    # combine function-level CFG to file-level CFG
    mask = [node['n'] for node in func_nodes]
    mask_for_ast = [len(node['ast_nodes']) for node in func_nodes]
    ast_all_nodes, ast_all_edges, mapping_relation = [], [], []
    ast_all_index, ast_all_depth = [], []
    cfg_edges, cfg_blocks = [], []
    mx_edge_type = 0 # constrain edge type < 5 (avoiding switch case)
    for cfg_id, cfg in enumerate(func_nodes):
        pre_mask = sum(mask[0:cfg_id])
        ast_base = sum(mask_for_ast[0:cfg_id])
        graph = [[] for _ in range(cfg['n'])]
        for edge in cfg['edges']:
            if len(edge) == 2:
                u, v, t = edge[0][0], edge[0][1], edge[1]
            else:
                u, v, t = edge
            graph[u].append((v, t))
        for calls in cfg['calling']:
            u, callee = calls
            if callee in func_names.keys():
                callee = func_names[callee]
                # connect call relation
                id_u, id_v = u + pre_mask, func_nodes[callee]['entry'] + sum(mask[0:callee])
                cfg_edges.append((id_u, id_v, 4))
                if func_nodes[callee]['end'] != -1:
                    id_ret = func_nodes[callee]['end'] + sum(mask[0:callee])
                    for rel in graph[u]:
                        cfg_edges.append((id_ret, rel[0] + pre_mask, rel[1]))
                else:
                    # the successor of block u will never be reached (callee is a dead loop)
                    graph[u] = []
        for u in range(cfg['n']):
            for adj in graph[u]:
                v, t = adj
                id_u, id_v = u + pre_mask, v + pre_mask
                cfg_edges.append((id_u, id_v, t))

        for eid, edge in enumerate(cfg_edges):
            if edge[2] >= 6:
                cfg_edges[eid] = (edge[0], edge[1], 6)
        ast_all_nodes.extend(cfg['ast_nodes'])
        ast_all_index.extend(cfg['ast_index'])
        ast_all_depth.extend(cfg['ast_depth'])
        for ast_edge in cfg['ast_edges']:
            u, v = ast_edge
            id_u, id_v = u + ast_base, v + ast_base
            ast_all_edges.append((id_u, id_v))
        for map_rel in cfg['mapping_relation']:
            block_id, ast_id = map_rel
            id_block, id_ast = block_id + pre_mask, ast_id + ast_base
            mapping_relation.append((id_block, id_ast))
    if len(cfg_edges) == 0 or len(ast_all_edges) == 0 or len(mapping_relation) == 0:
        # illegal
        return -1
    return {
        'n_blocks': sum(mask),
        'graph': cfg_edges,
        'ast_nodes': ast_all_nodes,
        'ast_index': ast_all_index,
        'ast_depth': ast_all_depth,
        'ast_edges': ast_all_edges,
        'mapping': mapping_relation,
        'label': label
    }


def deal_ast(ast, token_map):
    ast_nodes = ast['labels']
    ast_edges = ast['edges']
    label = ast['label']
    labels = []
    tr = [[] for _ in ast_nodes]
    for tk in ast_nodes:
        labels.append(token_map[tk])
    for eid, edge in enumerate(ast_edges):
        u, v = edge
        tr[u].append((eid, v))
    index, depth = bfs(tr, len(ast_nodes), -1)
    return {
        'ast_nodes': labels,
        'ast_edges': ast_edges,
        'indexes': index,
        'depth': depth,
        'label': label
    }


