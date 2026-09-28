# 外部来源布局批次(Lyu 附录 A 拓扑) / Externally sourced layout batch (Lyu Appendix A topology)

算例与主批次只差布局来源;边权为本文补齐的等权值,**不可**与 Lyu 或 van Os 的参照值比较。

Instances differ from the main batch only in layout source; edge weights are the equal weights filled in by this paper, and **must not** be compared with reference values from Lyu or van Os.

## E1 任务图漏报 / E1 task-graph missed detection

| 算例 / instance | n | C1 通过 / C1 pass | 均值 \|Cl\| / mean \|Cl\| | 均值种子 / mean seeds | Cl/\|R\| 中位 / median Cl/\|R\| | 结构泄漏 / structural leak |
|---|---:|---:|---:|---:|---:|---:|
| `LyuL2_4m` | 10 | 10/10 | 70.8 | 10.5 | 0.547 | 0 |
| `LyuL3_5m` | 10 | 10/10 | 48.5 | 9.3 | 0.438 | 0 |
| `LyuL4_6m` | 10 | 10/10 | 75.4 | 11.3 | 0.505 | 0 |
| `LyuL5_7m` | 10 | 10/10 | 91.1 | 11.0 | 0.523 | 0 |
| `LyuL6_8m` | 10 | 10/10 | 73.1 | 10.8 | 0.512 | 0 |

## E2 包含性 / E2 containment

| 算例 / instance | E2a | E2b | 可行 / feasible |
|---|---:|---:|---:|
| `LyuL2_4m` | 10/10 | 10/10 | 10/10 |
| `LyuL3_5m` | 10/10 | 10/10 | 10/10 |
| `LyuL4_6m` | 10/10 | 10/10 | 10/10 |
| `LyuL5_7m` | 10/10 | 10/10 | 10/10 |
| `LyuL6_8m` | 10/10 | 10/10 | 10/10 |

## E3 边界消融(关闭扩域) / E3 boundary ablation (scope expansion off)

| 算例 / instance | B 类漏报 / class-B missed detection | R1 可行 / R1 feasible | R2 可行 / R2 feasible |
|---|---:|---:|---:|
| `LyuL2_4m` | 10/10 | 0/10 | 10/10 |
| `LyuL3_5m` | 10/10 | 0/10 | 10/10 |
| `LyuL4_6m` | 10/10 | 0/10 | 10/10 |
| `LyuL5_7m` | 10/10 | 0/10 | 10/10 |
| `LyuL6_8m` | 10/10 | 0/10 | 10/10 |

## E4 结构(封死 LU 割走廊到视界末端) / E4 structure (seal the LU-cut corridors through the horizon)

两组算例逐参数同口径,只差布局来源。

The two instance groups use the same parameter protocol and differ only in layout source.

| 来源 / source | 算例 / instance | 机器 / machines | 节点 / nodes | 走廊 / corridors | LU割 / LU cut | 远端割 / far cut | 漏斗占比 / funnel share | 每节点走廊 / corridors per node | Cl/\|R\| 中位 / median Cl/\|R\| | Cl/活 中位 / median Cl/alive |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 外部 / external | `LyuL2_4m` | 4 | 16 | 23 | 2 | 2 | 0.0 | 1.4375 | 0.512 | 0.847 |
| 外部 / external | `LyuL3_5m` | 5 | 16 | 23 | 2 | 2 | 0.0 | 1.4375 | 0.305 | 0.500 |
| 外部 / external | `LyuL4_6m` | 6 | 25 | 38 | 2 | 2 | 0.0 | 1.52 | 0.385 | 0.629 |
| 外部 / external | `LyuL5_7m` | 7 | 25 | 38 | 2 | 2 | 0.0 | 1.52 | 0.422 | 0.648 |
| 外部 / external | `LyuL6_8m` | 8 | 25 | 38 | 2 | 2 | 0.0 | 1.52 | 0.460 | 0.754 |
| 自建 / self-built | `self_high_LD21` | 4 | 10 | 10 | 2 | 1 | 0.2857 | 1.0 | 0.497 | 0.777 |
| 自建 / self-built | `self_funnel_LD11` | 4 | 9 | 8 | 1 | 1 | 0.2857 | 0.8889 | 0.491 | 0.774 |
| 自建 / self-built | `self_mid_LD22` | 4 | 11 | 12 | 2 | 2 | 0.2857 | 1.0909 | 0.446 | 0.735 |

## E5 预算点 / E5 budget points

| 算例 / instance | 预算 s / budget s | R0+ Cmax | R2 Cmax | R2 ms | R0+ ms |
|---|---:|---:|---:|---:|---:|
| `LyuL2_4m` | 0.2 | 133.3 | 155.5 | 3.7 | 346 |
| `LyuL2_4m` | 1 | 128.7 | 155.5 | 3.7 | 1214 |
| `LyuL2_4m` | 2 | 125.7 | 155.5 | 3.7 | 2244 |
| `LyuL6_8m` | 0.2 | 144.3 | 149.0 | 4.2 | 495 |
| `LyuL6_8m` | 1 | 137.0 | 149.0 | 4.2 | 1449 |
| `LyuL6_8m` | 2 | 128.3 | 149.0 | 4.2 | 2357 |
