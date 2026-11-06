"""
extract_comments.py —— 从带审阅批注的 PDF 中提取「被批注文字 + 评语」，输出 Markdown 清单

功能
----
读取别人在 PDF 里添加的所有批注（便签 Text、高亮 Highlight、下划线 Underline、删除线 StrikeOut、
波浪线 Squiggly、文本框 FreeText、插入符 Caret、方框/圆圈/手绘 Square/Circle/Ink/Polygon 等），
逐条输出到 .md 文件。每条包含：
  - 编号 C001, C002 ...（按页码、页内从上到下的顺序递增）
  - page      被批注的页码（从 1 开始）
  - line      被批注的行：草稿带 lineno 行号时用 PDF 上印的行号；没有则用「本页第几行」（line_src 注明来源）
              跨行选中时写成 "35-36"
  - col       被选中文字在起始行中的起始列（1 起，按该行正文字符计数，不含页边行号）
  - len       被选中的字符个数
  - text      被选中的原文
  - context   被选中文字所在整行（或多行）的原文，供后续映射到 tex 时消歧
  - comment   评语；只高亮/划线而未写评语时为 none
  - kind      批注类型；author 批注人
  - more_targets  一条评语关联多个高亮时，其余高亮列在这里（格式同上，用 | 分隔）

便签（Text）与高亮在 PDF 内部没有显式关联。本脚本按审阅人「先高亮、后贴便签」的习惯启发式配对：
高亮创建于上一条便签之后、本便签之前，间隔不超过 --gap 分钟，且与便签图标距离不超过 --near 点。
配不上高亮的便签，以图标所在的整行作为被批注文字。配对可能出错，可直接在 .md 中手工调整，
后续脚本以 .md 为准。

已知局限：页边行号若是固定间距的「标尺」（如 acmart review 模式），与正文行距不一致，行号可能有 ±1 偏差；
双栏排版时「本页第几行」会把左右两栏的同一高度合并为一行；扫描版 PDF 无文字层无法提取。

用法
----
  pip install pymupdf
  python extract_comments.py <带批注的.pdf> [-o 输出.md] [--near 45] [--gap 10] [--no-pair]

  默认输出 <pdf名>_comments.md（与 PDF 同目录）。

让模型（Cursor Agent）使用
-------------------------
  对模型说：「用 script/pdf_review/extract_comments.py 提取 xxx.pdf 的批注」。
  模型应运行上面的命令，然后抽查若干条（尤其是 kind 含 "Text+" 的配对条目）是否合理，
  再继续用 extract_com_mapping.py 映射到 tex，用 extract_com_AnswerAndModify.md 逐条回答/给修改方案。
"""
import argparse
import datetime
import re
import statistics
from pathlib import Path

import fitz

MARKUP = {"Highlight", "Underline", "StrikeOut", "Squiggly"}
AREA = {"Square", "Circle", "Ink", "Polygon", "PolyLine", "Line"}
POINT = {"Text", "FreeText", "Caret", "Stamp", "FileAttachment"}


def pdf_minutes(s):
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})", s or "")
    if not m:
        return None
    return datetime.datetime(*map(int, m.groups())).timestamp() / 60


def clean(s):
    return (s or "").replace("\r\n", "\n").replace("\r", "\n").strip().replace("\n", " / ")


def pipe_safe(s):
    return s.replace("|", "｜")


