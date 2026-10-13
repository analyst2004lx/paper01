# output_database — 公开数据集分支的运行输出 / Run output of the public-dataset branch

与 `output/`(自造受控算例)平行、互不混用。分开的理由见 `database/README.md` 第一节:
两支的报告口径不同(`-ideal` 退化对标 vs `-excl` 争用版本),同目录存放迟早会被当作
同一批数据引用。

Parallel to `output/` (self-generated controlled instances) and not mixed with it. The reason for the split is in Section 1 of `database/README.md`: the two branches use different reporting conventions (`-ideal` degenerate benchmarking vs the `-excl` congestion version). Stored in one directory, they would eventually be cited as one batch.

## 目录约定(照 `output/` 的既有形状) / Directory convention (the existing shape of `output/`)

```text
output_database/
  <instance_name>/           # 单算例单次运行 / one instance, one run
    summary.json             #   各模式 makespan、特征参数、校验结果、收敛历史、走廊占用率 / makespan of each mode, feature parameters, validation result, convergence history, corridor occupancy
    timetable_<模式>.json    #   完整时刻表(工序 + 运输任务 + AGV 分段轨迹) / full timetable (operations + transport tasks + AGV segment trajectories)
    gantt_<模式>.txt         #   字符甘特图(makespan <= 300 时生成) / character Gantt chart (generated when makespan <= 300)
  matrix/<run>/              # 批跑账本 / batch-run ledger
    records.jsonl            #   每完成一个 (算例, 档位, 种子) 立即追加一行并 fsync / append one line and fsync as soon as one (instance, mode, seed) finishes
    summary.json
    report.md
```

## 两个 regime 分开落盘 / The two regimes are written separately

`-ideal` 与 `-excl` 是同一算例的两个版本(见 `database/README.md` 第三节),算例名自带后缀,
因此天然落在不同子目录,不需要额外约定。**但汇总时必须按后缀分表**:把退化档的 gap 和
争用档的阶梯增益放进同一张表,等于把"我们的 GA 不弱"和"闭环有收益"两件独立的事混成
一个数字。

`-ideal` and `-excl` are two versions of the same instance (see Section 3 of `database/README.md`). The instance name carries the suffix, so they land in different subdirectories with no extra convention. **Aggregation must still split tables by suffix.** Putting the degenerate-mode gap and the congestion-mode ladder gain in one table mixes two independent claims — "our GA is not weak" and "the closed loop has a gain" — into one number.

## 校验是落盘的前提 / Validation is a prerequisite for writing the files

每个解都要过 `algorithm/validator.py` 的八项检查并与复合下界比对,失败项单列在报告顶部。
公开算例上这一条比自造算例更要紧:自造算例的可行性由生成器保证,公开算例的可行性取决于
**转换器有没有把原数据读对**,而校验器是唯一能在结果层面抓住转换错误的东西。

Every solution must pass the eight checks in `algorithm/validator.py` and be compared with the composite lower bound. Failed items are listed on their own at the top of the report. This matters more on public instances than on self-generated ones: feasibility of a self-generated instance is guaranteed by the generator, while feasibility of a public instance depends on **whether the converter read the source data correctly**. The validator is the only thing that can catch a conversion error at the result level.
