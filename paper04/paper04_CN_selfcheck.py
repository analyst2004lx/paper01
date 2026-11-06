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

# 卡片 §6 术语表「禁止的近义说法」整栏 + 台账 §6.2／§6.3 的旧词与修辞禁语。
# 2026-09-21 扩充：原先只有下面前三条，覆盖面远小于卡片，B13 报的「TERM_BANNED 清零」
# 因此只说明那三个词清零，不等于卡片 §6 全表合规——「释放集」「收录」「时空预约图」
# 三类漂移就是在这个缺口里长期存活的。
BANNED = {
    # --- 卡片 §6 CONFLICT-1／CONFLICT-4（原有三条）---
    "工序图": "工序依赖图（CONFLICT-4：从未定义的简称）",
    "时空预约影响闭包": "时空预约闭包（CONFLICT-1：删「影响」二字）",
    "影响闭包": "时空预约闭包（CONFLICT-1：关键词处）",
    # --- 卡片 §6 行 161–163：两张依赖图 ---
    "任务图": "工序依赖图（唯一用名）",
    "任务依赖图": "工序依赖图（唯一用名）",
    "时空预约图": "预约依赖图 \\(G_R\\)（卡片 §6 行 162）",
    # --- 卡片 §6 行 163–164：占用与允许改写的集合 ---
    "时空占用": "走廊占用 / 预约记录 \\(r\\)",
    "释放集": "允许改写的占用集合 \\(U\\)（宏区旧名）",
    "释放域": "允许改写的占用集合 \\(U\\)",
    "解冻集": "允许改写的占用集合 \\(U\\)",
    "可改集": "允许改写的占用集合 \\(U\\)",
    # --- 卡片 §6 行 165：起点占用 ---
    "源头占用": "作为起点的占用 \\(\\mathrm{Seeds}\\)",
    # --- 卡片 §6 行 166：两侧的集合名不得互串 ---
    "受影响集合": "预约影响集（本文侧）或工序依赖图上的影响域（工序侧），不得用中性说法混指",
    "影响范围": "预约影响集 / 允许改写的占用集合，视所指而定",
    # --- 卡片 §6 行 167：扰动分类 ---
    "工序型扰动": "A 类",
    "走廊型扰动": "B 类",
    # --- 卡片 §6 行 168：恢复流程 ---
    "有界恢复": "有界修复（唯一用名）",
    "扩域": "扩大允许改写的范围（宏区旧名）",
    "局部修复": "有界修复（唯一用名）",
    # --- 卡片 §6 行 169：对照臂不得用中文别名作正式称呼 ---
    "右移法": "RS（中文说法只能作注解）",
    "重解码法": "RD（中文说法只能作注解）",
    # --- 卡片 §6 行 170：决策时刻 ---
    "当前时刻": "决策时刻 \\(t_{\\mathrm{now}}\\)",
    "响应时刻": "决策时刻 \\(t_{\\mathrm{now}}\\)",
    # --- 卡片 §6 行 171：尚未结束的占用 ---
    "活预约": "尚未结束的占用 \\(R^{\\circ}\\)（宏区旧名）",
    "未来占用": "尚未结束的占用 \\(R^{\\circ}\\)",
    # --- 台账 §6.2 的旧词（卡片未收，09-15 风格轮定下）---
    "收录": "纳入重调度范围（台账 §6.2.1）",
    "命中": "无法按原计划执行 / 占用时段与阻断窗重叠",
    "机器链": "同一台机器上排在其后的工序",
    "路段降速": "走廊通行变慢",
    "对照臂": "先写划界或搜索对象，编号留给实验表",
    "热启动全局重解": "以原排程为起点、在限定时间内重新搜索的全局重调度",
    "显式预约模型": "用时间窗记录走廊占用",
    "无冲突执行器": "同一套走廊路网、时间窗路由与无冲突校验",
    "中位耗时": "耗时中位数",
    # --- 台账 §6.3 的修辞禁语 ---
    "挂靠点": "直述做了什么（台账 §6.3）",
    "兑现": "直述做了什么（台账 §6.3）",
    "制导": "引导搜索以更换指派或路径",
    "关键链稀释": "写开瓶颈转移的机制（台账 §6.3）",
    "一击反例": "问题层面上的反例",
    "系统性漏报": "按该方法会得到空范围",
    "本文只做测量": "本文用既定先后划定须改写的占用",
}

# 单用即违例，但有合法复合词，必须先遮蔽后再查（否则逐行必然误报）。
# 形如 {被查的词: [先遮蔽掉的合法复合词, ...]}
BANNED_SOLO = {
    "闭包": (["时空预约闭包", "传递闭包"],
             "时空预约闭包（正式名）或预约影响集（通俗名）；「闭包」不得单用"),
    "种子": (["随机种子", "生成随机种子", "运行随机种子"],
             "随机种子（实验）或作为起点的占用 \\(\\mathrm{Seeds}\\)；"
             "「种子」单用与 \\(\\mathrm{Seeds}\\) 冲突，卡片 §6 行 172 严禁"),
}

