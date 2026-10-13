# SLID — Scheduling-Layer Injection Detection

面向信息物理生产系统（CPPS）**调度层**注入攻击的在线检测器：
时序半马尔可夫一致性 + 跨设备互锁不变量 + 序贯检验 + conformal 校准。

Online detector for **scheduling-layer** injection attacks on cyber-physical production systems (CPPS):
timing semi-Markov consistency + cross-device interlock invariants + sequential testing + conformal calibration.

命名取 **S**cheduling-**L**ayer **I**njection **D**etection。之所以用问题
命名而非技术命名（不叫 tsmd/tsmic 之类），是因为本文的创新定位在
"调度器–设备命令/状态回环"这个此前没有被系统处理过的攻击面上；
时序半马尔可夫、CUSUM、conformal 都各有先行工作，单拎出来站不住脚。

The name is **S**cheduling-**L**ayer **I**njection **D**etection. It is named after the problem rather than the technique (not tsmd/tsmic or the like) because the contribution sits on the "scheduler–device command/state loop", an attack surface that had not been treated systematically. Timing semi-Markov models, CUSUM, and conformal methods each have prior work, and none of them stands alone.

设计取舍全部来自对 Trier Fischertechnik IoT 事件日志的实测，具体数字写在
各模块 docstring 里；结论的完整推导见 `../新想法.md`。

Every design choice comes from measurements on the Trier Fischertechnik IoT event log. The numbers are written in each module's docstring; the full derivation of the conclusions is in `../新想法.md`.

## 一、快速开始 / 1. Quick start

```powershell
cd paper02\slid
py main.py                                        # 默认数据集 + 默认攻击 / default dataset + default attack
py main.py --dataset ft_trier --attack A2 --rho 0.15
py main.py --arm ablation                         # 递进消融链 / progressive ablation chain
py main.py --arm baselines --alpha 0.01           # 对照方法 / comparison methods
py -m pytest tests\test_all.py -v                 # T1–T40 断言 / T1–T40 assertions
py -m tools.model_diag                            # M1/M2/M5 与探针脚本对数 / check M1/M2/M5 against the probe scripts
py -m tools.timing_diag                           # M4 时长模型与 rho* 逐组表 / M4 sojourn model and per-group rho*
py -m tools.fusion_diag                           # M6 通道依赖、校准架构、稀释代价 / M6 channel dependence, calibration layout, dilution cost
py -m tools.a8_fisher                             # A8 红队:Fisher 合成路去留 / A8 red team: keep or drop the Fisher fusion path
py -m tools.online_diag                           # 时间序效度、逐消息时延、抗投毒 / temporal-order validity, per-message latency, poisoning resistance
py -m tools.robust_diag                           # 时间序 FPR、含错版 C'、E9 产品切换 / temporal-order FPR, corrupted C', E9 product switch
py -m tools.sigma_scan                            # E5 膨胀 sigma / E5 inflated sigma
py -m tools.transfer_diag                         # E6 场景 A/B/C 迁移 / E6 transfer across scenarios A/B/C
py -m tools.alarm_walkthrough                     # 可解释告警样例 / explainable alarm examples
py -m tools.coverage_matrix                       # 攻击 x 通道覆盖矩阵(实测) / attack x channel coverage matrix (measured)
py -m tools.struct_diag                           # M3 状态粒度(负面结果) / M3 state granularity (negative result)
py -m tools.baseline_diag                         # E1 同误报预算下的基线对比 / E1 baseline comparison at the same false-alarm budget
py -m tools.run_matrix --preset smoke             # 矩阵批跑自检 / matrix-batch self-check
py -m tools.bound_curve                           # 影响-可检测性曲线 / impact-detectability curve
py -m tools.calib_diag                            # 校准可靠性图 / calibration reliability diagram
```

复现论文表：`py -m tools.reproduce` 从已有 JSON 存档汇总 `experiments/*.csv`。
重跑诊断（不含 E1）加 `--run`；E1 主表另加 `--e1`。图在 `../Latex/figures/` 下跑对应 `fig_*_CN.py`。箱线只读存档里的 `detected_delays`。

Reproduce the paper tables: `py -m tools.reproduce` aggregates `experiments/*.csv` from existing JSON archives.
Rerun diagnostics (excluding E1) with `--run`; add `--e1` for the E1 main table. Figures are produced by the matching `fig_*_CN.py` under `../Latex/figures/`. Box plots read only `detected_delays` from the archive.

依赖见 `requirements.txt`，只有 numpy / scipy / matplotlib。

Dependencies are listed in `requirements.txt`: only numpy / scipy / matplotlib.

## 二、文件夹层级 / 2. Directory layout

