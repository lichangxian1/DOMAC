import os
import sys
import gc
import logging
import time
from collections import deque
import optuna
from optuna.trial import TrialState
import pandas as pd
import threading 
import torch.multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import torch

from src.core.compressor_tree import DOMAC_CompressorTree
from src.core.objectives import DOMACLossFunction
from src.optimizer.train import DOMACTrainer
from src.optimizer.legalizer import DOMACLegalizer
from src.parser.lib_parser import NLDMParser
from src.core.domac_utils import generate_multiplier_canvas

class HiddenPrints:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

# ================= [你最喜欢的原汁原味丝滑监听器] =================
from tqdm import tqdm
def progress_listener(queue, total_epochs):
    custom_format = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}"
    
    with tqdm(total=total_epochs, desc="[Optuna 终极轰炸]", dynamic_ncols=True, bar_format=custom_format) as pbar:
        while True:
            msg = queue.get()
            if msg == "DONE":
                break
            elif isinstance(msg, dict):
                if 'WNS_探针' in msg:
                    pbar.set_postfix_str(f"最强探针: {msg['WNS_探针']}", refresh=False)
            elif isinstance(msg, int):
                pbar.update(msg)
# =====================================================================

def evaluate_discrete_physical_metrics(model, loss_engine, hyperparams, discrete_M, discrete_P, pp_at, pp_slew, c_types, active_pin_mask):
    with torch.no_grad():
        orig_m_logits = model.m_logits.clone()
        orig_p_logits = model.p_logits.clone()
        orig_dag_mask = model.dag_mask.clone()
        model.dag_mask.fill_(0.0)
        
        discrete_P_tensor = torch.zeros_like(model.p_logits)
        for i, idx in enumerate(discrete_P):
            discrete_P_tensor[i, idx] = 1.0
            
        discrete_M_full = torch.zeros_like(model.m_logits)
        discrete_M_full[:, :-1] = discrete_M
        row_sums = torch.sum(discrete_M, dim=1)
        discrete_M_full[row_sums == 0, -1] = 1.0

        new_m_logits = torch.full_like(orig_m_logits, -1e4)
        new_m_logits[discrete_M_full == 1.0] = 1e4
        model.m_logits.copy_(new_m_logits)

        new_p_logits = torch.full_like(orig_p_logits, -1e4)
        new_p_logits[discrete_P_tensor == 1.0] = 1e4
        model.p_logits.copy_(new_p_logits)

        true_wns, true_tns, true_area, M_internal, P_c = model(pp_at, pp_slew, tau=1.0)
        _, loss_dict = loss_engine(true_wns, true_tns, true_area, M_internal, P_c, hyperparams, active_pin_mask, c_types)
        
        model.m_logits.copy_(orig_m_logits)
        model.p_logits.copy_(orig_p_logits)
        model.dag_mask.copy_(orig_dag_mask)
        
        return true_wns.item(), true_area.item(), loss_dict['l_bm'].item()

# ================= [核心重构：多进程独立 Worker] =================
def optuna_worker_process(storage_url, study_name, fa_tensors, ha_tensors, pp_cols, comp_cols, c_types, bit_width, progress_queue, num_trials):
    """
    这个函数会运行在你原版的 ProcessPoolExecutor 的独立进程中！
    独享 GIL，独享 CUDA 线程，再也不会卡顿！
    """
    # 强制单线程运算防止内部抢占
    torch.set_num_threads(1)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True 
        
    num_pp = len(pp_cols)
    target_sink_count = (bit_width * 2 - 1) * 2
    max_impls = max(len(fa_tensors), len(ha_tensors))
    
    total_nodes = num_pp + 2 * len(comp_cols)
    total_target_pins = len(comp_cols) * 3

    # 在独立的进程里，加载我们那个共享的 SQLite 数据库
    study = optuna.load_study(study_name=study_name, storage=storage_url)

    def objective(trial):
        param_combination = {
            't1': trial.suggest_float('t1', 1.8, 2.6, step=0.1),       
            'lambda1': trial.suggest_float('lambda1', 0.15, 0.25, step=0.01), 
            'lambda2': trial.suggest_float('lambda2', 0.2, 0.6, step=0.05),
            't2': 0.4,         
            'tau_k': 0.9835     
            # 't1': trial.suggest_float('t1', 1.0, 3.0)
        }
        
        FIXED_SEED = 42 
        torch.manual_seed(FIXED_SEED)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(FIXED_SEED)

        init_m_cpu = torch.randn((total_nodes, total_target_pins + 1)) * 0.01
        init_m = init_m_cpu.to(device)
        init_p_cpu = torch.zeros((len(comp_cols), max_impls))
        init_p = init_p_cpu.to(device)
        
        completed_epochs = 0
        MAX_EPOCHS = 300

        def epoch_callback_fn(epoch, current_wns):
            nonlocal completed_epochs
            
            # 恢复原汁原味：每个 Epoch 都推送，保证 UI 极致丝滑！
            STEP = 1
            progress_queue.put(STEP)
            completed_epochs += STEP
            
            if hasattr(current_wns, 'item'):
                current_wns = current_wns.item()
                
            progress_queue.put({'WNS_探针': f"{current_wns:.4f}ns (T{trial.number})"})
            
            # SQLite 的 Report 极快，直接每轮汇报即可
            trial.report(current_wns, epoch)
            if trial.should_prune():
                raise optuna.TrialPruned()

        with HiddenPrints():
            try:
                model = DOMAC_CompressorTree(
                    pp_cols, comp_cols, fa_tensors, ha_tensors, c_types, req_time=0.0, 
                    device=device, init_m_logits=init_m, init_p_logits=init_p
                ).to(device)

                loss_engine = DOMACLossFunction(target_sink_count=target_sink_count)
                trainer = DOMACTrainer(model, loss_engine, lr=0.05)
                trainer.hyperparams.update(param_combination)

                pp_at = torch.full((num_pp,), 0.1, device=device)
                pp_slew = torch.full((num_pp,), 0.02, device=device)

                final_M, final_P = trainer.train(pp_at, pp_slew, max_epochs=MAX_EPOCHS, epoch_callback=epoch_callback_fn)
                
                legalizer = DOMACLegalizer()
                discrete_M, discrete_P = legalizer.legalize(final_M, final_P, c_types, model.dag_mask)
                
                true_wns, true_area, final_l_bm = evaluate_discrete_physical_metrics(
                    model, loss_engine, trainer.hyperparams, discrete_M, discrete_P, pp_at, pp_slew, c_types, model.active_pin_mask
                )
                
                if final_l_bm >= 0.5:
                    return 9.99
                    
            except optuna.TrialPruned:
                raise
            except Exception as e:
                return 9.99
            finally:
                # 完美填补剪枝跳过的进度条
                rem_epochs = MAX_EPOCHS - completed_epochs
                if rem_epochs > 0:
                    progress_queue.put(rem_epochs)
                    
                if 'model' in locals(): del model
                if 'trainer' in locals(): del trainer
                if 'loss_engine' in locals(): del loss_engine
                torch.cuda.empty_cache()
                gc.collect()

        return true_wns + (true_area * 0.0001)

    # 关键：在这个独立的进程里，跑它分到的份额！
    study.optimize(objective, n_trials=num_trials)


