# ToDoList（clbs_new 节点排他模型改造）

最后更新：2026-11-08 12:30

## 论文中的新名称（代码、CSV、日志保留旧名）

- 方法：B0→OL，B0宽松→OL-RD，B0+→TS，BL→AE，B1→CLBS-R，B2→CLBS
- 布局：funnel→S11，high→S21，mid→S22，low→GC，scatter→GD
- 车臂比/车机比 → AGV 配比（$N_A/N_M$）
- 对照写在 `tools/baseline_ladder.py`、`algorithm/generator.py`、`paper01_SCI/CAIE/tab/gen_tables_ladder.py`、`fig/_style.py` 的注释里

## 待补跑实验（作者决定后统一跑；顺序执行，不要并行）

> 2026-11-08 15:00:第 1、2 条已跑完并写入论文 5.3 节(表 `tab:sens`,`tools/sens_summary.py --tex` 生成 `tab/tab_sens.tex` 与 `tab/sens_macros.tex`;数据 `output/sens_*.csv`)。第 3 条(同代数,`samegen_full*.csv`)与第 4 条(`prune_ablation.csv`,旧结果备份为 `prune_ablation_v1.csv`)运行中。

1. **[已完成] 机器节点容量 c 敏感性**（论文 5.3 节已留 `\TBD` 占位；§2.4 与参数表也声称"另行度量"）
   - 算例：S11（funnel）、S21（high），c ∈ {1, 2, ∞}（c=2 可复用主批次）
   - 方法：OL、TS、AE、CLBS（敏感性只比本文与对比方法，不跑 CLBS-R）
   - 10 种子、90 s；估计 2 算例 × 2 个新 c × 4 方法 × 10 种子，约 4–5 h
   - 需新写或扩展工具：`baseline_ladder` 增加 `--capacity` 参数，或新建 `tools/capacity_sens.py`
2. **[已完成] 异构度 H 在节点模型下重跑**（论文 5.3 节"异构度"段仍是旧模型 matrix 批次，带 `%% !!` 注释）
   - 在 S11 上取 H ∈ {0, 0.15, 0.3, 0.5}，比较 OL、TS、AE、CLBS，10 种子、90 s
3. **[已完成,同代数口径] 闭环内派遣的证据**（CLBS-R vs CLBS）：全部 10 组 × 10 种子各 30 代,CLBS −15.57%,97 胜 3 负,p<1e-4;逐组校正前 10/10 显著,Holm 后最小 p=0.058。汇总 `tools/samegen_summary.py --tex` → `tab/samegen_macros.tex`;论文 5.4、5.5、结论 (3)、局限 (2)、贡献与摘要已改写;旧图 `fig:protocols` 已删
   - **[已完成 2026-11-08]** 加速后的解码器在 90 s 同挂钟下重跑 CLBS-R/CLBS(3 进程并行,`output/ladder_b12_g*.csv`),经 `tools/merge_b12.py` 并入 `baseline_ladder.csv`(原文件备份为 `baseline_ladder_v1.csv`)。结果:CLBS-R→CLBS −2.69%(64/34,p=0.0015,HL −3.30% [−5.50,−0.90]),由加速前的 +2.07%(不显著)翻为显著;OL→CLBS −22.21%、TS→CLBS −15.01%、AE→CLBS −29.14%。表、宏、`fig_prediction3` 已重生成,正文派遣叙事已按"开环与闭环内均显著、闭环内净收益受开销所限"改写
   - 原三选一
   - 同代数批次正式化（`tools/samegen_check.py` 扩到 10 算例 × 10 种子）
   - 或用加速后的解码器在 90 s 下重跑 CLBS-R/CLBS
   - 或 180 s 预算重跑 CLBS-R/CLBS
4. **[已完成] 降本对照重跑**(−6.48%,44/0;加速 2.30×;已回填 `tab_prune` 与宏。开销诊断 `ladder_diag` 已用新解码器重跑:`\CostMultAfter` 4.54、`\CostMultBefore` 10.4,`\MsOpen/\MsLoopRule/\MsLoopProbe` 手工更新为 0.74/18.5/83.9 ms;收敛图、开销图、案例图已重画;案例算例两档 C_max 不变(91.0/54.5)。旧结果备份为 `*_v1`)（解码器已改为按下界升序试探，`tab_prune`、`\RouteCallCut*`、§4.4.4 的扫描顺序描述需更新）
5. **其余旧模型批次**：附加代价扫描（θ，节点模型下暂不支持定价）、同代数口径图 `fig_protocols`、动机算例图 `fig_motivating`；重跑或从论文中删去
   - 公开基准无需重跑：删去争用约束后与模型改造无关

## 当前进度（执行到哪里了）

- [x] 代码改造完成（`clbs` 原样保留，所有改动都在 `clbs_new`）
  - 毛坯库 `v0` 与成品库 `w0` 分开，成品库在路网对端，两库不排他
  - 机器节点容量 c（默认 2，`None` 表示 ∞），含交接车；交接时间 0；节点间隔 h = 0.5
  - 空车停在机器待命位并计入 c；机器满时把最早停放的空车驱离到最近库区（每个任务最多 2 次）
  - 路口容量 1，路由改为安全区间搜索（SIPP）
  - 网格类布局：机器挂在短支线上
  - 校验器新增节点容量、首末库区检查；测试新增 T16
