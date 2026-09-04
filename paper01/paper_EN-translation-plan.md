---
**User**

我建议先再次通读全文，理解了全文思想和重复出现的专业术语后，先做翻译的规划。按照：1）信、达、雅，翻译准确且符合英文术语表述；2）逻辑合理；3）固定的专有名词全文统一，符合这个研究领域习惯；这些原则方法实现后续翻译。
---

# paper_EN 翻译规划（2026-09-03）

对象：`paper01/paper_EN.tex`（由中文稿复制；题目与关键词已英译）。
原则：**信**（不改主张、数字、口径）／**达**（英文读者一次读懂）／**雅**（调度 + AGV/MAPF 通行说法，不用预审口吻）。
专名以本表为准。`paper-card.md` §6 仍是 8 月口径（把「预约表试探」当正式名）；`paper-ledger.md` §七是 9 月中文锁。英文锁以**本文件**为准。

---

## 0. 全文在说什么（翻译时不得走样）

问题沿用 van Os & Basten 已形式化的「带无冲突运输约束的柔性作业车间」，贡献在求解方法，不在问题定义。
常数矩阵看不见让行；两阶段方法看见争用却不能回头改指派。本文用**闭环双层框架**连接两层：

1. **评价通路 = 路由内嵌评价**：每个候选的适应度 = 下层无冲突路由后的完工时间（让行进入目标）。
2. **决策通路 = 预约表感知的车辆派遣**：选车前在预约表上两段试算，不按畅通时间派车。

两项优化（可采纳下界剪枝、胜者路径复用）不改变所选车辆与时间表，使派遣在同挂钟下付得起。
实验用四级阶梯拆两个维度（搜索是否计入延误 × 如何选车）。闭环是较大且逐组稳健的一笔；派遣合计显著、逐组看不清。两种更厚的接口（走廊加价、按让行改派/错峰）同预算下无稳定收益，是对照不是贡献。

翻译时**不得**把「沿用问题类」写成 propose；不得把合计显著写成逐组成立；不得把「尚不足以指出」写成 we do not claim 的口号体（英文用 *the sample is not sufficient to identify …*）。

---

## 1. 操作约定（每轮都遵守）

- **不动**：`\newcommand` 宏名与宏体、`\label`/`\ref`/`\cite` 键、`%` 注释（除非该注释会渲染）、算法过程名（`Route`、`Decode`、`EarliestEntry`）、布局档名（`funnel/high/mid/low/scatter`）、配置名（B0/B0+/B1/B2）。
- **数字一律走宏**，不把 `\GainLoopRule{}` 展开成 18.86%。
- **一句中文对一句英文**，不合并段落、不删交叉引用、不新增加强副词（*clearly, significantly better, first*）。
- **先锁词再写句**。本表没有的近义说法不要自造；拿不准先补进本表。
- **主张强度对齐中文**。中文是「尚未指出 / 不就规模作主张 / 采用而非提出」，英文用同一强度，不用 *proves / guarantees / optimal* 去替换「可证不改变输出」之外的句子。
- 工作顺序：专名表冻结 → 章节标题 → 摘要 → §3–§4（术语诞生地）→ §5 → §1–§2 → §6 → 图表题注与手打表 → 生成表另开一轮。
- 图文件：`paper_EN.tex` 已改引用不带 `_CN` 的英文 PDF（九张均已存在）。英文画图脚本中，画布文字已是英文；`fig_motivating.py` 的中文图内文字已抽出为 `STRINGS` / `STRINGS_CN` 并重出图。`fig_protocol.py` 的「开/关」只作 CSV 查找键，不入图。
- `\input{tab/tab_*_EN.tex}` 已切到英文生成表；中文稿仍读 `tab_*.tex`。重跑 `py paper01/tab/gen_tables_ladder.py` 会同时更新两套。

---

## 2. 专名总表（全文唯一用名）

首次出现：全称 + 一句定义；后文用表中「后文」。禁止列不得出现在读者可见正文（文献原词转述除外）。

### 2.1 框架与机制

