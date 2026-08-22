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
py -m tests.test_all                             # 运行 T1–T14 全部测试断言
py -m tools.sweep_price                          # 机制诊断扫描(θ / 派车 / 错峰 / 同算力复核)
```

矩阵批跑(主试验入口,规格 8.4):

```powershell
py -m tools.run_matrix --preset smoke             # 流程自检(2 算例 x 7 档 x 2 种子)
py -m tools.run_matrix --preset p3 --dry-run      # 先看任务数与预计耗时
py -m tools.run_matrix --preset p3                # high/funnel 受控对比(预测 3)
py -m tools.run_matrix --preset full --budget gen # 完整矩阵的等代数口径
py -m tools.run_matrix --preset full --report-only # 随时用已有账本出报告
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
    ga.py              #   主循环、通用算子、冲突制导局部搜索(规格 6.4–6.5);
                       #   挂钟预算闸门 time_budget_sec(规格 8.2 协议 1)
    baseline.py        #   七档定义 ARMS / solve_arm + 两阶段 open-loop(规格 8.1);
                       #   另有 ideal 档(退化对标,规格 12.2),故意不在 ARMS 内

    stats.py           #   描述统计、Wilcoxon 配对检验、Spearman(规格 8.2 协议 2)
    validator.py       #   独立校验器,八项检查 (a)–(h)(规格 9)
    report.py          #   字符甘特图、走廊占用率画像、结果摘要生成(规格 3.3)
  tools/
    sweep_price.py     #   机制诊断扫描(含同算力预算复核)
    gen_instances.py   #   扩展算例矩阵生成 CLI(规格 12.3.4)
    run_matrix.py      #   矩阵批跑器:预算标定 / 账本续跑 / 配对检验(规格 8.4)
    convert_public.py  #   公开基准 → 3.1 schema 转换器 + 布局保真度体检(规格 12.4 第 2 项)
    run_database.py    #   公开算例批跑器:ideal 档 + 自动算 gap + 三条硬性判定(规格 12.2)
  input/               # 输入算例(规格 3.1 JSON 格式)——自造受控算例这一支
    example_3x3x2.json #   验证用基准算例(建模文档第六节示例,已知可行解 makespan=51)
    congested_8x4x4.json #  拥堵型算例:哑铃拓扑 + 独占瓶颈走廊 + 远端快机
    ext/               #   生成的受控扩展算例(子目录,默认 glob 不扫)
  output/              # 运行结果(每算例一个子目录,含 summary.json、时刻表、甘特图)
    matrix/<run>/      #   批跑账本 records.jsonl + summary.json + report.md
  experiments/         # 自造算例的汇总 CSV(进论文的那张表,由导出脚本生成)
  database/            # 公开数据集这一支的唯一入口(规格 12.1/12.4)
    README.md          #   数据集键、口径、转换流程、两个 regime、验收标准
    raw/               #   原始发布件,只读;按数据集分子目录
    extracted/         #   从只读 PDF 提取的文本(pdftotext 产物,SHA256 记进 MANIFEST)
    json/              #   转换为 3.1 schema 的算例(转换器产物,不许手改)
      hf/              #     Homayouni & Fontes set 1:20 个 *-ideal.json + _fidelity.json
    network/           #   还原/数字化的路网模板(规格 12.4 第 3 项)
    refvalues/         #   文献参考值表,供自动算 gap(规格 12.4 第 5 项)
    MANIFEST.csv       #   逐文件来源 / 下载日期 / SHA256 / 状态
  output_database/     # 公开算例的运行结果(形状同 output/)
    records_<预算>.jsonl #   可续跑账本,**按算力预算分文件**(混用会静默出错)
  experiments_database/# 公开算例的汇总 CSV(形状同 experiments/)
    gap_ideal.csv      #   与文献参考值的 gap(进论文表 9)
    budget_effect.csv  #   两种算力预算并排:gap 是能力上界还是预算不足
    fidelity.csv       #   各布局矩阵能否还原为走廊图
  tests/
    test_all.py        # 规格 9 的 T1–T14 测试断言 + T15(矩阵型算例:有向 + 非度量)
