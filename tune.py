import os
import sys
import gc
import itertools
import numpy as np
import pandas as pd
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm  # 用于显示优雅的全局进度条

# 确保能扫到你的 src 模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import torch
from src.parser.lib_parser import NLDMParser
from src.core.compressor_tree import DOMAC_CompressorTree
from src.core.objectives import DOMACLossFunction
from src.optimizer.train import DOMACTrainer
from src.optimizer.legalizer import DOMACLegalizer
from domac import generate_multiplier_canvas

class HiddenPrints:
    """
    终端输出消音器：在多进程并发时拦截标准输出，
    防止成百上千个 Epoch 打印交织在一起导致终端崩溃。
    """
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

def evaluate_discrete_physical_metrics(model, loss_engine, hyperparams, discrete_M, discrete_P, pp_at, pp_slew, c_types, active_pin_mask):
    """
    【核心核算器】带 Sink 列自动补齐功能的离散网表验证器
    """
    with torch.no_grad():
        orig_m_logits = model.m_logits.clone()
        orig_p_logits = model.p_logits.clone()
        orig_dag_mask = model.dag_mask.clone()
        
        model.dag_mask.fill_(0.0)
        
        # 补齐 discrete_M 丢失的 Sink 列
        full_discrete_M = torch.zeros_like(model.m_logits)
        full_discrete_M[:, :-1] = discrete_M
        
        row_sums = torch.sum(discrete_M, dim=1)
        unconnected_mask = (row_sums < 0.5) 
        full_discrete_M[unconnected_mask, -1] = 1.0
        
        model.m_logits.copy_(full_discrete_M * 100.0)
        
        P_onehot = torch.zeros_like(model.p_logits)
        for j, impl_idx in enumerate(discrete_P):
            P_onehot[j, impl_idx] = 1.0
        model.p_logits.copy_(P_onehot * 100.0)
        
        true_wns, true_tns, true_area, M_internal, P_c = model(pp_at, pp_slew, tau=1.0)
        _, loss_dict = loss_engine(true_wns, true_tns, true_area, M_internal, P_c, hyperparams, active_pin_mask, c_types)
        
        model.m_logits.copy_(orig_m_logits)
        model.p_logits.copy_(orig_p_logits)
        model.dag_mask.copy_(orig_dag_mask)
        
        return true_wns.item(), true_area.item(), loss_dict['l_bm'].item()

def parallel_worker_task(task_args):
    """
    并行工作节点的核心函数：完全隔离的物理空间
    """
    param_combination, fa_tensors, ha_tensors, pp_cols, comp_cols, c_types, bit_width = task_args
    
    # 【性能优化】限制 PyTorch 内部的 CPU 线程数，防止多进程抢夺 CPU 导致死锁
    torch.set_num_threads(1)
    
    # 独立获取 GPU 句柄
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    num_pp = len(pp_cols)
    target_sink_count = (bit_width * 2 - 1) * 2
    max_impls = max(len(fa_tensors), len(ha_tensors))
    
    # 强制开启高斯噪声冷启动
    total_nodes = num_pp + 2 * len(comp_cols)
    total_target_pins = len(comp_cols) * 3
    init_m = torch.randn((total_nodes, total_target_pins + 1), device=device) * 0.5
    init_p = torch.zeros((len(comp_cols), max_impls), device=device)
    
    # 在消音器内部执行长达 300 Epoch 的轰炸
    with HiddenPrints():
        try:
            model = DOMAC_CompressorTree(
                pp_cols, comp_cols, fa_tensors, ha_tensors, c_types, req_time=0.0, 
                device=device, init_m_logits=init_m, init_p_logits=init_p
            ).to(device)

            loss_engine = DOMACLossFunction(target_sink_count=target_sink_count)
            trainer = DOMACTrainer(model, loss_engine, lr=0.05)
            
            # 注入参数
            trainer.hyperparams['t1'] = 20.0
            trainer.hyperparams['t2'] = 2.0
            trainer.hyperparams['lambda1'] = 10.0
            for k, v in param_combination.items():
                trainer.hyperparams[k] = v

            pp_at = torch.zeros(num_pp, device=device) 
            pp_slew = torch.full((num_pp,), 0.02, device=device)

            final_M, final_P = trainer.train(pp_at, pp_slew, max_epochs=300)
            
            legalizer = DOMACLegalizer()
            discrete_M, discrete_P = legalizer.legalize(final_M, final_P, c_types, model.dag_mask)
            
            true_wns, true_area, final_l_bm = evaluate_discrete_physical_metrics(
                model, loss_engine, trainer.hyperparams, 
                discrete_M, discrete_P, pp_at, pp_slew, 
                c_types, model.active_pin_mask
            )
            
            status = "SUCCESS" if final_l_bm < 0.5 else "MODE_COLLAPSE"
            
        except Exception as e:
            true_wns, true_area, final_l_bm, status = 9.99, 0.0, 999.0, f"CRASHED: {e}"
            
        finally:
            # 暴力清理该进程的显存驻留
            if 'model' in locals(): del model
            if 'trainer' in locals(): del trainer
            if 'loss_engine' in locals(): del loss_engine
            torch.cuda.empty_cache()
            gc.collect()

    return param_combination, true_wns, true_area, final_l_bm, status


