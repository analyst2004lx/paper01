# WireGuard connection issue
_Exported on 7/26/2026 at 12:19:39 GMT+8 from Cursor (3.13.10)_

---

**User**

@wireguard-log-2026-07-26T111318.txt 是我的wireguard日志，wireguard连不上远端的Vultr并进行路由服务，昨天好好的，今天就不行，请帮我分析出了什么问题，该怎么解决

---

**Cursor**

我先查看这份 WireGuard 日志，定位连不上 Vultr 的具体错误。

日志里握手失败很明显。我再核对成功握手出现过没有，以及从何时起变成单向无响应。

结论：**不是 Windows 客户端配置本身坏了，而是从昨天 20:17 关机/注销之后，今天再也收不到 Vultr（`104.156.231.123:51820`）的任何 WireGuard 回包，握手一直卡死。**

## 日志里发生了什么

| 时间 | 状态 |
|------|------|
| 昨天约 19:23–20:15 | 正常：能收到 Vultr 的 `keepalive`，隧道在工作 |
| 昨天 20:17 | 本地主动 `Shutting down`，随后 Windows 注销 |
| 今天 10:35 起 | 只见 `Sending handshake initiation`，**整日 0 条 Receiving**，反复 `Handshake did not complete after 5 seconds` |

关键证据：
- 对端 IP `104.156.231.123` **能 ping 通**（主机在线），说明不是整机宕机。
- WireGuard 用的是 **UDP 51820**；今天本地只发包、收不到握手响应 → UDP 通道或服务端 WG 有问题。
- 你当前出口是 `172.20.10.11`（很像手机热点），对 UDP VPN 经常比昨天家宽更严。

## 最可能原因（按优先级）

1. **Vultr 上 WireGuard 服务停了 / 进程挂了**（重启后没起来最常见）
2. **Vultr 防火墙没放行 UDP 51820**（系统 `ufw`/`iptables` 或 Vultr 控制台 Firewall）
3. **当前网络（热点/运营商）拦了 UDP 51820**（ICMP 通、WG 不通很典型）
4. **服务端密钥/配置被改过**（密钥不对时 WireGuard 会静默丢包，表现也是“只发不收”）

## 怎么修

### 1. 先 SSH 上 Vultr 查服务（最关键）

```bash
# 接口是否在
sudo wg show

# 服务是否在跑（按你实际安装方式二选一）
sudo systemctl status wg-quick@wg0
# 或
sudo systemctl status wireguard

# 是否在听 51820/udp
sudo ss -ulnp | grep 51820
```

如果 `wg show` 没有接口或服务 inactive：

```bash
sudo systemctl enable --now wg-quick@wg0
# 或
sudo wg-quick up wg0
```

### 2. 放行 UDP 51820

```bash
# ufw 示例
sudo ufw allow 51820/udp
sudo ufw reload
```

同时在 **Vultr → Firewall** 里确认有规则：`UDP 51820` 入站允许。

### 3. 看服务端有没有收到你的握手

在 Vultr 上抓包几秒，同时在 Windows 再点一次连接：

```bash
sudo tcpdump -ni any udp port 51820
```

- **完全没包** → 本地网络/运营商拦 UDP，或中间被墙；换网络（家宽/另一热点）再试  
- **有包进来但 Windows 仍无响应** → 多半是密钥不匹配或 `wg` 配置错误，核对两边 `PublicKey`/`PrivateKey`/`ListenPort`

### 4. Windows 端快速自检

1. 换到昨天能用的网络再连一次（排除热点拦 UDP）  
2. 确认配置里 `Endpoint = 104.156.231.123:51820`，且有 `PersistentKeepalive = 25`  
3. 关掉再开隧道；必要时重启 WireGuard 服务  

### 5. 握手通了再查“路由服务”

握手成功后若仍上不了网，再到 Vultr 查转发/NAT（这是下一步，不是今天卡死的原因）：

```bash
sysctl net.ipv4.ip_forward   # 应为 1
sudo iptables -t nat -L -n -v | grep MASQUERADE
```

---

**一句话**：昨天晚上断连后，今天是 **UDP 握手完全无回包**；主机 ICMP 正常，优先上 Vultr 把 `wg` 拉起来并放行 `51820/udp`，同时尽量换非热点网络验证。