```text
slid/
  README.md            # 本文件 / this file
  requirements.txt     # 依赖 / dependencies
  main.py              # 一键入口:载入日志 → 拟合 → 注入攻击 → 检测 → 写结果 / one-shot entry: load log → fit → inject attacks → detect → write results
  algorithm/           # 算法核心(与 新想法.md 的 M0–M9 一一对应) / algorithm core (one-to-one with M0–M9 in 新想法.md)
    ingest.py          #   M1 事件流解析,按 (设备, case) 切链 / M1 parse the event stream and split chains by (device, case)
    procmodel.py       #   M2 从 BPMN 导出可行性掩码 F 与互锁不变量 I / M2 export feasibility mask F and interlock invariants I from BPMN
    structural.py      #   M3 结构通道:case 级 Dirichlet 后验预测 / M3 structural channel: case-level Dirichlet posterior prediction
    timing.py          #   M4 时序通道:加性 AFT + NIG/Student-t 后验预测 / M4 timing channel: additive AFT + NIG/Student-t posterior prediction
    interlock.py       #   M5 互锁通道:带时长的令牌不变量 + 命令-响应因果 / M5 interlock channel: timed token invariants + command-response causality
    fusion.py          #   M6 通道合成(Fisher + 可检查的独立性前提) / M6 channel fusion (Fisher + a checkable independence premise)
    sequential.py      #   M7 CUSUM / e 过程 / M7 CUSUM / e-process
    conformal.py       #   M8 随机化 conformal 校准 / M8 randomized conformal calibration
    detector.py        #   M0/M9 在线回放流水线 + 抗投毒的门控更新 / M0/M9 online replay pipeline + poisoning-resistant gated update
    attacks.py         #   红队注入器 A1–A6 与 A8;A7 不实现即不报告 / red-team injectors A1–A6 and A8; A7 is not implemented and therefore not reported
    plant.py           #   自建场景 A/B/C(仅 E6,不作主验证) / hand-built scenarios A/B/C (E6 only, not the main validation)
    baselines.py       #   基线 B1–B5、统一判决口径 judge、六档消融 / baselines B1–B5, unified decision rule judge, six-tier ablation
    metrics.py         #   指标与报告口径 / metrics and reporting rules
  tools/               # 实验驱动与诊断 / experiment drivers and diagnostics
    run_matrix.py      #   矩阵批跑,断点续跑 / matrix batch runs, resumable
    bound_curve.py     #   理论界 vs 实测检出率 / theoretical bound vs measured detection rate
    calib_diag.py      #   校准可靠性图(含三条反例对照线) / calibration reliability diagram (three counterexample lines)
    model_diag.py      #   M1/M2/M5 落地后与 database/ 探针脚本对数 / after M1/M2/M5 land, check numbers against the database/ probe scripts
    timing_diag.py     #   M4 的四个聚合尺度、森林判定、逐组 rho* / M4's four aggregation scales, forest check, per-group rho*
    mbdf_undetectable.py #  构造性枚举原方法的恒不可检测状态集 / constructive enumeration of the original method's always-undetectable state set
    a8_fisher.py       #   A8 红队:Fisher 合成路去留 / A8 red team: keep or drop the Fisher fusion path
    export_experiments.py # 汇总成论文级 CSV / aggregate into paper-level CSVs
  input/               # 输入 / inputs
    ft_trier/          #   Trier Fischertechnik IoT 日志(主数据集) / Trier Fischertechnik IoT log (main dataset)
    hai/               #   HAI,用于跨过程耦合的外部效度 / HAI, for external validity of cross-process coupling
    sim/               #   自建仿真场景,补齐公开集缺失的攻击类型 / hand-built simulation, covering attack types missing from public sets
    raw/               #   数据来源与取用说明 / data sources and how they are used
  output/              # 每次运行的原始结果,按 tag 分目录 / raw results of each run, one directory per tag
  experiments/         # 导出的论文级 CSV / exported paper-level CSVs
  tests/
    test_all.py        #   T1–T40,每条对应一个已量化的事实 / T1–T40, each tied to one quantified fact
```

## 三、二十五条不可回退的设计约束 / 3. Twenty-five design constraints that must not be rolled back

这些都是先按"自然做法"实现、被数据打回来之后才定下的；其中第 4 条推翻了
先前写进文档的判断，第 10 条修掉的缺陷差点让核心攻击测成不可检测。改动前
请先看对应模块 docstring 里的实测数字，不要凭论证改。

These were fixed only after the "natural" implementation was pushed back by the data. Item 4 overturns a judgment previously written into the docs, and the defect fixed by item 10 nearly made the core attack measure as undetectable. Before changing anything, read the measured numbers in the corresponding module docstring; do not change them on argument alone.

1. **链的粒度是 (设备, case)，结构通道的粒度是 case。**
   设备级全局时间线会跨 case 边界，误报出 48.6% 的可行性违反；而设备级
   结构链本身信息量为零（3,062 个活动只产出 953 次转移，p 值取值唯一）。

   **Chain granularity is (device, case); the structural channel's granularity is the case.**
   A device-level global timeline crosses case boundaries and false-alarms at 48.6% on feasibility checks; the device-level structural chain itself carries zero information (3,062 activities yield only 953 transitions, and the p-value takes a single value).

2. **conformal p 值必须随机化。** 但理由是"通道离散度事先未知时它是唯一
   无条件安全的选择"，不是"总是更准"：朴素形式的灾难性失效（FPR 1.000）
   只出现在取值极粗的设备级通道；case 级通道有 28–32 个取值，朴素形式
   已达 0.049。互锁通道近乎二值，正属危险区。

   **Conformal p-values must be randomized.** The reason is that "when channel discreteness is unknown in advance, it is the only unconditionally safe choice", not that it is "always more accurate": the catastrophic failure of the naive form (FPR 1.000) appears only on the very coarse device-level channel; a case-level channel has 28–32 values and the naive form already reaches 0.049. The interlock channel is nearly binary and sits in the danger zone.

3. **校准集规模是硬约束，划分应随机。** `alpha >= 1/(n_calib+1)` 不满足时
   的"零误报"是假象，报告里必须标注。字典序切分的伤害集中在朴素臂
   （0.073 对 0.049）；随机化之后两种划分只差 0.053 对 0.046。
   Mondrian 逐组校准**不能**解决组间异质性：alpha=0.01 时 95% 的组不可达。

   **Calibration-set size is a hard constraint, and the split should be random.** When `alpha >= 1/(n_calib+1)` fails, a "zero false-alarm rate" is an illusion and must be marked in the report. The harm of a lexicographic cut is concentrated on the naive arm (0.073 versus 0.049); after randomization the two splits differ only as 0.053 versus 0.046. Mondrian per-group calibration **cannot** fix between-group heterogeneity: at alpha=0.01, 95% of groups are unreachable.

4. **合成前必须逐通道校准；Fisher 的独立性前提成立，但合成路不进生产配置。**
   三通道相关实测只有 -0.030 / -0.008 / +0.056，独立性成立，原"不能用
   Fisher"的论证把"同属横向证据"误当成"统计相关"。顺序仍不可换：
   8.1% 的良性活动时序 p 值触到数值下界，先合成会在 min 型统计量底部
   形成原子，Simes/minp 的 FPR 卡在 0.074。**但生产路径不跑合成**：
   score-level misplace 下 Fisher 0.413 对仅时序 0.108，红队 A8 实现同一
   攻击后，E1 口径下加合成路对 A8 是 -0.04、对 A1-A6 再 -0.04（结论
   五十三）。M6 代码留作诊断，换产线仍用 `fusion.dependence()` 复测。

   **Calibrate each channel before fusion; Fisher's independence premise holds, but the fusion path is not in the production configuration.** Measured pairwise correlations of the three channels are only -0.030 / -0.008 / +0.056, so independence holds. The old argument "Fisher cannot be used" mistook "both are cross-sectional evidence" for "statistical dependence". The order still cannot be swapped: 8.1% of benign activities have a timing p-value on the numerical floor, and fusing first forms an atom at the bottom of a min-type statistic, so the FPR of Simes/minp sticks at 0.074. **The production path does not run fusion**: under score-level misplace Fisher is 0.413 versus timing-only 0.108; after red-team A8 realizes the same attack, adding the fusion path under the E1 rule is -0.04 on A8 and another -0.04 on A1–A6 (conclusion 53). The M6 code is kept for diagnosis; on a new line, remeasure with `fusion.dependence()`.

