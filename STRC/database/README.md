# STRC 本地数据副本 / STRC local data copy

paper04(执行期扰动 / 时空预约影响闭包)所依赖的公开数据与算例,在此存一份**镜像**,
使数据与用它的代码同处一地——归档、打包投稿附件、给只看 `STRC/` 的人交代出处,
都不必跨到 `clbs/` 去捞。

The public data and instances that paper04 (execution-time disturbance / spatiotemporal reservation closure) depends on are kept here as a **mirror**, so the data sits next to the code that uses it — archiving, packaging a submission attachment, and telling someone who looks only at `STRC/` where it came from do not require reaching into `clbs/`.

```powershell
cd STRC
py -m tools.sync_database            # 从 clbs/ 重新同步并重写 MANIFEST.csv / re-sync from clbs/ and rewrite MANIFEST.csv
py -m tools.sync_database --check     # 校验副本未漂移(逐字节 + SHA256) / check the copy has not drifted (byte for byte + SHA256)
```

## 真值在哪:副本的纪律 / Where the truth is: discipline of the copy

**本目录是镜像,不是真值。** 真值是 `clbs/database/`:那里记着原始下载 URL、下载日期、
许可、以及每个族"能不能用、为什么"的完整判定。本目录只回答"paper04 到底吃了哪些字节"。

**This directory is a mirror, not the source of truth.** The source of truth is `clbs/database/`: the original download URL, the download date, the license, and the full judgment of whether each family can be used and why are recorded there. This directory only answers "which bytes paper04 actually consumed".

副本最容易烂在"两处不一致而无人知晓"上,所以立三条规矩:

A copy most easily goes bad as "the two places disagree and nobody knows", so three rules:

1. **不手工拷、不手工改。** 一律由 `tools/sync_database.py` 生成; / **Do not copy by hand, do not edit by hand.** Always generate with `tools/sync_database.py`;
2. **`MANIFEST.csv` 记 SHA256 与 clbs 源路径**,`--check` 逐字节比对两处并核对哈希; / **`MANIFEST.csv` records SHA256 and the clbs source path**, and `--check` compares the two byte for byte and checks the hash;
3. **算例不在本目录生成。** `instances/` 里的 JSON 由 `clbs/tools/gen_pub_layouts.py`
   产出,改参数要去改生成器再同步,不要就地编辑——手改一个算例文件等于凭空造了个算例,
   而它看上去仍像是从公开布局来的。 / **Instances are not generated in this directory.** The JSON in `instances/` is produced by `clbs/tools/gen_pub_layouts.py`; to change parameters, change the generator and sync again, do not edit in place — hand-editing an instance file invents an instance that still looks as if it came from a public layout.

`tools/pub_batch.py` 读的是 `instances/` 下的本地副本(缺失时回落到 `clbs/input/`),
所以这份副本不是摆设:它就是论文那批外部布局读数的实际输入。

`tools/pub_batch.py` reads the local copy under `instances/` (falling back to `clbs/input/` when it is missing), so this copy is not decoration: it is the actual input of the paper's external-layout readings.

## 目录 / Directory

```text
database/
  README.md
  MANIFEST.csv                 # 逐文件 role / clbs 源路径 / 字节数 / SHA256 / 用途 / per-file role / clbs source path / byte count / SHA256 / use
  raw/                         # 公开发布件的原样副本,只读 / verbatim copies of the public releases, read-only
    lyu2019/layouts/           #   6 张布局(3–8 机),**已用** / 6 layouts (3–8 machines), **used**
    liu2023/layouts/           #   4 张布局,**已排除**,存档以备复核 / 4 layouts, **excluded**, archived for review
    library/model_data.py      #   决定布局文件语义的解析源码 / parser source that fixes the meaning of the layout files
  instances/                   # 外部布局批次的全部输入(pub_batch 直接读这里) / every input of the external-layout batch (pub_batch reads here)
    S8x{4..8}x4-LyuL{2..6}-*.json   # 5 个外部布局算例 / 5 external-layout instances
    S8x4x4-LD{11,21,22}-*.json      # 3 个同参数自建对照 / 3 same-parameter self-built controls
```

