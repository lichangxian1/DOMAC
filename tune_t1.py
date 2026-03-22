import os
import sys
import time
import torch
import gc
import pandas as pd

# 确保能扫到你的 src 模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.parser.lib_parser import NLDMParser
from src.core.compressor_tree import DOMAC_CompressorTree
from src.core.objectives import DOMACLossFunction
from src.optimizer.train import DOMACTrainer
from src.optimizer.legalizer import DOMACLegalizer
from domac import generate_multiplier_canvas

def evaluate_discrete_physical_metrics(model, loss_engine, hyperparams, discrete_M, discrete_P, pp_at, pp_slew, c_types, active_pin_mask):
    """
    【核心核算器】将 Legalizer 产生的 0/1 离散矩阵强行注入计算图
    """
    with torch.no_grad():
        # 1. 备份
        orig_m_logits = model.m_logits.clone()
        orig_p_logits = model.p_logits.clone()
        orig_dag_mask = model.dag_mask.clone()
        
        # 2. 解除封印
        model.dag_mask.fill_(0.0)
        
        # ==================== [高危 Bug 修复区] ====================
        # 因为传进来的 discrete_M 缺少了通向 Sink 的最后一列
        # 我们需要把它补齐！
        
        # 先创建一个全零的，形状和 m_logits 完全一样的矩阵
        full_discrete_M = torch.zeros_like(model.m_logits)
        
        # 把前面的列（连接到压缩器的列）填进去
        full_discrete_M[:, :-1] = discrete_M
        
        # 接下来，计算哪些节点没有连接到任何压缩器？
        # 把它们的最后一列 (Sink列) 置为 1.0
        row_sums = torch.sum(discrete_M, dim=1)
        unconnected_mask = (row_sums < 0.5) 
        full_discrete_M[unconnected_mask, -1] = 1.0
        
        # 3. 强注入补齐后的完整矩阵
        model.m_logits.copy_(full_discrete_M * 100.0)
        # ===========================================================
        
        # 4. 构造 P_discrete 的 one-hot 矩阵并强注入
        P_onehot = torch.zeros_like(model.p_logits)
        for j, impl_idx in enumerate(discrete_P):
            P_onehot[j, impl_idx] = 1.0
        model.p_logits.copy_(P_onehot * 100.0)
        
        # 5. 执行一次纯净的前向推演 (tau=1.0)
        true_wns, true_tns, true_area, M_internal, P_c = model(pp_at, pp_slew, tau=1.0)
        
        # 6. 计算真实 Loss
        _, loss_dict = loss_engine(true_wns, true_tns, true_area, M_internal, P_c, hyperparams, active_pin_mask, c_types)
        
        # 7. 恢复现场
        model.m_logits.copy_(orig_m_logits)
        model.p_logits.copy_(orig_p_logits)
        model.dag_mask.copy_(orig_dag_mask)
        
        return true_wns.item(), true_area.item(), loss_dict['l_bm'].item()

