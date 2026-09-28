"""矩阵批跑器:数据集 x 攻击族 x rho x 档位 x 种子,断点续跑。

账本写 output/matrix/<preset>/records.jsonl,每条记录自带配置指纹,
重跑时跳过已完成任务;--report-only 直接用已有账本出报告。

预设:
    smoke   流程自检(1 数据集 x 2 攻击族 x 2 种子)
    main    主表(全部攻击族 x 全部基线 x 5 种子)
    sweep   rho 扫描曲线,与理论界对照
    full    完整矩阵

Matrix batch runner: dataset x attack family x rho x tier x seed, with resume.

The ledger is written to output/matrix/<preset>/records.jsonl. Each record carries a configuration fingerprint, and completed tasks are skipped on rerun; --report-only reports from the existing ledger.

Presets:
    smoke   pipeline self-check (1 dataset x 2 attack families x 2 seeds)
    main    main table (all attack families x all baselines x 5 seeds)
    sweep   rho sweep curve, compared with the theoretical bound
    full    full matrix
"""
from __future__ import annotations

PRESETS = ("smoke", "main", "sweep", "full")


def main() -> int:
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
