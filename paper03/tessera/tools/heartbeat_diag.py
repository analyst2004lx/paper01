"""第三、四档基线：等带宽时延、无绑定心跳、TESLA 归责失败、先知天花板。

这一档**不比 P1 检出率**——那是第一档的结构性 0。这里接的是带宽—安全裕度
定理与密码学划界：

  H1  等带宽周期性全量上报   同带宽下时延放大 report/token 倍
  H2  无密码绑定的 GOOSE 心跳 活性有、归责无
  H3  TESLA 式延迟密钥       认证有、不可否认无（披露后可伪造）
  U1  交接点全传感器先知     覆盖率 1.0；差额 = 本文覆盖缺口

用法(在 paper03/tessera/ 下):  py -m tools.heartbeat_diag
"""
from __future__ import annotations

import argparse
import os

from algorithm import baselines, budget, coverage, crypto, ingest, taskgraph


def load(xes, bpmn):
    raw = ingest.read_xes(xes)
    live = ingest.valid(raw, drop_failure=True)
    pos = {p for a in raw for p in (a.start_pos, a.end_pos) if p}
    g = taskgraph.load_bpmn(bpmn, log_positions=pos)
    return live, g, coverage.realized(live, g)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xes", default=None)
    ap.add_argument("--bpmn", default=None)
    ap.add_argument("--n", type=int, default=28)
    ap.add_argument("--p-loss", type=float, default=1e-2)
    ap.add_argument("--far", type=float, default=1.0)
    args = ap.parse_args()

    live, g, recs = load(args.xes or ingest.default_log_path(),
                         args.bpmn or taskgraph.default_bpmn_glob())
    kw = dict(p_loss=args.p_loss, n_devices=args.n,
              far_target_per_hour=args.far)
    auto = budget.SafetyBudget()
    motion = budget.SafetyBudget.from_protective_field(
        field_mm=budget.protective_field_mm()["field_mm"])

    print(f"活动 {len(live)}  设备 {args.n}  丢包 {args.p_loss}  "
          f"误报预算 {args.far}/h\n")

    print("一、H1 等带宽周期性全量上报（时延对照）")
    print(f"      {'口径':14s} {'沉默 B':>10s} {'沉默 T_det':>10s} "
          f"{'周期 T_det':>10s} {'倍率':>8s}")
    for name, b, rho in (("汽车·独立", auto, 0.0),
                         ("运动·独立", motion, 0.0),
                         ("运动·突发", motion, 0.3)):
        d = budget.cheapest(b, burst_rho=rho, **kw)
        if d is None:
            print(f"      {name:14s}  无可行解")
            continue
        s = baselines.silence_vs_periodic(d, n_devices=args.n)
        print(f"      {name:14s} {s['silence_bandwidth_bps']:10.0f} "
              f"{s['silence_detect_s']:10.3f} "
              f"{s['periodic_detect_s']:10.3f} "
              f"{s['latency_ratio']:8.2f}x")
    print(f"      全量报文 {baselines.FULL_REPORT_BYTES} B / "
          f"原像 {crypto.TOKEN_BYTES} B = "
          f"{baselines.FULL_REPORT_BYTES / crypto.TOKEN_BYTES:.0f}x。"
          f"倍率 ≈ 报文比（带宽守恒）。")
    print()

    print("二、H2 无密码绑定的 GOOSE 式心跳")
    h2 = baselines.unbound_goose()
    print(f"      检出沉默={h2.detects_silence}  身份绑定={h2.binds_identity}  "
          f"可转移证据={h2.transferable_evidence}  "
          f"抗伪心跳={h2.resists_spoofed_heartbeat}")
    print("      读法：活性有、归责无。攻击者可替被沉默设备伪造心跳掩盖 P2；"
          "即便发现缺失，也拿不出只有该设备能产生的凭证。")
    print()

    print("三、H3 TESLA 式延迟密钥（归责失败）")
    h3 = baselines.tesla_delayed_auth()
    key = os.urandom(16)
    msg = b"slot-7|device=vgr_1|state=ok"
    tag, ok = h3.forge_after_disclosure(key, msg)
    print(f"      认证={h3.authenticates}  不可否认={h3.non_repudiation}")
    print(f"      密钥披露后第三方重算 MAC：校验通过={ok}  "
          f"标签={tag.hex()[:16]}…")
    print("      读法：RFC 4082 明确不提供不可否认性。披露后任何人都能伪造"
          "『合法』历史包——归责失败。")
    print("      本文划界：原像是一次性凭证，不是 MAC 密钥；披露后第三方仍能"
          "验证『只有承诺者能产生』。")
    print()

    print("四、U1 交接点全传感器先知（天花板）")
    u1 = baselines.sensor_oracle(recs)
    print(f"      活动 {u1.n_activities}  本文已互证 {u1.n_ours}  "
          f"({u1.ours_coverage*100:.2f}%)  先知 {u1.n_oracle}  "
          f"({u1.oracle_coverage*100:.2f}%)")
    print(f"      覆盖缺口 {u1.gap*100:.2f}% = "
          f"{u1.n_oracle - u1.n_ours} 条。"
          f"先知不抬已覆盖区间的检出（本文已是 1.000），")
    print("      只回答『还差多少』——差额即按需主动互证的靶区。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
