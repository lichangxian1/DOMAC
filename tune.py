import os
import sys
import gc
import itertools
import numpy as np
import pandas as pd
import multiprocessing as mp
import threading 
import time
from collections import deque  # <--- 新增导入
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

# ================= [修改 2：替换 progress_listener 函数] =================
def progress_listener(queue, total_epochs):
    # 使用自定义格式，隐藏默认的 ETA 和速度，通过 postfix 注入我们自己计算的 5秒平均值
    custom_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{postfix}]"
    
    with tqdm(total=total_epochs, desc="[CUDA Epoch 寻优轰炸]", dynamic_ncols=True, bar_format=custom_format) as pbar:
        # history 队列存储元组: (timestamp, 已完成的 epochs 数量)
        history = deque()
        history.append((time.time(), 0))
        current_wns = "N/A"
        
        while True:
            msg = queue.get()
            if msg == "DONE":
                break
            elif isinstance(msg, dict):
                if 'WNS_探针' in msg:
                    current_wns = msg['WNS_探针']
            elif isinstance(msg, int):
                pbar.update(msg)
            
            # --- 5秒滑动窗口计算逻辑 ---
            current_t = time.time()
            current_n = pbar.n
            history.append((current_t, current_n))
            
            # 清理超过 5 秒的历史记录，但至少保留最旧的一个点用来算速度
            while len(history) > 1 and (current_t - history[0][0]) > 5.0:
                history.popleft()
            
            time_diff = current_t - history[0][0]
            if time_diff > 0:
                speed = (current_n - history[0][1]) / time_diff
            else:
                speed = 0.0
            
            # 计算动态 ETA
            if speed > 0:
                eta_sec = (total_epochs - current_n) / speed
                m, s = divmod(int(eta_sec), 60)
                h, m = divmod(m, 60)
                if h > 0:
                    eta_str = f"{h:02d}:{m:02d}:{s:02d}"
                else:
                    eta_str = f"{m:02d}:{s:02d}"
            else:
                eta_str = "??"
                
            # 格式化输出字符串：例如 "19:38:56,  2.12ep/s, WNS_探针=0.3705ns"
            postfix_str = f"{eta_str}, {speed:.2f}ep/s, WNS_探针={current_wns}"
            
            # 注入自定义的 postfix (无需刷新，下次 update 时会自动渲染)
            pbar.set_postfix_str(postfix_str, refresh=False)

# ================= [对齐 3：100% 对齐 domac.py 的 1e4 极端硬化验证逻辑] =================
def evaluate_discrete_physical_metrics(model, loss_engine, hyperparams, discrete_M, discrete_P, pp_at, pp_slew, c_types, active_pin_mask):
    with torch.no_grad():
        orig_m_logits = model.m_logits.clone()
        orig_p_logits = model.p_logits.clone()
        orig_dag_mask = model.dag_mask.clone()
        model.dag_mask.fill_(0.0)
        
        # 构造离散化物理尺寸的 One-Hot 张量
        discrete_P_tensor = torch.zeros_like(model.p_logits)
        for i, idx in enumerate(discrete_P):
            discrete_P_tensor[i, idx] = 1.0
            
        # 构造包含 Sink 的 M 矩阵
        discrete_M_full = torch.zeros_like(model.m_logits)
        discrete_M_full[:, :-1] = discrete_M
        row_sums = torch.sum(discrete_M, dim=1)
        discrete_M_full[row_sums == 0, -1] = 1.0

        # [核心修复] 使用和 domac.py 一模一样的 -1e4/1e4 暴力硬化，杜绝小数泄露
        new_m_logits = torch.full_like(orig_m_logits, -1e4)
        new_m_logits[discrete_M_full == 1.0] = 1e4
        model.m_logits.copy_(new_m_logits)

        new_p_logits = torch.full_like(orig_p_logits, -1e4)
        new_p_logits[discrete_P_tensor == 1.0] = 1e4
        model.p_logits.copy_(new_p_logits)

        true_wns, true_tns, true_area, M_internal, P_c = model(pp_at, pp_slew, tau=1.0)
        _, loss_dict = loss_engine(true_wns, true_tns, true_area, M_internal, P_c, hyperparams, active_pin_mask, c_types)
        
        # 恢复现场
        model.m_logits.copy_(orig_m_logits)
        model.p_logits.copy_(orig_p_logits)
        model.dag_mask.copy_(orig_dag_mask)
        
        return true_wns.item(), true_area.item(), loss_dict['l_bm'].item()

