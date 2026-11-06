# 论文压缩经验总结 / How to Compress a Research Paper

> 来源 / Source：对比三组"压缩前 → 压缩后"英文稿得到的经验规则。
> Rules distilled from three before/after pairs of English manuscripts:
>
> | 论文 Paper | 压缩前 Before | 压缩后 After | 词数变化 Words | 引文集合 Unique cites |
> |---|---|---|---|---|
> | paper01 (`paper_EN.tex` → `paper.tex`) | 24,840 词 words | 12,015 | −52% | 不变 unchanged |
> | paper02 (`paper02_EN.tex` → `paper02.tex`) | 13,675 | 10,835 | −21% | 不变 unchanged |
> | paper04 (`paper04_EN.tex` → `paper04.tex`) | 22,984 | 9,527 | −59% | 不变 unchanged |
>
> 原始要求 / Original instruction：不损失内容完整性和逻辑叙事，主要压缩重复章节、冗长表达。
> Keep content completeness and narrative logic; mainly remove repeated sections and verbose wording.
>
> 下面的条目把这条笼统要求细化为可执行的原则。每条先中文、后英文。
> The items below turn that broad instruction into actionable principles, Chinese first, then English.

---

## 0. 核心思想 / Core idea

**中文**：压缩的对象是**冗余**，不是**信息**。一篇初稿中，同一信息往往出现 3–5 次：摘要、引言贡献、方法小结、结果段落、表格、图、图注、结论各说一遍。压缩就是给每条信息找到**唯一的最佳位置**，其他位置删掉或改成一句指引。真正"新"的内容（定理陈述、主要数字、引文、局限）几乎一个不删。

**English**: Compress **redundancy**, not **information**. In a first draft the same fact typically appears 3–5 times: in the abstract, the contribution list, a method summary, the results prose, a table, a figure, its caption and the conclusion. Compression means giving each fact **one best home** and deleting the other occurrences or replacing them with a one-line pointer. Genuinely unique content (theorem statements, primary numbers, citations, limitations) is almost never removed.

**中文**：压缩率取决于初稿的冗余程度，而不是固定目标。冗余多的稿子（paper01、paper04）可压 50–60%；本来就紧凑的稿子（paper02）只压了约 20%，而且方法与理论部分几乎没动。

**English**: The achievable ratio depends on how redundant the draft is; it is not a fixed target. Verbose drafts (paper01, paper04) shrank by 50–60%. An already tight draft (paper02) shrank by only about 20%, and its method and theory sections were left almost untouched.

---

## 1. 硬约束：不能丢的东西 / Hard constraints: what must survive

1. **引文一篇不删 / Keep every citation.**
   - 中文：三组稿件压缩前后的去重引文集合完全相同。引用**次数**可以略减（74→65、52→50、49→47），即同一文献在相邻句子重复引用时只留一次。若删掉某段落导致某文献无处引用，就把该引用并入相邻句子。
   - English: In all three pairs the set of unique citations is identical before and after. The **number of citation instances** may drop slightly (74→65, 52→50, 49→47) by removing repeated citations of the same work in adjacent sentences. If deleting a passage would orphan a reference, move the citation into a neighbouring sentence.
2. **定理/命题/定义的陈述不删 / Keep all formal statements.**
   - 中文：命题、定理、定义的陈述原样保留；可压缩的是证明的叙述方式和陈述后面的"因此……"复述。
   - English: Proposition, theorem and definition statements stay as they are. What can be compressed is how the proof is narrated and the "Consequently, …" restatement that follows a statement.
3. **主要结果数字不删 / Keep primary result numbers.**
   - 中文：主要效应量、置信区间、校正后 p 值、可行率等核心结果保留（结果宏 137→133、119→104，删掉的几乎都是 min/max、IQR 等次要统计）。
   - English: Keep the core results: main effect sizes, confidence intervals, corrected p-values, feasibility rates and similar (result macros went 137→133 and 119→104; almost all removed ones are secondary statistics such as min/max ranges or IQRs).
4. **负面结果、局限和"不成立"的结论不删 / Keep negative results and limitations.**
   - 中文：方法表现较差的情形（例如"在 A4/A6 上低于 label-only 消融"）、显著性不足的比较、适用边界都要保留，最多缩短措辞。删掉它们会让论文显得夸大。
   - English: Keep cases where the method loses (e.g. "below the label-only ablation on A4/A6"), comparisons that are not significant, and scope boundaries; at most shorten the wording. Removing them makes the paper overclaim.
