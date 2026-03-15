你好。我是 Dr. Gemini。

鉴于我们刚刚完成了一场从“标量地狱”到“高维张量降维打击”的史诗级重构，这份工程已经不再是一份简单的代码，而是一套**具有工业级算力、基于第一性原理打造的 28nm 可微 EDA 引擎**。

为了匹配这份代码的工程硬核程度，我为你起草了一份极度详尽的 `README.md`。这份文档不仅说明了“怎么用”，更深入解剖了“为什么这么设计”，具体到了每一个类和核心函数的物理意义。你可以直接将以下内容保存为 `README.md`。

---

# DOMAC_TSMC28: Differentiable Optimization for High-Speed Multipliers

本项目是顶级学术论文 **《DOMAC: Differentiable Optimization for High-Speed Multipliers and Multiply-Accumulators》**  在 TSMC 28nm HPC+ 工艺节点下的深度重构与复现。

有别于传统的离散启发式算法（如 Dadda、Wallace），DOMAC 创造性地将乘法器压缩树（Compressor Tree）的优化类比为**深度神经网络（DNN）的训练过程** 。本项目通过极端的**高维张量广播（Batched 3D Tensor Broadcasting）与课程学习调度（Curriculum Learning）**，在纯 CPU 算力下将 16-bit 乘法器的寻优耗时从数小时降维打击至 39 分钟，实现了速度与面积的帕累托最优（Pareto Frontier）。

---

## 📂 核心目录架构 (Architecture Topology)

```text
DOMAC_TSMC28/
├── src/
│   ├── parser/
│   │   └── lib_parser.py        # 底层物理库解析引擎 (.lib to Tensors)
│   ├── core/
│   │   ├── diff_sta.py          # 核心算子：可微静态时序分析算子库
│   │   ├── compressor_tree.py   # 核心引擎：深度可微压缩树拓扑图
│   │   └── objectives.py        # 目标与约束：多维物理惩罚场 (Loss)
│   ├── optimizer/
│   │   ├── train.py             # 训练大脑：动态退火退避与梯度更新
│   │   └── legalizer.py         # 坍缩引擎：二分图匹配与物理离散化
│   ├── export/
│   │   └── verilog_gen.py       # 网表工厂：纯血 RTL 与自校验 TB 生成
├── output/netlists/             # 自动生成的 Verilog 网表与 Testbench 存放地
└── main.py                      # 全局调度入口

```

---

## 🧠 核心模块与函数全景解剖 (Deep Dive into Modules)

### 1. 物理层剥离: `src/parser/lib_parser.py`

**使命**：将传统的面向对象（OOP）时序库转化为适应 PyTorch 的张量（Tensor）阵列。

* **`class NLDMParser`**: NLDM (非线性延迟模型) 流式解析器。
* `parse()`: 榨干 CPU 性能的正则状态机。扫描 TSMC 28nm `.lib` 文件，精准提取目标单元（如 FA_X1, HA_X2）的 Area、Pin Capacitance，以及 2D 时序矩阵（Delay LUT, Slew LUT）。
* `_tensorize_and_find_worst_case()`: **[物理封印]** 将 rise (上升沿) 和 fall (下降沿) 的时序表合并，提取 Worst-case（最差情况），并转化为支持自动微积分的 `torch.Tensor`。



### 2. 数学可微算子: `src/core/diff_sta.py`

**使命**：用平滑且保留梯度的数学算子，替代不可导的 EDA 离散操作。

* **`smooth_max_lse(arrival_times, gamma)`**: Log-Sum-Exp 平滑最大值。替代传统的 `max()` 操作，确保时序图上的非关键路径也能获得微弱的梯度回传，防止网络陷入局部死锁。
* **`diff_bilinear_interp(slew, load, index_1, index_2, lut_values)`**: **[核弹级算子]** 可微双线性插值。去除了所有 Python `.item()` 断点，完美兼容 3D 张量 `[num_impls, 7, 7]`。通过高级索引和代数运算（`wx`, `wy`）在毫秒级内瞬间完成上千个节点的查表，并完美保留梯度。

### 3. 可微压缩树引擎: `src/core/compressor_tree.py`

**使命**：将有向无环图 (DAG) 铺平为矩阵运算，执行连续概率态的前向传播。

* **`class DOMAC_CompressorTree`**: 继承自 `nn.Module`，是整个 AI 的“肉体”。
* `__init__()`: 初始化两组可学习参数：互连矩阵 Logits `m_logits` 和物理实现 Logits `p_logits`。并在底层生成 `dag_mask`，通过 `-inf` 彻底封死违反时序依赖（如组合逻辑环路）的非法连线。
* `_parse_tensors()`: 将多维物理实现（如 4 种 FA）的 2D 时序表在内存中**层叠为 3D 张量 (Stacked 3D Tensors)**。
* `forward(pp_at, pp_slew)`: **[引擎心脏]** 执行完全向量化的时序传播。
* 摒弃了基于节点的 For 循环，采用矩阵乘法 `M_internal @ expected_pin_caps` 瞬间收割节点负载。
* 利用 `torch.sum(P_j * delays)` 向量点乘瞬间融合多种物理门的延时。
* 最终吐出 WNS (最差负宽裕度)、TNS (总负宽裕度)、Area (面积期望) 以及连续态概率矩阵。