5. **时序通道对抢跑攻击取单侧，理由是稳定而非功效。** 30 个折划分种子下
   单侧 DR 0.872 ± 0.026、双侧 0.722 ± 0.165，平均优势只有 +0.150
   （alpha=0.05 下 +0.018）。单侧阈值落在 [2.22, 3.34]，双侧散到
   [2.48, 7.27]。早先记录的"0.338"是最坏种子，不可作为方法优势引用。

   **The timing channel uses a one-sided test against early-reporting attacks because it is stable, not because it is more powerful.** Over 30 fold-split seeds the one-sided DR is 0.872 ± 0.026 and the two-sided DR is 0.722 ± 0.165; the mean advantage is only +0.150 (+0.018 at alpha=0.05). One-sided thresholds fall in [2.22, 3.34]; two-sided ones scatter to [2.48, 7.27]. The earlier recorded "0.338" is the worst seed and must not be cited as a methodological advantage.

6. **报告 conformal 保证必须给时间序口径，不能只给随机折。** 部署只能用
   过去拟合、对未来判定。现行残差 z 共形下，alpha=0.01 时序通道由随机折
   0.006 升到时间序 0.024，结构通道由 0.008 升到 0.012（`tools/robust_diag.py`）。
   旧记录「时序 0.010→0.007、结构 0.007→0.015」是参数化 p 值时期的数字，
   不得再抄。运维上两条统计通道都要按时间序解释，产品切换后时序通道必须
   重校准（E9 未见工作流 time@0.01=0.067）。

   **A reported conformal guarantee must use the temporal-order rule, not only random folds.** Deployment can only fit on the past and decide on the future. Under the current residual-z conformal, at alpha=0.01 the timing channel rises from 0.006 on a random fold to 0.024 in temporal order, and the structural channel from 0.008 to 0.012 (`tools/robust_diag.py`). The old record "timing 0.010→0.007, structure 0.007→0.015" is from the parametric-p-value period and must not be copied. Operationally both statistical channels are interpreted in temporal order, and after a product switch the timing channel must be recalibrated (E9 unseen workflow time@0.01=0.067).

7. **在线更新必须门控。** 无门控时 200 条抢跑注入把基线拖走，攻击者白拿
   26.4% 的调度提前量；门控后 1.4%。这是与原专利"无条件 EWMA 更新"的
   架构差异，不依赖任何统计功效优势。

   **Online update must be gated.** Without a gate, 200 early-reporting injections drag the baseline away and the attacker takes 26.4% of the schedule advance for free; with the gate, 1.4%. This is an architectural difference from the original patent's "unconditional EWMA update", and it does not depend on any power advantage.

8. **攻击编号以 新想法.md 覆盖矩阵为准。** 代码里曾用过另一套（A2=抢跑、
   A4=重放），而论文口径是 A3=抢跑、A4=状态模仿。错位不报错，只会让每个
   A 编号的结论张冠李戴。T22 钉死这一点，未实现的攻击族一律显式拒绝。

   **Attack numbers follow the coverage matrix in 新想法.md.** The code once used another set (A2 = early reporting, A4 = replay), while the paper's rule is A3 = early reporting and A4 = state mimicry. A mismatch does not raise an error; it only puts each numbered conclusion on the wrong attack. T22 nails this down. Unimplemented attack families are rejected explicitly.

9. **引用 rho\* 必须连同口径给出。** 路线条件化（20 组，σ 0.007–1.843，
   中位 rho\* 30.9%）与不条件化（31 组，中位 σ=0.207 → 38.2%）是两套都
   正确但不可混用的数字；把端点取自前者、中位取自后者会把协变量的收益
   抹掉。T6b 钉住这一点。

   **A cited rho\* must come with its reporting rule.** Route-conditioned (20 groups, σ 0.007–1.843, median rho\* 30.9%) and unconditioned (31 groups, median σ=0.207 → 38.2%) are both correct and must not be mixed. Taking endpoints from the first and the median from the second erases the covariate's gain. T6b pins this down.

10. **时序通道的不符合度分数用标准化残差 z，不能用 p 值。** p 值裁剪在
    1e-12，而 8.1% 的良性活动就落在那儿（规则 4），尾部再无分辨率，
    conformal 分不开"30% 抢跑"与"良性失配"。用 p 值时 A3 的时序检出率
    只有 0.03，换成 z 后回到 0.43。这个缺陷不报错、不破坏误报率，只是
    安静地把功效削掉一个量级。**凡 conformal + 参数化 p 值的组合都要查
    这一点。**T25 钉死。

    **The timing channel's nonconformity score is the standardized residual z, not a p-value.** p-values are clipped at 1e-12, and 8.1% of benign activities already sit there (rule 4), so the tail has no further resolution and conformal cannot separate "30% early reporting" from "benign mismatch". With p-values, A3's timing detection rate is only 0.03; with z it returns to 0.43. The defect raises no error and does not break the false-alarm rate; it quietly cuts power by an order of magnitude. **Every conformal + parametric p-value combination must be checked for this.** T25 nails it down.

