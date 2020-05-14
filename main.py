from config import experiment, save_dir, original_data_dir, with_df, labels
import os
from clang_cfg import Parser, AST, Block, CFG
import numpy as np
from merge import merge, deal_ast
from utils import deduplication, gen_dataflow, skip_space
from context_graph import gen_context_graph
import json
from tqdm import tqdm

def data_queue(code_list, raw_dir, work_dir, length):
    config_list = []
    code_paths = []
    root_dir = os.path.dirname(os.path.abspath(__file__)) + '/'
    for code in code_list:
        code = code.split('/')[-1]
        code_path = raw_dir + code
        work_path = work_dir
        code_config = {
            'directory': root_dir + work_path,
            'command': 'cc -fsyntax-only -w -I' + root_dir + '/include' + ' ' + root_dir + work_path + '/' + code,
            'file': code
        }
        config_list.append(code_config)
        code_paths.append(code_path)
        if len(config_list) == length:
            yield config_list, code_paths
            config_list, code_paths = [], []
    yield config_list, code_paths


def trans_oj_ecfg():
    exp_dir = original_data_dir + '/' + experiment + '/'
    problem_list = list(os.listdir(exp_dir))
    parser = Parser()
    experiment_save_dir = save_dir + '/' + experiment + '/'
    if not os.path.exists(experiment_save_dir):
        os.makedirs(experiment_save_dir)
    for problem in problem_list:
        prob_data_list = []
        prob_dir = exp_dir + problem + '/'
        code_list = list(os.listdir(prob_dir))
        code_list = deduplication(prob_dir, code_list, labels=labels)
        idx = 1
        # each problem has its tokenMap
        tk_mp = {'Stmt': 0}
        cfgs = []
        parse_result_path = save_dir + '/' + experiment + '/' + problem + '_raw_data.json'
        if not os.path.exists(parse_result_path):
            dataqueue = data_queue(code_list, prob_dir, work_dir=prob_dir, length=1)
            print('Parsing')
            pbar = tqdm(dataqueue)
            for codes in pbar:
                configs, paths = codes
                config_str = json.dumps(configs)
                cfg_list = parser.parse_to_extendcfg(paths, config_str)
                for idx, func_list in enumerate(cfg_list):
                    pbar.write(paths[idx])
                    func_result = []
                    code = paths[idx].split('/')[-1]
                    submission_name = code[:code.find('.')]
                    temp_lis = submission_name.split('_')[1:]
                    if experiment == 'codeforces':
                        temp_lis = temp_lis[:-1]
                    label = '_'.join(temp_lis)
                    for cfg in func_list:
                        cfg_dict = {}
                        cfg_edges = cfg.edges
                        block_list = cfg.block_list
                        func_name = cfg.func_name
                        cfg_block_list = []
                        for block in block_list:
                            ast_list = block.content
                            block_dict = []
                            for ast in ast_list:
                                ast_dict = {}
                                ast_edges, ast_labels, ast_defines, ast_use, ast_call = ast.edges, ast.node_labels, ast.define_vars, ast.use_vars, ast.calls
                                ast_dict['edges'] = ast_edges
                                ast_dict['labels'] = ast_labels
                                ast_dict['def'] = list(ast_defines)
                                ast_dict['use'] = list(ast_use)
                                ast_dict['calls'] = ast_call
                                block_dict.append(ast_dict)
                            cfg_block_list.append(block_dict)
                        cfg_dict['func_name'] = func_name
                        cfg_dict['cfg_edges'] = cfg_edges
                        cfg_dict['blocks'] = cfg_block_list
                        if with_df:
                            gen_dataflow(cfg_dict)
                        func_result.append(cfg_dict)
                    cfgs.append((func_result, label))
            with open(parse_result_path, 'w') as fh:
                json.dump(cfgs, fh)
        else:
            print('All ready parsed, load from json file')
            with open(parse_result_path, 'r') as fh:
                cfgs = json.load(fh)

        print('Generate token map')        
        for cfg, label in cfgs:
            for g in cfg:
                for asts in g['blocks']:
                    for t in asts:
                        for tk in t['labels']:
                            if tk not in tk_mp.keys():
                                tk_mp[tk] = idx
                                idx += 1
        map_path = save_dir + '/' + experiment + '/' + problem + '_tkmp.json'
        with open(map_path, 'w') as fh:
            json.dump(tk_mp, fh)
        pbar = tqdm(enumerate(code_list))
        for code_id, code in pbar:
            cfg, label = cfgs[code_id]
            pbar.write(code)
            data = merge(func_list=cfg, label=label, token_map=tk_mp)
            if data == -1:
                continue
            data['name'] = code
            prob_data_list.append(data)
        df_status = 'df' if with_df else 'nodf'
        prob_save_path = save_dir + '/' + experiment + '/' + problem + '_' + df_status + '.json'
        with open(prob_save_path, 'w') as fh:
            print(f'{problem} {df_status} stored in {prob_save_path}')
            json.dump(prob_data_list, fh)


