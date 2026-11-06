# STRC — Spatiotemporal Reservation Closure

无冲突柔性作业车间上的**时空预约影响闭包**：先沿「谁挡了谁」测量损坏范围，再在闭包上做最小扰动恢复。

On a conflict-free flexible job shop, the **spatiotemporal reservation closure (STRC)** first measures the damaged extent along 「谁挡了谁」 ("who blocks whom", the blocking relation), then restores the schedule on the closure with minimum disturbance.

本仓库与 `clbs/`（静态闭环双层调度）并列。**下层**（路网、预约表、时间窗路由、校验器、算例格式）复用 `clbs`；**上层**替换为扰动注入 → 闭包 → 升级阶梯修复，不做种群搜索。

This repository sits alongside `clbs/` (static closed-loop bilevel scheduling). The **lower layer** (road network, reservation table, time-window routing, validator, instance format) reuses `clbs`; the **upper layer** is replaced by disturbance injection → closure → escalation-ladder repair, with no population search.

## 一、快速开始 / 1. Quick start

```powershell
cd STRC
py -m tests.test_smoke          # 桥接 clbs + 空闭包自检 / bridge clbs + empty-closure smoke test
py main.py --help               # 一键入口(占位,待 E1 实现后填满) / one-shot entry (placeholder, to be filled after E1)
py -m tools.e1_miss --help      # 门禁实验 E1:任务图漏报 vs 预约闭包 / gate E1: task-graph missed detection vs reservation closure
py -m tools.e3_boundary --help  # 门禁实验 E3:R1(任务图) vs R2(闭包) / gate E3: R1 (task graph) vs R2 (closure)
```

依赖与 `clbs` 相同：纯标准库，Python ≥ 3.8。运行时通过 `algorithm/clbs_bridge.py` 把仓库根下的 `clbs/` 加入 `sys.path`，**不复制**路由代码。

Dependencies match `clbs`: the standard library only, Python ≥ 3.8. At runtime `algorithm/clbs_bridge.py` puts `clbs/` under the repository root on `sys.path`, and does **not copy** the routing code.

## 二、文件夹层级 / 2. Directory layout

```text
STRC/
  README.md
  requirements.txt
  main.py                 # 一键入口:载入排程 → 注入扰动 → STRC 修复 → 校验 / one-shot entry: load schedule → inject disturbance → STRC repair → validate
  algorithm/
    clbs_bridge.py        #   把 ../clbs 挂进 path,统一转导出下层符号 / mount ../clbs on path and re-export lower-layer symbols
    disturbance.py        #   扰动模型:走廊阻断 / RA 故障 / AGV 抛锚 / 插单 / disturbance model: corridor blockage / RA failure / AGV breakdown / insertion
    closure.py            #   STRC 核心:阻塞关系传递闭包 + 包含性检查钩子 / STRC core: transitive closure of the blocking relation + containment hook
    escalate.py           #   升级阶梯:改路 → 换车 → 改派 → 改序 / escalation ladder: reroute → switch vehicle → reassign → resequence
    repair.py             #   有界修复编排(在闭包上调用阶梯) / bounded-repair orchestration (call the ladder on the closure)
    metrics.py            #   Cmax 偏差 + 预约扰动量 / Cmax deviation + reservation disturbance
    ladder.py             #   实验档 R0 / R0+ / R1 / R2(对照用) / experiment arms R0 / R0+ / R1 / R2 (for comparison)
    report.py             #   摘要与闭包规模画像 / summary and closure-size profile
    __init__.py
  tools/
    e1_miss.py            #   E1 漏报实验(走廊阻断 → 任务图空、闭包非空) / E1 missed-detection experiment (corridor blockage → empty task graph, nonempty closure)
    e3_boundary.py        #   E3 边界对照(同修复引擎,只换影响域定义) / E3 boundary comparison (same repair engine, only the impact-set definition changes)
    run_ladder.py         #   四级阶梯批跑(同挂钟协议,对齐 clbs/tools/baseline_ladder) / four-level ladder batch (same wall-clock protocol, aligned with clbs/tools/baseline_ladder)
    pub_batch.py          #   外部布局批次:E1-E5 + 同参数自建对照 / external-layout batch: E1-E5 + same-parameter self-built controls
    cheap_baselines.py    #   E7 便宜对照臂:右移 RS / 重解码 RD / 不划边界 RA / R2 / E7 cheap arms: right-shift RS / re-decode RD / no boundary RA / R2
    scale_curve.py        #   E8 算例规模梯子:8x4x4 → 20x10x10,三臂同跑 / E8 instance-scale ladder: 8x4x4 → 20x10x10, three arms together
    sync_database.py      #   从 clbs 同步公开数据副本到 database/,记 SHA256 / sync the public-data copy from clbs into database/, record SHA256
    paper_numbers.py      #   论文宏取数(四批账本一并打印) / pull numbers for paper macros (print all four ledgers)
  database/               # 公开数据与算例的**本地镜像**(见 database/README.md) / **local mirror** of public data and instances (see database/README.md)
    MANIFEST.csv          #   逐文件 clbs 源路径 + SHA256 / per-file clbs source path + SHA256
    raw/                  #   Lyu/Liu 布局发布件 + 决定其语义的解析源码 / Lyu/Liu layout releases + the parser source that fixes their meaning
    instances/            #   外部布局批次的 8 个输入算例(5 外部 + 3 自建对照) / 8 input instances of the external-layout batch (5 external + 3 self-built controls)
  input/
    schedules/            #   初始可行排程(可由 clbs 闭环解导出的 JSON) / initial feasible schedules (JSON exported from a clbs closed-loop solution)
    disturbances/         #   扰动描述 JSON(类型、时刻、作用对象) / disturbance JSON (type, time, target)
  output/                 #   单次运行结果 / result of one run
  experiments/            #   批跑账本与汇总表 / batch ledgers and summary tables
    pub_layouts/          #   外部布局批次(独立账本,不并入 expanded/) / external-layout batch (separate ledger, not folded into expanded/)
  tests/
    test_smoke.py         #   桥接与模块可导入自检 / smoke test that the bridge and modules import
```

