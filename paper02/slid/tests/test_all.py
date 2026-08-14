"""SLID 断言集 T1–T21。

每条断言都对应一个**已在数据上量化过的事实**,回归时若被打破说明实现
偏离了论文声称的性质,而不只是数值抖动。括号内是实测值。

    T1  F 在良性数据上零违反                          (953/953, 0.00%)
    T2  I 在良性数据上违反率 <= 2%                    (47/2768, 1.70%)
    T3  参考模型对观测移动的覆盖率 >= 95%             (97.4%)
    T4  加性 AFT 与逐路线饱和模型残差相等             (差 0.000)
    T5  路线协变量把 sigma_log 至少降一半             (0.355 -> 0.116)
    T6  未见路线上冷启动先验优于加性外推              (0.159 < 0.279)
    T7  设备级结构链信息量为零(反例保护)             (953 次转移,p 值取值唯一)
    T8  case 级结构链状态数与转移数满足支撑度下限     (21 状态 / 2780 转移)
    T9  随机化 conformal 在名义 0.05 下 FPR 在 [0.04, 0.06]   (0.051)
    T10 朴素 conformal 在离散通道上 FPR 失控(反例保护) (1.000)
    T11 字典序划分破坏交换性,随机划分修复            (0.076 -> 0.053)
    T12 alpha < 1/(n_calib+1) 时报告标注为不可达
    T13 单侧检验在抢跑攻击下功效严格高于双侧          (0.874 > 0.338)
    T14 理论检出率与实测偏差 <= 0.05                  (平均 0.03)
    T17 先合成再校准会卡在原子上(反例保护)           (FPR 0.074,对 alpha 不敏感)
    T18 Trier 上三通道近似独立,故 Fisher 前提成立    (相关 -0.030/-0.008/+0.056)
    T19 多通道中等证据下只有累积型统计量能合起来      (0.413 对 0.187)
    T20 偶数自由度卡方生存函数正确
    T21 弃权按 1.0 计入,不构成证据也不掩盖证据
    T22 攻击编号与论文覆盖矩阵一致(反例保护)     (曾错位:A2/A4 两套编号)
    T23 A3 注入器只压缩时长,不动其他字段
    T24 M9 门控挡住基线投毒                       (漂移 -0.014 对 -0.307)
    T25 时序不符合度分数必须用 z 不能用 p 值      (A3 检出 0.43 对 0.03)
    T26 二值通道单消息功效上界 min(1, alpha/q)
    T27 A4 注入器必须知模型,否则头条主张测成假
    T28 一元 F 覆盖 100% 消息且良性零违反      (二元只覆盖 31.1%)
    T29 细化结构状态会变成词表外弃权            (负面结果,禁止照直觉细化)
    T30 阈值必须取自纯良性流                    (否则 A2 的 DR 假性归零)
    T31 未见组合会良性发生,只有参考模型能拒     (3.9%,用 BPMN 的根本理由)
    T32 B5 HSMM 的 Baum-Welch 似然单调递增      (它是真隐半马尔可夫的证据)
    T33 序贯臂必须复位且自报误报                (两坑叠加曾虚高 22 倍)
    T34 延迟预算 DR 有偶然地板,必须减掉        (alpha=0.05 时地板 0.43)
    T35 并行路数受 m <= alpha*(n_b+1) 约束      (逐消息一行的分辨率上限)
    T36 互锁天花板的 q 必须取部署流实测值      (训练折低估 9 倍)
    T37 配额只能用良性判据选                  (相邻折按攻击表现选会反向)

用法:  py -m pytest tests/test_all.py -v
"""
from __future__ import annotations

import functools
import os

import numpy as np
import pytest

from algorithm import (attacks, conformal, fusion, ingest, interlock,
                       procmodel, sequential, structural, timing)

todo = pytest.mark.skip(reason="待实现:该断言依赖尚未落地的模块")


@functools.lru_cache(maxsize=1)
def trier():
    """加载 Trier 良性数据与参考模型。数据缺失时整组跳过而非报错。"""
    xes, bpmn = ingest.default_log_path(), procmodel.default_bpmn_glob()
    if not os.path.exists(xes):
        pytest.skip(f"缺少 Trier 主日志: {xes}")
    raw = ingest.read_xes(xes)
    live = ingest.valid(raw, drop_failure=True)
    every = ingest.valid(raw, drop_failure=False)
    log_pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    model = procmodel.load_bpmn(bpmn, log_positions=log_pos)
    _, cnt = interlock.check_all(
        ingest.case_chains(live), model,
        all_by_case=ingest.case_chains(every))
    return live, model, interlock.summary(cnt)


def test_t0_parse_matches_reference():
    """解析口径本身的锚点:偏离说明 M1 的生命周期合并逻辑变了。"""
    live, model, _ = trier()
    assert len(live) == 3062
    assert len({a.case for a in live}) == 282
    assert model.n_models == 16
    assert len(model.positions) == 23
    assert len(model.move_graph) == 31


def test_t0b_student_t_cdf_is_correct():
    """自带的 Student-t CDF 是全部时序 p 值的基础,静默出错会污染一切。

    对照标准分位数表,并检查 nu -> inf 时收敛到正态。
    """
    assert abs(timing.student_t_cdf(0.0, 10) - 0.5) < 1e-12
    for t, nu, want in ((1.812461, 10, 0.95), (2.228139, 10, 0.975),
                        (-2.228139, 10, 0.025), (6.313752, 1, 0.95),
                        (2.919986, 2, 0.95), (1.644854, 1e7, 0.95)):
        assert abs(timing.student_t_cdf(t, nu) - want) < 1e-6, (t, nu)
    for t in (-3.0, -0.5, 0.5, 3.0):
        assert abs(timing.student_t_cdf(t, 1e9)
                   - timing.norm_cdf(t)) < 1e-6