| 中文 | 英文（锁定） | 后文 | 禁止 | 领域习惯 |
|---|---|---|---|---|
| 闭环双层框架 | closed-loop bilevel framework | the framework | joint / integrated / bi-level programming | bilevel 是运筹通行拼法 |
| 开环 / 闭环 | open-loop / closed-loop | 同左 | 开环搜索、在环 | 首次括注：search ignores / includes conflict-induced delay |
| 路由 | routing | routing | 不要为避歧义改掉 | 题目已用；首次 = conflict-free path planning on the corridor network |
| 无冲突路由 / 无冲突路径规划 | conflict-free routing / conflict-free path planning | routing | collision-free navigation（过宽） | AGV 文献常用 conflict-free |
| 路由器 | conflict-free path planner (hereafter, the router) | router | 单独抛 router | 不是上网设备 |
| 路由内嵌评价 | routing-in-the-loop evaluation | 同左 | in-the-loop evaluation, online evaluation | 适应度取自真实路由后的 makespan，不是「评价路由」 |
| 评价通路 | evaluation path | 同左 | feedback loop 1 | 首次：the evaluation path, i.e. routing-in-the-loop evaluation |
| 决策通路 | decision path | 同左 | control path | |
| 预约表感知的车辆派遣 | reservation-table-aware vehicle dispatching | reservation-table-aware dispatching | probing dispatch, congestion-aware dispatch（作本文机制名） | 标题/贡献/关键词用全称 |
| 规则派车 | rule-based dispatching | 同左 | greedy / heuristic dispatch | 即 \eqref{eq:rule}、空闲优先 |
| 试算 | trial query（两段式：two-leg trial query） | trial query | 作机制名的 probe / 试探 | 操作：查表、不写入最终时间表。宏名 `Probe` 不改 |
| 空闲优先派车 | idle-first dispatching | 同左 | nearest-vehicle（除非引 Lu） | Li 2026 的对照规则 |
| 可采纳下界剪枝 | admissible lower-bound pruning | the pruning | speedup trick | A* 用语 admissible |
| 胜者路径复用 | winner-path reuse | the reuse | path cache（单独用） | |
| 低开销 | low-overhead | 同左 | cost reduction, cheaper | 指单次评价计算开销，不是目标函数 |
| 附加额外代价 / 加价 | extra cost on occupied corridor–time slots; thereafter **surcharge** | surcharge | 未加注的 penalty | Kim 文转述可保留 congestion penalty |
| 层间接口 | inter-layer interface | interface | coupling channel | |
| 改派 | reassignment | 同左 | migration, re-allocation | |
| 错峰 | staggering | 同左 | delay operator | 调开工时刻，不改机器 |
| 按让行记录的局部搜索 | yield-record-guided local search | 同左 | certificate-guided LS | 不要把「冲突凭证」当读者用名 |

### 2.2 资源、延误、度量

| 中文 | 英文（锁定） | 后文 | 禁止 | 领域习惯 |
|---|---|---|---|---|
| 走廊 | corridor | 同左 | edge/arc（读者正文）；通道仅用于 parallel lanes | 与 spine 文献一致 |
| 并行通道 | parallel lane | lane | corridor（指数并列通道时） | |
| 停靠位 | berth | 同左 | parking lot | A6：等待在 berth，不占通行资源 |
| 机械臂 | robotic arm | arm | device | FJSP / 表内 / 文献语境可用 machine |
| 机器指派 | machine assignment | assignment | allocation | 与 FJSP 文献对齐 |
| 工序排序 | operation sequencing | sequencing | permutation（除非讲染色体） | |
| 让行等待 | yielding wait | yielding wait | congestion loss, blocking（除非真阻塞） | MAPF 常说 wait；本文要强调「让给谁」时用 yielding |
| 争用 / 走廊争用 | contention / corridor contention | contention | traffic jam | |
| 争用强度 | contention intensity | 同左 | congestion level（作本文指标名） | 自定义量，首次给定义 |
| 完工时间 | makespan | makespan | completion time（作 $C_{\max}$ 时） | 标准 |
| 适应度 | fitness | 同左 | objective value（可作解释，不作替换） | GA |
| 可实现的完工时间 | realized makespan | 同左 | reported / planned makespan | 统一执行器的输出 |
| 畅通最短路 / 理想行驶时间 | unimpeded shortest-path time / unimpeded travel time | unimpeded time | free-flow（可作一次同义） | 矩阵 $t^{*}$ |
| 常数运输时间矩阵 | constant travel-time matrix | the matrix | static distance matrix | FJSP_PT 约定 |
| 预约表 | reservation table | the table | booking table | SIPP / AGV 通行 |
| 时间窗预约 | time-window reservation | 同左 | time-slot booking | |
| 时间窗 Dijkstra | time-window Dijkstra | 同左 | SIPP（本文明确未采用按区间分标签） | |
| 占用区间 | occupancy interval | interval | reservation window | 半开 $[t,t+\tau_e)$ |
| 检查点与回滚 | checkpoint and rollback | 同左 | 首次括注 save and restore the table | |
| 关键链 | critical chain | 同左 | critical path（除转述 Qin） | 作业车间局部搜索 |
| 稀释 | dilution | 同左 | attenuation | §5.6.3 |