## 三、与 clbs 的边界 / 3. Boundary with clbs

| 模块 / module | STRC 怎么处理 / how STRC treats it |
| --- | --- |
| `ReservationTable` / `Network.route` | 经 `clbs_bridge` **原样复用** / **reused as is** via `clbs_bridge` |
| `validator` / 算例 JSON / `generator` | **原样复用** / **reused as is** |
| `blocking_opponents` | **沿用机制,换用途**(搜邻域 → 建闭包) / **same mechanism, different use** (search a neighborhood → build the closure) |
| `ga.py` 种群搜索 / population search | **不使用** / **not used** |
| 目标 / objective | \(\min C_{\max}\) → 恢复可行 + 少动已承诺时窗 / recover feasibility + move committed time windows as little as possible |

共享下层是受控对比的前提：R0（clbs 热启动重解）与 R2（STRC）若换路由器，预算–质量曲线将无法归因。

A shared lower layer is the premise of a controlled comparison: if R0 (clbs warm-start re-solve) and R2 (STRC) swapped routers, the budget–quality curve could not be attributed.

## 四、门禁实验(优先顺序) / 4. Gate experiments (priority order)

详见 [EXPERIMENTS.md](EXPERIMENTS.md)（创新结论 C1–C6 ↔ E1–E5 覆盖矩阵）。

See [EXPERIMENTS.md](EXPERIMENTS.md) (coverage matrix of claims C1–C6 ↔ E1–E5).

```powershell
py -m tests.test_smoke
py -m tools.e1_miss --auto-corridor          # C1 漏报 / C1 missed detection
py -m tools.e2_containment                   # C2a/C2b 包含性 / C2a/C2b containment
py -m tools.e3_boundary                      # C3 边界消融(规模+质量) / C3 boundary ablation (size + quality)
py -m tools.e4_structure                     # C4 结构预测(探索) / C4 structure prediction (exploratory)
py -m tools.e5_cross_curve                   # C5 Cmax/稳定性权衡(默认可 congested) / C5 Cmax/stability tradeoff (congested allowed by default)
py -m tools.run_ladder --budget-sec 1        # R0+/R1/R2 同预算对照 / R0+/R1/R2 compared at the same budget
py -m tools.pub_batch                        # 外部布局批次(独立账本) / external-layout batch (separate ledger)
py -m tools.cheap_baselines                  # E7 便宜对照臂(独立账本) / E7 cheap comparison arms (separate ledger)
py -m tools.scale_curve                      # E8 算例规模梯子(独立账本) / E8 instance-scale ladder (separate ledger)
py -m tools.expand_batch --only-e5 --out-dir experiments/_t   # A2 越界列(见下) / A2 out-of-bound columns (see below)
py -m tools.decode_cost                      # 单次解码 vs 一次有界修复的耗时 / one decode vs the time of one bounded repair
```

末两条是对照臂的**效度检查**，不产生论文主读数。

The last two are **validity checks** of the comparison arms; they do not produce the paper's main readings.

