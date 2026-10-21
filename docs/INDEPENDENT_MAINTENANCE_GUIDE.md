# BrainFusion-AI 独立维护手册

更新基线：2026-10-20。本文帮助项目负责人独立阅读、运行和维护当前工程。版本冻结后仍须按“交付前演练”实操并校订路径与截图。

## 1. 系统是什么、当前能做什么

BrainFusion-AI 是本地科研原型：FastAPI 后端管理病例、影像文件、分析任务、PACS/DICOM 来源和研究接口；Vue 前端提供病例、阅片工作站、研究和报告页面；Cornerstone3D 显示影像；MONAI 分割模型生成分割结果；SQLite 保存业务关系与版本状态；Orthanc 提供 DICOM 归档/DICOMweb；Docker Compose 提供隔离容器运行方式。

当前可演示病例17既有 NIfTI 数据的只读浏览、四序列切换、已有分割和报告，以及病例19病例详情中的真实PACS检查/序列/空间元数据查询。PACS像素读取关闭，因此当前不能演示DICOM图像、测量、复核或报告。隔离Compose页面为 http://127.0.0.1:18180，后端为 http://127.0.0.1:18100。真实同检查四序列DICOM到模型的转换、审核、激活、推理和报告链仍未完成；没有人工影像隐私复核时，候选影像不得进入像素读取或推理。

导师提出的“大模型生成报告”暂时不属于当前实现或验收范围。先完成现有系统和毕业论文工程材料，结构化报告稳定后再讨论模型用途、部署、隐私和评估。历史预测只代表其来源病例/模型版本，不是临床诊断。

## 2. 目录地图和数据边界

- backend/app/api/：HTTP 路由和权限入口。
- backend/app/services/：业务流程、完整性、PACS、转换、分析、报告和研究逻辑。
- backend/app/models/ 与 backend/app/schemas/：数据库模型及接口结构。
- backend/app/ai/、backend/app/research/：分割和研究实现。
- backend/tools/：启动、状态检查、测试、数据核验、恢复和打包工具。
- backend/tests/：后端自动化回归。
- frontend/src/views/、components/、api/：页面、控件及后端请求。
- frontend/e2e/：浏览器端端到端测试。
- docs/：架构、边界、运行、恢复、研究和验收说明。

源码在 E:\BrainFusion-AI；数据候选在 E:\BrainFusion-Data；模型、运行配置、数据库、日志、备份和测试证据在 E:\BrainFusion-Runtime。运行挂载以 docs/COMPOSE_NIFTI_DEMO_GUIDE_20261020.md 和私有环境文件为准。不要猜路径、把患者资料放入源码目录、分享私有环境文件，或删除模型、数据、唯一备份和验收证据。

追一条页面功能时，从 Vue 页面找到 API 请求，再到 backend/app/api/ 的路由、services/ 业务逻辑、models/ 和文件落点。详见 PROJECT_CODE_MAP.md、SYSTEM_ARCHITECTURE_CURRENT.md。

### 当前运行提示（2026-10-20）

当前 Docker 隔离演示端口为前端18180、后端18100；健康状态与启动/停止命令看 `COMPOSE_NIFTI_DEMO_GUIDE_20261020.md`。Orthanc 原归档在外部普通 PowerShell 中以前台方式运行，实例身份登记在 `E:\BrainFusion-Runtime\orthanc-local\process.json`。不要再用失败的后台启动方式反复尝试；正确启动、只读检查和安全停止命令见 `ORTHANC_FOREGROUND_RECOVERY_VALIDATION_20261020.md`。运行窗口要保持打开。

最新 PACS 状态：真实病例页元数据流程已验收，像素读取与阅片关闭（`allow_pixel_read=false`）。人工隐私复核与许可未通过前，不启用像素、不做导入/转换/推理。运行和页面证据见 `ORTHANC_FOREGROUND_RECOVERY_VALIDATION_20261020.md`、`PACS_METADATA_PAGE_VALIDATION_20261020.md`。联合恢复副本Orthanc已单独启动并通过只读元数据与身份/UID核对；应用连接恢复副本的病例关联验收仍未通过，详见 `SYSTEM_BACKUP_RESTORE.md` 及其证据JSON。
## 3. 日常演示：只读打开与关闭

在 PowerShell 查看容器：

    docker ps --format "{{.Names}} {{.Status}} {{.Ports}}"

若 brainfusion-backend 与 brainfusion-frontend 已运行，打开 http://127.0.0.1:18180。导师演示使用病例17已保存结果，只浏览；不要上传、导入、删除、推理、保存测量或保存视图。关浏览器不会停止容器。

结束隔离演示前，按 COMPOSE_NIFTI_DEMO_GUIDE_20261020.md 对应的私有环境文件执行该项目的 Compose down。它停止容器和网络，不删除隔离 runtime。不要执行 docker volume prune、全局清理或停止不明容器。再次启动前核对容器和端口，不得创建同端口第二套项目。