11. **二值通道的单消息功效上界是 min(1, alpha/q)，与不变量质量无关。**
    互锁软层良性违反率 q（训练折 0.0054，诊断口径 0.017），随机化 p 值
    在违反时均匀落在 [0, q]。alpha=0.001 时上界只剩 0.185。论文声称的
    alpha 范围必须与 q 一起给，否则"互锁检出率低"会被误读成不变量差。
    这也是"RFID/NFC 工件身份使软层升硬层"这条部署建议的定量理由。T26。

    **The per-message power bound of a binary channel is min(1, alpha/q), independent of invariant quality.** The benign violation rate q of the interlock soft layer (0.0054 on the training fold, 0.017 in the diagnostic rule) makes a randomized p-value fall uniformly in [0, q] on a violation. At alpha=0.001 the bound is only 0.185. A claimed alpha range must be given together with q, or "low interlock detection" will be misread as a weak invariant. This is the quantitative reason for the deployment advice "RFID/NFC workpiece identity promotes the soft layer to the hard-constraint layer". T26.

12. **覆盖矩阵只能实测，且必须写明攻击者知识等级。** 手写版 24 格中 11 格
    与实测不符。尤其 A4：注入器复制当前操作时结构通道拿到 0.19、头条主张
    当场作废，换成按转移模型挑最可能的下一步后才归零，互锁的 0.12 成为
    唯一提升。**"只有互锁能抓 A4"是方法与攻击者强度的联合性质，不是方法
    的性质。**未实现的攻击族（A7）一律不报告。T27，`tools/coverage_matrix.py`。
    注意分歧有两种成因：主张错，或**实现不全**——A2 硬层属后者，见规则 13。

    **The coverage matrix can only be measured, and the attacker's knowledge level must be stated.** 11 of 24 cells in the handwritten version disagree with measurement. A4 in particular: when the injector copies the current operation the structural channel scores 0.19 and the headline claim is void on the spot; only after the next step is chosen from the transition model does it return to zero, and the interlock's 0.12 is the only lift. **"Only interlock can catch A4" is a joint property of the method and the attacker's strength, not a property of the method.** Unimplemented families (A7) are not reported. T27, `tools/coverage_matrix.py`. Disagreement has two causes: the claim is wrong, or **the implementation is incomplete** — the A2 hard-constraint layer is the latter; see rule 13.

13. **F 分一元与二元，一元覆盖 100% 消息，二元只有 31%。** 二元的转移可达性
    要求同 case 同设备有前驱，实测 953/3062 = 31.1%，这就是 A2 硬层一度只有
    0.29 的全部原因。一元（"这台设备允不允许做这个操作"）无需前驱，补上后
    A2 硬层 0.98、良性违反 0/3062。能力集**必须按设备类归并**（`sm_2 → sm`）：
    16 个 BPMN 只实例化一台分选机，按实例归并会误判 sm_2 的 44 次 /sm/sort
    （1.44%）。T28。

    **F splits into unary and binary. Unary covers 100% of messages; binary covers only 31%.** Binary transition reachability requires a predecessor on the same device in the same case, measured 953/3062 = 31.1%, which is the whole reason the A2 hard-constraint layer was once only 0.29. Unary ("is this device allowed to perform this operation") needs no predecessor; after it is added, the A2 hard-constraint layer is 0.98 and benign violations are 0/3062. The capability set **must be merged by device class** (`sm_2 → sm`): the 16 BPMN models instantiate only one sorter, and merging by instance would falsely flag sm_2's 44 `/sm/sort` events (1.44%). T28.

14. **基线对比有五条口径，缺一不可比，全部由 `baselines.judge` 统一执行。**
    (a) 阈值取自**纯良性流**——A2 原地改写造成的级联触发不是虚警，算成
    误报会在级联率超过 alpha 时把阈值推成 +inf、检出率假性归零（本方法
    A2 的 DR 被这样测成过 0.00）。(b) 序贯臂**给基线也套上同一套 CUSUM**，
    否则无法把增益归因到通道设计而非累积机制。(c) 每个方法**并行**跑自己
    的子检测器、alpha 均分——压成一条 min-p 流会让弱信号被其它子检测器
    的噪声稀释（本方法 A4 因此从 0.23 掉到 0.17）。(d) 目标 ARL0 只能取
    1/alpha：超过良性流长时零误报使 ARL0 记作无穷、h 落到区间下界。
    (e) **CUSUM 告警后必须复位**，否则 S 越过 h 后每条消息都告警。
    (d)(e) 叠加时基线的序贯误报虚高到名义值的 **22 倍**、检出率一并虚高。
    **报告序贯结果必须同时给出实测序贯误报**，否则这类错误读者无法发现。
    T30、T33。

    **Baseline comparison has five reporting rules. Missing any one of them makes the comparison invalid, and `baselines.judge` enforces all of them.** (a) The threshold comes from a **purely benign stream** — cascade triggers from an in-place A2 rewrite are not false alarms; counting them as such pushes the threshold to +inf once the cascade rate exceeds alpha and falsely zeroes the detection rate (this method's A2 DR was once measured as 0.00 that way). (b) The sequential arm **puts the same CUSUM on the baselines too**, or the gain cannot be attributed to channel design rather than the accumulation mechanism. (c) Each method runs its own sub-detectors **in parallel** and splits alpha evenly — collapsing them into one min-p stream lets a weak signal be diluted by the noise of the other sub-detectors (this method's A4 therefore drops from 0.23 to 0.17). (d) The target ARL0 can only be 1/alpha: past the benign stream length a zero false-alarm rate records ARL0 as infinity and h falls to the lower end of the interval. (e) **CUSUM must reset after an alarm**, or every message alarms once S has crossed h. When (d) and (e) stack, a baseline's sequential false-alarm rate is inflated to **22 times** nominal, and the detection rate is inflated with it. **A sequential result must also report the measured sequential false-alarm rate**, or the reader cannot see this class of error. T30, T33.

