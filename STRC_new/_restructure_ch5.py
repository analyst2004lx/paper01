import sys

P = r"c:\Users\analy\Desktop\AI_Folder\paper04\paper04_CN_v3.tex"
src = open(P, encoding="utf-8").read()

marks = [
    ("E1", "\\subsection{E1：工序依赖图给出空范围}"),
    ("E2", "\\subsection{E2：闭合性与集外不变}"),
    ("E3", "\\subsection{E3：边界消融}"),
    ("E4old", "\\subsection{E4：路网结构指标能否预测影响集规模（探索性）}"),
    ("E5", "\\subsection{E5：与全局重调度的权衡}"),
    ("E6old", "\\subsection{E6：扰动类型与划界对象的交叉}"),
    ("E7a", "\\subsection{E7：毫秒量级内的对照}"),
    ("E7b", "\\textbf{划界收益随算例规模与阻断时长的变化。}"),
    ("E8", "\\subsection{E8：规模外推}"),
    ("pub", "\\subsection{外部布局批次的复现}"),
]
pos = []
for name, m in marks:
    i = src.find(m)
    if i < 0 or src.count(m) != 1:
        sys.exit("marker problem: " + name)
    pos.append(i)
end_sec = src.find("\\section{结论}")
end = src.rfind("%% ====", 0, end_sec)
end = src.rfind("\n", 0, end) + 1
assert pos == sorted(pos) and pos[-1] < end
blocks = {}
for k, (name, _) in enumerate(marks):
    blocks[name] = src[pos[k]:(pos[k + 1] if k + 1 < len(marks) else end)]

def demote(b, old, new):
    assert b.startswith(old), old
    return new + b[len(old):]

B = blocks
E1 = demote(B["E1"], marks[0][1], "\\subsubsection{E1：工序依赖图给出空范围}")
E2 = demote(B["E2"], marks[1][1], "\\subsubsection{E2：闭合性与集外不变}")
E3 = demote(B["E3"], marks[2][1], "\\subsubsection{E3：只更换划界对象}")
E4 = demote(B["E6old"], marks[5][1], "\\subsubsection{E4：四类扰动下的划界与修复}")
E5 = demote(B["E5"], marks[4][1], "\\subsubsection{E5：与全局重调度对比}")
E6 = demote(B["E7a"], marks[6][1], "\\subsubsection{E6：毫秒量级内的对照}")
E7 = B["E7b"]
E8 = demote(B["E8"], marks[8][1], "\\subsection{规模外推}")
PUB = demote(B["pub"], marks[9][1], "\\subsubsection{复现 E1--E3 与 E5}")
E9 = demote(B["E4old"], marks[3][1], "\\subsubsection{E9：路网结构指标能否预测影响集规模（探索性）}")

new = (
    "\\subsection{重调度范围}\n\\label{sec:exp_scope}\n\n"
    "本节检验两种划界给出的重调度范围：E1 检验走廊阻断下按工序依赖图划界是否为空，"
    "E2 检验预约影响集是否对依赖边封闭、修复后集外占用是否保持原计划。\n\n"
    + E1 + E2 +
    "\\subsection{调度方案的可行性}\n\\label{sec:exp_feas}\n\n"
    "本节比较修复后能否得到可继续执行的排程：E3 在同一回放程序下只更换划界对象，"
    "E4 把比较推广到四类扰动。\n\n"
    + E3 + E4 +
    "\\subsection{重调度速度与完工时间}\n\\label{sec:exp_speed}\n\n"
    "本节比较算法耗时与修复后的完工时间：E5 的对照是秒级的热启动全局重调度，"
    "E6 的对照是耗时同在毫秒量级的三种做法。\n\n"
    + E5 + E6 +
    "\\subsection{消融：划界与分层}\n\\label{sec:ablation}\n\n"
    + E7 + E8 +
    "\\subsection{外部布局：复现与结构指标}\n\\label{sec:pub}\n\n"
    + PUB + E9
)
src = src[:pos[0]] + new + src[end:]
open(P, "w", encoding="utf-8", newline="").write(src)
print("ok")
