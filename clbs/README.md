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
py main.py --mode closed                         # 只跑闭环算法
py main.py --mode ablation                       # 跑完整递进消融链(七档)
py main.py --seed 7 --pop 100 --gen 200          # 覆盖 GA 参数
py main.py --dispatch rule                       # 派车回到开环(对照)
py -m tests.test_all                             # 运行 T1–T8 全部测试断言
py -m tools.sweep_price                          # 机制诊断扫描(θ / 派车 / 错峰 / 同算力复核)
```

纯 Python 标准库实现,**无第三方依赖**(见 requirements.txt)。

## 二、文件夹层级

```text
clbs/
  README.md            # 本文件
  requirements.txt     # 依赖说明(无第三方依赖)
  main.py              # 一键运行入口:载入算例 → 求解 → 校验 → 写结果
  algorithm/           # 算法核心(与规格文档章节一一对应)
    instance.py        #   算例数据模型 + JSON 载入 + 特征参数 + 复合下界(规格 3.1 / 12.3.5)
    generator.py       #   受控扩展算例生成:布局模板、容量旋钮、H/F 控制、Tt/Tp 标定(规格 12.3)
    network.py         #   路网、t*、容量化预约表、价格表、多标签路由(规格 5.1–5.5)
    pricing.py         #   影子价格估计:有限差分定义式 + 代理式 + 一致性(规格 5.5)
    decoder.py         #   解码器、两种派车规则、带类型标签的关键链归因(规格 6.2–6.3、6.5)
    ga.py              #   主循环、通用算子、冲突制导局部搜索(规格 6.4–6.5)
    baseline.py        #   两阶段 open-loop 与四个消融档(规格 8)
    validator.py       #   独立校验器,八项检查 (a)–(h)(规格 9)
    report.py          #   字符甘特图、走廊占用率画像、结果摘要生成(规格 3.3)
  tools/
    sweep_price.py     #   机制诊断扫描(含同算力预算复核)
    gen_instances.py   #   扩展算例矩阵生成 CLI(规格 12.3.4)
  input/               # 输入算例(规格 3.1 JSON 格式)
    example_3x3x2.json #   验证用基准算例(建模文档第六节示例,已知可行解 makespan=51)
    congested_8x4x4.json #  拥堵型算例:哑铃拓扑 + 独占瓶颈走廊 + 远端快机
    ext/               #   生成的受控扩展算例(子目录,默认 glob 不扫)
  output/              # 运行结果(每算例一个子目录,含 summary.json、时刻表、甘特图)
  tests/
    test_all.py        # 规格 9 的 T1–T10 测试断言
