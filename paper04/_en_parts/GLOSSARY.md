# paper04 CN -> EN translation: glossary and style guide

## Style
- Target: a journal paper in operations research / scheduling (e.g. IJPR, C&OR, IEEE T-ASE). 信达雅: faithful to the meaning, fluent idiomatic academic English, concise. Do not translate word by word; restructure sentences so the logic is explicit (topic sentence first, then reasons). Avoid Chinglish ("this paper's", "carry out ... of ...", strings of nouns).
- Use "we" for the authors' actions ("We define ...", "We report ..."); "this paper" is fine for claims about the paper's scope. Present tense for claims and definitions, past tense for what was measured in experiments.
- No contractions. American spelling (behavior, modeling, labeled).
- Keep sentences at most ~35 words; split long Chinese run-on sentences.
- Do not add or drop technical content, numbers, hedges, or claims. If the Chinese is defensive or repetitive, keep the meaning but express it crisply.

## LaTeX rules (strict)
- Keep ALL LaTeX commands, macros (\NPairs, \FeasRone, \STRC, ...), labels, refs, cites, math, and environment structure exactly. Never expand a number macro into a literal.
- Translate text inside \caption{}, \Description{}, \textbf{}, \emph{}, table cells, \item, theorem optional titles [..], \paragraph{}, \section{} etc.
- Translate `%%` comments into English too (concise; keep their technical content). Keep comment lines as comments.
- Figures: change `figures/xxx_CN` to `figures/xxx` (English figures exist with the same stem without `_CN`).
- Chinese punctuation -> English punctuation. Chinese quotes 「」 or “” -> ``...''. Chinese "、" -> comma. "——" -> `---`. Full-width parentheses -> ASCII "( )" with a space before "(" in running text.
- "第~\ref{sec:x}~节" -> "Section~\ref{sec:x}"; "第~\ref{..}~章" -> "Section~\ref{..}"; "图~\ref{..}" -> "Figure~\ref{..}"; "表~\ref{..}" -> "Table~\ref{..}"; "命题~\ref" -> "Proposition~\ref"; "定义~\ref" -> "Definition~\ref"; "引理" -> "Lemma"; "注~\ref" -> "Remark~\ref"; "假设 A2" -> "Assumption A2"; "式~\eqref{..}" -> "Eq.~\eqref{..}" (or "\eqref{..}" at sentence middle).
- Chinese words inside math \text{..} must be translated (e.g. `\text{使}` -> `\text{such that}`, `\text{于}` -> `\text{in}`).
- Braced English words like {CUSUM} can be left as is.
- There must be NO Chinese characters left in the output, including comments.

