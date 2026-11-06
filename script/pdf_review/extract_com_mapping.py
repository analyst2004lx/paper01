"""
extract_com_mapping.py —— 把批注清单（extract_comments.py 生成的 .md）映射到 LaTeX 源码位置，输出 .json

功能
----
读取批注清单 .md 与 LaTeX 源文件（自动跟随 \\input / \\include 的子文件），对每条批注的被批注文字
（text，以及 more_targets 中的各段）在 tex 中定位，输出 JSON 列表。每条包含：
  id, page, line, line_src, col, len, text, context, comment, kind, author   —— 来自 .md
  tex_file      匹配到的 tex 文件（相对主 tex 目录）
  tex_line      起始行号（1 起）
  tex_col       起始列（1 起，按该行原始字符计数，含 LaTeX 命令）
  tex_end_line / tex_end_col   结束位置（含）
  tex_text      tex 中对应的原始片段
  match         匹配质量：exact（全文唯一精确匹配）/ context（借助所在整行消歧）/
                partial（仅部分片段匹配，位置为推算）/ none（未找到）
  more_targets  其余被批注片段，各自带上述 tex_* 字段
  .md 条目中的其它字段（如 Answer、Modify、Status）原样带入 JSON。

匹配方法：两侧都做规范化（NFKC，去空白、去 LaTeX 命令/花括号/数学符号、去 \\cite \\ref 等、
去 PDF 中的 [12] 式引用号），在规范化串上查找，再映射回 tex 原始行列。
PDF 编译后又改过 tex 的地方会落到 partial/none，需人工确认。

用法
----
  python extract_com_mapping.py <批注清单.md> <main.tex> [更多.tex ...] [-o 输出.json]
  python extract_com_mapping.py <批注清单.md> --sync-only [-o 输出.json]

  默认输出与 .md 同名的 .json。
  --sync-only：不重新映射 tex，只把 .md 里新增/修改的非定位字段（Answer、Modify、Status、comment 等）
               同步进已有 JSON。用于 tex 已被修改、但想保留原映射结果的情况。

让模型（Cursor Agent）使用
-------------------------
  对模型说：「用 script/pdf_review/extract_com_mapping.py 把 xxx_comments.md 映射到 main.tex」。
  模型运行后应报告 match 分布，并抽查 partial/none 条目，必要时在 .md 中修正 text 后重跑。
  在 extract_com_AnswerAndModify.md 流程里写回 Answer/Modify 到 .md 后，用 --sync-only 同步 JSON。
"""
import argparse
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

LOCATE_KEYS = {"page", "line", "line_src", "col", "len", "text", "context"}
TEX_KEYS = ("tex_file", "tex_line", "tex_col", "tex_end_line", "tex_end_col", "tex_text", "match")

DROP_ARG_CMDS = {"cite", "citep", "citet", "citeauthor", "citeyear", "ref", "eqref", "autoref", "cref", "Cref",
                 "pageref", "label", "includegraphics", "hspace", "vspace", "input", "include", "bibliography",
                 "bibliographystyle", "usepackage", "documentclass", "begin", "end", "setlength", "url", "href"}
SYMBOLS = {"alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε",
           "theta": "θ", "lambda": "λ", "mu": "μ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ",
           "phi": "φ", "varphi": "φ", "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ",
           "Lambda": "Λ", "Sigma": "Σ", "Phi": "Φ", "Omega": "Ω", "Pi": "Π", "le": "≤", "leq": "≤",
           "ge": "≥", "geq": "≥", "neq": "≠", "ne": "≠", "in": "∈", "notin": "∉", "times": "×",
           "infty": "∞", "cdot": "·", "ldots": "…", "dots": "…", "cdots": "⋯", "to": "→",
           "rightarrow": "→", "leftarrow": "←", "subseteq": "⊆", "subset": "⊂", "cup": "∪", "cap": "∩",
           "sum": "∑", "prod": "∏", "forall": "∀", "exists": "∃", "pm": "±", "approx": "≈"}
QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def norm_char(c):
    return unicodedata.normalize("NFKC", c).translate(QUOTES)


def norm_pdf(s):
    s = re.sub(r"\[\d+(?:\s*[,–-]\s*\d+)*\]", "", s or "")
    return "".join(norm_char(c) for c in s if not c.isspace() and c not in "~$")


# ---------------------------------------------------------------- tex index
def resolve_inputs(main):
    """main + \\input/\\include children, in reading order, without duplicates."""
    order, seen = [], set()

    def visit(p):
        p = p.resolve()
        if p in seen or not p.exists():
            return
        seen.add(p)
        order.append(p)
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = re.sub(r"(?<!\\)%.*", "", line)
            for m in re.finditer(r"\\(?:input|include|subfile)\{([^}]+)\}", line):
                child = (main.parent / m.group(1))
                if child.suffix != ".tex":
                    child = child.with_suffix(".tex")
                visit(child)

    visit(main)
    return order


def skip_group(line, i, open_c="{", close_c="}"):
    depth = 0
    while i < len(line):
        if line[i] == "\\":
            i += 2
            continue
        if line[i] == open_c:
            depth += 1
        elif line[i] == close_c:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return i


