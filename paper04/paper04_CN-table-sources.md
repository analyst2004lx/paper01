# 表格单元格出处清单（P11 / 第 10 维交付物）

生成日期：2026-09-18。对象：`paper04_CN_AI-Modify-26-09-17.tex`。
取证脚本：`paper04/table_inventory.py`（数字单元格计数）、`STRC/tools/p17_e5_stats.py`（离散度复算）。

## 为什么是「脚本化」而不是「宏化」

B13 曾试过把表体数字一律换成宏，结论是**不可行**：这些表\*本身\*就是数据源，
正文引用的读数是从表里摘出来的。若把表体换成宏，宏值又只能来自表，
就成了循环依赖——宏区会变成第二份真值，且无人保证它与 CSV 同步。

正解是反向的：**CSV → 脚本 → `.tex` 片段 → `\input`**。
表体由脚本从 `STRC/experiments/*.csv` 生成，宏区只保留\*正文要单独引用的那几个读数\*，
且这些宏同样由脚本写出。这样真值只有一份（CSV），表与宏都是它的投影。

## 分类结果（12 张表）

### 甲类：定性表，不需脚本化（2 张）

| 表 | 行 | 说明 |
|---|---|---|
| `tab:position` | 622 | 各类工况「需要改写什么」的定性对照，0 个数字单元格 |
| `tab:notation` | 756 | 记号表，唯一的数字不是读数 |

### 乙类：数据表，须脚本生成（10 张，合计约 327 个数字单元格）

| 表 | 行 | 数字单元格 | CSV 出处 | 重跑命令 |
|---|---|---|---|---|
| `tab:e1` | 1363 | 35 | `expanded/e1_miss.csv` | `py -m tools.expand_batch` |
| `tab:e2` | 1405 | 31 | `expanded/e2_containment.csv` | 同上 |
| `tab:e3` | 1483 | 40 | `expanded/e3_boundary.csv` | 同上 |
| `tab:e6` | 1532 | 20 | `expanded/e6_types.csv` | 同上 |
| `tab:e4` | 1659 | 17 | `e4_structure.csv` | `py -m tools.e4_structure` |
| `tab:e4pub` | 1678 | 50 | `pub_layouts/e4_structure.csv` | `py -m tools.pub_batch` |
| `tab:e5` | 1731 | 32 | `expanded/e5_cross_curve.csv` | `py -m tools.expand_batch --only-e5` |
| `tab:cheap` | 1816 | 14 | `cheap_baselines.csv` | `py -m tools.cheap_baselines` |
| `tab:scale` | 1923 | 25 | `expanded/scale_compare.csv` | `py -m tools.expand_batch`（φ 扫描段） |
| `tab:instscale` | 1970 | 63 | `scale_curve.csv` | `py -m tools.scale_curve` |

## 已完成的部分

乙类各表的**汇总量**（可行格数、通过率、区间端点）已经全部宏化，
宏名见各表「已用宏」一列，例如 `tab:e3` 的 `\FeasRone` / `\FeasRtwo` / `\NPairs`、
`tab:cheap` 的 11 个 `\Ms*` 与 `\ResFrac*`。**正文引用的读数没有一处是直接抄表体数字的**，
这一条由自检脚本的 `HARDCODED_NUM` 规则持续守着（当前 0 条）。

余下的是**逐格明细**（每算例每种子一行的那些数字），它们只出现在表体、不被正文单独引用，
因此不需要宏，只需要保证与 CSV 一致。

## 待作者执行（改动构建流程，故不在本轮代改）

1. 写 `STRC/tools/gen_tables.py`，对乙类 10 张表各输出一个 `tables/<label>.tex`
   片段（只含 `\toprule` 到 `\bottomrule` 之间的行），并同时写出
   `tables/macros.tex`（当前宏区里那些由 CSV 决定的宏）。
2. 正文把乙类表体换成 `\input{tables/<label>}`，宏区换成 `\input{tables/macros}`。
3. 在仓库 CI 或 `latexmk` 的 `$pre_compile` 钩子里先跑 `gen_tables.py`，
   使「CSV 改了但表没改」这种不一致无法通过编译。

代价与收益要说清：这样做会让 `.tex` 不再能脱离仓库单独编译（投稿时须附 `tables/`
的生成结果）。因此**建议在定刊、确认该刊接受附件目录结构之后再落地**；
在此之前本清单已足以让复核者按表逐格对账。

## 离散度口径（P17，本轮已补）

| 图/表 | n | 离散度口径 |
|---|---|---|
| `tab:e1` | 每算例 10 种子，共 50 对 | 逐算例 `Cl/|R|` 的 IQR 0.024–0.049；合池中位 0.571、极差 0.500–0.655 |
| `fig:e1e3` | 同上 | 左幅 `|Cl|` 的 IQR 逐算例 2–8；右幅为逐格计数，不配离散度 |
| `tab:scale` / `fig:scale` | 每档 10 种子 | STRC 耗时全扫描极差 2.2–23.8 ms；R0+ `C_max` 逐档 IQR 8–76 |

`tab:e5` 的离散度以「逐点胜/负计数」形式给出（35/1/0），不报均值离散度，
因为该表的结论是次序而非幅度。
