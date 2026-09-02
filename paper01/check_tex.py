# -*- coding: utf-8 -*-
"""改稿期间的轻量自检:在没有 TeX 引擎的机器上先排掉最常见的三类编译错误。

检查项:
  1. 正文引用了但导言区没有定义的自定义宏(未定义命令是最常见的编译中断原因);
  2. 定义了却没有任何地方引用的宏(通常意味着某处数字被写死了,绕过了单一来源);
  3. 花括号净差与常用环境的 begin/end 配对。

用法:py paper01/check_tex.py [要检查的 tex 路径]
     不传路径时检查同目录的 paper.tex。
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# 改稿期间的施工稿是另一个文件(paper_AI-Modify-<日期>.tex),必须显式传入才会被检查;
# 原始稿永不被改,对它反复运行本脚本的输出恒定不变,等于没有体检。
TEX = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "paper.tex")

src = open(TEX, encoding="utf-8").read()

print("受检文件             : %s" % os.path.relpath(TEX))

defined = set(re.findall(r"\\newcommand\{\\([A-Za-z]+)\}", src))
# 只看首字母大写的驼峰宏,即本文为"数字单一来源"新增的那批;LaTeX 自带命令不在此列。
# 两种写法都要认:带空花括号的 \Gain{},以及数学模式里直接跟符号的 $p=\PLoop$。
used = collections.Counter(re.findall(r"\\([A-Z][A-Za-z]*)(?![A-Za-z])", src))

# 由宏包提供的大写开头命令,不是本文定义的,须排除,否则告警会被它们淹没。
KNOWN = {
    # algorithmicx / algpseudocode
    "Require", "Ensure", "State", "Statex", "If", "ElsIf", "Else", "EndIf",
    "For", "ForAll", "EndFor", "While", "EndWhile", "Repeat", "Until",
    "Function", "EndFunction", "Procedure", "EndProcedure", "Return",
    "Comment", "Call", "Loop", "EndLoop",
    # amsmath / 数学符号
    "Delta", "Omega", "Gamma", "Lambda", "Sigma", "Theta", "Phi", "Psi", "Pi",
    "Big", "Bigl", "Bigr", "Bigg", "Biggl", "Biggr", "Leftarrow",
    "Rightarrow", "Longrightarrow", "Leftrightarrow",
    # LaTeX / acmart
    "TeX", "LaTeX", "BibTeX", "AtBeginDocument", "Acknowledgements",
    "Description", "Roman", "Alph", "Huge", "Large", "LARGE",
}
defined |= KNOWN

print("导言区定义的自定义宏 : %d 个" % (len(defined) - len(KNOWN)))
print("正文引用的自定义宏   : %d 个 / 共 %d 处" % (len(used), sum(used.values())))

missing = sorted(u for u in used if u not in defined)
print("引用但未定义(会编译失败): %s" % (", ".join(missing) if missing else "无"))

unused = sorted(d for d in defined
                if d not in used and d != "TBD" and d not in KNOWN)
print("定义但未引用(检查是否有写死的数字): %s" % (", ".join(unused) if unused else "无"))

# 去掉注释行再数括号,否则中文注释里的全角括号与说明文字会干扰
body = "\n".join(re.sub(r"(?<!\\)%.*$", "", ln) for ln in src.splitlines())
print("花括号净差(应为 0)  : %d" % (body.count("{") - body.count("}")))

bad = []
for env in ("abstract", "table", "figure", "enumerate", "itemize",
            "tabular", "algorithm", "equation", "align", "comment"):
    a = len(re.findall(r"\\begin\{%s\*?\}" % env, body))
    b = len(re.findall(r"\\end\{%s\*?\}" % env, body))
    if a != b:
        bad.append("%s(begin %d / end %d)" % (env, a, b))
print("环境不配对           : %s" % (", ".join(bad) if bad else "无"))

# 未解决的占位符:投稿前必须清零
tbd = len(re.findall(r"\\TBD\{", body))
print("残留 \\TBD 占位符     : %d 处" % tbd)

# 交叉引用一致性。改稿期间搬动与删除小节最容易留下悬空的 \ref,它编译时只报 warning
# 并在正文里印出 "??",很容易漏过去,故在这里当成错误来报。
labels = set(re.findall(r"\\label\{([^}]+)\}", body))
refs = set()
for m in re.findall(r"\\(?:eq|auto|c)?ref\{([^}]+)\}", body):
    refs |= {r.strip() for r in m.split(",")}
dangling = sorted(refs - labels)
print("引用了不存在的 label : %s" % (", ".join(dangling) if dangling else "无"))
# 章级 label 供他处引用,未被引用是正常的;其余孤立 label 多是删了引用却忘了删图表。
orphan = sorted(l for l in labels - refs if not l.startswith("sec:Chapter"))
print("定义却无人引用的 label: %s" % (", ".join(orphan) if orphan else "无"))

# 待办清点:改稿期间刻意留下的标记,投稿前必须逐条清零
for tag, desc in (("TODO", "TODO 标记"), ("!! 待填", "待填数值"), ("待改", "待改段落")):
    n = len(re.findall(re.escape(tag), src))
    print("%-20s : %d 处" % (desc, n))
