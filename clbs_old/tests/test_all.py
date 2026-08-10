"""规格文档第九节 T1–T14 测试断言。运行方式(clbs/ 目录下): py -m tests.test_all"""
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
from algorithm.generator import (CONGESTION_PRESETS, build_instance, make_spec,
                                 measure)
from algorithm.pricing import default_bucket_width
from algorithm.report import corridor_occupancy
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


# ---------------- T9 禁派集:被禁车辆不得承接,且全禁时仍可解码 ----------------

def t9_forbid_vehicles():
    inst, net = _load()
    ma = {(1, 1): 1, (3, 1): 1, (1, 2): 2, (1, 3): 3,
          (2, 1): 2, (2, 2): 3, (3, 2): 2}
    os_seq = [1, 3, 1, 1, 2, 2, 3, 1, 2, 3]

    base = decode(inst, net, ma, os_seq, conflict_free=True)
    tr0 = next(t for t in base.transports if t.job == 3 and t.i == 1)
    assert tr0.agv == 2, f"基线下 J3 首道应派给 AGV2,实际 AGV{tr0.agv}"

    # 禁掉 AGV2 后,该任务必须换车,且方案仍可行
    res = decode(inst, net, ma, os_seq, conflict_free=True, forbid={(3, 1): {2}})
    tr = next(t for t in res.transports if t.job == 3 and t.i == 1)
    assert tr.agv != 2, "禁派集未生效:AGV2 仍承接了 (3,1)"
    errors = validate(inst, res.to_timetable())
    assert not errors, "禁派后方案不可行:\n" + "\n".join(errors)

    # 全禁则回退到完整车队(保可解码性),不得抛异常或产生无限完工时间
    res_all = decode(inst, net, ma, os_seq, conflict_free=True,
                     forbid={(3, 1): {1, 2}})
    assert res_all.makespan < float("inf"), "全禁时应回退到完整车队"
    assert not validate(inst, res_all.to_timetable())


# ---------------- T10 占用率两套算法一致(顺带验预约表回滚无残留) ----------------

def t10_occupancy_consistency():
    inst, net = _load()
    delta = default_bucket_width(inst)
    ma = {(1, 1): 1, (3, 1): 1, (1, 2): 2, (1, 3): 3,
          (2, 1): 2, (2, 2): 3, (3, 2): 2}
    os_seq = [1, 3, 1, 1, 2, 2, 3, 1, 2, 3]
    # dispatch=exact 会做试探性落表再回滚;若回滚有残留,预约表侧会多出占用
    res = decode(inst, net, ma, os_seq, conflict_free=True, dispatch="exact",
                 bucket_width=delta, collect_occupancy=True)
    assert res.occupancy, "collect_occupancy=True 时应采集到占用率"

    from_table = res.occupancy                                  # 预约表侧
    from_tt = corridor_occupancy(res.to_timetable(), delta)      # 时刻表侧(独立重算)
    assert set(from_table) == set(from_tt), (
        f"占用槽位不一致: 仅预约表 {set(from_table) - set(from_tt)}, "
        f"仅时刻表 {set(from_tt) - set(from_table)}(疑似回滚残留)")
    for key, v in from_table.items():
        assert abs(v - from_tt[key]) < 1e-9, \
            f"槽位 {key} 占用率不一致: 预约表 {v} vs 时刻表 {from_tt[key]}"
    assert all(0.0 - 1e-9 <= v <= 1.0 + 1e-9 for v in from_tt.values()), \
        "独占语义下占用率不应超过 1"


# ---------------- T11 生成算例可解码、下界合法、H=0 退化 ----------------