### 2.3 实验与统计

| 中文 | 英文（锁定） | 后文 | 禁止 |
|---|---|---|---|
| 同挂钟预算 | equal wall-clock budget | wall-clock budget | same time, equal runtime（可解释一次） |
| 同代数 | equal generation count | equal generations | equal iterations（单独用） |
| 统一执行器 | common executor | 同左 | unified simulator |
| 四级基线阶梯 | four-level baseline ladder | the ladder | Baseline A–D |
| 受控算例 | controlled instance | instance | synthetic toy（除非讲动机图） |
| 组（读者可见） | instance | per-instance | cell, grid cell |
| 方向（布局/车臂比/柔性） | axis / factor | factor | family, clan |
| A/B/C 族 | Family A / B / C | Family A | tribe |
| 车臂比 | vehicle-to-arm ratio | $N_A/N_M$ | fleet ratio（单独、无定义） |
| 柔性 $F$ | flexibility | $F$ | optionality |
| 异构度 $H$ | heterogeneity | $H$ | diversity |
| 哑铃 | dumbbell | 同左 | 首次定义；工业类比 spine, tandem loop |
| 网格 | grid | 同左 | mesh |
| 近加性 | near-additivity | near-additive | almost linear |
| 正交互 | positive interaction | 同左 | synergy |
| 合计 | in the aggregate / pooled | pooled | overall significance（易读成逐组） |
| 尚不足以指出……稳定兑现 | not sufficient to identify on which class of instances the gain is stable | 同左 | we do not claim an applicable regime（口号） |
| 较大的一笔 / 较小但仍显著 | the larger effect / a smaller but still significant effect | 同左 | main effect / secondary effect（口号；摘要中文残留，英译按本行） |
| Hodges–Lehmann 伪中位数 | Hodges–Lehmann pseudomedian | pseudomedian | robust median |
| 配对 Wilcoxon | paired Wilcoxon signed-rank test | Wilcoxon | Mann–Whitney（除非真是独立样本） |
| Holm 校正 | Holm correction | Holm | Bonferroni（除非比较） |

### 2.4 文献与问题类（专名从文献，不另译花）

| 中文 | 英文 |
|---|---|
| 带运输的柔性作业车间 / FJSP\_PT | FJSP with transportation (FJSP\_PT) |
| 带无冲突运输约束的柔性作业车间 | FJSP with conflict-free transportation constraints |
| 多智能体路径规划 | multi-agent path finding (MAPF) |
| 任务持续到达 | settings with continuously arriving tasks；表内文献名可写 lifelong MAPF |
| 安全区间规划 / SIPP | Safe Interval Path Planning (SIPP) |
| 基于逻辑的 Benders 分解 | logic-based Benders decomposition (LBBD) |
| memetic 算法 | memetic algorithm |
| 间接指标 | indirect measure（density, learned edge weights）；proxy 可作形容词，不作专名 |

---

## 3. 章节标题（先锁，后文 `\ref` 读者看到的就是这些）

| 中文 | 英文 |
|---|---|
| 引言 | Introduction |
| 研究背景与动机 | Background and motivation |
| 与已有工作的差距 | Gap relative to prior work |
| 本文方法 | Approach |
| 主要结果 | Main results |
| 贡献 | Contributions |
| 相关工作 | Related work |
| 考虑运输的柔性作业车间调度 | Flexible job shop scheduling with transportation |
| 任务外生的无冲突路由与拥堵感知派车 | Conflict-free routing with exogenous tasks and congestion-aware dispatching |
| 调度与无冲突路由的一体化:反馈深度与本文定位 | Integrating scheduling and conflict-free routing: feedback depth and our position |
| 问题描述与数学模型 | Problem statement and model |
| 建模假设 | Modelling assumptions |
| 决策变量与派生的运输任务 | Decision variables and induced transport tasks |
| 时序关系与可行性条件 | Timing relations and feasibility |
| 与 FJSP\_PT 的关系 | Relation to FJSP\_PT |
| 计算复杂度 | Computational complexity |
| 算例特征的刻画 | Instance features |
| 闭环双层框架 | Closed-loop bilevel framework |
| 框架总览:路由内嵌评价与决策通路 | Overview: routing-in-the-loop evaluation and the decision path |
| 下层:时间窗预约与无冲突路由 | Lower level: time-window reservation and conflict-free routing |
| 上层:编码与事件驱动解码 | Upper level: encoding and event-driven decoding |
| 预约表感知的车辆派遣 | Reservation-table-aware vehicle dispatching |
| 层间接口的三种选择 | Three choices for the inter-layer interface |
| 低开销:可采纳下界剪枝与胜者路径复用 | Low overhead: admissible lower-bound pruning and winner-path reuse |
| 按让行记录的局部搜索 | Yield-record-guided local search |
| 外层遗传算法 | Outer genetic algorithm |
| 复杂度与代价分析 | Complexity and cost |
| 实验与结果分析 | Experiments |
| 实验设置 | Experimental setup |
| 受控算例族 | Controlled instance families |
| 比较协议 | Comparison protocol |
| 实现与运行环境 | Implementation and environment |
| 四级基线阶梯 | Four-level baseline ladder |
| 四级阶梯的合计比较 | Aggregate comparison on the ladder |
| 近加性与不可互相替代 | Near-additivity and non-substitutability |
| 三族扫描与单组分辨率 | Three-factor scans and per-instance resolution |
| 消融与受控负对照 | Ablations and controlled negative controls |
| 代价律与降本效果 | The cost law and the effect of the two speed-ups |
| 案例：漏斗算例上的甘特图与关键链 | Case study: Gantt chart and critical chain on the funnel instance |
| 公开基准上的退化比较 | Degenerate comparison on public benchmarks |
| 结论 | Conclusion |
| 结论与贡献 | Findings and contributions |
| 局限 | Limitations |
| 未来工作 | Future work |