# 卡片 §6 有四条禁语**故意不进脚本**，因为纯文本判不了所指，灌进来只会产生误报，
# 而误报一多就会让 TERM_BANNED 这个信号重新失效（这正是本次扩充要修的毛病）：
#   * 「预约」单用（行 163）——本文里它当动词用得比当名词多（「以时间窗预约走廊」
#     「本文预约的是边」「van Os 预约节点」），且合法复合词是开放集（预约子集、
#     预约依赖边、预约设定、预约时窗……）。实测 10 处命中有 8 处是动词或未列复合词。
#   * 「影响集」（行 166）——禁的是拿它称工序侧的 \(T_{\mathrm{impact}}\)，
#     而称预约侧时它是卡片行 160 认可的通俗名，脚本分不出所指。
#   * 「影响域」（行 160 禁 / 行 166 用）——同一个词在两行里一禁一用，只能靠人读。
#   * 对照臂的中文别名（行 169）——禁的是拿它作**正式称呼**，作注解合法（RS 全局右移）；
#     已收「右移法」「重解码法」这类明显当正式名用的造词，其余靠人读。
# 结论：术语纪律的这四项只能在通读时执行，不能指望自检。

# 就地豁免：标记写在违例行本身，或紧邻的上一整行注释里（后者不动版式，优先用）。
# 与 selfcheck:allow-num 同理，理由必须与标记写在一起。
ALLOW_TERM = "selfcheck:allow-term"
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
    # 两类豁免，否则本项信噪比为 0：
    #  (a) tabular/array 表体——协议规定表是数据源，宏由表出数，表体本就该写字面值；
    #      只豁免 tabular 而非 table，故 caption 与 \Description 仍在检查范围内。
    #  (b) 长度与版式参数（leftmargin=1.5em、width=0.92\linewidth），与读数无关。
    #  (c) 行尾标记 % selfcheck:allow-num——「同值不同源」的撞值。宏与字面量数值相同
    #      但是两个不同的量（如 R2 改动比例的四分位距恰等于剔除恒等格后的平均降幅），
    #      此时套宏会制造错误的溯源。标记须与撞值理由写在同一行，且计入下面的 INFO。
    ALLOW = "selfcheck:allow-num"
    TAB_ENVS = ("tabular", "tabularx", "longtable", "array")
    UNITS = r"(?:em|ex|pt|bp|sp|cm|mm|in|%|\\linewidth|\\textwidth|\\columnwidth|\\baselineskip|\\height|\\width)"
    depth = 0
    skipped = 0
    allowed = 0
    for i, line in enumerate(lines, 1):
        for env in TAB_ENVS:
            depth += len(re.findall(r"\\begin\{" + env + r"\*?\}", line))
            depth -= len(re.findall(r"\\end\{" + env + r"\*?\}", line))
        if line.strip().startswith("%") or "\\newcommand" in line:
            continue
        for key, owners in numeric.items():
            m = re.search(r"(?<![\d.])" + re.escape(key) + r"(?![\d])", line)
            if not m:
                continue
            tail = line[m.end():]
            head = line[:m.start()]
            if depth > 0 or re.match(r"\s*" + UNITS, tail) or re.search(r"=\s*$", head):
                skipped += 1
                continue
            if ALLOW in line:
                allowed += 1
                continue
            add("HARDCODED_NUM",
                "%s 疑为写死的数字，已有宏 %s" % (key, "/".join("\\" + o for o in owners)), i)
    if skipped:
        add("INFO_NUM_IN_TABLE",
            "另有 %d 处同值数字落在表体或长度参数中，按协议豁免（表为数据源）；"
            "若某读数确实只存在于表体而正文需引用，应加宏而非改表" % skipped)
    if allowed:
        add("INFO_NUM_IN_TABLE",
            "另有 %d 处由行尾 %s 就地豁免，属「同值不同源」撞值；"
            "复核时应逐条确认该行注明的撞值理由仍成立" % (allowed, ALLOW))

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

    # ---- 7. 术语禁用词（卡片 §6 全表 + 台账 §6.2／§6.3）----
    # 三点与旧版不同：
    #  (a) 剥行尾注释，不只跳过整行注释。宏区旧名（\newcommand{...}{...}  % 闭包/...）
    #      按卡片行 164 的既有处置属豁免范围，旧版会把它们全报出来。
    #  (b) 长词优先：命中「时空预约影响闭包」后不再就同一处报「影响闭包」。
    #  (c) 支持 selfcheck:allow-term 就地豁免，标记可写在本行或紧邻的上一整行注释。
    allow_lines = set()
    for i, line in enumerate(lines, 1):
        if ALLOW_TERM in line:
            allow_lines.add(i)
            if line.strip().startswith("%"):
                allow_lines.add(i + 1)
    term_allowed = 0
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("%"):
            continue
        text = re.sub(r"(?<!\\)%.*$", "", line)
        if not text.strip():
            continue
        hits = []
        for bad, good in BANNED.items():
            if bad in text:
                hits.append((bad, good))
        for bad, (masks, good) in BANNED_SOLO.items():
            probe = text
            for mk in sorted(masks, key=len, reverse=True):
                probe = probe.replace(mk, "\u25a1" * len(mk))
            if bad in probe:
                hits.append((bad, good))
        # 长词优先：若某命中是另一命中的子串，只报长的那个
        hits = [(b, g) for b, g in hits
                if not any(b != b2 and b in b2 for b2, _ in hits)]
        if not hits:
            continue
        if i in allow_lines:
            term_allowed += len(hits)
            continue
        for bad, good in hits:
            add("TERM_BANNED", "禁用词「%s」→ 应为 %s" % (bad, good), i)
    if term_allowed:
        add("INFO_TERM_ALLOWED",
            "另有 %d 处由 %s 就地豁免（转述文献用语或经裁决保留的同义登记）；"
            "复核时应逐条确认标记行注明的理由仍成立" % (term_allowed, ALLOW_TERM))

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
             "INFO_ANCHOR_UNREFERENCED", "INFO_NUM_IN_TABLE", "INFO_TERM_ALLOWED"]
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