15. **不要把结构通道的状态细化为 (设备, 操作)。** 面对"结构通道设备盲"这是
    最自然的修法，实测三项全负：alpha=0.01 的 FPR 由 0.017 升到 0.050（5 倍
    名义值）、A2 结构检出由 0.350 **归零**、A4 无收益。归零的机理要记住：
    细粒度下未见组合成为**词表外状态**，`struct_pvalue` 于是**弃权**而非
    告警——细化状态把可检测异常变成了"未知因而放过"。**弃权语义会把改进
    悄悄吞掉，且在指标上伪装成"模型不够好"。**正确的修法是规则 13 的一元 F：
    未见组合归硬约束判，不归统计通道判。T29，`tools/struct_diag.py`。

    **Do not refine the structural channel's state to (device, operation).** That is the most natural fix for "the structural channel is device-blind", and all three measurements are negative: the FPR at alpha=0.01 rises from 0.017 to 0.050 (5 times nominal), A2 structural detection falls from 0.350 to **zero**, and A4 gains nothing. Remember why it zeroes: at fine granularity an unseen pair becomes an **out-of-vocabulary state**, so `struct_pvalue` **abstains** instead of alarming — refining the state turns a detectable anomaly into "unknown, therefore let through". **Abstention semantics quietly swallow an improvement and disguise it, in the metrics, as "the model is not good enough".** The right fix is the unary F of rule 13: an unseen pair is judged by the hard constraint, not by the statistical channel. T29, `tools/struct_diag.py`.

16. **参考模型的信息学不出来，这是用 BPMN 的根本理由。** 日志里"没见过"与
    "不允许"无法区分，而时间序下"没见过"会以 **3.9%**（20/508，全是
    `hbw_1 //hbw/unload`）的比例良性发生，远超 alpha=0.01，故任何数据驱动
    模型都不能把未见组合当作证据。参考模型拒绝了这 20 条中的 **0** 条。
    这一条同时解释规则 13（一元 F 为何必须来自 BPMN）、规则 15（细化状态
    为何退化成弃权）、以及 B4 TABOR 为何打不过 B3 BUTLA（其站内贝叶斯网络
    的极端负对数似然在良性数据里已经出现）。T31。

    **What the reference model knows cannot be learned from the log. That is the fundamental reason to use BPMN.** A log cannot separate "never seen" from "not allowed", and under temporal order "never seen" occurs benignly at **3.9%** (20/508, all `hbw_1 //hbw/unload`), far above alpha=0.01, so no data-driven model may treat an unseen pair as evidence. The reference model rejects **0** of those 20. This one point also explains rule 13 (why unary F must come from BPMN), rule 15 (why refining the state degenerates into abstention), and why B4 TABOR loses to B3 BUTLA (the extreme negative log-likelihood of its within-station Bayesian network already appears in benign data). T31.

17. **不要声称全面优于所有基线，落后的两族已归因完毕。** 三路配置、序贯、
    误报对齐、**减去偶然地板**后：本方法均值 **0.48**（alpha=0.05 时 0.47），
    B2 markov 0.29、B4 tabor 0.21、B3 butla 0.17、B5 hsmm 0.11、B1 mbdf 0.01。
    但 **B2 在 A4（0.23 对 0.17）与 A6（0.28 对 0.14）上打赢本方法，且两个
    alpha 下都复现**，故不是分辨率假象。归因已逐项测量（规则 23）：**完全是
    预算摊薄**——结构通道满预算时 A4 拿 0.31、A6 拿 0.45，与 B2 的 0.41、0.45
    齐平，三路均分后只剩 0.18、0.19。可写的陈述是「平均领先 1.4-1.7 倍且无
    一族归零，而 B2 在 A3/A5 上精确为零」，**不能写成全面占优**。另外 B5 hsmm
    的校准漂移是 1.0×，与 conformal 相当，故 M8 的卖点只能写成「控制不依赖
    模型假设」，不能写成「只有我们控得住误报」。

    **Do not claim a blanket win over every baseline. The two families where we trail have been fully attributed.** After the three-path configuration, the sequential layer, false-alarm alignment, and **subtracting the chance-alarm baseline**: this method's mean is **0.48** (0.47 at alpha=0.05), B2 markov 0.29, B4 tabor 0.21, B3 butla 0.17, B5 hsmm 0.11, B1 mbdf 0.01. But **B2 beats this method on A4 (0.23 versus 0.17) and A6 (0.28 versus 0.14), and both alphas reproduce it**, so it is not a resolution artifact. The attribution has been measured item by item (rule 23): **it is entirely budget dilution** — at a full budget the structural channel scores 0.31 on A4 and 0.45 on A6, level with B2's 0.41 and 0.45, and after an even three-way split only 0.18 and 0.19 remain. The writable statement is "a mean lead of 1.4–1.7 times, with no family at zero, while B2 is exactly zero on A3/A5". **It must not be written as a blanket win.** Also, B5 hsmm's calibration drift is 1.0×, comparable to conformal, so M8's selling point can only be written as "the control does not depend on a model assumption", not as "only we can hold the false-alarm rate".

18. **两个报告口径缺陷，都会安静地把结论带偏，必须常查。**
    (a) **延迟预算口径的 DR 有偶然地板 1-(1-FPR)^(budget+1)**，alpha=0.05
    时高达 0.43。它不违反任何误报约束、不报错，只是一律抬高所有方法——
    而对弱基线是相对更大的恩惠：B1 MBDF 在 alpha=0.05 下未减地板拿到 0.38
    （六族 0.31-0.50，它自己的地板是 0.326），看上去「原方法也有三成检出
    率」，直接给 T-a 不可能性结果提供反例。减地板后本方法对 B2 的领先由
    1.3 倍变 1.7 倍、对 B5 由 2.6 倍变 4.4 倍。T34。
    (b) **并行子检测器的路数受 m <= alpha*(n_b+1) 约束。** 良性参照流 508
    条时经验 p 下界 1/509，四路均分后每路 alpha/4=0.0025 只容 1 个秩位，
    实际执行的是「取良性最大值作阈值」。失真是**攻击特异**的：A3 被削
    9.9 倍、A5 削 7.2 倍（正是时序通道那两个有理论支撑的核心攻击），而 A2
    不变。于是逐消息表的攻击族间相对大小完全不可信，且**系统性歧视多通道
    方法**。这是规则 6（校准集规模）的同一条约束在新位置咬人。T35。

    **Two reporting-rule defects, both of which quietly bend the conclusion, and both of which must be checked routinely.**
    (a) **Detection rate under a delay budget has a chance-alarm baseline 1-(1-FPR)^(budget+1)**, as high as 0.43 at alpha=0.05. It violates no false-alarm constraint and raises no error; it just lifts every method — and it is a relatively larger gift to a weak baseline. B1 MBDF, without subtracting the floor, scores 0.38 at alpha=0.05 (0.31–0.50 across the six families; its own floor is 0.326), which looks like "the original method also detects about thirty percent" and hands T-a a counterexample to the impossibility result. After subtracting the floor, this method's lead over B2 goes from 1.3× to 1.7×, and over B5 from 2.6× to 4.4×. T34.
    (b) **The number of parallel sub-detectors is constrained by m <= alpha*(n_b+1).** On a benign reference stream of 508 messages the empirical p floor is 1/509, and after a four-way split each path's alpha/4=0.0025 admits only one rank, so what actually runs is "take the benign maximum as the threshold". The distortion is **attack-specific**: A3 is cut 9.9× and A5 7.2× (exactly the two core attacks the timing channel has theory for), while A2 is unchanged. Relative sizes across attack families in the per-message table are then not believable, and the rule **systematically discriminates against multi-channel methods**. This is the same constraint as rule 6 (calibration-set size) biting in a new place. T35.

