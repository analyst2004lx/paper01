# FJSPT 公开基准数据集(原始发布件)说明

> 本文件是**逐文件的来源留档**;整条公开数据集分支的流程、两个 regime 的报告口径与
> 验收标准见上一级 `database/README.md`,机器可读清单见 `database/MANIFEST.csv`。

## 数据来源

- 来源网站:FAST Manufacturing 项目 "FJSPT Instances" 页面
  <https://fastmanufacturingproject.wordpress.com/2019/04/11/fjspt-instances/>
  另有两份不在这一页上:`bu` 在同站的 **JSPT** 页面
  (<https://fastmanufacturingproject.wordpress.com/2019/04/11/jspt-instances/>),
  `lyu` 在 IEEE Access(见末节)
- 下载日期:2026-07-26(下方文件清单七份);2026-08-17(`bu` 与 `lyu`,见末节)
- 说明:该站数据以 **PDF 表格**形式发布,需经格式转换(规格文档 12.4 第 2 项)
  转为本项目 3.1 节 JSON schema 后放入 `database/json/<dataset_key>/` 方可运行;
  本目录只存放未经加工的原始文件,**只读**——任何加工痕迹都必须落在转换器里,
  不能落在这里。

## 文件清单

| 文件名 | 数据集 | 内容 | 规模 | 在实验方案中的角色(规格 12.1/12.2) | 原始下载链接 |
| --- | --- | --- | --- | --- | --- |
| `homayouni_fontes_2020/homayouni2020_sfjs_mfjs_jobsets.pdf` | Homayouni & Fontes (2020) 小中型 | SFJS1–10 / MFJS1–10 工件-工序-机器加工时间表(源自 Fattahi et al. 2007 FJSP 实例) | 20 实例,2–12 工件、4–48 工序、2–8 机 | **第一层核心对标集**(文献 best-known 最全,用于算 gap) | [fjspt_hf2020.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2020/05/fjspt_hf2020.pdf) |
| `homayouni_fontes_2020/homayouni2020_traveltimes_2to8machines.pdf` | 同上(配套) | 2–8 机各布局的运输时间矩阵(Bilge & Ulusoy 布局 1、Deroussi 8 机布局、TTM2/TTM5、Reddy & Rao 6 机布局等) | 与上面 20 实例配套 | 上一行的必备配套文件,缺它数据不完整 | [2to8machines_layouts.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2020/05/2to8machines_layouts.pdf) |
| `brandimarte_1993/brandimarte1993_mk.pdf` | Homayouni & Fontes (2020) 大型之一 | Brandimarte MK 实例(FJSP 原始数据,自带部分柔性 Ω) | 10 实例,55–240 工序 | 第一层大规模测试;第二层扩展时 Ω 结构直接沿用 | [brandimarte1993-2.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2020/05/brandimarte1993-2.pdf) |
| `chambers_barnes_1996/chambersbarnes1996.pdf` | Homayouni & Fontes (2020) 大型之二 | Chambers & Barnes 实例(FJSP 原始数据) | 21 实例,100–225 工序 | 第一层大规模测试 | [chambersbarnes1996-1.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2020/05/chambersbarnes1996-1.pdf) |
| `homayouni_fontes_2020/homayouni2020_traveltimes_4to18machines.pdf` | 同上(配套) | 4–18 机各布局的运输时间矩阵(随机生成,取值 2–10) | 与两组大实例配套 | 上两行的必备配套文件 | [4to18machines_layouts-1.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2020/05/4to18machines_layouts-1.pdf) |
| `deroussi_norre_2010/deroussi2010_fjsp1to10.pdf` | Deroussi & Norre (2010) | fjsp1–10:Bilge & Ulusoy 十个工件集 × 四布局,机器全部复制一台(每工序 2 台备选、时间相同) | 10 实例 | 可选:"柔性但零异构"对照组 | [fjspt_instances_deroussinorre2010-1.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2019/04/fjspt_instances_deroussinorre2010-1.pdf) |
| `kumar_2011/kumar2011_exf.pdf` | Kumar, Janardhana & Rao (2011) | EXF 系列:Bilge & Ulusoy 实例改造,每工序 3 台备选机;按 t/p 比值分两组(>0.25 与 ≤0.25) | 56 实例(网站未发布工件集 3、6、10,原文有笔误) | 可选:T̄t/T̄p 因子分组现成 | [fjspt_kumar2011.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2020/05/fjspt_kumar2011.pdf) |

## 数据格式要点(转换器实现时参考)

- Brandimarte / Chambers-Barnes 文件的文本格式(网站原文说明):首行为
  `工件数 机器数 [每工序平均可用机器数]`;此后每行一个工件:
  `工序数 k m1 t1 m2 t2 ... `(k 为该工序可用机器数,后接 k 对"机器,加工时间"),
  依次给出各道工序;
- 运输时间矩阵含 LU(装卸站)到各机器及机器间的往返时间;
- 与本项目对标时统一取 `delta_return = 0`(成品不回运,与文献口径一致,见规格 12.2)。

## 2026-08-17 补齐的两份(此前列为"尚未下载")

| 文件名 | 数据集 | 内容 | 可机读 | 原始下载链接 |
| --- | --- | --- | --- | --- |
| `bilge_ulusoy_1995/bilge_ulusoy1995_jobsets_layouts.pdf` | Bilge & Ulusoy (1995) | 5 页数据附录(Fontes 等某文的 Appendix):Table 12 = 10 个工件集的工序/机器/工时,Table 13 = **4 个布局的行驶时间矩阵**,另含 HK 实例数据 | **否**,纯栅格 | [jspt_instances-1.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2023/02/jspt_instances-1.pdf) |
| `lyu_2019/lyu2019_ieee_access_8723142.pdf` | Lyu et al. (2019) | 16 页原文:Table 3 = 工序×机器工时(带"不可加工"), Table 4 = **20×20 邻接矩阵**(逐段时长), Figures 10–15 = 6 张带编号节点的栅格路网, Tables 5/6 = 参照完工时间 | 是(内嵌 Type 1) | IEEE Access 开放获取,[arnumber 8723142](https://ieeexplore.ieee.org/document/8723142/),doi:10.1109/ACCESS.2019.2919109 |

取这两份时各踩到一个坑,记下以免重犯:

- **`bu` 不在 FJSPT 那个页面上**,在同站的 **JSPT** 页面
  (`/2019/04/11/jspt-instances/`);按 FJSPT 页找是找不到的。
- **`bu` 那份不可机读**:`pdffonts` 输出为空(无任何内嵌字体),`pdftotext` 全文只得 5 个字符,
  即整份是栅格图像。故 hf 那条 `pdftotext` 流水线在这里失效,矩阵只能人工转录,
  产物与复核状态见 `../extracted/bu/layouts_4machines.txt` 与 `MANIFEST.csv`。
  需要看内容时用 `pdftoppm -r 200 -png` 渲染。

### 两条随之作废的旧判断

1. ~~"BU 的 4 张布局图可用于第二层还原路网 G"~~ —— **不成立**。四张矩阵**全部不对称**
   (布局 1 的 LU→M1 = 6 而 M1→LU = 12;布局 4 更悬殊,LU→M1 = 4 而 M1→LU = 18),
   而本项目的走廊是无向的、算出的 t\* 必然对称,故原定验收"还原图的 t\* 与原文矩阵逐项相等"
   **无解**。四张倒是**都满足三角不等式**(即确是某张**有向**图的最短路闭包,与"单向导轨"
   的记载吻合),但好处落在有向那一级,本项目用不上。复现:`py -m tools.check_fidelity bu --csv`。
   规格 12.4 第 3 项据此否决,受控争用实验的布局只能自造(规格 12.3)。
2. ~~"`lyu` 是唯一无需语义翻译即可直接跑的公开族"~~ —— **不成立**。它的"双向网络 + 每段同时
   仅一车"确实与假设 A6 一致(这一半是对的),但原文约束 (11) 另有 "a **node** can be occupied
   by only one vehicle at a given time",即**节点容量为 1**,而本项目的节点是零测度通过点。
   故 Lyu 的模型比本文**更紧**,直接跑等于放松了它的节点容量,可能得出在其模型下不可行的解、
   完工时间反而低于其发表值,数字不可比。详见 `../README.md` 第八节。

## 2026-08-18 增补:`tjsp_toolset/`(只取布局拓扑)

`TUE-EE-ES/TJSP-toolset` 是 van Os 硕士论文的配套软件,其中含 Lyu 与 Liu 两族布局的
**机读编码**。取它的用途与上面各族不同:**只借路网拓扑,不借工件数据,也没有边权可借。**

| 路径 | 内容 | 状态 |
| --- | --- | --- |
| `tjsp_toolset/data/benchmarks/lyu2019/layouts/*/N.data` | 6 张布局,各 14–44 字节 | 5 张已用 |
| `tjsp_toolset/data/benchmarks/liu2023/layouts/*/N.data` | 4 张布局 | 全部排除 |
| `tjsp_toolset/library/model_data.py` | 解析源码 | 留档作语义依据 |

布局文件只有三行:网格尺寸(如 `5x5`)、节点号列表、被拆掉的边(如 `(8 13) (19 20)`)。
**节点列表的语义不在文件里自述**,由 `model_data.py` 确定,故该文件必须一并留档:

- 列表顺序为 `[装货站, m1..mk, 卸货站]`——依据是
  `VEHICLE_START_LOCATIONS = MACHINE_LOCATIONS[0]  # Vehicles start at loading station`;
  六张布局的首尾两项都落在网格的对角两角,与此一致。
- 节点号为行主序 1 基编号,换算 `to_node(r,c) = (r-1)*rows + c`;六张都是方阵,故与
  `(r-1)*cols + c` 等价。
- 边为四邻接,**边权硬编码为 1**(`dijkstra_graph.addEdge(e[0]-1, e[1]-1, 1)`),
  缺边**双向删除**(`remove_edges` 两个方向各 remove 一次)。

据此可判定三件事,都写进了论文口径:

1. **边权不是 Lyu 的数据。** 原文只为单个示例算例发表过逐段时长(Table 4,取值 1/2/3,
   并不均匀);附录 A 那批布局的从未发表。工具集的单位边权是 van Os 模型设定的一部分
   ("(Uniform) duration of a single step"),不是 Lyu 的原始数据。故按其生成的算例
   **不可与 Lyu 或 van Os 的参照值比较**。
2. **Liu 那四张不能用。** 首行带 `d` 后缀,即 `IS_DIAGONAL`,允许对角移动
   (`model_data.py` 第 134–139 行),而本项目走廊为四邻接;接受对角移动要改的是下层
   路由层而不是算例,性质与 van Os 的节点容量问题相同。顺带一提,Liu 的布局装货站与
   卸货站同号(如 `4 3 7 9 4`),即单一装卸点,这一点反而与本项目一致。
3. **拓扑本身是忠实的、可对账的。** 转录结果登记在 `algorithm/generator.py` 的
   `PUB_LAYOUTS`,由 `tools/check_pub_layouts.py` 重读原始 `.data` 逐字段比对
   (含"缺边确实是四邻接边"这一项,以防编号口径错位),六张布局与生成算例的路网全部通过。

用法与实测结果见 `../README.md` 的"只借拓扑"一节与
`STRC/experiments/pub_layouts/README.md`。