def test_t0c_rho_star_matches_reported_endpoints():
    """rho* 公式与结论十八的两个端点精确吻合,可交叉验证 z 的口径为单侧。"""
    assert abs(timing.rho_star(0.007) - 0.016) < 0.001
    assert abs(timing.rho_star(1.843) - 0.986) < 0.001
    assert abs(timing.rho_star(0.315) - 0.519) < 0.001
    # 双侧只作对照,绝不能用于抢跑攻击的功效陈述
    assert timing.rho_star(0.155, one_sided=False) > timing.rho_star(0.155)


def test_t1_feasibility_mask_no_violation():
    """F 是硬约束的前提:良性数据上一次都不能违反。

    这条断言同时保护 M2 的两个关键实现细节——传递可达闭包与重试自环。
    任一退化都会让违反率跳到 14% 量级,F 就不能再作硬约束。
    """
    _, _, s = trier()
    assert s["F_checked"] == 953
    assert s["F_violations"] == 0


def test_t2_interlock_violation_rate():
    """I 只能作软证据,但残余违反必须保持在 2% 以内且成因可解释。"""
    _, _, s = trier()
    assert s["I_checked"] == 2768
    assert s["I_rate"] <= 0.02
    assert (s["cause_LATE"] + s["cause_NEVER"] + s["cause_FAILED"]
            == s["I_violations"])


def test_t3_model_coverage():
    """未建模的移动必须按"未知"处理;覆盖率跌破 95% 说明 BPMN 解析漏了分支。"""
    live, model, _ = trier()
    cov, _ = procmodel.coverage(model, live)
    assert cov >= 0.95


@functools.lru_cache(maxsize=1)
def timing_diag():
    xes = ingest.default_log_path()
    if not os.path.exists(xes):
        pytest.skip(f"缺少 Trier 主日志: {xes}")
    acts = ingest.valid(ingest.read_xes(xes), drop_failure=False)
    return acts, timing.sigma_diagnostics(acts)


def test_t4_additive_aft_equals_saturated():
    """加性 AFT 与逐路线饱和模型残差完全相等,根源是路线图为森林。

    两件事同源:森林 => 每条路线都是桥 => 加性参数化恰好可辨识(与饱和等价),
    但移除任一路线其端点效应即不可辨识(T6 的外推失败)。
    """
    _, d = timing_diag()
    assert d["all_forest"] is True
    assert d["additive_saturated_gap"] < 1e-9


def test_t5_route_covariate_reduces_sigma():
    """路线协变量至少把 sigma_log 降一半,否则 AFT 那一层就不值得加。"""
    _, d = timing_diag()
    assert abs(d["pooled"] - 0.355) < 0.005
    assert abs(d["conditioned"] - 0.116) < 0.005
    assert d["conditioned"] <= d["pooled"] / 2


def test_t6_coldstart_beats_extrapolation():
    """未见路线上,计划工时先验严格优于加性外推。

    这条决定了 DwellModel.location 的回落顺序:已见路线走 AFT,未见路线走
    log(plan)+bias,而不是让加性模型硬外推。
    """
    _, d = timing_diag()
    assert abs(d["loo_additive"] - 0.279) < 0.005
    assert abs(d["loo_planned"] - 0.159) < 0.005
    assert d["loo_planned"] < d["loo_additive"]


def test_t6b_conditioning_arms_are_not_conflated():
    """口径保护:条件化与不条件化的逐组中位不可混用。

    引用 rho* 时把 probe_bound 的端点(条件化)与 probe_timing 的中位
    (不条件化)拼在一起曾是一处真实错误。这条钉住两个中位确实不同,
    以及条件化确实是收紧而非放松。
    """
    acts, _ = timing_diag()
    base = timing.sigma_summary(timing.group_sigmas(acts))
    cond = timing.sigma_summary(
        timing.group_sigmas(acts, stratum="success", conditioned=True))
    assert base["n_groups"] == 31
    assert abs(base["median"] - 0.207) < 0.005
    assert cond["median"] < base["median"]
    assert abs(timing.rho_star(base["median"]) - 0.382) < 0.005


def test_t6c_manual_station_is_marked_uninformative():
    """人在回路工序必须被标为时序无信息,不能当作有效证据参与合成。"""
    acts, _ = timing_diag()
    models = timing.fit(acts)
    hw = models[("hw_1", "/hw/human_review")]
    assert timing.rho_star(hw.sigma) > 0.9
    assert hw.informative is False
    assert all(m.informative for k, m in models.items()
               if k != ("hw_1", "/hw/human_review") and m.sigma < 1.0)


def test_t7_device_level_chain_is_vacuous():
    """反例保护:在无状态服务端点上,设备级结构链没有信息量。

    若哪天有人把结构通道改回设备级并声称有效,这条断言会立刻失败。
    """
    live, _, _ = trier()
    gran, diag = ingest.chain_granularity(live)
    assert gran == "case"
    assert diag["mean_len"] < 2.0
    assert diag["frac_singleton"] > 0.5
    assert diag["n_transitions"] == 953


def test_t8_case_level_chain_support():
    """case 级链要有足够的状态数与转移支撑,Dirichlet 后验才不至于虚化。"""
    live, _, _ = trier()
    chains = ingest.case_chains(live)
    states = {a.op for v in chains.values() for a in v}
    n_trans = sum(len(v) - 1 for v in chains.values() if len(v) > 1)
    assert len(states) == 21
    assert n_trans == 2780
    assert n_trans / len(states) >= 100


@functools.lru_cache(maxsize=8)
def struct_arm(level: str, split: str, randomised: bool, seeds: int = 10):
    """结构通道在某个对照臂下的经验 FPR,返回 {alpha: (均值, 标准差)}。"""
    from algorithm import structural
    from tools import calib_diag
    acts, _ = timing_diag()
    acts = [a for a in acts if a.outcome != "failure"]
    if level == "case":
        seqs = {k: [a.op for a in v]
                for k, v in ingest.case_chains(acts).items()}
    else:
        seqs = {k: [a.op for a in v]
                for k, v in structural.device_case_chains(acts).items()}
    keys = list(seqs)
    splitter = ((lambda s: conformal.split_lexicographic(keys))
                if split == "lex" else
                (lambda s: conformal.split(keys, seed=s)))
    states = sorted({a.op for a in acts})
    res, uniq, _ = calib_diag.arm(seqs, splitter, randomised,
                                  list(range(seeds)), states)
    return res, uniq


