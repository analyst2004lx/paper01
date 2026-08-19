# output_database — 公开数据集分支的运行输出

与 `output/`(自造受控算例)平行、互不混用。分开的理由见 `database/README.md` 第一节:
两支的报告口径不同(`-ideal` 退化对标 vs `-excl` 争用版本),同目录存放迟早会被当作
同一批数据引用。

## 目录约定(照 `output/` 的既有形状)

```text
output_database/
  <instance_name>/           # 单算例单次运行
    summary.json             #   各模式 makespan、特征参数、校验结果、收敛历史、走廊占用率
    timetable_<模式>.json    #   完整时刻表(工序 + 运输任务 + AGV 分段轨迹)
    gantt_<模式>.txt         #   字符甘特图(makespan <= 300 时生成)
  matrix/<run>/              # 批跑账本
    records.jsonl            #   每完成一个 (算例, 档位, 种子) 立即追加一行并 fsync
    summary.json
    report.md
```

## 两个 regime 分开落盘

`-ideal` 与 `-excl` 是同一算例的两个版本(见 `database/README.md` 第三节),算例名自带后缀,
因此天然落在不同子目录,不需要额外约定。**但汇总时必须按后缀分表**:把退化档的 gap 和
争用档的阶梯增益放进同一张表,等于把"我们的 GA 不弱"和"闭环有收益"两件独立的事混成
一个数字。

## 校验是落盘的前提

每个解都要过 `algorithm/validator.py` 的八项检查并与复合下界比对,失败项单列在报告顶部。
公开算例上这一条比自造算例更要紧:自造算例的可行性由生成器保证,公开算例的可行性取决于
**转换器有没有把原数据读对**,而校验器是唯一能在结果层面抓住转换错误的东西。