- [x] 自测：16/16 测试通过；`node_smoke` 全部 PASS（各布局 × c∈{1,2,3,∞} × rule/exact）
- [x] 论文 A–D 已改完（`paper01_SCI/CAIE/paper01_CN_v2.tex`），可正常编译（32 页，无错误）
- [x] 新增 Lyu 式对照档 BL（AGV 编入染色体，`dispatch="gene"`），已接入 `tools/baseline_ladder.py`；测试 17/17 通过（新增 T17）
- [x] 论文改为以 C_max 为唯一判定指标（摘要、引言、贡献、相关工作小结与对照表、实验问题与方案表、对比方法、结果、结论）；BL 的数字用占位宏 `\GainLyu` 等，显示为"[待重跑]"
- [x] 单种子 90 s 试跑（A high，seed 42）：B0 82.5 / B0+ 71.5 / B1 49.0 / B2 57.5 / BL 80.0，日志在 `output/_probe90_high.log`
- [x] 用户已确认重跑（2026-11-07 23:10）
- [x] 三项重跑完成（2026-11-08，并行，各单线程）：主批次 8.7 h、降本对照 3.3 h、诊断 0.5 h；全部运行过校验器
  - 主批次 → `output/baseline_ladder.csv`（日志 `run_main.log`）
  - 降本对照 → `output/prune_ablation.csv`（日志 `run_prune.log`）
  - 诊断 → `output/ladder_cost.csv`、`ladder_convergence.csv`、`case_study/`（日志 `run_diag.log`）
- [x] 表格与宏生成脚本已重建：`paper01_SCI/CAIE/tab/gen_tables_ladder.py`（读 `clbs_new/output`，含 BL 列，`--apply` 写回导言区宏；输出日志 `output/gen_tables.log`）
- [x] 已回填：`tab_main`、`tab_bytag`、`tab_prune`、`tab_instances`、71 个宏；重画 `fig_prediction3`、`fig_protocol`、`fig_convergence_closedloop`、`fig_case_gantt`、`fig_case_chain`（`fig/_style.py` 的 OUTPUT 已指向 `clbs_new/output`）；正文按实测改写；编译通过
- [ ] **← 当前：等作者决定 B1/B2 的定位**（见下方提醒第一条）

### 主批次结果（节点模型，10 算例 × 10 种子，90 s）

- B2 对 B0 −16.79%（93/6）、对 B0+ −9.12%（79/21）、对 BL −24.22%（98/2），均 p<1e-4
- 闭环 B0→B1 −18.12%，10/10 组显著；但不再随争用上升（布局族各组 −19%～−22%）
- 派遣：开环 B0→B0+ −8.04%（显著）；闭环内 B1→B2 **+2.07%，p=0.19，不显著**；全体均值 B1 69.79 < B2 70.67
- 降本：开启剪枝+复用使 B2 再降 4.74%（38/0）；B2 单次评价仍约为 B1 的 8 倍（旧模型约 5 倍）

## 自查命令（约 1–2 分钟）

```powershell
cd c:\Users\analy\Desktop\AI_Folder\clbs_new
$env:PYTHONIOENCODING="utf-8"
py -3 -m tests.test_all
py -3 -m tools.node_smoke
```

- `tests.test_all`：运行 16 项测试，应全部通过
- `tools.node_smoke`：各布局 × c∈{1,2,3,∞} × 两种派车方式解码并校验，应输出 `ALL PASS`

## 已完成的重跑（2026-11-08，记录命令以备复现）

1. 主批次（已含 BL 档）：`py -3 -u -m tools.baseline_ladder --budget 90 --seeds 42,7,2024,13,1,8,99,123,777,31415`（与旧批次 `clbs/output/baseline_ladder.csv` 同一组种子）（每个算例每个种子约 5 分钟，10 算例 × 10 种子约 8–9 小时）
2. 降本对照：`py -3 -u -m tools.prune_ablation`
3. 诊断：`py -3 -u -m tools.ladder_diag`

## 提醒

- **解释器**：用 `py -3`（`python` 不在 PATH 上）；运行前先设 `$env:PYTHONIOENCODING="utf-8"`。
- **解码变慢约 5 倍**（如 rule 派车 6.7 ms → 41 ms），90 s 预算不变时 GA 代数减少；makespan 也变长（`high` exact 155 → 179）。
- **定价（θ>0）在节点模型下不支持**，会报 `ValueError`；论文局限（4）已注明。论文中的定价结果、局部搜索消融仍是旧模型结果。
- **论文中所有数值需在重跑后重新生成**：算例表 `tab_instances`、主结果表、`\LegDumbbell`、`\Contention*`、`\LBGap*`、案例分析。
- **动机算例图 `fig_motivating`** 仍按旧模型计算（文中已注明两库重合），必要时重画。
- **相关工作表 `tab:related`** 中 sun2023、kim2026、li2026 的"节点排他"列标了 `ref_check`，需对照原文核实。
- 旧模型结果保留在 `clbs/output`，不要覆盖。
- **闭环内派遣不显著（已证实）**：正文已改为"派遣只在开环下显著、闭环内被开销抵消"，并在 5.4 节留了 `%% !!` 注释。待作者决定：B2 是否仍作"本文方法"，还是改以 B1 为主方法、或缩短派遣开销后重跑；贡献 (2) 与第 4 章对派遣的定位相应调整。
- **独立算例批次（matrix，16 组）、附加代价扫描、同代数口径（fig_protocols）、公开基准**仍是旧模型结果，正文已注明或未改动，必要时在节点模型下重跑。
- **c 敏感性实验**：已列入"待补跑实验"第 1 条。
- **第 5 章结构（2026-11-08）**：5.1 实验设置与对比方法（含公开基准）→ 5.2 与对比方法的比较 → 5.3 敏感性分析（CLBS 对 OL/TS/AE 逐组）→ 5.4 消融（含各组成部分在不同场景下的作用）→ 5.5 案例分析。`tab_bytag` 现为 CLBS 对三种对比方法的逐组表，逐组消融效应见 `fig_prediction3`。
