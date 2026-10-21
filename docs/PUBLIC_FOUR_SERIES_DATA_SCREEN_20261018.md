# 公开四序列MRI数据筛选与几何验收记录（2026-10-18）

## 筛选结论

本轮使用NCI Imaging Data Commons（IDC）公开的v3只读SQL元数据接口筛同一PatientID、StudyInstanceUID中的T1非增强、T1增强、T2和FLAIR候选，并通过公开S3桶只下载两个小病例核对DICOM原始几何。IDC按患者/检查/序列组织公开DICOM，并支持REST/SQL查询和S3下载。[IDC API concepts](https://github.com/ImagingDataCommons/IDC-Docs/blob/prod/api/idc-api-concepts.md) [IDC query documentation](https://github.com/ImagingDataCommons/IDC-Docs/blob/prod/api/querying-with-sql.md)

**截至本记录，没有一个已核实病例满足BrainFusion当前“4序列dimensions与affine完全相同”的输入约束。** 两个ACRIN病例均留在`E:/BrainFusion-Data/PACS-candidates/`，未导入生产/演示Orthanc，未创建AI任务，也不构成真实页面验收通过。

## UPENN-GBM

TCIA官方资料确认UPENN-GBM有630位受试者、原始DICOM约139.4 GB、CC BY 4.0，并包含T1、增强T1、T2及T2-FLAIR模态。[TCIA UPENN-GBM](https://www.cancerimagingarchive.net/collection/upenn-gbm/) [队列论文](https://doi.org/10.1038/s41597-022-01560-7)

通过IDC对原始MR（排除派生结果）分组后，本次筛选得到3,680个MR Series、3,301个Study UID；每个Study最多两条MR Series，按四角色描述匹配得到0例。因此它当前不能满足“一次检查内四个原始DICOM序列”的要求。其已公开的四序列NIfTI衍生数据经预处理/配准，不能冒充原始PACS/DICOM验收数据。本次没有下载或导入UPENN-GBM。

## ReMIND

IDC索引确认ReMIND-013、ReMIND-110等同检查四序列候选，[TCIA官方集合页](https://www.cancerimagingarchive.net/collection/remind/)列明数据集DOI `10.7937/3RAG-D070`与CC BY 4.0许可；ReMIND-013含3D轴位MP2RAGE、增强T1、T2 SPACE和矢状位T2 FLAIR。对ReMIND-013首个候选角色序列下载了176张原始DICOM作字段筛查；全部缺少BurnedInAnnotation，未作像素人工审核，因此停止下载其它序列。该病例未生成NIfTI、未导入PACS、未激活或推理。逐实例SHA与筛查结果：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/remind013_dicom_screen_retry1/ReMIND-013-pixel-privacy-screen.json`。

ReMIND-110也有IDC索引确认的同Study四序列候选。为避免重复下载像素，使用IDC只读DICOMweb/WADO-RS系列元数据接口检查其最小序列2D_AX_T2_FLAIR：33/33实例的BurnedInAnnotation（0028,0301）均缺失，因此在该序列处停止，未请求其它序列或PixelData、未导入、未转换。该字段缺失不等于确认存在或不存在烧录文字；ReMIND-110仍需人工像素审核。脱敏汇总见E:/BrainFusion-Runtime/results/nightly/2026-10-18/remind110_metadata_screen/remind110-t2flair-metadata-screen.json。[IDC官方代理说明](https://learn.canceridc.dev/portal/proxy-policy)指出该DICOMweb接口只读且设有按IP/全局配额；[IDC官方教程](https://github.com/ImagingDataCommons/IDC-Tutorials)说明可通过DICOMweb访问影像元数据。因此本次仅请求所需元数据，未请求像素。

## ACRIN技术流程候选（非胶质瘤队列）

TCIA将ACRIN-NSCLC-FDG-PET列为人类非小细胞肺癌研究的多模态DICOM集合，许可为CC BY 3.0，引用DOI `10.7937/tcia.2019.30ilqfcl`。[TCIA ACRIN-NSCLC-FDG-PET](https://www.cancerimagingarchive.net/collection/acrin-nsclc-fdg-pet/)

为判断实际DICOM网格，下载并逐张核验了两位去标识病例中同一Study的四条脑MRI序列。每例均有T1、增强T1、T2、FLAIR四序列；它们只能作为PACS/影像转换工程候选，不能用于胶质瘤模型效果或临床效能结论。

- `ACRIN-NSCLC-FDG-PET-099`：112个DICOM实例，共41,190,270字节。四序列方向、层数、层间步长、FrameOfReferenceUID相同；但Rows/Columns分别为320×288、256×224、512×440、640×552，像素间距不同，起始位置亦不同。因此严格同网格检查失败。
- `ACRIN-NSCLC-FDG-PET-134`：104个DICOM实例，共24,376,516字节。四序列方向、首末层位置、层间步长及FrameOfReferenceUID相同；FLAIR、T1、增强T1为256×256且像素间距0.859375 mm，T2为512×512且像素间距0.4296875 mm。空间视野/采样中心一致，但矩阵与像素间距不同，严格同网格检查仍失败。若未来允许显式重采样到参考序列网格，该病例可作为工程验收候选；不得把它称为胶质瘤验证病例。

原始文件、来源许可和逐文件SHA-256/几何清单分别保存在：

- `E:/BrainFusion-Data/PACS-candidates/ACRIN-NSCLC-FDG-PET-099/SOURCE_AND_LICENSE.json`
- `E:/BrainFusion-Data/PACS-candidates/ACRIN-NSCLC-FDG-PET-134/SOURCE_AND_LICENSE.json`

下载/核验脚本和IDC查询结果在`E:/BrainFusion-Runtime/automation/`及`E:/BrainFusion-Runtime/results/nightly/2026-10-18/public_dataset_screen/`。所有文件仍是隔离候选材料。

## 替代公开集合初筛（2026-10-18）

- **Brain-Tumor-Progression（受限访问候选）**：TCIA官方页面说明该集合有20名受试者、40次检查，包含原始DICOM的平扫/增强T1、T2、FLAIR等序列，所有序列已配准到增强T1；但页面同时明确因部分影像可能重建人脸，下载前必须签署并提交TCIA Restricted License Agreement。故它不是可直接公开下载的替代数据。即使获得协议访问，也仍需确认许可覆盖本项目用途、具体Study/Series、像素隐私、序列角色和当前转换契约；数据DOI为10.7937/K9/TCIA.2018.15quzvnb。当前未取得协议、UID或数据，也未下载/导入。[TCIA官方集合与访问条款](https://wiki.cancerimagingarchive.net/display/Public/Brain-Tumor-Progression)
- **TCGA-LGG-Mask / TCGA-LGG（需受限访问，不是快速替代）**：TCIA说明108名患者中81名有覆盖T1W、T2W、增强T1和T2-FLAIR的四序列ROI；但对应原始DICOM被标为TCIA Restricted，因影像可能重建人脸，须先签署访问协议。掩膜/临床表格的许可不能替代影像DICOM的许可；即使申请获批，也要另核病例级同Study、几何与像素隐私。数据集DOI为10.7937/K9/TCIA.2017.BD7SGWCA。[TCIA官方数据页](https://wiki.cancerimagingarchive.net/pages/viewpage.action?pageId=24282890)
- **UCSF-PDGM（研究候选，不是DICOM工程候选）**：官方资料包含人类弥漫性胶质瘤、多模态MRI及IDH等临床标签，但公开下载为去颅骨、预处理的NIfTI，TCIA说明不提供原始DICOM。因此可在另行核对项目范围、标签和许可后评估SCI研究用途，不能用于证明本系统的PACS/DICOM链路。[TCIA UCSF-PDGM详情](https://www.cancerimagingarchive.net/collection/ucsf-pdgm/)
- **ICDC-Glioma（排除）**：TCIA页面将该集合列作犬类胶质瘤，不符合本项目的人类病例目标。[TCIA数据浏览页](https://www.cancerimagingarchive.net/browse-data/)

这些是集合层级的候选筛选，不是具体病例核验，也不改变ReMIND-013人工烧录文字复核仍待确认的状态。Brain-Tumor-Progression与TCGA-LGG原始DICOM均需先完成TCIA受限访问协议流程；取得授权后，才可继续核对对应版本/许可、具体Study/Series、像素隐私、序列角色与几何。不得因集合描述提到四序列或其已配准，就推断某一Study已满足本项目输入契约。

## 2026-10-18 公开替代来源复查

再次检查TCIA官方集合页后，没有发现能直接替代当前候选、同时满足“人类胶质瘤、同检查四序列原始DICOM、可公开使用、可通过本项目隐私门槛”的新来源：

- **UTSW-Glioma**是较新的大规模人类胶质瘤数据，官方页面提供增强T1、非增强T1、T2、FLAIR和临床分子标签，但公开影像格式为预处理NIfTI；可作为后续IDH/疗效研究候选，不能用于原始PACS/DICOM验收。[TCIA UTSW-Glioma](https://www.cancerimagingarchive.net/collection/utsw-glioma/)
- **ICDC-Glioma**提供CC BY 4.0许可的DICOM，但官方明确其对象为犬类胶质瘤；不用于本项目的人体病例或临床系统验收。[TCIA ICDC-Glioma](https://www.cancerimagingarchive.net/collection/icdc-glioma/)
- **REMBRANDT**包含人类脑胶质瘤多序列DICOM，但TCIA标注为受限访问，并要求签署Restricted License Agreement；在许可获批前不是可立即使用的替代来源。[TCIA REMBRANDT](https://www.cancerimagingarchive.net/collection/rembrandt/) [TCIA受限数据说明](https://wiki.cancerimagingarchive.net/display/Public/REMBRANDT)

因此数据方向仍是既有ReMIND公开病例待像素隐私复核，或先做本机纯工程链路验收。字段缺失不能证明影像里有或没有身份文字；在用户无法确认的情况下，不下载额外大批像素、不导入、不转换，也不把NIfTI衍生物说成真实原始DICOM验收。若需要推进真实像素路径，需由具备权限的导师/影像人员独立查看并留下病例、序列、切片范围和结论记录；这一人工检查不能由自动元数据筛选替代。

## 2026-10-18 ReMIND候选的有限元数据复筛

为找出可优先提交人工像素审核的公开候选，在IDC同检查四序列描述筛选结果中对7个ReMIND Study仅查询T2-FLAIR序列的只读DICOMweb元数据，检查BurnedInAnnotation（0028,0301），不请求PixelData、不保存原始元数据。7条候选FLAIR序列共534个实例，7/7序列中的字段均缺失：ReMIND-013（176）、023（32）、044（33）、066（30）、069（200）、110（33）、114（30）。ReMIND集合索引显示CC BY 4.0；但字段缺失不等于影像里有或没有身份文字，也不构成隐私通过。该筛查仅覆盖这7条描述匹配的候选FLAIR，不代表全面筛查所有公开影像或其余三个序列。脱敏计数及公开UID留存于`E:/BrainFusion-Runtime/results/nightly/2026-10-18/remind_followup_metadata_screen/aggregate.json`。用户目前答复为“暂时无法确认”，候选继续隔离。

## 对后续工程的影响

已选择并实现**显式、可追踪的重采样步骤**：参考T1增强、1 mm等向网格、按患者物理坐标identity mapping、线性插值；只在网页显式勾选后使用，默认严格同网格校验不变。方案和边界见[重采样工程验收记录](P3_DICOM_RESAMPLING_ENGINEERING_VALIDATION_20261018.md)。

ACRIN-134通过同一Study/Frame及覆盖几何规划，计划输出220×220×163；但源DICOM未声明`BurnedInAnnotation=NO`，真实像素转换被既有审核门槛拒绝，未输出NIfTI或导入活跃PACS。因此目前只能说显式方案和合成完整性路径通过测试，**不能说真实DICOM转换/病例页面链路已验收**。ACRIN仍仅为非胶质瘤队列的工程候选，且6.5 mm层间距插值到1 mm不恢复原采集细节，不支持模型效能验证。

## 可复核证据

- IDC UPENN分组及候选查询：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/public_dataset_screen/`
- ReMIND系列元数据：`remind013-series-detail.json`、`remind110-series-detail.json`
- ACRIN序列元数据：`acrin-axial-candidate-series.json`
- ACRIN逐实例几何、文件计数、体积和SHA-256清单：以上病例目录中的`SOURCE_AND_LICENSE.json`
- IDC公开查询官方说明：[IDC API concepts](https://github.com/ImagingDataCommons/IDC-Docs/blob/prod/api/idc-api-concepts.md)