如果你能贴 Vultr 上 `sudo wg show` 和 `systemctl status wg-quick@wg0` 的输出，我可以帮你直接判断是服务挂了、防火墙，还是密钥问题。

---

**User**

root@vultr:~#
 sudo wg show
root@vultr:~#: command not found
interface: wg0
  public key: NkCoffCF7P+Hc+nAXd5DqB02M6E3aSHv7jyn6vLt/0c=
  private key: (hidden)
  listening port: 51820

peer: xqXshr2tB9A4ncifg35CfmRoN+3zESWBIqO0bFblQ24=
  preshared key: (hidden)
  endpoint: 223.104.153.8:31098
  allowed ips: 10.66.66.5/32
  latest handshake: 15 hours, 7 minutes, 55 seconds ago
  transfer: 151.02 MiB received, 985.77 MiB sent

peer: yaPmaWIbe9gKcOsYbhQQo6tTXT1ElCVIXASa05/mrGU=
  preshared key: (hidden)
  allowed ips: 10.66.66.2/32

peer: tvs+7sfKL2fp3s7n2+u25rqVvh3PW+bR+XwkebEbCy4=
  preshared key: (hidden)
  allowed ips: 10.66.66.3/32

peer: wOkyC6vKi8pXT6HMCd2CGhrEuTSYMnNxVJYtNLAa+xk=
  preshared key: (hidden)
  allowed ips: 10.66.66.4/32

peer: rYdF0C+lGnsYBhuJFuLyW5L5lVdeAIPjEt6LD7pSpFo=
  preshared key: (hidden)
  allowed ips: 10.66.66.6/32



root@vultr:~# systemctl status wg-quick@wg0
● wg-quick@wg0.service - WireGuard via wg-quick(8) for wg0
     Loaded: loaded (/usr/lib/systemd/system/wg-quick@.service; enabled; preset: enabled)
     Active: active (exited) since Sat 2026-07-25 02:41:27 UTC; 24h ago
 Invocation: 4a8b376cd7614ef59d11cdbe29198536
       Docs: man:wg-quick(8)
             man:wg(8)
             https://www.wireguard.com/
             https://www.wireguard.com/quickstart/
             https://git.zx2c4.com/wireguard-tools/about/src/man/wg-quick.8
             https://git.zx2c4.com/wireguard-tools/about/src/man/wg.8
   Main PID: 111399 (code=exited, status=0/SUCCESS)
   Mem peak: 2.6M
        CPU: 109ms