5. **逻辑链不断 / Keep the argument chain intact.**
   - 中文：动机 → 缺口 → 方法 → 证据 → 结论的每一环都至少保留一句话。可以合并，不能跳过。
   - English: Motivation → gap → method → evidence → conclusion: each link keeps at least one sentence. Links may be merged but never skipped.
6. **交叉引用不失效 / Don't break cross-references.**
   - 中文：合并章节时把被合并章节的 `\label` 一并放到新标题下（如 `\label{sec:e1}\label{sec:e2}\label{sec:e3}`），这样正文其他地方的 `\ref` 不会报错。
   - English: When merging sections, stack the merged sections' `\label`s under the new heading (e.g. `\label{sec:e1}\label{sec:e2}\label{sec:e3}`) so existing `\ref`s still resolve.

---

## 2. 先删什么：冗余的优先级 / What to cut first: a priority order

**中文**：按下列顺序处理，越靠前越"安全"、收益越大：

1. 同一内容的**第二种呈现形式**（表格已有的数据又画成图；正文已经说了的数字又写进图注）。
2. **重复陈述**（Claims 与 Contributions；Limitations 与 Future Work；Organization 段把每章内容再复述一遍）。
3. **过程性/历史性材料**（实现过程中修过的 bug 的来龙去脉、参数的调试历史、为何没采用某方案的长篇解释）。
4. **次要证据**（补充性的校准表、只有 2–4 个数据点的表、仅作"定性参考"的对照）。
5. **句子层面的冗长**（"i.e."式复述、过度对冲、强调格式、套话）。

**English**: Work through this order; earlier items are safer and give larger savings:

1. The **second presentation** of the same content (a figure that re-plots a table; a caption that repeats numbers already in the text).
2. **Repeated statements** (Claims vs. Contributions; Limitations vs. Future Work; an Organization paragraph that re-summarizes each section).
3. **Process or history material** (the story of bugs fixed during implementation, parameter-tuning history, long explanations of why an alternative was not used).
4. **Secondary evidence** (supplementary calibration tables, tables with only 2–4 data points, comparisons that are only a "qualitative reference").
5. **Sentence-level verbosity** ("i.e." restatements, excessive hedging, emphasis formatting, boilerplate).

---

## 3. 结构层面 / Structural rules

### 3.1 引言 / Introduction

- **合并小节 / Merge subsections.**
  - 中文：Background、Gap、Approach、Main results、Contributions、Organization 等五六个小节压成 2 个（paper01："动机与缺口""方法与贡献"），或干脆用加粗的段首词（run-in head）代替小节标题（paper04：**The gap.** / **Stance.** / **Contributions.**）。
  - English: Collapse five or six subsections (Background, Gap, Approach, Main results, Contributions, Organization) into two (paper01: "Motivation and gap", "Approach and contributions"), or replace subsection titles with bold run-in heads (paper04: **The gap.** / **Stance.** / **Contributions.**).
- **Claims 与 Contributions 只留一份 / Keep only one of Claims and Contributions.**
  - 中文：若"本文主张"与"本文贡献"讲的是同三件事，只保留贡献列表。每条贡献 = 加粗标题 + 1–3 句（结论 + 证据位置），而不是一整段机制描述。
  - English: If "Claims" and "Contributions" state the same three points, keep only the contribution list. Each item is a bold title plus 1–3 sentences (the claim and where the evidence is), not a full paragraph describing the mechanism.
- **主要数字在引言只出现一次 / State main numbers once in the Introduction.**
  - 中文：如果贡献列表里已有关键数字，就删掉单独的"Main results"段，反之亦然。
  - English: If the contribution list already carries the key numbers, delete the separate "Main results" paragraph, or vice versa.
- **章节安排段压成一句 / Reduce the roadmap to one sentence.**
  - 中文：从"第 X 节讨论了……包括……并通过图 Y 展示……"的逐节摘要，变为"第 2 节综述相关工作；第 3 节……；第 7 节总结。"
  - English: Replace a per-section summary ("Section X discusses…, including…, illustrated in Figure Y…") with a single line: "Section 2 reviews related work; Section 3 …; Section 7 concludes."
