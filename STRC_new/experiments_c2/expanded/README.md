# Expanded experiment matrix

Batch entry: `py -m tools.expand_batch --seeds 42,7,2024,99,123 --budget-sec 2`

| File | Content |
| --- | --- |
| `e1_miss.csv` | 3 instances × 5 seeds |
| `e2_containment.csv` | structural + outside-field checks |
| `e3_boundary.csv` | R1 vs R2, no scope expand |
| `scale_compare.csv` | φ sweep, STRC(+expand) vs R0+@2s |
| `e5_cross_curve.csv` | budget sweep (3 seeds × 2 instances) |
| `summary.md` | aggregated tables |

Paper figures read these CSVs via `paper04/figures/fig_strc_*.py`.
