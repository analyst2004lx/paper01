# -*- coding: utf-8 -*-
"""Subset a CJK TTF so old matplotlib embeds tens of KB, not a full 20 MB font."""
from __future__ import annotations

import glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SUBSET = os.path.join(HERE, "_cjk_subset.ttf")
TTC_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simsun.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
)


def _collect_text() -> str:
    chars = set("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
    chars.update(" .,;:-+*/=()[]{}<>%#_~^'`|!?@&$\\")
    chars.update("αβγδεζηθικλμνξοπρστυφχψω")
    chars.update("—–…·×÷±≤≥≠≈∞°′″φα")
    chars.update("，。、；：？！（）【】《》“”‘’")
    for path in glob.glob(os.path.join(HERE, "*_CN.py")):
        with open(path, encoding="utf-8") as fh:
            chars.update(fh.read())
    return "".join(chars)


def _subset_stale() -> bool:
    if not os.path.isfile(SUBSET) or os.path.getsize(SUBSET) < 1000:
        return True
    mtime = os.path.getmtime(SUBSET)
    watched = glob.glob(os.path.join(HERE, "*_CN.py"))
    watched.append(os.path.join(HERE, "_cjk_mpl.py"))
    return any(os.path.isfile(p) and os.path.getmtime(p) > mtime for p in watched)


def _ensure_subset() -> str:
    if not _subset_stale():
        return SUBSET
    from fontTools.subset import Options, Subsetter
    from fontTools.ttLib import TTCollection, TTFont

    src = next(p for p in TTC_CANDIDATES if os.path.isfile(p))
    font = TTCollection(src).fonts[0] if src.lower().endswith(".ttc") else TTFont(src)
    opt = Options()
    opt.ignore_missing_glyphs = True
    opt.layout_features = ()
    opt.notdef_outline = True
    opt.recommended_glyphs = True
    subsetter = Subsetter(options=opt)
    subsetter.populate(text=_collect_text())
    subsetter.subset(font)
    family = "CJKSubset"
    nametab = font["name"]
    for name_id in (1, 4, 6, 16):
        nametab.setName(family, name_id, 3, 1, 0x409)
        nametab.setName(family, name_id, 1, 0, 0)
    font.save(SUBSET)
    return SUBSET


def setup_cjk() -> None:
    from matplotlib import font_manager, rcParams

    path = _ensure_subset()
    name = "CJKSubset"
    try:
        font_manager.fontManager.addfont(path)
        name = font_manager.FontProperties(fname=path).get_name()
    except AttributeError:
        font_manager.fontManager.ttflist.append(
            font_manager.FontEntry(
                fname=path, name=name, style="normal", variant="normal",
                weight="normal", stretch="normal", size="scalable"))
    rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [name],
        "font.serif": [name],
        "font.monospace": [name],
        "mathtext.fontset": "custom",
        "mathtext.rm": name,
        "mathtext.it": name,
        "mathtext.bf": name,
        "mathtext.default": "rm",
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "pdf.compression": 6,
    })