def norm_tex_line(line):
    """Normalised chars of one raw tex line, each with its 0-based column."""
    out = []
    m = re.search(r"(?<!\\)%", line)
    end = m.start() if m else len(line)
    i = 0
    while i < end:
        c = line[i]
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+)\*?", line[i:])
            if m:
                name, j = m.group(1), i + m.end()
                if name in SYMBOLS:
                    out.append((SYMBOLS[name], i))
                if j < end and line[j] == "[":
                    j = skip_group(line, j, "[", "]")
                if name in DROP_ARG_CMDS:
                    while j < end and line[j] == " ":
                        j += 1
                    if j < end and line[j] == "{":
                        j = skip_group(line, j)
                i = j
                continue
            if i + 1 < end and line[i + 1] in "%&_#{}$":
                out.append((line[i + 1], i))
            i += 2
            continue
        if line.startswith("---", i):
            out.append(("—", i)); i += 3; continue
        if line.startswith("--", i):
            out.append(("–", i)); i += 2; continue
        if line.startswith("``", i) or line.startswith("''", i):
            out.append(('"', i)); i += 2; continue
        if c == "`":
            out.append(("'", i)); i += 1; continue
        if c.isspace() or c in "{}$~&^_":
            i += 1
            continue
        for nc in norm_char(c):
            out.append((nc, i))
        i += 1
    return out