19. **E2 消融证明三个模块不必要，一个必须撤下标题。** 每路 alpha 固定
    （排除"去掉一条路等于给剩下每条路加预算"的混淆）后的净贡献：
    时序通道 **−0.11**（去掉后 A3/A5 精确归零，唯一不可替代）、
    硬层 F **−0.07**、结构通道 −0.04、conformal −0.01、
    **互锁通道 +0.01**、**Fisher 合成路 +0.03**、**路线协变量 +0.04**
    （后三项为正即"去掉更好"）。三条推论：(a) 跨设备互锁在没有工件身份
    标识的产线上撑不起头条主张，**已从标题撤下**——定稿标题为「基于时序半
    马尔可夫与参考模型可行性约束的工业生产调度层注入攻击检测」，两个方法词
    与本表选中的三条路一一对应（参考模型↔硬层 F、时序↔时序通道、马尔可夫↔
    结构通道）；
    (b) Fisher 合成针对的多通道攻击已按红队口径实现为 A8：可实现、确
    实跨通道、硬层不触发，但加合成路在序贯口径下 A8 Δ=-0.04、A1-A6
    Δ=-0.04，**正式撤掉**（结论五十三，`tools/a8_fisher.py`）；
    (c) 路线协变量的 sigma 收益只有 3%（0.236->0.228），此前的
    0.355->0.116 只在多路线搬运分组内成立——**全部 29 个分组里具名路线
    合计 34 条，多数分组单一路线、条件化是空操作**。

    **The E2 ablation shows three modules are unnecessary, and one must come off the title.** With each path's alpha held fixed (so "removing a path" is not confused with "giving the remaining paths more budget"), the net contributions are: timing channel **−0.11** (removing it zeroes A3/A5 exactly; the only irreplaceable one), hard-constraint F **−0.07**, structural channel −0.04, conformal −0.01, **interlock channel +0.01**, **Fisher fusion path +0.03**, **route covariate +0.04** (a positive sign on the last three means "better when removed"). Three corollaries: (a) cross-device interlock cannot carry a headline claim on a line with no workpiece identity, and **it has been removed from the title** — the settled title is "detection of injection attacks on the industrial production scheduling layer based on timing semi-Markov models and reference-model feasibility constraints", and the two method words match the three paths this table keeps (reference model ↔ hard-constraint F, timing ↔ timing channel, Markov ↔ structural channel); (b) the multi-channel attack that Fisher fusion targets has been realized as A8 under the red-team rule: it is realizable, it really is cross-channel, and the hard-constraint layer does not fire, but adding the fusion path under the sequential rule is Δ=-0.04 on A8 and Δ=-0.04 on A1–A6, so it is **formally removed** (conclusion 53, `tools/a8_fisher.py`); (c) the sigma gain of the route covariate is only 3% (0.236->0.228). The earlier 0.355->0.116 holds only inside multi-route transport groups — **across all 29 groups the named routes total 34, most groups have a single route, and conditioning is a no-op**.

22. **alpha 配额只能用良性判据选，绝不能在相邻时间折上按攻击表现选。**
    实测 calib 折选出的配额恰是 test 折上最差的那个（均分五路：calib 0.608
    第一、test 0.370 最差），而 calib 排第四的 {硬层,时序,结构} 在 test 上
    是最好的 0.482——**两折排序近乎反相关**。两个成因：同一配额从 calib 到
    test 掉 39%（纯粹晚了一折的概念漂移），且路数越多退化越大（五路 −0.238、
    三路 −0.094）。可用的判据是结论四十七的天花板：给每路配额 alpha_i，若
    alpha_i/q_i < 0.5 则不给预算（q_i = 该路离散异常事件的良性发生率，迭代
    到不动点）。实测正确剔除互锁（q=0.0315、天花板 0.397），test +0.058。
    **通用的"最异常处原子质量"已试过并失败**：硬层良性分数全并列在 0，读成
    q=1.0 把最有用的一路剔掉；互锁的原子被随机化 p 值摊成连续区间，读成
    0.0017 而非 3.15%。天花板是**通道语义**，必须逐通道声明——而随机化
    p 值（规则 5 要求的那一步）恰恰会抹掉这个信息，两条规则之间存在张力。
    最终配置 = 硬层 + 时序 + 结构：互锁由良性判据剔除、合成由 A8 红队
    实测剔除，两条理由都不依赖测试折。T37。

    **The alpha quota may be chosen only by a benign criterion, never by attack performance on an adjacent temporal fold.** The quota selected on the calib fold is exactly the worst one on the test fold (even five-way split: calib 0.608 is first, test 0.370 is worst), while {hard-constraint layer, timing, structure}, fourth on calib, is the best on test at 0.482 — **the two folds' rankings are nearly anti-correlated**. Two causes: the same quota drops 39% from calib to test (pure concept drift one fold later), and more paths degrade more (five paths −0.238, three paths −0.094). The usable criterion is the ceiling of conclusion 47: give each path a quota alpha_i, and give it no budget if alpha_i/q_i < 0.5 (q_i is that path's benign rate of discrete anomalous events, iterated to a fixed point). Measurement correctly drops interlock (q=0.0315, ceiling 0.397), test +0.058. **The generic "atom mass at the most anomalous point" was tried and failed**: the hard-constraint layer's benign scores all tie at 0 and are read as q=1.0, dropping the most useful path; interlock's atom is spread by the randomized p-value into a continuous interval and read as 0.0017 rather than 3.15%. The ceiling is **channel semantics** and must be declared per channel — and the randomized p-value (the step rule 5 requires) is exactly what erases that information, so the two rules are in tension. Final configuration = hard-constraint layer + timing + structure: interlock is dropped by the benign criterion, fusion is dropped by the A8 red-team measurement, and neither reason depends on the test fold. T37.

