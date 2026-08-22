# refvalues — 文献参考值表

规格 12.4 第 5 项。每个数据集一个 CSV,文件名即 `dataset_key`(如 `hf.csv`、`bu.csv`)。
`-ideal` 档的 gap(%) 由批跑器读这些表自动算,不许在报告里手抄数字。

## 列定义

| 列 | 含义 |
| --- | --- |
| `instance` | 算例原名(与 `database/json/<key>/` 中去掉 regime 后缀的名字一致) |
| `citekey` | `paper01/reference-base.bib` 里的键;没有对应条目就先补 bib,别留空 |
| `kind` | `proven_optimal` / `best_known` / `reported` / `lower_bound` 四者之一 |
| `value` | makespan 数值 |
| `method` | 产生该值的方法(如 `CP`、`BRKGA`、`LAHC`、`GA`) |
| `time_s` | 原文报告的求解时间(秒);没报就留空,**不要填 0** |
| `delta_return` | 该值所依据的口径:0 = 成品不回运(多数文献),1 = 回运 |
| `note` | 口径差异、疑问、失效说明 |

`kind` 的区分不是分类癖。`proven_optimal`(如 Ham 2020 的 CP 最优值)可以直接当下界参照,
用来给本方法的绝对质量定位;`best_known` 只是"目前最好的已知上界",拿它算出的 gap 为负
不代表求得最优。两者混进同一列再统一叫 gap,读者无法判断结论强度。

## 已知的坑

- **Nouri 等 (2016) 的部分结果已被 Homayouni & Fontes (2021) 证明无效**,收录时 `kind` 填
  `reported` 并在 `note` 注明失效,**不得计入 best_known**。规格 12.2 已有此警告。
- 文献间 `delta_return` 口径不统一。本项目 `-ideal` 档统一取 0(规格 12.2),故 `delta_return=1`
  的行不能与之直接比,只能另表列出。
- 同一实例常有多篇报告不同值,应**逐篇留行**而非只留最好的一行。只留最好值等于丢掉
  "这批算例上各方法的离散程度",而那恰恰是判断 1–2% 差距是否有意义的唯一依据。

## 收录来源(规格 12.2)

| 来源 | 方法 | 用途 |
| --- | --- | --- |
| Ham (2020) | CP,**精确最优值** | 下界参照,F3 |
| Homayouni 等 (2023) | BRKGA(多数实例最优) | best_known 主要来源 |
| Homayouni & Fontes (2021) | LAHC / 局部搜索 | best_known 与失效判定依据 |
| Chaudhry 等 (2022) | GA | 同族方法的量级参照 |
