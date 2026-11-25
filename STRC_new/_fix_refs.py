P = r"c:\Users\analy\Desktop\AI_Folder\paper04\paper04_CN_v3.tex"
src = open(P, encoding="utf-8").read()
R = [
    ("在规模批次上被改动的占用明显减少，而耗时相当（第~\\ref{sec:cheap}~节）。",
     "在规模批次上被改动的占用明显减少，而耗时相当（第~\\ref{sec:boundary}~节）。"),
    ("规模批次（第~\\ref{sec:cheap}~节）上升级约占 \\(W\\) 的 \\(0.2\\%\\)--\\(0.3\\%\\)，改为全图重规划的只有 \\(1\\) 对（第~\\ref{sec:cheap}~节）。",
     "规模批次（第~\\ref{sec:ablation}~节）上升级约占 \\(W\\) 的 \\(0.2\\%\\)--\\(0.3\\%\\)，改为全图重规划的只有 \\(1\\) 对。"),
    ("首轮失败的各 \\(2\\) 对都在第三级恢复可行（第~\\ref{sec:cheap}~节）。",
     "首轮失败的各 \\(2\\) 对都在第三级恢复可行（第~\\ref{sec:boundary}~节）。"),
    ("是唯一能单独检验预约影响集作用的对照（第~\\ref{sec:cheap}~节）。",
     "是唯一能单独检验预约影响集作用的对照（第~\\ref{sec:cheap}、\\ref{sec:boundary}~节）。"),
    ("推断性检验均在第~\\ref{sec:cheap}~节：",
     "推断性检验均在第~\\ref{sec:cheap}、\\ref{sec:ablation}~节："),
    ("来源是冻结集不被其他运输的重规划挤动（第~\\ref{sec:cheap}~节）。",
     "来源是冻结集不被其他运输的重规划挤动（第~\\ref{sec:boundary}~节）。"),
    ("且使完工时间略增（第~\\ref{sec:cheap}~节）。",
     "且使完工时间略增（第~\\ref{sec:layering}~节）。"),
    ("须扩大范围（第~\\ref{sec:cheap}~节）。",
     "须扩大范围（第~\\ref{sec:boundary}~节）。"),
]
for a, b in R:
    assert src.count(a) == 1, a
    src = src.replace(a, b)
open(P, "w", encoding="utf-8", newline="").write(src)
print("ok")