class Page:
    """Body text of one page organised into visual rows, with lineno detection."""

    def __init__(self, page):
        self.page = page
        chars = []
        for b in page.get_text("rawdict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    for c in s["chars"]:
                        r = fitz.Rect(c["bbox"])
                        if r.height > 0:
                            chars.append([r, c["c"]])
        self.linenos = self._detect_linenos(page, chars)
        num_boxes = [t[3] for t in self.linenos]
        body = [c for c in chars if not any(b.contains(self._center(c[0])) for b in num_boxes)]
        self.rows = self._build_rows(body)
        self._assign_lines()
        self.figures = self._detect_figures(page)
        for row in self.rows:
            c = fitz.Point((row["chars"][0][0].x0 + row["chars"][-1][0].x1) / 2, row["yc"])
            row["fig"] = any(f.contains(c) for f in self.figures)
        self.pos = {}
        for ri, row in enumerate(self.rows):
            for ci, ch in enumerate(row["chars"]):
                self.pos[id(ch)] = (ri, ci)

    @staticmethod
    def _center(r):
        return fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)

    @staticmethod
    def _detect_linenos(page, chars):
        w = page.rect.width
        cands = []
        for x0, y0, x1, y1, word, *_ in page.get_text("words"):
            if word.isdigit() and (x1 < w * 0.2 or x0 > w * 0.8):
                cands.append(((y0 + y1) / 2, int(word), round(x1), fitz.Rect(x0, y0, x1, y1)))
        if len(cands) < 5:
            return []
        xs = [c[2] for c in cands]
        col = max(set(xs), key=xs.count)
        core = [c[3] for c in cands if abs(c[2] - col) <= 2]
        lo, hi = min(r.x0 for r in core) - 2, max(r.x1 for r in core) + 2
        nums = sorted((c for c in cands if c[3].x0 >= lo and c[3].x1 <= hi), key=lambda c: c[0])
        if len(nums) < 5:
            return []
        inc = sum(1 for a, b in zip(nums, nums[1:]) if b[1] == a[1] + 1)
        return nums if inc >= 0.6 * (len(nums) - 1) else []

    @staticmethod
    def _build_rows(chars):
        rows = []
        for ch in sorted(chars, key=lambda c: (c[0].y0 + c[0].y1) / 2):
            r = ch[0]
            best = None
            for row in rows[-4:]:
                ov = min(r.y1, row["y1"]) - max(r.y0, row["y0"])
                if ov > 0.5 * min(r.height, row["y1"] - row["y0"]):
                    best = row
            if best is None:
                best = {"y0": r.y0, "y1": r.y1, "chars": [], "core": r.height}
                rows.append(best)
            best["chars"].append(ch)
            if r.height >= best["core"] * 0.8:
                best["y0"], best["y1"] = min(best["y0"], r.y0), max(best["y1"], r.y1)
        for row in rows:
            row["chars"].sort(key=lambda c: c[0].x0)
            while row["chars"] and not row["chars"][0][1].strip():
                row["chars"].pop(0)
            while row["chars"] and not row["chars"][-1][1].strip():
                row["chars"].pop()
            row["text"] = "".join(c[1] for c in row["chars"])
            row["yc"] = (row["y0"] + row["y1"]) / 2
        rows = [r for r in rows if r["chars"]]
        rows.sort(key=lambda r: r["yc"])
        return rows

    def _assign_lines(self):
        for i, row in enumerate(self.rows, 1):
            row["page_row"] = i
            row["lineno"] = None
        if not self.linenos:
            return
        ys = [n[0] for n in self.linenos]
        spacing = statistics.median(b - a for a, b in zip(ys, ys[1:])) if len(ys) > 1 else 12
        for row in self.rows:
            n = min(self.linenos, key=lambda t: abs(row["yc"] - t[0]))
            if abs(row["yc"] - n[0]) <= spacing * 0.6:
                row["lineno"] = n[1]

    def row_label(self, ri):
        row = self.rows[ri]
        return (row["lineno"], "lineno") if row["lineno"] is not None else (row["page_row"], "page_row")

    def _detect_figures(self, page):
        """Vector-drawing clusters / images that contain no long text rows (i.e. figures, not tables)."""
        cands = [fitz.Rect(i["bbox"]) for i in page.get_image_info()]
        try:
            cands += list(page.cluster_drawings())
        except Exception:
            pass
        figs = []
        for r in cands:
            if r.width < 60 or r.height < 30:
                continue
            long_rows = [row for row in self.rows if r.contains(fitz.Point(row["chars"][0][0].x0 + 1, row["yc"]))
                         and len(row["text"]) > 20]
            if not long_rows:
                figs.append(r)
        return figs

    def in_figure(self, rect):
        c = fitz.Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
        return next((f for f in self.figures if f.contains(c)), None)

    def caption_row(self, fig):
        """Row index of the caption (Fig./图/Table/表) just below or above the figure."""
        pat = re.compile(r"^(Fig(ure)?\.?|图|Table|表)\s*\d")
        below = [i for i, r in enumerate(self.rows) if not r["fig"] and r["y0"] >= fig.y1 - 2]
        above = [i for i, r in enumerate(self.rows) if not r["fig"] and r["y1"] <= fig.y0 + 2]
        for i in below[:2] + above[-2:][::-1]:
            if pat.match(self.rows[i]["text"]):
                return i
        return None

    def nearest_row(self, y):
        idx = [i for i, r in enumerate(self.rows) if r["lineno"] is not None and not r["fig"]] \
            or list(range(len(self.rows)))
        return min(idx, key=lambda i: abs(self.rows[i]["yc"] - y)) if idx else None

    def select(self, rects):
        """Characters whose centre lies inside any of rects -> sorted [(row, col)]."""
        hit = set()
        for rect in rects:
            rr = fitz.Rect(rect.x0 - 1, rect.y0 - 1, rect.x1 + 1, rect.y1 + 1)
            for row in self.rows:
                if row["y1"] < rr.y0 or row["y0"] > rr.y1:
                    continue
                for ch in row["chars"]:
                    if rr.contains(self._center(ch[0])):
                        hit.add(self.pos[id(ch)])
        return sorted(hit)

    def target_from_positions(self, positions):
        if not positions:
            return None
        spans = {}
        for r, c in positions:
            lo, hi = spans.get(r, (c, c))
            spans[r] = (min(lo, c), max(hi, c))
        positions = []
        for r in sorted(spans):
            chars = self.rows[r]["chars"]
            lo, hi = spans[r]
            while lo < hi and not chars[lo][1].strip():
                lo += 1
            while hi > lo and not chars[hi][1].strip():
                hi -= 1
            if chars[lo][1].strip():
                positions += [(r, c) for c in range(lo, hi + 1)]
        if not positions:
            return None
        rows = sorted({p[0] for p in positions})
        parts, prev = [], None
        for r, c in positions:
            ch = self.rows[r]["chars"][c][1]
            if prev is not None and r != prev and parts and parts[-1][-1:].isascii() and ch.isascii():
                parts.append(" ")
            parts.append(ch)
            prev = r
        first, last = self.row_label(rows[0]), self.row_label(rows[-1])
        line = str(first[0]) if rows[0] == rows[-1] else f"{first[0]}-{last[0]}"
        return dict(page=self.page.number + 1, line=line, line_src=first[1],
                    col=positions[0][1] + 1, len=len(positions),
                    text="".join(parts).strip(),
                    context=" ".join(self.rows[r]["text"] for r in range(rows[0], rows[-1] + 1)),
                    _y=self.rows[rows[0]]["yc"], _x=self.rows[rows[0]]["chars"][positions[0][1]][0].x0)

    def target_whole_row(self, ri, caret_x=None):
        row = self.rows[ri]
        label = self.row_label(ri)
        t = dict(page=self.page.number + 1, line=str(label[0]), line_src=label[1],
                 col=1, len=len(row["text"]), text=row["text"], context=row["text"],
                 _y=row["yc"], _x=row["chars"][0][0].x0)
        if caret_x is not None:
            ci = min(range(len(row["chars"])), key=lambda i: abs(row["chars"][i][0].x0 - caret_x))
            t.update(col=ci + 1, len=0, text="", _x=caret_x)
        return t


