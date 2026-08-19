"""带宽—安全裕度权衡：把 $r\\,T_{\\text{hb}}$ 接进功能安全的时间预算。

## 只接可问责沉默，不接耦合互证

`corroborate.py` 的实测逼出了一个必须遵守的限制：任务完成类判定的时延**只有
条件上界**。互证窗口必须容纳调度器自己的派发排队（本日志实测 p95 218.3 s、
max 1476.4 s），而排队本身没有上界，故 $T_{\\text{detect}}(\\text{路 1})$ 无法
无条件代入 FHI 预算。

可问责沉默不同：它判定的是设备的**状态声明**而非任务完成，与调度队列完全解耦，
$T_{\\text{detect}} = r\\,T_{\\text{hb}} + \\text{skew}$ 是**无条件**上界。因此
本模块的定理只以它为输入。`../paper03-NewIdea.md` 原文让两条路径都提供时延界，
是接错了量纲，已改。

## 预算分解

ISO 26262 把故障处理时间预算拆成检测与反应两段：

    FTTI  >=  FHI  =  T_detect + T_react

其中 FTTI（fault tolerant time interval）是从故障发生到危害发生的时间，
FHI（fault handling interval）是留给检测加反应的窗口。于是

    r * T_hb + skew  <=  FHI - T_react                         (安全约束)
    n * q(p, r, rho) * 3600 / T_hb  <=  误报预算               (可用性约束)
    B = n * L / T_hb                                            (带宽)

两条约束方向相反，这才构成一个真正的优化问题：$T_{\\text{hb}}$ 变大省带宽、
也让每小时的判决机会变少从而允许更小的 $r$，但 $r\\,T_{\\text{hb}}$ 会顶到安全
预算。最省带宽的配置总落在**其中一条约束的边界**上，哪一条边界起作用是本模块
要回答的问题——它决定论文该说"带宽受安全约束限制"还是"受丢包限制"。

## 这份数据撑不起什么，必须如实声明

Trier 日志没有 AGV、没有通信层（`../database/README.md` 第三节），故：

  - FHI 与 $T_{\\text{react}}$ 只能取标准的算例值并注明来源，不能声称实测；
  - 丢包率与突发相关系数是仿真参数，不是本产线的测量结果；
  - 距离换算（ISO 13855 的 $S = K T + C$）只在危害为**运动碰撞**时有意义。
    本文的主威胁是任务状态伪造，其危害是调度损害而非碰撞，故距离换算仅作
    **量纲示意**，用来说明同一个 $T_{\\text{detect}}$ 在运动场景下值多少米，
    不作为本文的安全论断。把它当主结论会被审稿人一眼看穿。
"""
from __future__ import annotations

from dataclasses import dataclass

from .silence import SilenceConfig, far_per_hour, min_misses

#: 约束名，用于报告"哪条边界起作用"。
SAFETY = "safety"
AVAILABILITY = "availability"
BOTH = "both"
NONE = "none"


@dataclass(frozen=True)
class SafetyBudget:
    """功能安全的时间预算。全部为**引用值**，非本数据实测。

    默认取 DLR 在 ASE 2023 给出的自动驾驶算例 FHI <= 2.43 s，反应段取
    ISO 3691-4:2023 防护场算例里的制动器响应 0.15 s 加 0.10 s 的调度侧动作
    （撤销可用性、冻结派单）。换场景必须换数并注明来源。
    """
    fhi_s: float = 2.43
    t_react_s: float = 0.25
    #: 数据来源标注。写进论文表格时逐项引用，不允许出现无来源的数。
    source: str = "FHI: DLR ASE 2023 算例; T_react: ISO 3691-4:2023 算例"

    @property
    def detect_budget_s(self) -> float:
        """留给检测的时间。$r\\,T_{hb}+\\text{skew}$ 必须落在这个数以内。"""
        return self.fhi_s - self.t_react_s

    def admits(self, cfg: SilenceConfig) -> bool:
        return cfg.detect_delay_s <= self.detect_budget_s

    @classmethod
    def from_protective_field(cls, *, v_mm_s: float = 1500.0,
                              field_mm: float = 1275.0,
                              t_react_s: float = 0.25) -> "SafetyBudget":
        """由**运动危害**反推预算：越界前必须完成检测加反应。

        这一条是实测逼出来的。照汽车领域的 FHI = 2.43 s 算，留给检测 2.18 s，
        而 1.5 m/s 的 AGV 在这段时间里走 3.26 m，是 ISO 3691-4 算例防护场
        （1.275 m）的 **256%**——车早就冲出安全包络了。可见**通用 FHI 对工厂
        AGV 太松，不能直接借用**。

        正确做法是让危害模型定预算：$\\text{FHI} = \\text{field} / v$，于是
        1.275 m / 1.5 m/s = 0.85 s，留给检测 0.60 s。论文的定理链条由此完整：
        危害模型 -> 时间预算 -> $(r, T_{hb})$ 可行区间 -> 带宽下界。四段都可核对。
        """
        return cls(fhi_s=field_mm / v_mm_s, t_react_s=t_react_s,
                   source=(f"由 ISO 3691-4 防护场 {field_mm:.0f} mm 与速度 "
                           f"{v_mm_s:.0f} mm/s 反推"))