本演示不证明真实 DICOM→AI、干净新机器安装、临床性能或外部验证。PACS状态成功只表示服务可达/元数据检查通过，不表示读取了影像像素。

## 4. 本地开发与验证

修改前确认工作目录为 E:\BrainFusion-AI，阅读 CURRENT_STAGE.md、CODEX_RULES.md 和受影响功能协议，检查 git status --short。工作树有大量既有未提交文件；不要重置、清理、覆盖或提交他人已有改动。小批修改，先跑针对性测试，再做完整回归。

项目约定项目文件修改、测试/构建、依赖安装、数据写入和服务启停都由有限同步开发锁包装。建立一个等待所有子进程结束的 PowerShell 工作脚本，然后执行：

    $runId = 'manual.yyyymmdd.step'
    $scriptPath = 'E:\BrainFusion-Runtime\automation\your-step.ps1'
    & 'E:\BrainFusion-AI\backend\tools\run_development_step.ps1' -RunId $runId -ScriptPath $scriptPath

每次用新 RunId。先 dot-source backend/tools/use_e_drive.ps1，将临时目录和缓存指向 E 盘。不要删除 development.lock 或抢锁；冲突时查看 development-lock.json 的身份和时间，排查原持有者。

依赖角色见 ENVIRONMENT_INVENTORY.md；前端版本以 frontend/package.json、package-lock.json 为准。不要直接升级主环境中的 Torch、MONAI 或全量依赖。测试命令和交付审计按 LOCAL_RUN.md、SOURCE_DELIVERY.md 当前段落执行，临时目录必须指向 E 盘。失败时读完整日志和失败用例；隔离测试通过不等于真实影像验收通过。

排错顺序：页面问题看浏览器控制台和 Network；API错误看容器/后端健康、OpenAPI 和当次日志；影像打不开先核对病例、文件、序列角色、空间几何、来源哈希和只读挂载；分析旧结果先核当前任务、输入 MRI ID、模型版本和输出完整性。不要用旧报告覆盖新病例上下文。

## 5. 更新 Docker 演示

Docker演示只用隔离副本。代码修改后按锁内流程跑相关回归和生产构建；重建镜像后检查 Compose 解析、镜像ID、健康检查、页面/API、只读挂载与持久性。持久目录、环境文件和 PACS 凭据不得进 Git 或源码 ZIP。验收记录见 E5_DOCKER_RUNTIME_VALIDATION_20261020.md。

容器健康不证明业务路径有效：曾发生隔离库 MRI/掩膜路径未重定位导致接口422。演示前检查代表病例四序列、mask、报告可读，并确认页面无错误。修改白名单源码后旧 ZIP 即为历史候选；重新审计、解包验证并记录新 SHA-256，不能覆盖旧证据。

## 6. DICOM/PACS 操作和保护

Orthanc 是归档服务；后端以受控认证访问 DICOMweb，浏览器不持有 PACS 密钥。数据包含 SQLite 索引、Storage 影像、Orthanc 配置、应用 pacs-config、本地账户、导入登记和转换材料。只备份 SQLite 或配置都不完整。详见 PACS_LOCAL_PREPARATION.md、P2_CONTROLLED_IMPORT_VALIDATION.md、LOCAL_REVIEW_ACCOUNTS.md。

不要仅按文件名判断增强T1、非增强T1、T2、FLAIR；核对同一检查、空间和来源。转换、审核、激活、推理是不同步骤；转换不会自动激活，激活也不代表已推理。来源或输入哈希变化时旧分析应失效。未获授权且无人完成人工隐私检查时，不读取候选像素、不导入、不转换、不推理。

## 7. 备份、恢复与回滚

恢复是离线操作，不要复制活动归档。开始前确认无分析/转换任务，按身份安全正常停止后端及 Orthanc，并检查监听端口已释放。按 SYSTEM_BACKUP_RESTORE.md 使用 snapshot_pacs_joint.py 在 E:\BrainFusion-Runtime\backups 下创建全新目录。快照含凭据，须限制本机访问，不能进入 Git、源码包、截图或消息。旧快照不得覆盖。

恢复写入另一全新目录；校验 manifest、每个文件 SHA-256、数据库完整性、应用数据、归档索引/文件、PACS身份、账户、导入/转换登记和 runtime.json。恢复副本不能与正式服务同时占用归档端口。运行后核验来源 UID、病例关系、账户重新登录和页面读取，再通过受控流程停恢复服务、回原配置。文件复制通过不代表运行恢复通过。

截至2026-10-20，当前重绑后私有联合快照为 E:/BrainFusion-Runtime/backups/closeout-joint-20261020T110853Z/。快照文件校验、SQLite完整性、科学/版本字段、运行路径与账户文件均已通过；恢复副本Orthanc在8043也通过了只读身份和UID集合核对，且已正常关闭。恢复工具已修复为自动沿用快照中已保存的PACS身份pin，并有16项针对性测试通过。应用病例关联同时绑定PACS URL和服务pin；所以8043只适合验证隔离Orthanc元数据，整体恢复标记必须保持false。用户当前要求先完成主体工程，应用级联合恢复验收后置；当前不得停用或切换8042，也不得自动重绑病例关联。主体工程收尾后，再决定是否安排维护窗口短暂让恢复副本接管8042，或另行审核有审计的关联重绑。原运行目录Orthanc在8042正常运行；当前PACS像素读取关闭。不得同时启动两个占用8042的Orthanc实例。

