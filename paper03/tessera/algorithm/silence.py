"""可问责沉默：心跳槽、原像缺失判定与误报—时延—带宽的解析关系。

## 机制

事件触发通信下沉默构成攻击面：拜占庭节点保持沉默，让接收方按预测模型推出
错误状态，零消息实现无界偏差。该攻击面的**学术提出权不属于本文**
（non-triggering misbehavior，arXiv:2201.02997），本文做的是它的**运行时
检出与归责**。做法是令沉默不再免费——槽 k 到期时设备必须披露哈希链原像
$h_k$，语义为"我在槽 k 内状态仍落在预测带内"。真沉默即收不到 $h_k$，而
$h_k$ 只有该设备能产生（单向性 + 承诺根已签名注册），故"槽 k 截止未收到
$h_k$"是**确定性判据**而非怀疑。

## 为什么 paper02 的二值通道天花板在此不适用（必须精确论证，不能只声称）

paper02 结论 11 与 21：二值通道的单消息功效上界是
$\\text{触发率} \\times \\min(1, \\alpha/q)$，其中 q 是该通道离散异常事件在
**良性流上的发生率**。互锁通道的 q 是日志的既有性质（部署流实测 4.7%，
训练折 0.54%，漂移 9 倍），压不下去——近似身份解析只做到 2.3%，剩下一半
必须靠真正的 NFC/RFID 工件标识。$\\alpha=0.001$ 时天花板只剩 0.185。

原像缺失判定形式上也是二值的，但有三处结构性差别，天花板因此不生效：

  1. **它是密码学协议违反，不是统计检验。** 签名校验失败不需要 p 值，
     原像缺失同理。paper02 的硬层（可行性掩码 F）也是这样：良性 q = 0，
     天花板恒为 1，故 F 作硬约束、互锁只能作软证据。可问责沉默属于前者。
  2. **q 是设计参数而非数据性质。** 良性缺失只来自丢包，故
     $q = p_{\\text{loss}}^{\\,r}$（r 为判决所需的连续缺失次数，丢包近似独立）。
     r 可自由选取，于是 q 可压到任意小——这与互锁那个压不动的 4.7% 是根本
     区别，也是本机制值得做的定量理由。
  3. **代价不是功效而是时延。** 天花板没有消失，而是**转化为时延预算约束**：
     $T_{\\text{detect}} = r \\cdot T_{\\text{hb}}$，必须落在功能安全的 FHI
     预算内。这条恰好把第二贡献接到第三贡献（带宽—安全裕度权衡定理）上，
     见 `budget.py`。

诚实的边界：上述第 2 点依赖丢包独立。工业无线的突发丢包会使
$q > p^{r}$，故 `far_prob` 提供 `burst_rho` 参数给出相关丢包下的上界，
论文中报告 FPR 时必须声明用的是哪个口径。

## 本数据集撑不起什么

Trier 日志没有通信层，故心跳与丢包必须仿真（`../database/README.md` 第三节
第 2 条）。可从数据得到的是**对照量**：设备沉默时，只靠耦合互证要多久才能
判定——那是命令账本给出的计划完成时刻，实测分布见 `tools/silence_diag.py`。
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from . import crypto

#: 判决类型。SILENT 是缺失判定，FORGED / EARLY 是不可否认的作恶证据。
SILENT = "silent"
FORGED = "forged_preimage"
EARLY = "early_reveal"


@dataclass
class SilenceConfig:
    """心跳参数。默认值是示例而非建议值，可行区间由 budget.py 给出。"""
    t_hb_s: float = 0.2
    #: 判决所需的连续缺失槽数。r=1 即零容忍，误报率等于丢包率。
    r_misses: int = 3
    #: 松散时间同步的容差，计入判决时延。
    skew_s: float = 0.01
    #: 每槽披露的字节数（原像）。
    token_bytes: int = crypto.TOKEN_BYTES

    @property
    def detect_delay_s(self) -> float:
        """沉默的最坏检测时延。接 FHI 预算的就是这个量。"""
        return self.r_misses * self.t_hb_s + self.skew_s

    def bandwidth_bps(self, n_devices: int) -> float:
        """心跳的稳态带宽，字节/秒。不含交接确认。"""
        return n_devices * self.token_bytes / self.t_hb_s


@dataclass
class Verdict:
    device: str
    kind: str
    slot: int
    t_decide: float
    #: 判决所依据的证据。FORGED / EARLY 时为已披露的原像，可交第三方核验。
    evidence: bytes = b""


@dataclass
class SilenceMonitor:
    """验证者侧的沉默监测器。

    每设备维护一个链验证器与连续缺失计数。判决在**截止时刻的扫描**中产生，
    不在收到消息时产生——这一点是必须的：沉默是"没有事件"，只有时钟推进才
    能观测到它，靠消息驱动永远等不到。
    """
    cfg: SilenceConfig
    _ver: dict[str, crypto.Verifier] = field(default_factory=dict)
    _misses: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _swept: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _revoked: set[str] = field(default_factory=set)
    n_hashes: int = 0
    n_reveals: int = 0

    def register(self, commitment: crypto.Commitment) -> None:
        self._ver[commitment.device] = crypto.Verifier(commitment)

    def on_reveal(self, device: str, slot: int, preimage: bytes, *,
                  now: float) -> Verdict | None:
        """处理一次原像披露。返回非 None 即作恶证据。"""
        v = self._ver[device]
        self.n_reveals += 1
        steps = slot - v.last_slot
        res = v.accept(slot, preimage, now=now, skew_s=self.cfg.skew_s)
        if res != crypto.STALE:
            self.n_hashes += max(1, steps)
        if res == crypto.BAD:
            return Verdict(device, FORGED, slot, now, preimage)
        if res == crypto.EARLY:
            return Verdict(device, EARLY, slot, now, preimage)
        return None

    def sweep(self, now: float) -> list[Verdict]:
        """把时钟推进到 `now`，对所有已过截止的槽判定缺失。

        连续缺失达 `r_misses` 即出具 SILENT 判决并冻结派单；一旦收到合法披露，
        计数复位。**复位是必须的**：paper02 结论"序贯臂必须复位且自报误报"
        记录过漏掉复位使检出率虚高 22 倍的代价。
        """
        out: list[Verdict] = []
        for dev, v in self._ver.items():
            c = v.commitment
            due = min(c.slot_at(now - self.cfg.skew_s) - 1, c.length)
            for slot in range(self._swept[dev] + 1, due + 1):
                self._swept[dev] = slot
                if slot <= v.last_slot:
                    self._misses[dev] = 0
                    continue
                self._misses[dev] += 1
                if (self._misses[dev] >= self.cfg.r_misses
                        and dev not in self._revoked):
                    self._revoked.add(dev)
                    out.append(Verdict(dev, SILENT, slot,
                                       c.deadline(slot) + self.cfg.skew_s))
        return out

    def revoked(self) -> set[str]:
        """已被冻结派单的设备。调度器据此停止下发新任务。"""
        return set(self._revoked)


# ---- 解析关系（论文里的图与定理都从这里出）-----------------------------

def far_prob(p_loss: float, r: int, *, burst_rho: float = 0.0) -> float:
    """良性流上出现一次 SILENT 误判的概率，即天花板公式里的 q。

    独立丢包下 $q = p^{r}$。`burst_rho` 是相邻槽丢包的条件相关系数，给出
    突发丢包下的上界 $q \\le p \\cdot (p + \\rho(1-p))^{r-1}$：第一次缺失
    概率仍是 p，后续每次的条件概率被抬高到 $p + \\rho(1-p)$。$\\rho=0$ 退化为
    独立情形，$\\rho=1$ 退化为 $q=p$（一旦丢包必连丢，r 完全失效）。
    工业无线必须报 $\\rho > 0$ 的口径。
    """
    if not 0.0 <= p_loss <= 1.0:
        raise ValueError("丢包率须在 [0, 1]")
    cond = p_loss + burst_rho * (1.0 - p_loss)
    return p_loss * cond ** (r - 1)


def far_per_hour(p_loss: float, cfg: SilenceConfig, n_devices: int,
                 *, burst_rho: float = 0.0) -> float:
    """全车队的 SILENT 误报次数/小时。这是运维真正关心的量。

    每设备每槽都是一次判决机会，故速率 = n / T_hb × q。
    """
    q = far_prob(p_loss, cfg.r_misses, burst_rho=burst_rho)
    return n_devices * q * 3600.0 / cfg.t_hb_s


def min_misses(p_loss: float, t_hb_s: float, n_devices: int,
               far_target_per_hour: float, *, burst_rho: float = 0.0,
               r_max: int = 64) -> int | None:
    """满足误报预算所需的最小 r。无解返回 None。"""
    for r in range(1, r_max + 1):
        cfg = SilenceConfig(t_hb_s=t_hb_s, r_misses=r)
        if far_per_hour(p_loss, cfg, n_devices,
                        burst_rho=burst_rho) <= far_target_per_hour:
            return r
    return None


def feasible_t_hb(p_loss: float, n_devices: int, far_target_per_hour: float,
                  budget_s: float, *, burst_rho: float = 0.0,
                  grid: int = 200, t_lo: float = 0.01, t_hi: float = 10.0
                  ) -> list[tuple[float, int, float, float]]:
    """在给定误报预算与 FHI 时延预算下，枚举可行的 $(T_{hb}, r)$。

    返回 [(T_hb, r, 检测时延, 带宽 B/s), ...]，按带宽升序。带宽随 $T_{hb}$
    单调下降，故最省带宽的配置总在时延预算的边界上——这正是"省带宽是带安全
    约束的优化问题"的形式化，也是论文那张可行区间图的数据来源。
    """
    out = []
    for i in range(grid):
        t = t_lo * (t_hi / t_lo) ** (i / (grid - 1))
        r = min_misses(p_loss, t, n_devices, far_target_per_hour,
                       burst_rho=burst_rho)
        if r is None:
            continue
        cfg = SilenceConfig(t_hb_s=t, r_misses=r)
        if cfg.detect_delay_s > budget_s:
            continue
        out.append((t, r, cfg.detect_delay_s, cfg.bandwidth_bps(n_devices)))
    return sorted(out, key=lambda x: x[3])


def power_ceiling(alpha: float, q: float) -> float:
    """paper02 的二值通道天花板 $\\min(1, \\alpha/q)$。

    在此仅用于**对照**：说明若把沉默当作统计通道去融合，会落回这条天花板；
    本文把它作为硬层，故不受此限。论文中必须同时给出两个数，否则审稿人会
    以"你的通道也是二值的"质疑。
    """
    return 1.0 if q <= 0 else min(1.0, alpha / q)


def pbft_bandwidth_bps(n: int, rate_hz: float, msg_bytes: int = 128) -> float:
    """周期性 PBFT 的正常路径带宽，作基线 `W1`（全体设备法定人数）的带宽上界。

    正常路径消息数约 $2n^2$ 条/轮（pre-prepare 广播 n、prepare 与 commit
    各 $n^2$），故带宽 $\\approx 2n^2 \\cdot R \\cdot L$。
    """
    return 2 * n * n * rate_hz * msg_bytes


def bytes_per_verdict(cfg: SilenceConfig) -> dict:
    """一次判决的密码学开销账，用于"非对称密码预算"那节的表格。"""
    return {
        "commit_root_once": crypto.TOKEN_BYTES + crypto.SIG_BYTES,
        "per_slot_reveal": cfg.token_bytes,
        "hashes_per_slot": 1,
        "signatures_per_slot": 0,
        "slots_per_verdict": cfg.r_misses,
    }


def entropy_bits(p_loss: float) -> float:
    """丢包过程的每槽熵，用于说明心跳流的可压缩性下界（附录用）。"""
    if p_loss in (0.0, 1.0):
        return 0.0
    return -(p_loss * math.log2(p_loss)
             + (1 - p_loss) * math.log2(1 - p_loss))