@dataclass(frozen=True)
class Design:
    """一个可行配置。带宽只含心跳，不含交接确认。"""
    t_hb_s: float
    r_misses: int
    detect_delay_s: float
    bandwidth_bps: float
    far_per_hour: float

    @property
    def slack_s(self) -> float:
        return self.detect_delay_s

    def __str__(self) -> str:
        return (f"T_hb={self.t_hb_s:.3f}s r={self.r_misses} "
                f"T_detect={self.detect_delay_s:.3f}s "
                f"B={self.bandwidth_bps:.0f} B/s "
                f"FAR={self.far_per_hour:.3f}/h")


def feasible(budget: SafetyBudget, *, p_loss: float, n_devices: int,
             far_target_per_hour: float, burst_rho: float = 0.0,
             token_bytes: int = 16, skew_s: float = 0.01,
             grid: int = 400, t_lo: float = 0.005, t_hi: float = 10.0
             ) -> list[Design]:
    """枚举同时满足安全预算与误报预算的 $(T_{hb}, r)$，按带宽升序。

    $r$ 取该 $T_{\\text{hb}}$ 下满足误报预算的**最小值**：$r$ 再大只增时延不减
    带宽（断言 C9），故最优解一定在最小可行 $r$ 上。
    """
    out: list[Design] = []
    for i in range(grid):
        t = t_lo * (t_hi / t_lo) ** (i / (grid - 1))
        r = min_misses(p_loss, t, n_devices, far_target_per_hour,
                       burst_rho=burst_rho)
        if r is None:
            continue
        cfg = SilenceConfig(t_hb_s=t, r_misses=r, skew_s=skew_s,
                            token_bytes=token_bytes)
        if not budget.admits(cfg):
            continue
        out.append(Design(
            t_hb_s=t, r_misses=r, detect_delay_s=cfg.detect_delay_s,
            bandwidth_bps=cfg.bandwidth_bps(n_devices),
            far_per_hour=far_per_hour(p_loss, cfg, n_devices,
                                      burst_rho=burst_rho)))
    return sorted(out, key=lambda d: d.bandwidth_bps)


def cheapest(budget: SafetyBudget, **kw) -> Design | None:
    """最省带宽的可行配置。无可行解返回 None——那说明预算给不出方案，
    是有意义的结论（须调 FHI、换网络或降设备数），不该靠放宽误报预算掩盖。
    """
    xs = feasible(budget, **kw)
    return xs[0] if xs else None


def slack(d: Design, budget: SafetyBudget, far_target_per_hour: float) -> dict:
    """最优解在两条约束上各剩多少余量，按相对值报。

    只报分类标签不够：实测最优解常常**两条边界都几乎顶满**（突发口径下安全余量
    1.1%、误报余量 3.3%），说明两条约束在最优点处近乎同时起作用。把它说成
    "只受安全约束限制"会失掉一半信息。
    """
    return {
        "safety_slack": ((budget.detect_budget_s - d.detect_delay_s)
                         / budget.detect_budget_s),
        "availability_slack": ((far_target_per_hour - d.far_per_hour)
                               / far_target_per_hour),
    }


