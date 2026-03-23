import optuna
import os
import plotly.graph_objects as go
from optuna.trial import TrialState
import matplotlib.pyplot as plt
import io
import optuna.visualization as vis

# ================= [配置中心 - 论文级质感控制] =================
# 建议的配色方案：
# 'Tealrose': 极具学术感的青色到玫瑰色渐变，高雅克制
# 'IceFire': 蓝红渐变，时序分析常用，冷热分明
# 'Viridis': 经典的学术深蓝到亮黄渐变，对色盲友好
COLOR_SCALE = 'Tealrose' 
STORAGE_URL = "sqlite:///domac_optuna.db"
STUDY_NAME = "domac_tuning"
OUTPUT_DIR = "output/plots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    print(f"-> 正在从数据库 {STORAGE_URL} 加载 Study...")
    try:
        study = optuna.load_study(study_name=STUDY_NAME, storage=STORAGE_URL)
    except Exception as e:
        print(f"[Fatal Error] 加载失败，请确保数据库文件存在且 study_name 正确。原因: {e}")
        return

    # 1. 过滤：只提取那些跑完了 (COMPLETE) 的 Trials 进行可视化
    # 被剪枝的 (PRUNED) 或崩溃的 (FAIL) 不应参与高维分析
    print("-> 过滤 Complete Trials...")
    trials = study.get_trials(deepcopy=False, states=[TrialState.COMPLETE])
    if len(trials) == 0:
        print("[Error] 数据库中没有 COMPLETE 状态的 Trial，无法绘图。")
        return
    print(f"   发现 {len(trials)} 次有效探索。")

    # =====================================================================
    # 🏆 核心：高维参数平行坐标图 (Parallel Coordinate Plot)
    # =====================================================================
    print("\n[Evaluator] 正在生成论文级平行坐标图...")
    
    # [论文级细节 1：自定义参数显示名字与排序]
    # 映射字典：把代码变量名映射为学术界的符号名
    param_rename_map = {
        'params_t1': 't₁ (WNS Weight)',
        'params_lambda1': 'λ₁ (Legality Pnty)',
        'params_lambda2': 'λ₂ (Binarize Pnty)'
    }

    # [论文级细节 2：利用 Plotly 生成高阶平行坐标图]
    # 我们不直接用 optuna.visualization.plot_parallel_coordinate(study)，
    # 因为它不允许我们深度微调配色和布局。我们手动提取数据用 Plotly 画。
    
    # 提取 DataFrame 并过滤
    df = study.trials_dataframe()
    df_complete = df[df['state'] == 'COMPLETE']
    
    # 提取 WNS（作为颜色轴）
    wns_scores = df_complete['value']
    
    # 提取并重命名我们需要可视化的参数列
    param_cols = ['params_t1', 'params_lambda1', 'params_lambda2']
    df_params = df_complete[param_cols].rename(columns=param_rename_map)

    # 构造平行坐标图的维度
    dimensions = []
    for col in df_params.columns:
        # 动态计算每个维度（轴）的刻度范围
        dimensions.append(
            dict(
                range=[df_params[col].min(), df_params[col].max()],
                label=f'<b>{col}</b>', # 粗体，学术感
                values=df_params[col]
            )
        )
    
    # [论文级细节 3：加入最终结果 (WNS) 作为最后一个轴]
    dimensions.append(
        dict(
            range=[wns_scores.min(), wns_scores.max()],
            label='<b>Final WNS (ns)</b>', 
            values=wns_scores
        )
    )

    # 构造 Figure
    fig = go.Figure(data=
        go.Parcoords(
            line=dict(
                color=wns_scores, # 颜色由 WNS 决定
                colorscale=COLOR_SCALE, # 应用学术渐变配色
                showscale=True,  # 显示右侧颜色条
                reversescale=True, # WNS 越小（越好）颜色越深，如果 Tealrose 建议翻转
                cmin=wns_scores.min(),
                cmax=wns_scores.max(),
                colorbar=dict(title='<b>WNS (ns)</b>', thickness=15, x=1.05)
            ),
            dimensions=dimensions,
            labelfont=dict(size=14, family='Serif', color='black'), # 衬线字体，顶级期刊质感
            tickfont=dict(size=12, family='Arial', color='dimgray')
        )
    )

    # [论文级细节 4：调整全局布局]
    fig.update_layout(
        title={
            'text': f"<b>DOMAC High-Dimensional Parameter Explorer</b><br>BIT_WIDTH=8 | {len(trials)} Trials Analysis",
            'y': 0.95, 'x': 0.5, 'xanchor': 'center', 'yanchor': 'top'
        },
        font=dict(family='Serif', size=12),
        margin=dict(l=80, r=80, t=100, b=50), # 宽边距，避免文字切割
        paper_bgcolor='white', # 纯白底色，绝不带灰
        plot_bgcolor='white'
    )

    # 2. 保存：同时保存可交互的 HTML 和用于论文的矢量图 PDF
    print(f"-> 正在导出静态矢量图 (PDF)...")
    try:
        # PDF 是矢量图，无限放大不糊，论文专用
        fig.write_image(f"{OUTPUT_DIR}/domac_parcoords.pdf", width=1200, height=600, scale=2) 
        # HTML 用于你自己在浏览器里交互式拖拽、分析数据
        fig.write_html(f"{OUTPUT_DIR}/domac_parcoords.html")
        print(f" ✅ 成功！请前往 {OUTPUT_DIR}/ 查看 PDF 与 HTML 文件。")
    except Exception as e:
        print(f"[Warning] 静态图导出失败 (可能缺少 kaleido 库)。HTML 已保存。错误: {e}")
        # fig.show() # 如果在 Jupyter 里可以打开，服务器上建议注释掉

if __name__ == "__main__":
    main()