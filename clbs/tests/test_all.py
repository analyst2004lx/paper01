"""规格文档第九节 T1–T8 测试断言。运行方式(clbs/ 目录下): py -m tests.test_all"""
from __future__ import annotations

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm.instance import load_instance, parse_instance
from algorithm.network import Network
from algorithm.decoder import decode
from algorithm.ga import GAConfig, run_ga, random_ma, random_os
from algorithm.validator import validate

HERE = os.path.dirname(os.path.abspath(__file__))
INSTANCE_PATH = os.path.join(HERE, "..", "input", "example_3x3x2.json")


def _load():
    inst = load_instance(INSTANCE_PATH)
    net = Network(inst.nodes, inst.corridors, inst.lu_node)
    return inst, net


def _base_os(inst):
    """一个固定的实工序 OS(不含伪工序)。"""
    return [1, 1, 1, 2, 2, 3, 3]


# ---------------- T1 理想最短路矩阵 ----------------

def t1_ideal_dist():
    _inst, net = _load()
    d = net.ideal_dist
    expected = {("v0", "r1"): 4, ("v0", "r2"): 7, ("v0", "r3"): 7,
                ("r1", "r2"): 6, ("r1", "r3"): 6, ("r2", "r3"): 4}
    for (a, b), v in expected.items():
        assert d[a][b] == v, f"t*({a},{b}) = {d[a][b]},期望 {v}"
        assert d[b][a] == v, f"t* 不对称: ({b},{a})"


# ---------------- T2 建模文档参考方案(makespan=51)通过校验 ----------------

def _reference_timetable():
    """建模文档第七节的可行方案完整时刻表(人工推演,已消解全部冲突)。"""
    ops = [
        (1, 1, 1, 4, 8), (1, 2, 2, 18, 23), (1, 3, 3, 27, 32),
        (2, 1, 2, 9, 13), (2, 2, 3, 17, 23),
        (3, 1, 1, 12, 15), (3, 2, 2, 30, 34),
    ]
    # (agv, u, v, enter, exit, task);伪工序编号 = n(j)+1
    segs = [
        # AGV1
        (1, "v0", "c1", 0, 2, "J1-1-loaded"), (1, "c1", "r1", 2, 4, "J1-1-loaded"),
        (1, "r1", "c1", 4, 6, "J3-1-empty"), (1, "c1", "v0", 6, 8, "J3-1-empty"),
        (1, "v0", "c1", 8, 10, "J3-1-loaded"), (1, "c1", "r1", 10, 12, "J3-1-loaded"),
        (1, "r1", "c2", 12, 16, "J1-2-loaded"), (1, "c2", "r2", 16, 18, "J1-2-loaded"),
        (1, "r2", "c2", 18, 20, "J3-2-empty"), (1, "c2", "r1", 20, 24, "J3-2-empty"),
        (1, "r1", "c2", 24, 28, "J3-2-loaded"), (1, "c2", "r2", 28, 30, "J3-2-loaded"),
        (1, "r2", "c2", 34, 36, "J3-3-loaded"), (1, "c2", "c1", 36, 39, "J3-3-loaded"),
        (1, "c1", "v0", 39, 41, "J3-3-loaded"),
        # AGV2
        (2, "v0", "c1", 2, 4, "J2-1-loaded"), (2, "c1", "c2", 4, 7, "J2-1-loaded"),
        (2, "c2", "r2", 7, 9, "J2-1-loaded"),
        (2, "r2", "c2", 13, 15, "J2-2-loaded"), (2, "c2", "r3", 15, 17, "J2-2-loaded"),
        (2, "r3", "c2", 19, 21, "J1-3-empty"), (2, "c2", "r2", 21, 23, "J1-3-empty"),
        (2, "r2", "c2", 23, 25, "J1-3-loaded"), (2, "c2", "r3", 25, 27, "J1-3-loaded"),
        (2, "r3", "c2", 27, 29, "J2-3-loaded"), (2, "c2", "c1", 29, 32, "J2-3-loaded"),
        (2, "c1", "v0", 32, 34, "J2-3-loaded"),
        (2, "v0", "c1", 34, 36, "J1-4-empty"), (2, "c1", "c2", 39, 42, "J1-4-empty"),
        (2, "c2", "r3", 42, 44, "J1-4-empty"),
        (2, "r3", "c2", 44, 46, "J1-4-loaded"), (2, "c2", "c1", 46, 49, "J1-4-loaded"),
        (2, "c1", "v0", 49, 51, "J1-4-loaded"),
    ]
    return {
        "instance": "example_3x3x2", "delta_return": 1, "makespan": 51.0,
        "operations": [{"job": j, "i": i, "machine": m, "start": float(s), "finish": float(f)}
                       for j, i, m, s, f in ops],
        "returns": [{"job": 2, "complete": 34.0}, {"job": 3, "complete": 41.0},
                    {"job": 1, "complete": 51.0}],
        "agv_segments": [{"agv": a, "u": u, "v": v, "enter": float(e), "exit": float(x),
                          "task": t} for a, u, v, e, x, t in segs],
    }


def t2_reference_plan_valid():
    inst, _net = _load()
    errors = validate(inst, _reference_timetable())
    assert not errors, "参考方案未通过校验:\n" + "\n".join(errors)


# ---------------- T3 任意染色体解码可行(三重保证) ----------------