def main():
    print("="*70)
    print(" [DOMAC Cluster] 大规模并行网格搜索引擎 (Multi-Process CUDA版)")
    print("="*70)
    
    # ================= [集群并发度配置] =================
    # RTX 3090 (24GB) 能够轻松容纳 6-8 个 8x8 乘法器的并发寻优任务
    MAX_CONCURRENT_WORKERS = 8 
    # ====================================================
    
    TUNING_CONFIG = {
        't1': {'start': 0, 'end': 2, 'step': 0.1},
        # 'tau_k': {'start': 0.97, 'end': 0.99, 'step': 0.01}
    }
    
    keys = list(TUNING_CONFIG.keys())
    value_lists = []
    for k in keys:
        cfg = TUNING_CONFIG[k]
        vals = np.arange(cfg['start'], cfg['end'] + cfg['step'] * 0.1, cfg['step']).tolist()
        value_lists.append(vals)
        
    combinations = list(itertools.product(*value_lists))
    print(f"[System] 检测到 {len(combinations)} 组超参数对，将启动 {MAX_CONCURRENT_WORKERS} 个并行核进击搜索...")
    
    # 1. 在主进程中仅解析一次物理库 (转为 CPU Tensor 防止跨进程死锁)
    with HiddenPrints():
        TARGET_CELLS = ['FA1D0BWP12T40P140', 'HA1D0BWP12T40P140']
        lib_path = "/home/changxian/library/t28_official/tcbn28hpcplusbwp12t40p140tt0p9v25c.lib"
        parser = NLDMParser(lib_path, TARGET_CELLS)
        nldm_db = parser.parse()
        fa_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('FA') and c in nldm_db]
        ha_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('HA') and c in nldm_db]
        
        BIT_WIDTH = 8
        pp_cols, comp_cols, c_types = generate_multiplier_canvas(BIT_WIDTH)
    
    # 2. 组装并行任务包
    tasks = []
    for combo_vals in combinations:
        current_params = dict(zip(keys, combo_vals))
        tasks.append((current_params, fa_tensors, ha_tensors, pp_cols, comp_cols, c_types, BIT_WIDTH))
        
    results = []
    
    # 3. 发起进程池 CUDA 并行轰炸
    with ProcessPoolExecutor(max_workers=MAX_CONCURRENT_WORKERS) as executor:
        # 提交所有任务
        future_to_param = {executor.submit(parallel_worker_task, task): task[0] for task in tasks}
        
        # 使用 tqdm 构建漂亮的终端动态进度条
        with tqdm(total=len(tasks), desc="[CUDA Matrix Search]", unit="组", dynamic_ncols=True) as pbar:
            for future in as_completed(future_to_param):
                param_combination, wns, area, l_bm, status = future.result()
                
                row_data = param_combination.copy()
                row_data.update({
                    'True_WNS(ns)': round(wns, 4),
                    'True_Area(μm²)': round(area, 4),
                    'Final_L_BM': round(l_bm, 4),
                    'Status': status
                })
                results.append(row_data)
                
                # 更新进度条后面的状态栏，实时显示刚才跑出的这一组的结果
                pbar.set_postfix({"WNS": f"{wns:.3f}", "L_BM": f"{l_bm:.1f}", "Stat": status})
                pbar.update(1)
                
    # 4. 数据汇总
    df = pd.DataFrame(results)
    df_sorted = df.sort_values(by=['Status', 'True_WNS(ns)'], ascending=[False, True])
    
    print("\n\n" + "="*70)
    print(" 🏆 [Auto-Tuner] 大规模并行搜索完成！报告汇总 (按最优 WNS 排序)")
    print("="*70)
    print(df_sorted.to_string(index=False))
    
    os.makedirs("output", exist_ok=True)
    df_sorted.to_csv("output/parallel_tuning_report.csv", index=False)
    
    valid_df = df_sorted[df_sorted['Status'] == 'SUCCESS']
    if not valid_df.empty:
        best_run = valid_df.iloc[0]
        print("\n🎯 [全局最优解推荐]")
        for k in keys:
            print(f"   -> {k} = {best_run[k]}")
        print(f"   该组合下生成的网表物理极限 WNS 为: {best_run['True_WNS(ns)']} ns")

if __name__ == "__main__":
    # 【PyTorch 并发核心】强制使用 spawn 启动进程，否则子进程初始化 CUDA 上下文必崩
    mp.set_start_method('spawn', force=True)
    main()