# paper01 vs paper04：扰动规模对照 / paper01 vs paper04: disturbance-scale comparison

- 算例: `congested_8x4x4` / instance: `congested_8x4x4`
- paper01: R0+ 热启动闭环 GA，预算 `2.0` s / paper01: R0+ warm-start closed-loop GA, budget `2.0` s
- paper04: STRC 时空闭包 + 第 1 级改路 + 失败扩域再修（工件后缀→同车后缀→全部未来） / paper04: STRC spatiotemporal closure + level-1 reroute + widen-and-repair on failure (job suffix → same-vehicle suffix → all future)
- 种子: [42, 7] / seeds: [42, 7]

| φ | 受扰工序 / disturbed ops | P04 可行率 / P04 feas. | P04 Cmax(均) / P04 Cmax (mean) | P04 耗时ms(均) / P04 time ms (mean) | P01 可行率 / P01 feas. | P01 Cmax(均) / P01 Cmax (mean) | P01 耗时ms(均) / P01 time ms (mean) | 耗时比 P01/P04 / time ratio P01/P04 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.10 | 2 | 100% | 207.5 | 7.6 | 100% | 106.5 | 2093 | 444× |
| 0.25 | 4 | 100% | 207.5 | 8.7 | 100% | 106.5 | 2082 | 431× |
| 0.50 | 8 | 100% | 220.5 | 5.1 | 100% | 115.5 | 2084 | 409× |
| 0.75 | 12 | 100% | 253.0 | 6.9 | 100% | 121.0 | 2048 | 298× |
| 1.00 | 14 | 100% | 294.0 | 9.3 | 100% | 154.0 | 2025 | 218× |

明细 CSV: `scale_compare.csv`

Detail CSV: `scale_compare.csv`
