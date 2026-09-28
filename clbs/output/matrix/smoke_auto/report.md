# 矩阵实验报告 / Matrix experiment report `smoke_auto`

- 预算模式 / Budget mode:`auto`(各算例预算 / per-instance budgets {'S8x4x4-LD21-H0.3-F0.6-A4-s42': 39.22, 'S8x4x4-LD11-H0.3-F0.6-A4-s42': 26.42});种群 / Population 40;种子 / Seeds [42, 7]
- 完成运行数 / Runs finished:28;校验失败 / Validation failures:0

## 一、各格子结果(均值 ± 样本标准差) / 1. Per-cell results (mean ± sample standard deviation)

> `秒` / `评估数` / `毫秒每评价` / `停机原因` 四列并列,是同算力协议是否真的成立的证据:秒数应相近,评估数可以差数十倍,而差多少**全部**由单次评价成本解释。`停机原因 = budget` 意味着该档被预算掐停而非收敛。
>
> The four columns `seconds` / `evaluations` / `milliseconds per evaluation` / `stop reason`, side by side, are the evidence that the same-compute protocol actually holds: the seconds should be close, the evaluation counts may differ by tens of times, and the whole of that difference is explained by the cost of one evaluation. `stop reason = budget` means the arm was cut off by the budget rather than converged.

| 算例 | 档位 | n | 均值±sd | 最好 | 最差 | 极差 | 秒/次 | 评估数 | 毫秒/评价 | 停机原因 | 下界 gap 上限 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S8x4x4-LD21-H0.3-F0.6-A4-s42 | rule | 2 | 133.0 ± 0.0 | 133.0 | 133.0 | 0.0 | 0.0 |  |  |  | 0.765 |
| S8x4x4-LD21-H0.3-F0.6-A4-s42 | twostage | 2 | 70.0 ± 1.4 | 69.0 | 71.0 | 2.0 | 39.2 | 93620 | 0.42 | budget | 0.5535 |
| S8x4x4-LD21-H0.3-F0.6-A4-s42 | nofeedback | 2 | 77.0 ± 2.8 | 75.0 | 79.0 | 4.0 | 39.3 | 3860 | 10.18 | budget | 0.5938 |
| S8x4x4-LD21-H0.3-F0.6-A4-s42 | opendispatch | 2 | 71.5 ± 2.1 | 70.0 | 73.0 | 3.0 | 39.2 | 11460 | 3.42 | budget | 0.5627 |
| S8x4x4-LD21-H0.3-F0.6-A4-s42 | nostagger | 2 | 70.0 ± 4.2 | 67.0 | 73.0 | 6.0 | 39.5 | 2540 | 15.55 | budget | 0.5527 |
| S8x4x4-LD21-H0.3-F0.6-A4-s42 | closed | 2 | 67.5 ± 2.1 | 66.0 | 69.0 | 3.0 | 39.6 | 2520 | 15.71 | budget | 0.5368 |
| S8x4x4-LD21-H0.3-F0.6-A4-s42 | priced | 2 | 77.5 ± 3.5 | 75.0 | 80.0 | 5.0 | 41.3 | 500 | 82.6 | budget | 0.5964 |
| S8x4x4-LD11-H0.3-F0.6-A4-s42 | rule | 2 | 134.0 ± 0.0 | 134.0 | 134.0 | 0.0 | 0.0 |  |  |  | 0.7668 |
| S8x4x4-LD11-H0.3-F0.6-A4-s42 | twostage | 2 | 76.0 ± 2.8 | 74.0 | 78.0 | 4.0 | 26.4 | 63640 | 0.41 | budget | 0.5886 |
| S8x4x4-LD11-H0.3-F0.6-A4-s42 | nofeedback | 2 | 77.0 ± 4.2 | 74.0 | 80.0 | 6.0 | 26.6 | 2840 | 9.37 | budget | 0.5936 |
| S8x4x4-LD11-H0.3-F0.6-A4-s42 | opendispatch | 2 | 77.0 ± 5.7 | 73.0 | 81.0 | 8.0 | 26.4 | 8980 | 2.94 | budget | 0.593 |
| S8x4x4-LD11-H0.3-F0.6-A4-s42 | nostagger | 2 | 78.5 ± 2.1 | 77.0 | 80.0 | 3.0 | 26.7 | 2000 | 13.35 | budget | 0.6018 |
| S8x4x4-LD11-H0.3-F0.6-A4-s42 | closed | 2 | 77.0 ± 4.2 | 74.0 | 80.0 | 6.0 | 26.6 | 1780 | 14.94 | budget | 0.5936 |
| S8x4x4-LD11-H0.3-F0.6-A4-s42 | priced | 2 | 83.0 ± 2.8 | 81.0 | 85.0 | 4.0 | 28.3 | 400 | 70.75 | budget | 0.6233 |

### 1.1 预算体检(同算力协议自身是否成立) / 1.1 Budget check (whether the same-compute protocol itself holds)

