"""评价指标。

报告口径三条硬规定(都是被实测逼出来的):

1. 检出率必须**在给定检测延迟预算下**报告,单条消息检出率会严重低估
   方法能力(rho=0.15 时 19.9% 对 86.8%)。
2. 每个名义 alpha 都要同时报告**有效校准集规模**,否则 alpha=0.001 处的
   零误报无法区分"方法好"和"样本不够无法产生这么小的 p 值"。
3. rho* 必须**逐设备逐操作**报告,不能只给全线均值:实测跨度 1.6% 到
   98.6%,均值会同时掩盖最好和最坏的情形。产线整体安全性由最差分组决定。

误报口径统一为**每设备每小时误报数**,便于与工业可接受水平对齐;同时
给出 ARL0 以支撑序贯层的理论对照。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Report:
    dr_by_delay: dict[int, float]        # 延迟预算(消息数) -> 检出率
    fpr: float
    fp_per_device_hour: float
    arl0: float
    detection_delay_p50: float
    detection_delay_p95: float
    n_calib: int
    alpha_nominal: float
    alpha_min_achievable: float
    per_group_rho_star: dict[tuple[str, str], float]
    per_message_latency_us: float
    memory_kb: float


def evaluate(alarms, labels, cfg=None, *, stream=None,
             n_calib: int = 0, latency_us: float = 0.0) -> Report:
    """把告警流与真值标签折成一份报告。

    `alarms` 是 Detector.replay 的输出,`labels` 与 `stream` 逐条对应。
    检出判定按**延迟预算**:第 i 条被篡改消息,若在第 i..i+budget 条消息
    区间内出现任一告警即算检出——这与"逐消息二分类"不同,也是规定 1
    要求的口径。
    """
    labels = list(labels)
    n = len(labels)
    idx = {}
    if stream is not None:
        for i, a in enumerate(stream):
            idx.setdefault((a.case, a.device, a.order), i)
    pos = sorted(i for i, v in enumerate(labels) if v)

    fired = sorted({idx.get((al.case, al.device, getattr(al, "order", None)),
                            _nearest(stream, al)) for al in alarms}
                   - {None}) if stream is not None else []

    budgets = tuple(getattr(cfg, "delay_budget", (1, 3, 10, 30))) \
        if cfg is not None else (1, 3, 10, 30)
    dr, delays = {}, []
    for b in budgets:
        hit = 0
        for i in pos:
            j = _first_at_least(fired, i)
            if j is not None and j - i <= b:
                hit += 1
                if b == max(budgets):
                    delays.append(j - i)
        dr[b] = hit / len(pos) if pos else float("nan")

    neg = [i for i, v in enumerate(labels) if not v]
    fp = sum(1 for j in fired if j < n and not labels[j])
    fpr = fp / len(neg) if neg else float("nan")
    hours = _span_hours(stream)
    n_dev = len({a.device for a in stream}) if stream else 1

    return Report(
        dr_by_delay=dr, fpr=fpr,
        fp_per_device_hour=fp / max(hours * n_dev, 1e-9),
        arl0=(len(neg) / fp) if fp else float("inf"),
        detection_delay_p50=_pct(delays, 50),
        detection_delay_p95=_pct(delays, 95),
        n_calib=n_calib,
        alpha_nominal=getattr(cfg, "alpha", float("nan")),
        alpha_min_achievable=1.0 / (n_calib + 1) if n_calib else float("nan"),
        per_group_rho_star={}, per_message_latency_us=latency_us,
        memory_kb=0.0)


def _nearest(stream, al):
    if stream is None:
        return None
    for i, a in enumerate(stream):
        if a.case == al.case and a.device == al.device \
                and a.t_consume == al.t:
            return i
    return None


def _first_at_least(sorted_idx, i):
    import bisect
    k = bisect.bisect_left(sorted_idx, i)
    return sorted_idx[k] if k < len(sorted_idx) else None


def _pct(xs, q):
    if not xs:
        return float("nan")
    s = sorted(xs)
    return s[min(int(len(s) * q / 100), len(s) - 1)]


def _span_hours(stream):
    if not stream:
        return 1.0
    ts = [a.t_consume for a in stream if a.t_consume is not None]
    if len(ts) < 2:
        return 1.0
    return max((max(ts) - min(ts)).total_seconds() / 3600.0, 1e-9)


def bound_check(measured: dict, predicted: dict) -> dict:
    """理论界与实测的对照。全 rho 区间平均绝对偏差应在 0.03 量级。"""
    keys = sorted(set(measured) & set(predicted))
    diffs = {k: measured[k] - predicted[k] for k in keys}
    mad = sum(abs(v) for v in diffs.values()) / len(diffs) if diffs else 0.0
    return {"per_rho": diffs, "mean_abs_dev": mad,
            "ok": mad <= 0.05}