### `raw/lyu2019/layouts/`

van Os 配套工具集(`TUE-EE-ES/TJSP-toolset`)对 Lyu 等(2019)附录 A 布局图的机读编码。
整份文件只有三行、14–44 字节:网格尺寸、仓库与机器所在的网格节点号、被拆掉的边对,
例如 `5x5` / `1 3 10 11 14 17 23 25` / `(8 13) (19 20)`。**不含任何行程时间。**

Machine-readable encoding, in van Os's companion toolset (`TUE-EE-ES/TJSP-toolset`), of the layout figures in Appendix A of Lyu et al. (2019).
Each file is only three lines, 14–44 bytes: grid size, grid-node numbers of the warehouse and the machines, and the pairs of removed edges,
for example `5x5` / `1 3 10 11 14 17 23 25` / `(8 13) (19 20)`. **It contains no travel times.**

已与 Lyu 原文 Figures 10–15 逐节点逐边核对相同(Layout 4 的两处缺边 8–13、19–20 精确对上)。
转录结果登记在 `clbs/algorithm/generator.py` 的 `PUB_LAYOUTS`,由
`clbs/tools/check_pub_layouts.py` 与这些 `.data` 文件逐字段对账,六张布局全部通过。

Checked node by node and edge by edge against Figures 10–15 of Lyu's paper and found identical (Layout 4's two missing edges 8–13 and 19–20 match exactly).
The transcription is registered in `PUB_LAYOUTS` of `clbs/algorithm/generator.py`, and `clbs/tools/check_pub_layouts.py` reconciles it field by field with these `.data` files; all six layouts passed.

`LyuL1`(3 机)已转录但未生成算例:固定 F=0.6 时 F·NM=1.8<2,与 B1 冲突;
为一张布局放宽 F 等于多引入一个变量。

`LyuL1` (3 machines) was transcribed but no instance was generated: at fixed F=0.6, F·NM=1.8<2, which conflicts with B1; relaxing F for one layout adds another variable.

### `raw/library/model_data.py`

**这个文件必须一并归档,不是附赠。** 布局文件那三行的语义——节点序列第一个是装货站、
每条边权重为 1、缺边按双向删除——由这份解析源码确定,而不是由布局文件自述。
没有它,`.data` 就是三行无法解释的数字。边权硬编码在
`dijkstra_graph.addEdge(e[0]-1, e[1]-1, 1)`。

**This file must be archived with the rest; it is not a bonus.** The meaning of those three lines — the first node in the sequence is the loading station, every edge has weight 1, and a missing edge is deleted in both directions — is fixed by this parser source, not stated by the layout file itself. Without it, a `.data` file is three lines of numbers that cannot be interpreted. The edge weight is hardcoded in `dijkstra_graph.addEdge(e[0]-1, e[1]-1, 1)`.

### `raw/liu2023/layouts/`

**未使用**,存档只为让排除理由可复核:其首行带 `d` 后缀,即声明允许对角移动,
而本项目走廊为四邻接。接受对角移动要改的是下层路由层,不是算例。

**Not used.** Archived only so the reason for exclusion can be reviewed: the first line carries a `d` suffix, declaring diagonal moves allowed, while corridors in this project are 4-adjacent. Accepting diagonal moves would change the lower routing layer, not the instance.

### `instances/`

八个算例,**逐参数同口径**(8 工件、4 AGV、每工件 3 工序、H=0.3、F=0.6、
T̄t/T̄p 标定到 1.0),只差布局来源:五个用外部布局,三个用自建哑铃族布局(mid/high/funnel)。
两组必须一起归档——没有对照组,"外部布局的闭包占比离散度更大"这句话就没有可比基线。
论文 `tab:e4` 那两张表用的是 12 工件 / 8 机 / 12 车 / T̄t/T̄p=4.0 的另一套参数,
与本批**不可直接对照**。

