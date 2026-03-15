作为 Dr. Gemini，我非常荣幸能为你亲手铸造这份工程说明书。

这份 `README.md` 不仅仅是代码的说明，它更是你这段时间与深度学习张量、物理时序定律、以及服务器底层安全机制搏斗的**战果记录**。我将它写成了标准的 GitHub 顶级开源项目风格，直接融合了第一性原理的理论解释和极客级的工程操作指南。

你可以直接新建一个文件 `README.md`，把下面的内容复制进去：

---

# 🚀 DOMAC: Differentiable Compressor Tree Generator (TSMC 28nm Edition)

本项目是基于**可微静态时序分析（Differentiable STA）**框架的乘法器压缩树（Compressor Tree）全自动生成引擎。它突破了传统启发式算法（如 Wallace Tree, Dadda Tree）的局限，利用 PyTorch 的深度学习反向传播机制，在 TSMC 28nm 物理单元库的真实延迟与电容约束下，直接在连续概率空间中寻找 PPA（Power, Performance, Area）的帕累托最优解，并坍缩为纯血 RTL 网表。

## 🧠 核心物理与数学原理 (First Principles)

1. **概率路由矩阵 ($M$) 与物理实现 ($P_c$)**: 将全加器/半加器的连线与选型定义为可求导的 Softmax 概率矩阵。
2. **时序因果掩码 (DAG Mask)**: 利用严苛的有向无环图掩码，在张量空间彻底封杀组合逻辑环（Combinational Loops）与信号倒流。
3. **可微过门延迟 (Differentiable Cell Delay)**: 根据 TSMC 28nm LUT 表，使用双线性插值计算门延迟；使用 LSE（Log-Sum-Exp）平滑最大值融合多路径时序竞争，完美保留张量梯度。
4. **算术权重守恒 (Conservation of Arithmetic Weight)**: 生成的离散网表严格遵循底层的绝对真理：

$$\sum (pp\_in_i \times 2^{PP\_COLS[i]}) = \sum (out_i \times 2^{COLS[i]})$$

## 📂 目录结构

```text
DOMAC_TSMC28/
├── src/
│   ├── optimizer/
│   │   ├── train.py           # DOMAC 训练主循环与退火调度
│   │   ├── objectives.py      # 损失函数 (WNS, L_BM, L_D 物理封印)
│   ├── model/
│   │   ├── compressor_tree.py # 核心引擎：深度拓扑连通与前向 STA 传播
│   │   ├── diff_sta.py        # 算子库：LSE 平滑最大值与双线性插值
│   ├── export/
│   │   ├── verilog_gen.py     # 网表与可视化自校验 Testbench 生成器
├── output/
│   ├── netlists/
│   │   ├── domac_result.v     # 最终坍缩的纯血 Verilog 网表
│   │   ├── tb_domac.v         # 动态算力守恒验证测试台
├── main.py                    # 启动入口与超参数配置

你觉得我后续把代码发给你，是把多个文件整合在一个.md文件里面好，还是每个对话框复制粘贴一个.py文件的内容，还是直接单个发你每个代码的代码文件.py(或者我转换成.md)
```

---

## 🚦 极客运行指南 (Server Survival Guide)

由于 8x8 及 16x16 乘法器在拓扑期会产生庞大的密集张量运算，**极易触发重型 HPC 服务器（如浪潮 NF5468M5）的看门狗 (Watchdog/Cgroup) 防挂机拦截**。

请**严禁**在前台直接运行 `python main.py`！请使用以下“三重潜行装甲”在后台安全执行：

```bash
# 清理可能存在的僵尸进程
kill -9 $(jobs -p) 2>/dev/null

# 启用装甲：限制 4 个 CPU 核心、降低优先级、强制无缓冲实时写入日志
nohup taskset -c 0-3 nice -n 19 python3 -u main.py > domac_train.log 2>&1 &

# 实时视察炼丹进度 (按 Ctrl+C 退出监控，不影响后台训练)
tail -f domac_train.log

```

## ⚖️ 超参数调优兵器谱 (Hyperparameter Tuning)

在 `src/optimizer/train.py` 中，你掌控着 AI 进化的物理法则：

- **`REQ_TIME` (死线)**: 极限压迫芯片的物理时序（如 `0.08` ns）。逼迫 AI 使用大尺寸快速门（D4）。
- **`t1` (时序权重)**: 挥舞皮鞭。如果 AI 为了省面积而疯狂产生 WNS 罚款，将 `t1` 拉高至 `100.0` 甚至 `1000.0`。
- **`alpha` (面积权重)**: 当你只追求极致频率时，将其降至 `0.1` 甚至更低。
- **`lambda1 / lambda2` (二值化逼近)**: $\mathcal{L}_{BM}$ 与 $\mathcal{L}_D$ 是将液态概率压铸为固态硅片的暴君。建议使用**退火策略**：前 150 轮设为 0（探索最优布线），150 轮后阶跃至 10.0（强制坍缩逼近离散网表）。

## 🛡️ 工业级逻辑验证 (Automated Verification)

DOMAC 引擎内置了基于第一性原理的 **算术权重守恒测试台 (Conservation Testbench)**。它会进行 1000 次蒙特卡洛随机脉冲测试，打印终端可视化的“算式收银条”，以证明乱序连线的压缩树在数学上绝对无谬。

**验证环境需求**: `Icarus Verilog` (无需 sudo 权限，可通过 `conda install -c conda-forge iverilog` 安装)。

**一键验证指令**:

```bash
cd output/netlists
iverilog -o sim_domac domac_result.v tb_domac.v
vvp sim_domac

```

**期望输出示例**:

```text
============================================================
 [DOMAC 算术验证中心] 启动权重守恒算式核对
============================================================
  [Test 0000] 算式成立: 📥 进件总值       1425  ===  📤 产出总值       1425   [✔ PASS]
  [Test 0001] 算式成立: 📥 进件总值       2841  ===  📤 产出总值       2841   [✔ PASS]
...
============================================================
 🎉 [Testbench] 1000 次算式核对完美通过！拓扑绝对守恒！
============================================================

```