def t11_generated_instances():
    rng = random.Random(0)
    for tag in sorted(CONGESTION_PRESETS):
        for h in (0.0, 0.3):
            spec = make_spec(tag, heterogeneity=h, flexibility=0.6, num_jobs=4,
                             num_machines=4, num_agvs=3, ops_per_job=2, seed=11)
            data = build_instance(spec)
            feat = measure(data)
            gi = parse_instance(data)
            gnet = Network(gi.nodes, gi.corridors, gi.lu_node)
            gnet.check_reachability()

            if h == 0.0:
                assert feat["heterogeneity"] == 0.0, \
                    f"{tag}: H=0 应退化为零异构,实测 {feat['heterogeneity']}"
            else:
                assert abs(feat["heterogeneity"] - h) < 0.06, \
                    f"{tag}: H 目标 {h} 实测 {feat['heterogeneity']},偏差过大"

            lb = feat["lower_bound"]
            for _ in range(20):
                res = decode(gi, gnet, random_ma(gi, rng), random_os(gi, rng),
                             conflict_free=True)
                assert res.makespan < float("inf")
                errors = validate(gi, res.to_timetable())
                assert not errors, f"{tag} 生成算例不可行:\n" + "\n".join(errors)
                # 下界必须真的是下界,否则 (a) 界推导错 或 (b) 解码违反了某条约束
                assert res.makespan >= lb - 1e-6, \
                    f"{tag}: C_max {res.makespan} 低于下界 {lb},界或解码有错"


# ---------------- T12 拥堵度旋钮只改容量:high/funnel 与 mid/high 受控对比 ----------------

def t12_congestion_knobs_isolated():
    def gen(tag):
        d = build_instance(make_spec(tag, heterogeneity=0.3, flexibility=0.6,
                                     num_jobs=6, num_machines=4, num_agvs=4,
                                     ops_per_job=3, seed=5))
        return d, measure(d)

    mid, f_mid = gen("mid")
    high, f_high = gen("high")
    funnel, f_funnel = gen("funnel")

    # high vs funnel:仅 LU 出口容量不同,其余逐字段相同
    assert high["proc_time"] == funnel["proc_time"], "high/funnel 加工时间应完全相同"
    assert high["machines"] == funnel["machines"], "high/funnel 机器位置应完全相同"
    assert abs(f_high["Tt_over_Tp"] - f_funnel["Tt_over_Tp"]) < 1e-9, \
        "high/funnel 的 Tt/Tp 应相同(容量旋钮不得改距离)"
    assert (f_high["lu_min_cut"], f_funnel["lu_min_cut"]) == (2, 1), \
        f"LU 割应为 2 vs 1,实测 {f_high['lu_min_cut']} vs {f_funnel['lu_min_cut']}"

    # mid vs high:仅中段通道数不同,LU 割相同
    assert (f_mid["far_group_cut"], f_high["far_group_cut"]) == (2, 1), \
        f"远端割应为 2 vs 1,实测 {f_mid['far_group_cut']} vs {f_high['far_group_cut']}"
    assert f_mid["lu_min_cut"] == f_high["lu_min_cut"] == 2, "mid/high 的 LU 割应相同"

    # 同种子必须逐字节可复现(F1)
    again = build_instance(make_spec("high", heterogeneity=0.3, flexibility=0.6,
                                     num_jobs=6, num_machines=4, num_agvs=4,
                                     ops_per_job=3, seed=5))
    assert json.dumps(again, sort_keys=True) == json.dumps(high, sort_keys=True), \
        "同种子生成结果不可复现"


# ---------------- T13 统计工具:与已知精确值逐位一致 ----------------

def t13_statistics():
    from algorithm.stats import describe, spearman, wilcoxon_signed_rank

    # 全部同向 5 对:零分布下 P(W+ <= 0) = 1/32,两侧 p = 0.0625
    w = wilcoxon_signed_rank([2, 3, 4, 5, 6], [1, 1, 1, 1, 1])
    assert w["method"] == "exact" and abs(w["p_value"] - 0.0625) < 1e-9, w

    # 教科书算例(与 scipy.stats.wilcoxon 一致:statistic=5, p=0.0391)
    x = [1.83, 0.50, 1.62, 2.48, 1.68, 1.88, 1.55, 3.06, 1.30]
    y = [0.878, 0.647, 0.598, 2.05, 1.06, 1.29, 1.06, 3.14, 1.29]
    w = wilcoxon_signed_rank(x, y)
    assert w["statistic"] == 5.0, w
    assert abs(w["p_value"] - 0.0390625) < 1e-4, w

    # 全平局:makespan 取整后最常见的情形,必须如实报出 n_eff=0 而非伪显著
    w = wilcoxon_signed_rank([70, 72, 70], [70, 72, 70])
    assert w["n_eff"] == 0 and w["p_value"] == 1.0 and w["method"] == "all-ties", w

    d = describe([71, 69, 80])          # 规格 13.2 的实测三种子
    assert d["range"] == 11 and abs(d["mean"] - 73.333) < 1e-3, d
    assert spearman([1, 2, 3, 4], [2, 4, 6, 9]) > 0.999
    assert spearman([1, 1, 1], [1, 2, 3]) is None, "无变异时应返回 None 而非 0"