21. **互锁通道的功效上界 = 攻击触发率 × min(1, alpha/q_部署)，q 必须取
    部署流实测值。** 训练折 q=0.0054 会让人以为天花板不生效，而测试流实测
    0.047（**漂移 9 倍，全项目最大**），天花板只有 0.21；代入 A4 的 0.69
    触发率得 0.145，与覆盖矩阵的 0.12 吻合。已试过跨 case 全局令牌池 +
    守恒（`interlock_scope='global'`）：q 由 1.70% 压到 0.22%、LATE 精确
    归零，但攻击触发率同时由 0.69 砍到 0.41，**端到端完全打平**，故默认
    仍取 'case'。**推论：要让互锁够用需把部署 q 压到 alpha 量级（约 1%），
    近似身份解析只做到 2.3%，剩下一半必须靠真正的 NFC/RFID 工件标识。**
    近似身份是一条走过并证明不通的路，如实写成负面结果比不写有价值。T36。

    **The interlock channel's power bound is attack trigger rate × min(1, alpha/q_deployment), and q must be the value measured on the deployment stream.** A training-fold q=0.0054 makes the ceiling look inactive, while the test stream measures 0.047 (**a 9× drift, the largest in the project**) and the ceiling is only 0.21; times A4's trigger rate 0.69 that is 0.145, which matches the coverage matrix's 0.12. A cross-case global token pool plus conservation (`interlock_scope='global'`) was tried: q falls from 1.70% to 0.22% and LATE is exactly zero, but the attack trigger rate is cut from 0.69 to 0.41 at the same time, so **end to end they tie**, and the default stays 'case'. **Corollary: to make interlock usable, deployment q must be pressed to the order of alpha (about 1%). Approximate identity resolution only reaches 2.3%; the remaining half needs a real NFC/RFID workpiece identity.** Approximate identity is a path that was walked and shown not to work. Writing it as a negative result is worth more than omitting it. T36.

20. **M8 conformal 的消融必须放在 FPR 表，不能放在 DR 表。** E1/E2 一律
    按误报对齐评测，而 M8 的作用就是把误报对齐——放进 DR 表等于让它自己
    抵消自己（实测 −0.01，看似无用）。它的证据只能来自误报侧：规则 5
    （不随机化则 FPR 达 1.000）、参数阈值使 FPR 近乎翻倍、原始参数化
    p 值在尾部错近两个数量级、时间序下退化 1.8 倍。

    **The M8 conformal ablation must sit in the FPR table, not the DR table.** E1/E2 are always evaluated with false alarms aligned, and M8's job is exactly to align false alarms — putting it in the DR table lets it cancel itself (measured −0.01, which looks useless). Its evidence can come only from the false-alarm side: rule 5 (without randomization the FPR reaches 1.000), a parametric threshold nearly doubles the FPR, a raw parametric p-value is wrong by nearly two orders of magnitude in the tail, and under temporal order it degrades by 1.8×.

23. **喂给 conformal 校准器的必须是保序的原始分数，不是随机化 p 值；这与
    规则 5 的边界必须写清。** 规则 5 针对**直接拿去比 alpha** 的 p 值。喂给
    校准器时随机化只会毁掉次序：结构通道的随机化 PIT 里 `U*at` 项，其 `at`
    （并列尾部质量）与该行支撑度成反比——厚支撑行 0.03、薄支撑行 **0.5**，
    于是薄支撑行完全没有功效，而攻击恰好落在薄支撑行上（常见转移没什么可
    伪造的）。换成预测概率后满预算差距由 −0.10 收到 −0.05，**且经验 FPR
    由 0.0217 降到 0.0138**（名义 0.01），不是以误报换功效。同型错误已发作
    三次：时序 p 值撞地板（规则 10）、天花板判据的原子被抹掉（规则 22）、
    本条。T38、`DetectorConfig.struct_score='prob'`。

    **What is fed to the conformal calibrator must be an order-preserving raw score, not a randomized p-value; the boundary with rule 5 must be written clearly.** Rule 5 is about p-values **compared directly with alpha**. Randomization fed to a calibrator only destroys order: in the structural channel's randomized PIT the `U*at` term has an `at` (tied tail mass) inversely proportional to that row's support — 0.03 on a thick-support row, **0.5** on a thin-support row — so a thin-support row has no power at all, and the attack lands exactly on thin-support rows (a common transition has little that can be forged). After switching to the predictive probability the full-budget gap shrinks from −0.10 to −0.05, **and the empirical FPR falls from 0.0217 to 0.0138** (nominal 0.01). That is not buying power with false alarms. The same kind of error has fired three times: the timing p-value hitting the floor (rule 10), the ceiling criterion's atom being erased (rule 22), and this one. T38, `DetectorConfig.struct_score='prob'`.

24. **比较装置只许校准一次。** `judge` 本身要做经验 p 值变换以对齐量纲，
    基线交的是原始分数、只经一次；我方若交 conformal p 值就被随机化两次，
    第一次的 `U*(1+eq)/(n+1)` 在并列密集处幅度超过相邻档位间距，**实测次序
    反转率 >20%、损失 0.07 净检出率**。部署时只有一层校准（冻结的
    conformal），`judge` 是它的替身而非附加层。这是一处**只罚我方一家**的
    口径缺陷，且不报错、不违反任何约束。T39，`_parts(conformal=False)`。

    **The comparison apparatus may calibrate only once.** `judge` itself applies an empirical p-value transform to align scales. Baselines hand in raw scores and pass through once; if we hand in a conformal p-value we are randomized twice. The first layer's `U*(1+eq)/(n+1)` exceeds the gap between adjacent bins where ties are dense, and **the measured order-reversal rate is >20%, costing 0.07 net detection rate**. At deployment there is only one calibration layer (the frozen conformal); `judge` stands in for it and is not an extra layer. This is a reporting defect that **penalizes only our side**, and it raises no error and violates no constraint. T39, `_parts(conformal=False)`.