def trans_oj_ast():
    exp_dir = original_data_dir + '/' + experiment + '/'
    problem_list = list(os.listdir(exp_dir))
    parser = Parser()
    experiment_save_dir = save_dir + '/' + experiment + '/'
    if not os.path.exists(experiment_save_dir):
        os.makedirs(experiment_save_dir)
    for problem in problem_list:
        prob_dir = exp_dir + problem + '/'
        code_list = list(os.listdir(prob_dir))
        code_list = deduplication(prob_dir, code_list, labels=labels)
        asts, datas = [], []
        tk_mp = {}
        gen = 0
        parse_result_path = save_dir + '/' + experiment + '/' + problem + '_ast_raw_data_cc.json'
        if not os.path.exists(parse_result_path):
            dataqueue = data_queue(code_list, prob_dir, work_dir=prob_dir, length=1)
            print('Parsing')
            pbar = tqdm(dataqueue)
            for codes in pbar:
                configs, paths = codes
                config_str = json.dumps(configs)
                for path in paths:
                    pbar.write(path)
                ast_list = parser.parse_to_ast(paths, config_str)
                for idx, ast in enumerate(ast_list):
                    code = paths[idx].split('/')[-1]
                    submission_name = code[:code.find('.')]
                    label = '_'.join(submission_name.split('_')[1:])
                    ast_dump = {}
                    ast_labels = ast.node_labels
                    ast_edges = ast.edges
                    ast_dump['labels'] = ast_labels
                    ast_dump['edges'] = ast_edges
                    ast_dump['label'] = label
                    asts.append(ast_dump)

            with open(parse_result_path, 'w') as fh:
                json.dump(asts, fh)
            print('Parsed result dumped')
        else:
            print('All ready parsed, load from json file')
            with open(parse_result_path, 'r') as fh:
                asts = json.load(fh)
        print('Generating token map...')
        graph_path = save_dir + '/' + experiment + '/' + problem + '_ast_graph.json'
        for ast in asts:
            for label in ast['labels']:
                if label not in tk_mp.keys():
                    tk_mp[label] = gen
                    gen += 1
        print(problem + ' ' + str(len(tk_mp)))
        for ast in asts:
            data = deal_ast(ast, tk_mp)
            if data == -1:
                continue
            datas.append(data)
        with open(graph_path, 'w') as fh:
            json.dump(datas, fh)
    print('Done')


def trans_ctx_graph():
    exp_dir = original_data_dir + '/' + experiment + '/'
    problem_list = list(os.listdir(exp_dir))
    experiment_save_dir = save_dir + '/' + experiment + '/'
    if not os.path.exists(experiment_save_dir):
        os.makedirs(experiment_save_dir)
    for problem in problem_list:
        asts, datas = [], []
        tk_mp = {}
        gen = 0
        parse_result_path = save_dir + '/' + experiment + '/' + problem + '_ast_raw_data_cc.json'
        if not os.path.exists(parse_result_path):
            trans_oj_ast()
        with open(parse_result_path, 'r') as fh:
            asts = json.load(fh)
        print('Generating token map...')
        graph_path = save_dir + '/' + experiment + '/' + problem + '_context_graph.json'
        for ast in asts:
            for label in ast['labels']:
                if label not in tk_mp.keys():
                    tk_mp[label] = gen
                    gen += 1
        print(len(tk_mp))
        for ast in asts:
            data = gen_context_graph(ast, tk_mp)
            if data == -1:
                continue
            datas.append(data)
        print(f'Dump for {problem}')
        with open(graph_path, 'w') as fh:
            json.dump(datas, fh)
    print('Done')


