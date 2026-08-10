# 扰动规模对照（独立批次）

本目录**只**存放「受扰动任务比例 φ → paper01 vs paper04」的对比结果。  
与 `../e1_miss.csv`、`../e5_cross_curve.csv` 等分离，勿混用。

## 程序（独立入口）

```powershell
cd STRC
py -m tools.scale_compare
py -m tools.scale_compare --scales 0.1,0.25,0.5,0.75,1.0 --budget-sec 2 --seeds 42,7
```

代码：`STRC/tools/scale_compare.py`（专用于本对照，不写入其它 experiments 表）。

## 协议

1. 基线排程；在 \(t_{now}\) 之后仍有预约的工序视为「未来工序」。  
2. 按最早未来预约时刻排序，取前 \(\varphi\) 比例为受扰动工序（\(\varphi=1\) = 全部未来工序）。  
3. **物理扰动**：将这些工序的未来预约时窗逐条封死（微阻断，不合并）。  
4. **paper04 (STRC)**：与微阻断重叠的预约作种子 → 时空闭包 → 第 1 级改路；失败则扩域再修（同工件后缀 → 同车后缀 → 全部未来预约）。  
5. **paper01 (R0+)**：同一微阻断下，热启动闭环 GA，固定挂钟预算。  

## 输出

| 文件 | 内容 |
| --- | --- |
| `scale_compare.csv` | 逐种子×φ 明细 |
| `scale_compare.md` | 按 φ 汇总的对比表 |
