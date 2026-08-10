"""把 Word 文档 (.docx) 或 Word 可打开的 HTML 转成 Markdown。

用法:
    py Convert_Word_to_MD.py                              # 默认转换同目录 汇报稿_应用场景介绍.docx
    py Convert_Word_to_MD.py 汇报稿_应用场景介绍.docx
    py Convert_Word_to_MD.py 汇报稿_应用场景介绍.html

优先用 .docx(结构更完整); .html 为 Word 另存产物时也可。
若目标 .md 已存在,则写入 *_from_word.md,避免覆盖原稿。
纯标准库实现,无需额外依赖。
"""
from __future__ import annotations

import io
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"

# Word 常见标题样式名 → Markdown 级别
HEADING_STYLES = {
    "heading1": 1, "heading 1": 1, "标题 1": 1, "标题1": 1,
    "heading2": 2, "heading 2": 2, "标题 2": 2, "标题2": 2,
    "heading3": 3, "heading 3": 3, "标题 3": 3, "标题3": 3,
    "heading4": 4, "heading 4": 4, "标题 4": 4, "标题4": 4,
    "title": 1, "标题": 1,
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if tag.startswith("{") else tag


def _heading_level_from_name(name: str) -> int | None:
    key = (name or "").strip().lower()
    if key in HEADING_STYLES:
        return HEADING_STYLES[key]
    m = re.match(r"heading\s*(\d)", key)
    if m:
        return int(m.group(1))
    m = re.match(r"标题\s*(\d)", (name or "").strip())
    if m:
        return int(m.group(1))
    return None


def _load_style_maps(zf: zipfile.ZipFile) -> tuple[dict[str, int], set[str]]:
    """从 styles.xml 得到 styleId→标题级别, 以及预格式(代码块)样式集合。"""
    heading: dict[str, int] = {}
    preformatted: set[str] = set()
    try:
        root = ET.fromstring(zf.read("word/styles.xml"))
    except KeyError:
        return heading, preformatted

    for style in root.findall(f"{W}style"):
        sid = style.get(f"{W}styleId") or ""
        name_el = style.find(f"{W}name")
        name = name_el.get(f"{W}val") if name_el is not None else ""
        level = _heading_level_from_name(name)
        if level is None:
            ppr = style.find(f"{W}pPr")
            if ppr is not None:
                ol = ppr.find(f"{W}outlineLvl")
                if ol is not None and ol.get(f"{W}val") is not None:
                    try:
                        level = int(ol.get(f"{W}val")) + 1
                    except ValueError:
                        level = None
        if level is not None and 1 <= level <= 4:
            heading[sid] = level
            heading[sid.lower()] = level
        # HTML Preformatted / HTML Code 等
        lname = (name or "").lower()
        if "preformatted" in lname or lname in ("html code", "code", "源代码"):
            preformatted.add(sid)

    for guess in ("Heading1", "Heading2", "Heading3", "Heading4"):
        lv = int(guess[-1])
        heading.setdefault(guess, lv)
        heading.setdefault(guess.lower(), lv)
    return heading, preformatted


def _run_text(run: ET.Element) -> str:
    """从 w:r 提取文本,并按粗体/斜体包一层 Markdown。"""
    parts: list[str] = []
    for child in run:
        name = _local(child.tag)
        if name == "t":
            parts.append(child.text or "")
        elif name == "tab":
            parts.append("\t")
        elif name == "br" or name == "cr":
            parts.append("\n")
    text = "".join(parts)
    if not text:
        return ""

    rpr = run.find(f"{W}rPr")
    bold = italic = False
    if rpr is not None:
        b = rpr.find(f"{W}b")
        i = rpr.find(f"{W}i")
        if b is not None:
            bold = b.get(f"{W}val") not in ("0", "false", "False")
        if i is not None:
            italic = i.get(f"{W}val") not in ("0", "false", "False")

    # 空白不包标记
    if text.strip():
        if bold and italic:
            text = f"***{text}***"
        elif bold:
            text = f"**{text}**"
        elif italic:
            text = f"*{text}*"
    return text


def _para_style(p: ET.Element) -> str:
    ppr = p.find(f"{W}pPr")
    if ppr is None:
        return ""
    style = ppr.find(f"{W}pStyle")
    if style is None:
        return ""
    return style.get(f"{W}val") or ""


def _is_list_item(p: ET.Element) -> tuple[bool, str]:
    """返回 (是否列表项, 'ol'|'ul')。"""
    ppr = p.find(f"{W}pPr")
    if ppr is None:
        return False, "ul"
    numpr = ppr.find(f"{W}numPr")
    if numpr is None:
        return False, "ul"
    # 无法可靠区分有序/无序时默认无序; 若段落文本以数字.开头则交给正文识别
    return True, "ul"


def _para_text(p: ET.Element) -> str:
    bits: list[str] = []
    for child in p:
        name = _local(child.tag)
        if name == "r":
            bits.append(_run_text(child))
        elif name == "hyperlink":
            for run in child.findall(f"{W}r"):
                bits.append(_run_text(run))
    # 合并相邻加粗: **a****b** → **ab** (只处理四个连续星号,避免误伤斜体)
    text = "".join(bits).replace("\n", " ")
    while "****" in text:
        text = text.replace("****", "")
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _cell_text(tc: ET.Element) -> str:
    paras = []
    for p in tc.findall(f"{W}p"):
        t = _para_text(p)
        if t:
            paras.append(t)
    return "<br>".join(paras).replace("\n", " ").strip()


def _table_to_md(tbl: ET.Element) -> str:
    rows: list[list[str]] = []
    for tr in tbl.findall(f"{W}tr"):
        cells = [_cell_text(tc) for tc in tr.findall(f"{W}tc")]
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    for r in rows:
        while len(r) < width:
            r.append("")
    lines = [
        "| " + " | ".join(rows[0]) + " |",
        "| " + " | ".join("---" for _ in range(width)) + " |",
    ]
    for r in rows[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def convert_docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        heading_map, pre_styles = _load_style_maps(zf)
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    body = root.find(f"{W}body")
    if body is None:
        return ""

    out: list[str] = []
    pre_buf: list[str] = []

    def flush_pre() -> None:
        if not pre_buf:
            return
        out.append("```")
        out.extend(pre_buf)
        out.append("```")
        out.append("")
        pre_buf.clear()

    for child in body:
        name = _local(child.tag)
        if name == "tbl":
            flush_pre()
            md = _table_to_md(child)
            if md:
                out.append(md)
                out.append("")
            continue
        if name != "p":
            continue

        style = _para_style(child).strip()
        level = heading_map.get(style) or heading_map.get(style.lower())
        if level is None:
            level = _heading_level_from_name(style)

        # 预格式段落:保留行内原样(不加粗标记),合并为代码块
        if style in pre_styles:
            raw_parts: list[str] = []
            for t in child.iter(f"{W}t"):
                raw_parts.append(t.text or "")
            # 空行也保留,用于 ASCII 图
            pre_buf.append("".join(raw_parts))
            continue

        text = _para_text(child)
        # 空的普通段落不打断预格式块(Word 有时会在 <pre> 行间插空段)
        if not text and not level:
            continue

        flush_pre()

        if level:
            # 标题里的加粗标记通常是样式带来的,去掉最外层成对 **
            title = re.sub(r"^\*\*(.+)\*\*$", r"\1", text)
            out.append("#" * level + " " + title)
            out.append("")
            continue

        is_list, _ = _is_list_item(child)
        if is_list:
            cleaned = re.sub(r"^\d+[\.\、]\s*", "", text)
            cleaned = re.sub(r"^[•●○■▪]\s*", "", cleaned)
            out.append(f"- {cleaned}")
            continue

        out.append(text)
        out.append("")

    flush_pre()
    return _normalize_md("\n".join(out))


def _merge_adjacent_fences(md: str) -> str:
    """把紧邻的多个 ``` 块合并成一个(Word HTML 常把 ASCII 图拆成逐行 <pre>)。"""
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].strip() != "```":
            out.append(lines[i])
            i += 1
            continue
        # 语言标记行: ```text
        fence_open = lines[i].strip()
        out.append(fence_open if fence_open == "```" else "```")
        i += 1
        while i < n:
            if lines[i].strip() == "```":
                j = i + 1
                while j < n and lines[j].strip() == "":
                    j += 1
                if j < n and lines[j].strip().startswith("```"):
                    # 跳过结束围栏 + 空行 + 下一开始围栏,继续同一代码块
                    i = j + 1
                    continue
                out.append("```")
                i += 1
                break
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def _normalize_md(md: str) -> str:
    md = _merge_adjacent_fences(md)
    # 附录问答: Word 常把「答:」粘在同一行,拆开便于阅读
    md = re.sub(r"(\*\*问[:：][^*]*\*\*)\s*答[:：]", r"\1\n答:", md)
    md = re.sub(r"(问[:：][^\n]*\?\*?)\s*答[:：]", r"\1\n答:", md)
    lines = md.split("\n")
    result: list[str] = []
    prev_list = False
    for line in lines:
        is_list = bool(re.match(r"^[-*]\s+", line) or re.match(r"^\d+\.\s+", line))
        if is_list and prev_list and result and result[-1] == "":
            result.pop()
        result.append(line)
        prev_list = is_list
    text = "\n".join(result)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


# ---------- HTML (Word 另存 / md_to_word_html 产物) ----------

class _HtmlToMd(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._buf: list[str] = []
        self._tag_stack: list[str] = []
        self._in_pre = False
        self._pre_lines: list[str] = []
        self._in_code = False
        self._skip = False
        self._table_rows: list[list[str]] = []
        self._row: list[str] = []
        self._cell_buf: list[str] = []
        self._in_cell = False
        self._list_type: list[str] = []
        self._ol_index: list[int] = []

    def _flush_pre(self) -> None:
        if not self._pre_lines:
            return
        self.out.append("```")
        self.out.extend(self._pre_lines)
        self.out.append("```")
        self.out.append("")
        self._pre_lines = []

    def _begin_block(self) -> None:
        """进入标题/段落/列表/表格等块级元素前,先结束代码块序列。"""
        self._flush_pre()
        self._flush_loose()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in ("script", "style", "head"):
            self._skip = True
            return
        if self._skip:
            return

        if tag in ("h1", "h2", "h3", "h4"):
            self._begin_block()
            self._tag_stack.append(tag)
        elif tag == "p":
            self._begin_block()
            self._tag_stack.append(tag)
        elif tag == "br":
            self._buf.append("\n" if self._in_pre else "<br>")
        elif tag == "hr":
            self._begin_block()
            self.out.append("---")
            self.out.append("")
        elif tag == "strong" or tag == "b":
            self._buf.append("**")
            self._tag_stack.append("strong")
        elif tag == "em" or tag == "i":
            self._buf.append("*")
            self._tag_stack.append("em")
        elif tag == "code" and not self._in_pre:
            self._buf.append("`")
            self._in_code = True
            self._tag_stack.append("code")
        elif tag == "pre":
            # Word 常把 ASCII 图拆成连续多个 <pre>; 只开一次收集
            self._flush_loose()
            self._in_pre = True
            self._buf.clear()
        elif tag == "blockquote":
            self._begin_block()
            self._tag_stack.append("blockquote")
        elif tag == "ul":
            self._begin_block()
            self._list_type.append("ul")
        elif tag == "ol":
            self._begin_block()
            self._list_type.append("ol")
            self._ol_index.append(0)
        elif tag == "li":
            self._begin_block()
            self._tag_stack.append("li")
        elif tag == "table":
            self._begin_block()
            self._table_rows = []
            self._tag_stack.append("table")
        elif tag == "tr":
            self._row = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._cell_buf = []
        elif tag == "a":
            self._tag_stack.append("a")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("script", "style", "head"):
            self._skip = False
            return
        if self._skip:
            return

        if tag in ("h1", "h2", "h3", "h4"):
            level = int(tag[1])
            text = "".join(self._buf).strip()
            self._buf.clear()
            if text:
                self.out.append("#" * level + " " + text)
                self.out.append("")
            self._pop("h1", "h2", "h3", "h4")
        elif tag == "p":
            text = "".join(self._buf).strip()
            self._buf.clear()
            if text:
                if self._tag_stack and "blockquote" in self._tag_stack:
                    for line in text.split("\n"):
                        self.out.append("> " + line)
                    self.out.append("")
                else:
                    self.out.append(text)
                    self.out.append("")
            self._pop("p")
        elif tag in ("strong", "b"):
            self._buf.append("**")
            self._pop("strong")
        elif tag in ("em", "i"):
            self._buf.append("*")
            self._pop("em")
        elif tag == "code" and self._in_code:
            self._buf.append("`")
            self._in_code = False
            self._pop("code")
        elif tag == "pre":
            # 保留行首空格(ASCII 图对齐); Word 常用 NBSP(\xa0) 充当空格
            line = "".join(self._buf).replace("\r", "").replace("\xa0", " ").rstrip("\n")
            self._buf.clear()
            self._in_pre = False
            self._pre_lines.append(line)
        elif tag == "blockquote":
            self._flush_loose()
            self._pop("blockquote")
        elif tag == "li":
            text = "".join(self._buf).strip()
            self._buf.clear()
            if self._list_type and self._list_type[-1] == "ol":
                self._ol_index[-1] += 1
                self.out.append(f"{self._ol_index[-1]}. {text}")
            else:
                self.out.append(f"- {text}")
            self._pop("li")
        elif tag == "ul":
            if self._list_type and self._list_type[-1] == "ul":
                self._list_type.pop()
            self.out.append("")
        elif tag == "ol":
            if self._list_type and self._list_type[-1] == "ol":
                self._list_type.pop()
            if self._ol_index:
                self._ol_index.pop()
            self.out.append("")
        elif tag in ("td", "th"):
            cell = "".join(self._cell_buf if self._in_cell else self._buf).strip()
            if not cell and self._buf:
                cell = "".join(self._buf).strip()
                self._buf.clear()
            self._cell_buf = []
            self._in_cell = False
            self._row.append(cell.replace("\n", " "))
        elif tag == "tr":
            if self._row:
                self._table_rows.append(self._row)
            self._row = []
        elif tag == "table":
            if self._table_rows:
                width = max(len(r) for r in self._table_rows)
                for r in self._table_rows:
                    while len(r) < width:
                        r.append("")
                lines = [
                    "| " + " | ".join(self._table_rows[0]) + " |",
                    "| " + " | ".join("---" for _ in range(width)) + " |",
                ]
                for r in self._table_rows[1:]:
                    lines.append("| " + " | ".join(r) + " |")
                self.out.append("\n".join(lines))
                self.out.append("")
            self._table_rows = []
            self._pop("table")
        elif tag == "a":
            self._pop("a")
        elif tag == "div":
            # Word 常用 div 包住一串 <pre>; 离开 div 时收束代码块
            self._flush_pre()

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_cell:
            self._cell_buf.append(data)
            return
        if self._in_pre:
            self._buf.append(data)
            return
        if not self._in_code:
            data = re.sub(r"[ \t]+", " ", data)
        self._buf.append(data)

    def _pop(self, *names: str) -> None:
        if self._tag_stack and self._tag_stack[-1] in names:
            self._tag_stack.pop()

    def _flush_loose(self) -> None:
        if not self._buf:
            return
        if any(t in self._tag_stack for t in ("p", "h1", "h2", "h3", "h4", "li")):
            return
        if self._in_pre:
            return
        text = "".join(self._buf).strip()
        self._buf.clear()
        if text:
            self.out.append(text)
            self.out.append("")

    def _flush_para(self) -> None:
        self._flush_loose()


def convert_html(text: str) -> str:
    parser = _HtmlToMd()
    parser.feed(text.lstrip("\ufeff"))
    parser._flush_pre()
    parser._flush_loose()
    return _normalize_md("\n".join(parser.out))


def _read_text_auto(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe"):
        return data.decode("utf-16-le")
    if data.startswith(b"\xfe\xff"):
        return data.decode("utf-16-be")
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8")
    for enc in ("utf-8", "gb18030", "utf-16"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def convert_file(src: Path) -> str:
    suffix = src.suffix.lower()
    if suffix == ".docx":
        return convert_docx(src.read_bytes())
    if suffix in (".html", ".htm"):
        return convert_html(_read_text_auto(src))
    raise ValueError(f"不支持的文件类型: {suffix} (请使用 .docx / .html)")


def main() -> int:
    here = Path(__file__).resolve().parent
    default_src = here / "汇报稿_应用场景介绍.docx"

    if len(sys.argv) >= 2:
        src = Path(sys.argv[1])
        if not src.is_absolute():
            cand = Path.cwd() / src
            src = cand if cand.is_file() else (here / src)
    else:
        src = default_src
        print(f"未指定文件,使用默认: {src.name}")

    if not src.is_file():
        print(f"找不到 Word/HTML 文件: {src}", file=sys.stderr)
        print(__doc__)
        return 1

    try:
        md = convert_file(src)
    except Exception as e:
        print(f"转换失败: {e}", file=sys.stderr)
        return 1

    dst = src.with_suffix(".md")
    # 避免误覆盖已有 Markdown 源稿
    if dst.exists():
        dst = src.with_name(src.stem + "_from_word.md")
    dst.write_text(md, encoding="utf-8")
    print(f"已生成 {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
