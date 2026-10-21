# 离线研究增量复核与重放

本指南对应2026-10-16 R2–R4当前本机实现，独立于产品研究页/活模型。四个工具不会自动改研究latest、病例或部署模型；所有已有评价22人仍已观察探索对象，不能当独立临床评价。临床IDH极性/预训练重叠、同协议自动/参考全队列及分割空区域/失败未补齐。

## 顺序、输入与范围

| 阶段 | 入口（backend/tools） | 先读冻结协议/验收 | 外部输入与输出 |
|---|---|---|---|
| R2熵权 | compare_entropy_fusion.py | R2_ENTROPY_PROTOCOL/VALIDATION | 已核源CSV、旧98/21/22拆分及可信模型；验证权重/旧概率复核 |
| R2消融 | run_fusion_ablation.py | R2_ABLATION_PROTOCOL/VALIDATION | 自有冻结config、旧受信模型/源SHA；固定敏感性网格/合成缺模态完整分母 |
| R3模拟 | run_federated_full.py | R3_FULL_PROTOCOL/VALIDATION | 自有冻结config、源CSV/角色；三种子双场景六法、训练内预处理/参数/逐轮与22人探索结果 |
| R4统计 | run_research_statistics.py | R4_STATISTICS_PROTOCOL/VALIDATION | 已验R3 config/源/训练索引/参数/预测SHA；患者级共同重抽样、验证温度、个体未校准模型解释 |

R4不需要重新训练R3；只读复用可信R3最终产物。joblib仅限已核SHA的本地受信产物，不能加载陌生模型。旧研究、R3源配置/结果、源CSV、拆分与模型不在源码包中；这些是明确外部前提。患者ID/概率/个体贡献也不随源码候选复制。

## 有限同步运行

先按PACS/本地运行指南核对现有服务、最新交接和运行任务。每个工具由run_development_step.ps1在有限同步工作脚本内执行；先导入use_e_drive.ps1以保证临时/缓存留E盘，重核源/协议/config SHA与角色。不要从本指南直接在锁外训练或生成产物。

三个config工具均接受`--config <自有冻结JSON> --config-sha256 <SHA> --protocol-sha256 <SHA> --output <新E盘nightly输出目录>`；熵权首工具接受`--data-root`、`--research-root`、`--output`及`--protocol-sha256`。实际完整路径/冻结配置只在本机nightly证据中，不假装随包可用。不覆盖既有输出，不为了搬家而改冻结JSON后保留旧SHA；新来源/角色/预算变更必须新版本协议和配置，不能绕过来源保护。

运行解释器本次Python3.10.21、NumPy2.2.6、SciPy1.15.3、sklearn1.7.2；无需GPU训练。源码的解包测试使用现有本机环境，不等于异机安装通过。CPU交付环境/特征worker的版本和用途另见CPU/PyRadiomics指南，不擅自换提取协议。

验收以每轮summary、source/output SHA、逐患者分母、日志和独立数值核查为准，不以文件存在代替通过。R3通信是参数字节估算/共享预处理与验证池，不宣称真实跨院隐私。R4每患者先平均三个种子，不将seed/中心/行当新增人；条件区间不包含重新拟合不确定性；原始0/1、非因果个体系数贡献、分割not_evaluated保持。负结果：熵权未胜基线、FedProx主AUC差为0、12温度条件Brier均变差，不能选最好值覆盖结论。

本机用户只需只读查各验收文档和对应证据，无需为看新统计重复导入192实例、复制650文件、提特征或生成PDF。所有发布/推送/外部数据申请仍不自动执行。