```

> **两支为何分家**:`main.py` 默认 glob 是 `input/*.json`,把上百个公开算例放进去会让默认
> 运行从 2 个算例变成 100 多个;更要紧的是两支**报告口径不同**(退化对标的 gap vs 争用版本
> 的阶梯增益),同目录存放迟早被当作同一批数据引用。详见 `database/README.md`。

## 三、算例输入格式

见规格文档 3.1 节 JSON schema。要点:

- `proc_time` 中键 `"(j,i)"` 为工序,值字典缺失的机器即不在 Ω_ji 内(部分柔性);
- `corridors` 为双向物理走廊,两方向共用一个独占预约资源;
- `delta_return`:1 = 成品回运计入 makespan(基本模型),0 = 不回运变体(与 FJSPT 公开基准对标时用);
- 所有时间为非负数(基准算例均为整数)。

- `network.ideal_dist`(选填):直接给定取放点两两行驶时间,**绕过最短路计算**。仅用于公开
  基准的退化对标——文献只发布一张"位置对–时长"矩阵,而该矩阵可能有向、甚至不满足三角不等式
  (实测 Homayouni & Fontes 的 7 个布局全部有向,3-M / 7-M 两个还非度量),这两种性质没有任何
  无向走廊图能承载。给了它就必须 `corridors: []`,此时 `Network.routable` 为假,`Router` 在
  `conflict_free=True` 下**显式报错**而不是给出无意义的解。回归断言见 T15。

公开数据集(Bilge / Deroussi / Kumar / Homayouni / Lyu,见规格文档 12.1)走独立的一支:
原始件在 `database/raw/`,转换后的算例落 `database/json/`,结果落 `output_database/`,
汇总落 `experiments_database/`。流程、两个 regime 的报告口径与三道验收标准见
`database/README.md`。

```powershell
# 一次性:从只读 PDF 提取文本(需 poppler 的 pdftotext,提取物连同 SHA256 记进 MANIFEST)
pdftotext -raw -enc UTF-8 database/raw/homayouni_fontes_2020/<f>.pdf database/extracted/hf/<f>.txt

py -m tools.convert_public --check     # 只做布局保真度体检(能否还原为走廊图),不落盘
py -m tools.convert_public             # 转换 hf 全 20 个算例 -> database/json/hf/
```

转换器纯标准库可跑(提取那一步才需外部二进制,故切成两步)。**提取错误不会静默通过**:每个
算例头自带 `M*J*O` 三个声明值,解析器逐个核对机器数、工件数、工序数与先后关系条数(= O − J),
少一行、串一行、数字粘连都会被这四个约束之一抓住。

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

> **对比协议(规格 8.2)**:① `opendispatch`/`nostagger` 等档运行更快,必须**同算力预算**比较(放宽快档早停至运行时间相当),否则会把"多花算力"误读为"机制更好";② 需 ≥10 个种子并报告离散度——拥堵算例上单档三种子极差可达 11,而各档均值之差仅 1–3;③ **等时间与等评估数两种口径都要报**——`twostage` 的第一阶段在理想模型下评价,单次成本比闭环低一到两个数量级(实测 0.43 vs 17–20 ms),等时间等于给它数十倍搜索次数,等评估数又等于让闭环多花数十倍 CPU,两种口径都不中立。
>
> 这三条已由 `tools/run_matrix.py` 做成默认行为(见下节),不必靠人工纪律维持。

### 矩阵批跑器(规格 8.4)

```powershell
py -m tools.run_matrix --preset p3 --dry-run   # 任务数与预计耗时
py -m tools.run_matrix --preset p3             # 跑;中断后重复同一命令即续跑
py -m tools.run_matrix --preset p3 --report-only   # 只出报告
```

- **预算标定**:`--budget auto` 逐算例以"完整方法的自然用时"为全部档位共享的挂钟预算;
  `--budget gen` 为等代数口径;`--budget 30` 为固定秒数;
- **可中断续跑**:每完成一个 (算例, 档位, 种子) 立即追加一行 JSONL 并 `fsync`,重跑
  同名 `--run` 自动跳过;任务顺序为"算例 → 种子 → 全部档位",中断后留下的是**完整
  配对块**而非半个种子;
- **报告**:`output/matrix/<run>/report.md` 含各格均值±标准差、毫秒每评价与停机原因
  (预算体检)、集成收益与机制增益的配对 Wilcoxon,以及 12.3.6 三条预期的自动判定。
  每个解都过独立校验器并与复合下界比对,失败项在报告顶部单列。
>
> **算例强度提示**:`example_3x3x2` 上 closed 与 twostage 均为 34.0,集成收益为 0(冲突太稀疏)。要检验集成收益必须用规格 12.3 的扩展算例,基准算例只用于 T1–T8 回归。

### 退化对标:公开基准(规格 12.2)

```powershell
py -m tools.run_database --smoke                       # 3 种子,先看流程与耗时
py -m tools.run_database --seeds 10                    # 正式跑(20x10,约 2 分钟)
py -m tools.run_database --only mfjs --pop 100 --gen 1000 --stall 100 `
                         --compare p100g200s30         # 高预算对照 -> budget_effect.csv
py -m tools.run_database --report-only                 # 用已有账本重出报告
```

配置为 `delta_return=0`、`conflict_free=False`(预约表禁用)、`num_agvs=2`,运输时间**原样取
所发布的矩阵**而非最短路合成。算例带 `-ideal` 后缀,与带 `-excl` 后缀的争用版本**分表报告**
——前者排除"单一实现"这一有效性威胁,后者才是本方法的贡献,合成一张表读者就分不清哪个结论
靠哪批数据。删去排他约束后 `-excl` 精确退化为 `-ideal`,故两者是同一算例加/不加一族约束。

**报告顶部三条硬性判定**,任一触发都必须先查错再看结论:解低于 `proven_optimal`、解低于自算
复合下界、校验失败。第一条是这一档**唯一的结果层保真证据**——退化档与文献是同一个数学问题,
可证最优是硬地板;而这一档没有 AGV 分段,校验器的 (d)(e)(f)(h) 天然为空,"校验通过"不能充当
转换正确的凭据。

**账本按算力预算分文件**(`records_p100g200s30.jsonl`),载入时逐行核对:账本键只有
(算例, 种子) 不含预算,若两种预算混进同一文件,续跑会静默跳过、报告会把两种算力的数字并进
同一列均值,而这种错误在结果里看不出来。

hf 实测(20 算例 × 10 种子):三条判定 200 次运行全部通过;12/20 最优解与参照值逐位相同,
10 个小型算例全部命中可证最优;平均 gap 2.68%,但四个最大算例(32–48 工序)均值 9.96%。
把预算提到 2.5 倍挂钟只把 mfjs 的平均 gap 从 5.37% 降到 4.53%,故这是搜索能力边界而非预算
不足。详见 `experiments_database/gap_ideal.csv` 与 `budget_effect.csv`。

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
机制解释见规格 13.3。`time_budget_sec=None`,即默认不设挂钟预算(仅批跑时由
`run_matrix` 设定,见规格 8.2 协议 1)。

已知的文档—代码不一致项列于规格 13.4(C_max 口径与占用率采集两项已修;禁派集接入
GA 与增量评价为有意暂缓)。

## 七、测试

`py -m tests.test_all` 依次执行规格 9 的 T1–T14:最短路矩阵、makespan=51 参考方案
校验、1000 随机染色体可行性、解码确定性、同机免运输、回运开关、冲突消解、GA 有效性、
禁派集生效与兜底、占用率两套计算一致性(顺带验证派车试探的落表-回滚无残留)、
生成算例可行性与下界合法性、拥堵度旋钮受控性与可复现性、统计工具与已知精确值一致、
批跑基础设施(预算闸门 / 账本续跑 / 配对不错位)。全部通过后方可用于数据集实验。
