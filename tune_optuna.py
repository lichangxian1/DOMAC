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

        # 【修复点 1】: 增加 true_glitch 接收模型输出
        true_wns, true_tns, true_area, true_glitch, M_internal, P_c = model(pp_at, pp_slew, tau=1.0)
        # 【修复点 2】: 将 true_glitch 传入 Loss 引擎
        _, loss_dict = loss_engine(true_wns, true_tns, true_area, true_glitch, M_internal, P_c, hyperparams, active_pin_mask, c_types)
        
        model.m_logits.copy_(orig_m_logits)
        model.p_logits.copy_(orig_p_logits)
        model.dag_mask.copy_(orig_dag_mask)
        
        # 【修复点 3】: 将毛刺功耗一起返回
        return true_wns.item(), true_area.item(), true_glitch.item(), loss_dict['l_bm'].item()

# ================= [核心重构：多进程独立 Worker] =================
# 【修改点 4】: 在函数签名中接收 target_weights 目标权重字典
def optuna_worker_process(storage_url, study_name, fa_tensors, ha_tensors, pp_cols, comp_cols, c_types, bit_width, progress_queue, num_trials, target_weights):
    """
    独立进程 Worker：独享 GIL 和 CUDA
    """
    torch.set_num_threads(1)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True 
        
    num_pp = len(pp_cols)
    target_sink_count = (bit_width * 2 - 1) * 2
    max_impls = max(len(fa_tensors), len(ha_tensors))
    
    total_nodes = num_pp + 2 * len(comp_cols)
    total_target_pins = len(comp_cols) * 3

    # study = optuna.load_study(study_name=study_name, storage=storage_url)
    # 增加数据库写入超时时间至 60 秒，防止高频剪枝导致锁死
    storage = optuna.storages.RDBStorage(
        url=storage_url,
        engine_kwargs={"connect_args": {"timeout": 60}}
    )
    # study = optuna.load_study(study_name=study_name, storage=storage)
    # 【修复点】强制给 Worker 进程也戴上 NopPruner 的紧箍咒！
    study = optuna.load_study(
        study_name=study_name, 
        storage=storage,
        pruner=optuna.pruners.NopPruner()  # <--- 加上这个参数
    )

    def objective(trial):
        # param_combination = {
        #     't1': trial.suggest_float('t1', 1, 4, step=0.05),       
        #     't2': trial.suggest_float('t2', 0.05, 0.5 ,step=0.05),  
        #     'lambda1': trial.suggest_float('lambda1', 0.02, 0.7, step=0.02), 
        #     'lambda2': trial.suggest_float('lambda2', 0.02, 0.7, step=0.02),
        #     'tau_k':0.995,
        #     'seed': 42,
        #     'max_epochs':300,
        #     'init_noise_std': 0.01,
        #     'beta':trial.suggest_float('beta', 0.0001,0.01)  # 新增：毛刺功耗权重，适度关注毛刺下降但不至于过早牺牲性能
        #     # 【新增】把学习率交给贝叶斯寻优，搜索区间 0.01 到 0.1
        #     'lr': trial.suggest_float('lr', 0.01, 0.1, log=True)
        # }
        
        param_combination = {
            't1': 1.5,     # WNS 权重拉到极致，逼迫网络突破延迟极限
            't2': 0.223,       # TNS 辅助全局路径寻优
            'alpha': 1,    # 【封印】前期绝对不许管面积！
            'lambda1': 0.2,  # 连线合法性是必须的
            'lambda2': 0.2,  # 【封印】前期不许进行二值化坍缩！让概率保持连续，充分探索！
            'tau_k':0.995,
            'seed': 42,
            'max_epochs':300,
            'init_noise_std': 0.01,
            'beta': trial.suggest_float('beta', 0.0001,0.01),     # 新增：毛刺功耗权重，适度关注毛刺下降但不至于过早牺牲性能
            'lr': trial.suggest_float('lr', 0.01, 0.1, log=True)
        }

        FIXED_SEED = param_combination['seed']
        torch.manual_seed(FIXED_SEED)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(FIXED_SEED)

        noise_std = param_combination['init_noise_std']
        init_m_cpu = torch.randn((total_nodes, total_target_pins + 1)) * noise_std
        init_m = init_m_cpu.to(device)
        
        init_p_cpu = torch.zeros((len(comp_cols), max_impls))
        init_p = init_p_cpu.to(device)
        
        completed_epochs = 0
        MAX_EPOCHS = param_combination['max_epochs']

        def epoch_callback_fn(epoch, current_wns):
            nonlocal completed_epochs
            
            STEP = 1
            progress_queue.put(STEP)
            completed_epochs += STEP
            
            if hasattr(current_wns, 'item'):
                current_wns = current_wns.item()
                
            progress_queue.put({'WNS_探针': f"{current_wns:.4f}ns (T{trial.number})"})
            
            # 使用目前的 WNS 作为过程剪枝指标依然是最可靠的
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
                trainer = DOMACTrainer(model, loss_engine, lr=param_combination['lr'])
                trainer.hyperparams.update(param_combination)

                pp_at = torch.full((num_pp,), 0.1, device=device)
                pp_slew = torch.full((num_pp,), 0.02, device=device)

                final_M, final_P = trainer.train(pp_at, pp_slew, max_epochs=MAX_EPOCHS, epoch_callback=epoch_callback_fn)
                
                legalizer = DOMACLegalizer()
                discrete_M, discrete_P = legalizer.legalize(final_M, final_P, c_types, model.dag_mask)
                
                # 【修改点 5】: 接收 true_glitch
                true_wns, true_area, true_glitch, final_l_bm = evaluate_discrete_physical_metrics(
                    model, loss_engine, trainer.hyperparams, discrete_M, discrete_P, pp_at, pp_slew, c_types, model.active_pin_mask
                )
                
                if final_l_bm >= 0.5:
                    return 999.0 # 给非法网络施加毁灭性惩罚
                    
            except optuna.TrialPruned:
                raise
            except Exception as e:
                return 999.0
            finally:
                rem_epochs = MAX_EPOCHS - completed_epochs
                if rem_epochs > 0:
                    progress_queue.put(rem_epochs)
                    
                if 'model' in locals(): del model
                if 'trainer' in locals(): del trainer
                if 'loss_engine' in locals(): del loss_engine
                torch.cuda.empty_cache()
                gc.collect()

        # =========================================================================
        # 👑 【核心修改点 6】: 基于用户自定义权重的线性组合目标函数
        # =========================================================================
        final_score = (
            target_weights.get('wns', 1.0) * true_wns +
            target_weights.get('area', 0.0) * true_area +
            target_weights.get('glitch', 0.0) * true_glitch
        )
        return final_score

    study.optimize(objective, n_trials=num_trials)