Jul 25 02:41:26 vultr systemd[1]: Starting wg-quick@wg0.service - WireGuard via wg-quick(8) for wg0...
Jul 25 02:41:26 vultr wg-quick[111399]: [#] ip link add dev wg0 type wireguard
Jul 25 02:41:26 vultr wg-quick[111399]: [#] wg setconf wg0 /dev/fd/63
Jul 25 02:41:26 vultr wg-quick[111399]: [#] ip -4 address add 10.66.66.1/24 dev wg0
Jul 25 02:41:26 vultr wg-quick[111399]: [#] ip link set mtu 1420 up dev wg0
Jul 25 02:41:26 vultr wg-quick[111399]: [#] iptables -I FORWARD 1 -i wg0 -o enp1s0 -j ACCEPT; iptables -I FORWARD 1 -i enp1s0 -o w>
Jul 25 02:41:27 vultr systemd[1]: Finished wg-quick@wg0.service - WireGuard via wg-quick(8) for wg0.
lines 1-21...skipping...
● wg-quick@wg0.service - WireGuard via wg-quick(8) for wg0
     Loaded: loaded (/usr/lib/systemd/system/wg-quick@.service; enabled; preset: enabled)
     Active: active (exited) since Sat 2026-07-25 02:41:27 UTC; 24h ago
 Invocation: 4a8b376cd7614ef59d11cdbe29198536
       Docs: man:wg-quick(8)
             man:wg(8)
             https://www.wireguard.com/
             https://www.wireguard.com/quickstart/
             https://git.zx2c4.com/wireguard-tools/about/src/man/wg-quick.8
             https://git.zx2c4.com/wireguard-tools/about/src/man/wg.8
   Main PID: 111399 (code=exited, status=0/SUCCESS)
   Mem peak: 2.6M
        CPU: 109ms

Jul 25 02:41:26 vultr systemd[1]: Starting wg-quick@wg0.service - WireGuard via wg-quick(8) for wg0...
Jul 25 02:41:26 vultr wg-quick[111399]: [#] ip link add dev wg0 type wireguard
Jul 25 02:41:26 vultr wg-quick[111399]: [#] wg setconf wg0 /dev/fd/63
Jul 25 02:41:26 vultr wg-quick[111399]: [#] ip -4 address add 10.66.66.1/24 dev wg0
Jul 25 02:41:26 vultr wg-quick[111399]: [#] ip link set mtu 1420 up dev wg0
Jul 25 02:41:26 vultr wg-quick[111399]: [#] iptables -I FORWARD 1 -i wg0 -o enp1s0 -j ACCEPT; iptables -I FORWARD 1 -i enp1s0 -o wg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; iptables -t nat -A>
Jul 25 02:41:27 vultr systemd[1]: Finished wg-quick@wg0.service - WireGuard via wg-quick(8) for wg0.


---

**Cursor**

服务端是正常的。问题已经能缩小到：**你这台 Windows（`windows02`）今天的握手包没有到达 Vultr，或密钥对不上。**

## 服务端结论

- `wg0` 在跑，监听 `51820`
- `wg-quick@wg0` 正常（`active`）
- 唯一有过成功握手的 peer 是 **`10.66.66.5`**：

```text
peer: xqXshr2tB9A4ncifg35CfmRoN+3zESWBIqO0bFblQ24=
  endpoint: 223.104.153.8:31098
  allowed ips: 10.66.66.5/32
  latest handshake: 15 hours ago   ← 正好对上昨晚约 20:15 断开
```

其它 peer（`.2` `.3` `.4` `.6`）都没有 `latest handshake`，说明最近都没连上。

所以：**不是 Vultr WireGuard 挂了**，而是昨晚那个成功 peer 断了之后，今天没有新的成功握手。

## 今天连不上的真正含义

服务器仍记着旧出口：`223.104.153.8:31098`（昨天的公网 IP）。  
你现在本机是 `172.20.10.11`（很像手机热点），公网 IP 已经变了。

客户端从新网络发包时，若服务端一直显示 `latest handshake: 15 hours ago` 不变，说明：

1. **UDP 51820 包根本没到 Vultr**（热点/运营商拦截最常见），或  
2. **Windows 配置的公钥/PSK 对不上**（WireGuard 会静默丢弃）

## 马上做这两步（在 Vultr 上）

**终端 1 — 抓包：**

```bash
sudo tcpdump -ni any udp port 51820 -c 20
```

**同时在 Windows 点连接**，看有没有包进来。

| 抓包结果 | 原因 | 处理 |
|---------|------|------|
| 完全没包 | 当前网络拦了 UDP | 换家宽/另一网络再连 |
| 有包进来，但 `wg show` 的 handshake 仍是 15h 前 | 密钥/PSK 不匹配 | 核对下面第 3 步 |
| 有包且 handshake 更新 | 隧道已通，再查路由/NAT | 查转发规则 |

**再看握手是否刷新：**

```bash
sudo wg show
```

重点看你对应 peer 的 `latest handshake` 是否变成几秒前。

## 核对 Windows 配置（很重要）

在 Windows 的 `windows02` 配置里确认：

1. **本机 Address** 是不是 `10.66.66.5/32`（或 `/24`）  
   - 若是 `.2/.3/.4/.6`，那你连的不是昨天那个 peer
2. **Peer 的 PublicKey** 必须是服务端的：  
   `NkCoffCF7P+Hc+nAXd5DqB02M6E3aSHv7jyn6vLt/0c=`
3. **本机公钥** 必须等于服务端里对应 peer 的那串（`.5` 应是 `xqXshr2tB9A4ncifg35CfmRoN+3zESWBIqO0bFblQ24=`）
4. **PresharedKey** 两边一致  
5. 建议有：`PersistentKeepalive = 25`

在 Windows 上看本机公钥：WireGuard 界面里该隧道的公钥，或导出配置核对。

## 建议操作顺序

1. Vultr 开着 `tcpdump`，Windows 再连一次  
2. 若没包 → **先换网络**（别用当前 `172.20.10.x` 热点）  
3. 若有包但握手不更新 → 把 Windows 配置里的 `Address`、本机公钥、`PublicKey`、`PresharedKey`（可打码中间）发我，我帮你对  
4. 握手通了若仍不能当路由出口，再查：

```bash
sysctl net.ipv4.ip_forward
sudo iptables -t nat -S | grep -i masq
```

---

**一句话**：Vultr 服务正常；卡在「今天这台 Windows 的握手没成功」。先用 `tcpdump` 区分是**网络拦 UDP**还是**密钥不对**。把抓包结果（有/无包）和 `windows02` 的 `Address`/公钥发过来即可继续往下排。

---

**User**

我的确使用了热点，密钥也是对的，我本机用的隧道地址是10.66.66.5/32。其它几台机器最近两天没有链接过Vultr。

---

**Cursor**

那就对上了：**服务端和密钥都没问题，是当前热点网络把 WireGuard 的 UDP 51820 拦了或弄丢了。**

依据很一致：
- Vultr 上 `10.66.66.5` 最后握手停在约 15 小时前（昨晚断连）
- 今天本机只发包、无回包
- 主机 ICMP 能通，但 WG 用不了 —— 热点上很常见

## 怎么处理

**首选：换网络再连**
- 家宽 / 公司网 / 另一家运营商热点
- 连上后 Vultr 上应看到 `latest handshake` 变成几秒前

**必须继续用热点时，试这些：**

1. **换端口**（有时只拦 51820）  
   Vultr `/etc/wireguard/wg0.conf` 把 `ListenPort` 改成例如 `51821` 或 `443`，放行该 UDP，重启：
   ```bash
   sudo systemctl restart wg-quick@wg0
   ```
   Windows 端 `Endpoint` 改成 `104.156.231.123:新端口`

2. **手机开飞行模式再关**，或改用 **USB 共享网络**（有时比 WiFi 热点松一点）

3. **热点开「兼容性/最大兼容」**（若有），关掉省电、VPN、专属 DNS 类加速

4. 仍不行：用 **wstunnel / udp2raw / cloaking** 把 WG 包封装进 TCP/443（改动较大，换网能好就不必上）

## 连上后快速确认

Vultr：
```bash
sudo wg show
# 10.66.66.5 的 latest handshake 应为 seconds ago
```

Windows：能 ping `10.66.66.1`，再测外网是否走隧道。

**结论：先换非热点网络验证；密钥和 `10.66.66.5` 不用改。** 换网后若 handshake 立刻恢复，就可以完全认定是热点 UDP 问题。

---

**User**

使用热点就不能使用Vultr吗？我想解决这个问题。昨天热点用得好好的，今天不能用是因为热点的地址变了吗？

---

**Cursor**

可以用热点连 Vultr，昨天能连就说明本身没问题。**公网 IP 变了一般不是原因**——WireGuard 客户端会主动握手，服务端会更新 endpoint。

## 昨天能用、今天不能，通常不是“地址变了”

| 现象 | 说明 |
|------|------|
| 公网 IP 从 `223.104.153.8` 换成别的 | 正常，WG 支持漫游 |
| 服务端仍显示旧 endpoint + 15 小时前握手 | 说明**今天的握手包没成功进来/回去** |
| 热点本地仍是 `172.20.10.x` | 只是手机给电脑的内网地址，不影响结论 |

更常见是：**同一热点，运营商对 UDP/VPN 的拦截或 NAT 行为今天变差了**（基站、CGNAT、QoS、短暂封禁都可能），表现就是 ICMP 通、WG 不通。

## 想稳定用热点：按这个顺序做

### 1. 换 UDP 端口（优先试，改动小）

很多网络会盯 `51820`，对 `443`/`53` 松一些。

**Vultr** 编辑 `/etc/wireguard/wg0.conf`：

```ini
ListenPort = 443
```

放行并重启：

```bash
sudo ufw allow 443/udp   # 若用 ufw
# Vultr 控制台 Firewall 也要放行 UDP 443
sudo systemctl restart wg-quick@wg0
sudo wg show   # 确认 listening port: 443
```

**Windows** 把 Endpoint 改成：

```text
Endpoint = 104.156.231.123:443
```

保存后再连。Vultr 上看 `10.66.66.5` 的 `latest handshake` 是否变成几秒前。

### 2. 客户端加保活 + 降 MTU（热点很有用）

Windows 配置建议：

```ini
[Interface]
Address = 10.66.66.5/32
MTU = 1280

[Peer]
Endpoint = 104.156.231.123:443
PersistentKeepalive = 25
```

`PersistentKeepalive = 25` 让客户端持续打洞，热点 NAT 不容易把映射掐掉。

### 3. 连的时候在 Vultr 抓包确认

```bash
sudo tcpdump -ni any udp port 443 -c 20
```

同时 Windows 点连接：
- **有包**且握手更新 → 端口策略生效，以后热点可继续用  
- **仍没包** → 当前蜂窝链路在拦 UDP，需要第 4 步

### 4. UDP 仍被拦：用 TCP 封装（一劳永逸但稍复杂）

在 Vultr + Windows 上加一层，例如：
- **wstunnel**（WebSocket/TLS 443）
- **udp2raw** / **hysteria** 等把 WG 包伪装成 TCP

适合“换端口也不行、但 HTTPS 能上”的运营商环境。

---

**直接回答你的两个问题：**
1. **热点可以用 Vultr**，不是热点就不能用。  
2. **不是因为地址变了**；是今天这条热点链路上 **UDP 握手没通**。先改 `443/udp` + `PersistentKeepalive=25` + `MTU=1280`，多数情况能恢复。

改完端口后把 `sudo wg show` 里 `.5` 那一段（有无新 handshake）发我，我帮你看是否已经好了。

---

**User**

因为好几台电脑使用了同一个Vultr服务器，我担心更改是否会影响其它主机使用？

---

**Cursor**

会，但取决于你怎么改。

## 若直接改 `ListenPort = 443`

**会影响所有主机。**  
服务端只听一个端口时，其它电脑配置里若仍是 `Endpoint = …:51820`，都会连不上，必须一起改成新端口。

密钥、`AllowedIPs`、各机的 `10.66.66.x` **不用改**，只改 Endpoint 端口。

---

## 不想影响其它机器：推荐这两种

### 方案 A：端口转发（推荐，其它机器零改动）

`wg0` 继续听 `51820`，再把 `443/udp` 转到 `51820`：

```bash
# 放行 443（按你实际防火墙调整）
sudo ufw allow 443/udp

# 把发到 443 的 UDP 转到 WireGuard 的 51820
sudo iptables -t nat -A PREROUTING -p udp --dport 443 -j REDIRECT --to-ports 51820
```

- **其它电脑**：继续用 `51820`，完全不用动  
- **你这台热点电脑**：Endpoint 改成 `104.156.231.123:443` 试连  

若重启后规则消失，把上面 `iptables` 写进 `/etc/wireguard/wg0.conf` 的 `PostUp`，并在 `PostDown` 里删掉对应规则。

### 方案 B：只改你这台客户端（不动服务器）

先试，对其它主机零影响：

```ini
MTU = 1280
PersistentKeepalive = 25
```

有时热点上这样就够了；不行再用方案 A。

---

## 小结

| 做法 | 其它主机 |
|------|----------|
| 改服务器 `ListenPort` | 要一起改 Endpoint |
| `443 → 51820` 转发 | 不用改 |
| 只改你电脑的 MTU/Keepalive | 不用改 |

建议：先只改你本机 MTU + Keepalive；仍不行再上方案 A，这样其它几台可以继续用 `51820`。

---

**User**

方案 B：只改你这台客户端（不动服务器），具体我应该怎么做？是在powershell里运行这两条指令还是怎么做？另外，我如果关闭本机Windows上的wireguard软件，是否影响我用热点继续上其它网站（此时不连接Vultr了）？

---

**Cursor**

不是 PowerShell。在 **WireGuard 图形界面**里改配置即可。

## 方案 B：怎么改

1. 打开 **WireGuard**
2. 选中隧道 `windows02`（或你实际用的那个）
3. 点 **Edit**（编辑）
4. 改成类似这样（只加/改这两项，其它密钥别动）：

```ini
[Interface]
PrivateKey = （保持原样）
Address = 10.66.66.5/32
MTU = 1280

[Peer]
PublicKey = （保持原样）
PresharedKey = （若有，保持原样）
AllowedIPs = （保持原样）
Endpoint = 104.156.231.123:51820
PersistentKeepalive = 25
```

5. 保存 → 先 **Deactivate** 再 **Activate**（或关掉再打开隧道）

若编辑里已有 `PersistentKeepalive = 25`，只加 `MTU = 1280` 即可。

---

## 关掉本机 WireGuard，还能用热点上其它网站吗？

**可以，而且通常更正常。**

- **断开/退出 WireGuard**：流量走手机热点，和没装 VPN 一样，上其它网站不受影响。
- **WireGuard 一直连着但握手失败**：若 `AllowedIPs` 含 `0.0.0.0/0`，流量会进“坏掉的隧道”，反而容易 **打不开网页**。连不上 Vultr 时，应先断开隧道。

关闭方式：
- 点 **Deactivate** = 只断隧道，软件可留着  
- 退出 WireGuard 程序 = 同样不再走 VPN  

两种都不会妨碍你用热点正常上网。

---

**User**

我的wireguard现有配置（没有修改过）如下：
[Interface]
PrivateKey = .......
Address = 10.66.66.5/32
DNS = 1.1.1.1, 8.8.8.8
MTU = 1380

[Peer]
PublicKey = NkCoffCF7P+Hc+nAXd5DqB02M6E3aSHv7jyn6vLt/0c=
PresharedKey = 7k0AzgCp33tZi6b8iHLE7y3XnP+DXfCslYv5JxL/4hw=
AllowedIPs = 0.0.0.0/0
Endpoint = 104.156.231.123:51820
PersistentKeepalive = 25


---

**Cursor**

你这份配置里，**方案 B 其实已经基本做完了**：

- 已有 `PersistentKeepalive = 25`
- 已有 `MTU = 1380`
- 服务端公钥也对（`NkCoff…`）

所以今天连不上，**多半不是缺这两项**，而是热点把 `51820/udp` 弄不通了。方案 B 最多再试一次把 MTU 再降一点。

## 你可以先做的唯一小改动

把：

```ini
MTU = 1380
```

改成：

```ini
MTU = 1280
```

保存后断开再连接。若仍一直 `Handshake did not complete`，就别在方案 B 上耗了，改走 **方案 A（443→51820 转发）**，只改你这台的 Endpoint 为 `:443`，其它电脑继续 `:51820`。

## 很重要的一点

你有：

```ini
AllowedIPs = 0.0.0.0/0
```

这是**全局代理**：隧道“看起来连着”但握手失败时，本机上网、DNS（`1.1.1.1`/`8.8.8.8`）都会一起挂。  
**连不上 Vultr 时务必 Deactivate**，关掉后热点上其它网站就恢复正常。

## 安全提醒

你把 `PresharedKey` 发出来了。若这段对话会存档/转发，建议之后在 Vultr 和各客户端上**轮换一次 PSK**（不急，先把连通性修好再说）。

---

**下一步建议**：先试 `MTU = 1280`；不行就上方案 A。需要的话我可以按你当前的 `wg0.conf` 结构，直接写好要加的 `PostUp`/`PostDown` 两行。

---

**User**

试过了，该方案行不通，告诉我方案A具体应该怎么做，同时，我不想影响其它主机使用Vultr服务器。

---

**Cursor**

可以。方案 A 的思路是：**服务器继续听 51820（其它主机不动），额外把 UDP 443 转到 51820；只有你这台改 Endpoint。**

下面按「先临时生效验证 → 再写进配置防重启丢失」做，尽量不影响其它人。

---

## 0. 事先确认（Vultr SSH）

```bash
# 看 UDP 443 有没有被占用（应为空；TCP 443 有 HTTPS 没关系）
sudo ss -ulnp | grep 443 || echo "UDP 443 free"

# 看当前 wg 仍在 51820
sudo wg show | head -n 5
```

若 `UDP 443` 已被其它程序占用，改用 `8443` 或 `53`（下面命令里把 `443` 换成所选端口即可）。

---

## 1. Vultr：临时加转发（先不要重启 wg）

```bash
# 系统防火墙（若用 ufw）
sudo ufw allow 443/udp
sudo ufw reload

# 把发到本机 UDP 443 的包转到 WireGuard 的 51820
sudo iptables -t nat -A PREROUTING -p udp --dport 443 -j REDIRECT --to-ports 51820

# 确认规则在
sudo iptables -t nat -L PREROUTING -n -v | grep 443
```

**同时打开 Vultr 网页控制台 → Firewall**（若这台机器挂了防火墙组）：  
新增一条：**UDP 443 Allow**（来源可先 `0.0.0.0/0`）。  
只开系统 `ufw`、不开控制台防火墙，外网仍可能进不来。

此时 **不要** `systemctl restart wg-quick@wg0`，其它主机继续用 `51820`，不受影响。

---

## 2. 只改你这台 Windows

编辑隧道，**只改一行**：

```ini
Endpoint = 104.156.231.123:443
```

其余（密钥、`Address`、`AllowedIPs`、`PersistentKeepalive` 等）不动。  
建议同时保留：

```ini
MTU = 1280
```

保存 → Deactivate → Activate。

---

## 3. 验证是否成功

**Vultr：**

```bash
# 连接时抓包（另开窗口）
sudo tcpdump -ni any udp port 443 -c 20

# 再看握手
sudo wg show
```

成功时：`10.66.66.5` 的 `latest handshake` 应为 **seconds ago**。

**Windows：** 能 `ping 10.66.66.1`，浏览器能上网。

| 结果 | 含义 |
|------|------|
| 抓包有 443、握手更新 | 方案 A 生效 |
| 抓包仍无包 | 热点连 443/udp 也拦了，或 Vultr 控制台防火墙没放行 |
| 有包但握手不更新 | 再查密钥（你这边之前已确认，概率低） |

其它主机：Endpoint 仍是 `:51820`，**不用改**。

---

## 4. 验证成功后再持久化（防重启丢失）

编辑服务端配置：

```bash
sudo nano /etc/wireguard/wg0.conf
```

在现有 `PostUp = ...` **末尾追加**（注意前面有分号接在原命令后）：

```text
; iptables -t nat -A PREROUTING -p udp --dport 443 -j REDIRECT --to-ports 51820
```

在现有 `PostDown = ...` **末尾追加**：

```text
; iptables -t nat -D PREROUTING -p udp --dport 443 -j REDIRECT --to-ports 51820
```

示例（不要整段照抄覆盖你原来的规则，只是示意结构）：

```ini
[Interface]
Address = 10.66.66.1/24
ListenPort = 51820
PrivateKey = ...
PostUp = iptables -I FORWARD 1 -i wg0 -o enp1s0 -j ACCEPT; iptables -I FORWARD 1 -i enp1s0 -o wg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; iptables -t nat -A POSTROUTING -o enp1s0 -j MASQUERADE; iptables -t nat -A PREROUTING -p udp --dport 443 -j REDIRECT --to-ports 51820
PostDown = iptables -D FORWARD -i wg0 -o enp1s0 -j ACCEPT; iptables -D FORWARD -i enp1s0 -o wg0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT; iptables -t nat -D POSTROUTING -o enp1s0 -j MASQUERADE; iptables -t nat -D PREROUTING -p udp --dport 443 -j REDIRECT --to-ports 51820
```

你机器上的 `PostUp`/`PostDown` 可能已有内容，**只追加** REDIRECT 那两段即可，别删掉原来的 FORWARD/MASQUERADE。

然后**选一个其它人影响最小的时间**执行一次：

```bash
sudo systemctl restart wg-quick@wg0
sudo wg show
sudo iptables -t nat -L PREROUTING -n -v | grep 443
```

重启后其它主机一般会在下次 keepalive/握手时自动恢复（它们仍连 `51820`）。

---

## 影响范围（给你吃个定心丸）

| 项目 | 其它主机 |
|------|----------|
| `ListenPort` 仍是 51820 | 不变 |
| Endpoint 仍 `:51820` | 不用改 |
| 密钥 / `10.66.66.x` | 不用改 |
| 仅你 Windows 改 `:443` | 只有你走 443 |

---

## 若 443 也不通

把上面所有 `443` 换成 `8443`（或 `53`），Windows Endpoint 同步改，并在 Vultr 防火墙放行对应 **UDP** 端口。

---

按顺序做完第 1、2 步后，把 `sudo wg show` 里 `10.66.66.5` 那段（有无新 handshake）发我，我帮你看是否已经通。

---

**User**

wg0.conf修改完了后，怎么保存（nano使用问题）并关闭？

---

**Cursor**

在 nano 里这样操作：

1. **保存**：按 `Ctrl + O`（Write Out）  
   - 底部会显示文件名，直接按 `Enter` 确认  

2. **退出**：按 `Ctrl + X`  

若退出前还没保存，会问 `Save modified buffer?`：按 `Y`，再按 `Enter`。

---

保存退出后建议执行：

```bash
sudo systemctl restart wg-quick@wg0
sudo wg show
sudo iptables -t nat -L PREROUTING -n -v | grep 443
```

---

**User**


root@vultr:~# sudo nano /etc/wireguard/wg0.conf
root@vultr:~# sudo systemctl restart wg-quick@wg0
sudo wg show
sudo iptables -t nat -L PREROUTING -n -v | grep 443
interface: wg0
  public key: NkCoffCF7P+Hc+nAXd5DqB02M6E3aSHv7jyn6vLt/0c=
  private key: (hidden)
  listening port: 51820

peer: yaPmaWIbe9gKcOsYbhQQo6tTXT1ElCVIXASa05/mrGU=
  preshared key: (hidden)
  allowed ips: 10.66.66.2/32

peer: tvs+7sfKL2fp3s7n2+u25rqVvh3PW+bR+XwkebEbCy4=
  preshared key: (hidden)
  allowed ips: 10.66.66.3/32

peer: wOkyC6vKi8pXT6HMCd2CGhrEuTSYMnNxVJYtNLAa+xk=
  preshared key: (hidden)
  allowed ips: 10.66.66.4/32

peer: xqXshr2tB9A4ncifg35CfmRoN+3zESWBIqO0bFblQ24=
  preshared key: (hidden)
  allowed ips: 10.66.66.5/32

peer: rYdF0C+lGnsYBhuJFuLyW5L5lVdeAIPjEt6LD7pSpFo=
  preshared key: (hidden)
  allowed ips: 10.66.66.6/32
    0     0 REDIRECT   udp  --  *      *       0.0.0.0/0            0.0.0.0/0            udp dpt:443 redir ports 51820


---

**Cursor**

服务端这边已经正确：

- `wg0` 仍在听 **51820**（其它主机不用改）
- `REDIRECT udp dpt:443 → 51820` 已生效  
- 计数 `0 0` 正常，说明你这台还没从 443 连过来

## 接下来只改你的 Windows

1. Endpoint 改为：`104.156.231.123:443`
2. 保存 → Deactivate → Activate
3. 再在 Vultr 执行：

```bash
sudo wg show
sudo iptables -t nat -L PREROUTING -n -v | grep 443
```

成功时应看到：
- `10.66.66.5` 的 `latest handshake` 为 **seconds ago**
- REDIRECT 那一行的包计数 **不再是 0**

若仍不通，再确认两处：
1. `sudo ufw status` 是否有 `443/udp ALLOW`
2. Vultr 控制台 Firewall 是否放行了 **UDP 443**

其它电脑继续用 `:51820` 即可。连上后把 `wg show` 里 `.5` 那段发我，我帮你确认。

---

**User**

如果其它主机上的wireGuard软件也将端口改成443是不是也可以运行？

---

**Cursor**

可以。服务端已把 **UDP 443 → 51820**，其它主机把 Endpoint 改成：

```text
Endpoint = 104.156.231.123:443
```

也能连，和继续用 `51820` 效果一样。

注意：
- 只改 **Endpoint 端口**，密钥、`Address`（各自的 `10.66.66.x`）不要动  
- **51820 和 443 可以混用**：有的机器用旧端口，有的用 443，都能连  
- 前提是 Vultr 防火墙已放行 **UDP 443**（你这台若已通，其它机一般也可以）

