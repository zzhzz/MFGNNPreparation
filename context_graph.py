import json
import sys
sys.setrecursionlimit(1000000)

Child = 0
Next_token = 1
LastRead = 2
LastWrite = 3
ComputedFrom = 4
ReturnsTo = 5
FormalArgName = 6
GuardedBy = 7
GuardedByNeg = 8
LastLexicalUse = 9


def gen_context_graph(ast, tk_mp):
    ctxg_edges = set()
    edges = ast['edges']
    labels = ast['labels']
    tr = [[] for _ in labels]
    out_degree = [0 for _ in labels]
    for edge in edges:
        u, v = edge
        ctxg_edges.add((u, v, Child))
        tr[u].append(v)
        out_degree[u] += 1

    token_list = [] # for next token and last lexical use
    method_decls = {}
    for u, tk in enumerate(labels):
        if tk == 'Function':
            name = labels[tr[u][0]]
            method_decls[name] = u

    def dfs(u, func_name, define_st, use_st, defined=False, use=False, compute_result=-1, if_branch=-1, cond_stmt=-1):
        if out_degree[u] == 0:
            token_list.append(u)
            if labels[u] in define_st.keys():
                ctxg_edges.add((u, define_st[labels[u]], LastWrite))
            else:
                define_st[labels[u]] = u
            if labels[u] in use_st.keys():
                ctxg_edges.add((u, use_st[labels[u]], LastRead))
            else:
                use_st[labels[u]] = u
            if if_branch == 0:
                ctxg_edges.add((u, cond_stmt, GuardedBy))
            elif if_branch == 1:
                ctxg_edges.add((u, cond_stmt, GuardedByNeg))
            if compute_result != -1:
                ctxg_edges.add((compute_result, u, ComputedFrom))
            if defined:
                define_st[labels[u]] = u
            if use:
                use_st[labels[u]] = u
            return u

        cur = labels[u]

        if cur == 'ReturnStmt':
            ctxg_edges.add((u, method_decls[func_name], ReturnsTo))

        if cur == 'Function':
            func_name = labels[tr[u][0]]

        if cur == 'CallExpr':
            callee = labels[tr[u][0]]
            if callee in method_decls.keys():
                decl_node = method_decls[callee]
                for i in range(1, len(tr[decl_node])):
                    ctxg_edges.add((tr[u][i], tr[decl_node][i], FormalArgName))
        if cur == 'BinaryOperator':
            op = labels[tr[u][0]]
            dfs(tr[u][0], func_name, define_st, use_st, defined, use, compute_result, if_branch, cond_stmt)
            if op == '=':
                bedef = dfs(tr[u][1], func_name, define_st, use_st, True, True, compute_result, if_branch, cond_stmt)
                dfs(tr[u][2], func_name, define_st, use_st, False, True, bedef, if_branch, cond_stmt)
            else:
                dfs(tr[u][1], func_name, define_st, use_st, False, True, compute_result, if_branch, cond_stmt)
                dfs(tr[u][2], func_name, define_st, use_st, False, True, compute_result, if_branch, cond_stmt)
            return tr[u][-1]

        if cur == 'IfStmt':
            cond = tr[u][0]
            dfs(tr[u][0], func_name, define_st, use_st)
            if len(tr[u]) >= 2:
                dfs(tr[u][1], func_name, define_st, use_st, defined, use, compute_result, if_branch=0, cond_stmt=cond)

            if len(tr[u]) >= 3:
                dfs(tr[u][2], func_name, define_st, use_st, defined, use, compute_result, if_branch=1, cond_stmt=cond)
            return tr[u][-1]

        for v in tr[u]:
            dfs(v, func_name, define_st, use_st, defined, use, compute_result, if_branch, cond_stmt)

        return tr[u][-1]

    dfs(0, '', {}, {})
    vars = {}
    for idx, u in enumerate(token_list):
        if idx+1 < len(token_list):
            ctxg_edges.add((u, token_list[idx+1], Next_token))
        if labels[u] in vars.keys():
            ctxg_edges.add((u, vars[labels[u]], LastLexicalUse))
        vars[labels[u]] = u

    for tk_id, tk in enumerate(labels):
        labels[tk_id] = tk_mp[tk]

    return {
        'labels': labels,
        'edges': list(ctxg_edges),
        'label': ast['label']
    }

