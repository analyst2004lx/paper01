# -*- coding: utf-8 -*-
"""核对导言区宏与生成脚本的输出是否逐字相同。

为什么要单独一个脚本:check_tex.py 只能看出"宏有没有定义、有没有被引用",看不出
宏里的**数字**是否还与 CSV 一致。重跑实验后忘记重贴宏块,是这份稿子最容易出现且
最难自查的一类错误——正文与表会各说各话,而两边都能编译通过。

用法:py paper01/check_macros.py
"""
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
GEN = os.path.join(HERE, "tab", "gen_tables_ladder.py")

env = dict(os.environ, PYTHONIOENCODING="utf-8")
r = subprocess.run([sys.executable, GEN], cwd=ROOT, env=env,
                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
out = r.stdout.decode("utf-8", "replace")
if r.returncode != 0:
    print(out)
    raise SystemExit("!! 生成脚本失败,先修它")

DEF = re.compile(r"\\newcommand\{\\([A-Za-z]+)\}\{(.*)\}\s*$")
gen = {}
for line in out.splitlines():
    m = DEF.match(line.strip())
    if m:
        gen[m.group(1)] = m.group(2)

src = io.open(os.path.join(HERE, "paper.tex"), encoding="utf-8").read()
tex = {}
for line in src.splitlines():
    # 去掉行尾注释再匹配,否则 "% A funnel(哑铃)" 会被并进宏值里
    line = re.sub(r"(?<!\\)%.*$", "", line).strip()
    m = DEF.match(line)
    if m:
        tex[m.group(1)] = m.group(2)

bad = []
for k, v in sorted(gen.items()):
    if k not in tex:
        bad.append("缺少 \\%s(生成值 %s)" % (k, v))
    elif tex[k] != v:
        bad.append("\\%s 不一致:正文 %s / 生成 %s" % (k, tex[k], v))

print("生成脚本给出 %d 个宏,导言区共 %d 个宏定义" % (len(gen), len(tex)))
if bad:
    print("不一致 %d 处:" % len(bad))
    for b in bad:
        print("  " + b)
    raise SystemExit(1)
print("全部逐字一致:表、图与正文同源。")
