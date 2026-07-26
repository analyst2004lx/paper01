# CLBS — Closed-Loop Bilevel Scheduler

异构机械臂柔性作业车间调度 + AGV 无冲突路径规划的**闭环双层求解器**。
算法规格完全遵循《异构资源柔性作业车间协同调度核心算法.md》(下称"规格文档"),
建模假设遵循《建模问题梳理_异构资源柔性作业车间协同调度.md》。

## 一、快速开始(一键运行)

```powershell
cd clbs
py main.py                 # 对 input/ 下全部算例,跑 闭环 + 两阶段 + 规则基线,结果写入 output/
```

常用参数:

```powershell
py main.py --instance input/example_3x3x2.json   # 只跑指定算例
py main.py --mode closed                         # 只跑闭环算法(closed | twostage | rule | both)
py main.py --seed 7 --pop 100 --gen 200          # 覆盖 GA 参数
py -m tests.test_all                             # 运行 T1–T8 全部测试断言
```

纯 Python 标准库实现,**无第三方依赖**(见 requirements.txt)。

## 二、文件夹层级

```text
clbs/
  README.md            # 本文件
  requirements.txt     # 依赖说明(无第三方依赖)
  main.py              # 一键运行入口:载入算例 → 求解 → 校验 → 写结果
  algorithm/           # 算法核心(与规格文档章节一一对应)
    instance.py        #   算例数据模型 + JSON 载入 + 实例特征参数(规格 3.1 / H 五)
    network.py         #   路网、理想最短路 t*、预约表、时间窗 Dijkstra(规格 5.1–5.4)
    decoder.py         #   事件驱动解码器、车辆派工规则、拥堵统计、关键路径(规格 6.2–6.3)
    ga.py              #   GA 主循环、遗传算子、拥堵反馈局部搜索(规格 6.4–6.5)
    baseline.py        #   两阶段 open-loop 基线、调度规则基线(规格 8)
    validator.py       #   独立校验器(规格 9)
    report.py          #   字符甘特图与结果摘要生成
  input/               # 输入算例(规格 3.1 JSON 格式)
    example_3x3x2.json #   验证用基准算例(建模文档第六节示例,已知可行解 makespan=51)
  output/              # 运行结果(每算例一个子目录,含 summary.json、时刻表、甘特图)
  tests/
    test_all.py        # 规格 9 的 T1–T8 测试断言
```

## 三、算例输入格式

见规格文档 3.1 节 JSON schema。要点:

- `proc_time` 中键 `"(j,i)"` 为工序,值字典缺失的机器即不在 Ω_ji 内(部分柔性);
- `corridors` 为双向物理走廊,两方向共用一个独占预约资源;
- `delta_return`:1 = 成品回运计入 makespan(基本模型),0 = 不回运变体(与 FJSPT 公开基准对标时用);
- 所有时间为非负数(基准算例均为整数)。

公开数据集(Bilge / Deroussi / Kumar / Homayouni,见规格文档 12.1)需先经格式转换器
转为本 JSON 格式后放入 `input/`;转换器属规格 12.4 的待办项,尚未实现。

## 四、求解模式

| 模式 | 说明 | 对应规格章节 |
| --- | --- | --- |
| closed | 闭环双层:GA 适应度 = 路由后真实 C_max;精英个体做拥堵反馈改派局部搜索 | 4、6 |
| twostage | 两阶段 open-loop 基线:先用理想矩阵 t* 排产,冻结方案后再无冲突路由修复 | 8.1 |
| rule | 调度规则基线:最短加工时间指派 + 贪心排序,单次解码 | 8.4 |

退化对标(规格 12.2):对 FJSPT 公开基准,设 `delta_return=0` 并以 twostage 的
第一阶段(理想矩阵、无冲突)结果与文献 best-known 比较。

## 五、输出说明

每个算例在 `output/<算例名>/` 下生成:

- `summary.json`:各模式 makespan、闭环相对两阶段的改进率、实例特征参数(T̄t/T̄p、
  异构度、柔性度、NA/NM)、运行时间、校验结果、GA 收敛历史;
- `timetable_<模式>.json`:完整时刻表(工序 + 运输任务 + AGV 分段轨迹);
- `gantt_<模式>.txt`:字符甘特图(makespan ≤ 300 时生成)。

## 六、默认参数(规格 7)

pop=100, max_gen=200, stall_gen=30, pc=0.8, pm=0.2, elite=5,
top_ls=10%, L_ls=5, λ=0.5, rounds=3;random_seed 默认 42(命令行可覆盖)。
车辆派工规则默认用理想矩阵 t* 估算(`dispatch_exact` 未实现,见规格 6.3)。

## 七、测试

`py -m tests.test_all` 依次执行规格 9 的 T1–T8:最短路矩阵、makespan=51 参考方案
校验、1000 随机染色体可行性、解码确定性、同机免运输、回运开关、冲突消解、GA 有效性。
全部通过后方可用于数据集实验。