## 8. 研究结果与数据

按 DATASET_PLAN.md、EXPERIMENT_PROTOCOL.md、R1–R4协议和许可登记操作科研数据。患者ID、标签、拆分和纳排标准必须来自来源；标准化、特征选择、校准和融合参数只在允许的训练/验证集拟合。复制数据前核许可、隐私、哈希和存储空间，不重下已有可用资料。

记录 run_id、代码/数据/模型哈希、配置、拆分、随机种子、输出目录、失败和统计区间。失败实验也保留，不拼接不同配置结果。UTSW-Glioma 是 NIfTI/标签候选，不是 DICOM/PACS 样本。公开DICOM工程候选优先考虑TCIA UPENN-GBM：当前官方集合页列630名受试者、3,301个检查、3,680个序列，DICOM约139.4 GB并标注CC BY 4.0；论文报道其共配准结构MRI包括T1、增强T1、T2和FLAIR。以上不能证明某个原始DICOM检查有满足系统要求的同Study四序列和共同空间。该集合尚未下载或读像素；小批量下载前核实manifest与随附LICENSE/使用政策，TCIA通用脑部影像说明与集合页信息如有冲突先向TCIA确认。TCIA下载流程正在迁移到Data Retriever/NCI Imaging Data Commons，按当前官方文档操作。无人完成人工烧录文字、序列角色和空间复核前，不开放像素、转换、导入或AI桥。详见PUBLIC_GLIOMA_DATA_RECOMMENDATION_20261020.md和USER_ACCEPTANCE_QA_20261020.md。SCI投稿是可选支线，不等于系统验收通过。来源：[TCIA UPENN-GBM](https://www.cancerimagingarchive.net/collection/upenn-gbm/)、[TCIA下载说明](https://wiki.cancerimagingarchive.net/display/NBIA/Downloading%2BTCIA%2BImages)、[TCIA数据使用政策](https://wiki.cancerimagingarchive.net/display/Public/Data%2BUsage%2BPolicies%2Band%2BRestrictions)、[队列研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC9338035/)。

## 9. 交付与版本冻结、磁盘清理

源码-only ZIP 不含运行环境、数据、模型或私有配置，不是安装器。交付前核 RELEASE_SCOPE.md、RELEASE_CHECKLIST.md；重新生成源码候选、检查文件清单和扫描结果、解包复跑测试，记录 ZIP SHA-256，再按冻结版本刷新配置、来源清单、操作手册和截图。只有候选与实际运行版本一致时才称当前候选。

C/E盘只清理已证明逐字节重复、无进程/任务/配置引用、且非唯一备份/数据/模型/运行依赖的文件。先记录候选路径、大小、哈希、重复目标和引用检查，再小批处理并验证。目录名相似、旧时间戳或大体积不是删除依据；用途不明则保留。

## 10. 常用资料

- 当前状态/优先级：CURRENT_STAGE.md、MASTER_ROADMAP_2026.md、RELEASE_CHECKLIST.md
- 演示/启停：COMPOSE_NIFTI_DEMO_GUIDE_20261020.md、LOCAL_RUN.md、FIXED_DEMO_GUIDE.md
- 功能边界：FEATURE_OVERVIEW.md、RELEASE_SCOPE.md、PROJECT_CODE_MAP.md
- PACS/影像：PACS_LOCAL_PREPARATION.md、LOCAL_REVIEW_ACCOUNTS.md、P2/P3/P4验收记录
- 备份/交付：SYSTEM_BACKUP_RESTORE.md、SOURCE_DELIVERY.md、E5_DOCKER_RUNTIME_VALIDATION_20261020.md
- 研究材料：DATASET_PLAN.md、EXPERIMENT_PROTOCOL.md、THESIS_ENGINEERING_MATERIALS.md

## 11. 交付前独立演练

项目负责人需实际完成并记录：①只读检查 Docker、打开固定演示、解释结果和临床边界；②从一项前端功能追踪到API、服务和数据表/文件；③在隔离分支改一处安全UI并运行测试/构建、检查差异后撤销演练改动；④从日志区分页面、后端、PACS和文件/几何错误；⑤先读懂恢复副本核验材料及当前未验收原因；主体工程收尾后，只有在用户安排维护窗口时才执行恢复副本接管8042的演练并回到原服务；⑥完成两次导师演示预演，讲清系统路线、PACS/Cornerstone、已有模型、结构化报告、未验收项及研究计划。

演练完成前，本文是可执行草案，不表示用户已完成培训，也不解除影像人工审核等外部门槛。