25. **A4/A6 落后 B2 的归因已封闭：预算摊薄，与 M3 质量无关。** 三项逐一
    测量：(a) **split conformal 的数据代价为 0.00**——让 B2 只吃
    `Detector.fit` 内部真正用于拟合的 67% 折，六族逐格与吃满 train 完全相同；
    (b) 口径缺陷共 0.07（规则 23、24）；(c) 其余全是摊薄。**天花板判据无法
    改善这一点**：它只能剔除有离散功效上限的路，无法在三条连续路之间判断
    「哪一路对当前攻击有信号」——那需要攻击先验，一引入就回到规则 22 的过
    拟合。`tools/path_power.py`。

    **The attribution of A4/A6 trailing B2 is closed: budget dilution, unrelated to M3's quality.** Measured one by one: (a) **the data cost of split conformal is 0.00** — letting B2 eat only the 67% fold that `Detector.fit` actually uses for fitting, every cell of the six families matches eating the full train; (b) reporting defects total 0.07 (rules 23 and 24); (c) the rest is all dilution. **The ceiling criterion cannot improve this**: it can only drop a path that has a discrete power ceiling, and it cannot tell, among three continuous paths, "which path has a signal on the current attack" — that needs an attack prior, and introducing one returns to the overfitting of rule 22. `tools/path_power.py`.

## 四、落地进度 / 4. Implementation status

| 模块 / Module | 状态 / Status | 锚点断言 / Anchor assertions |
| --- | --- | --- |
| M1 `ingest` 解析与分链 / parse and split chains | 已实现 / implemented | T0, T7, T8 |
| M2 `procmodel` 导出 F / I / export F / I | 已实现 / implemented | T1, T3 |
| M5 `interlock` 令牌回放 / token replay | 已实现 / implemented | T1, T2 |
| M4 `timing` 时长模型与理论界 / sojourn model and bound | 已实现 / implemented | T0b, T0c, T4–T6c |
| M3 `structural` case 级转移模型 / case-level transition model | 已实现 / implemented | T7–T11 |
| M7 `sequential` CUSUM / e 过程 / CUSUM / e-process | 已实现 / implemented | T15, T16 |
| M8 `conformal` 随机化校准 / randomized calibration | 已实现 / implemented | T9–T14 |
| M6 `fusion` Fisher 合成与依赖检查 / Fisher fusion and dependence check | 已实现，**不进生产配置** / implemented, **not in the production configuration** | T17–T21, T40 |
| M0/M9 `detector` 在线回放流水线 / online replay pipeline | 已实现 / implemented | T24, T25 |
| `attacks` 注入器 / injectors | A1–A6 与 A8 已实现，A7 不实现即不报告 / A1–A6 and A8 implemented; A7 is not implemented and therefore not reported | T22, T23, T27, T40 |
| `metrics` 报告口径 / reporting rules | 已实现 / implemented | — |
| `tools/mbdf_undetectable` | 已实现 / implemented | 原方法不可检测集(T-a) / original method's undetectable set (T-a) |
| `tools/coverage_matrix` | 已实现 / implemented | 攻击 x 通道矩阵，24 格实测 / attack x channel matrix, 24 cells measured |
| `tools/struct_diag` | 已实现 / implemented | T29（状态粒度负面结果） / T29 (negative result on state granularity) |
| `baselines` B1–B5 | 已实现 / implemented | T30–T33 |
| `baselines` B6 lstm_ae / B7 flow | 不实现即不报告 / not implemented, therefore not reported | — |
| `baselines` 六档消融 / six-tier ablation | 骨架 / skeleton | — |

已实现部分与 `database/` 探针脚本逐位对齐：3,062 个活动 / 282 个 case，
F 953 次检查 0 违反，I 2,768 次检查 47 违反（LATE 17 / NEVER 29 / FAILED 1），
参考模型覆盖率 97.38%，case 级链 21 状态 / 2,780 次转移 / 140 个变体。
其中"BPMN 导出的 15 个资源、21 个操作与日志词表完全重合"这一点得到复核，
说明参考模型对**活动词表**零遗漏，未建模的只有位置级分支
（如 `sm_2_automatic_pos`）。

The implemented part lines up digit by digit with the probe scripts under `database/`: 3,062 activities / 282 cases, F checked 953 times with 0 violations, I checked 2,768 times with 47 violations (LATE 17 / NEVER 29 / FAILED 1), reference-model coverage 97.38%, case-level chain 21 states / 2,780 transitions / 140 variants. The point "the 15 resources and 21 operations exported from BPMN coincide completely with the log vocabulary" was rechecked, so the reference model misses nothing in the **activity vocabulary**. What is unmodeled is only position-level branches (such as `sm_2_automatic_pos`).

## 五、与既有材料的关系 / 5. Relation to existing material

- 数据集本体与探索性验证脚本在 `../database/ft_trier_iot_log/`
  （`probe_timing.py`、`derive_invariants*.py`、`probe_aft*.py`、
  `probe_structural*.py`、`probe_bound.py`）。那些是一次性的可行性探针，
  留在数据集旁边保存取证过程；本目录是收敛后的实现，二者结论必须一致，
  由 `tests/test_all.py` 的 T1–T14 把关。

  The dataset itself and the exploratory validation scripts live in `../database/ft_trier_iot_log/` (`probe_timing.py`, `derive_invariants*.py`, `probe_aft*.py`, `probe_structural*.py`, `probe_bound.py`). Those are one-shot feasibility probes, kept next to the dataset to preserve the evidence trail. This directory is the converged implementation. The two must agree, and T1–T14 in `tests/test_all.py` hold that line.

- 方法论证、创新点定位、威胁模型、实验设计见 `../新想法.md`。

  The method argument, the positioning of the contribution, the threat model, and the experiment design are in `../新想法.md`.

- 原方法（马尔可夫-贝叶斯双层框架）的论文与专利在 `../../paper02_old/`，
  在本目录里以基线 B1 的身份出现。

  The paper and patent of the original method (the Markov-Bayesian two-layer framework) are in `../../paper02_old/`. In this directory it appears as baseline B1.
