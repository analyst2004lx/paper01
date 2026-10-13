"""门控与时延在"主表协议"在线实现上的重测(对应论文局限 (4) / 未来工作 (5))。

tools.online_diag 用的 Detector 在线实现与主表判决协议不同:序贯层是 Fisher 合成后
按设备的单路 CUSUM(ARL0=1000,占一半预算),另一半预算给逐通道单消息判决,且保留
物料令牌互锁通道。本工具把在线实现改成与 baselines.judge_detail 同构:

  - 三路:硬约束层、时序、结构;去掉互锁通道(令牌账本不再计算,只保留看门狗布防)。
  - 每路预算 alpha/3:时序、结构两路各自单消息判决 p <= alpha/3。
  - 每路一个 CUSUM(c=1.5),门限 h_i 在校准折该路共形 p 值上按 ARL0_i = 3/alpha 反解,
    告警后复位。
  - 硬约束层触发即告警并丢弃消息,不进入更新。
  - 门控更新与 Detector._commit 相同(告警或隔离窗口内不更新,EWMA 0.95)。

输出:
  Q2 逐消息时延(observe 全流程,单核),与 M 扩展
  Q3 门控 / 无门控下持续 200 条 rho=0.30 提前上报的基线漂移
存档:output/online_aligned_archive.json

用法(在 paper02/slid/ 下):  py -m tools.online_aligned
"""
from __future__ import annotations

import json
import math
import os
import platform
import time

import numpy as np

from algorithm import ingest, procmodel, sequential
from algorithm.detector import (Alarm, Detector, DetectorConfig, _group,
                                _order_cases)
from tools.online_diag import _clone_faster

OUT = os.path.join("output", "online_aligned_archive.json")
PATHS = ("time", "struct")          # 统计路;硬约束层另行处理
IDX = {"time": 0, "struct": 1}


class AlignedDetector(Detector):
    """与主表判决协议同构的在线实现。"""

    def fit(self, benign, model=None, *, rng=None, temporal=True,
            frac=(0.67, 0.33)):
        super().fit(benign, model, rng=rng, temporal=temporal, frac=frac)
        by_case = _group(benign)
        keys = _order_cases(by_case, temporal=temporal, rng=rng)
        ca = [a for k in keys[int(len(keys) * frac[0]):] for a in by_case[k]]
        rows = [self._recalibrate(r, rng) for r in self._score_stream(ca, rng=rng)]
        arl0 = max(int(len(PATHS) + 1) / self.cfg.alpha, 2)
        self.h_path = {ch: sequential.calibrate_h([r[IDX[ch]] for r in rows],
                                                  int(arl0), k=self.cfg.cusum_k)
                       for ch in PATHS}
        self.n_cal = len(rows)
        self._reset_online()
        return self

    def _alpha_path(self) -> float:
        return self.cfg.alpha / (len(PATHS) + 1)

    def _token_check(self, act) -> bool:
        self._arm_watchdog(act)
        return False

    def observe(self, act, *, rng=None, now=None):
        self._n_seen += 1
        self._flush_pending(act.t_consume)
        hard = self._hard_layer(act)
        if hard is not None:
            self.stats["hard"] += 1
            self._quarantine = self.cfg.quarantine
            return [hard]
        p = self._recalibrate(self._score_one(act, rng=rng), rng)
        alarms = []
        a_i = self._alpha_path()
        for ch in PATHS:
            v = p[IDX[ch]]
            if v <= a_i:
                alarms.append(Alarm(act.t_consume, act.device, act.case,
                                    "channel", ch, v, f"{ch} p={v:.4g}"))
            det = self._seq.setdefault(
                ch, sequential.CUSUM(k=self.cfg.cusum_k, h=self.h_path[ch]))
            if det.update(v):
                alarms.append(Alarm(act.t_consume, act.device, act.case,
                                    "sequential", ch, det.s, f"{ch} CUSUM"))
                det.reset()
        self._commit(act, alarms, p)
        return alarms


def _load():
    raw = ingest.read_xes(ingest.default_log_path())
    live = ingest.valid(raw, drop_failure=True)
    log_pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(procmodel.default_bpmn_glob(), log_positions=log_pos)
    return live, model


def build(live, model, seed: int = 0):
    """与 tools.online_diag.build(temporal=True) 同一切分(按 case 时间序 75/25)。"""
    rng = np.random.default_rng(seed)
    by_case = _group(live)
    keys = _order_cases(by_case, temporal=True)
    cut = int(len(keys) * 0.75)
    det = AlignedDetector(DetectorConfig(alpha=0.01)).fit(
        [a for k in keys[:cut] for a in by_case[k]], model=model, rng=rng,
        temporal=True)
    test = [a for k in keys[cut:] for a in by_case[k]]
    return det, test, rng