def t3_random_chromosomes_feasible():
    inst, net = _load()
    rng = random.Random(0)
    for it in range(1000):
        ma = random_ma(inst, rng)
        os_seq = random_os(inst, rng)
        result = decode(inst, net, ma, os_seq, conflict_free=True)
        assert result.makespan < float("inf")
        errors = validate(inst, result.to_timetable())
        assert not errors, f"第 {it} 个随机染色体不可行:\n" + "\n".join(errors)


# ---------------- T4 解码确定性 ----------------

def t4_decode_deterministic():
    inst, net = _load()
    rng = random.Random(7)
    ma, os_seq = random_ma(inst, rng), random_os(inst, rng)
    r1 = decode(inst, net, ma, os_seq, conflict_free=True)
    r2 = decode(inst, net, ma, os_seq, conflict_free=True)
    assert json.dumps(r1.to_timetable(), sort_keys=True) == \
           json.dumps(r2.to_timetable(), sort_keys=True), "同一染色体两次解码结果不一致"


# ---------------- T5 同机连续工序无运输任务(C4) ----------------

def t5_same_machine_no_transport():
    inst, net = _load()
    ma = {(1, 1): 1, (1, 2): 1, (1, 3): 1,
          (2, 1): 3, (2, 2): 3, (3, 1): 2, (3, 2): 2}
    os_seq = [1, 1, 1, 2, 2, 3, 3, 1, 2, 3]
    result = decode(inst, net, ma, os_seq, conflict_free=True)
    for j in (1, 2, 3):
        n = sum(1 for tr in result.transports if tr.job == j)
        assert n == 2, f"工件 {j} 应只有 2 个运输任务(首道送达+成品回运),实际 {n}"
    assert not validate(inst, result.to_timetable())


# ---------------- T6 回运开关 δ_return ----------------

def t6_delta_return_switch():
    inst1, net1 = _load()
    with open(INSTANCE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["delta_return"] = 0
    inst0 = parse_instance(data)
    net0 = Network(inst0.nodes, inst0.corridors, inst0.lu_node)

    ma = {(1, 1): 1, (1, 2): 2, (1, 3): 3, (2, 1): 2, (2, 2): 3,
          (3, 1): 1, (3, 2): 2}
    os_base = _base_os(inst1)
    r1 = decode(inst1, net1, ma, os_base + [1, 2, 3], conflict_free=True)
    r0 = decode(inst0, net0, ma, os_base, conflict_free=True)
    assert r1.makespan >= r0.makespan - 1e-9, "计回运的 C_max 不应更小"
    real_max = max(rec.finish for rec in r1.ops.values() if not rec.pseudo)
    assert abs(r0.makespan - real_max) < 1e-9, \
        "δ=0 的 C_max 应等于 δ=1 同方案的最大实工序完工时刻"
    assert not validate(inst0, r0.to_timetable())


# ---------------- T7 冲突消解:两车抢同一走廊,后到者让行 ----------------

def t7_conflict_resolution():
    inst, net = _load()
    ma = {(1, 1): 1, (3, 1): 1, (1, 2): 2, (1, 3): 3,
          (2, 1): 2, (2, 2): 3, (3, 2): 2}
    os_seq = [1, 3, 1, 1, 2, 2, 3, 1, 2, 3]  # J1、J3 首道相继从 v0 发往 r1
    result = decode(inst, net, ma, os_seq, conflict_free=True)
    tr = next(t for t in result.transports if t.job == 3 and t.i == 1)
    assert tr.agv == 2, f"J3 首道应派给 AGV2,实际 AGV{tr.agv}"
    first = tr.loaded_plan.segments[0]
    assert first.enter == 2.0, f"AGV2 应等到 t=2 才进入 v0-c1,实际 {first.enter}"
    assert tr.loaded_plan.arrive == 6.0, f"AGV2 应 t=6 到达 r1,实际 {tr.loaded_plan.arrive}"
    assert tr.loaded_plan.total_wait > 0, "让行等待应被计入拥堵统计"
    assert not validate(inst, result.to_timetable())


# ---------------- T8 GA 有效性:小算例应不劣于人工参考方案(51) ----------------

def t8_ga_beats_reference():
    inst, net = _load()
    cfg = GAConfig(pop=40, max_gen=60, stall_gen=25, seed=42)
    out = run_ga(inst, net, cfg, conflict_free=True, use_ls=True)
    best = out["best_result"]
    errors = validate(inst, best.to_timetable())
    assert not errors, "GA 最优解未通过校验:\n" + "\n".join(errors)
    assert best.makespan <= 51.0 + 1e-9, \
        f"GA 最优 C_max = {best.makespan},应不劣于参考方案 51"
    print(f"      (GA 最优 C_max = {best.makespan:.1f}, {out['generations']} 代, "
          f"{out['evaluations']} 次评估)")


# ---------------- 运行器 ----------------

TESTS = [
    ("T1 理想最短路矩阵", t1_ideal_dist),
    ("T2 参考方案(makespan=51)校验", t2_reference_plan_valid),
    ("T3 1000 随机染色体可行性", t3_random_chromosomes_feasible),
    ("T4 解码确定性", t4_decode_deterministic),
    ("T5 同机连续工序免运输", t5_same_machine_no_transport),
    ("T6 回运开关 δ_return", t6_delta_return_switch),
    ("T7 走廊冲突消解与让行", t7_conflict_resolution),
    ("T8 GA 有效性(<=51)", t8_ga_beats_reference),
]


def main() -> int:
    failed = 0
    for name, fn in TESTS:
        try:
            fn()
            print(f"[PASS] {name}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"[FAIL] {name}: {e}")
    print(f"\n{len(TESTS) - failed}/{len(TESTS)} 通过")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
