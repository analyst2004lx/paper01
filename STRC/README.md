# STRC — Spatiotemporal Reservation Closure

无冲突柔性作业车间上的**时空预约影响闭包**：先沿「谁挡了谁」测量损坏范围，再在闭包上做最小扰动恢复。

本仓库与 `clbs/`（静态闭环双层调度）并列。**下层**（路网、预约表、时间窗路由、校验器、算例格式）复用 `clbs`；**上层**替换为扰动注入 → 闭包 → 升级阶梯修复，不做种群搜索。

## 一、快速开始

```powershell
cd STRC
py -m tests.test_smoke          # 桥接 clbs + 空闭包自检
py main.py --help               # 一键入口(占位,待 E1 实现后填满)
py -m tools.e1_miss --help      # 门禁实验 E1:任务图漏报 vs 预约闭包
py -m tools.e3_boundary --help  # 门禁实验 E3:R1(任务图) vs R2(闭包)
```

依赖与 `clbs` 相同：纯标准库，Python ≥ 3.8。运行时通过 `algorithm/clbs_bridge.py` 把仓库根下的 `clbs/` 加入 `sys.path`，**不复制**路由代码。

## 二、文件夹层级

```text
STRC/
  README.md
  requirements.txt
  main.py                 # 一键入口:载入排程 → 注入扰动 → STRC 修复 → 校验
  algorithm/
    clbs_bridge.py        #   把 ../clbs 挂进 path,统一转导出下层符号
    disturbance.py        #   扰动模型:走廊阻断 / RA 故障 / AGV 抛锚 / 插单
    closure.py            #   STRC 核心:阻塞关系传递闭包 + 包含性检查钩子
    escalate.py           #   升级阶梯:改路 → 换车 → 改派 → 改序
    repair.py             #   有界修复编排(在闭包上调用阶梯)
    metrics.py            #   Cmax 偏差 + 预约扰动量
    ladder.py             #   实验档 R0 / R0+ / R1 / R2(对照用)
    report.py             #   摘要与闭包规模画像
    __init__.py
  tools/
    e1_miss.py            #   E1 漏报实验(走廊阻断 → 任务图空、闭包非空)
    e3_boundary.py        #   E3 边界对照(同修复引擎,只换影响域定义)
    run_ladder.py         #   四级阶梯批跑(同挂钟协议,对齐 clbs/tools/baseline_ladder)
    pub_batch.py          #   外部布局批次:E1-E5 + 同参数自建对照
    cheap_baselines.py    #   E7 便宜对照臂:右移 RS / 重解码 RD / 不划边界 RA / R2
    scale_curve.py        #   E8 算例规模梯子:8x4x4 → 20x10x10,三臂同跑
    sync_database.py      #   从 clbs 同步公开数据副本到 database/,记 SHA256
    paper_numbers.py      #   论文宏取数(四批账本一并打印)
  database/               # 公开数据与算例的**本地镜像**(见 database/README.md)
    MANIFEST.csv          #   逐文件 clbs 源路径 + SHA256
    raw/                  #   Lyu/Liu 布局发布件 + 决定其语义的解析源码
    instances/            #   外部布局批次的 8 个输入算例(5 外部 + 3 自建对照)
  input/
    schedules/            #   初始可行排程(可由 clbs 闭环解导出的 JSON)
    disturbances/         #   扰动描述 JSON(类型、时刻、作用对象)
  output/                 #   单次运行结果
  experiments/            #   批跑账本与汇总表
    pub_layouts/          #   外部布局批次(独立账本,不并入 expanded/)
  tests/
    test_smoke.py         #   桥接与模块可导入自检
```

## 三、与 clbs 的边界

| 模块 | STRC 怎么处理 |
| --- | --- |
| `ReservationTable` / `Network.route` | 经 `clbs_bridge` **原样复用** |
| `validator` / 算例 JSON / `generator` | **原样复用** |
| `blocking_opponents` | **沿用机制,换用途**(搜邻域 → 建闭包) |
| `ga.py` 种群搜索 | **不使用** |
| 目标 | \(\min C_{\max}\) → 恢复可行 + 少动已承诺时窗 |

共享下层是受控对比的前提：R0（clbs 热启动重解）与 R2（STRC）若换路由器，预算–质量曲线将无法归因。

## 四、门禁实验(优先顺序)

详见 [EXPERIMENTS.md](EXPERIMENTS.md)（创新结论 C1–C6 ↔ E1–E5 覆盖矩阵）。

```powershell
py -m tests.test_smoke
py -m tools.e1_miss --auto-corridor          # C1 漏报
py -m tools.e2_containment                   # C2a/C2b 包含性
py -m tools.e3_boundary                      # C3 边界消融(规模+质量)
py -m tools.e4_structure                     # C4 结构预测(探索)
py -m tools.e5_cross_curve                   # C5 Cmax/稳定性权衡(默认可 congested)
py -m tools.run_ladder --budget-sec 1        # R0+/R1/R2 同预算对照
py -m tools.pub_batch                        # 外部布局批次(独立账本)
py -m tools.cheap_baselines                  # E7 便宜对照臂(独立账本)
py -m tools.scale_curve                      # E8 算例规模梯子(独立账本)
py -m tools.expand_batch --only-e5 --out-dir experiments/_t   # A2 越界列(见下)
py -m tools.decode_cost                      # 单次解码 vs 一次有界修复的耗时
```