def parallel_worker_task(task_args):
    param_combination, fa_tensors, ha_tensors, pp_cols, comp_cols, c_types, bit_width, progress_queue = task_args
    
    torch.set_num_threads(1)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # ================= [对齐 4：同步开启 CuDNN 加速] =================
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True 
        
    num_pp = len(pp_cols)
    target_sink_count = (bit_width * 2 - 1) * 2
    max_impls = max(len(fa_tensors), len(ha_tensors))
    
    FIXED_SEED = 42 
    torch.manual_seed(FIXED_SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(FIXED_SEED)

    total_nodes = num_pp + 2 * len(comp_cols)
    total_target_pins = len(comp_cols) * 3
    
    # ================= [对齐 1：严格复刻 domac.py，先在 CPU 生成噪声，再送到 GPU！] =================
    init_m_cpu = torch.randn((total_nodes, total_target_pins + 1)) * 0.5
    init_m = init_m_cpu.to(device)
    init_p_cpu = torch.zeros((len(comp_cols), max_impls))
    init_p = init_p_cpu.to(device)
    # ==============================================================================================
    
    completed_epochs = 0
    MAX_EPOCHS = 300

    def epoch_callback_fn(epoch, current_wns):
        nonlocal completed_epochs
        STEP = 1
        if (epoch + 1) % STEP == 0:
            progress_queue.put(STEP)
            completed_epochs += STEP
            if hasattr(current_wns, 'item'):
                current_wns = current_wns.item()
            progress_queue.put({'WNS_探针': f"{current_wns:.4f}ns"})

    with HiddenPrints():
        try:
            model = DOMAC_CompressorTree(
                pp_cols, comp_cols, fa_tensors, ha_tensors, c_types, req_time=0.0, 
                device=device, init_m_logits=init_m, init_p_logits=init_p
            ).to(device)

            loss_engine = DOMACLossFunction(target_sink_count=target_sink_count)
            # ================= [对齐 2：恢复 0.05 学习率] =================
            trainer = DOMACTrainer(model, loss_engine, lr=0.05)
            # ==============================================================
            
            trainer.hyperparams.update(param_combination)

            pp_at = torch.full((num_pp,), 0.1, device=device)
            pp_slew = torch.full((num_pp,), 0.02, device=device)

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
    
    MAX_CONCURRENT_WORKERS = 12 
    
    # TUNING_CONFIG = {
    #     # 't1':{'start': 0, 'end': 4, 'step': 0.2},     # WNS 权重
    #     # 't2': {'start': 0, 'end': 2, 'step': 0.1}       # TNS 
    #     # 'alpha':{'start': 0, 'end': 2, 'step': 0.1}  # 面积！
    #     # 'lambda1':{'start': 0.02, 'end': 0.3, 'step': 0.02},  # 连线合法性
    #     # 'lambda2':{'start': 0.2, 'end': 0.8, 'step': 0.05}  # 二值化
    #     # 'tau_k':{'start': 0.97, 'end': 0.99, 'step': 0.005},  # 降温系数
    # }
    
# 总组合数: 5 * 5 * 1 * 4 * 5 * 1 = 500 组并行仿真
    TUNING_CONFIG = {
        # [轴 1: 物理极限压榨与寄生电容的高精微雕 (25宫格)]
        't1':      {'start': 1.4,  'end': 2.2,  'step': 0.2},  # 5组: [1.4, 1.6, 1.8, 2.0, 2.2]
        # 'alpha':   {'start': 0.6,  'end': 1.4,  'step': 0.2},  # 5组: [0.6, 0.8, 1.0, 1.2, 1.4]
        
        # [被彻底冻结的次要与环境参数]
        't2':      {'start': 0.1,  'end': 0.1,  'step': 1.0},  # 1组: [0.1] (仅作路径清理，无需调)
        'tau_k':   {'start': 0.981,'end': 0.990,'step': 0.0025},  # 1组: [0.985] (最稳健的探索期底座)
        
        # [轴 2: 拓扑合法性与离散坍缩的“走钢丝”极限测试]
        'lambda1': {'start': 0.15, 'end': 0.21, 'step': 0.02}, # 4组: [0.15, 0.17, 0.19, 0.21]
        'lambda2': {'start': 0.3,  'end': 0.7,  'step': 0.1},  # 5组: [0.3, 0.4, 0.5, 0.6, 0.7]
    }

    keys = list(TUNING_CONFIG.keys())
    value_lists = [np.arange(cfg['start'], cfg['end'] + cfg['step'] * 0.1, cfg['step']).tolist() for cfg in TUNING_CONFIG.values()]
    combinations = list(itertools.product(*value_lists))
    print(f"[System] 检测到 {len(combinations)} 组超参数对，将启动 {MAX_CONCURRENT_WORKERS} 个并行核进击搜索...")
    
    with HiddenPrints():
        TARGET_CELLS = ['FA1D1BWP12T40P140', 'HA1D1BWP12T40P140']
        lib_path = "/home/changxian/library/t28_official/tcbn28hpcplusbwp12t40p140tt0p9v25c.lib"
        parser = NLDMParser(lib_path, TARGET_CELLS)
        nldm_db = parser.parse()
        fa_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('FA')]
        ha_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('HA')]
        BIT_WIDTH = 8
        pp_cols, comp_cols, c_types = generate_multiplier_canvas(BIT_WIDTH)
    
    manager = mp.Manager()
    progress_queue = manager.Queue()
    
    total_global_epochs = len(combinations) * 300 
    
    listener_thread = threading.Thread(target=progress_listener, args=(progress_queue, total_global_epochs))
    listener_thread.start()

    tasks = [(dict(zip(keys, combo)), fa_tensors, ha_tensors, pp_cols, comp_cols, c_types, BIT_WIDTH, progress_queue) for combo in combinations]
    results = []
    
    with ProcessPoolExecutor(max_workers=MAX_CONCURRENT_WORKERS) as executor:
        future_to_param = {executor.submit(parallel_worker_task, task): task[0] for task in tasks}
        
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

    progress_queue.put("DONE")
    listener_thread.join()

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