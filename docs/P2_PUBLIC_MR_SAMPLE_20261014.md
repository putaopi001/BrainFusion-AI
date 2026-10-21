# 有限公开MR样本实际取得与支持边界

窗口：2026-10-14 18:08起，北京时间；run_id `20261014T180828_p2sample`。证据根：`E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T180828_p2sample/`。本轮没有运行归档、修改病例库或启用AI。

## 来源和用途

从[TCIA UPENN-GBM官方集合](https://www.cancerimagingarchive.net/collection/upenn-gbm/)及其[官方数据说明](https://wiki.cancerimagingarchive.net/pages/viewpage.action?pageId=70225642)核对集合DOI `10.7937/TCIA.709X-DN49`，版本页列Version 2（2022-10-24）。本轮NBIA公开序列查询实际返回CC BY 4.0许可及同一匿名受试者的六序列大小/实例数。按[官方公共REST API](https://wiki.cancerimagingarchive.net/display/Public/NBIA%2BSearch%2BREST%2BAPI%2BGuide)仅选两组有限候选，不取全队列，不获取临床表/IDH标签，不登录或申请访问。匿名来源ID、Study/Series/SOP与FrameOfReference UID、确切URL、字节数和SHA留在E盘Data的来源/实例清单中。

两组源描述含`Processed_CaPTk`。按[集合原论文](https://doi.org/10.1038/s41597-022-01560-7)的处理说明，将其记录为发布者加工/去面部的临床采集来源DICOM；不称原始未加工扫描仪文件，也不是本地用现存NIfTI生成的测试DICOM。官方数据说明明确该集合另供的NIfTI与DICOM按设计不对齐，因此不拿已有NIfTI/mask直接当这组DICOM的模型输入或真值。

文件夹`.../t1/`仅沿用源描述作样本短名，没有确认其为当前模型的T1n角色；普通阅片不需要四序列或IDH标签。

## 实际取得及检查

| 候选 | 实际数据 | 来源完整性 | 现有几何契约 | 当前处置 |
|---|---|---|---|---|
| 60实例FLAIR源描述 | ZIP 2,816,912字节，DICOM合计6,077,738字节 | ZIP CRC及60/60发布者MD5一致；每文件SHA/UID已记录；全部像素可解码 | 声明SpacingBetweenSlices为1mm，IPP/IOP实测约3mm，现有`declared_slice_spacing_mismatch`明确拒绝 | 原件保留隔离；不改元数据、不插值、不归档 |
| 192实例经典MR源描述 | DICOM合计19,432,662字节，与NBIA系列文件大小一致 | 实际getSOPInstanceUIDs→逐实例getSingleImage，192/192源UID与本地SHA核对、全部像素可解码；该逐实例端点未提供发布者MD5，不称已核官方SHA/MD5 | 现有`validate_series`不作修改地通过；192×256×192，spacing XYZ=0.9765625/0.9765625/1mm，经典单帧MR、非MOSAIC，实际文件为Implicit VR Little Endian | 已得到支持几何的真实有限序列；尚未PACS导入/Cornerstone真实阅片或模型激活 |

首个curl下载在连接阶段55秒超时；改用正常Windows .NET默认HTTPS路由后60实例ZIP下载成功，TLS一直开启。192实例整体ZIP传输60秒取消，4,370,206字节`.partial`留在Data，不当完整ZIP使用；改为逐实例有界下载，先3个短测，再续下其余189个，复用已完整文件，全部结束。逐实例上限1MiB、系列总预算32MiB；所有文件留E盘，没有新增软件或执行下载内容。

Data根：`E:/BrainFusion-Data/PACS-candidates/UPENN-GBM/20261014T180828_p2sample/`。支持候选在`t1/instances/`；其`source-manifest.json`、`source-instance-list.json`、`instance-download-192.json`提供真实来源对应。FLAIR的发布者MD5来自同一HTTPS ZIP内清单，属于传输完整性核验，不能解释为独立签名认证。252个DICOM在检查/渲染之后SHA/大小全部不变。

## 像素和元数据复核边界

按物理层位排序，以原像素大小和共同的首源DICOM窗值生成六张32层联系表；已逐张技术查看覆盖192层，在该显示窗下未见烧录身份文字。联系表只有图像外本地层号，没有叠加源姓名/日期等字段。图像和渲染清单在`t1/technical-contact-sheets/`，证据`technical-visual-review.json`绑定联系表SHA。

这是Codex AI技术目视检查，未冒充人工/医生审核，也不保证其他窗值、图层或完整脱敏。192实例源文件均缺BurnedInAnnotation标记；预检仍记录私有属性576个、日期/时间/自由文本/不透明字段以及每实例一个阻断标签。所有源UID绑定检查通过，元数据发现不等同已证实真实身份泄漏。`t1-preflight-reports.json`保留字段路径与原因，不保留字段原值；没有为了让样本通过删除保护或修改源文件。

## 下一步及抽查

1. 查看本run的`t1-series-inspection.json`：192实例、全像素解码、源UID与SHA一致，`series_validation.passed=true`，归档/模型仍false。
2. 查看`flair-geometry-diagnostic.json`：实测约3mm和声明1mm不一致，拒绝继续保留。
3. 查看Data的`t1/technical-contact-sheets/`六张图与`technical-visual-review.json`，核对覆盖1–192层、仅技术观察的范围。
4. 查看`t1-preflight-reports.json`中的待处理标签路径；下一轮据实际字段准备有审计的脱敏派生副本及产品导入批准路径，保留原件/UID对应。归档可运行后优先真实导入→Cornerstone，不能把本地解码/几何通过升级为实际DICOMweb验收。

本轮抽查地址为E盘文件；检查时原登记的5179/8012无监听、旧PID已不存在，未重启服务，因此不提供虚假的在线页面结果。Orthanc历史安装动作仍被自动审批拒绝（原反馈仅`blocked by policy`）；未重试或绕过。PACS与业务联合恢复、匹配四序列AI、完整P2–P4继续未验收。