```

## 三、算例输入格式

见规格文档 3.1 节 JSON schema。要点:

- `proc_time` 中键 `"(j,i)"` 为工序,值字典缺失的机器即不在 Ω_ji 内(部分柔性);
- `corridors` 为双向物理走廊,两方向共用一个独占预约资源;
- `delta_return`:1 = 成品回运计入 makespan(基本模型),0 = 不回运变体(与 FJSPT 公开基准对标时用);
- 所有时间为非负数(基准算例均为整数)。

公开数据集(Bilge / Deroussi / Kumar / Homayouni,见规格文档 12.1)需先经格式转换器
转为本 JSON 格式后放入 `input/`;转换器属规格 12.4 的待办项,尚未实现。

### 受控扩展算例(规格 12.3)

```powershell
py -m tools.gen_instances --list      # 只打印特征表,不落盘
py -m tools.gen_instances            # 4 档拥堵度 × 4 个异构度 = 16 个算例 -> input/ext/
py -m tools.gen_instances --seeds 42 7 2024 --jobs 10 --machines 5
```

拥堵度四档 `low / mid / high / funnel` **只改路网容量结构**,Tt/Tp 被统一标定到同一
目标值,故各档之间运输强度不变、变的只有结构。其中 **`high` 与 `funnel` 是一组
受控对比**:同种子下加工时间、机器位置、Tt/Tp 逐字段相同,唯一差别是 LU 出口容量
(2 条 vs 1 条)。funnel 多出的拥堵**与机器指派无关**(每个工件的首道送达与成品回运
都必经),故若各反馈机制只在 high 上显示增益、在 funnel 上消失,即证明"决策无关
拥堵稀释机制信号"这一诊断。详见规格 12.3.3。

生成的每个文件自带 `_spec`(完整生成参数含种子,逐字节可复现)与 `_features`
(实测特征、目标值、复合下界);两者均以 `_` 开头,载入时被忽略。

## 四、求解模式

| 模式 | 说明 | 对应规格章节 |
| --- | --- | --- |
| closed | 完整方法:适应度 = 路由后真实 C_max;派车查预约表试探;精英个体做冲突制导改派 + 错峰 | 4、6(8.1 档 6) |
| twostage | 两阶段 open-loop 基线:先用理想矩阵 t* 排产,冻结方案后再无冲突路由修复 | 8.1 档 2 |
| nofeedback | 消融:去掉 6.5 局部搜索 | 8.1 档 3 |
| opendispatch | 消融:派车回到开环(理想矩阵估算) | 8.1 档 4 |
| nostagger | 消融:关闭错峰算子,只留改派 | 8.1 档 5 |
| rule | 调度规则基线:最短加工时间指派 + 贪心排序,单次解码 | 8.1 档 1 |
| priced | **负面对照**:开启价格加权路由(θ>0),经检验有害,如实报告用 | 5.5、13.3 |
| ablation | 依次跑上述七档 | 8.1 |

> **对比协议(规格 8.2)**:① `opendispatch`/`nostagger` 等档运行更快,必须**同算力预算**比较(放宽快档早停至运行时间相当),否则会把"多花算力"误读为"机制更好";② 需 ≥10 个种子并报告离散度——拥堵算例上单档三种子极差可达 11,而各档均值之差仅 1–3。
>
> **算例强度提示**:`example_3x3x2` 上 closed 与 twostage 均为 34.0,集成收益为 0(冲突太稀疏)。要检验集成收益必须用规格 12.3 的扩展算例,基准算例只用于 T1–T8 回归。

退化对标(规格 12.2):对 FJSPT 公开基准,设 `delta_return=0` 并以 twostage 的
第一阶段(理想矩阵、无冲突)结果与文献 best-known 比较。

## 五、输出说明

每个算例在 `output/<算例名>/` 下生成:

- `summary.json`:各模式 makespan、闭环相对两阶段的改进率、实例特征参数(T̄t/T̄p、
  异构度、柔性度、NA/NM,以及结构指标 `funnel_share` / `lu_min_cut` / `far_group_cut`)、
  运行时间、校验结果、GA 收敛历史,以及 **`occupancy` 走廊占用率画像**
  (每条走廊的平均/峰值占用与忙桶数、瓶颈走廊、最忙的时空槽位);
- `timetable_<模式>.json`:完整时刻表(工序 + 运输任务 + AGV 分段轨迹);
- `gantt_<模式>.txt`:字符甘特图(makespan ≤ 300 时生成)。

占用率由 `report.corridor_occupancy` **从时刻表独立重算**(不读预约表内部状态),
只对每个模式的最终最优解算一次,对搜索零影响。它用于实证"某条走廊是否真的是瓶颈"
——例如 `congested_8x4x4` 的实测显示 `c1–c2`(0.68)与 LU 出口 `v0–c1`(0.55)是
**两级串联咽喉**,而非规格 3.1 原先声称的单一瓶颈,详见规格 3.1 的实测修正。

## 六、默认参数(规格 7)

pop=100, max_gen=200, stall_gen=30, pc=0.8, pm=0.2, elite=5,
top_ls=10%, L_ls=5, ls_rounds=3;random_seed 默认 42(命令行可覆盖)。
派车默认 `dispatch=exact`(查预约表试探,闭环);`use_conflict_ops=True`(启用错峰算子);
`theta=0.0`,即**价格协调默认关闭**——诊断显示 θ>0 系统性有害,数据见规格 13.2、
机制解释见规格 13.3。

已知的文档—代码不一致项(待修)列于规格 13.4,其中"C_max 口径分散在 decoder 与
validator 两处"属正确性风险,应最先处理。

## 七、测试

`py -m tests.test_all` 依次执行规格 9 的 T1–T12:最短路矩阵、makespan=51 参考方案
校验、1000 随机染色体可行性、解码确定性、同机免运输、回运开关、冲突消解、GA 有效性、
禁派集生效与兜底、占用率两套计算一致性(顺带验证派车试探的落表-回滚无残留)、
生成算例可行性与下界合法性、拥堵度旋钮受控性与可复现性。全部通过后方可用于数据集实验。
