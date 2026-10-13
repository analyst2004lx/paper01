# refvalues — 文献参考值表 / Literature reference-value tables

规格 12.4 第 5 项。每个数据集一个 CSV,文件名即 `dataset_key`(如 `hf.csv`、`bu.csv`)。
`-ideal` 档的 gap(%) 由批跑器读这些表自动算,不许在报告里手抄数字。

Spec 12.4, item 5. One CSV per dataset; the filename is the `dataset_key` (for example `hf.csv`, `bu.csv`). The gap (%) of the `-ideal` mode is computed automatically by the batch runner from these tables. Numbers must not be copied into a report by hand.

## 列定义 / Column definitions

| 列 / Column | 含义 / Meaning |
| --- | --- |
| `instance` | 算例原名(与 `database/json/<key>/` 中去掉 regime 后缀的名字一致) / Original instance name (the name under `database/json/<key>/` with the regime suffix removed) |
| `citekey` | `paper01/reference-base.bib` 里的键;没有对应条目就先补 bib,别留空 / Key in `paper01/reference-base.bib`; if there is no entry, add the bib first and do not leave it blank |
| `kind` | `proven_optimal` / `best_known` / `reported` / `lower_bound` 四者之一 / one of `proven_optimal` / `best_known` / `reported` / `lower_bound` |
| `value` | makespan 数值 / makespan value |
| `method` | 产生该值的方法(如 `CP`、`BRKGA`、`LAHC`、`GA`) / method that produced the value (for example `CP`, `BRKGA`, `LAHC`, `GA`) |
| `time_s` | 原文报告的求解时间(秒);没报就留空,**不要填 0** / solve time reported in the source (seconds); leave blank if unreported, **do not fill in 0** |
| `delta_return` | 该值所依据的口径:0 = 成品不回运(多数文献),1 = 回运 / convention behind the value: 0 = finished goods are not hauled back (most of the literature), 1 = return haul |
| `note` | 口径差异、疑问、失效说明 / convention differences, doubts, and notes that a result is invalidated |

`kind` 的区分不是分类癖。`proven_optimal`(如 Ham 2020 的 CP 最优值)可以直接当下界参照,
用来给本方法的绝对质量定位;`best_known` 只是"目前最好的已知上界",拿它算出的 gap 为负
不代表求得最优。两者混进同一列再统一叫 gap,读者无法判断结论强度。

The split on `kind` is not a taxonomy habit. `proven_optimal` (for example Ham 2020's CP optima) can be used directly as a lower-bound reference and locates the absolute quality of this method. `best_known` is only "the best known upper bound so far"; a negative gap against it does not mean an optimum was found. Mixing the two into one column and calling both gap leaves the reader unable to judge how strong the conclusion is.

## 已知的坑 / Known pitfalls

- **Nouri 等 (2016) 的部分结果已被 Homayouni & Fontes (2021) 证明无效**,收录时 `kind` 填
  `reported` 并在 `note` 注明失效,**不得计入 best_known**。规格 12.2 已有此警告。

  **Some results of Nouri et al. (2016) have been shown invalid by Homayouni & Fontes (2021).** When they are recorded, set `kind` to `reported` and note the invalidation in `note`. They **must not be counted as best_known**. Spec 12.2 already carries this warning.

- 文献间 `delta_return` 口径不统一。本项目 `-ideal` 档统一取 0(规格 12.2),故 `delta_return=1`
  的行不能与之直接比,只能另表列出。

  The literature does not share one `delta_return` convention. This project's `-ideal` mode uses 0 throughout (spec 12.2), so a row with `delta_return=1` cannot be compared with it directly and can only be listed in a separate table.

- 同一实例常有多篇报告不同值,应**逐篇留行**而非只留最好的一行。只留最好值等于丢掉
  "这批算例上各方法的离散程度",而那恰恰是判断 1–2% 差距是否有意义的唯一依据。

  The same instance often has different values in several papers. **Keep one row per paper** rather than only the best row. Keeping only the best value throws away "how spread the methods are on this batch", which is the only basis for judging whether a 1–2% gap means anything.

## 收录来源(规格 12.2) / Sources included (spec 12.2)

| 来源 / Source | 方法 / Method | 用途 / Role |
| --- | --- | --- |
| Ham (2020) | CP,**精确最优值** / CP, **exact optima** | 下界参照,F3 / lower-bound reference, F3 |
| Homayouni 等 (2023) / Homayouni et al. (2023) | BRKGA(多数实例最优) / BRKGA (optimal on most instances) | best_known 主要来源 / main source of best_known |
| Homayouni & Fontes (2021) | LAHC / 局部搜索 / LAHC / local search | best_known 与失效判定依据 / basis for best_known and for invalidation decisions |
| Chaudhry 等 (2022) / Chaudhry et al. (2022) | GA | 同族方法的量级参照 / magnitude reference for a method of the same family |