def run_single_experiment(t1_value, device, fa_tensors, ha_tensors, pp_cols, comp_cols, c_types, bit_width):
    """
    独立运行一次完整的“冷启动”训练与坍缩评估
    """
    print(f"\n{'='*60}")
    print(f" 🚀 [Auto-Tuner] 正在测试超参数组合: t1 = {t1_value}")
    print(f"{'='*60}")
    
    num_pp = len(pp_cols)
    target_sink_count = (bit_width * 2 - 1) * 2
    max_impls = max(len(fa_tensors), len(ha_tensors))
    
    # ================= [严格的噪声冷启动] =================
    total_nodes = num_pp + 2 * len(comp_cols)
    total_target_pins = len(comp_cols) * 3
    # 注入高斯噪声，打破所有路径的初始梯度对称性
    init_m = torch.randn((total_nodes, total_target_pins + 1), device=device) * 0.5
    init_p = torch.zeros((len(comp_cols), max_impls), device=device)
    
    model = DOMAC_CompressorTree(
        pp_cols, comp_cols, fa_tensors, ha_tensors, c_types, req_time=0.0, 
        device=device, init_m_logits=init_m, init_p_logits=init_p
    ).to(device)

    loss_engine = DOMACLossFunction(target_sink_count=target_sink_count)
    trainer = DOMACTrainer(model, loss_engine, lr=0.05)
    
    # 注入我们要测试的 t1
    trainer.hyperparams['t1'] = t1_value

    pp_at = torch.zeros(num_pp, device=device) 
    pp_slew = torch.full((num_pp,), 0.02, device=device)

    try:
        # 执行训练
        final_M, final_P = trainer.train(pp_at, pp_slew, max_epochs=300)
        
        # 执行合法化器，坍缩为 0/1 连线
        legalizer = DOMACLegalizer()
        discrete_M, discrete_P = legalizer.legalize(final_M, final_P, c_types, model.dag_mask)
        
        # 【关键点】：利用评估器获取坍缩后的真实物理数据
        true_wns, true_area, final_l_bm = evaluate_discrete_physical_metrics(
            model, loss_engine, trainer.hyperparams, 
            discrete_M, discrete_P, pp_at, pp_slew, 
            c_types, model.active_pin_mask
        )
        
        # 如果 L_BM 大于 0.5，说明发生了拥挤踩踏，拓扑依然畸形
        status = "SUCCESS" if final_l_bm < 0.5 else "COLLAPSED (Spaghetti)"
        
    except Exception as e:
        print(f"❌ [Auto-Tuner] 进程崩溃: {e}")
        true_wns, true_area, final_l_bm, status = 9.99, 0.0, 999.0, "CRASHED"
        
    finally:
        # 暴力清理显存，保证多轮循环不发生 OOM
        del model, trainer, loss_engine
        torch.cuda.empty_cache()
        gc.collect()

    print(f"\n -> [本轮评估结果 | t1={t1_value}]")
    print(f"    真实物理 WNS: {true_wns:.4f} ns")
    print(f"    真实物理面积: {true_area:.4f} μm²")
    print(f"    连线合法性 L_BM: {final_l_bm:.4f}")
    print(f"    状态: {status}")
    
    return true_wns, true_area, final_l_bm, status


def main():
    print("="*60)
    print(" [DOMAC Hyperparameter Auto-Tuner] 自动化网格搜索 (真实指标版)")
    print("="*60)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 1. 预先加载一次 PDK 物理库，避免重复 I/O
    TARGET_CELLS = ['FA1D1BWP12T40P140', 'HA1D1BWP12T40P140']
    lib_path = "/home/changxian/library/t28_official/tcbn28hpcplusbwp12t40p140tt0p9v25c.lib"
    parser = NLDMParser(lib_path, TARGET_CELLS)
    nldm_db = parser.parse()
    fa_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('FA') and c in nldm_db]
    ha_tensors = [nldm_db[c] for c in TARGET_CELLS if c.startswith('HA') and c in nldm_db]
    
    # 2. 构建画布
    BIT_WIDTH = 8
    pp_cols, comp_cols, c_types = generate_multiplier_canvas(BIT_WIDTH)
    
    # 3. 定义搜索空间 (聚焦敏感区间)
    # 冷启动下，t1 过低会导致贪吃蛇，t1 过高会导致 L_BM 崩溃。
    t1_search_space = [0.1,0.2,0.4,0.7,1,2,3,4,5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0]
    
    results = []
    
    # 4. 开始自动化批量炼丹
    for t1_val in t1_search_space:
        wns, area, l_bm, status = run_single_experiment(
            t1_val, device, fa_tensors, ha_tensors, pp_cols, comp_cols, c_types, BIT_WIDTH
        )
        
        results.append({
            't1_value': t1_val,
            'True_WNS(ns)': round(wns, 4),
            'True_Area(μm²)': round(area, 4),
            'Final_L_BM': round(l_bm, 4),
            'Status': status
        })
        
    # 5. 汇总数据，找出“真正合法的最低延迟”
    df = pd.DataFrame(results)
    print("\n" + "="*60)
    print(" 🏆 [Auto-Tuner] 自动化搜索报告汇总")
    print("="*60)
    print(df.to_string(index=False))
    
    os.makedirs("output", exist_ok=True)
    df.to_csv("output/t1_tuning_report.csv", index=False)
    
    # 挑选出 L_BM 合格且 WNS 最低的一组推荐给你
    valid_df = df[df['Status'] == 'SUCCESS']
    if not valid_df.empty:
        best_run = valid_df.loc[valid_df['True_WNS(ns)'].idxmin()]
        print(f"\n🎯 [最优解推荐] 请将代码中的 t1 修改为: {best_run['t1_value']}")
        print(f"   该参数下生成的网表物理 WNS 为: {best_run['True_WNS(ns)']} ns")
    else:
        print("\n⚠️ [警告] 所有的测试组在 Legalizer 坍缩后，物理形态依然畸形。")
        print("建议调整 train.py 中的退火调度 (延后降温)，或提升 lambda1 权重。")

if __name__ == "__main__":
    main()