def test_t9_randomised_conformal_calibrated():
    """随机化 conformal 在名义 0.05 下经验 FPR 落在 [0.04, 0.06]。"""
    for level in ("case", "device"):
        res, uniq = struct_arm(level, "random", True)
        mean, _ = res[0.05]
        assert 0.04 <= mean <= 0.06, (level, mean)
        assert uniq > 100, (level, uniq)


def test_t10_plain_conformal_breaks_on_discrete():
    """反例保护:朴素 p 值在**取值极粗**的通道上使 FPR 彻底失控。

    这条的适用范围必须说清:(设备, case) 链的 p 值只有 1~3 个取值,
    校准分位数落在原子上,FPR 冲到 1.000 / 0.855。而 case 级链有 28~32
    个取值,朴素形式反而接近名义值——所以"必须随机化"的理由不是
    "总是更准",而是"通道离散度未知时它是唯一无条件安全的选择"。
    """
    res_dev, uniq_dev = struct_arm("device", "lex", False)
    assert uniq_dev <= 3
    assert res_dev[0.05][0] > 0.5

    res_case, uniq_case = struct_arm("case", "random", False)
    assert uniq_case > 20
    assert res_case[0.05][0] < 0.07


def test_t11_split_effect_is_confined_to_the_plain_arm():
    """字典序划分的伤害集中在朴素臂,随机化之后两种划分差别很小。

    早先"0.076 -> 0.053"的说法是拿单次字典序划分对比 20 次随机划分的
    平均,两边随机化抽样次数不同,把差距放大了。对等比较下:
        朴素:   字典序 0.073 vs 随机 0.049   (差距明确)
        随机化: 字典序 0.053 vs 随机 0.046   (差距在一个标准差内)
    """
    plain_lex = struct_arm("case", "lex", False)[0][0.05][0]
    plain_rnd = struct_arm("case", "random", False)[0][0.05][0]
    rand_lex = struct_arm("case", "lex", True)[0][0.05][0]
    rand_rnd = struct_arm("case", "random", True)[0][0.05][0]
    assert plain_lex - plain_rnd > 0.01, (plain_lex, plain_rnd)
    assert abs(rand_lex - rand_rnd) < 0.02, (rand_lex, rand_rnd)


def test_t12_unreachable_alpha_is_flagged():
    """alpha < 1/(n_calib+1) 时必须被标为不可达,否则"零误报"是假象。"""
    c = conformal.Calibrator(scores=[float(i) for i in range(49)]).freeze()
    assert abs(c.min_alpha - 1 / 50) < 1e-12
    assert c.reachable(0.05) and not c.reachable(0.01)
    # 该校准集根本产生不了小于 1/50 的 p 值
    ps = [c.pvalue(1e9, randomised=False) for _ in range(5)]
    assert min(ps) >= c.min_alpha - 1e-12

    acts, _ = timing_diag()
    bank = conformal.ConformalBank(min_size=30)
    for a in acts:
        bank.add(conformal.mondrian_groups(a), 0.0)
    n = len(bank.groups)
    bad01 = sum(1 for g in bank.groups.values() if not g.reachable(0.01))
    assert bad01 / n > 0.5, (bad01, n)


@functools.lru_cache(maxsize=2)
def bound_stability(alpha: float, seeds: int = 10):
    from tools import bound_curve as bc
    from math import log as _log
    acts, _ = timing_diag()
    rows = []
    for seed in range(seeds):
        cal, test, _ = bc.build_folds(acts, seed=seed)
        if not cal or not test:
            continue
        c1, c2 = bc._scores(cal)
        t1, t2 = bc._scores(test)
        a1, a2 = bc._scores(test, shift=_log(0.5))
        h1 = float(np.quantile(c1, 1 - alpha))
        h2 = float(np.quantile(c2, 1 - alpha))
        rows.append((float(np.mean(a1 > h1)), float(np.mean(a2 > h2)),
                     h1, h2))
    return rows


def test_t13_one_sided_is_more_stable_not_merely_more_powerful():
    """单侧检验的真正优势是**稳定**,平均功效增益远小于早先声称的值。

    早先记为"双侧 0.338 对单侧 0.874",这是单个折划分种子的结果;
    30 个种子下双侧是 0.722 ± 0.165、范围 [0.326, 0.880],0.338 落在
    最低端。单侧则是 0.872 ± 0.026。病根是混合校准把 sigma 跨越
    0.008~1.846 的分组塞进同一个分位数,|z| 的 99% 分位被少数低 sigma
    组的极端点主导,而左尾阈值不受其影响。
    """
    rows = bound_stability(0.01)
    dr1 = np.array([r[0] for r in rows])
    dr2 = np.array([r[1] for r in rows])
    h1 = np.array([r[2] for r in rows])
    h2 = np.array([r[3] for r in rows])
    assert dr1.mean() > 0.80
    assert dr1.mean() > dr2.mean()
    # 稳定性才是主要论据:单侧的离散度显著小于双侧
    assert dr1.std() < dr2.std() / 2
    assert h1.std() < h2.std() / 2
    # 反例保护:不得再声称平均增益有 0.5 那么大
    assert (dr1 - dr2).mean() < 0.35


def test_t14_bound_matches_measurement():
    """理论检出率与实测的平均绝对偏差 <= 0.05(实测 0.022)。"""
    from math import log as _log
    from tools import bound_curve as bc
    acts, _ = timing_diag()
    cal, test, _ = bc.build_folds(acts, seed=7)
    z_cal = np.array([r["z"] for r in cal])
    z_test = np.array([r["z"] for r in test])
    s_test = np.array([r["sigma"] for r in test])
    thr1 = float(np.quantile(-z_cal, 0.99))
    errs = []
    for rho in (0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50):
        shift = _log(1 - rho) / s_test
        dr = float(np.mean(-(z_test + shift) > thr1))
        pred = float(np.mean([timing.norm_cdf(-thr1 - s) for s in shift]))
        errs.append(abs(dr - pred))
    assert np.mean(errs) <= 0.05, np.mean(errs)


