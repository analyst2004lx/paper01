"""Extract highlight + sticky-note comments from an annotated PDF and map them to tex lines.

Usage: python extract_comments.py paper_CN-lw.pdf ../paper01/paper_CN.tex comments_paper_CN.md
"""
import re
import sys
import json
import fitz

PDF, TEX, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
NEAR_PT = 45  # max distance (pt) between a highlight and the note icon to be grouped
MAX_GAP_MIN = 10  # highlight must be created at most this many minutes before the note


def minutes(pdf_date):
    d = pdf_date[2:14]  # D:YYYYMMDDHHmm...
    return int(d[6:8]) * 1440 + int(d[8:10]) * 60 + int(d[10:12]) + int(d[4:6]) * 44640


def norm(s):
    s = re.sub(r"\[\d+(?:[,–-]\s*\d+)*\]", "", s)
    return re.sub(r"[\s~]", "", s)


def build_tex_index(path):
    chars, lines = [], []
    for ln, line in enumerate(open(path, encoding="utf-8"), 1):
        line = re.sub(r"(?<!\\)%.*", "", line)
        line = re.sub(r"\\(cite|ref|eqref|label|citep|citet)\{[^}]*\}", "", line)
        line = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", line)
        line = re.sub(r"[{}$\s~]", "", line)
        chars.append(line)
        lines.extend([ln] * len(line))
    return "".join(chars), lines


TEX_STR, TEX_LINES = build_tex_index(TEX)
TEX_RAW = open(TEX, encoding="utf-8").read().splitlines()