def dist(r1, r2):
    dx = max(r2.x0 - r1.x1, r1.x0 - r2.x1, 0)
    dy = max(r2.y0 - r1.y1, r1.y0 - r2.y1, 0)
    return (dx * dx + dy * dy) ** 0.5


def quads(a):
    v = a.vertices or []
    if v and len(v) % 4 == 0 and a.type[1] in MARKUP:
        return [fitz.Quad(v[i:i + 4]).rect for i in range(0, len(v), 4)]
    return [a.rect]


def extract(pdf_path, near, gap, pair):
    doc = fitz.open(pdf_path)
    entries = []
    for page in doc:
        annots = list(page.annots())
        if not annots:
            continue
        pg = Page(page)
        by_xref = {a.xref: a for a in annots}
        replies = {}
        for a in annots:
            if a.irt_xref and a.irt_xref in by_xref:
                replies.setdefault(a.irt_xref, []).append(a)

        marks, notes = [], []
        for a in annots:
            typ = a.type[1]
            if typ == "Popup" or a.irt_xref in by_xref:
                continue
            info = a.info
            comment = clean(info.get("content"))
            for r in replies.get(a.xref, []):
                comment += f" / 【回复 {r.info.get('title', '')}】{clean(r.info.get('content'))}"
            item = dict(kind=typ, author=info.get("title", ""), comment=comment,
                        time=pdf_minutes(info.get("creationDate")), rects=quads(a), annot_rect=a.rect)
            if typ in MARKUP or typ in AREA:
                tgt = pg.target_from_positions(pg.select(item["rects"]))
                if tgt is None:
                    ri = pg.nearest_row((a.rect.y0 + a.rect.y1) / 2)
                    if ri is None:
                        continue
                    tgt = pg.target_whole_row(ri)
                    tgt["text"] = "（图形/空白区域，无文字）"
                    tgt["len"] = 0
                item["targets"] = [tgt]
                marks.append(item)
            elif typ in POINT:
                ri = pg.nearest_row((a.rect.y0 + a.rect.y1) / 2)
                if ri is None:
                    continue
                if typ == "Caret":
                    item["targets"] = [pg.target_whole_row(ri, caret_x=a.rect.x0)]
                    marks.append(item)
                else:
                    fig = pg.in_figure(a.rect)
                    if fig is not None:
                        cap = pg.caption_row(fig)
                        tgt = pg.target_whole_row(cap if cap is not None else ri)
                        yc = (a.rect.y0 + a.rect.y1) / 2
                        tgt.update(text="（批注贴在图上）", len=0, _y=yc,
                                   context=("图题：" if cap is not None else "最近正文行：") + tgt["context"])
                        if pg.linenos:
                            tgt["line"] = str(min(pg.linenos, key=lambda t: abs(t[0] - yc))[1])
                    else:
                        tgt = pg.target_whole_row(ri)
                    item["targets"] = [tgt]
                    notes.append(item)

        if pair:
            have_time = all(n["time"] is not None for n in notes) and all(m["time"] is not None for m in marks)
            notes.sort(key=lambda n: (n["time"] or 0))
            used, prev_t = set(), None
            for n in notes:
                if n["kind"] != "Text":
                    continue
                cand = []
                for i, m in enumerate(marks):
                    if i in used or m["comment"] or m["kind"] not in MARKUP:
                        continue
                    d = min(dist(r, n["annot_rect"]) for r in m["rects"])
                    if have_time:
                        if not ((prev_t is None or m["time"] >= prev_t) and m["time"] <= n["time"]):
                            continue
                        if n["time"] - m["time"] > gap or d > near:
                            continue
                        cand.append(i)
                    elif d <= near / 2:
                        cand.append((d, i))
                if not have_time and cand:
                    cand = [min(cand)[1]]
                prev_t = n["time"]
                if cand:
                    used.update(cand)
                    ts = [marks[i]["targets"][0] for i in cand]
                    ts.sort(key=lambda t: (t["_y"], t["_x"]))
                    n["targets"] = ts
                    n["kind"] = "Text+" + "+".join(sorted({marks[i]["kind"] for i in cand}))
            marks = [m for i, m in enumerate(marks) if i not in used]

        for it in marks + notes:
            it["page"] = page.number + 1
            entries.append(it)

    entries.sort(key=lambda e: (e["page"], e["targets"][0]["_y"], e["targets"][0]["_x"]))
    return entries


