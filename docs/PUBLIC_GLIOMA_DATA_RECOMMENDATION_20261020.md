# 公开胶质瘤数据候选评估（2026-10-20）

## 推荐分工

**首选研究候选：TCIA UTSW-Glioma。** TCIA 官方页面列出 625 名受试者、22.9 GB、CC BY 4.0；每例包含术前 T1w、增强后 T1w、T2w、T2-FLAIR，并提供肿瘤分割及 IDH、1p/19q、MGMT 等分子/临床信息。公开版本已预处理并以 NIfTI 发布，TCIA 明确表示不提供原始 DICOM。因此它适合现有 NIfTI/研究链路和 IDH/MGMT 分类实验，不适合作为 Orthanc 原始 DICOM 导入验收。下载需要 Aspera。已仅下载官方临床元数据 TSV（100,025 bytes；SHA-256 f7ff889fa7d197b2f589695d3e7ea8a2d1d198c4f9c0044fc71898a08aa24ed0），未下载或读取影像像素，也未跑本项目推理。625 行中 625个Subject ID唯一无重复；年龄/性别625/625齐全、肿瘤分级618/625有值。IDH有622个明确标签（446 wild type、176 mutated、3 NA）；MGMT有281个明确标签（167 unmethylated、114 methylated、344 NA）。IDH 适合作为优先终点候选；MGMT 仅可在有标签子集上另行设计，不能按全队列完整终点使用。

**PACS 候选：TCIA UPENN-GBM。** 官方页面列出 630 名受试者、3,301 个检查、3,680 个系列，DICOM 139.4 GB，CC BY 4.0，并提供分子/临床数据。官方特别说明其 DICOM 与配套 NIfTI 预处理影像刻意不对齐。此前只读 NBIA 系列目录筛查没有通过本项目“四个角色在同一 Study、输入几何符合约束”的匹配门槛；需要确认实际扫描协议/Study metadata，未确认前不能按同一病例四序列接入，也不能跨格式配对。

两者不能直接拼作一个队列：患者身份映射、终点定义、处理流水线、标签缺失和跨队列泄漏需分别审计。月底前先用 UTSW 完成可复现的队列检查及模型适配可行性；PACS 演示继续使用独立且授权清楚的工程数据，待序列匹配和隐私门槛通过再导入。

## 下载/使用前门槛

1. 保存 TCIA 页面版本、DOI、CC BY 4.0 属性和数据引用；遵守 TCIA Data Usage Policy，不尝试识别或联系参与者。
2. 先核对标签含义、IDH 阳性/阴性/未知分布、病例与影像对应、四序列命名、缺失及分割映射，再决定全量下载。UTSW 约 22.9 GB；UPENN DICOM 约 139.4 GB。
3. 核验有限病例 shape/affine/spacing、方向、共同网格、mask 标签和系统模型输入契约；不得假设 BraTS 模型可直接兼容，任何重采样须记录并审计。
4. 患者级拆分；标准化/选择/调参限训练验证集，封存测试集。研究输出不称诊断工具。
5. UPENN 还需 Study UID 级序列匹配、DICOM 隐私/烧录文字和用途核验。没有人工影像复核时，应披露未复核并限制像素路径。
6. 数据引用 DOI：UTSW 10.7937/DFAE-1B86；UPENN 10.7937/TCIA.709X-DN49。

## 本轮结论

UTSW-Glioma 是贴近“四序列 IDH 研究”的候选，不是已导入/训练/验证的数据集。UPENN-GBM 是公开 DICOM 备选，但同检查四序列门槛未过且下载更大。ACRIN-134 仍仅限工程验证。当前没有公开数据真实四序列 PACS+ML 闭环证据。

## 官方来源

- [TCIA UTSW-Glioma collection](https://www.cancerimagingarchive.net/collection/utsw-glioma/)
- [TCIA UPENN-GBM collection](https://www.cancerimagingarchive.net/collection/upenn-gbm/)
- [TCIA Data Usage Policies and Restrictions](https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/)
- [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)
## 2026-10-20 补充：在线公开DICOM候选

优先可继续考察 TCIA UPENN-GBM。TCIA当前集合页将其标为公开、CC BY 4.0，DICOM影像约139.4 GB，630名受试者、3,301个检查、3,680个序列，并有单独发布的NIfTI及临床表；集合DOI为10.7937/TCIA.709X-DN49。研究论文描述了该队列共配准结构MRI的T1、T1-Gd、T2、T2-FLAIR，但这不等于每个原始DICOM Study都能直接通过本系统的四序列同检查/共同空间门槛。

推荐用途分开处理：先用可选的少量受试者/series manifest 验证下载、DICOM归档和元数据组织；取得许可并由有权限人员完成烧录文字、序列身份和共同空间人工复核之后，才考虑开放像素读取与转换。官方目录目前提示DICOM下载需使用TCIA Data Retriever，且约139.4 GB；不要直接全量下载。下载器会附带数据使用政策/许可文件，必须按该集合当时显示的条款及TCIA政策执行并保存引用。

TCIA说明其去标识化遵循DICOM隐私配置和额外清理措施，但去标识化不能作为每幅图像没有烧录文字的人工证明。本项目仍遵循“第二位获准影像复核者逐张检查烧录隐私；核对许可、同Study四序列角色及共同空间”的门槛。没有该复核时，仅可记录候选和下载许可元数据，不读像素、不导入、不启用DICOM AI桥。

下载流程以TCIA当前页面为准：从影像门户针对少量目标受试者/series生成manifest，再用TCIA Data Retriever选择E盘隔离数据目录下载；保存manifest、下载器随附的LICENSE/使用政策、数据引用和校验记录。TCIA在2026年的基础设施迁移中正逐步用Data Retriever/NCI Imaging Data Commons替换旧NBIA流程，因此不要依赖旧教程截图。 另外，TCIA通用政策对脑/头颈影像有额外访问和许可说明，而UPENN-GBM集合页当前显示CC BY 4.0；两者必须结合本次manifest和下载随附LICENSE核对。若实际许可与页面或通用说明不一致，先暂停下载/使用并向TCIA确认，不自行推断。

官方依据： [UPENN-GBM集合页](https://www.cancerimagingarchive.net/collection/upenn-gbm/)；[TCIA在线下载说明](https://wiki.cancerimagingarchive.net/display/NBIA/Downloading%2BTCIA%2BImages)；[TCIA数据使用政策](https://wiki.cancerimagingarchive.net/display/Public/Data%2BUsage%2BPolicies%2Band%2BRestrictions)；[TCIA去标识说明](https://www.cancerimagingarchive.net/submission-and-de-identification-overview/)；[UPENN-GBM队列研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC9338035/)。