def tex_locate(text):
    t = norm(re.sub(r"^\s*(\d+(\.\d+)*|\([ivx]+\))\s*", "", text))
    for ln, line in enumerate(TEX_RAW, 1):
        if t and re.search(r"section\*?\{\s*" + re.escape(t) + r"\s*\}", line.replace(" ", "")):
            return ln
    if len(t) < 4:
        return None
    for size in (len(t), 24, 14, 8):
        if size > len(t):
            continue
        for start in range(0, len(t) - size + 1, max(1, size // 2)):
            i = TEX_STR.find(t[start:start + size])
            if i >= 0 and TEX_STR.find(t[start:start + size], i + 1) < 0:
                return TEX_LINES[i]
    return None


def page_chars(page):
    out = []
    for b in page.get_text("rawdict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                for c in s["chars"]:
                    out.append((fitz.Rect(c["bbox"]), c["c"]))
    return out


def line_numbers(page):
    """lineno-package margin numbers -> list of (y_center, number)."""
    res = []
    for x0, y0, x1, y1, w, *_ in page.get_text("words"):
        if x1 < 100 and w.isdigit():
            res.append(((y0 + y1) / 2, int(w), x1))
    xs = [round(t[2]) for t in res]
    col = max(set(xs), key=xs.count) if xs else 0
    return [t for t in res if abs(t[2] - col) < 2]


def nearest_line(nums, y):
    return min(nums, key=lambda t: abs(t[0] - y))[1] if nums else None


def text_in(chars, rect):
    sel = [(r, c) for r, c in chars if rect.contains(fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))]
    sel.sort(key=lambda t: t[0].x0)
    return "".join(c for _, c in sel)


def row_text(chars, nums, y0, y1):
    xs = [round(t[2]) for t in nums]
    left = (max(set(xs), key=xs.count) if xs else 60) + 4
    return text_in(chars, fitz.Rect(left, y0, 580, y1))


def nearest_row(chars, nums, yc):
    """Text of the body row closest to y=yc, and that row's y-center."""
    xs = [round(t[2]) for t in nums]
    left = (max(set(xs), key=xs.count) if xs else 60) + 4
    centers = {round((r.y0 + r.y1) / 2) for r, c in chars if r.x0 >= left and c.strip()}
    if not centers:
        return "", yc
    y = min(centers, key=lambda c: abs(c - yc))
    return row_text(chars, nums, y - 3, y + 3), y


def quads(annot):
    v = annot.vertices or []
    return [fitz.Quad(v[i:i + 4]).rect for i in range(0, len(v), 4)] or [annot.rect]


def dist(r1, r2):
    dx = max(r2.x0 - r1.x1, r1.x0 - r2.x1, 0)
    dy = max(r2.y0 - r1.y1, r1.y0 - r2.y1, 0)
    return (dx * dx + dy * dy) ** 0.5


doc = fitz.open(PDF)
items = []
for page in doc:
    chars, nums = page_chars(page), line_numbers(page)
    hls, notes = [], []
    for a in page.annots():
        t = a.type[1]
        info = a.info
        if t == "Highlight":
            rs = quads(a)
            text = "".join(text_in(chars, r) for r in rs)
            context = "".join(row_text(chars, nums, r.y0, r.y1) for r in rs)
            hls.append(dict(time=info["creationDate"], rects=rs, text=text,
                            tex_line=tex_locate(text) if len(norm(text)) >= 14 else tex_locate(context),
                            lines=sorted({nearest_line(nums, (r.y0 + r.y1) / 2) for r in rs} - {None})))
        elif t == "Text":
            icon = a.rect
            anchor, row_y = nearest_row(chars, nums, (icon.y0 + icon.y1) / 2)
            notes.append(dict(time=info["creationDate"], icon=icon,
                              comment=info["content"].replace("\r", "\n").strip(),
                              author=info.get("title", ""),
                              anchor=anchor, tex_line=tex_locate(anchor),
                              line=nearest_line(nums, row_y)))
    notes.sort(key=lambda n: n["time"])
    used = set()
    prev_t = ""
    for n in notes:
        group = []
        for i, h in enumerate(hls):
            if i in used or not (prev_t <= h["time"] <= n["time"]):
                continue
            if minutes(n["time"]) - minutes(h["time"]) > MAX_GAP_MIN:
                continue
            if min(dist(r, n["icon"]) for r in h["rects"]) <= NEAR_PT:
                group.append(i)
        used.update(group)
        prev_t = n["time"]
        n["highlights"] = [hls[i] for i in group]
        items.append(dict(kind="comment", page=page.number + 1, **n))
    for i, h in enumerate(hls):
        if i not in used:
            items.append(dict(kind="highlight_only", page=page.number + 1, **h))


def sort_key(it):
    ln = it["line"] if it["kind"] == "comment" else (it["lines"] or [0])[0]
    if it["kind"] == "comment" and it["highlights"]:
        ln = min([ln or 10**6] + [h["lines"][0] for h in it["highlights"] if h["lines"]])
    return (it["page"], ln or 0)


items.sort(key=sort_key)

md = [f"# 审阅意见提取：{PDF}", "",
      f"- tex 源：`{TEX}`（tex 行号为按文本自动匹配，`?` 表示未能唯一匹配）",
      "- 「锚点行」= 便签图标所在的那一行原文；「关联高亮」= 便签前创建、且位置相近的高亮（启发式配对，需人工确认）",
      "- 状态：`TODO` / `讨论中` / `已改` / `不改(理由)`", ""]
data = []
cid = hid = 0
for it in items:
    if it["kind"] == "comment":
        cid += 1
        tl = next((h["tex_line"] for h in it["highlights"] if h["tex_line"]), None) or it["tex_line"]
        md += [f"## C{cid:03d} · p{it['page']} L{it['line']} · tex L{tl or '?'}", "",
               "**评语**：" + it["comment"].replace("\n", " / "), "",
               f"**锚点行** (tex L{it['tex_line'] or '?'})：{it['anchor'] or '（图标不在正文行上）'}", ""]
        for h in it["highlights"]:
            md.append(f"- 关联高亮 (L{','.join(map(str, h['lines']))}，tex L{h['tex_line'] or '?'})：{h['text']}")
        md += ["", "**状态**：TODO", "", "**修改方案**：", ""]
        data.append(dict(id=f"C{cid:03d}", page=it["page"], pdf_line=it["line"], tex_line=tl,
                         comment=it["comment"], anchor=it["anchor"],
                         highlights=[dict(text=h["text"], pdf_lines=h["lines"], tex_line=h["tex_line"])
                                     for h in it["highlights"]]))
    else:
        hid += 1
        tl = it["tex_line"]
        md.append(f"- **H{hid:03d}** · p{it['page']} L{','.join(map(str, it['lines']))} · tex L{tl or '?'}"
                  f"（仅高亮）：{it['text']}")
        md.append("")
        data.append(dict(id=f"H{hid:03d}", page=it["page"], pdf_lines=it["lines"], tex_line=tl,
                         highlight=it["text"]))

open(OUT, "w", encoding="utf-8").write("\n".join(md))
open(OUT.rsplit(".", 1)[0] + ".json", "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=1))
print(f"comments={cid} highlight_only={hid} unmatched_tex={sum(1 for d in data if not d['tex_line'])}")