- **保留"立场/边界"段 / Keep the positioning paragraph.**
  - 中文：说明"本方法是什么、不是什么"的段落（如"影响集是测量，不是决策"）防止审稿人误读，应保留并压缩，而不是删除。
  - English: A paragraph that states what the method is and is not (e.g. "the impact set is a measurement, not a decision") prevents misreading by reviewers; compress it but don't delete it.

### 3.2 相关工作 / Related work

- 中文：合并主题相近的子小节（paper02：把"包级检测"和"连续控制检测"合并；把"一致性检查"和"序列异常"合并）。每篇文献只描述一次；"与本文的区别"集中在每组末尾写一句，而不是每篇文献后都写。
- English: Merge closely related sub-subsections (paper02 merged "packet-level" with "continuous-control" detection, and "conformance checking" with "sequence anomaly"). Describe each cited work once; state "how we differ" once at the end of each group rather than after every paper.

### 3.3 实验 / Experiments

- **合并同类实验 / Merge similar experiments.**
  - 中文：几个都在验证"性质成立/检查通过"的实验（paper04 的 E1–E3）合并成一节、一张表；新标题直接写结论或内容（"E1–E3: empty scope, containment, and boundary ablation"）。
  - English: Merge experiments that all verify that properties hold or checks pass (paper04 E1–E3) into one section with one table; give the merged section a title that states its content or finding ("E1–E3: empty scope, containment, and boundary ablation").
- **用结论式标题 / Use claim-style titles.**
  - 中文：例："E4: static structure does not predict the impact-set size (exploratory)"。标题已传达结论，正文就不用再铺垫。
  - English: Example: "E4: static structure does not predict the impact-set size (exploratory)". The title carries the finding, so the body needs no build-up.
- **去掉 `\paragraph` 层级 / Remove `\paragraph` layers.**
  - 中文：paper01 的 `\paragraph` 从 31 个减到 6 个。小标题过多会迫使每段都有开场白和收尾句；去掉后段落可以直接衔接。
  - English: paper01 went from 31 `\paragraph` headings to 6. Too many small headings force every paragraph to have its own opener and closer; without them paragraphs can flow directly.

### 3.4 结论、局限与展望 / Conclusion, limitations, future work

- 中文：把"局限（k）"和"未来工作：对应局限（k）……"合并为成对条目：**局限 + 对应的改进方向**写在同一条里，删掉"This corresponds to limitation (k)"之类的回指和重复描述。结论开头的贡献复述压成一段，数字只保留最核心的 1–2 个。
- English: Merge "Limitation (k)" and "Future work: this corresponds to limitation (k)…" into paired items, with **the limitation and its remedy in the same item**, and delete back-references such as "This corresponds to limitation (k)" along with the duplicated description. Compress the contribution recap at the start of the conclusion into one paragraph that keeps only the 1–2 most important numbers.

---

## 4. 图、表、算法 / Figures, tables, algorithms

1. **同一数据只保留一种形式 / One form per dataset.**
   - 中文：表格已给出全部数值时，删除把它重画成柱状图的图（paper02 删除 `fig:e1`，因为它是 `tab:e1` 的柱状图版本）。
   - English: If a table already gives every value, drop the figure that re-plots it as bars (paper02 removed `fig:e1`, a bar-chart version of `tab:e1`).
2. **次要表格降级为一句话 / Demote secondary tables to a sentence.**
   - 中文：只作"定性参考"的补充表（如换一种校准方式的结果表）删掉，把其中 1–2 个关键数字写进正文（paper02 的 `tab:e1calib` 只保留均值行和两个亮点）。
   - English: A supplementary table that is only a "qualitative reference" (e.g. results under an alternative calibration) is removed, and its 1–2 key numbers go into the text (paper02 `tab:e1calib`: only the mean row and two highlights survived).
3. **数据点极少的表改为一句话 / Turn near-empty tables into a sentence.**
   - 中文：例如每个方法只有 2–4 次报警的报警间隔表，改为"每种方法仅报警 2–4 次，不足以估计 ARL0"。
   - English: Example: an alarm-interval table where each method raised only 2–4 alarms becomes "each method raises only 2–4 alarms, too few to estimate ARL0".
4. **全部通过的检查用合计报告 / Report all-pass checks as totals.**
   - 中文：如果某列在每一行都是"10/10 通过"，删掉该列，在图注或正文写一句"所有实例均通过，合计见正文"。
   - English: If a column reads "10/10 pass" on every row, delete the column and write once, in the caption or text, "all checks pass on every instance; totals are in the text".