`cheap_baselines` 与 `scale_curve` 补的是对照阶梯中间那一档。此前阶梯是
R1（释放集为空＝不动）→ R2 → R0+（$0.2$–$2$ s 种群搜索），从「什么都不做」直接跳到
「跑两秒搜索」，于是「低两至三个数量级」这个读数里分不清有多少只是因为对照选贵了。
三条新臂：**RS** 全局右移（不改路径/指派/序，未完成的一切统一后推到阻断窗之后；冻结判据
与 R2 相同，故按 A2 可采纳），**RD** 原染色体重解码（保持机器指派与扫描序，在装了阻断的
路由层上从头解一遍；**不受 A2 约束**，故 CSV 里 `past_changed>0` 的格数必须与它的
`makespan` 一起读），**RA** 不划边界（释放 $t_{now}$ 之后的全部预约，其余**逐项**与 R2
相同）。结论：RS 更快（$1.75$ vs $3.16$ ms）但质量与稳定性都输；
RD 反而比一次有界修复贵 $2.3$ 倍，且 $31/50$ 格改写历史。

`cheap_baselines` and `scale_curve` fill the middle rung of the comparison ladder. The ladder used to be
R1 (empty release set = do nothing) → R2 → R0+ ($0.2$–$2$ s population search), jumping from "do nothing" straight to
"search for two seconds", so the reading "two to three orders of magnitude lower" could not say how much was only because the comparison was expensive.
Three new arms: **RS** global right-shift (do not change paths/assignments/sequence; push everything unfinished back past the blockage window as one delay; the freeze test
matches R2, so it is admissible under A2), **RD** re-decode the original chromosome (keep machine assignment and scan order, and solve once from scratch on the routing layer with the blockage installed; **not bound by A2**, so the number of cells with `past_changed>0` in the CSV must be read together with its
`makespan`), **RA** draw no boundary (release every reservation after $t_{now}$; everything else matches R2 **item by item**).
Conclusion: RS is faster ($1.75$ vs $3.16$ ms) but loses on both quality and stability;
RD is instead $2.3$ times more expensive than one bounded repair, and $31/50$ cells rewrite history.

**RA 是这三条里最要紧的一条**，因为它是唯一能把闭包这个对象单独隔离出来的对照：与 R2
共用引擎、冻结判据、阻断安装与协议，只差释放集取闭包还是取平凡上界，故两臂之差可整份
归给闭包。读数是耗时与 $C_{\max}$ 几乎相同（$3.16$ vs $3.30$ ms；逐格 $0/46/4$），
改动比例 $0.535$ vs $0.604$（逐格 $32/17/1$，Wilcoxon $p=5.9\times10^{-7}$）。
即：**毫秒级响应来自单遍改路而非闭包，闭包兑现的是稳定性**，且降幅与闭包排除掉多少
成正比（释放占比 $0.94$ 的算例只降 $0.010$，$0.88$ 的降 $0.128$）。

**RA is the one that matters most among the three**, because it is the only comparison that isolates the closure as an object: it shares the engine, the freeze test, the blockage installation, and the protocol with R2, and differs only in whether the release set is the closure or the trivial upper bound, so the whole gap between the arms can be attributed to the closure. The readings of time and $C_{\max}$ are almost the same ($3.16$ vs $3.30$ ms; per cell $0/46/4$), and the change ratios are $0.535$ vs $0.604$ (per cell $32/17/1$, Wilcoxon $p=5.9\times10^{-7}$). That is: **millisecond response comes from one reroute pass, not from the closure; what the closure delivers is stability**, and the reduction is proportional to how much the closure excludes (an instance with release share $0.94$ drops only $0.010$, and one with $0.88$ drops $0.128$).

`scale_curve` 的梯子是工件 $2k$、机器 $k$、车 $k$，$k=4..10$，拥堵档与 $H$/$F$/Tt-Tp
及两处割集同口径标定，**只有规模变**（算例由 `clbs/tools/gen_instances.py` 生成）。
要紧的一条是闭包占比不随规模上涨（$0.544 \to 0.426$），否则「有界」就名存实亡。

The `scale_curve` ladder is jobs $2k$, machines $k$, vehicles $k$, $k=4..10$, with congestion level, $H$/$F$/Tt-Tp, and the two cuts calibrated on the same protocol, so **only the scale changes** (instances are generated by `clbs/tools/gen_instances.py`). The point that matters is that the closure ratio does not rise with scale ($0.544 \to 0.426$); otherwise "bounded" would be a name without the property.

`--only-e5` 跑出的 CSV 多四列 `R0/R2_past_changed|total`：按假设 A2，
`t_end <= t_now` 的预约不得被改写，有界修复应恒为 $0$，而全局重解臂从 $t=0$
重新解码、不受该约束——这四列把它越界的程度量出来。存档在
`experiments/e5_a2_audit.csv`（与 `expanded/e5_cross_curve.csv` 同协议同代码路径；
官方文件未覆盖是因为 R0+ 受挂钟预算约束、完成代数随机，重跑会改动论文表格读数）。