class TexIndex:
    def __init__(self, files, root):
        self.raw = {}
        self.headings = {}
        chars, where = [], []
        for f in files:
            rel = str(f.relative_to(root)) if f.is_relative_to(root) else str(f)
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            self.raw[rel] = lines
            for ln, line in enumerate(lines, 1):
                h = re.match(r"\s*\\(?:part|chapter|(?:sub){0,2}section|paragraph)\*?(?:\[[^\]]*\])?\{(.*)\}", line)
                if h:
                    key = "".join(ch for ch, _ in norm_tex_line(h.group(1)))
                    self.headings.setdefault(key, []).append(len(chars))
                for ch, col in norm_tex_line(line):
                    chars.append(ch)
                    where.append((rel, ln, col))
        self.s = "".join(chars)
        self.where = where

    def unique(self, t, lo=0, hi=None):
        hi = len(self.s) if hi is None else hi
        i = self.s.find(t, lo, hi)
        if i < 0 or self.s.find(t, i + 1, hi) >= 0:
            return None
        return i

    def chunk_locate(self, t, lo=0, hi=None):
        """Estimate start of t via its first uniquely-matching chunk."""
        for size in (len(t), 24, 16, 10, 6):
            if size > len(t) or size < 4:
                continue
            step = max(1, size // 2)
            for k in range(0, len(t) - size + 1, step):
                i = self.unique(t[k:k + size], lo, hi)
                if i is not None:
                    return max(0, i - k)
        return None

    def align(self, t, lo, hi):
        """Align t against s[lo:hi]; return (start, length) of the aligned tex region or None."""
        lo, hi = max(0, lo), min(len(self.s), hi)
        sm = difflib.SequenceMatcher(None, t, self.s[lo:hi], autojunk=False)
        blocks = [b for b in sm.get_matching_blocks() if b.size >= 2]
        if not blocks or sum(b.size for b in blocks) < 0.5 * len(t):
            return None
        start, end = lo + blocks[0].b, lo + blocks[-1].b + blocks[-1].size
        return start, end - start

    def span(self, start, n):
        end = min(len(self.s) - 1, start + max(n, 1) - 1)
        f1, l1, c1 = self.where[start]
        f2, l2, c2 = self.where[end]
        if f1 != f2:
            f2, l2, c2 = f1, l1, len(self.raw[f1][l1 - 1]) - 1
        if l1 == l2:
            text = self.raw[f1][l1 - 1][c1:c2 + 1]
        else:
            seg = self.raw[f1][l1 - 1:l2]
            seg[0], seg[-1] = seg[0][c1:], seg[-1][:c2 + 1]
            text = "\n".join(seg)
        return dict(tex_file=f1, tex_line=l1, tex_col=c1 + 1, tex_end_line=l2, tex_end_col=c2 + 1, tex_text=text)

    def locate(self, text, context, col):
        if re.fullmatch(r"（[^）]*）", text or ""):
            text = ""
            context = re.sub(r"^(图题|最近正文行)：", "", context or "")
        num = re.match(r"^\s*(?:\d+(?:\.\d+)*|\([ivx]+\)|[A-Z](?:\.\d+)+)\s*(?=[^\d.\s])", context or "")
        if num:
            context = context[num.end():]
            col = max(1, int(col) - num.end())
            text = re.sub(r"^\s*(?:\d+(?:\.\d+)*|\([ivx]+\)|[A-Z](?:\.\d+)+)\s*(?=[^\d.\s])", "", text or "")
        t, c = norm_pdf(text), norm_pdf(context)
        if not t and not c:
            return dict(match="none")
        if c in self.headings and len(self.headings[c]) == 1 and (not t or t == c):
            return dict(self.span(self.headings[c][0], len(c)), match="exact")
        if len(t) >= 8:
            i = self.unique(t)
            if i is not None:
                return dict(self.span(i, len(t)), match="exact")
        if c:
            ci = self.unique(c)
            if ci is None:
                ci = self.chunk_locate(c)
            if ci is not None:
                al = self.align(c, ci - 30, ci + len(c) + 30)
                if al and self.s.find(c, ci, ci + len(c)) != ci:
                    ci = al[0]
                lo, hi = max(0, ci - 30), min(len(self.s), ci + len(c) + 30)
                if not t:
                    expect = ci + len(norm_pdf(context[:max(0, int(col) - 1)]))
                    return dict(self.span(min(expect, len(self.s) - 1), 1), match="context")
                expect = ci + len(norm_pdf(context[:max(0, int(col) - 1)]))
                hits, j = [], self.s.find(t, lo, hi)
                while j >= 0:
                    hits.append(j)
                    j = self.s.find(t, j + 1, hi)
                if hits:
                    best = min(hits, key=lambda h: abs(h - expect))
                    return dict(self.span(best, len(t)), match="context")
                if len(t) >= 4:
                    al = self.align(t, expect - 10, expect + len(t) + 30)
                    if al:
                        return dict(self.span(*al), match="partial")
        if t:
            i = self.chunk_locate(t)
            if i is not None:
                al = self.align(t, i - 30, i + len(t) + 60)
                return dict(self.span(*(al or (i, len(t)))), match="partial")
        return dict(match="none")


# ---------------------------------------------------------------- md parsing
def parse_md(path):
    entries, cur, key = [], None, None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+(C\d+)\s*$", raw)
        if m:
            cur = {"id": m.group(1)}
            entries.append(cur)
            key = None
            continue
        if cur is None:
            continue
        m = re.match(r"^- ([A-Za-z_][\w]*):\s?(.*)$", raw)
        if m:
            key = m.group(1)
            cur[key] = m.group(2)
            continue
        if key and (raw.startswith("  ") or raw.startswith("\t")):
            cur[key] = (cur[key] + "\n" if cur[key] else "") + raw[2:]
        elif key and not raw.strip():
            cur[key] += "\n"
    for e in entries:
        for k in list(e):
            if isinstance(e[k], str):
                e[k] = e[k].rstrip("\n")
        e["more_targets"] = parse_targets(e.get("more_targets", ""))
        for k in ("page", "col", "len"):
            if str(e.get(k, "")).isdigit():
                e[k] = int(e[k])
    return entries


def parse_targets(block):
    out = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        t = {}
        for part in line[2:].split(" | "):
            if "=" in part:
                k, v = part.split("=", 1)
                t[k.strip()] = int(v) if v.strip().isdigit() and k.strip() in ("page", "col", "len") else v
        out.append(t)
    return out


# ---------------------------------------------------------------- main
def map_entries(entries, idx):
    for e in entries:
        e.update(idx.locate(e.get("text", ""), e.get("context", ""), e.get("col", 1) or 1))
        for t in e["more_targets"]:
            t.update(idx.locate(t.get("text", ""), t.get("context", ""), t.get("col", 1) or 1))
    return entries


def ordered(e):
    head = ["id", "page", "line", "line_src", "col", "len", "kind", "author", "text", "context", "comment"]
    keys = head + [k for k in TEX_KEYS] + ["more_targets"]
    out = {k: e[k] for k in keys if k in e}
    out.update({k: v for k, v in e.items() if k not in out})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("md")
    ap.add_argument("tex", nargs="*")
    ap.add_argument("-o", "--out")
    ap.add_argument("--sync-only", action="store_true")
    a = ap.parse_args()
    out = Path(a.out or Path(a.md).with_suffix(".json"))
    entries = parse_md(a.md)

    if a.sync_only:
        if not out.exists():
            sys.exit(f"{out} 不存在，请先不带 --sync-only 运行一次")
        old = {e["id"]: e for e in json.loads(out.read_text(encoding="utf-8"))}
        for e in entries:
            base = old.get(e["id"], {})
            for k, v in e.items():
                if k not in LOCATE_KEYS and k != "more_targets":
                    base[k] = v
            old[e["id"]] = base
        merged = [ordered(old[e["id"]]) for e in entries]
        out.write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"synced {len(merged)} entries -> {out}")
        return

    if not a.tex:
        sys.exit("需要至少一个 tex 文件")
    main_tex = Path(a.tex[0]).resolve()
    files = []
    for t in a.tex:
        for f in resolve_inputs(Path(t)):
            if f not in files:
                files.append(f)
    idx = TexIndex(files, main_tex.parent)
    entries = [ordered(e) for e in map_entries(entries, idx)]
    out.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    stat = {}
    for e in entries:
        stat[e["match"]] = stat.get(e["match"], 0) + 1
    print(f"wrote {out}: {len(entries)} entries, tex files={len(files)}, match={stat}")


if __name__ == "__main__":
    main()
