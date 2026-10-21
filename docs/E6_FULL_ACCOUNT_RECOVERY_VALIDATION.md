# E6 含账户与多病例的本机完整数据组合恢复

2026-10-16凌晨，run_id `20261016T052133_fullaccount`，系统UTC21:18:25.2892488/北京05:18:25实际开工，属于10/15晚至10/16凌晨。先核对服务/锁/反馈、旧快照、磁盘与清单；约412GB空闲，新组合应用650文件521478562字节，活动分析/特征/导入由现有快照工具拒绝。本轮只有一次新完整备份/恢复，不下载/重导192、不重复推理或提取，不每轮重抄650文件。

## 夹具和实际范围

当前正式库新做SQLite备份后，在本轮私有工程副本保留全部19病例/17表和原科学结果；合入此前真实归档工程副本病例19的36距离、2视图、6不可变复核及1独立病例意见，另合入真实NIfTI病例17已验T1n/隐藏mask/三相机视图。未在正式库加记录、删病例、造患者/标签或重建分析输出；这些是已有真实鼠标/来源工程记录，用于恢复，不是新增临床判读。原病例17患者资料与研究覆盖输入仍独立保持。

活动账户取原正式两账户配置（local-reviewer/local-researcher），字节SHA恢复一致；旧6条工程actor继续是当时的历史快照，不强行改成当前账户或医师资质。恢复后登录原本机local-reviewer，固定显示“本地复核账户（本机授权）”，另存第7条明确工程复核，professional_credential_verified=false。

## 本轮已完成验收

1. 正常身份停机后，真正snapshot_pacs_joint backup/restore CLI收录196归档/配置、650应用文件/模型/研究/产物、5导入文件及两账户配置，独立恢复。源码、Python/Node/Orthanc二进制不被该工具复制；账户私有配置没有明文初始密码/会话。未放宽来源、PACS鉴权或像素权限。
2. verify_system_restore逐文件核对650原件/备份和恢复资产（特征request/state只按既有规则改路径/缓存键），17表所有科学/版本字段在批准路径映射后保持。归档实际读取192份原字节SHA、服务标识及检查UID/病例关联，与备份前直接观察完全一致。
3. 在新模型/研究/上传/结果目录实际启动，通过真实启动前依赖/权重/研究SHA/特征门槛检查。Edge155 headless打开NIfTI17，恢复同一T1n/隐藏mask、三物理相机/窗值；再切真实病例1、DICOM19，36距离/视图恢复且不串病例。19病例身份列表、代表病例17患者/临床/分析/报告/特征科学API与原服务基线一致，不推理、不提取。
4. DICOM来源/几何/36距离/独立意见/旧6复核及内容/导出SHA一致；原正式doctor账户在恢复配置登录、固定署名，保存/刷新第7条。内容SHA保持、导出SHA变化。只在恢复副本写1条工程复核；规范化批准路径后其他16表与旧6复核原行完全不改。
5. 真正停止/重启恢复后的Orthanc与前后端，再次科学API/来源/第7条actor/版本一致；先前活cookie失效，重新登录同账户可用，同client_uid重试返回原#7而非新行。重启不是只关浏览器；日志记录实际进程身份。
6. finally在同一有限同步锁步骤内回原归档/八路径及四额外配置，原正式17表全行、650源文件/离线归档全部文件/原配置SHA、原账户/登记及两个源工程库SHA保持。实际PACS ready/账户configured后释放。所有实际步骤退出0；无退役holder/空等待、依赖安装或被拒Orthanc环境动作重试。

离线备份/恢复、两种真实来源/账户、恢复服务重启及回原目录的主要实际步骤共98.917秒；不含准备代码/夹具/文档时间，不是归档吞吐或模型性能。两种真实三视图、账户复核局部和重启报告头截图已查看；局部截图不是整页PDF排版验收，本轮没有新PDF。

## 外部前提核对：不等于独立安装系统

本轮external-prerequisites.json明确并实际记录4个既有可执行/插件路径、大小和SHA：主Python、特征Python、Orthanc及DICOMweb插件；只核这4个文件，不冒充全部Python/Node环境重新构建。当前源码目录与前端/已安装浏览器也在数据组合之外。没有执行外部安装、下载或修改系统。

导入registry/回执已恢复，但受控再导入所需的已复核源DICOM/PNG/来源材料保留在原登记外部目录，不静默搬运/再审批。本轮实际核对1组登记的derivative-manifest、preparation-report及review JSON三份固定SHA；没有重复全源像素审计或导入。普通已归档阅片的192原字节已在新Orthanc内，能真实打开；如果移往新机器，还须按许可提供上述再导入证据材料或明确禁用相应再导入入口，不能称完全自包含。

这完成“本机完整数据/归档/模型/研究/账户组合”恢复子项。代码/二进制/环境及异机安装、完整新源码交付候选仍另验；P3真实匹配四序列和E5正常系统授权条件未变。新快照含私有服务凭据/盐化摘要和业务数据，必须留Runtime/backups，不能入Git/公开源码包；测试活token仅留私有父目录，不属于snapshot。

## 证据、实际运行和抽查

公开说明用的本机证据根 `E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T052133_fullaccount/`：plan-guard/fixture-scope、application-plan、full-joint-backup/restore、application-restore-audit、fixture/restored-live-archive、restored-account-proof、full-account-browser-save/restart、after-save-proof、full-post-live-scientific-audit、external-prerequisites、original-offline-preservation、final-preservation/services、recovery-timing。原始全表proof仍是本机资料，勿公开分发。

私有fixture/snapshot/restored在Runtime/backups/20261016T052133_fullaccount；恢复候选当前已停止，正式后台30304/UTC2026-10-15T21:26:25.6822586Z、前端20208/UTC2026-10-15T21:26:25.6851202Z，Orthanc28324/UTC2026-10-15T21:26:16.1338304Z，回原8042归档。地址仍 http://127.0.0.1:5179/case/19 、API http://127.0.0.1:8012/docs 。原默认数据仍为既有nightly路径；不能删除。日志/身份以Runtime/local/processes.json、backend/frontend out/err及orthanc-local/process.json为准，无下载/训练/推理/提取/构建长任务。

抽查最多四项：①正式Edge病例17 Cornerstone切序列正常、无工程保存视图；②病例19原检查/序列仍192层且无工程复核；③对照新完整恢复两来源/账户/重启截图和17表规范化审计；④看external-prerequisites说明“可实际恢复数据”与“独立安装包”之间的边界。不要切正式库来展示工程第7条。

下一轮第一步：核对锁/服务/反馈与Git，E6刷新当前源码交付候选及可复现清单（旧10/10包不含后续PACS/账户等实现），在新目录检查包不混入数据/模型/凭据、解包后代码身份和适当验证；复用本次数据组合，不再完整复制650或重跑模型。P3/E5按解除条件续接，不以打包宣布完整系统完成。