5. **同一案例的多张图合并 / Merge figures of the same case.**
   - 中文：同一个案例的甘特图与传播链图合成一张多面板图（paper01 `fig:case`）。说明性的示意图若与框架图重复则删（paper04 `fig:closure`）。
   - English: Combine the Gantt chart and the propagation chain for the same case into one multi-panel figure (paper01 `fig:case`). Drop illustrative schematics that duplicate the framework figure (paper04 `fig:closure`).
6. **消融/对照方法不需要算法框和示意图 / Ablations and controls don't need algorithm boxes or illustrations.**
   - 中文：负对照或次要基线的伪代码删掉，用一两句文字定义它（paper01 删掉了局部搜索算法框、收敛曲线和参数 θ 示意图）。
   - English: Drop pseudo-code for negative controls or secondary baselines and define them in one or two sentences (paper01 removed a local-search algorithm box, a convergence plot and a θ illustration).
7. **并列的长文字列表改成表格 / Turn long parallel prose into a table.**
   - 中文：五六个基线方法逐段介绍时，改成一张"名称 / 改写范围 / 作用"的小表反而更短（paper04 新增 `tab:baselines`）。这是唯一一种"新增"图表的情况。
   - English: When five or six baselines are each introduced in prose, a small table (name / rewrite scope / purpose) is shorter (paper04 added `tab:baselines`). This is the one case where compression adds a float.
8. **图注只说"是什么"，不说"说明了什么" / Captions say what is shown, not what it proves.**
   - 中文：图注保留变量、单位、条件、样本量；删掉对结论的复述和对已删除表格的引用。保留下来的图注一般缩短 30–50%。
   - English: Captions keep variables, units, conditions and sample sizes; drop restatements of the finding and references to removed tables. Retained captions typically shrink by 30–50%.

---

## 5. 理论部分 / Theory

- **陈述保留，复述删除 / Keep the statement, drop the restatement.**
  - 中文：命题后面紧跟的"Consequently, …"或"In other words, …"如果只是换说法重复命题，删掉。
  - English: A "Consequently, …" or "In other words, …" right after a proposition is deleted if it only rephrases the statement.
- **证明压成推理链 / Compress proofs into a chain.**
  - 中文：标准、直接的证明压成一行推理链（"由 (a) 和 (b)，… ⇒ …，故 …"）；非平凡的证明保留关键步骤。
  - English: Compress routine proofs into a one-line chain ("by (a) and (b), … ⇒ …, hence …"); for non-trivial proofs keep the key steps.
- **"第一、第二、第三"式 Remark 压成短句 / Condense numbered remarks.**
  - 中文：每点一句，或并入正文。
  - English: One sentence per point, or fold them into the text.
- **小定义并入大定义 / Inline small definitions.**
  - 中文：只被一个定义使用的辅助定义（如"种子集"）直接写进主定义（paper04 删除 `def:seeds`，其内容并入 `def:task_impact`）。
  - English: An auxiliary definition used by only one other definition (e.g. "seed set") is written into the main definition (paper04 removed `def:seeds` and folded it into `def:task_impact`).
- **方法和理论是压缩最少的部分 / Method and theory are cut least.**
  - 中文：paper02 的方法和理论章节几乎原样保留；压缩集中在引言、相关工作和实验叙述上。
  - English: In paper02 the method and theory sections were kept almost verbatim; the cuts were concentrated in the introduction, related work and experiment narrative.

---

## 6. 实验设置 / Experimental protocol

1. **合并零散的设置段落 / Merge scattered setup paragraphs.**
   - 中文：运行环境、代码可用性、统计方法合成一段（paper04 Protocol 从 2,367 词降到 825 词）。
   - English: Merge environment, code availability and statistical method into one paragraph (paper04 Protocol went from 2,367 to 825 words).
2. **指标定义集中一处 / Define metrics in one place.**
   - 中文：放在一个"Metrics"段里，后文直接使用，不在每个实验里重新定义。
   - English: Put them in one "Metrics" paragraph and use them afterwards without redefining them in each experiment.
3. **主要统计量保留，次要离散度删除 / Keep primary statistics, drop secondary dispersion.**
   - 中文：保留 HL 估计、95% 置信区间、Holm 校正 p 值；删除 IQR、min/max、并列（ties）处理细节，除非它们改变结论。
   - English: Keep the Hodges–Lehmann estimate, 95% CI and Holm-corrected p; drop IQRs, min/max and details of tie handling unless they change a conclusion.