def main():
    print("="*70)
    print(" 🧠 [DOMAC Master] Optuna + 纯血多进程并发搜索引擎")
    print("="*70)
    
    with HiddenPrints():
        TARGET_CELLS = ['FA1D1BWP12T40P140', 'HA1D1BWP12T40P140']
        lib_path = "/home/changxian/library/t28_official/tcbn28hpcplusbwp12t40p140tt0p9v25c.lib"
        parser = NLDMParser(lib_path, TARGET_CELLS)
        nldm_db = parser.parse()
        fa_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('FA')]
        ha_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('HA')]
        BIT_WIDTH = 8
        pp_cols, comp_cols, c_types = generate_multiplier_canvas(BIT_WIDTH)

    TOTAL_TRIALS = 60
    CONCURRENT_WORKERS = 8
    
    # 计算每个 Worker 负责多少个 Trial
    trials_per_worker = [TOTAL_TRIALS // CONCURRENT_WORKERS + (1 if x < TOTAL_TRIALS % CONCURRENT_WORKERS else 0) for x in range(CONCURRENT_WORKERS)]

    # ================= [准备 Optuna 共享数据库] =================
    storage_url = "sqlite:///domac_optuna.db"
    study_name = "domac_tuning"
    
    # 每次新跑前，清理上次的旧数据库，确保纯净开局
    if os.path.exists("domac_optuna.db"):
        os.remove("domac_optuna.db")
        
    pruner = optuna.pruners.MedianPruner(n_warmup_steps=50, n_startup_trials=5)
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    # Master 进程先创建好骨架
    study = optuna.create_study(
        study_name=study_name,
        storage=storage_url, 
        direction="minimize", 
        pruner=pruner
    )

    # ================= [启动全局队列与监听线程] =================
    manager = mp.Manager()
    progress_queue = manager.Queue()
    total_global_epochs = TOTAL_TRIALS * 300 
    
    listener_thread = threading.Thread(target=progress_listener, args=(progress_queue, total_global_epochs))
    listener_thread.start()
    
    # ================= [召唤原版 ProcessPoolExecutor] =================
    # 彻底告别 Optuna 的幽灵线程锁，回到最纯正的进程池并发！
    with ProcessPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
        futures = []
        for n_trials in trials_per_worker:
            future = executor.submit(
                optuna_worker_process, 
                storage_url, study_name, fa_tensors, ha_tensors, pp_cols, comp_cols, c_types, BIT_WIDTH, progress_queue, n_trials
            )
            futures.append(future)
            
        for future in as_completed(futures):
            # 捕获可能出现的任何子进程崩溃
            future.result() 

    # 结束监听
    progress_queue.put("DONE")
    listener_thread.join()

    # ================= [输出终极战报] =================
    print("\n\n" + "="*70)
    print(" 🏆 [Auto-Tuner] 贝叶斯寻优结束！最终战报")
    print("="*70)
    
    # 重新从数据库拉取最终结果
    study = optuna.load_study(study_name=study_name, storage=storage_url)
    
    pruned_trials = study.get_trials(deepcopy=False, states=[TrialState.PRUNED])
    complete_trials = study.get_trials(deepcopy=False, states=[TrialState.COMPLETE])

    print(f" -> 总共发起的试验次数: {len(study.trials)}")
    print(f" -> 被智能剪枝节约的次数: {len(pruned_trials)} (极其可观的算力节省！)")
    print(f" -> 完整跑完收敛的次数: {len(complete_trials)}")
    
    best_trial = study.best_trial
    print(f"\n🎯 [全局最强天选参数]")
    print(f" -> 🏆 突破极限 WNS (含面积惩罚): {best_trial.value:.4f} ns")
    print(" -> 最佳超参数组合:")
    for key, value in best_trial.params.items():
        print(f"    * {key}: {value}")

    df = study.trials_dataframe()
    os.makedirs("output", exist_ok=True)
    df.to_csv("output/optuna_tuning_report.csv", index=False)
    print(f"\n📂 详细报告已生成至: output/optuna_tuning_report.csv")

if __name__ == "__main__":
    mp.set_start_method('spawn', force=True)
    main()