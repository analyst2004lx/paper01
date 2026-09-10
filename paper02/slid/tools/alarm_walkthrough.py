"""抽出一条 A2 硬层否决与一条 A3 时序累积的可解释走读。

产出 slid/output/alarm_walkthrough.json,供 fig_alarm*.py 作图。
用法(在 paper02/slid/ 下):  py -m tools.alarm_walkthrough
"""
from __future__ import annotations

import numpy as np

from algorithm import archive, attacks, baselines, ingest, procmodel, sequential
from algorithm.detector import Detector, DetectorConfig
from tools.baseline_diag import attack_stream, split


def _trace(det, stream, labels, *, rng, window=7):
    """按在线语义重放,记录硬层原因、时序 z、结构分数与时序 CUSUM。"""
    det._reset_online()
    cusum = sequential.CUSUM(k=1.5, h=7.8)
    rows = []
    for i, a in enumerate(stream):
        hard = det._hard_layer(a)
        raw = det._score_one(a, rng=rng)
        z = None
        m = det.timing.get((a.device, a.op))
        if m is not None and m.informative and a.duration_s:
            z = m.standardise(a.duration_s, route=a.route, planned_s=a.planned_s)
        p_t = raw[0]
        fired = cusum.update(p_t)
        s = cusum.s
        if fired:
            cusum.reset()
        rows.append({
            "i": i,
            "injected": bool(labels[i]),
            "device": a.device,
            "op": a.op,
            "case": a.case,
            "hard": None if hard is None else hard.explanation,
            "hard_ch": None if hard is None else hard.channel,
            "z": None if z is None else float(z),
            "struct": float(raw[1]),
            "S": float(s),
            "cusum_fire": bool(fired),
            "duration_s": a.duration_s,
        })
    det._reset_online()
    return rows


def _window(rows, center: int, half: int = 4):
    lo = max(0, center - half)
    hi = min(len(rows), center + half + 1)
    return rows[lo:hi]


def pick_a2(rows):
    for r in rows:
        if r["injected"] and r["hard"]:
            return _window(rows, r["i"])
    return None


def pick_a3(rows):
    for r in rows:
        if r["injected"] and r["cusum_fire"]:
            return _window(rows, r["i"])
    # 若单条未越界,取注入段里 |z| 最负且 S 最大的位置
    inj = [r for r in rows if r["injected"] and r["z"] is not None]
    if not inj:
        return None
    r = min(inj, key=lambda x: (x["z"] if x["z"] is not None else 0, -x["S"]))
    return _window(rows, r["i"])


def main() -> int:
    raw = ingest.read_xes(ingest.default_log_path())
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(procmodel.default_bpmn_glob(), log_positions=pos)
    train, calib, test = split(live)
    det = Detector(DetectorConfig(alpha=0.01, online_update=False)).fit(
        train, model=model, rng=np.random.default_rng(0), temporal=True)

    out = {"A2": None, "A3": None}
    for fam, picker in (("A2", pick_a2), ("A3", pick_a3)):
        stream, lab = attack_stream(test, fam, 0, 0.2, 0.30, det.struct, det.model)
        rows = _trace(det, stream, lab, rng=np.random.default_rng(7))
        win = picker(rows)
        if win is None:
            raise SystemExit(f"{fam} 没有可画的告警窗口")
        out[fam] = win
        print(f"=== {fam} {attacks.FAMILY_ZH[fam]} 窗口 {len(win)} 条 ===")
        for r in win:
            mark = "*" if r["injected"] else " "
            hard = (r["hard_ch"] or ".")
            z = "   na" if r["z"] is None else f"{r['z']:+5.2f}"
            print(f"  {mark} {r['i']:>4} {r['device']:<8} {r['op']:<28} "
                  f"hard={hard:<4} z={z} S={r['S']:.2f}")

    archive.dump(archive.WALK_PATH, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
