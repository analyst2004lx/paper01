# -*- coding: utf-8 -*-
"""paper04_CN 自检脚本（{{CHECK}} 的替代品，标准库 only）

由 PaperRefinePrompt.md §7 末尾的规定生成：仓库内不存在 check_tex.py，
故 {{CHECK}} = NO_CHECKER，改用本脚本。

用法：
    py paper04/paper04_CN_selfcheck.py                     # 默认查施工稿，缺失则查原始稿
    py paper04/paper04_CN_selfcheck.py <tex 路径>
    py paper04/paper04_CN_selfcheck.py <tex 路径> --json   # 供逐轮告警差异对比

每轮应用修改后跑一次，与上一轮输出对比；出现新告警立即回滚该条。
"""
from __future__ import print_function

import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "paper04_CN-work.tex")
ORIG = os.path.join(HERE, "paper04_CN.tex")

# 卡片 §6 术语表：正文禁用词 -> 应改为
BANNED = {
    "工序图": "工序依赖图（CONFLICT-4：4 处从未定义的简称）",
    "时空预约影响闭包": "时空预约闭包（CONFLICT-1：删「影响」二字）",
    "影响闭包": "时空预约闭包（CONFLICT-1：关键词处）",
}
# CONFLICT-3：扩样前 15 对批次的旧读数。
# 只有 0.54 在 tab:e1 中不存在，是唯一可判定的残留标志；
# 0.57 / 0.58 本身是合法读数，不能单独作为证据，故只匹配成对出现的旧区间。
STALE = ["0.54"]
# 允许两数之间夹 LaTeX 数学定界符（如 \(0.54\)--\(0.58\)），否则会漏。
STALE_RANGE = [r"0\.54[^0-9]{1,12}0\.5[78]"]
PLACEHOLDERS = [r"\\TBD", r"TODO", r"待填", r"待改", r"XXXXXXX"]


def strip_comments(text):
    out = []
    for line in text.split("\n"):
        out.append(re.sub(r"(?<!\\)%.*$", "", line))
    return "\n".join(out)


