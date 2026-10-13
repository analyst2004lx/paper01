"""tab:repro 中 B2 近似方向的检验(评审 P13)。

B2 的站内联合分布按朴素分解 P(op) prod P(v|op)。原文的站内结构是学出来的,任何学到的
结构都介于朴素分解与饱和联合 P(op, start, end, outcome) 之间。本工具在主表同一协议
(baselines.judge_detail,测试折未注入流作参照,alpha=0.01,注入率 20%,rho=0.30,
三个注入种子,延迟预算 10 条,扣偶然告警基线)下比较两端:

  naive      现行 B2(应复现 tab:e1 的 B2 列)
  saturated  站内饱和联合分布(Dirichlet 平滑,alpha=0.5)

若 saturated 在各攻击族上不高于 naive,则"朴素近似不会压低 B2"在本日志上有实测依据。
输出:output/repro_direction.json

用法(在 paper02/slid/ 下):  py -m tools.repro_direction
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from algorithm import baselines, ingest, procmodel
from algorithm.baselines import EPS, TABOR, BUTLA, order_stream
from algorithm.detector import Detector, DetectorConfig
from tools.baseline_diag import FAMILIES, attack_stream, split

OUT = os.path.join("output", "repro_direction.json")


@dataclass
class TABORSaturated(TABOR):
    """站内联合取饱和分布 P(op, start, end, outcome | stage)。"""
    p_joint: dict = field(default_factory=dict)
    n_dev: dict = field(default_factory=dict)
    k_dev: dict = field(default_factory=dict)

    def fit(self, train):
        self.auto = BUTLA(name="butla").fit(train)
        cnt = defaultdict(lambda: defaultdict(float))
        for a in order_stream(train):
            cnt[a.device][(a.op,) + tuple(getattr(a, v) for v in self.VARS)] += 1.0
        self.p_joint = {d: dict(m) for d, m in cnt.items()}
        self.n_dev = {d: sum(m.values()) for d, m in cnt.items()}
        self.k_dev = {d: len(m) + 1 for d, m in cnt.items()}
        self.p_op = {d: True for d in cnt}
        return self

    def parts(self, act) -> tuple:
        auto = self.auto.parts(act)
        m = self.p_joint.get(act.device)
        if not m:
            return auto + (0.0,)
        key = (act.op,) + tuple(getattr(act, v) for v in self.VARS)
        tot = self.n_dev[act.device] + self.alpha * self.k_dev[act.device]
        ll = math.log(max((m.get(key, 0.0) + self.alpha) / tot, EPS))
        return auto + (-ll,)


def main() -> int:
    alpha, rate, rho, seeds = 0.01, 0.2, 0.30, 3
    raw = ingest.read_xes(ingest.default_log_path())
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(procmodel.default_bpmn_glob(), log_positions=pos)
    train, calib, test = split(live)
    benign = order_stream(test)
    det = Detector(DetectorConfig(alpha=alpha, online_update=False)).fit(
        train, model=model, rng=np.random.default_rng(0), temporal=True)

    variants = {"naive": TABOR(name="tabor").fit(train),
                "saturated": TABORSaturated(name="tabor_sat").fit(train)}
    ben = {}
    for n, m in variants.items():
        pb = m.parts_stream(benign)
        ben[n] = [[r[j] for r in pb] for j in range(len(pb[0]))]

    records = []
    for fam in FAMILIES:
        for s in range(seeds):
            stream, lab = attack_stream(test, fam, s, rate, rho, det.struct, det.model)
            st = order_stream(stream)
            idx = {id(a): i for i, a in enumerate(stream)}
            lb = [lab[idx[id(a)]] for a in st]
            for n, m in variants.items():
                pa = m.parts_stream(st)
                pa = [[r[j] for r in pa] for j in range(len(pa[0]))]
                d = baselines.judge_detail(ben[n], pa, lb, alpha=alpha).to_dict()
                records.append({"family": fam, "seed": s, "variant": n,
                                "seq_net": d["seq_net"], "seq_fpr": d["seq_fpr"]})

    summary = {}
    print(f"{'攻击':<6}{'naive':>16}{'saturated':>16}")
    for fam in FAMILIES:
        row = {}
        for n in variants:
            v = [r["seq_net"] for r in records if r["family"] == fam and r["variant"] == n]
            row[n] = {"mean": float(np.mean(v)), "sd": float(np.std(v))}
        summary[fam] = row
        print(f"{fam:<6}" + "".join(
            f"{row[n]['mean']:>10.2f}±{row[n]['sd']:.2f}" for n in variants))
    means = {n: float(np.mean([summary[f][n]["mean"] for f in FAMILIES])) for n in variants}
    print("六类均值: " + "  ".join(f"{n}={v:.3f}" for n, v in means.items()))

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"protocol": {"alpha": alpha, "rate": rate, "rho": rho,
                                "seeds": seeds, "budget": 10,
                                "reference": "uninjected test fold (main-table rule)",
                                "smoothing": 0.5},
                   "summary": summary, "family_mean": means, "runs": records},
                  f, ensure_ascii=False, indent=1)
    print("written", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
