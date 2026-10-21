# R1训练侧10例同协议小批协议 v1

冻结于2026-10-16T06:36:21.166064+00:00，run_id 20261016T143332_r1cohort。此协议在新增MRI下载、推理与特征结果查看前冻结；用于同协议数据工程短测/失败分母，不是独立模型评价或充分统计样本。原98训练/21验证/22已观察拆分不变，五工程病例4/13/16/17/19排除，不从验证/评价集选图。

选择规则：既有影像归档清单与完整本地参考mask ZIP、旧训练名单交集，检查0四序列各唯一+参考mask唯一，按数值ID最小前10，不按标签/体积/Dice/概率挑选：25, 26, 29, 31, 44, 45, 63, 66, 67, 76。本批全是训练侧，原始idh1/2极性未知仍不作临床解释，MONAI预训练患者重叠未知。完整队列重拟合、融合比较与独立评价需后续协议，不因本10例成功就标R1/R4整项完成。

数据来源[WAW-GliomAI v3官方记录](https://zenodo.org/records/22205631)，既有本地版本id22205631/CC-BY-4.0，官方metadata刷新一次仅核新数据版本/大小/checksum，变更即拒绝。完整预处理影像ZIP 3164137716字节/md5:0d24a3a2c76bc6fa9b5b6468679676b1；本批估计选中压缩MRI 204326563字节/提取MRI 206009450字节，不下载全ZIP。范围缓存1MiB块、精确206/Content-Range、断点.partial追加和块SHA，选中成员ZIP CRC32与落地SHA；不能称验证全ZIP MD5。参考mask复用本地1.9MB完整ZIP，publisher MD5已核，源NIfTI/旧五例不变；不执行归档内脚本。

顺序：先准备10例的40 MRI+10参考mask，逐例检查原始shape/affine/spacing/方向、有限像素/非恒值/合法mask与区域计数。不满足现有1mm轴对齐四序列模型契约的病例明确失败且保留10人计划分母；不替换候选补足成功数，不配准/重采样，不用IDH标签要求阻塞MRI准备。

准备通过后先对第一人短测固定MONAI BraTS SegResNet模型，checkpoint SHA 860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae，既有LPS/非零归一化/ROI128x128x96，batch=1、GPU上限6000MB、无并发GPU任务；原始空间保存新mask，原/参考mask只读。只进行推理、不训练分割器，OOM仅依现有CPU保守回退记录，不扩大批量。记录PID/UTC启动/config/log、磁盘、单步耗时/显存后再逐例同配置执行。未经短测不扩10人推理。

参考/自动掩膜两路均调用同一已验worker/固定特征协议 waw_selected20_minmax_v1 和旧模型选定20项（具体名称/config哈希冻结）；整MRI minmax[0,1] float64、binWidth0.02、Original、不提取协议外影像变换、不重采样。该缩放是五参考复现推断而非发布者明确协议；本批固定，不据结果调参。worker Python3.11候选与旧兼容gate保持。区域1/2/3空区域selected feature为null，分母不丢失；掩膜映射WAW1核心坏死/2FLAIR/3增强，模型TC/WT/ET规则沿用原实现，reference不是推理输入。

分割对照使用既有WT/TC/ET：双方空Dice1/HD95null，一方空Dice0/HD95null，另列empty_rule计数，不把空值删除后只报成功平均。保留每位成功/失败/原因、区域体素/体积、Dice/HD95、特征有限/缺失/漂移及全部10人分母；不把这些训练侧值当独立临床准确率。个别程序失败可新attempt续接，但不得无痕覆盖或替换患者。现有产品DB/报告/研究latest/活模型不切换。

本轮所有实际写入/测试/下载/推理使用有限同步run_development_step包装器；输出留E盘：E:/BrainFusion-Data/WAW-GliomAI-v3/training-pilot-20261016-v1，配置和日志在本轮nightly证据目录。数据与模型不提交/推送。完成标准：10人输入来源/空间与可恢复小批，第一例真实推理/两路同协议短测，随后才推进剩余；不重复旧五例或只增加恒false预检。
