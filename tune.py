
import os
import sys
import gc
import itertools
import numpy as np
import pandas as pd
import multiprocessing as mp
import threading # 新增：用于后台跑进度条
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm  

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import torch
from src.parser.lib_parser import NLDMParser
from src.core.compressor_tree import DOMAC_CompressorTree
from src.core.objectives import DOMACLossFunction
from src.optimizer.train import DOMACTrainer
from src.optimizer.legalizer import DOMACLegalizer
from domac import generate_multiplier_canvas

class HiddenPrints:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

# ================= [新增：独立的进度条监听线程] =================
def progress_listener(queue, total_epochs):
    """
    运行在主进程的后台线程：监听所有子进程发来的进度包，更新全局 tqdm。
    """
    # tqdm 默认输出到 stderr，不会被 HiddenPrints 拦截，完美契合
    with tqdm(total=total_epochs, desc="[CUDA Epoch 寻优轰炸]", unit="ep", dynamic_ncols=True) as pbar:
        while True:
            msg = queue.get()
            if msg == "DONE":
                break
            elif isinstance(msg, dict):
                # 收到子进程发来的最新 WNS 状态字典，更新后缀
                pbar.set_postfix(msg)
            elif isinstance(msg, int):
                # 收到 Epoch 数量步进
                pbar.update(msg)
# ================================================================

