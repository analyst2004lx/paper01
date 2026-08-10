# FJSPT 公开基准数据集(原始 PDF)说明

## 数据来源

- 来源网站:FAST Manufacturing 项目 "FJSPT Instances" 页面
  <https://fastmanufacturingproject.wordpress.com/2019/04/11/fjspt-instances/>
- 下载日期:2026-07-26
- 说明:该站数据以 **PDF 表格**形式发布,需经格式转换(规格文档 12.4 第 2 项)
  转为本项目 3.1 节 JSON schema 后放入 `clbs/input/` 方可运行;
  本目录仅存放未经加工的原始文件。

## 文件清单

| 文件名 | 数据集 | 内容 | 规模 | 在实验方案中的角色(规格 12.1/12.2) | 原始下载链接 |
| --- | --- | --- | --- | --- | --- |
| `homayouni2020_sfjs_mfjs_jobsets.pdf` | Homayouni & Fontes (2020) 小中型 | SFJS1–10 / MFJS1–10 工件-工序-机器加工时间表(源自 Fattahi et al. 2007 FJSP 实例) | 20 实例,2–12 工件、4–48 工序、2–8 机 | **第一层核心对标集**(文献 best-known 最全,用于算 gap) | [fjspt_hf2020.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2020/05/fjspt_hf2020.pdf) |
| `homayouni2020_traveltimes_2to8machines.pdf` | 同上(配套) | 2–8 机各布局的运输时间矩阵(Bilge & Ulusoy 布局 1、Deroussi 8 机布局、TTM2/TTM5、Reddy & Rao 6 机布局等) | 与上面 20 实例配套 | 上一行的必备配套文件,缺它数据不完整 | [2to8machines_layouts.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2020/05/2to8machines_layouts.pdf) |
| `brandimarte1993_mk.pdf` | Homayouni & Fontes (2020) 大型之一 | Brandimarte MK 实例(FJSP 原始数据,自带部分柔性 Ω) | 10 实例,55–240 工序 | 第一层大规模测试;第二层扩展时 Ω 结构直接沿用 | [brandimarte1993-2.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2020/05/brandimarte1993-2.pdf) |
| `chambersbarnes1996.pdf` | Homayouni & Fontes (2020) 大型之二 | Chambers & Barnes 实例(FJSP 原始数据) | 21 实例,100–225 工序 | 第一层大规模测试 | [chambersbarnes1996-1.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2020/05/chambersbarnes1996-1.pdf) |
| `homayouni2020_traveltimes_4to18machines.pdf` | 同上(配套) | 4–18 机各布局的运输时间矩阵(随机生成,取值 2–10) | 与两组大实例配套 | 上两行的必备配套文件 | [4to18machines_layouts-1.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2020/05/4to18machines_layouts-1.pdf) |
| `deroussi2010_fjsp1to10.pdf` | Deroussi & Norre (2010) | fjsp1–10:Bilge & Ulusoy 十个工件集 × 四布局,机器全部复制一台(每工序 2 台备选、时间相同) | 10 实例 | 可选:"柔性但零异构"对照组 | [fjspt_instances_deroussinorre2010-1.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2019/04/fjspt_instances_deroussinorre2010-1.pdf) |
| `kumar2011_exf.pdf` | Kumar, Janardhana & Rao (2011) | EXF 系列:Bilge & Ulusoy 实例改造,每工序 3 台备选机;按 t/p 比值分两组(>0.25 与 ≤0.25) | 56 实例(网站未发布工件集 3、6、10,原文有笔误) | 可选:T̄t/T̄p 因子分组现成 | [fjspt_kumar2011.pdf](https://fastmanufacturingproject.wordpress.com/wp-content/uploads/2020/05/fjspt_kumar2011.pdf) |

## 数据格式要点(转换器实现时参考)

- Brandimarte / Chambers-Barnes 文件的文本格式(网站原文说明):首行为
  `工件数 机器数 [每工序平均可用机器数]`;此后每行一个工件:
  `工序数 k m1 t1 m2 t2 ... `(k 为该工序可用机器数,后接 k 对"机器,加工时间"),
  依次给出各道工序;
- 运输时间矩阵含 LU(装卸站)到各机器及机器间的往返时间;
- 与本项目对标时统一取 `delta_return = 0`(成品不回运,与文献口径一致,见规格 12.2)。

## 尚未下载

- **Bilge & Ulusoy (1995) 原始 JSPT 实例与 4 个导轨布局图**:在同站
  [JSPT Library 页面](https://fastmanufacturingproject.wordpress.com/2019/04/11/jspt-instances/),
  第二层扩展实验(还原有向路网 G,规格 12.3a)时再取。