4. **辩护性解释压成从句 / Shrink justifications to a clause.**
   - 中文："为什么排除某类实例""为什么两个批次分工如此""解释器版本""随机种子为何恰好相同"等长解释，压成一个从句或一句话，或干脆删除。
   - English: Long explanations such as why an instance family was excluded, why two batches divide the work this way, interpreter versions, or why seeds happen to coincide become one clause or one sentence, or are dropped.
5. **实现历史压成一个短段落 / Condense implementation history.**
   - 中文：如果某个实现缺陷的故事影响结果的可信度（如"按操作粒度重路由会导致 E2b 只通过 24 个单元"），保留结论性的 3–5 句；纯过程性的故事（paper04 `rem:e2b_history`，501 词）删掉或改为一句指引。
   - English: If the story of an implementation defect bears on the credibility of the results (e.g. "rerouting per operation made E2b pass in only 24 cells"), keep a 3–5 sentence conclusion; drop or reduce to a pointer the purely procedural narrative (paper04 `rem:e2b_history`, 501 words).
6. **稳健性检验写成一句 / State robustness checks in one sentence.**
   - 中文：例："在三种非均匀边权下结论不变，R2 分别在 x、y、z 个单元可行。"
   - English: Example: "Under three non-uniform weightings the conclusion is unchanged; R2 is feasible in x, y, z cells."

---

## 7. 结果叙述 / Results narrative

- **按结论分组，不按表格行逐条念 / Group by finding, don't read the table row by row.**
  - 中文：写成"第一类攻击……第二类……第三类……"，每组先给结论，再给支撑数字。
  - English: Write "first group of attacks… second… third…", each group giving the finding first and then the supporting numbers.
- **关于同一对象的零散段落合并到对应组里 / Merge scattered remarks about the same object.**
  - 中文：例如关于某基线（B3）的单独一段，拆进它所对应的攻击组里（paper02）。
  - English: For example, a stand-alone paragraph about one baseline (B3) is distributed into the attack groups it relates to (paper02).
- **表中已有的数字，正文只引用支撑论点的那几个 / Cite only the numbers that support the point.**
  - 中文：不要把表里的数字再完整复述一遍。
  - English: Do not re-list all the numbers that are already in the table.
- **逐步时间线改成公式加关键数字 / Turn step-by-step timelines into formulas.**
  - 中文：例："t=3 时 A 让行，t=5 时 B……"这类逐步推演，改成一条紧凑公式加关键数字，细节交给图。
  - English: Replace step-by-step walk-throughs ("at t=3 A yields, at t=5 B…") with a compact formula plus key numbers, and let the figure carry the detail.
- **探索性/补充实验降级 / Downgrade exploratory experiments.**
  - 中文：在标题标注"(exploratory)"，正文只保留结论和最关键的统计量。
  - English: Mark them "(exploratory)" in the title and keep only the finding and its key statistic in the text.

---

## 8. 摘要 / Abstract

- 中文：冗长的摘要约压缩 1/3（paper01 498→334 词，paper04 533→366 词）；已经精炼的摘要不动（paper02）。
- English: A long abstract is cut by about a third (paper01 498→334 words, paper04 533→366); an already tight abstract is left as is (paper02).
- 中文：保留**问题 → 缺口 → 方法 → 主要结果（含数字）→ 意义**五个要素。删除括号里的"即……"解释、多重"we propose / we show"框架句，以及次要的 p 值。每个结果只说一次。
- English: Keep five elements: **problem → gap → method → main results (with numbers) → significance**. Remove parenthetical "i.e." explanations, stacked "we propose / we show" frames and secondary p-values. State each result only once.

---

## 9. 句子层面 / Sentence level

1. **删除"即/换言之"复述 / Remove "i.e." restatements.**
   - 中文：如果括号或从句只是换个说法重复前文，删掉。
   - English: If a parenthesis or clause merely rephrases what was just said, delete it.
2. **减少强调格式 / Reduce emphasis formatting.**
   - 中文：`\emph` 从 81→32、111→32，`\textbf` 109→70。每段至多强调一个真正关键的词。
   - English: `\emph` went 81→32 and 111→32, `\textbf` 109→70. Emphasize at most one truly key term per paragraph.
