"""TESSERA 断言集。每条断言锚定一个已量化的事实,不写"看起来对"的检查。

沿用 paper02 的做法:数字写死在断言里,改动实现若动了这些数,测试必须失败,
逼人回来解释为什么。分两类——
  A. **与 paper02 对数**:同一份日志,解析口径必须一致,否则"同数据同划分"
     的对照实验主张作废。
  B. **本文的新测量**:互证超图的规模与覆盖度。这些是 TESSERA 的第一批实测
     结果,写进论文前先固定在这里。

    A1  日志规模与 paper02 一致          (3,157 / 3,062 / 282 case / 15 设备)
    A2  BPMN 抽取与 paper02 一致         (16 模型 / 23 位置 / 31 条物料流边)
    A3  设备无状态,故观测单元取交接事件  (2,109 条链, 65.1% 长度为 1)
    B1  互证超图规模                     (185 条边 / 14 个交接位置)
    B2  见证集合是 O(1)                  (中位 1, 最大 6)
    B3  无对手方区间只有三个入库操作     (语义一致,非随机缺口)
    B4  互证覆盖度                       (2,145/3,062 = 70.05%)
    B5  case 末位活动是结构上界          (282 个缺口;链中 77.2%)
    B6  见证独立性须按设备实例判定       (按类判使覆盖率掉到 64.89%)
    B7  互证窗口 Δ 的长尾来自调度排队    (中位 6.7 s, p95 119.7 s)
    C1  哈希链往返与承诺根签名可核验
    C2  伪造原像被拒,且披露即自证其罪    (FORGED 带可转移证据)
    C3  提前披露被拒                     (前置条件 2,防跨槽预付沉默)
    C4  SILENT 判决时刻恰为 r*T_hb+skew  (确定性判据,非统计检验)
    C5  收到合法披露后缺失计数必须复位   (反例保护,paper02 曾虚高 22 倍)
    C6  域分离使同 seed 跨设备/会话不通用
    C7  突发丢包把所需 r 从 3 抬到 9     (误报 475 次/h -> 7.9e-7)
    C8  沉默通道的 q 是设计参数          (r>=2 即解开天花板;互锁压不动)
    C9  带宽只由 T_hb 决定,与 r 无关     (r 花时延不花带宽)
    C10 沉默的检测时延远小于互证         (1.81 s 对计划时长中位 45 s)
    D1  P1 伪造声明与良性活动逐字段一致  (7 个字段 100%,时长落在 IQR 内)
    D2  良性流上互证的误报率             (69/3062 = 2.25%)
    D3  P1/P3 的互证检出率              (363/363 = 1.000, 中位 54.6 s)
    D4  P3 完全逃脱沉默机制,只有互证能抓 (消融表最关键的一行)
    D5  派发排队容差不可省               (省了良性误报从 2.25% 涨到 19.8%)
    D6  P4 一跳串谋只推迟判决,不逃脱     (主 0.184,串谋方 0.750)
    D7  看门狗基线 S1 对 P1/P3/P4 无能力 (0.000,它只管"该报的没报")
    D8  次生告警:沉默者连带指控其上游    (277 条,必须与沉默机制合用才能正确归因)
    D9  攻击编号与文档一致               (反例保护,paper02 规则 8)
    E1  串谋界的作用域与分母口径         (SELF_ONLY 必须留下,NO_REALIZED 必须剔除)
    E2  实测串谋界 k_min=1、中位 5       (安全论断只能引用最小值与低分位)
    E3  同设备接手让链免费延长           (7.45% 覆盖缺口的安全代价:1,945 个免费跳)
    E4  安全感知任务分配是负面结果       (min/中位纹丝不动,增益全在本来安全的链上)
    E5  模型级下界逐工作流算,不可合并     (合并会把界虚高)
    E6  串谋界与 P4 实测互为佐证         (结构 19.0% vs 实测逃脱 25.0%,同量级)
    F1  时间预算只能接沉默,不能接互证    (互证时延超最松预算 25 倍,量纲不同)
    F2  借用汽车 FHI 对工厂 AGV 太松     (检测预算对应行驶距离 = 防护场 256%)
    F3  危害模型反推的预算与可行区间     (FHI 0.85 s / 检测 0.60 s / 2,311 B/s)
    F4  突发容忍的带宽代价               (3.32x;r 3 -> 10)
    F5  最优解顶在安全边界               (4 个口径中 3 个,1 个两条同时顶满)
    F6  最严口径仍比 PBFT 便宜两个数量级 (131x;省的是频率不是节点数)
    F7  预算给不出方案时必须返回 None    (不许靠放宽误报预算掩盖)
    G1  见证资格不可按设备类硬查         (反例保护:那会重新引入 B6 修掉的 bug)
    G2  W1 共识对任务状态伪造检出恰为 0  (一致 != 真实;付 131 倍带宽换一个看门狗)
    G3  W2 问所有人零增益               (检出逐位相同,见证集 4.13x)
    G4  W3 随机提名崩塌                 (0.105;失败形态是发现不了而非乱指控)
    G5  W4 空间邻居只恢复 52%           (却多付 34% 见证集——第一贡献的主证据)
    G6  基线只许换选取规则,不许换协议    (公平性的结构保证)
    H1  S1 看门狗与 D7 交叉一致         (P1/P3 = 0, P2 = 1;同窗口同容差)
    H2  S2 计划残差对 P1/P3 结构性失效  (DR≈FAR≈0;时长落在分布中央)
    H3  S3 一致性检验对 P1/P3 结构性失效 (FAR=0 且 DR=0;伪造轨迹对齐代价为 0)
    H4  P1 与 P3 对单观测者必须完全一样 (自检:否则实现漏进了不该有的信息)
    H5  R0 地板:判别力 ≈ 0             (等告警预算下随机指控不工作)
    H6  第一档与第二档接口不得混用       (SingleObserver ≠ WitnessPolicy)
    I1  H1 等带宽周期上报时延 ≈ 8x      (报文比 128/16;带宽守恒)
    I2  H1 最严口径仍超检测预算         (4.68 s ≫ 0.60 s)
    I3  H2 活性有归责无                 (无身份绑定、无可转移证据)
    I4  H3 TESLA 披露后可伪造           (MAC 可被第三方复现;无不可否认)
    I5  U1 先知覆盖率 = 1,缺口 = 29.95% (差额即按需主动互证靶区)
    I6  第三/四档与前两档接口不得混用   (解析对照 ≠ 回放赛马)
    J1  p=50% 突发口径仍可行           (PISTIS 地标;B=27.5 KB/s = PBFT/36)
    J2  带宽随丢包率单调上升           (扫参敏感性的结构保证)
    J3  main 入口 P1 检出与 detect_diag 同口径 (DR=1.000)

用法(在 paper03/tessera/ 下):  py -m pytest tests/test_all.py -v
"""
from __future__ import annotations

import os
import sys
from statistics import mean, median

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithm import (attacks, baselines, budget,  # noqa: E402
                       collusion, corroborate, coverage, crypto, ingest,
                       silence, taskgraph)


@pytest.fixture(scope="module")
def log():
    return ingest.read_xes(ingest.default_log_path())


@pytest.fixture(scope="module")
def live(log):
    return ingest.valid(log, drop_failure=True)


@pytest.fixture(scope="module")
def graph(log):
    pos = {p for a in log for p in (a.start_pos, a.end_pos) if p}
    return taskgraph.load_bpmn(log_positions=pos)


@pytest.fixture(scope="module")
def recs(live, graph):
    return coverage.realized(live, graph)


# ---- A. 与 paper02 对数 -------------------------------------------------

def test_log_scale_matches_paper02(log, live):
    assert len(log) == 3157
    assert len(live) == 3062
    assert len({a.case for a in live}) == 282
    assert len({a.device for a in live}) == 15
    assert len({a.op for a in live}) == 21


def test_bpmn_extraction_matches_paper02(graph):
    assert graph.n_models == 16
    assert len(graph.resources) == 15
    assert len(graph.operations) == 21
    assert len(graph.positions) == 23
    assert len(graph.move_graph) == 31


def test_device_stateless_so_unit_is_handover(live):
    """paper02 结论 4:本产线设备无跨作业状态机,65.1% 的 (设备, case) 链长度
    为 1。这是 TESSERA 把观测单元取为交接事件而非设备内转移的直接理由,
    若此结论在别的数据集上不成立,互证的建模单元需要重新论证。
    """
    chains = ingest.split_chains(live)
    assert len(chains) == 2109
    frac1 = sum(1 for v in chains.values() if len(v) == 1) / len(chains)
    assert 0.645 < frac1 < 0.655
    assert sum(max(0, len(v) - 1) for v in chains.values()) == 953