末两条是对照臂的**效度检查**，不产生论文主读数。

`cheap_baselines` 与 `scale_curve` 补的是对照阶梯中间那一档。此前阶梯是
R1（释放集为空＝不动）→ R2 → R0+（$0.2$–$2$ s 种群搜索），从「什么都不做」直接跳到
「跑两秒搜索」，于是「低两至三个数量级」这个读数里分不清有多少只是因为对照选贵了。
三条新臂：**RS** 全局右移（不改路径/指派/序，未完成的一切统一后推到阻断窗之后；冻结判据
与 R2 相同，故按 A2 可采纳），**RD** 原染色体重解码（保持机器指派与扫描序，在装了阻断的
路由层上从头解一遍；**不受 A2 约束**，故 CSV 里 `past_changed>0` 的格数必须与它的
`makespan` 一起读），**RA** 不划边界（释放 $t_{now}$ 之后的全部预约，其余**逐项**与 R2
相同）。结论：RS 更快（$1.75$ vs $3.16$ ms）但质量与稳定性都输；
RD 反而比一次有界修复贵 $2.3$ 倍，且 $31/50$ 格改写历史。

**RA 是这三条里最要紧的一条**，因为它是唯一能把闭包这个对象单独隔离出来的对照：与 R2
共用引擎、冻结判据、阻断安装与协议，只差释放集取闭包还是取平凡上界，故两臂之差可整份
归给闭包。读数是耗时与 $C_{\max}$ 几乎相同（$3.16$ vs $3.30$ ms；逐格 $0/46/4$），
改动比例 $0.535$ vs $0.604$（逐格 $32/17/1$，Wilcoxon $p=5.9\times10^{-7}$）。
即：**毫秒级响应来自单遍改路而非闭包，闭包兑现的是稳定性**，且降幅与闭包排除掉多少
成正比（释放占比 $0.94$ 的算例只降 $0.010$，$0.88$ 的降 $0.128$）。

`scale_curve` 的梯子是工件 $2k$、机器 $k$、车 $k$，$k=4..10$，拥堵档与 $H$/$F$/Tt-Tp
及两处割集同口径标定，**只有规模变**（算例由 `clbs/tools/gen_instances.py` 生成）。
要紧的一条是闭包占比不随规模上涨（$0.544 \to 0.426$），否则「有界」就名存实亡。

`--only-e5` 跑出的 CSV 多四列 `R0/R2_past_changed|total`：按假设 A2，
`t_end <= t_now` 的预约不得被改写，有界修复应恒为 $0$，而全局重解臂从 $t=0$
重新解码、不受该约束——这四列把它越界的程度量出来。存档在
`experiments/e5_a2_audit.csv`（与 `expanded/e5_cross_curve.csv` 同协议同代码路径；
官方文件未覆盖是因为 R0+ 受挂钟预算约束、完成代数随机，重跑会改动论文表格读数）。

`decode_cost` 回答的是「把种群调小，全局重解能不能进毫秒档」。答案是能：
单次解码 $0.6$–$6.1$ ms，只有一次有界修复的 $0.95$–$2.18$ 倍。所以
**不要**把 R0+ 守不住小预算写成结构性下限——那是 $40$ 个体这一配置的属性。

## 五、算例从哪来

分三种来源，**账本分开、不混报**：

| 来源 | 位置 | 说明 |
| --- | --- | --- |
| 自建受控算例（主批次） | `../clbs/input/...` | 直接指向，不复制；正文所有 `/50` 读数出自此 |
| 外部布局算例 + 同参数对照 | `database/instances/` | **本地镜像**，见下 |
| 初始排程 / 扰动 | `input/schedules/`、`input/disturbances/` | 排程由 clbs 闭环解导出（脚本待补）；扰动 schema 见 `algorithm/disturbance.py` |

### 本地公开数据镜像 `database/`

paper04 用到的公开数据（Lyu 等 2019 的布局拓扑）**在本仓库存一份镜像**，使数据与用它的
代码同处一地——归档与投稿附件不必跨到 `clbs/` 去捞。`tools/pub_batch.py` 读的就是这份
副本，不是摆设。

```powershell
py -m tools.sync_database            # 从 clbs 重新同步
py -m tools.sync_database --check    # 校验未漂移(逐字节 + SHA256)
```

**真值仍在 `clbs/database/`**（那里记原始下载 URL、许可、各族可用性判定）；本地这份只回答
"paper04 到底吃了哪些字节"。副本最容易烂在两处静默不一致上，故一律由脚本生成、
`MANIFEST.csv` 记 SHA256、`--check` 可查漂移。

引用这批数字前必须知道三处口径：**逐段行驶时间是补的**（Lyu 未发表附录布局的边权，本批取
等权）、**装卸点做了合并**、**工件与工时未借用**（公开族运输占比过低，搬入会让争用现象消
失）。即被外部化的只有**布局出处**。详见 `database/README.md` 与
`experiments/pub_layouts/README.md`。
