# 外部来源布局批次

入口:`py -m tools.pub_batch`(在 `STRC/` 下)。汇总数由 `py -m tools.paper_numbers`
的末段一并打印,论文正文的宏只应从那里抄。

## 这是一批独立账本

**不要把本目录并入 `experiments/expanded/`。** 主批次的 5 算例 × 10 种子 = 50 对是
paper04 正文里所有 `/50` 读数(`\NPairs`)的来源;把外部布局混进那个批次会让全部门槛
读数改口径。本批用自己的一套宏(`\NPub*`、`\PubClo*`)。

## 算例从哪来

路网拓扑三项——网格尺寸、装卸站与机器落位、断掉的边——逐项转录自
`clbs/database/raw/tjsp_toolset/data/benchmarks/lyu2019/layouts/`,即 van Os 配套工具集
对 Lyu 等(2019)附录 A 布局图的机读编码。转录结果登记在
`clbs/algorithm/generator.py` 的 `PUB_LAYOUTS`,并由 `clbs/tools/check_pub_layouts.py`
与原始 `.data` 文件逐字段对账(六张布局 + 生成算例的路网,全部通过)。
算例由 `clbs/tools/gen_pub_layouts.py` 生成,落在 `clbs/input/pub/`。

**本批实际读的是 `STRC/database/instances/` 下的镜像**,以便数据与 paper04 的代码同处
一地;原始布局与解析源码的副本在 `STRC/database/raw/`。真值仍在 `clbs/database/`
(那里记原始 URL、许可与各族可用性判定),镜像由 `py -m tools.sync_database` 生成,
`--check` 可查两处是否漂移。口径与排除理由见 `STRC/database/README.md`。

## 三处口径(引用本批数字前必须知道)

1. **逐段行驶时间不是原始数据。** Lyu 只为单个示例算例发表过逐段时长(取值并不均匀),
   附录 A 那批布局的从未发表。本批按"所有边等权"补齐,与 van Os 的单步常量假设在结构上
   一致,只是时间单位标度不同(标度被 Tt/Tp 标定吸收)。
   **因此本批结果不可与 Lyu 或 van Os 的参照值作任何比较。**
2. **装卸点做了合并。** 原布局有分离的装货站与卸货站;本项目只有一个装卸点,故取车辆
   起始处的装货站充当该点,卸货站退化为普通网格节点。
3. **工件数据没有借用。** 公开族的平均运输时长只占平均加工时长的百分之几,运输在其上
   几乎不构成争用;一并搬入会让本文的研究对象消失。外部化的只有路网。

Liu 2023 那四张布局未收入:其数据声明允许对角移动,而本项目走廊为四邻接;接受对角移动
要改的是下层路由层而不是算例。

`LyuL1`(3 机)已转录但未生成算例:固定 F=0.6 时 F·NM=1.8<2,与 B1 冲突;为一张布局
放宽 F 等于多引入一个变量。

## 文件

| 文件 | 内容 |
| --- | --- |
| `e1_miss.csv` | 5 布局 × 10 种子,任务图漏报 |
| `e2_containment.csv` | 结构闭合 + 外侧字段逐条比对 |
| `e3_boundary.csv` | R1 vs R2,关闭扩域 |
| `e4_structure.csv` | 封死 LU 割走廊到视界末端;**含 3 张同参数自建对照** |
| `e5_cross_curve.csv` | 预算扫描(2 布局 × 3 种子 × 3 预算) |
| `summary.md` | 汇总表 |
| `run_log.txt` | 批跑输出 |

`e4_structure.csv` 里 `instance` 以 `self_` 开头的三行是自建对照组(`clbs/input/ext/` 的
`S8x4x4` 三档),与外部布局逐参数同口径,只差布局来源。没有这一组就无法判断"外部布局的
闭包占比离散度更大"——论文 `tab:e4` 那张表用的是另一套参数(12 工件/8 机/12 车),
与本批不可直接对照。