# ---------------- T14 批跑基础设施:预算闸门、账本续跑、配对不错位 ----------------

def t14_batch_infrastructure():
    import shutil
    import tempfile
    from tools.run_matrix import Ledger, _check_p3

    inst, net = _load()

    # (1) 时间预算必须真的掐停:早停与代数上限都放开,只能由预算终止
    cfg = GAConfig(pop=30, max_gen=10 ** 9, stall_gen=10 ** 9, seed=42,
                   time_budget_sec=1.0)
    out = run_ga(inst, net, cfg, conflict_free=True, use_ls=True)
    assert out["stopped_by"] == "budget", f"应由预算终止,实际 {out['stopped_by']}"
    assert 1.0 <= out["runtime_sec"] <= 6.0, f"预算 1s 却用了 {out['runtime_sec']}s"
    assert not validate(inst, out["best_result"].to_timetable())

    # 不给预算时行为不变(向后兼容:stopped_by 只能是 stall / max_gen)
    out2 = run_ga(inst, net, GAConfig(pop=20, max_gen=3, stall_gen=99, seed=42),
                  conflict_free=True, use_ls=False)
    assert out2["stopped_by"] == "max_gen", out2["stopped_by"]

    # (2) 账本:追加即落盘,重新打开后能识别已完成项(续跑的唯一依据)
    tmp = tempfile.mkdtemp(prefix="clbs_ledger_")
    try:
        led = Ledger(tmp)
        led.append({"kind": "result", "instance": "I", "arm": "closed", "seed": 42,
                    "makespan": 50.0, "valid": True})
        led.append({"kind": "budget", "instance": "I", "budget_sec": 12.5})
        again = Ledger(tmp)
        assert again.done_keys() == {("I", "closed", 42)}, again.done_keys()
        assert again.budgets()["I"]["budget_sec"] == 12.5
        assert len(again.results()) == 1, "budget 记录不得混入结果集"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # (3) high/funnel 配对:high 侧多一个 funnel 没有的种子(seed=3,且其增益极大)。
    #     只有按 (H, 种子) 取交集才会把它排除;若按列表顺序拼接,它会被算进均值。
    cells = {
        ("HI", "closed"): {42: 80.0, 7: 90.0, 3: 100.0},
        ("HI", "nofeedback"): {42: 88.0, 7: 99.0, 3: 200.0},
        ("FU", "closed"): {42: 80.0, 7: 90.0},
        ("FU", "nofeedback"): {42: 82.0, 7: 90.0},
    }
    feat = {"HI": {"congestion_tag": "high", "target_heterogeneity": 0.3},
            "FU": {"congestion_tag": "funnel", "target_heterogeneity": 0.3}}

    class _A:
        arms = ["closed", "nofeedback"]

    d = _check_p3(cells, feat, _A())["by_mechanism"]["nofeedback"]
    assert d["n_pairs"] == 2, f"只有 seed 42/7 可配对,实际 {d['n_pairs']}"
    assert abs(d["high_mean_gain"] - 8.0 / 88.0) < 1e-4, \
        f"high 侧均值 {d['high_mean_gain']} 疑似混入了未配对的 seed=3"
    assert abs(d["funnel_mean_gain"] - (2.0 / 82.0) / 2) < 1e-4, d
    assert d["verdict"] == "支持", d


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
    ("T9 禁派集生效与兜底", t9_forbid_vehicles),
    ("T10 占用率一致性与回滚无残留", t10_occupancy_consistency),
    ("T11 生成算例可行性与下界合法性", t11_generated_instances),
    ("T12 拥堵度旋钮受控性与可复现", t12_congestion_knobs_isolated),
    ("T13 统计工具(精确 Wilcoxon / 平局 / 秩相关)", t13_statistics),
    ("T14 批跑基础设施(预算闸门/账本续跑/配对不错位)", t14_batch_infrastructure),
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