def binding_constraint(d: Design, budget: SafetyBudget, *, p_loss: float,
                       n_devices: int, far_target_per_hour: float,
                       burst_rho: float = 0.0, tol: float = 0.05
                       ) -> str:
    """判断最优解顶在哪条边界上。

    这决定论文的论断方向：顶在安全边界说明"带宽受安全约束限制"，顶在误报边界
    说明"受丢包限制"。两句话的工程含义完全不同，不能含糊其辞；两者同时顶满时
    必须说"同时"，那才是最优点的真实结构。
    """
    s = slack(d, budget, far_target_per_hour)
    at_safety = s["safety_slack"] <= tol
    at_avail = s["availability_slack"] <= tol
    if at_safety and at_avail:
        return BOTH
    if at_safety:
        return SAFETY
    if at_avail:
        return AVAILABILITY
    return NONE


def burst_premium(budget: SafetyBudget, *, p_loss: float, n_devices: int,
                  far_target_per_hour: float, burst_rho: float,
                  **kw) -> dict:
    """突发丢包容忍的**带宽代价**。这是本模块最可引用的一条定量结果。

    独立丢包口径下所需的 $r$ 较小，$T_{\\text{hb}}$ 可以放得更大、带宽更省；
    突发口径要求更大的 $r$，同一个安全预算就把 $T_{\\text{hb}}$ 压小，带宽随之
    上升。比值即"为了在成簇丢包下维持同样的误报与安全保证，要多付多少带宽"。
    """
    a = cheapest(budget, p_loss=p_loss, n_devices=n_devices,
                 far_target_per_hour=far_target_per_hour, burst_rho=0.0, **kw)
    b = cheapest(budget, p_loss=p_loss, n_devices=n_devices,
                 far_target_per_hour=far_target_per_hour,
                 burst_rho=burst_rho, **kw)
    return {
        "independent": a,
        "bursty": b,
        "premium": (b.bandwidth_bps / a.bandwidth_bps
                    if a and b and a.bandwidth_bps else None),
        "burst_rho": burst_rho,
    }


# ---- 量纲示意：把时延折算成距离（仅在危害为运动碰撞时有意义）-----------

def iso13855_distance_mm(t_detect_s: float, *, k_mm_s: float = 1600.0,
                         c_mm: float = 850.0, t_react_s: float = 0.25
                         ) -> float:
    """ISO 13855 的 $S = K\\,T + C$。

    $K$ 为接近速度（标准对人员步行取 1600 mm/s；对 AGV 取其行驶速度），
    $T$ 为系统总响应时间（此处 = 检测 + 反应），$C$ 为侵入距离补偿。

    **本文不把它作为安全论断。** 主威胁是任务状态伪造，危害是调度损害而非
    碰撞；此函数只用来回答"同一个 $T_{\\text{detect}}$ 在运动场景下值多少米"，
    是量纲示意。当作主结论会被一眼看穿。
    """
    return k_mm_s * (t_detect_s + t_react_s) + c_mm


def protective_field_mm(*, v_mm_s: float = 1500.0, t_sensor_s: float = 0.10,
                        t_brake_s: float = 0.15, brake_mm: float = 650.0,
                        margin_mm: float = 250.0) -> dict:
    """ISO 3691-4:2023 防护场算例，逐项复现以便论文引用时可核对。

    默认参数即标准算例：1.5 m/s 下扫描仪 0.10 s + 制动器 0.15 s 给出反应距离
    0.375 m，加制动距离 0.65 m 与裕度 0.25 m，得 1.275 m。
    """
    react_mm = v_mm_s * (t_sensor_s + t_brake_s)
    return {"react_mm": react_mm, "brake_mm": brake_mm,
            "margin_mm": margin_mm,
            "field_mm": react_mm + brake_mm + margin_mm}


def detection_travel_mm(t_detect_s: float, v_mm_s: float = 1500.0) -> float:
    """检测时延对应的行驶距离。用于对照防护场：若它远小于防护场，说明该时延
    在运动场景下也不构成额外的空间代价；反之则须缩短 $T_{\\text{detect}}$。
    """
    return v_mm_s * t_detect_s