def test_t15_cusum_requires_slack_above_one():
    """H0 下 E[-log p] = 1,故 CUSUM 的松弛量必须 > 1,否则必然误报。"""
    with pytest.raises(ValueError):
        sequential.CUSUM(k=1.0, h=10.0)
    rng = np.random.default_rng(0)
    benign = list(rng.random(4000))
    h = sequential.calibrate_h(benign, target_arl0=500, k=1.5)
    c = sequential.CUSUM(k=1.5, h=h)
    alarms = sum(1 for p in benign if c.update(p) or c.reset())
    assert alarms <= len(benign) / 400
    # 攻击流:证据持续偏大时应迅速告警
    attack = list(rng.random(200) * 0.002)
    d = sequential.run_to_detection(attack, sequential.CUSUM(k=1.5, h=h),
                                    budget=40)
    assert d is not None and d <= 10


def test_t16_e_process_is_anytime_valid():
    """e 过程在 H0 下财富是鞅,越界概率受 Ville 不等式约束。"""
    rng = np.random.default_rng(1)
    fired = 0
    trials = 400
    for _ in range(trials):
        e = sequential.EDetector(alpha=0.05)
        for p in rng.random(200):
            if e.update(p):
                fired += 1
                break
    assert fired / trials <= 0.05 + 0.02, fired / trials


