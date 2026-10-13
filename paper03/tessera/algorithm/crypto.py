"""哈希链承诺与非对称密码预算。

可问责沉默的密码学底座。查新（`../paper03-NewIdea.md` 第三节 (b)）的结论是
TESLA 与 RFC 4082 **明确声明不提供不可否认性**——密钥披露后任何人都能伪造
"合法"的 TESLA 包。本文的用法与之有本质区别，且这个区别必须在实现里体现，
不能只在论文里声称：

    TESLA 把链上元素当作 **MAC 密钥**，故安全性依赖披露时刻的时间约束，
    披露之后就失去认证价值。本文把链上原像**直接当作一次性凭证**，语义是
    "我在第 k 个心跳槽声明状态仍在预测带内"。由哈希单向性，除承诺者本人外
    无人能产生该原像，因此任何持有承诺根的第三方都能验证该披露确实出自该
    节点，且披露事实本身不因时间流逝而失效。

要让这个论证严密，三个前置条件缺一不可，本模块逐条实现并在 tests 中钉死：

  1. **承诺根由该节点用 Ed25519 一次性签名注册，并绑定节点身份与会话。**
     否则攻击者可另造一条链冒名注册。见 `Commitment.sign` / `verify_root`。
  2. **链元素与槽号一一绑定。** 反向链天然给出绑定：槽 k 的元素是
     $s_{N-k}$，其正向哈希 k 次必等于承诺根，索引即绑定。但仅此不够——
     还须拒绝**提前披露**：在槽 k 内披露槽 k+1 的元素会让验证者据此推出槽 k
     的元素，等于预付未来的沉默。见 `Verifier.accept` 的 EARLY 分支。
  3. **披露时限由松散时间同步保证。** 本模块只提供带容差的时限判定，
     时钟同步本身是威胁模型里的显式假设（工业 TSN / 5G URLLC 下成立）。

**域分离**：链的每一步哈希都拌入 `tessera|<device>|<session>`，因此同一
seed 在不同设备或不同会话下产生不同的链，杜绝跨设备/跨会话搬运。

**截断到 16 字节**是有意为之，与 TESLA 约 20 字节/包的开销可比。安全性取
**原像抗性**（$2^{128}$），碰撞抗性在此不相关：攻击者需要的是某个特定值的
原像，不是任意碰撞对。截断链在函数图上的期望环长约 $2^{64}$，对任何现实的
链长都不构成问题。

Hash-chain commitments and the asymmetric-cryptography budget.

Cryptographic base of accountable silence. The literature check
(`../paper03-NewIdea.md`, section 3 (b)) finds that TESLA and RFC 4082
**explicitly do not provide non-repudiation** — after key disclosure anyone
can forge a "valid" TESLA packet. This use differs in kind, and the difference
must show up in the implementation, not only in the paper:

    TESLA treats a chain element as a **MAC key**, so security depends on the
    disclosure-time constraint and the element loses authentication value
    afterward. Here the preimage is **itself a one-time credential**, meaning
    "in heartbeat slot k I still claim my state lies inside the prediction
    band." By hash one-wayness, only the committer can produce that preimage,
    so any third party holding the commitment root can verify that the
    disclosure came from that node, and the fact of disclosure does not expire.

Three preconditions are all required. This module implements each and pins
them in tests:

  1. **The commitment root is registered once with an Ed25519 signature,
     bound to node identity and session.** Otherwise an attacker can register
     a forged chain under another name. See `Commitment.sign` / `verify_root`.
  2. **Chain elements are bound one-to-one to slot indices.** The reverse
     chain gives the binding: slot k's element is $s_{N-k}$, and hashing it
     forward k times must equal the root. That is not enough — **early
     disclosure must also be rejected**: revealing slot k+1's element inside
     slot k lets the verifier derive slot k's element, which prepays future
     silence. See the EARLY branch of `Verifier.accept`.
  3. **The disclosure deadline is guaranteed by loose time synchronization.**
     This module only checks the deadline with a skew tolerance. Clock sync
     itself is an explicit assumption of the threat model (it holds under
     industrial TSN / 5G URLLC).

**Domain separation**: every hash step mixes in `tessera|<device>|<session>`,
so the same seed yields a different chain on another device or session.
Cross-device and cross-session replay is blocked.

**Truncation to 16 bytes** is intentional, comparable to TESLA's ~20 bytes
per packet. Security is **preimage resistance** ($2^{128}$); collision
resistance is irrelevant here: the attacker needs the preimage of one specific
value, not an arbitrary colliding pair. The expected cycle length of a
truncated chain on its functional graph is about $2^{64}$, which is not a
problem for any realistic chain length.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass, field

#: 链元素长度。16 B = 128 bit 原像抗性。 / Chain element length. 16 B = 128-bit preimage resistance.
TOKEN_BYTES = 16
#: Ed25519 签名长度，用于带宽核算。 / Ed25519 signature length, for bandwidth accounting.
SIG_BYTES = 64
#: HMAC-SHA256 截断长度，高频路径用。 / Truncated HMAC-SHA256 length, used on the high-rate path.
MAC_BYTES = 16


def _tag(device: str, session: str) -> bytes:
    return f"tessera|{device}|{session}".encode()


def step(x: bytes, tag: bytes) -> bytes:
    """链的一步：截断的带域分离哈希。

    One chain step: truncated hash with domain separation.
    """
    return hashlib.sha256(tag + b"|" + x).digest()[:TOKEN_BYTES]


def walk(x: bytes, n: int, tag: bytes) -> bytes:
    """正向走 n 步。

    Walk n steps forward.
    """
    for _ in range(n):
        x = step(x, tag)
    return x


@dataclass
class HashChain:
    """设备侧持有的反向哈希链。

    $s_0$ = seed，$s_i = H(s_{i-1})$，承诺根 = $s_N$。槽 k（k 从 1 起）披露
    $s_{N-k}$。披露顺序与生成顺序相反，故已披露的元素无法用于推出未披露的。

    Reverse hash chain held on the device.

    $s_0$ = seed, $s_i = H(s_{i-1})$, commitment root = $s_N$. Slot k
    (k starting at 1) discloses $s_{N-k}$. Disclosure order is the reverse of
    generation order, so a disclosed element cannot derive an undisclosed one.
    """
    device: str
    session: str
    length: int
    seed: bytes = field(default_factory=lambda: os.urandom(32))

    def __post_init__(self):
        if self.length < 1:
            raise ValueError("链长必须 >= 1")
        tag = _tag(self.device, self.session)
        x = self.seed
        self._chain = [x]
        for _ in range(self.length):
            x = step(x, tag)
            self._chain.append(x)

    @property
    def root(self) -> bytes:
        return self._chain[self.length]

    def element(self, slot: int) -> bytes:
        """槽 `slot` 应披露的原像。slot 取 1..length。

        Preimage that slot `slot` must disclose. `slot` is in 1..length.
        """
        if not 1 <= slot <= self.length:
            raise ValueError(f"槽号越界: {slot} 不在 1..{self.length}")
        return self._chain[self.length - slot]

    @property
    def n_bytes_state(self) -> int:
        """设备侧存储开销。可用 Jakobsson-Coppersmith 的时空折衷换成
        $O(\\log N)$，本文不涉及，如实记账即可。

        Device-side storage cost. A Jakobsson–Coppersmith time–space tradeoff
        can reduce it to $O(\\log N)$; this paper does not, and the account is
        reported as stored.
        """
        return TOKEN_BYTES * (self.length + 1)


@dataclass(frozen=True)
class Commitment:
    """已签名的承诺，注册于验证者处。

    签名覆盖 (设备, 会话, 根, 链长, 起始时刻, 心跳间隔) 的规范编码。把
    `t_hb_s` 与 `t0` 纳入签名是必要的：否则攻击者可事后声称自己承诺的是
    另一个心跳间隔，从而否认某次缺失。

    Signed commitment, registered at the verifier.

    The signature covers the canonical encoding of (device, session, root,
    chain length, start time, heartbeat interval). Including `t_hb_s` and
    `t0` is required: otherwise the attacker can later claim a different
    heartbeat interval and deny a miss.
    """
    device: str
    session: str
    root: bytes
    length: int
    t0: float
    t_hb_s: float
    sig: bytes = b""

    def payload(self) -> bytes:
        return (f"tessera-commit|{self.device}|{self.session}|"
                f"{self.root.hex()}|{self.length}|{self.t0:.6f}|"
                f"{self.t_hb_s:.6f}").encode()

    def slot_at(self, t: float) -> int:
        """时刻 t 落在第几个槽。槽 k 覆盖 [t0+(k-1)T, t0+kT)。

        Which slot time t falls in. Slot k covers [t0+(k-1)T, t0+kT).
        """
        return int((t - self.t0) // self.t_hb_s) + 1

    def deadline(self, slot: int) -> float:
        return self.t0 + slot * self.t_hb_s


def sign_commitment(c: Commitment, private_key) -> Commitment:
    """用 Ed25519 一次性签名注册承诺根。整条链只签这一次——这正是"非对称
    密码预算"的含义：稀有事件用签名，高频路径用哈希与 MAC。

    Register the commitment root with a one-time Ed25519 signature. The whole
    chain is signed only once — that is the "asymmetric cryptography budget":
    rare events use signatures; the high-rate path uses hashes and MACs.
    """
    from dataclasses import replace
    return replace(c, sig=private_key.sign(c.payload()))


def verify_root(c: Commitment, public_key) -> bool:
    """验证承诺根确实由该节点注册。前置条件 1。

    Verify that the commitment root was registered by this node. Precondition 1.
    """
    from cryptography.exceptions import InvalidSignature
    try:
        public_key.verify(c.sig, c.payload())
        return True
    except InvalidSignature:
        return False


#: 验证结果。EARLY 与 BAD 都是不可否认的作恶证据，MISS 只是缺失。
#: Verification outcomes. EARLY and BAD are undeniable evidence of misbehavior; a miss is only absence.
ACCEPT = "accept"
BAD = "bad_preimage"
EARLY = "early_reveal"
STALE = "stale_slot"


@dataclass
class Verifier:
    """验证者侧的链状态。增量验证：正常情况每槽只需一次哈希。

    Verifier-side chain state. Incremental check: one hash per slot in the normal case.
    """
    commitment: Commitment
    _last_slot: int = 0
    _last_value: bytes = b""

    def __post_init__(self):
        self._last_value = self.commitment.root

    @property
    def last_slot(self) -> int:
        return self._last_slot

    def accept(self, slot: int, preimage: bytes, *, now: float,
               skew_s: float = 0.0) -> str:
        """校验槽 `slot` 的披露。

        `now` 是**接收侧**时刻（消息自带时间戳攻击者可控，不得采用）。
        返回 ACCEPT / BAD / EARLY / STALE 之一。

        Check the disclosure for slot `slot`.

        `now` is the **receiver-side** time (a timestamp carried in the message
        is attacker-controlled and must not be used). Returns one of
        ACCEPT / BAD / EARLY / STALE.
        """
        if slot <= self._last_slot:
            return STALE
        if now < self.commitment.deadline(slot) - self.commitment.t_hb_s - skew_s:
            return EARLY
        tag = _tag(self.commitment.device, self.commitment.session)
        if walk(preimage, slot - self._last_slot, tag) != self._last_value:
            return BAD
        self._last_slot, self._last_value = slot, preimage
        return ACCEPT


def mac(key: bytes, msg: bytes) -> bytes:
    """高频路径的链路层认证。截断到 16 B。

    Link-layer authentication on the high-rate path. Truncated to 16 B.
    """
    return hmac.new(key, msg, hashlib.sha256).digest()[:MAC_BYTES]


def mac_ok(key: bytes, msg: bytes, tag: bytes) -> bool:
    return hmac.compare_digest(mac(key, msg), tag)


def new_keypair():
    """Ed25519 密钥对。仅用于承诺根注册与视图切换。

    Ed25519 key pair. Used only for commitment-root registration and view changes.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey)
    sk = Ed25519PrivateKey.generate()
    return sk, sk.public_key()
