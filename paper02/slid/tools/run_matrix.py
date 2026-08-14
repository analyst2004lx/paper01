"""矩阵批跑器:数据集 x 攻击族 x rho x 档位 x 种子,断点续跑。

账本写 output/matrix/<preset>/records.jsonl,每条记录自带配置指纹,
重跑时跳过已完成任务;--report-only 直接用已有账本出报告。

预设:
    smoke   流程自检(1 数据集 x 2 攻击族 x 2 种子)
    main    主表(全部攻击族 x 全部基线 x 5 种子)
    sweep   rho 扫描曲线,与理论界对照
    full    完整矩阵
"""
from __future__ import annotations

PRESETS = ("smoke", "main", "sweep", "full")


def main() -> int:
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