def evaluate_discrete_physical_metrics(model, loss_engine, hyperparams, discrete_M, discrete_P, pp_at, pp_slew, c_types, active_pin_mask):
    # [原有逻辑保持不变]
    with torch.no_grad():
        orig_m_logits = model.m_logits.clone()
        orig_p_logits = model.p_logits.clone()
        orig_dag_mask = model.dag_mask.clone()
        model.dag_mask.fill_(0.0)
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
    并行工作节点的核心函数：接收进度队列，定时回传心跳。
    """
    param_combination, fa_tensors, ha_tensors, pp_cols, comp_cols, c_types, bit_width, progress_queue = task_args
    
    torch.set_num_threads(1)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    num_pp = len(pp_cols)
    target_sink_count = (bit_width * 2 - 1) * 2
    max_impls = max(len(fa_tensors), len(ha_tensors))
    
    total_nodes = num_pp + 2 * len(comp_cols)
    total_target_pins = len(comp_cols) * 3
    init_m = torch.randn((total_nodes, total_target_pins + 1), device=device) * 0.5
    init_p = torch.zeros((len(comp_cols), max_impls), device=device)
    
    completed_epochs = 0
    MAX_EPOCHS = 300

    # ================= [新增：动态向主进程队列投递进度的回调函数] =================
    def epoch_callback_fn(epoch, current_wns):
        nonlocal completed_epochs
        # epoch 是 0-indexed (0~299)
        # 每满 20 个 epoch，向主进程抛出一个 +20 的进度信号
        if (epoch + 1) % 20 == 0:
            progress_queue.put(20)
            completed_epochs += 20
            # 顺便抛出当前的 WNS 状态，让主进程进度条尾部动态闪烁
            if hasattr(current_wns, 'item'):
                current_wns = current_wns.item()
            progress_queue.put({'WNS_探针': f"{current_wns:.3f}ns"})
    # ==============================================================================

    with HiddenPrints():
        try:
            model = DOMAC_CompressorTree(
                pp_cols, comp_cols, fa_tensors, ha_tensors, c_types, req_time=0.0, 
                device=device, init_m_logits=init_m, init_p_logits=init_p
            ).to(device)

            loss_engine = DOMACLossFunction(target_sink_count=target_sink_count)
            trainer = DOMACTrainer(model, loss_engine, lr=0.05)
            
            trainer.hyperparams.update({'t1': 20.0, 't2': 2.0, 'lambda1': 10.0})
            trainer.hyperparams.update(param_combination)

            pp_at = torch.zeros(num_pp, device=device) 
            pp_slew = torch.full((num_pp,), 0.02, device=device)

            # 将回调函数挂载进去
            final_M, final_P = trainer.train(pp_at, pp_slew, max_epochs=MAX_EPOCHS, epoch_callback=epoch_callback_fn)
            
            legalizer = DOMACLegalizer()
            discrete_M, discrete_P = legalizer.legalize(final_M, final_P, c_types, model.dag_mask)
            true_wns, true_area, final_l_bm = evaluate_discrete_physical_metrics(
                model, loss_engine, trainer.hyperparams, discrete_M, discrete_P, pp_at, pp_slew, c_types, model.active_pin_mask
            )
            status = "SUCCESS" if final_l_bm < 0.5 else "MODE_COLLAPSE"
            
        except Exception as e:
            true_wns, true_area, final_l_bm, status = 9.99, 0.0, 999.0, f"CRASHED: {e}"
            
        finally:
            # 安全兜底：如果训练崩溃或未跑满，把剩余的 Epoch 一次性填入进度条防止卡死
            rem_epochs = MAX_EPOCHS - completed_epochs
            if rem_epochs > 0:
                progress_queue.put(rem_epochs)
                
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
    
    MAX_CONCURRENT_WORKERS = 8 
    
    TUNING_CONFIG = {
        't1':{'start': 0, 'end': 4, 'step': 0.2},     # WNS 权重
        # 't2': {'start': 0, 'end': 2, 'step': 0.1}       # TNS 
        # 'alpha':{'start': 0, 'end': 2, 'step': 0.1}  # 面积！
        # 'lambda1':{'start': 0.02, 'end': 0.3, 'step': 0.02},  # 连线合法性
        # 'lambda2':{'start': 0.3, 'end': 0.8, 'step': 0.05}  # 二值化
        'tau_k':{'start': 0.97, 'end': 0.99, 'step': 0.005},  # 降温系数
    }
    
    keys = list(TUNING_CONFIG.keys())
    value_lists = [np.arange(cfg['start'], cfg['end'] + cfg['step'] * 0.1, cfg['step']).tolist() for cfg in TUNING_CONFIG.values()]
    combinations = list(itertools.product(*value_lists))
    print(f"[System] 检测到 {len(combinations)} 组超参数对，将启动 {MAX_CONCURRENT_WORKERS} 个并行核进击搜索...")
    
    with HiddenPrints():
        TARGET_CELLS = ['FA1D0BWP12T40P140', 'HA1D0BWP12T40P140']
        lib_path = "/home/changxian/library/t28_official/tcbn28hpcplusbwp12t40p140tt0p9v25c.lib"
        parser = NLDMParser(lib_path, TARGET_CELLS)
        nldm_db = parser.parse()
        fa_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('FA')]
        ha_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('HA')]
        BIT_WIDTH = 8
        pp_cols, comp_cols, c_types = generate_multiplier_canvas(BIT_WIDTH)
    
    # ================= [配置多进程通信队列] =================
    manager = mp.Manager()
    progress_queue = manager.Queue()
    
    # 所有任务要跑的总 Epoch 数
    total_global_epochs = len(combinations) * 300 
    
    # 启动后台监听线程
    listener_thread = threading.Thread(target=progress_listener, args=(progress_queue, total_global_epochs))
    listener_thread.start()
    # ========================================================

    tasks = [(dict(zip(keys, combo)), fa_tensors, ha_tensors, pp_cols, comp_cols, c_types, BIT_WIDTH, progress_queue) for combo in combinations]
    results = []
    
    with ProcessPoolExecutor(max_workers=MAX_CONCURRENT_WORKERS) as executor:
        future_to_param = {executor.submit(parallel_worker_task, task): task[0] for task in tasks}
        
        # 主线程等待所有 future 执行完毕即可，进度条已完全交由监听线程托管
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

    # 发送结束信号并回收监听线程
    progress_queue.put("DONE")
    listener_thread.join()

    # 数据汇总部分保持不变
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
    mp.set_start_method('spawn', force=True)
    main()