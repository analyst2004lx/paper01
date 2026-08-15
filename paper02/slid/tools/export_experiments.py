"""把 output/ 下的原始结果汇总成 experiments/ 里的论文级 CSV。

产出:
    main_table.csv      主对比表(方法 x 攻击族 x 指标)
    ablation.csv        递进消融链
    rho_star.csv        逐设备逐操作的 rho*
    calibration.csv     名义 alpha / 经验 FPR / 有效校准集规模
    delay.csv           检测延迟分布
    cost.csv            单消息时延与内存占用(边缘部署可行性)
    meta.json           环境指纹:提交号、随机种子、数据集校验和
"""
from __future__ import annotations


def main() -> int:
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit(main())