def cjk_len(text):
    text = re.sub(r"\$[^$]*\$", "", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", "", text)
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def load(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def check(path):
    raw = load(path)
    body = strip_comments(raw)
    lines = raw.split("\n")
    warn = []

    def add(kind, msg, line=None):
        warn.append({"kind": kind, "msg": msg, "line": line})

    # ---- 1. 宏：定义但未引用（最灵敏的报警器）----
    # 宏体必须按花括号配平截取：定义行常带行尾注释（\newcommand{\X}{0.064}  % 说明），
    # 若直接取到行尾，宏体会把注释一起吞掉，写死的数字就检不出来。
    defs = {}
    for m in re.finditer(r"\\newcommand\{?\\([A-Za-z]+)\}?(?:\[\d+\])?\{", raw):
        i = m.end()
        depth, buf = 1, []
        while i < len(raw) and depth:
            ch = raw[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if not depth:
                    break
            buf.append(ch)
            i += 1
        defs[m.group(1)] = "".join(buf)
    for name in sorted(defs):
        uses = len(re.findall(r"\\" + name + r"(?![A-Za-z])", body))
        if uses <= 1:  # 1 = 定义处自身
            add("MACRO_UNUSED", "宏 \\%s 定义但正文 0 处引用（常见原因：被展开成写死的数字）" % name)

    # ---- 2. 写死的数字：与已定义数字宏的值相同 ----
    numeric = {}
    for name, val in defs.items():
        v = val.strip()
        if re.match(r"^-?\d+(\.\d+)?(\s*\\%|\s*\\,?(ms|s)|%)?$", v):
            key = re.match(r"^-?\d+(\.\d+)?", v).group(0)
            if len(key) >= 3:
                numeric.setdefault(key, []).append(name)
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("%") or "\\newcommand" in line:
            continue
        for key, owners in numeric.items():
            if re.search(r"(?<![\d.])" + re.escape(key) + r"(?![\d])", line):
                add("HARDCODED_NUM",
                    "%s 疑为写死的数字，已有宏 %s" % (key, "/".join("\\" + o for o in owners)), i)

    # ---- 3. 环境与花括号平衡 ----
    stack = []
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("%"):
            continue
        for m in re.finditer(r"\\(begin|end)\{([^}]+)\}", line):
            if m.group(1) == "begin":
                stack.append((m.group(2), i))
            else:
                if not stack:
                    add("ENV_UNBALANCED", "\\end{%s} 无对应 \\begin" % m.group(2), i)
                elif stack[-1][0] != m.group(2):
                    add("ENV_UNBALANCED",
                        "\\end{%s} 与未闭合的 \\begin{%s}(第 %d 行) 交叉"
                        % (m.group(2), stack[-1][0], stack[-1][1]), i)
                    stack.pop()
                else:
                    stack.pop()
    for name, i in stack:
        add("ENV_UNBALANCED", "\\begin{%s} 未闭合" % name, i)

    bal = body.count("{") - body.count("}")
    if bal:
        add("BRACE_UNBALANCED", "全文花括号不平衡，{ 比 } 多 %d" % bal)

    # ---- 4. \label / \ref ----
    labels = set(re.findall(r"\\label\{([^}]+)\}", body))
    refs = set()
    for pat in (r"\\ref\{([^}]+)\}", r"\\eqref\{([^}]+)\}",
                r"\\autoref\{([^}]+)\}", r"\\Cref\{([^}]+)\}",
                r"\\cref\{([^}]+)\}"):
        refs |= set(re.findall(pat, body))
    for r in sorted(refs - labels):
        add("REF_DANGLING", "\\ref{%s} 指向不存在的 label" % r)
    # 图表 label 未被引用是 P10 的实质问题；章节/定理锚点未被交叉引用是正常写法，
    # 单列为 INFO，避免淹没真告警。
    for l in sorted(labels - refs):
        if re.match(r"(tab|fig|alg):", l):
            add("FLOAT_UNREFERENCED", "\\label{%s} 浮动体从未被正文引用（P10）" % l)
        else:
            add("INFO_ANCHOR_UNREFERENCED", "\\label{%s} 仅作锚点，未被交叉引用" % l)

    # ---- 5. 引用键 ----
    keys = set()
    for m in re.finditer(r"\\cite[a-z]*\{([^}]+)\}", body):
        for k in m.group(1).split(","):
            keys.add(k.strip())
    bib = os.path.join(os.path.dirname(os.path.abspath(path)), "reference-base.bib")
    if os.path.exists(bib):
        bibkeys = set(re.findall(r"@\w+\{([^,]+),", load(bib)))
        for k in sorted(keys - bibkeys):
            add("CITE_MISSING", "\\cite{%s} 在 bib 中不存在" % k)

    # ---- 6. 占位符 ----
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("%"):
            continue
        for pat in PLACEHOLDERS:
            if re.search(pat, line):
                add("PLACEHOLDER", "占位符 %s" % pat.replace("\\\\", "\\"), i)

    # ---- 7. 术语禁用词（卡片 §6）----
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("%"):
            continue
        for bad, good in BANNED.items():
            if bad in line:
                # 「工序依赖图」含「工序图」? 不含，安全；「时空预约影响闭包」含「影响闭包」
                if bad == "影响闭包" and "时空预约影响闭包" in line:
                    continue
                add("TERM_BANNED", "禁用词「%s」→ 应为 %s" % (bad, good), i)

    # ---- 8. CONFLICT-3 旧读数残留 ----
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("%") or "\\newcommand" in line:
            continue
        for pat in STALE_RANGE:
            if re.search(pat, line):
                add("STALE_READING",
                    "旧区间 0.54–0.5x（CONFLICT-3：以 tab:e1 为准改为 0.56–0.59）", i)
        if re.search(r"Cl|\\lvert R\\rvert|闭包|影响集", line):
            for s in STALE:
                if re.search(r"(?<![\d.])" + re.escape(s) + r"(?![\d])", line):
                    add("STALE_READING",
                        "%s 在 tab:e1 中不存在，判为扩样前 15 对批次残留（CONFLICT-3）" % s, i)

    # ---- 9. 字数与占比 ----
    stats = {}
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", body, re.S)
    if m:
        n = cjk_len(m.group(1))
        stats["abstract_cjk"] = n
        if not (400 <= n <= 700):
            add("ABS_LEN", "摘要 %d 汉字，超出 §5.11 区间 400–700" % n)

    bs = body.find("\\begin{document}")
    total = cjk_len(body[bs:]) if bs >= 0 else cjk_len(body)
    stats["body_cjk"] = total

    heads = [(i, k, t) for i, k, t in
             ((i, m2.group(1), m2.group(2))
              for i, ln in enumerate(lines, 1)
              for m2 in [re.match(r"\s*\\(section|subsection)\*?\{(.*)\}\s*$", ln)]
              if m2)]
    spans = {}
    for idx, (i, kind, title) in enumerate(heads):
        end = heads[idx + 1][0] - 1 if idx + 1 < len(heads) else len(lines)
        spans[title] = cjk_len("\n".join(lines[i - 1:end]))
    stats["sections"] = spans

    if total:
        lim = spans.get("局限")
        if lim and lim > 0.05 * total:
            add("LIMIT_LEN", "局限 %d 字 = 全文 %.1f%%，超硬约束 5%%（≈%d 字）"
                % (lim, 100.0 * lim / total, int(0.05 * total)))

    return warn, stats


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    path = args[0] if args else (WORK if os.path.exists(WORK) else ORIG)
    if not os.path.exists(path):
        print("找不到文件：%s" % path)
        return 2

    warn, stats = check(path)
    if as_json:
        print(json.dumps({"file": os.path.basename(path),
                          "stats": stats,
                          "warnings": warn},
                         ensure_ascii=False, indent=1))
        return 0

    buf = []
    buf.append("自检对象：%s" % path)
    buf.append("正文汉字 %d｜摘要汉字 %s"
               % (stats.get("body_cjk", 0), stats.get("abstract_cjk", "n/a")))
    buf.append("")
    order = ["ENV_UNBALANCED", "BRACE_UNBALANCED", "REF_DANGLING", "CITE_MISSING",
             "MACRO_UNUSED", "HARDCODED_NUM", "PLACEHOLDER", "TERM_BANNED",
             "STALE_READING", "FLOAT_UNREFERENCED", "ABS_LEN", "LIMIT_LEN",
             "INFO_ANCHOR_UNREFERENCED"]
    groups = {}
    for w in warn:
        groups.setdefault(w["kind"], []).append(w)
    for kind in order:
        items = groups.get(kind)
        if not items:
            continue
        buf.append("== %s（%d）" % (kind, len(items)))
        for w in items:
            loc = ("第 %d 行" % w["line"]) if w["line"] else "-"
            buf.append("   %-10s %s" % (loc, w["msg"]))
        buf.append("")
    for kind in sorted(set(groups) - set(order)):
        buf.append("== %s（%d）" % (kind, len(groups[kind])))
        for w in groups[kind]:
            loc = ("第 %d 行" % w["line"]) if w["line"] else "-"
            buf.append("   %-10s %s" % (loc, w["msg"]))
        buf.append("")
    info = len([w for w in warn if w["kind"].startswith("INFO_")])
    buf.append("告警合计 %d 条（另有 %d 条 INFO 不计入）" % (len(warn) - info, info))

    text = "\n".join(buf)
    out = os.path.splitext(path)[0] + "_selfcheck.txt"
    with io.open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    try:
        print(text)
    except UnicodeEncodeError:
        print("（控制台编码不支持，已写入 %s）" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
