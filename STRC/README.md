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
  input/
    schedules/            #   初始可行排程(可由 clbs 闭环解导出的 JSON)
    disturbances/         #   扰动描述 JSON(类型、时刻、作用对象)
  output/                 #   单次运行结果
  experiments/            #   批跑账本与汇总表
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
```

## 五、算例从哪来

- 车间/路网 JSON：直接指向 `../clbs/input/...`（不必复制）  
- 初始排程：用 clbs 闭环解导出到 `input/schedules/`（导出脚本待补）  
- 扰动：写在 `input/disturbances/*.json`，schema 见 `algorithm/disturbance.py`
