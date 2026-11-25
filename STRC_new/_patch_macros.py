import re
import sys

P = r"c:\Users\analy\Desktop\AI_Folder\paper04\paper04_CN_v3.tex"
NEW = {
    "FeasRtwo": r"\NPairs/\NPairs",
    "PassInvar": r"\NPairs/\NPairs",
    "EoneCloLo": "0.56", "EoneCloHi": "0.60",
    "MsRepairMed": "7.3", "MsRepairMax": "9.7",
    "EfiveWLT": "33/2/1", "EfiveWinMin": "9", "EfiveTieMin": "2",
    "EoneFracIqrLo": "0.039", "EoneFracIqrHi": "0.105", "EoneFracMed": "0.590",
    "EoneFracMin": "0.321", "EoneFracMax": "0.667",
    "ScaleMsMin": "4.2", "ScaleMsMax": "13.9", "ScaleCmaxIqrLo": "2", "ScaleCmaxIqrHi": "15",
    "SpeedLo": "149", "SpeedHi": "3475",
    "StrictlyLarger": "82/100", "ClosureAliveFrac": r"90\%",
    "PubEfiveNoCross": "16/18",
    "MsShift": "1.91", "MsRedecode": "8.94", "MsAllFuture": "7.19", "MsCheapRtwo": "7.67",
    "RedecodeRatio": "1.2",
    "WinVsShift": "24/14/5", "WinVsRedecode": "9/13/28", "WinVsAllFuture": r"0/\NPairs/0",
    "ResFracCheapRtwo": "0.568", "ResFracShift": "0.622", "ResFracRedecode": "0.581",
    "ResFracAllFuture": "0.568",
    "RAStabWTL": "2/47/1", "ClosureShareLo": "0.56", "ClosureShareMean": "0.90",
    "ScaleCloLo": "0.51", "ScaleCloHi": "0.57",
    "ScaleAliveShare": "0.61", "ScaleCloAliveLo": "0.82", "ScaleCloAliveHi": "0.92",
    "ScaleMsHi": "26.3", "ScaleRatioLo": "1.2", "ScaleRatioHi": "3.0",
    "ScaleFeasFirst": r"68/\ScalePairs", "ScaleFeasAll": r"68/\ScalePairs",
    "ProbeLeakPairs": "2/50", "ProbeLeaks": "2", "ProbeOutsidePairs": "48",
    "SegExtraPairs": r"46/\NPairs", "SegExtraMean": "4.1", "SegExtraMax": "15", "SegShare": "0.96",
    "TierReplanShare": "0.69", "WCRouteFrac": "0.13", "WCTimeFrac": "0.77",
    "FeasESixBlock": r"\NPairs/\NPairs", "FeasSlow": r"\NPairs/\NPairs",
    "FeasESixAgv": r"\NPairs/\NPairs", "FeasESixRa": r"\NPairs/\NPairs",
    "WeightLogRtwo": r"49/\NPairs", "WeightLuRtwo": r"\NPairs/\NPairs", "WeightSplitRtwo": r"48/\NPairs",
}
COMMENTS = {
    "FeasRtwo": "% R2 恢复可行的格数",
    "PassInvar": "% E2b 外侧字段逐条不变",
    "EfiveTieMin": "% 同,持平的格数(example_3x3x2 种子 42;LyuL6_8m 种子 2024)",
    "WinVsShift": "% R2 对 RS 的 Cmax 赢/平/输(两臂都可行的 43 对)",
    "WinVsRedecode": "% 同,R2 对 RD(50 对)",
    "WinVsAllFuture": "% 同,R2 对 RA(50 对)",
    "ScaleCloLo": "% 闭包占全表比例,各规模均值最低:k=8 的 0.509",
    "ScaleCloHi": "% 同,最高:k=4 的 0.568",
    "ScaleAliveShare": "% 均 |R^o|/|R|,七个规模的均值 0.609",
    "ScaleCloAliveLo": "% 闭包占尚未结束占用之比,各规模均值最低:k=9 的 0.821",
    "ScaleCloAliveHi": "% 同,最高:k=6 的 0.920",
    "ScaleMsHi": "% R2 耗时中位:k=10",
    "ScaleRatioLo": "% RD/R2 耗时比(中位数之比):k=4",
    "ScaleRatioHi": "% 同,k=10",
}
src = open(P, encoding="utf-8").read()
for k, v in NEW.items():
    pat = re.compile(r"^(\\newcommand\{\\" + k + r"\}\{)(.*?)(\})([ \t]*%[^\n]*)?$", re.M)
    m = pat.search(src)
    if not m:
        sys.exit("missing " + k)
    com = m.group(4) or ""
    if k in COMMENTS:
        com = "  " + COMMENTS[k]
    line = m.group(1) + v + m.group(3) + com
    src = src[:m.start()] + line + src[m.end():]
open(P, "w", encoding="utf-8", newline="").write(src)
print("ok", len(NEW))