def fmt_target_inline(t):
    return " | ".join(f"{k}={pipe_safe(str(t[k]))}" for k in ("page", "line", "line_src", "col", "len", "text", "context"))


def write_md(entries, pdf_path, out):
    lines = [f"# PDF 审阅批注清单：{Path(pdf_path).name}", "",
             f"- source_pdf: {Path(pdf_path).resolve()}",
             f"- generated: {datetime.datetime.now():%Y-%m-%d %H:%M}",
             f"- total: {len(entries)}（有评语 {sum(1 for e in entries if e['comment'])}，"
             f"仅标记无评语 {sum(1 for e in entries if not e['comment'])}）",
             "- 字段：line_src=lineno 表示 PDF 页边印刷行号，page_row 表示本页第几行；col 从 1 起；"
             "len 为选中字符数；context 为所在整行原文；comment=none 表示只做了标记未写评语；"
             "标尺式行号可能有 ±1 偏差",
             "- 便签与高亮的配对为启发式推断，可直接修改本文件纠正；后续脚本以本文件为准", ""]
    for i, e in enumerate(entries, 1):
        t = e["targets"][0]
        lines += [f"## C{i:03d}",
                  f"- page: {t['page']}",
                  f"- line: {t['line']}",
                  f"- line_src: {t['line_src']}",
                  f"- col: {t['col']}",
                  f"- len: {t['len']}",
                  f"- kind: {e['kind']}",
                  f"- author: {e['author']}",
                  f"- text: {t['text']}",
                  f"- context: {t['context']}",
                  f"- comment: {e['comment'] or 'none'}"]
        if len(e["targets"]) > 1:
            lines.append("- more_targets:")
            lines += [f"  - {fmt_target_inline(x)}" for x in e["targets"][1:]]
        lines.append("")
    Path(out).write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out")
    ap.add_argument("--near", type=float, default=45, help="便签与高亮配对的最大距离（pt）")
    ap.add_argument("--gap", type=float, default=10, help="高亮须在便签前多少分钟内创建")
    ap.add_argument("--no-pair", action="store_true", help="不做便签-高亮配对，全部单独成条")
    a = ap.parse_args()
    out = a.out or str(Path(a.pdf).with_name(Path(a.pdf).stem + "_comments.md"))
    entries = extract(a.pdf, a.near, a.gap, not a.no_pair)
    write_md(entries, a.pdf, out)
    n_c = sum(1 for e in entries if e["comment"])
    print(f"wrote {out}: {len(entries)} entries ({n_c} with comment, {len(entries) - n_c} mark-only)")


if __name__ == "__main__":
    main()