def trans_promise():
    project_list = os.listdir(original_data_dir + '/' + experiment + '/')
    experiment_save_dir = save_dir + '/' + experiment + '/'
    if not os.path.exists(experiment_save_dir):
        os.makedirs(experiment_save_dir)
    tk_mp = {'Stmt': 0}
    idx = 1
    for proj in project_list:
        print(proj)
        parse_result_path = save_dir + '/' + experiment + '/' + proj + '_ast_raw_data_cc.json'
        proj_dir = original_data_dir + '/' + experiment + '/' + proj + '/'
        class_list = os.listdir(proj_dir)
        if not os.path.exists(parse_result_path):
            data_list = []
            for claz in class_list:
                with open(proj_dir + claz, 'r') as rfh:
                    item = json.load(rfh)
                func_result = []
                label = item['label']
                ecfg_list = item['data']
                for cfg in ecfg_list:
                    cfg_dict = {}
                    cfg_edges = cfg['edgeSet']
                    block_list = cfg['blocks']
                    func_name = cfg['method_name']
                    cfg_block_list = []
                    for block in block_list:
                        block_dict = []
                        ast_dict = {}
                        ast_edges = block['edges']
                        ast_labels = block['nodes']
                        ast_defines = block['def']
                        ast_use = block['use']
                        ast_call = block['callees']
                        ast_dict['edges'] = ast_edges
                        ast_dict['labels'] = ast_labels
                        ast_dict['def'] = list(ast_defines)
                        ast_dict['use'] = list(ast_use)
                        ast_dict['calls'] = ast_call
                        block_dict.append(ast_dict)
                        cfg_block_list.append(block_dict)
                    cfg_dict['func_name'] = func_name
                    cfg_dict['cfg_edges'] = cfg_edges
                    cfg_dict['blocks'] = cfg_block_list
                    if with_df:
                        gen_dataflow(cfg_dict)
                    func_result.append(cfg_dict)
                label = '1' if int(label) > 0 else '0'
                data_list.append((func_result, label))

            with open(parse_result_path, 'w') as fh:
                print(proj + " done " + " save")
                json.dump(data_list, fh)

    print('Generate token map')
    for proj in project_list:
        parse_result_path = save_dir + '/' + experiment + '/' + proj + '_ast_raw_data_cc.json'
        with open(parse_result_path, 'r') as fh:
            cfgs = json.load(fh)
        for cfg, label in cfgs:
            for g in cfg:
                for asts in g['blocks']:
                    for t in asts:
                        for tk in t['labels']:
                            if tk not in tk_mp.keys():
                                tk_mp[tk] = idx
                                idx += 1

    map_path = save_dir + '/' + experiment + '/' + 'token_map.json'
    with open(map_path, 'w') as fh:
        json.dump(tk_mp, fh)
    print(len(tk_mp))
    mx_ty = 0
    for proj in project_list:
        parse_result_path = save_dir + '/' + experiment + '/' + proj + '_ast_raw_data_cc.json'
        proj_dir = original_data_dir + '/' + experiment + '/' + proj + '/'
        class_list = os.listdir(proj_dir)
        prob_data_list = []
        pbar = tqdm(enumerate(class_list))
        with open(parse_result_path, 'r') as fh:
            cfgs = json.load(fh)
        for code_id, code in pbar:
            cfg, label = cfgs[code_id]
            pbar.write(code)
            data = merge(func_list=cfg, label=label, token_map=tk_mp)
            if data == -1:
                continue
            data['name'] = code.replace('.json', '')
            prob_data_list.append(data)
            for edge in data['graph']:
                _, _, t = edge
                mx_ty = max(mx_ty, t)
        df_status = 'df' if with_df else 'nodf'
        prob_save_path = save_dir + '/' + experiment + '/' + proj + '_' + df_status + '.json'
        with open(prob_save_path, 'w') as fh:
            print(f'{proj} {df_status} stored in {prob_save_path}')
            json.dump(prob_data_list, fh)


if __name__ == '__main__':
    if experiment == 'promise':
        trans_promise()
    else:
        trans_oj_ast()
        trans_oj_ecfg()
        trans_ctx_graph()

