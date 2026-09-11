# Paper figures for paper03

Each `fig_*.pdf` is produced by the same-name Python script.

```powershell
cd paper03\Latex\fig
# optional: refresh data/plot_data.json
py export_data.py
# conceptual
py fig_system.py
py fig_attack_tree.py
py fig_architecture.py
py fig_budget_chain.py
py fig_protocol.py
# experiments
py fig_tier1.py
py fig_witness.py
py fig_ablation.py
py fig_heartbeat.py
py fig_budget_bw.py
py fig_loss_sweep.py
py fig_collusion.py
py fig_coverage.py
# Chinese system figure (开题)
py fig_system_CN.py
```

Shared style/data helpers: `_style.py`. Data refresh: `export_data.py` → `data/`.