def latency(det, test, rng, reps=3):
    prev = det.cfg.online_update
    det.cfg.online_update = False
    stream = sorted((x for x in test if x.t_consume is not None),
                    key=lambda x: (x.t_consume, x.order))
    per = []
    for _ in range(reps):
        det._reset_online()
        for a in stream:
            t0 = time.perf_counter()
            det.observe(a, rng=rng)
            per.append((time.perf_counter() - t0) * 1e6)
    det._reset_online()
    det.cfg.online_update = prev
    return np.array(per)


def scale_m(det, test, rng, ms=(1, 10, 50, 100)):
    import copy
    base = sorted((x for x in test if x.t_consume is not None),
                  key=lambda x: (x.t_consume, x.order))[:80]
    orig = dict(det.timing)
    prev = det.cfg.online_update
    det.cfg.online_update = False
    out = []
    for M in ms:
        extra, stream = {}, []
        for m in range(M):
            for a in base:
                b = copy.copy(a)
                if m:
                    b.device = f"{a.device}#m{m}"
                    mdl = orig.get((a.device, a.op))
                    if mdl is not None:
                        extra[(b.device, a.op)] = mdl
                stream.append(b)
        stream.sort(key=lambda x: (x.t_consume, x.order, x.device))
        det.timing = {**orig, **extra}
        det._reset_online()
        per = []
        for a in stream:
            t0 = time.perf_counter()
            det.observe(a, rng=rng)
            per.append((time.perf_counter() - t0) * 1e6)
        out.append({"M": M, "median_us": float(np.median(per)), "n_msg": len(stream)})
        det._reset_online()
        det.timing = orig
    det.cfg.online_update = prev
    return out


def poisoning(live, model, seed=0, rho=0.30, n_inject=200):
    out = {}
    for gated in (True, False):
        det, test, rng = build(live, model, seed=seed)
        det.cfg.online_update = True
        det.cfg.gated_update = gated
        key = max((k for k, m in det.timing.items() if m.informative),
                  key=lambda k: det.timing[k].n)
        m = det.timing[key]
        route = max(m.route_effect, key=lambda r: 1)
        before = m.route_effect[route]
        victims = [a for a in test if (a.device, a.op) == key and a.duration_s]
        det._reset_online()
        for i in range(n_inject):
            det.observe(_clone_faster(victims[i % len(victims)], rho), rng=rng)
        after = det.timing[key].route_effect[route]
        out["gated" if gated else "ungated"] = {
            "group": f"{key[0]}/{key[1]}", "loc_before": before, "loc_after": after,
            "drift": after - before, "absorbed_advance": 1 - math.exp(after - before),
            "update_applied": int(det.stats["update_applied"]),
            "update_blocked": int(det.stats["update_blocked"]),
            "n_inject": n_inject, "rho": rho}
    return out


def main() -> int:
    live, model = _load()
    det, test, rng = build(live, model, seed=0)
    print(f"h_path={det.h_path}  n_cal={det.n_cal}  ARL0_i={int(3 / 0.01)}")
    us = latency(det, test, rng)
    sc = scale_m(det, test, rng)
    print(f"Q2 median {np.median(us):.1f} us  p95 {np.percentile(us, 95):.1f}"
          f"  p99 {np.percentile(us, 99):.1f}  n={len(us)}")
    for r in sc:
        print(f"   M={r['M']:<4} median {r['median_us']:.1f} us")
    pois = poisoning(live, model)
    for k, r in pois.items():
        print(f"Q3 {k:<8} {r['group']:<28} drift {r['drift']:+.4f} "
              f"absorbed {r['absorbed_advance']:+.1%} "
              f"applied {r['update_applied']} blocked {r['update_blocked']}")
    doc = {"protocol": {"paths": ["hard"] + list(PATHS), "interlock": False,
                        "alpha": 0.01, "alpha_path": 0.01 / 3, "arl0_path": 300,
                        "cusum_k": det.cfg.cusum_k, "h_path": det.h_path,
                        "n_cal": det.n_cal, "ewma": det.cfg.ewma,
                        "quarantine": det.cfg.quarantine,
                        "split": "temporal 75/25 by case, seed 0"},
           "env": {"python": platform.python_version(), "cpu": platform.processor()},
           "latency_us": [float(x) for x in us],
           "median_us": float(np.median(us)),
           "p95_us": float(np.percentile(us, 95)),
           "p99_us": float(np.percentile(us, 99)),
           "scale": sc, "poisoning": pois}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print("written", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
