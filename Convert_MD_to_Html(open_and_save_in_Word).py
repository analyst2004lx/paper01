"""把汇报稿 Markdown 转成 Word 可直接打开的 HTML。

用法:
    py md_to_word_html.py                          # 默认转换同目录 汇报稿_应用场景介绍.md
    py md_to_word_html.py 汇报稿_应用场景介绍.md

生成同名 .html 文件。用 Word 打开该文件,再"另存为"→"Word 文档(*.docx)"即可。
正文用宋体、字符图用新宋体(NSimSun,中文全角/英文半角等宽,能保持 ASCII 图对齐)。
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

CSS = """
body { font-family: "宋体", SimSun, serif; font-size: 11pt; line-height: 1.7;
       max-width: 900px; margin: 2em auto; color: #000; }
h1 { font-family: "黑体", SimHei, sans-serif; font-size: 20pt; text-align: center;
     margin-top: 1em; }
h2 { font-family: "黑体", SimHei, sans-serif; font-size: 15pt; margin-top: 1.6em;
     border-bottom: 1px solid #999; padding-bottom: 4px; }
h3 { font-family: "黑体", SimHei, sans-serif; font-size: 12.5pt; margin-top: 1.2em; }
pre { font-family: NSimSun, "新宋体", Consolas, monospace; font-size: 10pt;
      line-height: 1.25; background: #f6f6f6; border: 1px solid #ccc;
      padding: 10px; white-space: pre; overflow-x: auto; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10.5pt; }
th, td { border: 1px solid #666; padding: 5px 8px; vertical-align: top;
         text-align: left; }
th { background: #e8e8e8; font-weight: bold; }
blockquote { border-left: 4px solid #999; margin: 1em 0; padding: 0.4em 1em;
             background: #f6f6f6; }
code { font-family: NSimSun, Consolas, monospace; background: #f0f0f0;
       padding: 0 3px; }
hr { border: none; border-top: 1px solid #bbb; margin: 2em 0; }
li { margin: 0.3em 0; }
"""


def inline(text: str) -> str:
    """行内标记:转义 HTML 后,还原 <br>,再处理粗体/斜体/行内代码。"""
    text = html.escape(text, quote=False).replace("&lt;br&gt;", "<br>")
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def convert(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    i = 0
    list_stack: list[str] = []   # 'ul' / 'ol'

    def close_lists() -> None:
        while list_stack:
            out.append(f"</{list_stack.pop()}>")

    while i < len(lines):
        line = lines[i]

        # 代码块
        if line.startswith("```"):
            i += 1
            block: list[str] = []
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(html.escape(lines[i], quote=False))
                i += 1
            i += 1
            close_lists()
            out.append("<pre>" + "\n".join(block) + "</pre>")
            continue

        # 表格:当前行与下一行构成 |---|---| 的分隔样式
        if (line.strip().startswith("|") and i + 1 < len(lines)
                and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1])):
            close_lists()
            header = split_row(line)
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            out.append("<table>")
            out.append("<tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr>")
            for r in rows:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
            out.append("</table>")
            continue

        stripped = line.strip()

        if not stripped:
            close_lists()
            i += 1
            continue

        if re.match(r"^-{3,}$", stripped):
            close_lists()
            out.append("<hr>")
            i += 1
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            close_lists()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        if stripped.startswith(">"):
            close_lists()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + "<br>".join(inline(q) for q in quote if q)
                       + "</blockquote>")
            continue

        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            if not list_stack or list_stack[-1] != "ol":
                close_lists()
                out.append("<ol>")
                list_stack.append("ol")
            out.append(f"<li>{inline(m.group(2))}</li>")
            i += 1
            continue

        m = re.match(r"^[-*]\s+(.*)$", stripped)
        if m:
            if not list_stack or list_stack[-1] != "ul":
                close_lists()
                out.append("<ul>")
                list_stack.append("ul")
            out.append(f"<li>{inline(m.group(1))}</li>")
            i += 1
            continue

        # 普通段落(合并连续行)
        para = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^\s*(#{1,4}\s|```|\||>|[-*]\s|\d+\.\s|-{3,}$)", lines[i]):
            para.append(lines[i].strip())
            i += 1
        close_lists()
        out.append("<p>" + inline("".join(para)) + "</p>")

    close_lists()
    return "\n".join(out)


def main() -> int:
    here = Path(__file__).resolve().parent
    default_src = here / "汇报稿_应用场景介绍.md"

    if len(sys.argv) >= 2:
        src = Path(sys.argv[1])
        if not src.is_absolute():
            # Prefer cwd, then script directory
            cand = Path.cwd() / src
            src = cand if cand.is_file() else (here / src)
    else:
        src = default_src
        print(f"未指定文件,使用默认: {src.name}")

    if not src.is_file():
        print(f"找不到 Markdown 文件: {src}", file=sys.stderr)
        print(__doc__)
        return 1

    body = convert(src.read_text(encoding="utf-8"))
    doc = (f'<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
           f"<title>{html.escape(src.stem)}</title>\n<style>{CSS}</style>\n"
           f"</head>\n<body>\n{body}\n</body>\n</html>\n")
    dst = src.with_suffix(".html")
    dst.write_text(doc, encoding="utf-8")
    print(f"已生成 {dst}")
    print("用 Word 打开该文件,再另存为 .docx 即可。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