| 算例 | 最便宜档 | 毫秒/评价 | 最贵档 | 毫秒/评价 | 成本比 |
| --- | --- | --- | --- | --- | --- |
| S8x4x4-LD21-H0.3-F0.6-A4-s42 | twostage | 0.42 | priced | 82.6 | 196.7x |
| S8x4x4-LD11-H0.3-F0.6-A4-s42 | twostage | 0.41 | priced | 70.75 | 172.6x |

**两阶段档的评价成本天然低一两个数量级**——它的第一阶段在理想运输模型下搜索(路由退化为查 t\* 表),故等挂钟时间等于给它数十倍的搜索次数。**等时间与等评估数两种口径都不中立**:前者偏向廉价代理模型的开环法,后者偏向每次评价都做真实路由的闭环法。结论必须同时给出两种口径(`--budget auto` 与 `--budget gen`)才算完整。

**The two-stage arm's evaluation cost is naturally one or two orders of magnitude lower** — its first stage searches under the ideal travel model (routing degenerates to a lookup of the t\* table), so the same wall-clock time gives it tens of times more search steps. **Neither the same-time nor the same-evaluation protocol is neutral**: the former favors the open-loop method on a cheap surrogate model, and the latter favors the closed-loop method that really routes on every evaluation. A conclusion is complete only when both protocols are reported (`--budget auto` and `--budget gen`).


## 二、集成收益(closed vs twostage,同种子配对) / 2. Integrated gain (closed vs twostage, paired on the same seed)

| 算例 | 拥堵档 | H | 两阶段 | 闭环 | 相对收益 | n | 非平局对数 | p(Wilcoxon) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S8x4x4-LD21-H0.3-F0.6-A4-s42 | high | 0.3 | 70.0 | 67.5 | 3.6% | 2 | 2 | 0.5   |
| S8x4x4-LD11-H0.3-F0.6-A4-s42 | funnel | 0.3 | 76.0 | 77.0 | -1.5% | 2 | 2 | 1.0   |

## 三、机制增益(closed 相对各消融档) / 3. Mechanism gain (closed versus each ablation arm)

| 算例 | 消融档 | 拥堵档 | H | 消融 | 闭环 | 机制增益 | 非平局对数 | p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S8x4x4-LD21-H0.3-F0.6-A4-s42 | nofeedback | high | 0.3 | 77.0 | 67.5 | 12.3% | 2 | 0.5   |
| S8x4x4-LD21-H0.3-F0.6-A4-s42 | opendispatch | high | 0.3 | 71.5 | 67.5 | 5.6% | 2 | 0.34578   |
| S8x4x4-LD21-H0.3-F0.6-A4-s42 | nostagger | high | 0.3 | 70.0 | 67.5 | 3.5% | 2 | 0.5   |
| S8x4x4-LD11-H0.3-F0.6-A4-s42 | nofeedback | funnel | 0.3 | 77.0 | 77.0 | 0.0% | 0 | 1.0   |
| S8x4x4-LD11-H0.3-F0.6-A4-s42 | opendispatch | funnel | 0.3 | 77.0 | 77.0 | -0.1% | 2 | 1.0   |
| S8x4x4-LD11-H0.3-F0.6-A4-s42 | nostagger | funnel | 0.3 | 78.5 | 77.0 | 1.9% | 1 | 1.0   |

## 四、12.3.6 三条预期的判定 / 4. Verdicts on the three predictions in 12.3.6

**预测 1(拥堵/异构越高收益越大)**:证据不足(H 取值少于 3 档);Spearman(收益, H) = None / **Prediction 1 (the gain grows with congestion/heterogeneity)**: insufficient evidence (fewer than 3 levels of H); Spearman(gain, H) = None
- 按拥堵档 / By congestion level:{'funnel': -0.0149, 'high': 0.0358}
- 按异构度 / By heterogeneity:{'0.3': 0.0104}

**预测 2(H=0 时机制失效)**:证据不足(缺 H=0 或 H>0 的格子) / **Prediction 2 (the mechanism fails at H=0)**: insufficient evidence (missing an H=0 cell or an H>0 cell)

**预测 3(high 上机制增益 > funnel 上)**:支持 / **Prediction 3 (mechanism gain on high > on funnel)**: supported

| 消融档 | high 增益 | funnel 增益 | 配对数 | 非平局对数 | p | 判定 |
| --- | --- | --- | --- | --- | --- | --- |
| nofeedback | 0.1233 | 0.0 | 2 | 2 | 0.5 | 支持 |
| opendispatch | 0.056 | -0.0007 | 2 | 2 | 0.5 | 支持 |
| nostagger | 0.0349 | 0.0195 | 2 | 2 | 1.0 | 支持 |

---

> 解读约束(规格 8.2、13.2):引用任何数字必须连同**种子数与预算模式**一并给出;非平局对数少于种子数一半时,该行差异基本落在取整噪声内。
>
> Reading constraint (spec 8.2, 13.2): any cited number must be given together with the **seed count and the budget mode**. When the number of non-tie pairs is under half the seed count, that row's difference mostly sits inside rounding noise.