Eight instances, **the same parameter protocol** (8 jobs, 4 AGVs, 3 operations per job, H=0.3, F=0.6, T̄t/T̄p calibrated to 1.0), differing only in layout source: five use external layouts, three use self-built dumbbell-family layouts (mid/high/funnel). The two groups must be archived together — without the control group, "external layouts have a larger dispersion of closure ratio" has no comparable baseline. The two tables `tab:e4` in the paper use another parameter set, 12 jobs / 8 machines / 12 vehicles / T̄t/T̄p=4.0, and **cannot be compared directly** with this batch.

## 三处口径:引用本批数字前必须知道 / Three conventions: required before citing this batch

1. **逐段行驶时间不是原始数据,是补的。** Lyu 只为单个示例算例发表过逐段时长(取值并不
   均匀),附录 A 那批布局的从未发表。本批按"所有边等权"补齐——与 van Os 的单步常量
   假设在结构上一致(其模型输入表把单步时长直接写作常量,并非为跑 Lyu 算例临时凑的),
   只是时间单位标度不同,而标度被 T̄t/T̄p 标定吸收。
   **因此本批结果不可与 Lyu 或 van Os 的任何参照值作比较。**
   **Per-segment travel times are not original data; they were filled in.** Lyu published per-segment durations only for a single example instance (the values are not uniform); those of the Appendix A layouts were never published. This batch fills them in as "all edges equal weight" — structurally the same as van Os's constant-step assumption (that model's input table writes the step duration as a constant directly, not something improvised to run a Lyu instance), and only the time-unit scale differs, which the T̄t/T̄p calibration absorbs.
   **Results of this batch therefore cannot be compared with any reference value from Lyu or van Os.**
2. **装卸点做了合并。** 原布局有分离的装货站与卸货站;本项目只有一个装卸点,故取车辆
   起始处的装货站充当该点,卸货站退化为普通网格节点。
   **Load and unload points were merged.** The original layouts have separate loading and unloading stations; this project has only one load/unload point, so the loading station at the vehicle start is used as that point, and the unloading station becomes an ordinary grid node.
3. **工件与工时没有借用,只外部化了路网。** 公开族的平均运输时长只占平均加工时长的百分之
   几,运输在其上几乎不构成争用;一并搬入会让本文的研究对象直接消失。
   **Jobs and processing times were not borrowed; only the road network was externalized.** On the public family, mean transport time is only a few percent of mean processing time, and transport barely creates contention there; bringing it in as well would make the object of this paper disappear.

第 1、3 条是 paper04 局限一节仍然承认的两项,不因有了这份副本而消解:被外部化的只是
**布局出处**,边权与工件数据仍是自建。公开族至今没有发布执行期扰动的基准,这一支换不掉。

Items 1 and 3 are two limitations that the limitations section of paper04 still acknowledges; having this copy does not dissolve them: what was externalized is only the **source of the layout**, and edge weights and job data are still self-built. The public family has still not published a benchmark of execution-time disturbances, so this branch cannot be swapped out.

## 相关位置 / Related locations

| 位置 / location | 内容 / content |
| --- | --- |
| `clbs/database/` | **真值**:原始下载链接、许可、各族可用性判定 / **source of truth**: original download links, license, usability judgment of each family |
| `clbs/algorithm/generator.py` | `PUB_LAYOUTS` 转录表 + `pubgrid` 布局构造 / `PUB_LAYOUTS` transcription table + `pubgrid` layout construction |
| `clbs/tools/gen_pub_layouts.py` | 由布局生成 `instances/` 那五个算例 / generate those five instances in `instances/` from the layouts |
| `clbs/tools/check_pub_layouts.py` | 转录对账(布局三项 + 生成算例的路网) / transcription reconciliation (the three layout items + the road network of the generated instances) |
| `STRC/tools/pub_batch.py` | 本批 E1–E5 的批跑入口 / batch entry for E1–E5 of this batch |
| `STRC/experiments/pub_layouts/` | 本批结果账本(独立于 `experiments/expanded/`) / result ledger of this batch (separate from `experiments/expanded/`) |
