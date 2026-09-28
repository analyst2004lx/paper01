# 输入数据来源 / Input data sources

## ft_trier — Fischertechnik IoT-enriched 事件日志（主数据集） / ft_trier — Fischertechnik IoT-enriched event log (main dataset)

来源：Trier 大学发布于 Zenodo 的智能工厂事件日志，本体存放在
`../../../database/ft_trier_iot_log/`。本目录只放检测器实际消费的切片，
不重复存原始压缩包。

Source: the smart-factory event log published by the University of Trier on Zenodo. The original lives in `../../../database/ft_trier_iot_log/`. This directory keeps only the slice the detector actually consumes, and does not store the original archive again.

选它而不是 "Industry 4.0 production line + Digital Twin under cyber attack"
的理由：后者的引用文献集中在网络流量层的入侵检测，缺少工序级的命令-状态
配对与计划工时；本文的三个通道都需要工序粒度的结构信息，而 Trier 日志同时
提供 `lifecycle:state` 三段式生命周期、`planned_operation_time`、
起止位置参数，以及 16 个可导出不变量的 Camunda BPMN 参考模型。

Why this set rather than "Industry 4.0 production line + Digital Twin under cyber attack": that literature concentrates on intrusion detection at the network-traffic layer and lacks operation-level command-state pairing and planned sojourn times. All three channels here need structural information at operation granularity, and the Trier log supplies a three-stage `lifecycle:state`, `planned_operation_time`, start and end position parameters, and 16 Camunda BPMN reference models from which invariants can be exported.

关键规模：清洗版 282 个 case、3,062 个活动实例、15 个资源、21 个 case 级
状态、2,780 次 case 级转移。**不要整包解压**——清洗版展开后 66.6 GB、
含错版 54.2 GB，其中绝大部分是不需要的传感器子日志；全部分析只用
`MainProcess_cleaned.xes`（约 10 MB），从 zip 内流式读取即可。

Key scale: the cleaned edition has 282 cases, 3,062 activity instances, 15 resources, 21 case-level states, and 2,780 case-level transitions. **Do not unpack the whole archive** — the cleaned edition expands to 66.6 GB and the corrupted edition to 54.2 GB, most of it unused sensor sub-logs. All analysis uses only `MainProcess_cleaned.xes` (about 10 MB), streamed from inside the zip.

## hai — HIL-based Augmented ICS 数据集 / hai — HIL-based Augmented ICS dataset

数据字典结论：1 Hz 过程/执行器标签，无 case、无调度命令账本、无工序名。
控制回路设定值不是派工。区间删失分支可以吃量化误差，但不能把 HAI 改写成
调度层评测；互锁通道已从生产配置剔除，也不再拿 HAI 给它找支撑。
CSV 未摄入；`ingest.hai_dictionary_verdict()` 给出判定。

Data-dictionary conclusion: 1 Hz process/actuator tags, with no case, no scheduling command ledger, and no operation names. A control-loop setpoint is not a dispatch. The interval-censoring branch can absorb quantization error, but HAI must not be rewritten as a scheduling-layer evaluation. The interlock channel has already been removed from the production configuration, and HAI is no longer used to support it. The CSV is not ingested; `ingest.hai_dictionary_verdict()` states the verdict.

## sim — 自建仿真场景 / sim — hand-built simulation scenarios

`algorithm/plant.py` 再生 A/B/C 三条产线，只用于 E6 参数迁移与机理扫描。
A7 不实现即不报告。主结论一律以 Trier 真实日志为准。

`algorithm/plant.py` regenerates the three lines A/B/C, used only for the E6 parameter transfer and mechanism scans. A7 is not implemented and therefore not reported. Main conclusions always rest on the real Trier log.
