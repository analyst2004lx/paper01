# Paper figures for paper03

## Build

```powershell
cd paper03\Latex\fig
py export_data.py
py plot_all.py
.\build_tikz.ps1
```

Or: `.\build_all.ps1`

## Outputs cited in `paper03.tex`

| File | Role |
| --- | --- |
| `fig_system.pdf` | System + message loop |
| `fig_attack_tree.pdf` | P1–P4 decision tree |
| `fig_architecture.pdf` | M1–M7 pipeline |
| `fig_budget_chain.pdf` | Hazard→budget→BW |
| `fig_protocol.pdf` | Dual-deadline + heartbeat timeline |
| `fig_tier1.pdf` | Tier-1 structural zero |
| `fig_witness.pdf` | Tier-2 witness selection |
| `fig_ablation.pdf` | Coverage / ablation heatmap |
| `fig_heartbeat.pdf` | H1 equal-bandwidth latency |
| `fig_budget_bw.pdf` | Silence BW vs PBFT |
| `fig_loss_sweep.pdf` | Loss sweep |
| `fig_collusion.pdf` | Collusion $k$ histogram |
| `fig_coverage.pdf` | Oracle gap (U1) |

Sources: `tikz_*.tex` (concept), `export_data.py` + `plot_all.py` (experiments), `data/`.
