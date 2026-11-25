"""把读 STRC 数据的 *_CN.py 复制成 *_CN_new.py:数据改读 STRC_new,输出名加 _new。原脚本与原图不动。"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
for name in ("fig_strc_e1e3_CN", "fig_strc_e5_CN", "fig_strc_scale_CN", "fig_strc_case_CN"):
    with open(os.path.join(HERE, name + ".py"), encoding="utf-8") as f:
        src = f.read()
    src = src.replace('"..", "..", "STRC"', '"..", "..", "STRC_new"')
    src = src.replace("单遍改路", "分层回放")
    src = re.sub(r'OUT = os\.path\.join\(HERE, "%s"\)' % name, 'OUT = os.path.join(HERE, "%s_new")' % name, src)
    assert '"%s_new"' % name in src, name
    with open(os.path.join(HERE, name + "_new.py"), "w", encoding="utf-8") as f:
        f.write(src)
    print("wrote", name + "_new.py")