The CSV from `--only-e5` adds four columns `R0/R2_past_changed|total`: under assumption A2, reservations with `t_end <= t_now` must not be rewritten, so bounded repair should stay at $0$, while the global re-solve arm decodes again from $t=0$ and is not bound by that constraint — these four columns measure how far it steps outside. Archived at `experiments/e5_a2_audit.csv` (same protocol and code path as `expanded/e5_cross_curve.csv`; the official file was not overwritten because R0+ is bound by a wall-clock budget and the generation at which it finishes is random, so a rerun would change the readings in the paper tables).

`decode_cost` 回答的是「把种群调小，全局重解能不能进毫秒档」。答案是能：
单次解码 $0.6$–$6.1$ ms，只有一次有界修复的 $0.95$–$2.18$ 倍。所以
**不要**把 R0+ 守不住小预算写成结构性下限——那是 $40$ 个体这一配置的属性。

`decode_cost` answers "if the population is shrunk, can a global re-solve reach the millisecond range". The answer is yes: one decode is $0.6$–$6.1$ ms, only $0.95$–$2.18$ times one bounded repair. So do **not** write R0+'s failure to hold a small budget as a structural floor — that is a property of the configuration with $40$ individuals.

## 五、算例从哪来 / 5. Where the instances come from

分三种来源，**账本分开、不混报**：

Three sources, with **ledgers kept separate and not mixed in reporting**:

| 来源 / source | 位置 / location | 说明 / note |
| --- | --- | --- |
| 自建受控算例（主批次） / self-built controlled instances (main batch) | `../clbs/input/...` | 直接指向，不复制；正文所有 `/50` 读数出自此 / pointed at directly, not copied; every `/50` reading in the text comes from here |
| 外部布局算例 + 同参数对照 / external-layout instances + same-parameter controls | `database/instances/` | **本地镜像**，见下 / **local mirror**, see below |
| 初始排程 / 扰动 / initial schedule / disturbance | `input/schedules/`、`input/disturbances/` | 排程由 clbs 闭环解导出（脚本待补）；扰动 schema 见 `algorithm/disturbance.py` / schedules are exported from a clbs closed-loop solution (script still to be added); disturbance schema is in `algorithm/disturbance.py` |

### 本地公开数据镜像 `database/` / Local mirror of public data `database/`

paper04 用到的公开数据（Lyu 等 2019 的布局拓扑）**在本仓库存一份镜像**，使数据与用它的
代码同处一地——归档与投稿附件不必跨到 `clbs/` 去捞。`tools/pub_batch.py` 读的就是这份
副本，不是摆设。

The public data used by paper04 (the layout topology of Lyu et al. 2019) **is mirrored in this repository**, so the data sits next to the code that uses it — archiving and submission attachments do not have to reach into `clbs/`. `tools/pub_batch.py` reads this copy; it is not decoration.

```powershell
py -m tools.sync_database            # 从 clbs 重新同步 / re-sync from clbs
py -m tools.sync_database --check    # 校验未漂移(逐字节 + SHA256) / check that it has not drifted (byte for byte + SHA256)
```

**真值仍在 `clbs/database/`**（那里记原始下载 URL、许可、各族可用性判定）；本地这份只回答
"paper04 到底吃了哪些字节"。副本最容易烂在两处静默不一致上，故一律由脚本生成、
`MANIFEST.csv` 记 SHA256、`--check` 可查漂移。

**The source of truth remains `clbs/database/`** (that is where the original download URL, the license, and the usability judgment of each family are recorded); the local copy only answers "which bytes paper04 actually consumed". A copy most easily goes bad as two places that disagree in silence, so it is always generated by the script, `MANIFEST.csv` records SHA256, and `--check` can look for drift.

引用这批数字前必须知道三处口径：**逐段行驶时间是补的**（Lyu 未发表附录布局的边权，本批取
等权）、**装卸点做了合并**、**工件与工时未借用**（公开族运输占比过低，搬入会让争用现象消
失）。即被外部化的只有**布局出处**。详见 `database/README.md` 与
`experiments/pub_layouts/README.md`。

Before citing these numbers, three conventions must be known: **per-segment travel times were filled in** (Lyu never published edge weights for the appendix layouts; this batch uses equal weights), **load and unload points were merged**, and **jobs and processing times were not borrowed** (on the public family, transport is too small a share of processing, and bringing it in would make contention disappear). What was externalized is only the **source of the layout**. See `database/README.md` and `experiments/pub_layouts/README.md`.