命题/引理标题随正文译，label 不动：
- `lem:label`：Earliest arrival is sufficient
- `prop:decodable`：Every chromosome is decodable
- `prop:speedup_equiv`：The two speed-ups do not change the selected vehicle or the timetable

---

## 4. 逻辑与语气（信）

- 贡献四条与结论四条必须同构，机制名与题目逐字一致（英文字符串）。
- 「不改变所选车辆与最终时间表」全文统一，不用 *provably equivalent*（未写等价类型）。
- 负对照：*as controls; no stable makespan gain under the same wall-clock budget*。不写 *we implemented failures so the reader can see the cost*。
- 局限 ↔ 未来工作五条对五条，译完后对一遍挂靠句。
- 摘要中文残留「主效应 / 次效应 / 合计口径」：英译按 §2.3「较大的一笔 / 较小但仍显著 / in the aggregate」，不要译回 *main effect / secondary effect*。

---

## 5. 建议施工顺序

1. 本表确认（本步）。  
2. 写入全部 `\section`/`\subsection` 英文标题。  
3. 摘要四段（用本表专名；保留全部宏）。  
4. §3 假设与符号、§4 机制定义（后文都指回这里）。  
5. §5 协议与结果（口径句最容易译滑）。  
6. §1–§2（已有专名可复用，避免引言另起一套词）。  
7. §6。  
8. 图注、`tab:related`、`tab:notation`、`tab:arms`、`tab:attrib`。  
9. 生成表 `tab_*.tex` 与中文图：单独一轮，不和正文混做。

每块译完自检：专名是否落在本表；宏是否仍在；有无把「组」译成 cell；有无把试算升格成机制名。

## 6. 进度（2026-09-03）

- [x] 专名表冻结
- [x] 全部 `\section`/`\subsection`/`\subsubsection`/`\paragraph` 英文标题；lemma/prop/algorithm 标题；定理环境印刷名（Assumption/Proposition/Lemma/Figure/Table/Algorithm/Proof）
- [x] 摘要四段（主/次效应按 §2.3 译为 larger / much smaller；组 = instances）
- [x] §3 全文（含手打 `tab:notation`）
- [x] §4 全文（含 `fig:framework` 题注、`tab:attrib`、三则算法内文；首次给出 router 全称）
- [x] §5 全文（协议、阶梯、合计/近加性/逐组分辨率、消融、代价律、案例、公开退化比较；手打 `tab:arms` 与 §5 图注；生成表已切 `tab_*_EN.tex`）
- [x] §1–§2（含手打 `tab:related`；`% [ref_check: ...]` 注释未动）
- [x] §6（结论四条与贡献四条机制名同构；局限 (1)–(5) ↔ 未来工作 (1)–(5) 均有挂靠句）
- [x] 其余图注与 `tab:related`（图注已随 §1/`tab:related` 译完；`paper_EN.tex` 的 `\includegraphics` 已改指向不带 `_CN` 的英文 PDF）
- [x] 生成表：`gen_tables_ladder.py` 一次写出中英两套（`tab_*.tex` 供 `paper.tex`，`tab_*_EN.tex` 供 `paper_EN.tex`）；数字同源。`tab_ablation.tex` 已是英文且未被任何正文 `\input`。