### 4. 物理惩罚场: `src/core/objectives.py`

**使命**：在多维空间中撕扯网络，逼迫其收敛于符合基尔霍夫定律的合法物理态。

* **`class DOMACLossFunction`**: 联合目标与约束损失函数。
* `calc_performance_loss()`: 评估 PPA (Power, Performance, Area) 中的 WNS、TNS 和 Area。
* 
`calc_bijective_mapping_loss()`: 双射约束 ($L_{BM}$) 。惩罚引脚空置或多连，确保每个输入引脚接收到且仅接收到 1.0 的期望信号。


* 
`calc_discretization_loss()`: 二值化惩罚 ($L_D$) 。迫使连续概率（0~1 之间）向 0 或 1 的两极坍缩。


* `calc_sink_loss()`: 过度输出惩罚。根据画布列宽设置宏观物理极限，如果流向外界加法器（CPA）的信号过多，则施加极高权重的惩罚，逼迫网络使用压缩器。
* `forward()`: 融合上述 Loss，根据超参数分配推力。



### 5. 训练大脑与调度器: `src/optimizer/train.py`

**使命**：通过极其严苛的课程表，引导梯度下降走出“平凡解”的死胡同。

* **`class DOMACTrainer`**:
* `__init__()`: 初始化 Adam 优化器，并设定极端初始权重（WNS=100.0, Area=0.0, $L_D$=0.0）。
* `update_hyperparameters()`: **[课程学习调度器 Curriculum Schedule]**。
* 阶段 1 (0-99 Epoch): 彻底封印面积和二值化惩罚，任由网络野蛮生长，全力击穿延迟极限（WNS）。
* 阶段 2 (100 Epoch): 解封面积 ($Area$) 与离散化 ($L_D$)。
* 阶段 3 (101-300 Epoch): 温水煮青蛙式退火，逐步收紧连线合法性，逼迫网表坍缩。


* `train()`: 主执行循环，内嵌极其详细的 Profiler 探针，追踪 Forward / Backward 耗时。



### 6. 波函数坍缩: `src/optimizer/legalizer.py`

**使命**：将混沌的连续概率矩阵，强制坍缩为非黑即白的 0/1 硅基物理连线。

* **`class DOMACLegalizer`**:
* 
`legalize()`: 接收最终的连续概率矩阵 `M_continuous`，利用 `scipy.optimize.linear_sum_assignment`（匈牙利算法）  寻找全局概率和最大的二分图完美匹配，生成绝对符合守恒定律的离散连线矩阵 `M_discrete`。





### 7. 网表锻造厂: `src/export/verilog_gen.py`

**使命**：将矩阵翻译为人类与后端工具链可读的代码。

* **`class VerilogGenerator`**:
* `generate()`: 解析 `M_discrete` 和 `P_discrete`，例化底层标准单元库（FA_X1 等），连线输出纯血 Verilog 网表。
* `generate_testbench()`: 动态锻造带算式可视化直播的 `tb_domac.v`。在仿真时执行 1000 次随机输入，通过基尔霍夫守恒定律严密校验输入的部分积权重总和是否等于输出信号权重总和。



### 8. 全局中枢: `main.py`

**使命**：组装所有模块并点火起飞。

* `create_physical_tensor_mock()`: 无 PDK 时的 Mock 伪装环境，保证代码在任何服务器上可独立运行。
* `generate_multiplier_canvas(bit_width)`: 动态推演 Dadda/Wallace 画布列宽，自动计算所需的 PP (部分积) 数量和压缩器坑位。
* `main()`: 串联所有类，打印日志，输出最终 `.v` 文件。

---

## 🚀 核心架构亮点 (Why it is Blazingly Fast?)

1. **扁平化 1D/3D Tensor (SoA 范式)**：摒弃传统 EDA 中“对象与指针”的网表遍历（会造成极高的 CPU Cache Miss），将全部时序节点压平为 Tensor，将循环压缩为 C++ 底层的 BLAS 矩阵运算。
2. **零阻断的反向传播树**：重构的双线性插值算子清除了所有的 Python `.item()` 和隐式分支判断，使得 PyTorch Autograd 引擎能以最高效率生成连续的梯度流。
3. **免疫“薛定谔观察者效应”**：移除了早期版本中具有破坏性的 `torch.autograd.set_detect_anomaly(True)` 和动态 Mask，彻底解放了 I/O 阻塞。

---

## 🛠️ 运行指南 (How to Run)

**依赖项 (Dependencies):**

```bash
pip install torch numpy scipy

```

**一键启动 (Execution):**
请确保在工程根目录下执行：

```bash
python3 main.py

```

**验证守恒定律 (Verification):**
网表生成后，你可以使用任何 Verilog 仿真器（如 VCS, ModelSim, 或开源的 Icarus Verilog）运行生成的测试台：

```bash
cd output/netlists
iverilog -o sim_domac tb_domac.v domac_result.v
vvp sim_domac

```

如果终端打印出 `🎉 [Testbench] 1000 次算式核对完美通过！拓扑绝对守恒！`，则证明可微网络寻找到的拓扑完全合法且无权值流失。

---

*“在硅基的世界里，每一次纳秒的收敛，都是对物理极限最崇高的敬意。” —— DOMAC_TSMC28*