3. **减少冗余交叉引用 / Cut redundant cross-references.**
   - 中文：paper04 的 `\ref` 从 204 降到 66。同一节在一段里只引用一次；不需要每句都指向"见第 X 节"。
   - English: paper04's `\ref` count dropped from 204 to 66. Reference a given section at most once per paragraph; not every sentence needs "see Section X".
4. **同一数字只出现在一个地方 / Each number lives in one place.**
   - 中文：正文中的字面数字减少了 25–40%，主要是删掉了重复出现的数字。
   - English: Literal numbers in the text fell by 25–40%, mostly by removing numbers that appeared more than once.
5. **对冲适度 / Moderate hedging.**
   - 中文：保留真正必要的限定（适用条件、显著性），删掉层层叠加的"to some extent / it may be argued that / in principle"。
   - English: Keep necessary qualifiers (scope conditions, significance) and drop stacked ones like "to some extent / it may be argued that / in principle".
6. **合并相邻短句 / Merge adjacent short sentences.**
   - 中文：如"X 成立。这是因为 Y。"→"X 成立，因为 Y。"；相邻两句主语相同时合并。
   - English: "X holds. This is because Y." → "X holds because Y."; merge adjacent sentences that share a subject.
7. **删除元话语 / Remove meta-discourse.**
   - 中文：如"In this section, we…""As discussed above…""It is worth noting that…"。
   - English: For example "In this section, we…", "As discussed above…", "It is worth noting that…".

---

## 10. 操作流程与自检 / Procedure and self-check

**中文**：

1. **先量化**：统计各节词数、图表数、`\cite`/`\ref`/`\emph` 数量，找出最长、最重复的章节，优先处理。
2. **建"信息归属表"**：列出每条关键结论/数字目前出现在哪些位置，为每条选定唯一归属（通常是：数字归结果正文或表格，结论归摘要和贡献列表各一次）。
3. **自顶向下**：先做结构合并（章节、图表），再做段落压缩，最后做句子打磨。
4. **压缩后自检**：
   - 去重引文集合与压缩前完全一致；
   - 所有定理/命题/定义标签仍在，且陈述未改；
   - 每个保留的 `\ref` 都能解析（合并章节时 `\label` 已叠放）；
   - 主要结果数字（宏）都还在，被删的只能是次要统计；
   - 负面结果、局限仍然存在；
   - 能编译，无未定义引用警告。

**English**:

1. **Measure first**: count words per section, floats, and `\cite`/`\ref`/`\emph` occurrences; start with the longest and most repetitive sections.
2. **Build a fact-ownership table**: list where each key claim or number currently appears and choose one home for each (typically numbers live in the results text or a table; claims appear once in the abstract and once in the contribution list).
3. **Top-down**: do structural merges (sections, floats) first, then paragraph compression, and finally sentence polishing.
4. **Post-compression checks**:
   - the unique citation set is identical to the original;
   - every theorem/proposition/definition label still exists with an unchanged statement;
   - every remaining `\ref` resolves (labels stacked on merged headings);
   - all primary result numbers (macros) are still present, and only secondary statistics were removed;
   - negative results and limitations are still present;
   - the document compiles with no undefined-reference warnings.

---

## 11. 给 AI 的提示词模板 / Prompt template for an AI

```text
请压缩这篇论文（目标约 X%），遵循 Paper-HowToCompress.md：
1. 压缩冗余而非信息：每条信息只保留一个最佳位置；
2. 引文集合、定理/命题/定义陈述、主要结果数字、负面结果与局限一律保留；
3. 按优先级删除：重复的呈现形式 > 重复陈述 > 过程/历史材料 > 次要证据 > 句子冗长；
4. 合并章节时叠放原 \label，保证 \ref 可解析；
5. 方法与理论部分尽量少动，重点压缩引言、相关工作、实验设置与结果叙述；
6. 完成后输出：各节压缩前后词数、删除/合并的图表清单、引文集合是否一致。

Compress this paper (target about X%) following Paper-HowToCompress.md:
1. Compress redundancy, not information: give each fact one best home;
2. Keep all citations, formal statements, primary result numbers, negative results and limitations;
3. Cut in priority order: duplicate presentations > repeated statements > process/history material > secondary evidence > sentence verbosity;
4. When merging sections, stack the original \label commands so every \ref resolves;
5. Touch method and theory as little as possible; focus on the introduction, related work, protocol and results narrative;
6. Report afterwards: per-section word counts before/after, the list of removed or merged floats, and whether the citation set is unchanged.
```
