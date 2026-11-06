# experiments_database — 公开数据集分支的汇总产物 / Summary products of the public-dataset branch

与 `experiments/`(自造受控算例的汇总 CSV)平行。`output_database/` 存的是每次运行的原始
产物,本目录存的是**进论文的那张表**:由导出脚本从 `output_database/` 的账本聚合而来,
一律可重新生成,不许手工编辑。

Parallel to `experiments/` (the summary CSVs of the self-generated controlled instances). `output_database/` stores the raw product of each run. This directory stores **the table that enters the paper**: aggregated by the export script from the ledgers in `output_database/`. Everything here can be regenerated and must not be edited by hand.

## 预期文件 / Expected files

| 文件 / File | 内容 / Contents | 对应规格 / Spec |
| --- | --- | --- |
| `instances.csv` | 每个算例一行:规模、T̄t/T̄p、H、F、N_A/N_M、争用强度、复合下界、来源 `dataset_key` / one row per instance: size, T̄t/T̄p, H, F, N_A/N_M, congestion intensity, composite lower bound, source `dataset_key` | 12.3.5 |
| `runs.csv` | 每个 (算例, 档位, 种子) 一行:makespan、用时、毫秒每评价、停机原因、校验结论 / one row per (instance, mode, seed): makespan, time, milliseconds per evaluation, stop reason, validation verdict | 8.2 |
| `gap_ideal.csv` | **`-ideal` 档**:本方法 vs 文献参考值的 gap(%),按 `kind` 分列(proven_optimal / best_known) / **`-ideal` mode**: gap (%) of this method against the literature reference values, split by `kind` (proven_optimal / best_known) | 12.2 |
| `gains_excl.csv` | **`-excl` 档**:四级阶梯的配对增益与 Wilcoxon / **`-excl` mode**: paired gains of the four-level ladder and Wilcoxon | 8.1、8.2 |
| `fidelity.csv` | 路网还原保真度:还原图全对最短路 vs 原文发布矩阵的**逐项**比对与最大偏差 / road-network reconstruction fidelity: an **entry-by-entry** comparison of the reconstructed graph's all-pairs shortest paths against the published matrix, and the maximum deviation | 12.4 第 3 项 / 12.4 item 3 |
| `meta.json` | 导出时的 git commit、时间戳、源账本路径、脚本版本 / git commit, timestamp, source-ledger path, and script version at export | — |

`gap_ideal.csv` 与 `gains_excl.csv` **必须是两个文件**。它们回答两个独立问题:前者排除
"单一实现"这一有效性威胁(我们的上层搜索够不够强),后者才是方法的贡献。合成一张表的
代价是读者再也分不清哪个结论靠哪批数据。

`gap_ideal.csv` and `gains_excl.csv` **must be two files**. They answer two independent questions: the first rules out the "single implementation" validity threat (is our upper-level search strong enough), and the second is the contribution of the method. Merging them into one table costs the reader the ability to tell which conclusion rests on which batch.

`fidelity.csv` 是整条 add-on 路线可信度的落点。公开数据给了图与弧时长、唯独没给弧容量
(其原模型里车辆从不干扰),本项目补的就是这一个量;`fidelity.csv` 是"我们只补了这一个量"
的凭证。它不全等时要留最大偏差与成因(取整、单向弧方向、口径差异),而不是悄悄放宽。

`fidelity.csv` is where the credibility of the whole add-on route lands. The public data give the graph and the arc durations and give no arc capacities (in the original model vehicles never interfere). This project adds exactly that one quantity, and `fidelity.csv` is the record that "we added only that one quantity". When it is not an exact match, keep the maximum deviation and its cause (rounding, one-way arc direction, convention difference) rather than quietly relaxing the check.

## 与论文数字的关系 / Relation to the numbers in the paper

`paper01/paper.tex` 里所有数值走宏定义,单一来源即本目录的 CSV。改了数据要**重跑导出再
更新宏**,不要在正文里手改数字——本项目在跨批次引用上已经栽过一次(论文结论二十四)。

Every number in `paper01/paper.tex` goes through a macro, and the single source is the CSVs in this directory. After the data change, **re-run the export and then update the macros**. Do not edit numbers by hand in the text — this project has already been burned once by cross-batch citation (paper conclusion 24).

## 命名 / Naming

沿用 `experiments/` 的文件名,分支差异由目录本身表达,不再加 `_db` 之类后缀。同名不同目录
比同目录不同后缀更难误引。

Keep the filenames of `experiments/`. The branch difference is expressed by the directory itself, with no extra suffix such as `_db`. The same name in a different directory is harder to cite by mistake than a different suffix in the same directory.
