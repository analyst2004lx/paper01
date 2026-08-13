# 输入数据来源

## ft_trier — Fischertechnik IoT-enriched 事件日志（主数据集）

来源：Trier 大学发布于 Zenodo 的智能工厂事件日志，本体存放在
`../../../database/ft_trier_iot_log/`。本目录只放检测器实际消费的切片，
不重复存原始压缩包。

选它而不是 "Industry 4.0 production line + Digital Twin under cyber attack"
的理由：后者的引用文献集中在网络流量层的入侵检测，缺少工序级的命令-状态
配对与计划工时；本文的三个通道都需要工序粒度的结构信息，而 Trier 日志同时
提供 `lifecycle:state` 三段式生命周期、`planned_operation_time`、
起止位置参数，以及 16 个可导出不变量的 Camunda BPMN 参考模型。

关键规模：清洗版 282 个 case、3,062 个活动实例、15 个资源、21 个 case 级
状态、2,780 次 case 级转移。**不要整包解压**——清洗版展开后 66.6 GB、
含错版 54.2 GB，其中绝大部分是不需要的传感器子日志；全部分析只用
`MainProcess_cleaned.xes`（约 10 MB），从 zip 内流式读取即可。

## hai — HIL-based Augmented ICS 数据集

用途是外部效度：验证跨过程耦合场景下互锁通道仍然成立。注意它是 1 Hz
定周期轮询而非事件驱动，时序通道必须走区间删失分支，否则量化误差会系统性
污染似然。

## sim — 自建仿真场景

补齐公开数据集覆盖不到的攻击类型（尤其是 A7 多设备协同伪造）与参数化
可控性（可调 sigma、可调耦合强度）。仿真结果只用于机理验证与灵敏度分析，
主结论一律以真实日志为准。