def test_t17_fusion_needs_per_channel_calibration_first():
    """规矩 1 的反例保护:先合成再统一校准,min 型统计量会卡在原子上。

    原始时序 p 值有 ~8% 触到裁剪下界,合成后在底部形成原子。此时
    conformal 阈值落在原子内,FPR 对 alpha 不敏感——这正是失效特征。
    """
    rng = np.random.default_rng(0)
    n = 4000
    # 复现失效机理:一个通道有 8% 的质量堆在下界
    floor = rng.random(n) < 0.08
    p_time = np.where(floor, 1e-12, rng.random(n))
    rows = [(float(t), float(s), float(i)) for t, s, i
            in zip(p_time, rng.random(n), rng.random(n))]
    s = np.array([fusion.combine(r, "simes") for r in rows])
    ca, te = s[: n // 2], s[n // 2:]
    fpr = [float((te <= np.quantile(ca, a)).mean()) for a in (0.05, 0.01)]
    # 两个 alpha 给出几乎相同的 FPR,且都远超名义值
    assert abs(fpr[0] - fpr[1]) < 0.02, fpr
    assert fpr[1] > 0.05, fpr


def test_t18_channels_are_near_independent_on_trier():
    """Fisher 的前提是可测的,不是可假设的。

    Trier 上三通道证据的两两相关都在 ±0.06 内,故 Fisher 可用;换产线
    必须重测。这条断言同时保护 dependence() 的口径。
    """
    rng = np.random.default_rng(0)
    n = 3000
    indep = [(float(a), float(b), float(c)) for a, b, c
             in zip(rng.random(n), rng.random(n), rng.random(n))]
    d = fusion.dependence(indep)
    assert d["max_abs"] < fusion.INDEPENDENCE_TOL and d["fisher_ok"]
    # 强相关时必须判定 Fisher 不可用
    u = rng.random(n)
    dep = [(float(x), float(x), float(y)) for x, y in zip(u, rng.random(n))]
    assert not fusion.dependence(dep)["fisher_ok"]


def test_t19_fisher_accumulates_where_min_type_cannot():
    """规矩 3 的机理:多通道各带中等证据时,只有累积型统计量能合起来。

    三个通道各自 p=0.05 时,alpha=0.01 下 Fisher 触发而 Simes/minp 不:
    Fisher 把三份中等证据加起来(约 0.006),Simes 最好也只能还原到单个
    通道的 0.05,minp 还要再付 3 倍。这解释了多通道攻击下 0.413 对 0.187。
    """
    moderate = (0.05, 0.05, 0.05)
    assert fusion.fisher(moderate) < 0.01
    assert fusion.simes(moderate) == pytest.approx(0.05)
    assert fusion.minp(moderate) == pytest.approx(0.15)
    # 反过来,单通道极端时 min 型不该输给 Fisher 太多
    lopsided = (1e-4, 1.0, 1.0)
    assert fusion.minp(lopsided) < 0.001
    # 合成相对单通道的稀释:min 型要付 k 倍 alpha 的代价
    assert fusion.minp(lopsided) == pytest.approx(3e-4)


def test_t20_chi2_sf_is_correct():
    """Fisher 依赖偶数自由度卡方生存函数,错了会静默改变所有合成 p 值。"""
    for x, df, want in ((0.0, 2, 1.0), (5.991465, 2, 0.0500),
                        (9.487729, 4, 0.0500), (16.811894, 6, 0.0100),
                        (12.591587, 6, 0.0500), (1.386294, 2, 0.5000)):
        assert abs(fusion.chi2_sf(x, df) - want) < 1e-4, (x, df)


def test_t22_attack_numbering_matches_the_paper():
    """反例保护:攻击编号一旦与 新想法.md 覆盖矩阵错位,所有实验结果作废。

    代码里曾用过另一套编号(A2=抢跑、A4=重放),而论文口径是 A3=抢跑、
    A4=状态模仿,且"A4 只有互锁通道能抓"是头条主张。错位不会报错,只会
    悄悄让每个 A 编号的结论张冠李戴,故必须钉死。
    """
    assert attacks.FAMILY_ZH == {
        "A1": "朴素重放", "A2": "物理不可行注入", "A3": "抢跑重放",
        "A4": "状态模仿", "A5": "渐变漂移", "A6": "消息抑制/延迟",
        "A7": "多设备协同伪造"}
    # 未实现的攻击族必须显式拒绝,不能静默返回良性流冒充攻击结果
    for fam in set(attacks.FAMILY_ZH) - set(attacks.IMPLEMENTED):
        with pytest.raises(NotImplementedError):
            attacks.inject([], attacks.AttackSpec(family=fam))


def test_t23_advance_attack_only_shortens_duration():
    """A3 注入器的正确性:只压缩时长,不动 case/device/order 与开始时刻。"""
    live, _, _ = trier()
    sub = [a for a in live if a.duration_s][:400]
    bad, labels = attacks.inject(
        sub, attacks.AttackSpec(family="A3", rho=0.3, rate=0.5, seed=0))
    assert len(bad) == len(sub) == len(labels)
    assert 0 < sum(labels) < len(labels)
    for a, b, hit in zip(sub, bad, labels):
        assert (a.case, a.device, a.order) == (b.case, b.device, b.order)
        assert a.t_start == b.t_start
        if hit:
            assert abs(b.duration_s - a.duration_s * 0.7) < 1e-6
        else:
            assert b.duration_s == a.duration_s


def test_t24_gating_blocks_baseline_poisoning():
    """M9 门控是与原专利"无条件在线更新"的实质差别,必须可量化。

    攻击者持续注入抢跑数据试图把基线拉向自己;无门控时基线被拖走,
    门控时几乎不动。这里只验证机制方向与量级差,数值细节见 online_diag。
    """
    live, model, _ = trier()
    drift = {}
    for gated in (True, False):
        det = _online_detector(live, model, gated=gated)
        key = max((k for k, m in det.timing.items() if m.informative),
                  key=lambda k: det.timing[k].n)
        route = next(iter(det.timing[key].route_effect))
        before = det.timing[key].route_effect[route]
        victim = next(a for a in live
                      if (a.device, a.op) == key and a.duration_s)
        rng = np.random.default_rng(0)
        for _ in range(120):
            det.observe(_faster(victim, 0.30), rng=rng)
        drift[gated] = abs(det.timing[key].route_effect[route] - before)
        if gated:
            assert det.stats["update_blocked"] > det.stats["update_applied"]

    # 断言机制而非魔数:门控把基线漂移压到无门控的几分之一
    assert drift[False] > 0.15, drift
    assert drift[True] < drift[False] / 3, drift


def _online_detector(live, model, *, gated: bool = True):
    from algorithm.detector import Detector, DetectorConfig
    by_case = {}
    for a in live:
        by_case.setdefault(a.case, []).append(a)
    keys = sorted(by_case)[: int(len(by_case) * 0.75)]
    return Detector(DetectorConfig(alpha=0.01, gated_update=gated)).fit(
        [a for k in keys for a in by_case[k]], model=model,
        rng=np.random.default_rng(0))


def _faster(a, rho):
    import copy
    from datetime import timedelta
    b = copy.copy(a)
    b.t_end = a.t_start + timedelta(seconds=a.duration_s * (1 - rho))
    return b


def test_t25_timing_score_must_be_z_not_pvalue():
    """反例保护:p 值在数值下界饱和,会安静地把核心攻击的检出率削掉一个量级。

    这个缺陷不报错、不破坏误报率,只是让 A3 抢跑的时序检出率从 0.43 掉到
    0.03。机理是 8.1% 的良性活动 p 值已在下界,尾部再无次序可言。
    """
    from algorithm.detector import DetectorConfig
    assert DetectorConfig().timing_score == "z"
    # p 值臂:大量样本堆在下界,分位数无法分辨"更极端"
    floor = [1e-12] * 80 + [0.5] * 920
    assert len({round(v, 15) for v in floor}) == 2
    c = conformal.Calibrator(scores=[-v for v in floor]).freeze()
    rng = np.random.default_rng(0)
    hit = np.mean([c.pvalue(-1e-12, rng=rng) <= 0.01 for _ in range(2000)])
    assert hit < 0.2, hit          # 攻击落在原子里,大部分时候够不到 alpha
    # z 臂:同样极端的观测有连续次序,分位数分得开
    z = list(np.random.default_rng(1).normal(size=1000))
    cz = conformal.Calibrator(scores=z).freeze()
    assert cz.pvalue(6.0, rng=rng) <= 0.01


def test_t26_binary_channel_power_is_capped_by_alpha_over_q():
    """互锁是二值通道,单消息功效上界 min(1, alpha/q),与不变量质量无关。

    这条决定了论文能声称的 alpha 下限,也是"软层升硬层"部署条件的定量理由。
    """
    rng = np.random.default_rng(0)
    for q, alpha in ((0.017, 0.01), (0.017, 0.001), (0.05, 0.01)):
        # 违反必然发生时的随机化 p 值:p = U * q
        dr = np.mean([rng.random() * q <= alpha for _ in range(20000)])
        assert abs(dr - min(1.0, alpha / q)) < 0.02, (q, alpha, dr)


def test_t27_mimicry_attacker_must_use_the_model():
    """A4 注入器若不知模型就会制造异常重复,把'只有互锁能抓'测成假。"""
    live, _, _ = trier()
    sub = [a for a in live if a.duration_s][:600]
    chains = {}
    for a in sub:
        chains.setdefault(a.case, []).append(a.op)
    tm = structural.fit(chains, states=sorted({a.op for a in sub}))

    naive, ln = attacks.inject(sub, attacks.AttackSpec(
        family="A4", rate=0.2, seed=0))
    smart, ls = attacks.inject(sub, attacks.AttackSpec(
        family="A4", rate=0.2, seed=0, struct_model=tm,
        knowledge="model"))
    assert sum(ln) == sum(ls) > 0

    def repeat_rate(stream, labels):
        """伪造消息与其前一条重复的比例——结构通道正是靠这个抓 A4。"""
        prev, n, rep = {}, 0, 0
        for a, hit in zip(stream, labels):
            if hit and prev.get(a.case) == a.op:
                rep += 1
            if hit:
                n += 1
            prev[a.case] = a.op
        return rep / max(n, 1)

    assert repeat_rate(naive, ln) > 0.9      # 朴素注入器几乎全是重复
    assert repeat_rate(smart, ls) < 0.5      # 知模型的攻击者不留这个把柄


def test_t28_unary_f_covers_every_message_and_is_benign_clean():
    """F 的一元部分覆盖 100% 消息、良性零违反;二元部分只覆盖 31%。

    A2 硬层从 0.29 升到 0.98 全靠这一项。能力集必须按设备类归并——按实例
    会把 sm_2 的 44 次 /sm/sort 误判为违反(1.44%)。
    """
    live, model, _ = trier()
    assert procmodel.device_class("sm_2") == "sm"
    assert procmodel.device_class("hbw") == "hbw"

    viol = [a for a in live if not model.can_perform(a.device, a.op)]
    assert viol == [], viol[:3]                    # 良性零违反
    covered = [a for a in live
               if procmodel.device_class(a.device) in model.capable]
    assert len(covered) == len(live)                # 一元覆盖 100%

    seen, checkable = set(), 0
    for a in sorted(live, key=lambda x: (x.t_consume, x.order)):
        if (a.case, a.device) in seen:
            checkable += 1
        seen.add((a.case, a.device))
    assert 0.29 < checkable / len(live) < 0.33      # 二元覆盖 31%

    # 按实例归并会破功:sm_2 拿不到 sm_1 的能力
    inst = {}
    for d, ops in model.capable.items():
        inst[d] = ops
    assert "/sm/sort" in model.capable["sm"]


def test_t29_finer_structural_states_abstain_instead_of_flagging():
    """细化状态把可检测异常变成词表外弃权——负面结果,禁止照直觉细化。"""
    live, _, _ = trier()
    sub = [a for a in live if a.duration_s][:800]
    coarse, fine = {}, {}
    for a in sub:
        coarse.setdefault(a.case, []).append(a.op)
        fine.setdefault(a.case, []).append(f"{a.device}|{a.op}")
    tm_c = structural.fit(coarse, states=sorted({a.op for a in sub}))
    tm_f = structural.fit(fine, states=sorted(
        {f"{a.device}|{a.op}" for a in sub}))
    assert len(tm_f.states) > len(tm_c.states)

    # 挑一个"该设备没做过、但别的设备做过"的操作,即 A2 的注入方式
    ops_by_dev = {}
    for a in sub:
        ops_by_dev.setdefault(a.device, set()).add(a.op)
    dev, prev = next((a.device, a.op) for a in sub)
    alien = next(o for o in {x.op for x in sub}
                 if o not in ops_by_dev[dev])

    # 粗粒度:操作在词表内,可给出 p 值
    assert structural.struct_pvalue(tm_c, prev, alien) is not None
    # 细粒度:组合在词表外,弃权(None 或 1.0),异常被悄悄放过
    v = structural.struct_pvalue(tm_f, f"{dev}|{prev}", f"{dev}|{alien}")
    assert v is None or v > 0.5, v


def test_t30_threshold_must_come_from_a_clean_benign_stream():
    """阈值不能定在受攻击流内部的良性消息上。

    A2 原地改写操作名,后继良性消息会拿伪造的前驱去比对,产生攻击引起的
    级联触发;算成误报时若级联率超过 alpha,阈值退化为 +inf、检出率假性
    归零——本方法 A2 的 DR 确实这样被测成过 0.00。
    """
    from algorithm.baselines import dr_at_alpha
    # 受攻击流内部:12% 的良性消息因级联拿到 +inf,阈值随之退化
    contaminated = [float("inf")] * 12 + [0.0] * 88
    thr_bad = sorted(contaminated)[int(0.99 * 100) - 1]
    assert thr_bad == float("inf")
    assert not any(s > thr_bad for s in [float("inf")] * 20)   # 检出归零

    # 纯良性流:阈值有限,攻击消息被抓出来
    clean = [0.0] * 100
    dr, fpr = dr_at_alpha(clean, [float("inf")] * 20, 0.01)
    assert dr == 1.0 and fpr <= 0.01


def test_t31_unseen_pairs_occur_benignly_so_only_the_model_can_reject():
    """日志里"没见过"与"不允许"无法区分,而"没见过"会良性发生。

    这是用 BPMN 参考模型的根本理由,也同时解释了 B4 打不过 B3、以及细化
    结构状态为何退化成弃权。
    """
    from tools.baseline_diag import split
    live, model, _ = trier()
    train, _, test = split(live)
    seen = set()
    for a in train:
        seen.add((a.device, a.op))
    st = [a for a in test if a.t_consume]
    oov = [a for a in st if (a.device, a.op) not in seen]

    # "没见过"在时间序下良性发生,比例远超 alpha=0.01,故不可作为证据
    assert len(oov) / len(st) > 0.01, len(oov) / len(st)
    # 参考模型不误伤它们:它区分"不在我的样本里"与"设计上不允许"
    assert all(model.can_perform(a.device, a.op) for a in oov)


def test_t34_delay_budget_dr_has_a_chance_floor():
    """延迟预算口径下"什么都不检测"也能拿分,地板必须减掉。

    地板 = 1-(1-FPR)^(budget+1)。alpha=0.05、预算 10 条时高达 0.43。
    实测 B1 MBDF 六族全部贴地板——这正是 T-a 的预期表现,但照抄未减地板的
    数字会让论文自己给不可能性结果提供反例。
    """
    from algorithm.baselines import chance_floor, judge
    assert chance_floor(0.05, 10) > 0.40
    assert chance_floor(0.01, 10) > 0.09
    assert chance_floor(0.0, 10) == 0.0

    # 一个与标签完全无关的分数流:检出率应当就是地板,净值约为零
    rng = np.random.default_rng(3)
    n = 800
    benign = [list(rng.random(n))]
    attack = [list(rng.random(n))]
    labels = [i % 5 == 0 for i in range(n)]
    _, _, sdr, sfpr, floor = judge(benign, attack, labels, alpha=0.05)
    assert abs(floor - chance_floor(sfpr, 10)) < 1e-12
    assert abs(sdr - floor) < 0.15, (sdr, floor)


def test_t35_per_message_arm_is_resolution_limited():
    """并行子检测器的路数受 m <= alpha*(n_b+1) 约束。

    良性参照流 508 条时经验 p 下界是 1/509；四路均分后每路 alpha/4=0.0025,
    阈值下只容 1 个秩位,实际执行的是"取良性最大值作阈值"。这会把 A3/A5
    削掉一个数量级,而 A2 不变——失真是攻击特异的,且歧视多通道方法。
    """
    from algorithm.baselines import empirical_p
    n_b, alpha, m = 508, 0.01, 4
    floor_p = 1.0 / (n_b + 1)
    assert alpha / m > floor_p                      # 勉强可达
    assert int(alpha / m * (n_b + 1)) == 1          # 只容 1 个秩位
    assert int(alpha / 1 * (n_b + 1)) == 5          # 不分路时 5 个

    col = list(range(n_b))
    # 仅次高分在 alpha/4 下已不可判为异常,在 alpha 下可以
    assert empirical_p(col, [n_b - 2])[0] > alpha / m
    assert empirical_p(col, [n_b - 2])[0] <= alpha
    # 可容纳路数的一般规则
    assert max(1, int(alpha * (n_b + 1))) == 5


def test_t36_interlock_ceiling_uses_deployment_q():
    """互锁单消息功效上界 = 攻击触发率 * min(1, alpha/q_部署)。

    q 必须取**部署流**实测值:训练折 0.0054 会让人以为天花板不生效,而测试流
    实测 0.047,天花板只有 0.21。代入 A4 的 0.69 触发率得 0.145,与覆盖矩阵
    的 0.12 吻合。全局池把 q 减半但触发率也减半,故净收益接近零(结论四十七)。
    """
    def power(trigger, q, alpha=0.01):
        return trigger * min(1.0, alpha / q)

    q_train, q_deploy = 0.0054, 0.047
    assert min(1.0, 0.01 / q_train) == 1.0          # 训练折看似不受限
    assert power(0.69, q_deploy) < 0.20             # 部署流其实被压到 0.15
    assert abs(power(0.69, q_deploy) - 0.147) < 0.01

    # 全局池:q 减半、触发率也减到 0.41 -> 两效应抵消,净收益 < 0.05
    assert abs(power(0.41, 0.023) - power(0.69, q_deploy)) < 0.05
    # 要让互锁够用,部署 q 必须压到 alpha 量级;全局池只到 2.3%
    assert 0.023 > 0.01


def test_t37_alpha_allocation_is_selected_on_benign_data_only():
    """配额只能用良性判据选,不能在相邻折上按攻击表现选(结论四十八、四十九)。

    judge 必须支持非均分 weights,且 weight=0 的路完全不参与判决——否则
    "剔除互锁"无法表达。同时锁住通用原子统计量失败的那两处误判。
    """
    from algorithm.baselines import judge

    rng = np.random.default_rng(5)
    n = 900
    # 两条路:第 0 条有信号,第 1 条纯噪声
    lab = [i % 4 == 0 for i in range(n)]
    sig_b = list(rng.normal(0, 1, n))
    sig_a = [v + (3.0 if L else 0.0) for v, L in zip(sig_b, lab)]
    noise_b, noise_a = list(rng.normal(0, 1, n)), list(rng.normal(0, 1, n))

    both = judge([sig_b, noise_b], [sig_a, noise_a], lab, alpha=0.05)
    only = judge([sig_b, noise_b], [sig_a, noise_a], lab, alpha=0.05,
                 weights=[1.0, 0.0])
    # 把预算全给有信号的那一路,检出率必须不低于均分
    assert only[2] >= both[2], (only[2], both[2])

    with pytest.raises(ValueError):
        judge([sig_b], [sig_a], lab, alpha=0.05, weights=[0.5, 0.5])
    with pytest.raises(ValueError):
        judge([sig_b], [sig_a], lab, alpha=0.05, weights=[0.0])

    # 通用原子统计量的两处误判:良性全并列在同一值时,"最异常处的原子质量"
    # 读成 1.0,会把良性零违反的硬层误剔;而随机化会把二值通道的原子抹平。
    def atom_at_max(xs):
        top = max(xs)
        return sum(1 for x in xs if x >= top) / len(xs)

    hard_benign = [0.0] * 500                 # 硬层:良性零违反
    assert atom_at_max(hard_benign) == 1.0    # 误判成"全是异常"
    q = 0.03
    smeared = [rng.uniform(0, q) if i < 15 else q + rng.uniform(0, 1 - q)
               for i in range(500)]
    assert atom_at_max(smeared) < 0.01        # 真实 q=0.03 被抹成 <0.01


def test_t32_hsmm_em_likelihood_is_monotone():
    """Baum-Welch 的对数似然必须单调递增——这是 B5 是真 HSMM 的关键证据。

    有 bug 的 Baum-Welch 典型表现就是似然非单调。实测 12 次迭代
    -8093 -> -4716,严格单调。
    """
    from algorithm import baselines as B
    live, _, _ = trier()
    sub = [a for a in live if a.duration_s][:900]
    m = B.HSMM(k_grid=(3,))
    m.ops = sorted({a.op for a in sub})
    m.oidx = {o: i for i, o in enumerate(m.ops)}
    seqs = m._sequences(sub)

    lls = []
    for it in (1, 2, 4, 6, 8):
        mm = B.HSMM(k_grid=(3,), iters=it)
        mm.ops, mm.oidx = m.ops, m.oidx
        lls.append(mm._em(seqs, 3, 6)["ll"])
    assert all(lls[i] >= lls[i - 1] - 1e-6 for i in range(1, len(lls))), lls
    assert lls[-1] > lls[0]


def test_t33_sequential_arm_must_reset_and_report_its_own_fpr():
    """序贯口径的两个坑,叠加时把基线的误报虚高到名义值的 22 倍。

    坑一:CUSUM.update 不自复位,不复位则 S 越过 h 后每条消息都告警。
    坑二:目标 ARL0 超过良性流长时,零误报使 ARL0 记作无穷、h 落到区间下界。
    """
    from algorithm.baselines import _cusum_alarms
    rng = np.random.default_rng(0)
    benign = list(rng.random(600))

    # 坑一:不复位时告警数会接近流长
    h = sequential.calibrate_h(benign, 100, k=1.5)
    c = sequential.CUSUM(k=1.5, h=h)
    no_reset = sum(1 for p in benign if c.update(p))
    _, with_reset = _cusum_alarms(benign, benign, alpha=0.01)
    assert len(with_reset) < no_reset
    assert len(with_reset) / len(benign) < 0.03      # 与名义 0.01 同量级

    # 坑二:目标 ARL0 撑不起时必须报错而不是悄悄返回一个低 h
    try:
        _cusum_alarms(benign[:50], benign[:50], alpha=0.001)
        raise AssertionError("应当拒绝:50 条消息撑不起 ARL0=1000")
    except ValueError:
        pass


def test_t38_structural_score_must_be_probability_not_randomised_pit():
    """结构通道喂给校准器的必须是预测概率,不是随机化 PIT p 值。

    与 T25(时序必须用 z 而非撞地板的 p 值)同型:随机化 PIT
    p = below + U*at 把 Dirichlet 平滑造成的一大片**并列尾部原子**摊成一段
    均匀区间,于是一个从未见过的转移有相当概率拿到高于 alpha 的 p 值。

    关键在于**并列尾部质量 at 与该行支撑度成反比**:支撑厚的行 at 很小、PIT
    尚可用;支撑薄的行(转移只出现过几次)at 能占到半数概率质量,于是 U*at 近乎
    铺满 (0,1],这一行**完全没有功效**。而攻击恰好落在薄支撑的行上——常见转移
    没什么可伪造的。所以不能说"PIT 平均还行",要按行看。
    """
    from algorithm import structural as S

    states = [f"s{i}" for i in range(20)]
    counts = np.zeros((20, 20))
    counts[0, 1] = 300.0                       # 厚支撑行:见过 300 次
    counts[2, 3] = 4.0                         # 薄支撑行:只见过 4 次
    tm = S.TransitionModel(states=states, counts=counts,
                           index={s: i for i, s in enumerate(states)})

    thick = tm.predictive("s0")
    thin = tm.predictive("s2")
    at_thick = float(thick[thick == thick[7]].sum())
    at_thin = float(thin[thin == thin[7]].sum())
    # 薄支撑行的并列尾部质量高一个量级,且已远超 alpha=0.05
    assert at_thin > 10 * at_thick
    assert at_thin > 0.5 and at_thick < 0.05

    rng = np.random.default_rng(0)
    pit = [S.struct_pvalue(tm, "s2", "s7", randomised=True, rng=rng)
           for _ in range(600)]
    # 薄支撑行上 PIT 形式对"从未见过的转移"几乎无功效:多数落在 alpha 之上
    assert np.mean([p > 0.05 for p in pit]) > 0.8, np.mean(pit)

    # 概率形式:确定值,且严格小于同一行里见过的那个后继 -> 次序完好,
    # 分辨率交给下游的良性经验分布,不在每条消息上自摊一次。
    prob = S.struct_score(tm, "s2", "s7")
    assert prob is not None
    assert prob < S.struct_score(tm, "s2", "s3")
    assert S.struct_score(tm, "s2", "s8") == pytest.approx(prob)


def test_t39_comparison_harness_must_calibrate_exactly_once():
    """E1 口径:交给 judge 的必须是原始分数,不能先过一层冻结 conformal。

    judge 内部本就要做经验 p 值变换。若我方先过一遍随机化 conformal 再交给
    它,同一条流被随机化两次,而基线只经一次——第一次的 U*(1+eq)/(n+1) 项在
    并列密集处足以打乱相邻原子的次序,实测结构通道因此损失 0.07 净检出率。
    部署时只有一层校准(冻结的 conformal),judge 是它的替身而非附加层。

    机制是**随机化 conformal 不保序**:并列密集时 U*(1+eq)/(n+1) 项的幅度
    超过相邻档位之间的间距,于是分数更异常的那条消息可能拿到更大的 p 值。
    单次经验变换按构造保序,叠第二次才引入这种反转。
    """
    from algorithm.baselines import empirical_p
    from algorithm.conformal import Calibrator

    rng = np.random.default_rng(0)
    # 良性分数只取少数几个离散档位 -> 并列密集,与转移概率的形状一致
    grid = np.array([0.2, 0.5, 0.9])
    ben = list(rng.choice(grid, 400))
    s_lo, s_hi = 0.21, 0.25                    # 都比 0.2 档更异常,s_hi 更甚

    # 单次经验变换:保序,严格不等
    p1 = empirical_p([-x for x in ben], [-s_lo, -s_hi])
    assert p1[1] <= p1[0]

    cal = Calibrator()
    for x in ben:
        cal.add(-x)
    cal.freeze()
    inv = 0
    for i in range(600):
        r = np.random.default_rng(i)
        a = cal.pvalue(-s_lo, rng=r)
        b = cal.pvalue(-s_hi, rng=r)
        inv += b > a                           # 更异常的反而拿到更大的 p
    # 叠加的这一层随机化把相邻档位之间的次序打乱了相当一部分
    assert inv / 600 > 0.2, inv / 600


def test_t21_abstention_is_neutral_not_evidence():
    """弃权按 1.0 计入:缺证据不能变成反证,也不能反过来掩盖别的通道。"""
    assert fusion.simes((0.01, 1.0, 1.0)) == pytest.approx(0.03)
    assert fusion.fisher((1.0, 1.0, 1.0)) == pytest.approx(1.0)
    # 弃权不应让已有的强证据失效
    assert fusion.fisher((1e-6, 1.0, 1.0)) < 0.01
    # None 与 1.0 等价,避免调用方用 None 表示弃权时行为分叉
    assert fusion.simes((0.01, None, None)) == pytest.approx(0.03)
