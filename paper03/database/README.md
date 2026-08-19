# paper03 数据集取用说明

## 一、本目录有什么

```text
database/
  README.md                        # 本文件
  ft_trier_iot_log/
    MainProcess_cleaned.xes        # 主日志(清洗版),11.4 MB
    bpmn-models/WF_*.bpmn          # 16 个 Camunda BPMN 参考模型
    README.md                      # 数据集原始说明(作者提供,含引用要求)
    LICENSE.txt                    # CC BY 4.0
```

从 `../../paper02/database/ft_trier_iot_log/` 拷入，**未做任何修改**。
paper02 的一次性探针脚本（`extract_vocab.py`、`inspect_bpmn.py`、
`derive_invariants*.py`、`probe_*.py`）没有拷贝：它们是 paper02 的取证过程，
留在原处即可；实现 `tessera` 时直接读取那些脚本作为参考，不复制。

`paper02/database/hai/`（HAI ICS 数据集）也没有拷贝。它是单一连续过程的
时序数据，没有多智能体任务交接语义，无法激活耦合互证机制。

## 二、为什么用这份数据

Trier 大学 Fischertechnik 教学工厂的 IoT-enriched 事件日志。选它的理由分两层。

**结构上它罕见地契合本文的机制。** 产线是两条独立产线**经工件交换互联**——
工件交换即物理交接，耦合关系本身就在数据里。每个 BPMN serviceTask 的
Camunda HTTP connector URL 形如
`/vgr/pick_up_and_transport?resource=vgr_1&start=dm_2_sink_pos&end=ov_1_pos`，
设备、操作、起点、终点四元组直接可读，位置在活动间首尾相接，跨设备交接也在
其中（VGR_2 送到 `dm_2_sink_pos`，VGR_1 从该位置取走）。**互证超图的边可以
自动导出，不需要手工编造再自证**——这直接消解了"你的领域知识是不是为了
好看而设计的"这一质疑。此外活动带 `assigned → inProgress → success/failure`
三态生命周期，可与命令账本配对；随数据发布 16 个 BPMN，为任务图提供权威来源。

**方法论上它换来一个强实验。** paper02 用的是同一份日志，因此可以在
**同数据、同注入协议、同划分**下做对照：paper02 的方法在 A4（掌握模型知识的
状态模仿）上单消息检出率只有 0.12，而这正是耦合互证的靶心。这堵住了
"换了数据集才显得更好"的质疑。

## 三、它撑不起什么（必须靠别的手段）

1. **没有攻击者。** 攻击须自行注入（P1–P4，见 `../tessera/README.md` 第四节）。
   自注入在本领域是标准做法，且对"任务状态伪造"这类攻击是唯一选择——没有
   公开数据集包含它，这本身正是本文的立论。
2. **没有通信层。** 无消息级带宽、无无线丢包与时延，故带宽与检测时延的主张
   不能来自这份数据，须在信道模型下用网络仿真补（3GPP TR 38.901 Indoor
   Factory，ns-3 或 OMNeT++）。
3. **没有 AGV。** 本产线是传送带与真空吸盘搬运，没有自由行驶的 AGV，
   **因此 ISO 3691-4 的防护场计算在这份数据上落不了地**。安全裕度定理应
   重新锚定在通用的 FTTI/FHI 时间预算（ISO 26262 / IEC 61508），把 ISO 3691-4
   降级为仿真场景中的一个示例。这与"小论文不特别强调柔性车间领域"的定位一致。
4. **规模偏小。** 282 个 case、3,062 个活动、十余台设备，做长任务链的串谋界
   实验不够。串谋界的规模化评估改用 FJSP 标准算例（Brandimarte Mk01–Mk15、
   Hurink edata/rdata/vdata、Kacem、Fattahi、Dauzère-Pérès & Paulli），
   放在 `../tessera/input/fjsp/`。
5. **子日志（含 IoT 传感器数据）没有拷贝，也尚未取用。** 主日志只有任务级
   事件；对手方的**本地传感证据**（光电门、吸盘绝对方位传感器）在子过程 XES
   文件里，通过事件的 `SubProcessID` 属性关联，解压后体积很大（作者报告
   1.36 亿传感器数据点）。当前设计只做**任务级互证**，够用；若要把互证下沉到
   传感层、或用真实力/位信号标定对手方本地事件检测器的漏检与误报率，
   需要另行下载子日志的一个子集。**这是一个已知的待决项，不是遗漏。**

## 四、引用要求（CC BY 4.0，必须署名）

数据集：

> L. Malburg, J. Grüger, R. Bergmann. *Dataset: An IoT-Enriched Event Log for
> Process Mining in Smart Factories* (2022).
> <https://doi.org/10.6084/m9.figshare.20130794>

对应论文与本体：

> L. Malburg, J. Grüger, R. Bergmann. *An IoT-Enriched Event Log for Process
> Mining in Smart Factories.* arXiv:2209.02702 (2022).

> P. Klein, L. Malburg, R. Bergmann. *FTOnto: A Domain Ontology for a
> Fischertechnik Factory by Reusing Existing Ontologies.* 21st LWDA,
> CEUR-WS vol. 2454, pp. 253–264 (2019).

XES 扩展（如用到传感器数据）：

> J. Grüger et al. *SensorStream: An XES Extension for Enriching Event Logs
> with IoT-Sensor Data.* arXiv:2206.11392 (2022).

> J. Mangler et al. *DataStream XES Extension: Embedding IoT Sensor Data into
> Extensible Event Stream Logs.* Future Internet 15(3):109 (2023).
> <https://doi.org/10.3390/fi15030109>

详见 `ft_trier_iot_log/README.md`（作者原文）。