# ---- B. 互证超图与覆盖度(本文的新测量)---------------------------------

def test_witness_graph_scale(graph):
    assert len(graph.witness_edges) == 185
    assert len(graph.handover_positions) == 14
    assert len({e.producer for e in graph.witness_edges}) == 18


def test_witness_set_is_o1(graph):
    """见证集合规模是 O(1) 主张的实测依据:中位 1、最大 6,与设备总数无关。

    这是"见证集合由任务图而非无线拓扑决定"的可检验后果——若见证集合随规模
    增长,不需要全网 BFT 的论证就不成立。
    """
    sizes = [len({e.consumer for e in graph.witness_edges
                  if e.producer == p})
             for p in {e.producer for e in graph.witness_edges}]
    assert max(sizes) == 6
    assert sorted(sizes)[len(sizes) // 2] == 1


def test_no_counterparty_region_is_hbw_storage(graph):
    """模型上无对手方的只有三个入库操作。这是按需主动互证的靶区,规模很小
    且语义一致(工件进入仓库后本 case 内不再有人接手),不是随机的建模缺口。
    """
    assert coverage.no_counterparty_ops(graph) == {
        ("hbw", "/hbw/store"),
        ("hbw", "/hbw/store_empty_bucket"),
        ("hbw", "/hbw/get_empty_bucket"),
    }


def test_corroboration_coverage(recs):
    s = coverage.summarize(recs)
    assert s["n_activities"] == 3062
    assert s["n_corroborated"] == 2145
    assert s["n_same_device_only"] == 228
    assert s["n_no_realized"] == 183
    assert s["n_no_model"] == 506
    assert 0.700 < s["frac_corroborated"] < 0.701


def test_case_terminal_activities_are_structurally_uncoverable(recs):
    """每个 case 的末位活动都无下游接手方,282 个 case 恰好贡献 282 个缺口。

    这不是缺陷:它是互证覆盖的**结构上界**,与 paper02 那个"二元可行性掩码
    只覆盖 31% 的消息"同类。去掉末位活动后链中覆盖率为 2145/2780 = 77.2%,
    论文中报告覆盖率时必须同时给出这两个口径。
    """
    s = coverage.summarize(recs)
    assert s["n_gap_terminal"] == 282
    assert s["n_gap_midchain"] == 635
    midchain = s["n_activities"] - s["n_gap_terminal"]
    assert midchain == 2780
    assert 0.771 < s["n_corroborated"] / midchain < 0.772


def test_cross_instance_handover_is_not_self_corroboration(recs):
    """见证独立性必须按设备实例判定。按设备类判会把 vgr_2 -> vgr_1 的跨产线
    交接误判为自证,实测代价是 VGR 覆盖率从 80.6% 掉到 62.6%、总覆盖率从
    70.05% 掉到 64.89%。
    """
    vgr = [r for r in recs if r.act.op == "/vgr/pick_up_and_transport"]
    assert len(vgr) == 880
    ok = sum(1 for r in vgr if r.status == coverage.OK)
    assert ok == 709
    cross = [r for r in vgr if r.status == coverage.OK
             and r.witness.device != r.act.device
             and taskgraph.device_class(r.witness.device)
             == taskgraph.device_class(r.act.device)]
    assert len(cross) > 100


def test_corroboration_window(recs):
    """互证窗口 Δ 的实测分布,决定 pending 超时该取多大。

    中位 6.7 s 而 p95 达 119.7 s,长尾来自调度排队而非物理交接——paper02 已
    实测派发阶段时长 p95 为 253.6 s、sigma_log=1.475,由调度器排队竞争主导。
    因此 Δ 不能按分位数一刀切,须以命令账本的计划时刻为基准,这一点在
    corroborate.py 实现时必须处理,否则 P1 的检测时延会被排队噪声吞掉。
    """
    s = coverage.summarize(recs)
    assert s["delay_n"] == 2145
    assert s["delay_negative"] == 1
    assert 6.0 < s["delay_median_s"] < 7.5
    assert 100 < s["delay_p95_s"] < 130


# ---- C. 可问责沉默 -----------------------------------------------------

def _commit(length=32, t_hb=1.0, device="vgr_1", session="s1"):
    sk, pk = crypto.new_keypair()
    ch = crypto.HashChain(device, session, length=length)
    c = crypto.sign_commitment(
        crypto.Commitment(device, session, ch.root, length,
                          t0=0.0, t_hb_s=t_hb), sk)
    return ch, c, pk


def test_c1_chain_roundtrip_and_signed_root():
    ch, c, pk = _commit()
    assert crypto.verify_root(c, pk)
    assert len(ch.root) == crypto.TOKEN_BYTES == 16
    mon = silence.SilenceMonitor(silence.SilenceConfig(t_hb_s=1.0))
    mon.register(c)
    for k in (1, 2, 3, 7):
        assert mon.on_reveal("vgr_1", k, ch.element(k), now=k - 0.5) is None
    # 正常情况每槽一次哈希;跳槽时按跨度补齐,这是开销记账的依据
    assert mon.n_hashes == 1 + 1 + 1 + 4


def test_c2_forged_preimage_is_transferable_evidence():
    """伪造原像必被拒。这是"路 3 自证其罪"的实现:一旦披露,该披露本身连同
    已签名的承诺根就构成可交第三方核验的证据。
    """
    ch, c, _ = _commit()
    mon = silence.SilenceMonitor(silence.SilenceConfig(t_hb_s=1.0))
    mon.register(c)
    v = mon.on_reveal("vgr_1", 1, b"\x00" * crypto.TOKEN_BYTES, now=0.5)
    assert v is not None and v.kind == silence.FORGED
    assert v.evidence == b"\x00" * crypto.TOKEN_BYTES
    # 被拒的披露不得推进链状态,否则攻击者可用垃圾值把验证者顶到未来槽
    assert mon.on_reveal("vgr_1", 1, ch.element(1), now=0.6) is None


def test_c3_early_reveal_is_rejected():
    """前置条件 2:槽 k 内披露槽 k+1 的元素会让验证者据此推出槽 k 的元素,
    等于预付未来的沉默。这是 TESLA 一族的已知问题,必须显式拒绝。
    """
    ch, c, _ = _commit()
    mon = silence.SilenceMonitor(silence.SilenceConfig(t_hb_s=1.0))
    mon.register(c)
    v = mon.on_reveal("vgr_1", 5, ch.element(5), now=0.5)
    assert v is not None and v.kind == silence.EARLY


def test_c4_silent_verdict_is_deterministic_in_time():
    """SILENT 的判决时刻恰为 r*T_hb + skew,不早不晚。

    这是"确定性判据而非怀疑"的可检验含义,也是 T_detect 能代入 FHI 预算的
    前提——若判决时刻取决于统计量的抖动,时延就没有确定上界。
    """
    cfg = silence.SilenceConfig(t_hb_s=1.0, r_misses=3, skew_s=0.01)
    _, c, _ = _commit(t_hb=1.0)
    mon = silence.SilenceMonitor(cfg)
    mon.register(c)
    assert mon.sweep(2.5) == []
    out = mon.sweep(10.0)
    assert len(out) == 1 and out[0].kind == silence.SILENT
    assert abs(out[0].t_decide - cfg.detect_delay_s) < 1e-9
    assert mon.revoked() == {"vgr_1"}


def test_c5_miss_counter_resets_on_valid_reveal():
    """反例保护。paper02 记录漏掉复位使检出率虚高 22 倍。"""
    cfg = silence.SilenceConfig(t_hb_s=1.0, r_misses=3, skew_s=0.01)
    ch, c, _ = _commit(t_hb=1.0)
    mon = silence.SilenceMonitor(cfg)
    mon.register(c)
    mon.sweep(2.5)                                    # 槽 1、2 缺失
    assert mon.on_reveal("vgr_1", 3, ch.element(3), now=2.6) is None
    assert mon.sweep(5.5) == []                       # 槽 4、5 缺失但已复位
    assert mon.sweep(6.5) and mon.revoked() == {"vgr_1"}


def test_c6_domain_separation_blocks_transplant():
    """同 seed 在不同设备或会话下产生不同链,故凭证不可跨设备/跨会话搬运。"""
    seed = b"\x11" * 32
    a = crypto.HashChain("vgr_1", "s1", length=8, seed=seed)
    b = crypto.HashChain("vgr_2", "s1", length=8, seed=seed)
    d = crypto.HashChain("vgr_1", "s2", length=8, seed=seed)
    assert a.root != b.root and a.root != d.root
    _, c, _ = _commit()
    mon = silence.SilenceMonitor(silence.SilenceConfig(t_hb_s=1.0))
    mon.register(c)
    v = mon.on_reveal("vgr_1", 1, b.element(1), now=0.5)
    assert v is not None and v.kind == silence.FORGED


def test_c7_burst_loss_inflates_required_r():
    """突发丢包是本机制误报率主张的真实威胁,必须按突发口径选 r。

    p=1e-2、T_hb=0.2 s、28 台设备、误报预算 1 次/小时:独立丢包下 r=3 就够,
    但同一个 r 在 rho=0.3 下的误报率是 475 次/小时——高出近三个数量级,设计
    完全失效。按突发口径需 r=9,代价只是时延从 0.61 s 到 1.81 s。
    """
    p, t, n = 1e-2, 0.2, 28
    r0 = silence.min_misses(p, t, n, 1.0)
    rb = silence.min_misses(p, t, n, 1.0, burst_rho=0.3)
    assert r0 == 3 and rb == 9
    naive = silence.far_per_hour(
        p, silence.SilenceConfig(t_hb_s=t, r_misses=r0), n, burst_rho=0.3)
    assert 400 < naive < 550
    ok = silence.far_per_hour(
        p, silence.SilenceConfig(t_hb_s=t, r_misses=rb), n, burst_rho=0.3)
    assert ok <= 1.0
    assert abs(silence.SilenceConfig(t_hb_s=t, r_misses=rb).detect_delay_s
               - 1.81) < 0.01


def test_c8_silence_q_is_a_design_parameter_unlike_interlock():
    """沉默通道逃出天花板的机理:q 可由 r 自由压低,而互锁的 q 是数据性质。

    paper02 实测互锁部署流 q=0.047、天花板 0.021,且近似身份解析只能压到
    0.023——压不动。沉默通道在 p=1e-2 时 r=1 的天花板确实只有 0.1(此时天花板
    生效),但 r=2 即解开。故本文可把它作硬层,而 paper02 只能把互锁作软证据。
    """
    alpha = 0.001
    assert silence.power_ceiling(alpha, 0.047) < 0.03      # 互锁,压不动
    assert silence.power_ceiling(alpha, silence.far_prob(1e-2, 1)) == 0.1
    assert silence.power_ceiling(alpha, silence.far_prob(1e-2, 2)) == 1.0
    # 突发口径下同样解开
    assert silence.power_ceiling(
        alpha, silence.far_prob(1e-2, 3, burst_rho=0.3)) == 1.0


def test_c9_bandwidth_depends_on_t_hb_only():
    """r 花时延不花带宽。这是相对周期性共识的结构优势——省的是共识频率 R。"""
    a = silence.SilenceConfig(t_hb_s=0.2, r_misses=3)
    b = silence.SilenceConfig(t_hb_s=0.2, r_misses=9)
    assert a.bandwidth_bps(28) == b.bandwidth_bps(28)
    assert abs(a.bandwidth_bps(28) - 2240.0) < 1e-6
    # 时延近似线性于 r,略低于 3 倍是因为时钟容差只计一次
    assert abs(b.detect_delay_s / a.detect_delay_s - 2.967) < 0.01
    # 与周期性 PBFT 的量级差
    pbft = silence.pbft_bandwidth_bps(28, 10.0)
    assert pbft / a.bandwidth_bps(28) > 800


def test_c10_silence_is_far_faster_than_corroboration_alone(live):
    """组合的必要性之一的定量依据。

    设备沉默时,任务完成类判定只能等超时,而超时窗口必须容纳**调度器自己的派发
    排队**(本日志实测 p95 218.3 s,容差取 260 s),否则良性流误报四分之一。
    于是 P2 的互证/看门狗时延中位 325–334 s,而可问责沉默在突发口径下 1.81 s
    即判定,快 180 倍以上。

    机理差别比倍数更重要:心跳判定的是设备的**状态声明**而非任务完成,与调度
    队列完全解耦,故 r·T_hb 是无条件上界;任务完成类判定只有条件上界。
    安全裕度定理应当接前者。
    """
    planned = [a.planned_s for a in live if a.planned_s]
    assert len(planned) == 3062
    assert abs(median(planned) - 45.0) < 0.01
    cfg = silence.SilenceConfig(t_hb_s=0.2, r_misses=9)
    ccfg = corroborate.CorroborateConfig()
    assert abs(ccfg.corr_window_s(45.0) - 332.5) < 0.01
    assert ccfg.corr_window_s(45.0) / cfg.detect_delay_s > 180


# ---- D. 攻击注入与互证协议 ---------------------------------------------

RATE, SEED = 0.2, 42


@pytest.fixture(scope="module")
def p1(recs):
    return attacks.AttackSpec(family=attacks.P1, rate=RATE, seed=SEED)


def _run(recs, graph, family, *, refute=True, cfg=None):
    spec = attacks.AttackSpec(family=family, rate=RATE, seed=SEED,
                              explicit_refutation=refute)
    reports, _ = attacks.inject(recs, spec)
    primary = {id(r) for r in reports if r.forged and not r.accomplice}
    accomp = {id(r) for r in reports if r.accomplice}
    proto = corroborate.replay(reports, graph, cfg, refute=refute)
    hit = [e for e in proto.evidence if e.claim_id in primary]
    return {
        "reports": reports, "proto": proto, "primary": primary,
        "accomp": accomp, "hit": hit,
        "dr": len({e.claim_id for e in hit}) / max(len(primary), 1),
        "lat": [e.latency_s for e in hit],
        "dr_acc": len({e.claim_id for e in proto.evidence
                       if e.claim_id in accomp}) / max(len(accomp), 1),
        "secondary": [e for e in proto.evidence if e.claim_seen
                      and e.claim_id not in primary
                      and e.claim_id not in accomp],
    }


def test_d1_forged_claim_is_field_identical_to_benign(recs, p1):
    """P1 的构造性质:伪造声明在**每个单观测者可见字段**上都与良性一致。

    这比重跑一遍 paper02 的残差检测器更强的主张——它说明残差类方法在本问题上
    的失效是**构造上的**,不是参数没调好。时长取该 (设备, 操作) 的良性中位数,
    故必然落在四分位距内,纵向检验无残差可用。
    """
    rep = attacks.indistinguishability_report(recs, p1)
    assert rep["n_forged"] == 363
    assert all(v == 1.0 for v in rep["fields_intact"].values())
    assert set(rep["fields_intact"]) == {
        "device", "op", "case", "workflow", "start_pos", "end_pos", "outcome"}
    assert rep["duration_in_iqr"] == 1.0


def test_d2_benign_false_alarm_rate(recs, graph):
    """良性流上互证的误报率 2.25%。

    分母口径必须钉死:只算**声明确实到达过**的 pending。声明从未到达的
    (case 末位、对手方从未被派发) 是结构性覆盖缺口,把它们算进误报会把
    2.25% 说成 6.34%,算进检出则会把缺口伪装成能力。
    """
    proto = corroborate.replay(attacks.benign_stream(recs), graph)
    armed = [e for e in proto.evidence if e.claim_seen]
    assert len(armed) == 69
    assert abs(len(armed) / len(recs) - 0.0225) < 0.0005
    assert proto.counts[corroborate.CONFIRMED] == 1961
    assert proto.counts[corroborate.UNWITNESSED] == 506
    assert proto.counts[corroborate.NOT_DISPATCHED] == 401


def test_d3_corroboration_catches_false_completion(recs, graph):
    """P1/P3 的互证检出率 1.000,时延中位 54.6 s。

    对手方装有到料光电门时,判决在它尝试取件的那一刻产生(349/363 由否证达成),
    远早于窗口到期。无传感器的褐地设备只能等超时,检出率降到 0.860、时延中位
    升到 365 s——传感器覆盖度直接决定检测时延,这是部署侧的可操作结论。
    """
    for fam in (attacks.P1, attacks.P3):
        r = _run(recs, graph, fam)
        assert len(r["primary"]) == 363
        assert r["dr"] == 1.0
        assert abs(median(r["lat"]) - 54.6) < 0.5
        n_ref = sum(1 for e in r["hit"]
                    if e.outcome == corroborate.REFUTED)
        assert n_ref == 349
    blind = _run(recs, graph, attacks.P1, refute=False)
    assert abs(blind["dr"] - 0.860) < 0.005
    assert median(blind["lat"]) > 300


def test_d4_p3_escapes_silence_entirely(recs, graph):
    """消融表最关键的一行:老练谎报者按时披露原像,沉默机制毫无信号。

    P3 的伪造声明 `revealed=True`,原像逐槽按时披露,可问责沉默的检出率为 0;
    只有耦合互证能抓(1.000)。这是耦合互证**不可被替代**的直接证据。
    反过来 P1 的朴素谎报者不维持心跳,两个机制都能抓——两族必须分开跑,
    否则消融表读不出"各自都有对方覆盖不到的攻击"。
    """
    p3 = _run(recs, graph, attacks.P3)
    assert all(r.revealed for r in p3["reports"] if r.forged)
    assert p3["dr"] == 1.0
    p1 = _run(recs, graph, attacks.P1)
    assert not any(r.revealed for r in p1["reports"] if r.forged)
    assert p1["dr"] == 1.0
    # 沉默机制的检出口径:原像是否按槽披露
    assert sum(1 for r in p3["reports"] if r.forged and not r.revealed) == 0
    assert sum(1 for r in p1["reports"] if r.forged and not r.revealed) == 363


def test_d5_dispatch_allowance_is_not_optional(recs, graph):
    """派发排队容差不可省:省了良性流总告警从 6.34% 涨到 21.42%。

    本日志实测派发时延(命令下发到开始动作)中位仅 4.4 s,但 p95 达 218.3 s、
    max 1476.4 s,与 paper02 独立测得的 p95 253.6 s 吻合。这段等待由调度器
    自己的队列决定,与交接无关。

    容差换的是误报、付的是最坏检测时延:260 s 处总告警已降到平台(声明已到达
    的那一档从 130 s 起就稳定在 2.25%),再加只增时延不减误报。代价必须如实
    写进论文——任务完成类判定只有**条件**上界,无条件上界靠可问责沉默给出。
    """
    disp = sorted((r.act.t_start - r.act.t_cmd).total_seconds()
                  for r in recs if r.act.t_cmd and r.act.t_start)
    assert len(disp) == 3062
    assert abs(disp[len(disp) // 2] - 4.4) < 0.2
    assert abs(disp[round(0.95 * (len(disp) - 1))] - 218.3) < 1.0
    assert disp[-1] > 1400.0
    bs = attacks.benign_stream(recs)
    naive = corroborate.replay(
        bs, graph, corroborate.CorroborateConfig(dispatch_allowance_s=0.0))
    tuned = corroborate.replay(bs, graph)
    assert abs(len(naive.evidence) / len(recs) - 0.2142) < 0.0005
    assert abs(len(tuned.evidence) / len(recs) - 0.0634) < 0.0005
    # 声明已到达那一档从 130 s 起饱和,再加容差只增时延
    mid = corroborate.replay(
        bs, graph, corroborate.CorroborateConfig(dispatch_allowance_s=130.0))
    assert len([e for e in mid.evidence if e.claim_seen]) == 69


def test_d6_one_hop_collusion_only_defers_the_verdict(recs, graph):
    """P4 一跳串谋只把判决推迟一跳,并未逃脱。

    串谋方为上游的假交接背书,主受害者的声明因此提交(检出率仅 0.184);但串谋方
    自己也没收到工件,它随后的交付声明同样是假的,被**它自己的下游**诚实设备
    否证(0.750)。所以谎言要活到工件真正被消耗,链上每一跳都需一台被劫持设备。

    这条断言防的是一个具体的低估:若注入器不建模链式传播,串谋方的检出率会测成
    0.002,于是把能力边界说得比实际宽得多。
    """
    r = _run(recs, graph, attacks.P4)
    assert len(r["primary"]) == 375
    assert len(r["accomp"]) == 304
    assert abs(r["dr"] - 0.184) < 0.01
    assert abs(r["dr_acc"] - 0.750) < 0.01
    assert r["dr_acc"] > 4 * r["dr"]


def test_d7_watchdog_is_blind_to_false_reports(recs, graph):
    """看门狗基线 S1 对 P1/P3/P4 全无能力。

    IEC 61850 GOOSE 的 MaxTime 心跳与 fail-safe 只管"该报的没报",被一条按时
    到达、字段完全正常的伪造声明完全满足。它对 P2 有效(1.000),但时延同样要
    容纳派发队列(334 s),故也不是可问责沉默的替代品。
    """
    for fam in (attacks.P1, attacks.P3, attacks.P4):
        reports, _ = attacks.inject(
            recs, attacks.AttackSpec(family=fam, rate=RATE, seed=SEED))
        assert not any(r.withheld for r in reports if r.forged)
    reports, _ = attacks.inject(
        recs, attacks.AttackSpec(family=attacks.P2, rate=RATE, seed=SEED))
    forged = [r for r in reports if r.forged]
    assert forged and all(r.withheld for r in forged)


def test_d8_silence_causes_collateral_accusation_of_upstream(recs, graph):
    """次生告警:沉默的设备同时**拒绝为其上游作证**,连带指控无辜邻居。

    P2 下有 277 条诚实声明因其下游沉默而超时。这不是协议误报(良性流上只有
    69 条),而是攻击的真实后果,也是必须与可问责沉默合用的第二个理由——沉默
    机制直接指认沉默者,上游的未确认声明才能被正确归因而非被冤枉。
    """
    p2 = _run(recs, graph, attacks.P2)
    assert len(p2["secondary"]) == 277
    benign = corroborate.replay(attacks.benign_stream(recs), graph)
    assert len([e for e in benign.evidence if e.claim_seen]) == 69
    assert len(p2["secondary"]) > 4 * 69


def test_d9_attack_numbering_matches_the_document():
    """反例保护(paper02 规则 8):编号错位会让论文里每个编号都是错的。"""
    assert attacks.IMPLEMENTED == ("P1", "P2", "P3", "P4")
    assert attacks.FAMILY_ZH == {"P1": "谎报完成", "P2": "完全沉默",
                                 "P3": "假称合法", "P4": "串谋"}
    with pytest.raises(NotImplementedError):
        attacks.inject([], attacks.AttackSpec(family="P5"))


# ---- E. 串谋界 -----------------------------------------------------------

@pytest.fixture(scope="module")
def chains(recs):
    return collusion.walk(recs)


def test_e1_collusion_scope_and_denominator(recs, chains):
    """作用域的两条边界都必须钉死,方向相反,任一错了都会歪。

    **剔除 `NO_REALIZED`(183 条)**:链长 1、k=1,但那不是"一台设备就够串谋",
    而是本 case 内根本无人接手,属覆盖率缺口。混进来把 k_min 压到 1 的理由是
    错的。

    **保留 `SELF_ONLY`(228 条)**:该跳确实没有独立见证,但它是攻击者可以真实
    瞄准的活动,谎言仍要在下游被截住,k 有意义。排除它等于替机制挑掉最不利的
    样本——实测这 228 条里就藏着全部 23 条 k=1 的链。

    这条口径与 `coverage.py` 的覆盖率分母**故意不同**:覆盖率问"这一跳有没有
    独立证据",串谋界问"永久藏住要买通几台设备",后者天然跨跳。
    """
    scoped = collusion.in_scope(chains)
    assert len(chains) == 2556
    assert len(scoped) == 2373
    dropped = [c for c in chains if c.origin.status == coverage.NO_REALIZED]
    assert len(dropped) == 183
    assert all(c.k == 1 and c.n_hops == 1 for c in dropped)
    kept_self = [c for c in scoped if c.origin.status == coverage.SELF_ONLY]
    assert len(kept_self) == 228
    assert all(c.origin.status == coverage.SELF_ONLY
               for c in scoped if c.k == 1)


def test_e2_measured_collusion_bound(chains):
    """实测串谋界:k_min=1、中位 5、max 13,k>=3 占 80.99%。

    可写进论文的陈述:"任务状态伪造要永久隐藏,中位需五台设备同时被劫持,
    81% 的情形需三台以上;但存在 23 条最坏链只需一台"——最坏情形必须报,
    它正是按需主动互证的靶区。均值无意义,攻击者挑最薄弱处下手。
    """
    s = collusion.summarize(chains)
    assert s["k_min"] == 1
    assert s["k_median"] == 5
    assert s["k_max"] == 13
    assert abs(s["frac_k_ge_3"] - 0.8099) < 0.0005
    assert s["n_k1"] == 23
    # k=1 全部来自同设备免费跳,这决定了它只能靠按需主动互证而非改派工来修
    assert s["n_k1_free_hop"] == 23
    assert s["hops_max"] == 17


def test_e3_same_device_handover_extends_the_lie_for_free(chains):
    """同设备接手不引入新的作证者,攻击者不需额外劫持任何设备即可推进一跳。

    这把 coverage 那 7.45% 的同设备缺口从"覆盖率数字"变成**具体的安全代价**:
    1,627 条链共获得 1,945 个免费跳。免费跳无法靠改派工消除(工件仍夹在机床
    夹具里),只能靠按需主动互证补上。
    """
    s = collusion.summarize(chains)
    assert s["n_free_hop_chains"] == 1627
    assert s["free_hops_total"] == 1945
    assert abs(s["frac_device_reuse"] - 0.7273) < 0.0005
    free = [c for c in collusion.in_scope(chains) if c.free_hops]
    assert all(c.n_hops > c.k for c in free)


def test_e4_security_aware_assignment_is_a_negative_result(recs):
    """增补一在本产线上是**负面结果**,必须如实报。

    可达理想派工(只消除非相邻复用)下:k_min 1 -> 1、中位 5 -> 5,纹丝不动;
    只有均值从 5.13 抬到 5.80。原因由增益分布给出:1,282 条可改善的链里,原本
    k<=2 的只有 **14 条**,增益几乎全落在 k>=5 即**本来就安全**的链上。

    两个不可排产化解的来源:相邻同设备接手(23 条 k=1 全属此类,工件仍在夹具
    里),以及工艺流程本身的层数(模型级下界 2)。

    因此增补一的正确定位不是"提高安全保证",而是"在不牺牲产能的前提下改善
    分布均值"。写成前者是 overclaim,这条断言就是防它。
    """
    ga = collusion.assignment_gain(recs)
    assert ga["k_min_actual"] == ga["k_min_achievable"] == 1
    assert ga["k_median_actual"] == ga["k_median_achievable"] == 5
    assert abs(ga["k_mean_actual"] - 5.13) < 0.01
    assert abs(ga["k_mean_achievable"] - 5.80) < 0.01
    assert ga["n_improvable"] == 1282
    assert ga["n_improvable_at_k_le_2"] == 14
    assert ga["reuse_by_device"][0] == ("vgr_1", 1263)
    # 无约束理想会虚报:k_min 被说成从 1 抬到 2
    assert ga["k_min_unconstrained"] == 2
    sw = collusion.same_class_reuse(recs)
    assert sw["n_swappable"] == 1282
    assert sw["n_adjacent_only"] == 444
    assert sw["n_single_instance"] == 0


def test_e5_structural_bound_is_per_workflow(graph):
    """模型级下界必须逐工作流算,合并 16 个模型的邻接会把界虚高。

    一个 case 只走一条工艺路线,攻击者要买通的也只是那条路线上的设备。逐流算得
    k_min=2(WF_108/WF_121 的 wt 搬运只有两层独立见证),中位 8。这个量是过程
    模型的性质,不随排产变化,因此可作设计期指标——也正是它决定了实测 k_min
    同样是 2。
    """
    st = collusion.structural_bound(graph)
    assert st["n_workflows"] == 16
    assert st["k_min"] == 2
    assert st["k_median"] == 8
    assert st["worst_workflow_k"] == 2
    weakest = {wf for (wf, _), k in st["weakest_nodes"] if k == 2}
    assert weakest == {"WF_108", "WF_121"}
    assert all(op == "/wt/pick_up_and_transport"
               for (_, (_dc, op)), k in st["weakest_nodes"] if k == 2)


def test_e6_bound_and_p4_injection_corroborate_each_other(recs, graph, chains):
    """两条独立算出的路径互为佐证。

    结构上 k<=2 的链占 19.0%,即一跳串谋应有约这么大比例能永久藏住;detect_diag
    实测串谋方逃脱率 25.0%(1-0.750)。同一量级,差额来自串谋方自身链上的覆盖
    缺口。这不是精确相等的关系,论文里只能说"同量级、可互为佐证",不能写成
    "定量吻合"。
    """
    s = collusion.summarize(chains)
    h = dict(s["k_hist"])
    frac_k2 = (h[1] + h[2]) / s["n_in_scope"]
    assert h[2] == 428
    assert abs(frac_k2 - 0.190) < 0.002
    r = _run(recs, graph, attacks.P4)
    escape = 1.0 - r["dr_acc"]
    assert abs(escape - 0.250) < 0.01
    assert 1.0 < escape / frac_k2 < 3.0     # 同量级,不主张精确吻合


# ---- F 组:带宽—安全裕度预算(budget.py)--------------------------------

_BKW = dict(p_loss=1e-2, n_devices=28, far_target_per_hour=1.0)


@pytest.fixture(scope="module")
def budgets():
    """两种危害模型给出的两个预算,以及 ISO 3691-4 算例防护场。"""
    pf = budget.protective_field_mm()
    return (budget.SafetyBudget(),
            budget.SafetyBudget.from_protective_field(field_mm=pf["field_mm"]),
            pf)


def test_f1_only_silence_can_be_plugged_into_the_time_budget(budgets):
    """时间预算只能接可问责沉默,接互证是接错量纲。

    沉默的 r*T_hb+skew 与调度队列解耦,是**无条件**上界。互证窗口必须容纳派发
    排队(实测 p95 218.3 s),连最松的汽车口径检测预算 2.18 s 都超出 100 倍,
    而排队本身没有上界——所以那不是"数大一点",是**没有上界可代**。

    这条断言防的是论文里把两条路径并列写成"都提供时延界"。
    """
    auto, motion, _ = budgets
    assert abs(auto.detect_budget_s - 2.18) < 1e-9
    assert abs(motion.detect_budget_s - 0.60) < 1e-9
    # 沉默:在最严口径下仍能落进预算
    d = budget.cheapest(motion, burst_rho=0.3, **_BKW)
    assert d is not None and motion.admits(
        silence.SilenceConfig(t_hb_s=d.t_hb_s, r_misses=d.r_misses))
    # 互证:仅派发容差一项就把最松预算顶穿
    corr = corroborate.CorroborateConfig()
    assert corr.dispatch_allowance_s / auto.detect_budget_s > 100


def test_f2_borrowed_automotive_fhi_is_too_loose_for_a_factory_agv(budgets):
    """借用汽车领域的 FHI 会**太松**,这是本模块最要紧的一条。

    FHI=2.43 s 留给检测 2.18 s,1.5 m/s 的 AGV 在这段时间里走 3.27 m,是 ISO
    3691-4 算例防护场(1.275 m)的 **256%**——车早已冲出安全包络,预算却还说
    "合规"。故通用 FHI 不能直接搬进工厂场景。

    正确做法是让危害模型定预算(FHI = field / v),得 0.85 s、检测 0.60 s,
    对应行驶 0.90 m = 防护场的 71%,落在包络内。
    """
    auto, motion, pf = budgets
    assert abs(pf["field_mm"] - 1275.0) < 1e-9
    ratio_auto = budget.detection_travel_mm(auto.detect_budget_s) / pf["field_mm"]
    ratio_mo = budget.detection_travel_mm(motion.detect_budget_s) / pf["field_mm"]
    assert abs(ratio_auto - 2.565) < 0.002      # 256%,超出包络
    assert abs(ratio_mo - 0.706) < 0.002        # 71%,落在包络内
    assert ratio_auto > 1.0 > ratio_mo


def test_f3_motion_derived_budget_still_admits_a_cheap_design(budgets):
    """预算收紧后仍有可行解,代价是带宽变贵——如实报,不藏。

    运动危害口径(检测预算 0.60 s)下最省配置 T_hb=0.194 s、r=3、2,311 B/s。
    对照汽车口径的 621 B/s,收紧预算的价格是 3.7 倍带宽。这是"把安全论断对齐到
    真实危害模型"的价格,不是方法的缺陷。
    """
    auto, motion, _ = budgets
    a = budget.cheapest(auto, burst_rho=0.0, **_BKW)
    m = budget.cheapest(motion, burst_rho=0.0, **_BKW)
    assert a.r_misses == m.r_misses == 3
    assert abs(a.bandwidth_bps - 620.9) < 0.5
    assert abs(m.bandwidth_bps - 2311.2) < 0.5
    assert abs(m.t_hb_s - 0.1938) < 0.0005
    assert abs(m.bandwidth_bps / a.bandwidth_bps - 3.72) < 0.01


def test_f4_burst_tolerance_has_a_bandwidth_price(budgets):
    """突发容忍的带宽代价 = 3.32x。本模块最可引用的一条。

    机理是两步:突发口径把所需 r 从 3 抬到 10(断言 C7 的同一效应),同一安全
    预算于是把 T_hb 从 0.194 s 压到 0.058 s,而带宽只由 T_hb 决定(断言 C9),
    故带宽按 T_hb 的比值上涨。

    只报独立丢包口径的带宽是不诚实的:工业无线的丢包成簇。
    """
    _, motion, _ = budgets
    p = budget.burst_premium(motion, burst_rho=0.3, **_BKW)
    a, c = p["independent"], p["bursty"]
    assert (a.r_misses, c.r_misses) == (3, 10)
    assert abs(p["premium"] - 3.32) < 0.01
    assert abs(c.bandwidth_bps - 7674.6) < 0.5
    # 代价确实只经由 T_hb 传导,r 本身不花带宽
    assert abs(p["premium"] - a.t_hb_s / c.t_hb_s) < 1e-9


def test_f5_the_optimum_sits_on_the_safety_boundary(budgets):
    """最优解顶在安全边界,故论文可以说"带宽受安全约束限制"。

    4 个口径中 3 个纯粹顶在安全边界(余量 <1.5%),1 个(汽车口径 + 突发)
    两条边界同时顶满(安全余量 1.2%、误报余量 3.3%)。后者必须说"同时",
    只说安全会失掉一半信息——这就是 `slack` 存在的理由。
    """
    auto, motion, _ = budgets
    got = {}
    for name, b in (("auto", auto), ("motion", motion)):
        for rho in (0.0, 0.3):
            d = budget.cheapest(b, burst_rho=rho, **_BKW)
            got[(name, rho)] = budget.binding_constraint(
                d, b, burst_rho=rho, **_BKW)
            assert budget.slack(d, b, 1.0)["safety_slack"] < 0.015
    assert got[("auto", 0.3)] == budget.BOTH
    assert [got[k] for k in (("auto", 0.0), ("motion", 0.0),
                             ("motion", 0.3))] == [budget.SAFETY] * 3


def test_f6_still_two_orders_cheaper_than_pbft_at_the_strictest_setting(budgets):
    """最严口径(运动危害 + 突发丢包)下仍比周期性 PBFT 便宜两个数量级。

    7.7 KB/s 对 PBFT 5 Hz 的 1.00 MB/s = 131 倍。这条必须用**最贵**的自家
    配置去比,用最省的 621 B/s 比会得到 1,616 倍——那是挑口径,审稿人一查就穿。

    省下的是共识频率 R,不是参与节点数,故容错阈值未降低(paper02 规则:
    对照必须在同一容错前提下)。
    """
    _, motion, _ = budgets
    c = budget.cheapest(motion, burst_rho=0.3, **_BKW)
    pbft = silence.pbft_bandwidth_bps(28, 5.0)
    assert abs(pbft - 1003520.0) < 1.0
    assert abs(pbft / c.bandwidth_bps - 130.7) < 0.5
    assert 100 < pbft / c.bandwidth_bps < 1000


def test_f7_infeasible_budget_must_be_reported_not_papered_over(budgets):
    """预算给不出方案时返回 None,而不是悄悄放宽误报预算。

    FHI=0.05 s 时突发口径无解:所需 r>=10 与 skew=0.01 s 已把时延顶穿。这是
    有意义的工程结论(须调 FHI、换网络或降设备数),不是异常。
    """
    tight = budget.SafetyBudget(fhi_s=0.05, t_react_s=0.02)
    assert budget.cheapest(tight, burst_rho=0.3, **_BKW) is None
    assert budget.feasible(tight, burst_rho=0.3, **_BKW) == []
    # 放宽误报预算能换回可行解——正是不该悄悄做的那件事
    loose = dict(_BKW, far_target_per_hour=1e4)
    assert budget.cheapest(tight, burst_rho=0.3, **loose) is not None


# ---- G 组:见证选取规则的基线对照(baselines.py)--------------------------

def _bl(recs, graph, family, **kw):
    """同一协议下跑一条基线:良性误报 + P1 检出。公平性由此保证。"""
    pol = baselines.make(family, graph, **kw)
    benign = corroborate.replay(attacks.benign_stream(recs), graph, policy=pol)
    far = len([e for e in benign.evidence if e.claim_seen]) / len(recs)
    reports, _ = attacks.inject(recs, attacks.AttackSpec(
        family=attacks.P1, rate=RATE, seed=SEED, explicit_refutation=True))
    primary = {id(r) for r in reports if r.forged and not r.accomplice}
    proto = corroborate.replay(reports, graph, policy=pol, refute=True)
    hit = {e.claim_id for e in proto.evidence if e.claim_id in primary}
    return {"far": far, "dr": len(hit) / len(primary),
            "sizes": [x for x in baselines.witness_set_sizes(pol, recs) if x],
            # 悬而未决数取**良性流**上的，与 baseline_diag 第三节同口径
            "unresolved": benign.counts.get(corroborate.NOT_DISPATCHED, 0)}


def test_g1_witness_eligibility_must_not_be_checked_by_class(recs, graph):
    """**反例保护。** 见证资格不可按设备类硬查,那会重新引入 B6 修掉的 bug。

    实现基线时试过在确认路径上加"作证者的设备类必须落在模型见证集内",结果本文
    自己的 P1 检出率从 1.000 掉到 0.928、良性证据从 69 条掉到 64 条(后者不是
    改善,是证据变少),覆盖率也会退回 B6 之前的 64.89%。

    机理已查明:2,373 个已实现对手方中 392 个不在模型见证集内,其中 **285 个是
    同类跨实例**交接(`vgr_2` 交付、`vgr_1` 取走)、88 个是同机顺序工序
    (`mm/mill` -> `mm/deburr`)——模型级见证边按**跨类**交接构造,压根无法表达
    "同类的另一台实例"。真正跨类却未建模的只有 6 例。

    故口径仍是 B6 那条:**见证资格看设备类,见证独立性看设备实例。**
    """
    from algorithm.taskgraph import device_class
    n_bad = n_good = 0
    for r in recs:
        if r.witness is None:
            continue
        exp = {dc for dc, _ in graph.witnesses_of(r.act.device, r.act.op)}
        if device_class(r.witness.device) in exp:
            n_good += 1
        else:
            n_bad += 1
    assert (n_good, n_bad) == (1981, 392)
    same_class = sum(
        1 for r in recs if r.witness is not None
        and device_class(r.witness.device) not in
        {dc for dc, _ in graph.witnesses_of(r.act.device, r.act.op)}
        and device_class(r.witness.device) == device_class(r.act.device))
    assert same_class == 386          # 392 中仅 6 例是真正跨类却未建模
    # 默认规则必须放行,否则上述 392 条真实证据被丢弃
    assert corroborate.WitnessPolicy(graph).admits(None, None) is True


def test_g2_consensus_detects_exactly_nothing(recs, graph):
    """`W1`:PBFT 式共识对任务状态伪造的检出**恰为 0**。

    共识确认的是"多数副本对消息的内容与顺序达成一致",不是物理事实;一条格式
    正确、签名有效、按时到达的伪造声明会被法定人数顺利提交。它对 P2 仍有效
    (无声明可提交),故其检出能力**恰等于看门狗 S1**,而带宽是本文的 131 倍。
    一句话:付 131 倍带宽换一个看门狗。

    两处操作化上的坑,都记在这里以免重犯:保留互证窗口会让它白捡 0.136(窗口在
    伪造声明到达前到期),保留否证通道也给 0.136(全部来自对手方否证)。共识不制造
    "B 必须为 A 的交付作证"这项义务,故两者都不该给。反过来说才是要点:**把否证
    通道交给 PBFT 就是把耦合互证交给它**,那恰好证明检出来自互证而非共识。
    """
    r = _bl(recs, graph, baselines.W1)
    assert r["dr"] == 0.0
    assert r["far"] == 0.0
    assert r["unresolved"] == 0
    pol = baselines.make(baselines.W1, graph)
    assert pol.confirm_on_claim and not pol.corroborates


def test_g3_interrogating_everyone_buys_nothing(recs, graph):
    """`W2`:问所有人**不会造出证据**,检出与误报与本文逐位相同。

    有本地传感证据的只有真正的对手方,问谁都一样。代价是见证集 4.95 倍即互证
    带宽 4.13 倍,零增益——这从反面支持 $O(1)$ 见证集的主张。

    另有一处预判错了,按实测记正:原以为无对手方的活动会照样开窗并全部超时成为
    假指控。实际没有,因为**双截止时刻**把它们兜住了(对手方从未被派发,互证窗口
    就从不装填,于是归档而非指控)。悬而未决数从 401 涨到 900,那是**覆盖率的
    假象**:看着监控面更广,实则一条也结算不了。
    """
    o = _bl(recs, graph, baselines.OURS)
    w = _bl(recs, graph, baselines.W2)
    assert (o["dr"], o["far"]) == (1.0, 69 / 3062)
    assert (w["dr"], w["far"]) == (o["dr"], o["far"])
    assert abs(mean(w["sizes"]) / mean(o["sizes"]) - 4.13) < 0.02
    assert (o["unresolved"], w["unresolved"]) == (401, 900)
    assert w["far"] < 0.03            # 没有变成假指控


def test_g4_random_nomination_collapses(recs, graph):
    """`W3`:随机提名的检出崩到 0.105(本文 1.000)。

    随机挑中的设备对**这一次**交接没有本地传感证据,到不了场也确认不了。失败
    形态是**什么都发现不了**(误报仅 0.002),不是乱指控——后者同样被双截止时刻
    兜住了。可见"有见证者"远不等于"有正确的见证者"。

    报告口径仍须给出判别力(检出 − 误报),这是方法论要求:换一个不含双截止时刻的
    协议,随机提名就会以乱指控的形态失败。
    """
    o = _bl(recs, graph, baselines.OURS)
    w = _bl(recs, graph, baselines.W3, k=1)
    assert abs(w["dr"] - 0.105) < 0.01
    assert w["far"] < 0.005
    assert w["dr"] - w["far"] < 0.15 < o["dr"] - o["far"]
    assert w["unresolved"] > 2000     # 绝大多数交付永远结算不了
    # 提名必须只依赖活动身份:换调用顺序不得改变任何一个数
    pol = baselines.make(baselines.W3, graph, k=1)
    a = [pol.eligible(r.act) for r in recs[:50]]
    baselines.witness_set_sizes(pol, recs)
    assert [pol.eligible(r.act) for r in recs[:50]] == a


def test_g5_spatial_neighbors_recover_only_half(recs, graph):
    """`W4`:空间邻居只恢复本文 **52%** 的检出,却多付 **34%** 的见证集规模。

    这一行是第一贡献的主证据。空间邻接是**静态**的、与当前工件走哪条工艺路线
    无关,故既漏掉图上不相邻的真对手方,又纳入大量与本次交接无关的设备;本文规则
    由任务图 + 当前 case 共同确定,是动态的。

    须注意这是把 COLAW/Vouch+ 的**选取原则**移植过来,不是它们的完整系统——
    后者依赖测距/RSSI,本数据没有(见 README 第四节末)。
    """
    o = _bl(recs, graph, baselines.OURS)
    w = _bl(recs, graph, baselines.W4, hops=1)
    assert abs(w["dr"] - 0.518) < 0.01
    assert abs(w["dr"] / o["dr"] - 0.518) < 0.01
    assert abs(mean(w["sizes"]) / mean(o["sizes"]) - 1.34) < 0.02
    assert w["dr"] < o["dr"] and mean(w["sizes"]) > mean(o["sizes"])


def test_g6_baselines_differ_only_in_the_selection_rule(graph):
    """公平性的结构保证:五条基线共用同一个协议对象,只替换 `WitnessPolicy`。

    "基线用另一份实现"无法排除实现差异,故此处断言所有基线都是 `WitnessPolicy`
    的子类型,且窗口配置(含派发排队容差 260 s)对所有基线相同。
    """
    for fam in baselines.FAMILIES:
        pol = baselines.make(fam, graph)
        assert isinstance(pol, corroborate.WitnessPolicy)
        proto = corroborate.CorroborationProtocol(graph, policy=pol)
        assert proto.cfg.dispatch_allowance_s == 260.0
    assert len(baselines.FAMILIES) == 5


# ---- H 组:第一档单观测者基线(结构性 0)----------------------------------

def _tier1(recs, graph, family, *, alarm_rate: float | None = None):
    """跑一条第一档检测器:良性误报 + P1/P2/P3 检出。"""
    kw = {}
    if family == baselines.R0 and alarm_rate is not None:
        kw["alarm_rate"] = alarm_rate
    det = baselines.make_tier1(family, graph, **kw)
    benign = attacks.benign_stream(recs)
    det.calibrate(benign)
    fa = det.accuse(benign)
    out = {"far": len(fa) / len(benign), "n_fa": len(fa)}
    for fam in (attacks.P1, attacks.P2, attacks.P3):
        reports, _ = attacks.inject(recs, attacks.AttackSpec(
            family=fam, rate=RATE, seed=SEED, explicit_refutation=True))
        primary = {id(r) for r in reports if r.forged and not r.accomplice}
        hit = det.accuse(reports) & primary
        out[fam] = len(hit) / max(len(primary), 1)
    return out


def test_h1_watchdog_matches_d7_on_p1_p3_and_catches_p2(recs, graph):
    """`S1` 看门狗:对 P1/P3 无能力,对 P2 全检出——与断言 D7 交叉一致。

    窗口与本文用同一套派发排队容差 260 s,不给基线设障。它对"该报的没报"有效,
    对按时到达、字段正常的伪造声明完全无效。
    """
    r = _tier1(recs, graph, baselines.S1)
    assert r[attacks.P1] == 0.0
    assert r[attacks.P3] == 0.0
    assert r[attacks.P2] == 1.0
    # 良性误报非零(真实调度迟到),但必须远小于省掉容差时的 19.8%(见 D5)
    assert 0.01 < r["far"] < 0.08


def test_h2_plan_residual_is_structurally_blind_to_forgery(recs, graph):
    """`S2` 计划残差:P1/P3 检出是结构性的 0,不是阈值没调好。

    伪造时长取该 (设备, 操作) 的中位数,恰落在残差分布最中央;结果位被置为
    success。阈值按良性流标定到 0.995 分位——再紧就要误报。都做足之后 DR≈FAR≈0。
    """
    r = _tier1(recs, graph, baselines.S2)
    assert r["far"] < 0.01
    assert r[attacks.P1] < 0.01
    assert r[attacks.P3] < 0.01
    assert abs(r[attacks.P1] - r["far"]) < 0.01
    assert r[attacks.P2] == 1.0       # 沉默仍能发现,本文不主张这一点


def test_h3_conformance_is_structurally_blind_to_forgery(recs, graph):
    """`S3` 一致性检验:良性 FAR=0 且 P1/P3 DR=0。

    操作化只保留两条不会误伤良性的规则(全局非法活动、交接对上的严格逆序),
    避开了 case 内并发链交错与 BPMN 残缺带来的 28% 假误报。伪造声明是合法活动
    的逐字段拷贝,对齐代价为 0——构造性不可能。
    """
    r = _tier1(recs, graph, baselines.S3)
    assert r["far"] == 0.0
    assert r[attacks.P1] == 0.0
    assert r[attacks.P3] == 0.0
    assert r[attacks.P2] == 1.0
    # 任务图必须带上 S3 所需的逐工作流字段
    assert len(graph.wf_tasks) == 16
    assert sum(len(v) for v in graph.wf_order.values()) > 0


def test_h4_p1_and_p3_are_identical_to_single_observer(recs, graph):
    """自检:P1 与 P3 对单观测者必须完全一样。

    两者的差别只在是否披露哈希链原像——那不是单观测者能看到的字段。若某条
    第一档基线给出不同的数,说明实现里漏进了本不该有的信息。
    """
    for fam in baselines.TIER1:
        r = _tier1(recs, graph, fam, alarm_rate=69 / 3062)
        assert r[attacks.P1] == r[attacks.P3], fam


def test_h5_random_accusation_has_no_discriminative_power(recs, graph):
    """`R0` 地板:等告警预算下随机指控的判别力 ≈ 0。

    告警率取本文良性误报 69/3062。任何判别力显著大于 0 的方法才算真在工作;
    本文的判别力是 1.000 − 0.0225 = 0.977。
    """
    r = _tier1(recs, graph, baselines.R0, alarm_rate=69 / 3062)
    assert abs(r["far"] - 69 / 3062) < 0.01
    assert abs(r[attacks.P1] - r["far"]) < 0.02
    assert r[attacks.P1] - r["far"] < 0.02


def test_h6_tier1_and_tier2_interfaces_must_not_mix(graph):
    """第一档与第二档接口不得混用:性质完全不同,不可塞进同一张表。

    第一档是 `SingleObserver`(只看单观测者可见字段),第二档是 `WitnessPolicy`
    (只换见证选取规则)。混用会把"结构性 0"和"赛马"读成同一件事。
    """
    for fam in baselines.TIER1:
        det = baselines.make_tier1(fam, graph)
        assert isinstance(det, baselines.SingleObserver)
        assert not isinstance(det, corroborate.WitnessPolicy)
    for fam in baselines.FAMILIES:
        pol = baselines.make(fam, graph)
        assert isinstance(pol, corroborate.WitnessPolicy)
    assert set(baselines.TIER1).isdisjoint(baselines.FAMILIES)


# ---- I 组:第三档心跳/带宽 + 第四档天花板 ---------------------------

def test_i1_equal_bandwidth_periodic_latency_is_size_ratio(budgets):
    """`H1`:等带宽下周期上报的检测时延倍率 ≈ 报文比 128/16 = 8。

    这是带宽守恒的直接推论,不是仿真。`budget.py` 先解出沉默的 B,再代入
    $T_{period} = n \\cdot L_{report} / B$。有 skew 时倍率略小于 8,但必须落在
    报文比附近——若差很多,说明等带宽口径写错了。
    """
    _, motion, _ = budgets
    d = budget.cheapest(motion, burst_rho=0.0, **_BKW)
    h1 = baselines.equal_bandwidth_periodic(d, n_devices=_BKW["n_devices"])
    assert h1.size_ratio == 128 / 16 == 8.0
    assert abs(h1.latency_ratio - 8.0) < 0.2
    assert abs(h1.period_s / d.t_hb_s - 8.0) < 1e-9
    s = baselines.silence_vs_periodic(d, n_devices=_BKW["n_devices"])
    assert abs(s["latency_ratio"] - h1.latency_ratio) < 1e-12


def test_i2_equal_bandwidth_periodic_misses_the_detect_budget(budgets):
    """`H1` 在最严口径下检测时延 4.68 s,远超运动危害的 0.60 s 检测预算。

    等带宽对比的闭合论证:沉默能落入 FHI,同带宽的全量周期上报不能。
    这不是"我们更快一点",而是对方在安全预算内根本不可行。
    """
    _, motion, _ = budgets
    d = budget.cheapest(motion, burst_rho=0.3, **_BKW)
    h1 = baselines.equal_bandwidth_periodic(d, n_devices=_BKW["n_devices"])
    assert abs(h1.detect_delay_s - 4.680) < 0.01
    assert h1.detect_delay_s > motion.detect_budget_s
    assert d.detect_delay_s <= motion.detect_budget_s
    # 倍率仍贴近报文比
    assert abs(h1.latency_ratio - 7.88) < 0.05


def test_i3_unbound_goose_has_liveness_without_accountability():
    """`H2`:活性有、归责无。

    GOOSE MaxTime 能发现沉默,但心跳无身份绑定、无可转移证据、不能抗伪心跳。
    攻击者可替被沉默设备伪造心跳掩盖 P2——这是结构性能力边界,不是检出率高低。
    """
    h2 = baselines.unbound_goose()
    assert h2.detects_silence is True
    assert h2.binds_identity is False
    assert h2.transferable_evidence is False
    assert h2.resists_spoofed_heartbeat is False
    assert h2.name == baselines.H2


def test_i4_tesla_forgeable_after_key_disclosure():
    """`H3`:密钥披露后第三方可重算 MAC——归责失败。

    RFC 4082 明确不提供不可否认性。本断言把那句话落成可执行反例,并与
    `crypto.py` 的划界对照:本文原像是一次性凭证,不是 MAC 密钥。
    """
    h3 = baselines.tesla_delayed_auth()
    assert h3.authenticates and not h3.non_repudiation
    key, msg = os.urandom(16), b"tessera-tesla-counterexample"
    tag, ok = h3.forge_after_disclosure(key, msg)
    assert ok is True
    assert tag == crypto.mac(key, msg)
    # 对照:本文原像披露后,第三方仍无法从承诺根推出未披露槽的原像
    ch = crypto.HashChain("vgr_1", "sess", 8)
    root = ch.root
    revealed = ch.element(1)
    assert crypto.walk(revealed, 1, crypto._tag("vgr_1", "sess")) == root
    # 已知槽 1 的原像推不出槽 2
    assert ch.element(2) != revealed


def test_i5_sensor_oracle_gap_is_the_coverage_hole(recs):
    """`U1`:先知覆盖率 = 1.0,与本文差额 = 覆盖缺口 29.95%。

    先知不抬已覆盖区间的检出(本文在已互证区间已是 1.000),只回答"还差多少"。
    917 = 3062 - 2145,与断言 B4 的覆盖度互为表里。
    """
    u1 = baselines.sensor_oracle(recs)
    assert u1.n_activities == 3062
    assert u1.n_ours == 2145
    assert u1.n_oracle == 3062
    assert abs(u1.ours_coverage - 2145 / 3062) < 1e-12
    assert u1.oracle_coverage == 1.0
    assert abs(u1.gap - (1 - 2145 / 3062)) < 1e-12
    assert u1.n_oracle - u1.n_ours == 917


def test_i6_tier3_and_tier4_are_not_replay_baselines(graph):
    """第三/四档是解析对照,不得混进 WitnessPolicy / SingleObserver 回放表。

    H1 吃的是 `budget.Design`,H2/H3 是能力边界声明,U1 吃的是覆盖记录。
    与第一档(结构性 0)、第二档(见证选取赛马)性质不同,断言编号也分开(I 组)。
    """
    assert set(baselines.TIER3).isdisjoint(baselines.TIER1)
    assert set(baselines.TIER3).isdisjoint(baselines.FAMILIES)
    assert set(baselines.TIER4).isdisjoint(baselines.TIER1)
    assert baselines.H1 in baselines.TIER3
    assert baselines.U1 in baselines.TIER4
    d = budget.cheapest(budget.SafetyBudget.from_protective_field(),
                        burst_rho=0.0, **_BKW)
    h1 = baselines.equal_bandwidth_periodic(d)
    assert h1.name == baselines.H1
    assert not isinstance(h1, corroborate.WitnessPolicy)
    assert not isinstance(h1, baselines.SingleObserver)


# ---- J 组:loss_sweep 与 main 入口 ------------------------------------

def test_j1_pistis_landmark_loss_still_admits_a_design(budgets):
    """p=50%(PISTIS 地标)突发口径下仍可行,且仍比 5 Hz PBFT 便宜。

    这不是把 PISTIS 当数值基线——事件语义完全不同。只回答审稿人会问的那句:
    你们的心跳在同样恶劣丢包下还站得住吗?答案是站得住,代价 27.5 KB/s = PBFT/36。
    """
    _, motion, _ = budgets
    d = budget.cheapest(motion, p_loss=0.5, n_devices=28,
                        far_target_per_hour=1.0, burst_rho=0.3)
    assert d is not None
    assert d.r_misses == 36
    assert abs(d.bandwidth_bps - 27502.1) < 1.0
    assert d.detect_delay_s <= motion.detect_budget_s
    pbft = silence.pbft_bandwidth_bps(28, 5.0)
    assert abs(pbft / d.bandwidth_bps - 36.5) < 0.1


def test_j2_bandwidth_rises_monotonically_with_loss(budgets):
    """带宽随丢包率单调上升——扫参敏感性的结构保证。

    若某处反降,说明 cheapest 的网格或 min_misses 写坏了。
    """
    _, motion, _ = budgets
    prev = 0.0
    for p in (1e-3, 1e-2, 5e-2, 1e-1, 2e-1, 5e-1):
        d = budget.cheapest(motion, p_loss=p, n_devices=28,
                            far_target_per_hour=1.0, burst_rho=0.3)
        assert d is not None and d.bandwidth_bps >= prev - 1e-9
        prev = d.bandwidth_bps
    # 相对默认 p=1% 的代价约 3.6x
    d1 = budget.cheapest(motion, burst_rho=0.3, **_BKW)
    d50 = budget.cheapest(motion, p_loss=0.5, n_devices=28,
                          far_target_per_hour=1.0, burst_rho=0.3)
    assert abs(d50.bandwidth_bps / d1.bandwidth_bps - 3.58) < 0.05


def test_j3_main_evaluate_matches_detect_diag_on_p1(recs, graph):
    """main.evaluate 与 detect_diag 同口径:P1 检出 363/363 = 1.000。

    一键入口不许另起一套分母或对齐规则,否则 output/summary.json 与诊断工具
    会对不上。
    """
    import main as tessera_main
    r = tessera_main.evaluate(recs, graph, attacks.P1, refute=True,
                              rate=RATE, seed=SEED)
    assert (r["n_forged"], r["n_hit"], r["dr"]) == (363, 363, 1.0)
    assert abs(r["latency_median_s"] - 54.6) < 0.5