## Terminology (use exactly these; keep consistent)
| Chinese | English |
|---|---|
| 柔性作业车间调度 | flexible job shop scheduling (FJSP) |
| 考虑运输的柔性作业车间 | flexible job shop with transportation |
| 工序 | operation |
| 工件 | job |
| 机器 / 机械臂 | machine / robotic arm |
| 车辆 / AGV | vehicle / AGV |
| 走廊 | corridor |
| 路网 / 走廊路网 | (corridor) network |
| 装卸站 | load/unload station (LU) |
| 工序依赖图 | operation-precedence graph |
| 时间窗预约 | time-window reservation |
| 预约表 / 时空预约表 | reservation table / spatiotemporal reservation table |
| 走廊占用 / 占用 | corridor occupancy / occupancy |
| 预约 | reservation |
| 让行 / 让行关系 | yielding / yielding relation |
| 让行边 | yield edge |
| 同车后继 / 同工件后继 / 同机后继 | same-vehicle successor / same-job successor / same-machine successor (edges) |
| 接续关系 | succession relations |
| 预约依赖图 / 依赖边 | reservation dependency graph / dependency edge |
| 时空预约闭包 (\STRC) | spatiotemporal reservation closure (\STRC) |
| 预约影响集 / 影响集 | reservation impact set / impact set |
| 起点 / 起点占用集 | seed / seed set (Src) |
| 起点工序集 | seed operation set |
| 传递闭包 | transitive closure |
| 对外封闭 / 结构闭合性 | closed under outgoing edges / structural closure |
| 包含性 | containment |
| 结构可预测性 | structural predictability |
| 重调度范围 | rescheduling scope |
| 划界 / 划界对象 | delineating the scope / the object on which the scope is delineated (short: "scope object") |
| 按工序依赖图划界 | scoping on the operation-precedence graph |
| 按预约影响集划界 | scoping on the reservation impact set |
| 受影响工序重调度 (AOR) | affected-operation rescheduling (AOR) |
| 影响域 T_impact | affected set \(T_{\mathrm{impact}}\) |
| 扰动 | disturbance |
| A 类 / B 类 扰动 | Class A / Class B disturbances |
| 走廊阻断 | corridor blockage |
| 走廊通行变慢 | corridor slowdown |
| 通行权临时取消 | temporary revocation of right of way |
| 机械臂故障 / 车辆故障 / 插单 | robotic-arm failure / vehicle failure / rush-order insertion |
| 阻断窗 / 受扰时段 | blockage window / disturbed interval |
| 决策时刻 t_now | decision time \(t_{\mathrm{now}}\) |
| 尚未结束的占用 | unfinished occupancies (those with \(t^e>t_{\mathrm{now}}\)) |
| 已结束的占用 | finished occupancies |
| 允许改写 / 改写 | rewritable / rewrite |
| 保持原计划 / 集外保持 | kept as planned / kept outside the set |
| 改路 | reroute / rerouting |
| 第 1 级改路 | level-1 rerouting |
| 扩大允许改写的范围 / 扩域 | scope escalation / escalate the rewritable scope |
| 有界修复 | bounded repair |
| 局部恢复 | local recovery |
| 全局重调度 | global rescheduling |
| 热启动 | warm-started |
| 改动比例 | rewrite fraction |
| 完工时间 C_max | makespan \(C_{\max}\) |
| 算法耗时 | runtime |
| 恢复可行 / 可行率 | restore feasibility / feasibility rate |
| 释放集 | release set |
| 泄漏 | leak / leakage |
| 漂移 | drift |
| 差分试探 / 边集差分试探 | difference probe / edge-set difference probe |
| 冻结判据 | freezing criterion |
| 固定前缀解码 | fixed-prefix decoding |
| 重解码 | re-decoding |
| 全局右移 | global right shift |
| 对照臂 / 臂 | baseline arm / arm (R0+, R1, R2, RS, RD, RA — keep names) |
| 格 (算例--随机种子格) | cell (instance--seed cell) |
| 算例 | instance |
| 随机种子 | random seed |
| 对 (50 对) | pairs |
| 预算档 | budget level |
| 反超 / 交叉点 | crossover |
| 胜/持平/负 | win/tie/loss |
| 合池 | pooled |
| 四分位距 | interquartile range (IQR) |
| 视界 H | horizon \(H\) |
| 滚动视界 | rolling horizon |
| 段 (运输段) / 空载段 / 满载段 | leg / empty leg / loaded leg |
| 甘特图 | Gantt chart |
| 外部布局批次 | external-layout batch |
| 主批次 | main batch |
| 漏斗占比 | funnel share |
| 最小割 | minimum cut |
| 最小性 | minimality |
| 探索性 | exploratory |
| 小结 | Summary |
| 局限 / 后续工作 | Limitations / Future work |

## Section title reference (English titles already chosen)
Introduction; Background and motivation; The gap the operation-precedence graph cannot capture; Claims; Contributions; Organization;
Related work; Local rescheduling in job shops; Occupancy order on exclusive resources; Local replanning in conflict-free multi-vehicle routing; Flexible job shop scheduling with transportation; Positioning of this paper;
The corridor-reservation setting and the execution-time recovery problem; System setting and notation; Execution-time assumptions; A dichotomy of disturbances; The recovery problem;
The spatiotemporal reservation closure; Reservation dependency edges; Containment; Structural predictability;
Bounded repair on the reservation impact set; Rewritable set, kept-as-planned set, and level-1 rerouting; Scope escalation after failure; Comparison with global rescheduling;
Experiments; Protocol; E1: the operation-precedence graph yields an empty scope; E2: containment; E3: boundary ablation; Case Gantt chart; E4: structure (exploratory); E5: trade-off against global rescheduling; E6: crossing disturbance types with scope objects; E7: comparisons within the millisecond range; Sweep over disturbance magnitude; E8: extrapolation to larger instances; Reproduction on the external-layout batch; Summary;
Conclusion; Limitations; Future work.

## Terminology reference
An older, more literal English draft of the same paper is at `paper04/paper04.tex`. You may consult it for how terms were rendered, but the Chinese source has since been revised: translate from the Chinese source, not from the old draft, and prefer this glossary where they differ.