def main():
    print("="*70)
    print(" 🧠 [DOMAC Master] Optuna + 多维目标融合搜索雷达")
    print("="*70)
    
    # =========================================================================
    # 🎯 【全新控制台】在此定义你想要优化的目标（任意线性组合）
    # =========================================================================
    # 案例 1: 纯时序极限突破 (WNS 唯一目标)
    # TARGET_WEIGHTS = {'wns': 1.0, 'area': 0.0, 'glitch': 0.0}
    
    # 案例 2: PPA 综合考量 (时序为主，极其轻微的面积惩罚防止无脑堆大门)
    # TARGET_WEIGHTS = {'wns': 1.0, 'area': 0.0001, 'glitch': 0.0}
    
    # 案例 3: 功耗-时序双雄博弈 (压制毛刺方差的同时保住时序)
    # 注意: Glitch (方差) 数值极小 (0.0001~0.01级别)，因此需要给它 10.0 ~ 100.0 的高权重才能与 WNS(0.7ns级别) 抗衡
    TARGET_WEIGHTS = {
        'wns': 0, 
        'area': 0.0000, 
        'glitch': 1.0 
    }
    
    print(f" [Target] 当前优化目标权重: WNS({TARGET_WEIGHTS.get('wns', 0)}), Area({TARGET_WEIGHTS.get('area', 0)}), Glitch({TARGET_WEIGHTS.get('glitch', 0)})")
    
    with HiddenPrints():
        TARGET_CELLS = ['FA1D0BWP12T40P140', 'HA1D0BWP12T40P140','FA1D1BWP12T40P140', 'HA1D1BWP12T40P140','FA1D2BWP12T40P140', 'HA1D2BWP12T40P140','FA1D4BWP12T40P140', 'HA1D4BWP12T40P140']
        lib_path = "/home/changxian/library/t28_official/tcbn28hpcplusbwp12t40p140tt0p9v25c.lib"
        parser = NLDMParser(lib_path, TARGET_CELLS)
        nldm_db = parser.parse()
        fa_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('FA')]
        ha_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('HA')]
        BIT_WIDTH = 8
        pp_cols, comp_cols, c_types = generate_multiplier_canvas(BIT_WIDTH)

    TOTAL_TRIALS = 500
    CONCURRENT_WORKERS = 6
    
    trials_per_worker = [TOTAL_TRIALS // CONCURRENT_WORKERS + (1 if x < TOTAL_TRIALS % CONCURRENT_WORKERS else 0) for x in range(CONCURRENT_WORKERS)]

    storage_url = f"sqlite:///domac_optuna_{BIT_WIDTH}bit.db"
    study_name = f"domac_tuning_{BIT_WIDTH}bit"
        
    # pruner = optuna.pruners.MedianPruner(n_warmup_steps=200, n_startup_trials=50)
    # 不剪枝，让每个试验都跑满 300 Epoch，充分挖掘潜力（尤其是毛刺优化可能需要较长时间才能显现效果）
    pruner = optuna.pruners.NopPruner()
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    study = optuna.create_study(
        study_name=study_name,
        storage=storage_url, 
        direction="minimize", 
        pruner=pruner,
        load_if_exists=True
    )

    manager = mp.Manager()
    progress_queue = manager.Queue()
    total_global_epochs = TOTAL_TRIALS * 300 
    
    listener_thread = threading.Thread(target=progress_listener, args=(progress_queue, total_global_epochs))
    listener_thread.daemon = True
    listener_thread.start()
    
    with ProcessPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
        futures = []
        for n_trials in trials_per_worker:
            # 【修改点 7】: 将 TARGET_WEIGHTS 安全地传递给子进程 Worker
            future = executor.submit(
                optuna_worker_process, 
                storage_url, study_name, fa_tensors, ha_tensors, pp_cols, comp_cols, c_types, BIT_WIDTH, progress_queue, n_trials, TARGET_WEIGHTS
            )
            futures.append(future)
            
        for future in as_completed(futures):
            future.result() 

    progress_queue.put("DONE")
    listener_thread.join()

    print("\n\n" + "="*70)
    print(" 🏆 [Auto-Tuner] 贝叶斯寻优结束！最终战报")
    print("="*70)
    
    study = optuna.load_study(study_name=study_name, storage=storage_url)
    
    pruned_trials = study.get_trials(deepcopy=False, states=[TrialState.PRUNED])
    complete_trials = study.get_trials(deepcopy=False, states=[TrialState.COMPLETE])

    print(f" -> 总共发起的试验次数: {len(study.trials)}")
    print(f" -> 被智能剪枝节约的次数: {len(pruned_trials)}")
    print(f" -> 完整跑完收敛的次数: {len(complete_trials)}")
    
    if len(complete_trials) > 0:
        best_trial = study.best_trial
        print(f"\n🎯 [全局最强天选参数]")
        print(f" -> 🏆 突破极限综合得分 (WNS/Area/Glitch 加权和): {best_trial.value:.6f}")
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