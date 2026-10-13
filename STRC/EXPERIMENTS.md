# STRC 实验设计：创新结论 ↔ E1–E5 / STRC experiment design: claims ↔ E1–E5

## 一、要验证的创新结论（按强度） / 1. Claims to verify (by strength)

| ID | 结论 / claim | 一句话 / in one sentence |
| --- | --- | --- |
| C1 | **边界划错** / **wrong boundary** | 走廊类扰动在任务图上 \(T_{\mathrm{direct}}=\varnothing\)，在预约表上种子/闭包非空 / A corridor disturbance has \(T_{\mathrm{direct}}=\varnothing\) on the task graph, while the seed set and the closure are nonempty on the reservation table |
| C2 | **闭包是对的影响对象** / **the closure is the right impact object** | 闭包外与种子无依赖；释放闭包后外侧预约可保持不变（包含性） / Nothing outside the closure depends on the seeds; after the closure is released, outside reservations can stay unchanged (containment) |
| C3 | **贡献在边界定义** / **the contribution is the boundary definition** | 同修复引擎下，只换 R1(任务图) / R2(闭包)，走廊扰动上 R2 胜、机器故障上两者接近 / Under the same repair engine, swapping only R1 (task graph) / R2 (closure), R2 wins on corridor disturbances and the two are close on machine faults |
| C4 | **结构可预测** / **structure is predictable** | 闭包规模随站点最小割变化（funnel 大、high 小） / Closure size moves with the station min-cut (funnel large, high small) |
| C5 | **与全局搜索互补** / **complements global search** | 紧预算闭包修复优，宽预算 clbs 重解优（交叉曲线） / Closure repair is better on a tight budget; clbs re-solve is better on a wide budget (a crossing curve) |
| C6 | **阶梯是加分项** / **the ladder is a bonus** | 多数 B 类扰动在改路/换车级恢复（非核心，有数再进贡献列表） / Most class-B disturbances recover at the reroute/vehicle-switch level (not core; enter the contribution list only once there are numbers) |

## 二、E1–E5 覆盖矩阵 / 2. E1–E5 coverage matrix

| 实验 / experiment | 覆盖结论 / claim covered | 不覆盖什么 / what it does not cover | 门禁？ / gate? |
| --- | --- | --- | --- |
| **E1 漏报** / **E1 missed detection** | **C1** | 不含修复质量 / not repair quality | **是（先做）** / **yes (do first)** |
| **E2 包含性** / **E2 containment** | **C2** | 不含「修得好」 / not "repaired well" | 是（E1 后） / yes (after E1) |
| **E3 边界消融** / **E3 boundary ablation** | **C3** | 不含结构规律 / not structural regularities | **是（与 E1 并列硬）** / **yes (as hard as E1)** |
| **E4 结构预测** / **E4 structure prediction** | **C4** | 需 funnel/high；协议须阻断 **LU 割边** 且看中位数 / needs funnel/high; the protocol must block the **LU cut edges** and look at the median | 探索中（均值易被单种子翻转） / exploratory (the mean is easily flipped by one seed) |
| **E5 权衡曲线** / **E5 tradeoff curve** | **C5** | 第1级 R2 未必在 Cmax 上交叉；以 **稳定性+耗时 vs Cmax** 证明互补 / level-1 R2 need not cross on Cmax; complementarity is shown by **stability + time vs Cmax** | ✅ `tools/e5_cross_curve.py` |
| （E6 阶梯深度） / (E6 ladder depth) | C6 | — | 可选 / optional |

**结论：E1–E5 足以覆盖 C1–C5（独立小论文主贡献）。**  
C6 不进主贡献亦可发。缺口只有「修复引擎本身」——E3/E5 的完整版需要 `repair.py`；但 E1、E3 的**规模对照版**（只比释放集，不跑修复）即可先证 C1/C3 的问题层与对象层。

**Conclusion: E1–E5 are enough to cover C1–C5 (the main contribution of a standalone short paper).**
C6 can be published without entering the main contribution. The only gap is "the repair engine itself" — the full versions of E3/E5 need `repair.py`; but the **size-comparison versions** of E1 and E3 (compare release sets only, do not run repair) can already establish the problem layer and the object layer of C1/C3.

## 三、分阶段落地 / 3. Phased delivery

1. **Phase A**：排程导出 + 扰动种子 + 闭包 + **E1** + E3 规模对照 ✅ / schedule export + disturbance seeds + closure + **E1** + E3 size comparison ✅
2. **Phase B**：E2a/E2b + 最小修复（第 1 级改路）+ E3 质量对照 ✅（见 `repair.py`） / E2a/E2b + minimal repair (level-1 reroute) + E3 quality comparison ✅ (see `repair.py`)
3. **Phase C**：E4（`tools/e4_structure.py`）+ E5（`tools/e5_cross_curve.py`，R0+/R2 交叉曲线）✅ / E4 (`tools/e4_structure.py`) + E5 (`tools/e5_cross_curve.py`, R0+/R2 crossing curve) ✅

## 四、统一口径 / 4. Shared conventions

- 下层：`clbs` 预约表 / 路由 / 校验器（经 `clbs_bridge`） / Lower layer: `clbs` reservation table / router / validator (via `clbs_bridge`)
- 初始排程：冲突自由解码的可行解（可用短 GA 或 `ma_min_time` 启发式） / Initial schedule: a feasible solution from conflict-free decoding (a short GA or the `ma_min_time` heuristic)
- 扰动时刻 `t_now`：默认取 makespan 的 30%–50%，保证仍有未来预约 / Disturbance time `t_now`: by default 30%–50% of the makespan, so future reservations remain
- 报告列：`|T_direct|`, `|T_impact|`, `|seeds|`, `|closure|`, `lu_min_cut`, `feasible_after_block` / Reported columns: `|T_direct|`, `|T_impact|`, `|seeds|`, `|closure|`, `lu_min_cut`, `feasible_after_block`
