## 2026-10-20 最新现场状态（优先于下方旧快照）

隔离 Docker 前后端再次实测 healthy（前端 http://127.0.0.1:18180、后端 http://127.0.0.1:18100）；Orthanc 已由外部 PowerShell 前台运行，PID/启动时间/可执行文件/配置/8042监听身份匹配，认证 `/system` 版本1.13.0 与 DICOMweb QIDO 通过。后端只读归档列表查询200、1个检查；PACS `ready/read_available=true`。因人工烧录隐私复核尚未完成，已备份后将 `allow_pixel_read` 关闭；最新状态 `pixel_read_enabled=false`、`dicom_view_available=false`，导入和AI桥关闭。没有读取像素、导入或修改归档数据。前台终端必须保持打开；安全停止与复现命令见 [Orthanc前台恢复验收](ORTHANC_FOREGROUND_RECOVERY_VALIDATION_20261020.md)。

本轮最新源码-only内部候选位于 `E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T211000_handover_public_data_candidate/`：466个白名单文件、受限扫描0发现、ZIP大小1,534,962字节；包状态为passed，SHA-256 `453f49c8492e1c575f44721a66bdf29ab1b0a98553082bae0f196a740d91208e`，逐文件解包核验见该目录 `validation.json`。本候选已纳入最新维护手册、交付范围、操作指南和用户决策Q&A；本轮仅做交付材料一致性及源码包构建/哈希核验，没有重复跑测试或全量回归。候选不含运行环境、数据或模型，也不等于最终异机部署或真实四序列AI验收。

原归档与恢复副本分别通过只读元数据验证；恢复副本身份与保存pin/原服务一致，检查和实例UID集合匹配，并已正常关闭。恢复工具已修复为自动保留该pin，针对性测试16项通过。由于病例关联指纹也绑定PACS地址，恢复副本只有接管原8042地址或完成有审计的关联重绑后才能做应用级恢复验收；当前整体恢复标记仍为false。病例详情页真实PACS元数据流程已验收：检查、序列、实例及空间清单均可查询，阅片按钮因像素门控而禁用；0写入、0像素请求、0页面异常。证据见 [PACS元数据页面验收](PACS_METADATA_PAGE_VALIDATION_20261020.md) 与 [备份恢复说明](SYSTEM_BACKUP_RESTORE.md)。
### 当前收尾顺序与用户决定（2026-10-20）

用户明确要求先完成项目主体，暂缓所谓的应用级恢复测试；当前不得为恢复副本停用/切换原Orthanc（8042），不得改病例关联，也不要重复询问维护窗口。主体工程收尾后，再决定是否做该维护窗口验收。现有Docker只读演示可继续使用。

本轮按主体交付推进：详细操作指南已补入Docker只读演示的启动/关闭、页面浏览、MRI源文件位置、隔离可写副本的上传和MONAI分割输出目录，并明确当前演示不允许上传/推理；公开DICOM数据候选补充为TCIA UPENN-GBM，小批量筛查待许可与人工复核，不触碰像素门控。 公开数据决策流程也进入用户验收问答，列明集合许可核对、少量manifest、同检查四序列与人工复核条件。源码-only候选已更新至 E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T211000_handover_public_data_candidate/，466个白名单文件、扫描0发现、ZIP SHA-256 453f49c8492e1c575f44721a66bdf29ab1b0a98553082bae0f196a740d91208e；没有运行回归测试或切换Orthanc。

剩余工作按依赖排序：
1. 当前操作指南、备份恢复说明、验收清单、导师演示材料已按2026-10-20现场状态核齐；已生成文档对齐的源码-only内部候选。仍需在功能/配置冻结后完成最终版本对应性复核和正式交付封版；当前候选不含运行数据、模型或安装环境，也未作为完整发布包验收。
2. 负责人按最终指南完成独立操作、修改/排错和两次导师预演；演练是交付环节，不能由文档或Codex代替。
3. 主体工程完成后再安排应用级联合恢复验收；此项需短暂占用8042，现按用户决定后置。
4. 真实DICOM像素/转换/AI仍取决于获准人员核对烧录隐私、许可、四序列角色及共同空间。目前没有第二位影像复核者，故像素读取、导入和AI桥保持关闭；不以NIfTI、元数据或机器预筛冒充真实影像验收。
5. 大模型生成报告按用户决定暂缓；毕业论文工程材料与系统展示是当前主线，SCI为有余力时的支线。

## 2026-10-20 19:29 历史快照（已被本文件顶部最新状态覆盖）

Docker隔离演示前端 http://127.0.0.1:18180 返回200，后端 http://127.0.0.1:18100/ healthy；当前展示范围为病例17 NIfTI只读浏览。正式本机Orthanc目前未运行，PACS状态unavailable，8042未监听；活动归档数据未损坏，Docker容器仍运行。后台启动器已修复：现在在适用时请求CREATE_BREAKAWAY_FROM_JOB，并仍强制验证目标进程不属于任何Job；专用测试2项通过。补丁后用户从Anaconda PowerShell复测仍失败：启动器报告0x1800且确认目标仍在Job中，子进程已安全终止；PACS仍unavailable、8042未监听。0x1800只描述启动器当前Job的标志，不能证明目标已脱离全部嵌套Job。Codex上下文0x2800同样失败；WMI进程创建短探针仍在Job中，不作为绕过方案。用户按诊断确认当前Anaconda PowerShell为in_job=True；虽提示停止，随后仍手动调用启动脚本，目标被保护性终止，未修改归档。通过Shell COM再开的PowerShell也继承Job，WMI短探针亦处于Job；这些均不能作为隔离来源。该启动问题已由用户随后在Codex外PowerShell以前台方式解决；不要再按本历史段尝试Task Manager/Job诊断或重启原Orthanc。当前运行状态见本文件顶部；离线恢复副本的在线启动仍未通过。

重绑后的私有联合快照与隔离恢复已完成：E:/BrainFusion-Runtime/backups/closeout-joint-20261020T110853Z/。196个归档/配置文件、702个应用文件；SHA-256、SQLite完整性、17张表科学/版本字段和13条统一运行路径通过；应用/归档文件哈希和应用数据库字段核对通过；恢复副本的Orthanc未能启动，因此Docker应用没有对恢复副本执行QIDO，joint-restore.json标明live_restoration_verified=false；全程未读取影像像素。请从Codex外的普通PowerShell运行：
    & 'E:\BrainFusion-AI\backend\tools\start_orthanc_local.ps1' -Root 'E:\BrainFusion-Runtime\orthanc-local'
然后以 http://127.0.0.1:18100/pacs/status 的state=ready确认恢复。

当前源码候选：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T1935_recovery_scope_refresh/candidate/；463个白名单文件、扫描0发现，ZIP SHA-256 1368f78e6dd32051a3610bcefac26dda031c990df6fa3ee6eea6ffd3bb368546。只读交付核验463/463匹配、SQLite签名未变、passed_existing_workstation_only。后端695项全回归通过；与上一候选的差异仅为两份恢复文档，代码哈希未变，复用同一695项回归证据。Docker/Linux Compose验收另有E5记录，不能由本机预检替代。

剩余优先项：①在Codex外启动Orthanc并复查PACS；②安排有权限人员核对同检查四序列图像烧录文字、数据许可和序列角色，当前无人可复核，因此真实DICOM→AI不能验收；③项目负责人按手册完成独立操作、故障排查、备份恢复及两次导师预演；④冻结后刷新最终交付材料，并仅清理有精确重复、无引用且非唯一备份/证据的文件。大模型按用户决定暂缓，SCI不是系统工程收尾门槛。

## 2026-10-20 独立维护手册与源码候选增量

新增 docs/INDEPENDENT_MAINTENANCE_GUIDE.md，覆盖当前系统范围、目录/数据边界、只读 Docker 演示、开发与测试、PACS保护、备份恢复、研究约束、版本冻结、磁盘清理和独立演练。手册明确大模型暂缓，重绑后联合恢复尚未实测，DICOM真实四序列闭环需人工隐私复核。项目尚未冻结，因此标记为可执行草案，最终路径/配置需冻结后实测，用户独立操作与两次导师预演仍未完成。

源码-only内部候选已重建：463个文件，扫描0发现；ZIP SHA-256 6875da13016b55bc7f1b010f671c1b4a0691586485f12c27ca252f1ceb14e1a3。候选解包副本后端全量回归694 passed、4条既有弃用警告（203.69秒）；源码打包定向测试6 passed。候选证据：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T2300_maintenance_guide_candidate/。没有覆盖旧候选、提交或发布；全量测试只运行在解包隔离副本。曾有本地测试服务器断连堆栈打印，最终pytest退出码0且无失败用例。

PACS重绑后联合全系统恢复和人工影像隐私复核仍待解决；当前隔离Docker演示保留，不为恢复演练停服务。大模型不属于本轮验收。
## 2026-10-20 导师路线与数据候选更新

导师目标为 PACS + 机器学习预测 + 大模型生成报告。PACS/DICOM工程路径、已有IDH研究原型及结构化分割报告分别存在，但真实数据端到端和LLM服务均未验收；没有本地LLM运行时；按用户最新决定先完成现有工作，之后再评估LLM接入。数据候选推荐TCIA UTSW-Glioma用于NIfTI四序列/分子标签研究；官方元数据已只读筛查：625个唯一ID无重复、年龄/性别625/625，IDH明确622/625、MGMT明确281/625，影像未下载。UPENN-GBM仅候选为DICOM/PACS数据，四序列同检查未确认。系统/毕业设计为主线，SCI作为有余力时的研究支线。用户与Codex是唯一协作者，目前无人可做第二位影像复核。C/E盘可并行逐项清理，但只有精确重复、未被引用且非唯一备份/证据的对象才可处理；目录相似不能证明重复。详见 PUBLIC_GLIOMA_DATA_RECOMMENDATION_20261020.md 和 USER_ACCEPTANCE_QA_20261020.md。
## 2026-10-20 Compose 演示即时只读冒烟检查

加载隔离演示环境文件后，Compose配置解析通过；前端首页、后端根路由、OpenAPI及PACS状态接口均HTTP 200；OpenAPI包含68条路由；backend/frontend容器均running/healthy，镜像ID与20:40审计记录一致。未读取DICOM像素、未写病例/业务数据、未启停容器。报告：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T2250_compose_demo_readonly_smoke_final/smoke-report.json。

该检查只证明当前隔离NIfTI演示入口可用，不替代真实DICOM、干净机器安装、临床/效能验收或独立恢复演练。

隔离Compose健康检查步骤已补入docs/LOCAL_RUN.md。由于源码白名单内的运行/恢复说明在17:55候选生成后又有更新，该候选仅作历史版本；待源码、配置与独立维护手册冻结后统一重建和回归最终源码包。

## 2026-10-20 Compose 重绑后配置隔离恢复检查

从私有补充快照恢复到全新隔离目录，3/3配置文件的SHA-256与清单一致、JSON均可解析；本地账户结构及PACS必需字段检查通过，恢复目录ACL仅限当前用户、Administrators、SYSTEM。活动配置与快照哈希仍一致，Docker演示的原后端和前端容器仍健康。报告：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T2210_post_rebind_config_restore_check/recovery-check-report.json。

此项只验证三份配置的文件级恢复，不启动恢复服务，也不代表应用数据库、模型/数据集或Orthanc归档完整恢复。正式交付手册仍须在代码/配置冻结后编写，并由用户按手册独立完成启动、浏览、修改配置、测试、备份/恢复及故障排查演练；不得把本次小范围检查作为整机恢复通过。

## 2026-10-20 预重绑 Orthanc 备份 ACL 收紧

复核发现原有 pacs-identity-rebind 备份继承了 Authenticated Users 可修改、Users 可读权限。已仅修改该备份目录及其 197 个清单文件的 ACL，限定为当前用户、Administrators 和 SYSTEM；所有原始 SHA-256、字节数及 manifest SHA-256 收紧前后相同。没有删除/移动文件，也没有触碰运行中的 Orthanc、Compose 或当前配置。

验证结果：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T2130_secure_backup_acl/backup-acl-verification.json。此次仅改变备份副本权限，不代表完整恢复演练。

## 2026-10-20 Orthanc 重绑后 Compose 配置补充快照

原 pacs-identity-rebind 归档在重绑前生成，其中 pacs-config.json SHA-256 与当前值不同。现已为重绑后的 Compose 运行配置补存 PACS 配置、本地账户哈希和 radiomics gate 三个文件；逐文件 SHA-256 复核通过。新目录 ACL 只允许当前用户、Administrators 与 SYSTEM，未继承 Users/Authenticated Users 访问。

私有快照位置：E:/BrainFusion-Runtime/backups/compose-run-config-20261020/。其含 PACS 凭据/本地账户摘要，不得进入源码ZIP或公开材料；它只补足当前三份运行配置，不是应用数据/模型/Orthanc完整备份。需与原 Orthanc pre-rebind 197文件归档及 Compose runtime 持久化副本组合恢复。验证报告：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T2115_post_rebind_config_backup/backup-verification.json。

## 2026-10-20 Compose 当前配置与活动容器一致性核验

只读解析 docker-compose.yml 与演示环境文件，并逐项比对实际运行容器：12/12项通过。后端full镜像ID sha256:aa3711890c529ecafc64a5815d94a623a24df6e9c5fc70efd504520c54e63973、前端最终镜像ID sha256:ba5ff46e3af0304819506af8c2958dd2e658ee0169f537d45ccbcdb0e1e99a07，均匹配且healthy；6个后端挂载均与解析配置路径一致、位于E盘，配置/模型/研究/数据集/PACS派生5挂载为只读，只有隔离runtime可写。报告不含环境变量值：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T2040_compose_delivery_config/active-compose-config-audit.json。

此项证明当前已运行的case17隔离NIfTI演示配置与容器一致，不代表干净机器部署或真实DICOM/AI验收。当前入口和只读操作要求见LOCAL_RUN.md顶部；不要重复启动当前容器。
## 2026-10-20 环境来源补充核验

只读扫描 pip 缓存，为主环境 54 项 Python 分发找到 52 项名称/版本候选，且对应已安装 RECORD 的比对文件均无差异。未修改环境；缓存不能证明原始安装来源。详见 ENVIRONMENT_INVENTORY.md 与证据 E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T1945_main_python_cache_audit/。

## 2026-10-20 17:55 维护手册进入最终源码打包白名单

为了确保项目冻结后交付的源码 ZIP 能包含独立维护手册，已将预定文件 docs/INDEPENDENT_MAINTENANCE_GUIDE.md 加入明确的源码文档白名单，并扩展白名单回归：手册将被纳入，夜间交接、评审反馈、每日任务及未审核材料仍排除。工具和测试变更后新生成源码-only候选：462项、扫描0发现、ZIP SHA-256 6a42920a203b7fa5aa3a271cbfdc9812ccf6ac79139b617ec747266f3a33df1c。解包候选中来源打包定向测试6 passed。与上一个候选仅两份后端打包器/测试文件不同；前端依赖、生产构建与E2E内容未改变，沿用上一候选相同文件集的通过证据。该ZIP仍是内部源码候选，手册正文、真实DICOM人工复核、配置/数据交付封版和用户带教尚未完成。证据：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T1755_source_candidate_manual_allowlist/。

## 2026-10-20 17:50 当前源码交付候选

针对前端依赖安全修复后，重新生成源码-only ZIP：462个白名单文件，扫描器0发现，SHA-256 2fc3a3cd85c083259870b7e73bf4ffea37fe51bfba53290eec9bc402b81528f1。已在解包副本对前端执行 npm ci、npm audit（0项）、npm ls（无问题）、生产构建、Edge E2E（8通过、1跳过）；PDF下载用例一次超时，单测及整套重跑通过。候选不包含数据、模型、运行环境或前端 node_modules，仅为当前源码-only内部候选；不能替代最终配置、安装环境、人工审阅、系统交付封版。审计范围和完整限制见 SOURCE_DELIVERY.md 及候选目录 E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T1745_source_candidate_scoped_dependencies/。

## 2026-10-20 17:45 最终前端镜像确认

补查依赖树时发现全局 fflate override 与 jsPDF版本冲突，已将覆盖限定到 Cornerstone vtk.js / nifti-reader-js 分支并保留 jsPDF fflate 0.8.3；npm audit 0项、npm ls --all有效、生产构建和 Edge E2E 8通过/1跳过。前端镜像已重新构建并强制重建运行容器，容器 Image ID 与最新镜像一致：sha256:ba5ff46e3af0304819506af8c2958dd2e658ee0169f537d45ccbcdb0e1e99a07。最后在该容器上实测 case17 NIfTI Cornerstone三视图及四序列切换成功，0写请求/0页面错误，测量和视图状态未保存。仅是 NIfTI工程链路验证，不代表真实DICOM或临床/效能验收。

## 2026-10-20 17:40 依赖树一致性复核

npm ls --all 发现全局 fflate 0.7.5 override 会与 jsPDF 声明的0.8.3冲突。已收窄 override 到 @kitware/vtk.js 和 nifti-reader-js，保留 jsPDF的0.8.3；最终 npm ls --all通过、npm audit为0。生产构建、完整 Edge E2E（8通过、1跳过）通过；一次PDF下载超时后单测和完整E2E重跑通过。Docker镜像已按最终锁文件重建，case17 NIfTI四序列生产页面复测通过。详见 NIFTI_DEMO_AND_FRONTEND_SECURITY_20261020.md。

## 2026-10-20 17:20 更新：NIfTI Docker 页面实测与依赖安全修复

隔离演示首次业务接口检查揭示 staging 副本漏改 sequences_json 与分析掩膜路径，容器健康但病例文件 API 返回422。已修复隔离运行副本中的 MRI、序列和掩膜路径，源数据库 SHA-256 不变；健康探测修正为根路径 /。前后端均 healthy，case 17 测量和视图状态 API 为200。使用修复副本和更新后的 Cornerstone Docker 前端，在 Edge 实测三视图及 t1c/t1n/t2w/t2f 切换，0写请求、0页面错误。原依赖审计11项经 Cornerstone 5.7.3 对齐和兼容 overrides 降为0，生产构建及 Edge E2E 为8通过、1跳过。以上只代表已有 NIfTI 工程链路，不代表真实 DICOM、临床或模型效能验收。详见 NIFTI_DEMO_AND_FRONTEND_SECURITY_20261020.md 与 E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T1815_real_nifti_compose_demo_fixed/。

独立阅读/操作/改进手册仍是最终交付物：待功能与配置冻结后，按最终版本实测，覆盖架构和数据流、启动和日常操作、代码入口、修改开发、测试、备份恢复和故障排查。用户实际带教和演示预演也尚未完成。

# 2026-10-20 后续增量：完整回归与后台进程安全收口

## 2026-10-20 16:20 当前隔离 Compose 演示状态（覆盖此前“容器已停止”的状态快照）

当前用户可查看 http://127.0.0.1:18180。Docker Compose 后端与前端在本轮复核时均为 healthy，分别绑定本机 127.0.0.1:18100 和 127.0.0.1:18180。演示使用病例17现存 NIfTI 数据库的隔离副本及对应文件；源数据库前后 SHA-256 相同。范围仅为已存在 NIfTI 病例的容器页面/文件读取演示，不是四序列 DICOM、DICOM→AI 或模型效能验收。说明与停止命令见 COMPOSE_NIFTI_DEMO_GUIDE_20261020.md。不要另启第二套同端口 Compose，也不要把当前演示副本并入正式数据。

## 2026-10-20 16:38 当前前端锁文件安全审计

使用当前 frontend/package-lock.json（SHA-256 8f8f1d092112a005d488c5adeff146dbe00818d82f0122bc935c06a17cac05fe）查询 npm audit，完整依赖树与 production-only 均为 11 项告警：6 high、5 moderate、0 critical。production-only 数量相同，说明这些包位于运行依赖闭包；涉及 Cornerstone/DICOM 与 vtk/fflate，以及 dcmjs/adm-zip、uuid 等传递依赖。npm 没有给出兼容的自动修复；唯一建议为将 @cornerstonejs/tools 降至 0.27.2，属于主版本变化，未执行降级、override、安装或锁文件修改。原始查询与摘要证据：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T1637_frontend_security_audit/。 旧源码候选 20261020T155438_source_candidate_current_status 中的 docs/LOCAL_DELIVERY_ACCEPTANCE.md 与当前文件 SHA 不同（仅交接文档变更，代码未变）；不要称旧ZIP为当前文件包，最终源码/配置冻结时再重建并核其清单。这是依赖清单告警，不等同于已证明系统可被利用；应在任何升级前评估 Cornerstone 版本对齐并跑真实/受支持阅片回归。当前 Compose 服务仅绑定本机回环地址，但这一部署限制不能替代修复/风险处置。

正式 Compose/Orthanc 隔离验收、最终镜像重建持久性复验和 M2 定向回归结果见下方本日记录。本轮继续修正两处全量回归失败：Docker 多阶段构建摘要测试现在只检查四个外部基础镜像；后台进程启动会核验服务子进程自身的 Windows Job 成员身份，受 kill-on-close 作业约束时拒绝报告成功，并记录 PID 和子进程是否已回收。启动器已从 WMI 异步创建改为 PowerShell 内直接同步调用 E 盘 Python 引导程序，避开 WMI provider 额外 job；但 Codex 托管的 PowerShell 本身仍在受约束 job 中，因此受限时安全拒绝启动。对应回归覆盖“无法安全脱离就拒绝启动”。

最终全量后端回归：694 passed、4 条既有弃用警告，195.99 秒。日志 `E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T132214_linux-radiomics-e5/backend-full-regression-final5.log`；开发锁已正常释放（退出码0）。普通本机交互 PowerShell 下的后台常驻成功仍未证明，需另行实测；不得据此承诺 Codex 托管进程可靠脱离所有 job。像素人工复核当前无人可做，所以 ACRIN-134 仍未放行 PixelData。

当前工作树另已生成源码-only内部候选并在解包副本复验：462个白名单文件，审计0发现，后端694 passed、4条弃用警告；前端生产构建通过，Edge/Chromium E2E为8 passed、1 skipped（获准真实报告病例未配置）。ZIP SHA-256 `dd9886ecf3e1c023acb32914aacbb45e6494a3adbb25209de010a330f9736fd6`。浏览器用例是合成UI契约，不是病例验收。结构化证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T155438_source_candidate_current_status/candidate-regression.json`。与实际回归候选逐文件对比只有两份交接文档变化，代码哈希相同，因此复用其后端/前端回归。此候选不含数据、模型、Python/Node环境或前端依赖，也未做最终配置/运行数据封版，不能作为完整安装包或最终冻结发布。

当前只读本机状态：`status_local.ps1` 显示后端旧 PID 28328 和前端旧 PID 11988 均不再匹配/监听，Orthanc PID 16272 正常监听8042；Docker项目容器均已停止。本轮未启动原生服务，因为本 Codex 托管 PowerShell 处于 job 限制中，启动路径需从普通用户交互 PowerShell 单独验证。该状态意味着目前不能直接进行本机网页正式演示。

## 2026-10-19 E5 root-cause evidence: Windows servicing rolled back WSL feature enablement

After the user ran the elevated DISM command and restarted, the Docker installer still reported VirtualMachinePlatform disabled. Read-only WMI now reports InstallState=2 (Disabled) for both VirtualMachinePlatform and Microsoft-Windows-Subsystem-Linux. The machine reports firmware virtualization enabled and a hypervisor present. DISM/CBS logs show the enable command set VirtualMachinePlatform to On and pended changes for reboot; during startup servicing, Network Drivers failed to load NetSetupAI.dll (0x8007007e), followed by CBS_E_INSTALLERS_FAILED / 0x800f0922 and a rollback transaction. This explains why the feature was still disabled after restart; do not treat the Docker installer as the root cause.

Recovery path for the device administrator: run DISM /Online /Cleanup-Image /RestoreHealth in elevated Command Prompt or PowerShell, wait for successful completion, then run sfc /scannow. Microsoft recommends DISM before SFC to repair the component image and protected system files. After both complete, enable Microsoft-Windows-Subsystem-Linux and VirtualMachinePlatform with DISM, verify each reports State: Enabled, restart, verify again, and only then retry the regular-user Docker Desktop installer. If Windows repair fails or the same CBS rollback recurs, retain the CBS.log lines for NetSetupAI.dll and 0x800f0922 for Windows servicing repair; do not repeatedly retry Docker.

No repair command or system-feature change was executed by Codex; these diagnostics and next steps are based on read-only logs and component-state queries. Docker/container acceptance remains incomplete.


## 2026-10-19 E5 environment update: WSL installed; VirtualMachinePlatform still requires administrator enablement

The user has installed WSL. In this session, wsl --version reports WSL 3.0.3 and wsl --list --verbose reports no user Linux distribution. The Docker Desktop 4.95.0 installer explicitly reports that the Windows optional feature VirtualMachinePlatform is disabled. This session is not elevated; the read-only DISM query returned exit code 740, and no system feature was changed. Docker CLI/Desktop are not yet successfully installed; the Docker terms have not been accepted and the computer has not been restarted.

The earlier status saying WSL was not installed is superseded. E5 is currently blocked on an administrator enabling VirtualMachinePlatform and restarting Windows. An administrator can run the following in elevated PowerShell:

    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

After restart, the regular user can install Docker Desktop per-user and personally review and accept its first-run terms. Compose parsing, image build/run and E5 project validation remain outstanding. This update does not claim Docker or container acceptance.

## 2026-10-18 23:01：当前生产前端包Edge只读浏览器验收

因旧`frontend/dist`与10月18日旧构建记录中的favicon哈希已漂移，本轮没有引用旧产物；按当前工作树重新执行`npm run build`，输出到独立E盘目录`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2258_frontend_edge_prod/production-dist/`，VITE_API_BASE明确为8012，43个文件共约11.96 MB，逐文件SHA清单见`build-validation.json`。构建仍报告Cornerstone第三方`fs/path/url`浏览器外置和大分块警告，未改变依赖或构建策略。

以Windows Edge加载这份实际生产bundle，并让只读API请求访问当前8012服务。浏览器原生CORS/本地网络限制要求同源；因此由Playwright测试路由提供构建文件、同源API路径继续到真实后端，未关闭浏览器安全设置，也未启动或替换常驻服务。病例17详情/当前分析、四序列NIfTI及mask、病例研究结果、报告页面全部通过；pageErrors、consoleErrors、failedRequests、blockedWrites均为0。四张截图与机器报告见`production-edge-same-origin-fixed/`。脚本按页面请求拦截并中止所有非GET/HEAD请求，没有运行推理、特征提取或业务写入。

该结果补齐“最新生产bundle浏览器执行”这一同机、只读范围，但不是NGINX/Docker静态HTTP部署、干净机器、Docker/Linux、真实四序列DICOM或模型效能验收。10月18日早先用旧dist的检查与首次浏览器路由尝试失败日志原样保留，不作为通过证据。

## 2026-10-18 22:50：final12源码候选封版复验

将最新Docker/WSL权限说明纳入白名单后生成内部源码候选final12：459个源文件，受限审计0发现；ZIP SHA-256为`d7f118d8f392fc45d6e187d495f933d437dd82d69ff6064bf09a4b57a90791f8`，逐文件解包哈希验证通过。解包副本后端全回归694 passed、0 failed、4条既有弃用警告。只读交付预检为`passed_existing_workstation_only`：候选459/459与当前工作树一致，14项实现源码和3项再现工具与现有工程材料匹配，严格预检通过、数据库签名未变。

完整证据位于`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2255_source_final12/`。本机Docker/WSL仍未安装/启用；容器构建、Linux worker、干净机器和真实四序列链路未验。历史主环境仍有49/54个Python分发缺少原始安装来源证明。final12是内部源码包，不包含运行数据/模型/环境，也不是公开发布。

## 2026-10-18 22:38：容器权限路径澄清与转换作业回归

按当前Docker官方Windows安装说明核对后，纠正文档中的权限误区：Docker Desktop推荐的per-user安装/更新不需管理员；本机首次启用WSL 2仍需管理员并通常需要重启。当前Codex会话不能自行提权。已在`DOCKER_PREREQUISITES.md`写明管理员一次性启用WSL2、普通用户安装/启动Docker Desktop、再由Codex普通会话做E5验证的可执行步骤，并列出Docker VMM（Beta）作为需实测的备选；曾被自动审批拦截的安装尝试标为历史事实。

修正`SYSTEM_COMPLETION_CHECKLIST.md`中10月17日快照关于“转换CLI尚无持久作业接口”的过期描述。当前源码实际已有网页创建/启动/查询/重试及持久作业服务；独立重跑相关转换登记、启动和联合快照模块：50 passed、4条既有弃用警告。没有改业务源码、数据库、模型、影像或常驻服务。日志及同步步骤位于`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T_conversion_jobs_current_docs/`，独占开发锁已释放。

此项只核实持久作业组件回归与安装路径说明；不解除ACRIN-134像素隐私人工确认、不代表真实四序列转换/激活/推理或Docker/Linux运行验收。

## 2026-10-18 22:20 ACRIN-134像素预筛与Python主环境依赖层重建

ACRIN-134本地公开候选包含AX FLAIR、AX T1、AX T1 POST、AX T2 FSE四组序列，各26张、共104张。逐张像素渲染的完整序列图和四周放大图经初步视觉筛查，未见明显姓名、ID、日期或机构烧录文字；所有实例的BurnedInAnnotation均缺失，因此该筛查不等于正式隐私认证。用户当前暂时无法确认，病例继续隔离，未导入、转换或推理。逐张图、SHA清单和限制说明见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2150_main_env_rebuild_candidate/pixel-review/`。

另在E盘独立Python310用户包目录重建51个官方索引轮子，哈希校验与pip check通过；当前项目严格运行预检通过，数据库完整性ok、17个现存模型病例链路通过，未执行迁移或推理；当前工作树后端回归694 passed、4条既有弃用警告。Python311特征工作器继续使用独立NumPy1.26.4/SimpleITK2.5.2/PyRadiomics3.1.0。原`.conda`主环境、项目源码、数据库、模型和服务均未替换/重启；重建包的来源记录不能代替历史安装来源证明（49/54个原Python分发仍缺原始轮子出处）。证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2150_main_env_rebuild_candidate/`。

只读服务复核中，登记后端PID28328与前端PID11988仍按原启动时间运行，后端健康且前端HTTP200。Docker CLI仍不存在，WSL尚未安装，当前会话非管理员；E5只保留本机原生环境回退，容器/异机验收未完成。后续仍需合适人工确认像素隐私与四序列角色、执行真实DICOM转换/页面阅片闭环、安排容器系统窗口，并完成用户带教和两次演练。

## 2026-10-18 20:35 E5 Docker依赖闭包与源码候选最终核对

Docker专用CPython 3.10/Linux amd64 core/full两套SHA-256锁分别含28/44 wheel；full包括Torch 2.11.0+cpu、MONAI、scikit-learn/joblib及完整解析闭包。Pillow Docker版为12.2.0，本机环境未改。Compose前后端均固定linux/amd64。定向11项通过，工作树及最终459文件源码候选全量后端回归均694 passed、4条既有弃用警告。当前白名单源码与候选逐项一致、审计0发现，归档SHA-256以候选机器报告为准；44/44 wheel版本及SHA与锁匹配。完整报告见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2205_pixel_qna_final7/candidate-regression.json`。Docker CLI/WSL和容器实际构建/运行仍待，E5未验。

## 2026-10-18 20:40 服务退出观察交叉核对

正在运行的六小时只读观察进程PID16316（计划于UTC 14:22结束）已记录旧后端4108和前端21448于UTC 09:43:07退出，原样退出码均为4294967295。对照同秒的`20261018T1040_live_source_alignment/planned-restart.json`与`stop.log`，这是为加载当前已测试源码而执行的计划停止，不是新的未知退出。Orthanc未停止；后续后端28328/前端11988于UTC 10:27按原runtime配置启动，服务身份、页面/API/PACS/账户健康通过；数据库17表111行重启前后逻辑摘要相同。当前只读状态见本机`status_local.ps1`，监测原始事件见`20261018T0820_service_stability/observation/events.jsonl`。该窗口没有发现新的非计划退出，但观察进程仍只绑定旧服务身份中的Orthanc，尚未结束；不能据此推断长期稳定，也不解释10月16日那次历史三服务退出，旧根因仍未知。

## 2026-10-18 18:45 Docker基础镜像固定与交付候选更新

Python/Node/NGINX三阶段基础镜像已改为官方多架构清单SHA固定，并新增回归守卫（8项通过）。候选`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1837_docker_base_lock/candidate/`454文件，审计通过，SHA-256 `a73030c528e1ad2927ce8dc13d2270e2ae9f895e09de4981d6f29b0dd8205561`，解包全后端691 passed、4 warnings。容器未实际拉取/构建/运行，Python传递依赖闭包仍未固定；不能标为E5通过。具体摘要与平台子digest见`DOCKER_PREREQUISITES.md`及`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1837_docker_base_lock/base-image-digests.json`。

## 2026-10-18 18:34 当前服务完整性只读冒烟

修复后的常驻API对一份已存在、已验收的NIfTI模型分析执行只读检查：`/analysis`、病例详情、历史与分割状态均HTTP 200；当前分析未过期、历史标记当前、分割可用；4次请求未写业务数据，也未保存病例ID、结果值或路径。耗时约0.04、0.07、0.04及0.24秒。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T_integrity_live_readonly/validation.json`。这是当前NIfTI服务冒烟，不是新DICOM或四序列模型验收。

## 2026-10-18 文件完整性校验耗时测量

只读测量本机一个已验收模型分析所用的4个NIfTI输入与mask：共5个文件、20.28 MiB；首次顺序SHA-256为0.0178秒，第二次为0.0170秒，摘要重复一致。报告不保存病例ID或路径，见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T_integrity_hash_benchmark/validation.json`。这是一个本机NIfTI样本的文件读取性能量级，不代表更大DICOM病例、并发环境、Docker/Linux或医学效能验收；性能随盘、文件大小与缓存变化。尚无必要为少量重复哈希引入跨请求缓存，避免再次出现内容漂移漏检。

## 2026-10-18 文件完整性同元数据漂移修复

在分析/特征完整性接口中复现并修复：文件内容改动但字节数不变、修改时间恢复原值时，按路径/大小/mtime缓存摘要会漏掉漂移。`checked_digest`现每次读取文件内容计算SHA-256，再决定是否显示当前分析/特征；不重写已成功历史记录。新增同大小同mtime回归覆盖分析与特征API，隔离测试确认漂移后当前结果被隐藏、历史记录和状态文件保持不变。

验证：旧实现的定向复现按预期失败；修复后完整性定向13项通过；当前后端完整回归690 passed、0 failed、4条既有弃用警告。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T_integrity_hash_cache/`。每次核验会重新读取MRI/mask文件，换取内容级漂移识别；对大文件读时影响尚未在真实多序列数据或目标容器环境中实测。未改变正式病例、模型结果或业务数据库内容；本机前后端按原配置正常重启，Orthanc未重启。

## 2026-10-18 18:10：主环境来源核验与源码候选刷新（早前快照）

主CUDA环境20个Conda包均有已登记官方URL/SHA-256；原先4个缓存缺失归档已从对应Anaconda官方HTTPS源下载到独立Runtime证据目录并逐个匹配，当前20/20归档文件哈希均已核验；当前环境未安装/替换任何包。仍有49/54个Python分发没有原始wheel来源，故不能称完整主环境安装锁。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1300_main_env_conda_archive_recheck/validation.json`。

包含更新后环境清单的当时源码候选`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1330_source_candidate_env20/candidate/`共454文件，受限审计无发现，ZIP SHA-256 `e31bf3c3fdc5d4f8bea0fb3f110a9c28f51c9030e5894125f6ef2a88f5dd2119`；解包候选全量后端回归688 passed、0 failed、4条依赖弃用警告。Docker/WSL自动审批阻塞、影像烧录文字人工确认待办和本机服务健康状态见本交接及`CURRENT_STAGE.md`。以上不替代Docker/Linux或真实DICOM验收。

---
## 2026-10-18 18:00：交付候选与 Docker 前提复核（早前快照）

当时内部源码候选已包含更新后的`DOCKER_PREREQUISITES.md`：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1230_source_candidate_post_env/candidate/`，454文件，受限凭据审计无发现，ZIP SHA-256 `2528cc297178d838241f89fab872252b190e4699c3a4dd1c70b029890d55b026`；解包候选全量后端回归688 passed、0 failed、4条依赖弃用警告。证据在同一run目录的`candidate/audit.json`、`candidate/validation.json`和`unpacked-pytest.log`。这是源码交付候选与Windows回归，不含数据/模型/环境，不等于Docker或真实DICOM验收。

环境复核：Windows 11专业版build 26200、31.2 GB内存、硬件虚拟化已启用；Docker/WSL运行环境仍未安装，当前账号非管理员。自动审批拦截了用户级Docker安装命令，命令未执行、未下载、未安装；细节和解除路径见[容器前提](DOCKER_PREREQUISITES.md)及[项目问答](PROJECT_DEMO_QA.md)。若用户未手动安装并接受首次启动协议/完成所需系统功能，月底仍按本机原生验收，E5保留未验。

---
## 2026-10-18 后端全量回归复核（早前快照，后更新为690项）

当前工作树后端全量回归为688 passed、0 failed、4条依赖弃用警告。首次运行将pytest临时目录放在深层nightly证据路径，4个转换作业测试因此触发产品路径长度保护；短路径重跑4项均通过，随后全量以`E:\bfpt2`为pytest临时目录通过。未修改转换逻辑或业务数据。日志：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1120_backend_full_regression_shortpath/pytest.log`；首次诊断：`.../20261018T1100_backend_full_regression/pytest.log`；短路径定向复核：`.../20261018T1110_pathguard_rerun/pytest.log`。本机前后端及Orthanc检查仍健康。

---
## 2026-10-18 当前源码本机服务对齐

隔离启动验证使用当前运行库的独立快照：数据库完整性ok、恢复后行数一致；当前源码根接口、OpenAPI和本地审核会话接口通过。随后按登记PID/启动时间正常停止旧前后端，在保留配置下启动当前源码；严格运行预检通过。当前前端PID 22124、后端PID 24060，仍为5179/8012；Orthanc PID 14640未停止。只读线上复核确认根接口/OpenAPI/转换方案预览路由/前端200、PACS ready、本地审核账户已配置，数据库重启前后完整性与17张表行数相同。证据：E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1040_live_source_alignment/ 和 E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1050_live_source_smoke/。服务观察器16316仍按原计划观察旧前后端PID，计划重启及其退出属于本次版本对齐；不另起观察器或停止Orthanc。

候选四序列图像中的烧录个人信息你暂时无法确认，因此候选仍隔离，未导入、转换或推理。Docker/WSL仍不可用，容器解析、构建及Linux/PACS网络验收未完成。源码候选/215项回归继续适用；月底工程验收不可把以上本机启动冒烟当作真实四序列或Docker验收。

---
## 2026-10-18 后续容器存储与 PACS 网络回归

账户、PACS、转换、阅片派生及隔离路径已跨平台化，Windows 仍限 E:，POSIX 要求绝对路径并保留归属/完整性检查；Compose 显式配置只读派生资料和持久隔离区。PACS 只在显式开关下接受 host.docker.internal，其他主机仍拒绝。解包源码候选回归 215 passed，候选 SHA-256 `2b7ac833366d6f48dababa9a4612c0e2ff8ff95cb8d6ef2a8e906ab02839a702`。Docker/WSL 不可用，因此没有 Compose 解析、构建或 Linux/Orthanc 网络验收。

## 2026-10-18 E5 容器与跨平台存储进展

账户、PACS 配置/导入、转换/审核、阅片派生和隔离路径已改为跨平台绝对路径规则；Windows 仍限 E 盘，POSIX 接受绝对路径并保留路径完整性检查，相关本机回归 214 passed。Docker/WSL 未安装，Compose 解析、镜像构建和 Linux 实测未完成。PACS 客户端仍只接受 loopback，容器访问宿主机 Orthanc 的网关地址需要继续设计并测试。此前源码候选已过期，待重新打包。

## 2026-10-18 分析历史读取错误隔离

当前分析状态请求和历史列表请求并行独立；当前状态API失败时，历史列表仍可显示且错误分区呈现。病例切换迟到响应仍受病例ID与请求代次保护。两个定向Edge场景通过；完整Edge E2E 8 passed/1按设计跳过，Vite生产构建通过，当前5179服务Edge模拟API冒烟2 passed。证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1840_analysis_history_error_final/`和`.../20261018T1900_analysis_history_live_edge/`。源码候选454/454一致、数据库未变，ZIP SHA-256 `a3735d9f4c5b9e22221f4db4ee1820c8ee1377e6f29c347100271a28bd599322`，就绪证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/analysis_history_error_final_v2/readiness/`。未读取或改写业务病例。真实DICOM与目标环境门槛仍未验。

## 2026-10-18 真实分析历史页面只读冒烟

当前5179前端读取8012真实后端的只读Edge检查通过：既有病例页面HTTP 200、历史列表有1条记录、无页面异常和历史读取警告；验证仅保存计数/状态，不保存记录内容，不进行业务写入。证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/analysis_history_live_case_readonly_retry1/`。

# 当前阶段补充：2026-10-18后续核验

## 2026-10-18 M2分析历史页面可见性

分割分析页现在读取`/analysis/{case_id}/history`并显示当前/历史版本与状态；旧成功run只显示为历史元数据，页面不展示其旧结果。Edge合成API场景验证旧结果内容不泄露，1 passed；完整Edge E2E 6 passed/1按设计跳过，生产构建通过，并在现有5179前端服务上以模拟API做只读Edge冒烟1 passed。证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1200_analysis_history_final/`。无真实病例读取/业务写入。

## 2026-10-18 激活后报告与分析历史接口回归

扩展隔离激活回归：切换到新DICOM来源MRI后，旧成功AnalysisRun仍可在`/analysis/{case_id}/history`读取但标记`current=false`；病例当前详情不暴露旧分析/报告，`GET /reports/{case_id}`返回404，历史MRI/成功run/报告保留，旧测量标记为obsolete-input。`test_dicom_conversion_activation.py`模块3 passed、4条既有弃用警告；日志：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1010_activation_history_api/pytest.log`。完全是隔离合成登记与Stub归档检查，不是实际影像或运行中账户验收。

## 2026-10-18 角色审核与显式激活页面流程（合成接口验收）

新增 Edge E2E 覆盖已登记转换版本的四角色展示、本地医生登录、版本摘要绑定的角色审核、当前MRI未改变提示，以及二次确认后激活请求与历史保留/未推理回执。另以隔离API断言旧成功分析标为非当前、旧报告不再由当前报告API返回且历史记录保留。测试均使用模拟接口/隔离数据库，不读取真实影像，也不证明真实病例端到端验收；Edge全套6 passed/1个真实病例场景按设计跳过，激活模块3 passed。日志分别见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1200_analysis_history_final/full-playwright.log`和`.../20261018T1010_activation_history_api/pytest.log`。

## 2026-10-18 16:22 服务稳定性只读观察（进行中）

只读状态脚本UTC 08:22:15确认backend 4108、frontend 21448、Orthanc 14640仍与登记身份一致、分别持有8012/5179/8042监听，health/PACS/account检查通过。已为这三项精确PID+启动时间启动独立观察器PID 16316，UTC 08:22:02启动、预计UTC 14:22:02到期（本机22:22），最长6小时；只记录退出UTC和代码，不重启服务、不写项目/业务数据、不持有开发锁。登记与计划见E:/BrainFusion-Runtime/local/service-observer.json及E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T0820_service_stability/。后续只续读此PID/观察目录；到期后检查summary/events，不重复启动监测。
上一观察器PID 15108已在UTC 09:17:10于10月17日到期，summary为deadline_reached；记录到backend/frontend在UTC 06:43:44退出，退出码4294967295，与同日UTC 06:44的计划版本更新/正常停止时间吻合；Orthanc当时仍存活，监测到期未记录其退出。这解释了该两条观察退出，不解释更早历史事件，也不构成跨夜稳定验收。证据为E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017_urgent_fixes/service-exits-independent/summary.json及当日planned-restart记录。

截至2026-10-18 15:32（北京时间），显式重采样前后端改动已加载到常驻本机服务；服务健康、OpenAPI含重采样选项，Edge重采样页面场景1项通过。上线前完成活动库只读快照，重启后17张表逐行摘要一致，PACS/账户配置哈希未变，Orthanc进程身份不变。当前后端全量回归686项通过（4条弃用警告），前端Edge全套E2E现为6项通过、1个未配置真实病例的报告场景按设计跳过；新增角色审核→显式激活合成场景日志见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1200_analysis_history_final/full-playwright.log`。真实四序列元数据候选已找到，但ACRIN-134、ReMIND-013均未通过烧录文字门槛；ReMIND-110的T2-FLAIR只读元数据检查中33/33实例也缺BurnedInAnnotation。你暂时无法人工确认像素文字，故不能宣称DICOM→AI链路已验。转换材料联合恢复工具16项隔离测试通过，实际转换材料仍为空。

本机Windows原生backend/frontend/Orthanc身份和健康检查通过。Docker CLI不存在、WSL未安装；当前Codex非管理员，普通WSL安装入口未完成且不自动重启。本月底先以原生环境验收，容器/异机范围仍未验。

2026-10-18：IDC公开元数据补筛了7个ReMIND同Study四序列候选的T2-FLAIR，534/534实例均未提供BurnedInAnnotation字段；只查询只读DICOMweb metadata，未取PixelData、未保存原始metadata、未导入或转换。字段缺失无法判定像素内容，用户答复仍是“暂时无法确认”，所以数据候选保持隔离。脱敏汇总：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/remind_followup_metadata_screen/aggregate.json`；解释与范围见`docs/PUBLIC_FOUR_SERIES_DATA_SCREEN_20261018.md`。本次文档增量进入final10候选`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2335_source_final10/candidate/`；以该批实际回归及交付复验为准。

公开数据候选目前包括TCIA ReMIND-013与ReMIND-110的同Study四序列元数据组合，许可均为CC BY 4.0。ReMIND-013首序列176张DICOM均缺BurnedInAnnotation；ReMIND-110 T2-FLAIR的33份只读DICOMweb元数据也均缺该字段，未请求像素或其它序列。你暂时无法人工确认图像内是否烧录姓名、ID、日期或机构文字，因此两例均未导入、转换或推理。另筛到的Brain-Tumor-Progression/TCGA-LGG原始DICOM均需受限许可申请。MP2RAGE角色、其余序列的共同FrameOfReference仍未核实。旧UPENN-GBM候选仍未取得真实同检查四序列UID；配准NIfTI衍生物不能冒充DICOM验收。详见`docs/PUBLIC_FOUR_SERIES_DATA_SCREEN_20261018.md`。

46项回归日志与本机环境检查证据分别位于`E:/BrainFusion-Runtime/results/nightly/2026-10-18/m1_m2_integration/`和`E:/BrainFusion-Runtime/results/nightly/2026-10-18/environment_native/`。月底剩余用户共同时间约26–39小时；首要数据门槛为可合法使用的同检查四序列来源、人工序列角色判断及像素隐私审核，数据不足时不替代为模拟通过。

### 2026-10-18 15:47之后：材料与源码交付核验

## 2026-10-18 22:50：最终7候选与材料快照重新对齐

最终7源码候选459项与当时工作树一致，后端694项回归通过（4条既有弃用警告）。交付复验发现16:10工程材料中的一项源码证据比实际源码早约2.5小时；随后按原只读病例17流程于22:40重新采集源码/API/数据库签名，数据库签名前后相同，重建27项材料索引与ZIP；病例页截图和工程图沿用16:10已审核文件，本轮没有重拍或重渲染。最终7只读交付复验于22:50通过；完整结果：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2250_delivery_readiness_final7_rebound/result/validation.json`；重建材料包：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2240_materials_rebind_final7/`。最终8源码候选459项与工作树完全一致，ZIP SHA-256为`2834625cdc62750a218cbbeff298b629888a6933f752871af8c5b69b5db36eca`；后端694项回归通过（4条既有弃用警告），0项审计发现。最终8只读交付复验于23:05通过：14项实现源码及3项再现工具与当前版本一致、严格本机预检通过、数据库内容签名不变。结果：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2300_source_final8/readiness/result/validation.json`。本段准确状态更新进入final9文档候选：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2315_source_final9/candidate/`。本机服务健康，但Docker/异机、完整环境原始包来源、真实四序列DICOM到AI及研究效能仍未验。

你回复“暂时无法确认”四张图像是否烧录个人/机构文字；未指定某个Study/Series UID，故相关候选继续隔离，未像素检查通过、转换、导入或推理。准确候选及下一步人工确认方式见`docs/PUBLIC_FOUR_SERIES_DATA_SCREEN_20261018.md`与`docs/PROJECT_DEMO_QA.md`。本工程进度不以这一步冒充完成。

### 2026-10-18 15:53–15:57：主环境来源记录补充

新增只读工具`backend/tools/capture_conda_provenance.py`，从当前主环境的已安装Conda记录中读取20个官方包的URL和SHA-256，并重算本地可找到的16个Conda缓存归档（全部匹配记录SHA-256）；其余4个归档未在缓存中。pydicom本地wheel也重新计算并匹配安装记录。54项Python分发中49项仍无原始wheel来源记录，所以这仍不是完整安装锁或异机复建证明。最终来源证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1655_main_env_provenance/cache-rehashed-final/`；已同步[环境清单](ENVIRONMENT_INVENTORY.md)。本轮源码/交付复核将在本批文档与工具更新后重新生成。

---

## 2026-10-18 转换材料联合备份与恢复路径补齐

联合恢复工具现在除转换索引外，还会同批收录同一运行根下的四类转换材料：方案草稿/原始DICOM采集、作业输入与状态、转换输出，以及索引；每个文件进入私有Runtime快照并逐文件核SHA。发现未完成的`.prepare-*`暂存时拒绝生成成功快照。恢复到独立目录时会重定位索引、作业和原始文件清单中的服务器路径，并重算被重写的作业原始文件清单SHA，防止恢复后作业仍指向旧目录。旧联合包保持兼容；恢复报告仍不会把文件恢复说成服务/临床/AI验收。

本机只读盘点：`E:/BrainFusion-Runtime/local/dicom-conversions.json`不存在，`dicom-conversion-plans`和`dicom-conversion-outputs`不存在，`dicom-conversion-jobs`存在但为空；没有可交付/恢复的真实转换任务、四序列草稿、采集源文件或转换输出。下次取得符合条件且来源许可清楚的同检查四序列后，先按病例页面完成预览与原文件捕获，再启动转换；对照原始实例字节、转换输出和角色审核逐项实测，随后再执行联合备份/独立目录恢复核验。不得以合成测试代替该验收。此次隔离恢复用例16 passed；证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/conversion_recovery/`。

---

## 2026-10-18 网页创建四序列方案与服务更新

病例PACS面板现可从已关联的同一检查中明确选择T1c/T1n/T2w/FLAIR四条不同序列，使用本地医生会话与CSRF检查元数据空间；证据栏只收不含患者信息的编号。方案检查通过后，服务器重新核对病例/归档关联及序列版本，再从固定归档逐份读取、校验并保存原始DICOM字节和SHA-256，创建持久排队作业。浏览器不提交文件路径，也看不到服务器目录；创建只排队，医生还要显式点“启动转换”。失败不会留下本次半截原文件副本，不激活MRI或运行AI。

验证：新增方案服务/接口用例与持久启动回归共16项通过（4条已有弃用警告）；实际Edge页面用模拟接口完成四角色选择→预览→创建排队作业，0页面异常、客户端无路径字段；Vite构建通过。常驻backend/frontend已更新到PID 29080/20576，Orthanc 14640保持原进程；17张数据库表的逐表/逐行摘要和完整性重启前后相同，新接口已加载，匿名请求401。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/web_conversion_plan/`。

当前归档只读库存为1检查/1序列，因此真实四序列方案、原文件获取、转换、角色审核、激活、模型/特征/报告仍没有真实来源可验；AI桥接保持关闭。M1工程入口已接通但整条真实链未验收；M2来源联动/历史与旧结果、M3真实四序列、M4联合恢复/交付、E5容器/目标环境及带教/演示均继续保留。下一有效工作先继续现有材料恢复与交付余项，并在合法同一检查四序列可用时按页面流程实际验收；不拿合成数据替代。

---
---

## 2026-10-17 15:27 B2审核输入守卫与S4当前源码候选

run_id 20261017T1458_b2reviewedinputguard、20261017T1524_b2workerretry、20261017T1550_s4sourceguard_handofffix。分析提交现在校验当前激活MRI的四个NIfTI与审核SHA-256完全一致，并把期望哈希绑定到任务；分割工作器加载前/后校验，结果返回后再次守卫。隔离契约测试9 passed、4条既有弃用警告：审核激活版本被真实分析API选择、AnalysisRun绑定该MRI、输入漂移409拒绝、错误输出哈希不落为当前mask/报告。未运行模型推理、未改正式病例。首次测试夹具导入遗漏及修正后重跑证据均保留。

刷新内部源码候选：444文件，原文件3,079,832字节；ZIP 1,431,621字节，SHA-256 2fd79cdcd51ef30087ad3ffd769edb2eaf1ea94ded06a5136b88bcadb371dbfd。候选逐文件审计/解包校验通过，解包副本相同9项回归通过。仅内部源码包；无数据库、影像、模型、环境或私有账户/PACS配置，不发布。证据 E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1550_s4sourceguard_handofffix/verification.json；初次匹配脚本短路和修正脚本保存在1540_s4sourceguard及1545_s4sourceguard_retry1。

真实门槛保持：本机PACS只读库存为1项MR检查/1条MR序列，不足四序列角色映射；无真实转换、审核激活或DICOM来源下推理/报告，P3受阻，未以合成契约验收代替。服务未重启，backend/frontend/Orthanc PID 6744/27024/12432保持健康；退出观察PID 15108仍运行，原截止UTC 2026-10-17T09:17:10.678743Z，不自动重启、不持锁。

下一步：若取得许可明确、同一检查含可审计T1c/T1n/T2w/FLAIR序列和来源材料，按B1真实角色复核→B2转换/激活→分析任务进行真实验证；否则不重复下载/合成测试，先做可独立的S5/S6系统演示和论文材料准备，且培训/预演等待用户参与。


运行边界与时间更正：本次B2哈希守卫和15:50源码候选只代表当前工作树/候选验收。常驻backend PID 6744于北京时间14:43启动，uvicorn命令未启用reload；健康服务未重启，因此新哈希守卫尚未加载到活进程，不声称线上本机API验收。下次正常计划后端版本更新时才加载该改动并复验；本轮遵守健康无异常不重启。
本轮若干E盘证据目录run_id的HHMM后缀晚于实际墙钟，是我错误估算生成时间；目录唯一、内容与测试记录保留，但这些后缀不作为执行时刻证据。当前更正记录按UTC 07:27（北京时间15:27）形成。后续每个run_id将先重新读取系统UTC。

## 2026-10-17 15:33 B2审核输入绑定与后台执行校验

run_id 20261017T1458_b2reviewedinputguard / 20261017T1524_b2workerretry。静态核对发现转换激活时虽保存四个NIfTI SHA-256，但分析提交端未核对当前文件是否仍为审核版本，存在激活后字节漂移仍可排队的缺口。现已补提交前来源哈希核对、将审核哈希清单随分析请求传递、工作器加载前/加载后复核，并在执行结果返回时拒绝不匹配哈希；旧MRI/分析/报告历史与过期标注的处理保持既有语义。

隔离工程测试验证：激活版本被现有分析API选中、AnalysisRun绑定激活MRI ID并收到准确的四序列审核哈希；激活后修改单序列字节会在队列前返回409且不重复提交；模拟工作器输出错误哈希时任务失败、不生成当前mask/报告。相关后端测试最终9 passed、4条既有弃用警告；未运行MONAI/GPU推理，也未改正式病例或服务。证据 E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1458_b2reviewedinputguard/ 与 20261017T1524_b2workerretry/。首次测试夹具漏导入Path的失败和修正后重跑均保留。

真实DICOM→AI仍受阻：当前本机真实PACS只有1项MR检查/1条序列，不具备四角色映射条件；不猜角色、不声称真实审核/转换/推理。服务backend/frontend/Orthanc仍为6744/27024/12432且健康；只读退出观察15108实际进程仍在，截止UTC 09:17:10.678743Z（北京时间17:17:10），无自动重启/不持锁。

下一步：刷新内部源码候选，使其包含本次审核字节门槛；继续B1/B2组件审阅，真实DICOM门槛仍需可审计四序列样本与来源/角色确认，随后按该输入做真实转换和模型闭环。

## 2026-10-17 15:21 S3/S4前后端源码组合及B1真实归档门槛核实

run_id 20261017T1521_s4b1handoff。当前源码/CPU后端环境已在全新E盘同机前缀重建，strict只读运行预检通过；backend针对五组B1/B2、来源与联合恢复测试25项通过。当前源码前端在解包副本使用E盘Node24/npm11缓存离线安装397包并构建成功，随后Microsoft Edge实际运行B1审核/激活交互夹具：两项检查通过、0页面异常，请求只由测试路由截获，不产生真实业务写入。Vite提示Cornerstone codec的fs/path externalized及大chunk；npm提示3个旧依赖与2个未批准生命周期脚本，不影响本次构建结果，范围不是浏览器DICOM验收。证据分别见1516_s4freshcpu、1509_s3freshpreflight、1513_s4frontverify、1518_s4edgeverify。

新增本机真实归档只读结构核实：已有1项MR检查、1条MR序列；只保存Study/Series UID哈希、模态和计数，未取像素/未导入/未审核。它满足普通真实DICOM浏览已有验收，不满足四序列模型映射；不能给唯一序列猜角色。结构证据见 E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1520_b1pacsinventory/pacs-structure.json。B1/B2真实输入激活与B3/B4仍需同一真实四序列检查及可审计的序列/采集来源确认。本机服务仍健康：backend/frontend/Orthanc PID 6744/27024/12432；退出观察15108按原计划至UTC 09:17:10（北京时间17:17），不自动重启、不持锁。

下一步：检查审核后激活是否被真实模型任务入口消费，以及输入替换/旧结果失效是否原子绑定；只做代码与测试契约核查，不伪造四序列运行。若接口已接线，再转到可获取的真实四序列来源/人工角色确认门槛；不盲重试旧网络或重复合成测试。
## 2026-10-17 15:10 S3/S4全新同机CPU前缀重建及只读启动预检通过

run_id 20261017T1510_s3s4handoff。用已验收的离线Conda/52-wheel缓存与官方SHA匹配的pydicom 3.0.2 wheel，在全新E盘前缀E:/BrainFusion-Runtime/envs/runtime311-cpu-delivery-20261017T1516_s4重建当前源码锁包；72个缓存文件校验通过，追加pydicom 3.0.2后pip check为零问题。新版源码444文件/3,072,555字节；锁包SHA c98437fd48d6628a146e01cdcffd67810c09b721050fbe342dfa82359b4a46fb。五组B1/B2、来源与联合恢复测试在新前缀解包源码副本通过：25 passed, 4 warnings in 6.84s。随后由新解释器对当前登记13路径和已登记运行根执行严格只读启动预检：status passed、errors/warnings均空；SQLite只读integrity=ok、模型来源与研究复现门槛通过，独立特征worker版本/兼容记录通过。未导入app.main、不迁移或写DB、不推理；CPU设备报告CUDA不可用为预期。证据：E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1514_s4freshcpu/current-source-locks/validation.json、E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1516_s4freshcpu/verification.json、E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1509_s3freshpreflight/。

三次前缀准备/参数校验在安装器创建新prefix前退出，原因与输出留在对应run目录；没有部分prefix。验收前后backend/frontend/Orthanc仍为6744/27024/12432，正式CUDA主环境与正式服务数据库未切换。此项是同机全新CPU依赖前缀/只读运行根预检，不是新机器、容器、模型推理或真实DICOM→AI验收；DICOM转换索引目前不存在，真实角色审核/转换/激活及B3/B4仍待输入与端到端证据。

下一步：核对本轮新prefix、源码包与现有前端Node24候选/锁的一致性及CPU交付边界；保持正式服务不切换。真实四序列DICOM来源仍未到位时不重复合成验证。
## 2026-10-17 15:03 S4当前源码候选与CPU候选环境组合验收

run_id 20261017T1503_s4handoff。最新源码候选在既有独立runtime311-cpu-candidate（CPython 3.11.17）解包副本中完成五组B1/B2、来源与联合恢复定向回归：25 passed, 4 warnings in 5.37s；本轮测试使用E盘隔离SQLite、私有配置路径和临时目录，未写服务病例/归档或模型。构成核对：核心依赖13/13、研究依赖5/5、本机观测依赖16/16、DICOM预检1/1与主CUDA解释器版本匹配；受支持PyRadiomics工作器11/11与独立Python3.11.17匹配；两边pip check退出0。历史宽泛requirements.txt不作为安装锁，未用于升级主CUDA。Runtime登记13路径中12存在，DICOM转换索引路径尚无文件（当前无转换记录时可选）；不能据此称转换恢复/激活验收。详细版本和路径类型见E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1502_s4roles/composition.json，测试日志/隔离目录见20261017T1506_s4cpuunpack/。

范围边界：这是已安装同机CPU候选对当前源码包的组合验证，不是全新prefix重建、异机/容器部署或真实DICOM→AI验证。下一步优先核实当前CPU交付引导缓存与最新pydicom增量是否具备一次全新E盘prefix的离线重建条件；旧10/10 prefix不得当成最新版本。保持服务PID不变，不改正式配置。
## 2026-10-17 14:48 S4源码候选
当前内部源码ZIP已含B1/B2更新，解包副本五组相关测试通过；不是干净环境安装或发布。活动本机服务API路由已加载，PACS和账户健康，真实匹配四序列转换仍无输入。证据 E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T144838_s4source/verification.json。

## 2026-10-17 14:44 当前本机运行候选
B1角色审核及B2审核后输入激活路由已加载至常驻API；PACS/账户/前后端健康通过，活动库备份后17张既有表逐表计数一致，Orthanc未重启。无真实转换/激活/推理。证据 E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1444_b1b2routes/verification.json。

# 当前状态：S4源码候选已于14:48生成并通过解包回归；B1/B2路由在本机已加载，三服务健康；真实DICOM到AI、干净环境/异机/容器复建仍待验证

## 2026-10-17 14:16 正式交付与用户掌握门槛

[交付及带教计划](PROJECT_HANDOVER_AND_FORMAL_DEMO.md)纳入用户要求：完成系统并冻结版本后，带本人熟悉项目、独立操作/讲解与两次预演，再给导师正式展示。G1–G8剩余与学习验收分开，未实际带教不标已掌握。下一步仍是常驻新API/配置/迁移/真实DICOM链与可复建交付，提示词v5.1。

## 2026-10-17 13:30 S3配置契约增量

runtime.json v1八路径保持兼容；v2增加五个E盘路径键供PACS、导入登记/作业、本地账户、DICOM转换索引注入并参与进程登记。定向配置测试结果见20261017T1330_s3runtimev2。没有切换当前服务、复制私有配置或重启。真实v2恢复目录试运行、新环境复建与P3真实四序列AI桥仍未验。


## 2026-10-17 12:53 S3安全验证纠正

首次CPU候选当前源码import触发工作区E:/BrainFusion-AI/backend/brainfusion.db的幂等schema migration（日志列出mris.input_source与source_provenance_json）。库内事后只读计数为15病例、12 MRI、6分析，无迁移前快照，故不声称逐字节未变；未回滚，迁移后副本与计数保存在1253_s3isolation。核对活动服务登记所指的restored-validation.db为不同路径，19病例/17 MRI/24 runs，未被这次操作修改。随后在显式新建的E盘隔离SQLite库重新导入，17表/零病例数据，pydicom与B2路由通过。以后应用导入检查必须明确隔离DATABASE_URL。
# 当前状态：B2隔离激活工程验收完成，S3 CPU候选补入固定DICOM依赖；真实DICOM到AI仍受阻

## 2026-10-17 12:51 S3候选依赖增量

已验证E盘缓存pydicom 3.0.2 wheel哈希与PyPI发布一致，在runtime311-cpu-candidate中离线追加该唯一依赖；候选仅新增一个包，pip check和当前源PACS/B2路由导入通过。主CUDA、特征工作器、服务和正式库未改。既有402文件源码ZIP对B1/B2已过时，12个路径差异已记录但未重打包。P3依旧没有真实审核者/匹配四序列闭环证据。详见最新交接。
# 当前状态：B2隔离激活组件已通过工程测试，真实DICOM到AI仍受阻

## 2026-10-17 12:26 B2组件验证

真实DICOM角色审核后切换AI输入的工程路径已建立：审核/转换版本与哈希绑定、审核会话门控、切换前PACS来源字节复核、空闲时切换当前MRI并保留旧分析/报告、失效旧标注；每次切换产生新MRI来源记录，且不启动推理。隔离后端21项、Edge155合成交互检查与runtime目录Vite构建通过。常驻后端OpenAPI未加载新路由，本批没有重启健康服务、操作真实病例或运行模型。真实四序列身份/匹配网格/本地实审尚无证据，P3仍受阻。当前服务/观察身份与下一步见[Nightly交接](NIGHTLY_HANDOFF.md)。
# 当前状态：B1审核API与现有页面夹具交互通过；真实来源和AI激活待验

## 2026-10-17 11:52 B1可见交互验证

PacsPanel角色审核弹窗和Edge155合成路由夹具验证通过，Vite独立构建通过；证据位于E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1144_b1review_ui_final。后端组件/API定向3项通过（归档来源使用测试替身）。UI夹具不能代表真实PACS/医生审核；当前常驻后端仍未加载新路由，没有激活AI/MRI。B1仍待真实来源/实审，B2转换作业及原子激活未做，P3受阻。

## 2026-10-17 11:45 B1角色审核API组件

[B1审核组件验收](B1_DICOM_ROLE_REVIEW_VALIDATION.md)：新增版本/四角色绑定的本地医生角色审核接口和E盘追加审计日志，定向3项通过。正向来源回执由测试替身提供，非真实归档验收；专业资质不作证明，AI输入未激活、当前PACS未重启加载新路由。下一步接PacsPanel可见操作，再做真实样本/角色门槛；S1观察继续。

## 2026-10-17 11:17 紧急修复通过

[本批修复](URGENT_FIXES_20261017.md)：S0缺pydicom契约统一，后端全套639通过/0失败；后台启动与开发清理组解耦的实际控制测试通过，三个服务已按原配置恢复，真实两来源Edge六组回归通过。正式17表19病例/路径保持。只读status_local可核当前健康；新有期限退出观察见最新交接，历史根因/跨夜稳定未冒称完成。下一项交付收尾/B1–B2，P3/E5/R1等数据环境门槛保留。

## 2026-10-16 16:19 全面核查与收尾计划

当前三服务正常、原退出观察仍在，根因未明；本轮635项后端检查634过/1失败，缺pydicom的旧可选契约与当前必需依赖冲突，需S0处理。正式17表19病例/选定配置指纹/八路径保持；既有六组Edge及43文件dist字节证据已核，不当本轮重验浏览器。

[剩余工作计划](REMAINING_WORK_PLAN_20261016.md)已列S/B/E5/研究/论文工时与条件；[任务规程](DAILY_SYSTEM_COMPLETION_TASK.md)已更新v4。先S0/S1稳定性和已知失败，优先实际DICOM-AI接线与交付；B1/B2可先组件开发，真四序列端到端仍需匹配数据。既有P1/P2与F/E证据保留，不宣称全系统交付或更新了应用计划配置。完整本轮证据和下一步见最新交接。

## 2026-10-16 15:38接续：服务恢复与病例导航修复

按15:30人工交接暂停离线研究扩展，先[恢复原三服务并修复导航](LOCAL_SERVICE_RECOVERY_VALIDATION.md)。当前后台25128/前端14984/Orthanc21924，8012/5179/8042身份/健康/账户/PACS及匿名归档401通过，原17表19病例/四配置八路径保持。无效病例链接不再发422/残留旧患者，旧响应和医生意见不能覆盖新病例，错误可返回管理。Edge155实际六组导航/两来源三视图/零写及最终构建通过。

历史15:17请求完整URL与三服务退出原因仍未知，不把恢复当根因修复。只读退出观测PID22672截止UTC2026-10-16T09:54:21.2478499Z，记录未来退出码、不持锁/重启/改业务数据；有这一诊断任务，无下载/模型任务。下一优先核观测及服务、固定两来源人工演示与最小修复交付，暂缓六法校准，不重复旧数据恢复/导入/全包构建。


## 2026-10-16 14:32接续：训练侧准备组件与六法融合区间

[R1准备](R1_TRAINING_PILOT_VALIDATION.md)冻结原训练侧10人/40 MRI、明确原152人仅归档清单；真实可恢复范围/空间工具10不同检查和4实际CLI拒绝通过。实际官方API TLS及Windows DNS均失败，无新MRI/推理/特征，R1整体仍受阻，已停止不变条件重试。随后[R4六法区间补充](R4_FUSION_INTERVAL_VALIDATION.md)完成22已观察人/六法2000共享抽样、72000独立指标核对与四配对差；熵权减平均AUC -0.074380、条件区间[-0.206612,0.024793]，不宣称优效/等效。R4整体进行中，分割/全自动参考队列与独立评价未完。

正式17表/配置/三服务保持，无长任务/无需立即操作。下一独立项先冻R2六法验证侧校准；仅官方网络/材料有新证据才续R1 v2，不重训R3、重跑五例或重复下载失败。


## 2026-10-16 13:31本轮结束：统计局部验收与研究源组合

[R4局部验收](R4_STATISTICS_VALIDATION.md)完成22人/24向量患者级区间、验证侧12温度和792个体逻辑解释，288000指标独立核验；12条件校准Brier均变差，主差退化不作等效。[E6研究源码增量](E6_RESEARCH_SOURCE_DELTA_VALIDATION.md)补研究协议漏收，408→429（4改21增），独立组合75检查及7实际CLI拒绝通过。未激活产品或改正式17表/配置/三服务；无长任务。R4/R2/P4/E6整体进行中，R1/P3/E5等门槛不抹去；下一优先R1已有MRI与训练侧10–20例同协议队列准备，先核清单/角色并冻结，不重复旧研究训练。


## 2026-10-16 13:31接续：R4患者级统计/校准/解释局部验收

run_id `20261016T133509_r4stats`。[R4局部验收](R4_STATISTICS_VALIDATION.md)：事后探索协议先于本批计算冻结，22已观察患者按三种子均值，24向量/2000次共同类别分层患者bootstrap；12温度仅21公共验证人拟合并先写盘冻结。14不同用例分批/7真实拒绝/独立288000指标单元及792个体逻辑解释核对通过。主FedProx-FedAvg AUC差区间[0,0]标为退化，不作等效；12条件Brier校准后全部变差，负结果保留。

R4整体进行中：全队列分割空区域/失败仍not_evaluated，R1同协议自动/参考队列、临床极性与独立评价未解。未激活产品/模型/latest，正式17表19病例/配置/路径与三服务保持，无长任务。下一独立小批E6补新增研究源码/精确公开协议白名单与增量交付，旧408文件组合早于R2–R4不冒称包含新能力。


## 2026-10-16 12:28接续：R3预定完整轻量联邦模拟

本窗另同步FEATURE_OVERVIEW与POST_SPRINT_PLAN：当前新增能力明确为离线研究、不切研究页/正式模型；旧10/07工时和原型待办标为历史，避免误把已验R2/R3重复排期。未据此新增患者/实验计数或承诺日历工期。

run_id `20261016T123110_r3full`。[R3协议/验收](R3_FULL_VALIDATION.md)在明确本机参考掩膜表格探索范围已验收：先冻三个种子、IID/训练标签偏斜、同构23参数逻辑模型、相同9,800样本梯度预算；六方法含Centralized/Local-only/FedAvg/FedProx/旧TOPSIS/熵权TOPSIS，共36方法条件。25首批+17最终检查含重叠，26不同用例分批通过；7来源/角色/预算拒绝通过，独立重核36总体+108中心指标与792重复预测，仅22人。

全部拟合/写盘冻结后才评价；共享训练预处理/21人公共验证假设明确，单类别/空中心null及最差定义数保留。六条件FedProx/FedAvg AUC差均0，参数不同；不选优/激活或推等效/临床结论。通信22,080 bytes/联邦方法仅参数估算，非真实流量/隐私。最终CPU全任务3.1708秒，不外推MRI推理规模。

原17表19病例/四配置/八路径、旧科学源码/模型/latest及后台27968/前端25228/归档15488持续保持，健康/PACS ready；无长任务/无需立即用户动作。R1事实/同协议队列、R2完整自动/参考对照、R4统计解释及P3/E5/P4/E6剩余独立保留；没有宣称第一阶段或完整研究版交付。下一独立项R4先冻结患者级统计/配对比较与实际逻辑模型解释规则，不把种子当患者。

## 2026-10-16 11:27接续：R2敏感性与缺模态工程消融

run_id `20261016T112909_r2ablation`。[补充协议与验收](R2_ABLATION_VALIDATION.md)：先冻结配置/协议，仅21验证人矩阵生成40变体，再用旧已观察22人概率做21固定分支权重点及六场景×六方法诊断。15新组件测试/7来源与冻结拒绝通过；不重跑上轮28项、不训练/重分/激活/改旧熵协议或产品/论文结论。

三项删列仍[0,1]；36指标扰动中6种改变分支权重，最大变化0.360680。792条重复方法场景记录完整保留总分母，204为模拟失败条目而非独立患者：全缺每方法22/22失败且指标null，单例全缺21成功/1失败，单分支基线不能借另一模态冒充成功。全部是事后描述性/合成缺失，不选网格最好值、不推临床可靠性。

三服务仍原PID27968/25228/15488和UTC02:31启动时间，API8012/页面5179/归档8042，健康/PACS ready；17表19病例全行/四配置/八路径及服务登记SHA保持，本轮未再启停。无下载/训练/推理/提取/构建长任务，无需立即用户动作。R2整体仍进行中，同协议自动/参考完整队列及R4/独立评价未完，P3/E5门槛保持。

下一轮转R3完整轻量模拟：核服务/反馈/锁后读federated.py与已有FedProx组件，先冻结同构模型/三种子/患者角色/IID与Non-IID/公平预算，再补Local-only/FedProx等；不重复已完成R2诊断或用原22人选优。详情、证据、抽查见本轮报告及NIGHTLY_HANDOFF。

## 2026-10-16 10:28接续：R2熵权独立组件、探索性负结果与服务恢复

R2实现run_id `20261016T101158_entropy`（UTC02:08开工、10:11建目录、10:21完成代码/验证；02:26心跳打断整理），本次续接run_id `20261016T103011_resume`，UTC02:28:59重新核对。已先冻结协议，实现独立熵权/冻结状态/缺分支回退，22组件+5旧研究检查通过，补零距离容差1项通过，共28不同用例/4既有警告；5来源/角色/覆盖拒绝和零距离运行时核验亦通过。[协议及当前验收](R2_ENTROPY_VALIDATION.md)。

只读复用原受信模型和98/21/22拆分，核源CSV/模型/名单/特征顺序/验证指标及22人原预测，再冻结21验证人的熵权并重载。六方法同人同事件；旧/熵权TOPSIS均[0,1]，探索22人AUC0.818182，平均0.892562、固定0.6/0.4为0.900826；保留没有优势的结果。参考掩膜/已观察拆分，原始0/1临床极性未知，无训练/重分/新模型激活/产品或论文结论更新。R2整体进行中，不宣称正式独立评价或完整第二阶段。

中断后10:28发现原三个服务均已不存在且端口空闲，原因未知（非OS重启证据）；保留日志/登记，正常既有脚本恢复原CUDA/八路径/四配置。当前后台27968/2026-10-16T02:31:46.4457727Z，前端25228/2026-10-16T02:31:46.902061Z，Orthanc15488/2026-10-16T02:31:34.9049114Z。API http://127.0.0.1:8012，UI http://127.0.0.1:5179/case/19 与/workstation/17?viewer=cornerstone，本机鉴权归档8042；PACS ready/账户configured，原192元数据/网格、匿名401、前端200与服务PID/启动时间/端口复用通过。17表/19病例全行、四配置SHA及原八路径保持；未改产品启动代码、未安装/提权或重试被拒环境动作。

已改：新增backend/app/research/entropy_topsis.py、backend/tests/test_entropy_topsis.py、backend/tools/compare_entropy_fusion.py、docs/R2_ENTROPY_PROTOCOL.md、R2_ENTROPY_VALIDATION.md；旧topsis/experiment逐字节保持。同步本交接/清单/阶段/研究协议/进度/日报。无新用户产品反馈，不编造REVIEW_FEEDBACK。原未提交实现保护，无提交/推送/重置。

实现证据E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T101158_entropy：冻结SHA、27测试/补1、5拒绝/零距离、observed-comparison-final四产物与13个输入/源码SHA、首次失败日志。恢复证据E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T103011_resume：原日志/登记、前后数据guard、实际启动/复用、recovery-validation/final-services。失败：两次PowerShell参数拆分0测试、两个退化夹具预期错误、恢复验收脚本误读归一化序列字段；均保留非零退出/日志，按实际接口/数学上界修正后通过，没有放宽生产保护。

当前无下载/训练/推理/提特征/构建长任务；常驻应用不占开发锁。日志Runtime/local/backend/frontend out/err，归档E:\BrainFusion-Runtime\orthanc-local\logs\20261016T023134868Z。旧进程退出原因尚无证据；若再发生，先核新日志/进程退出来源，不循环启停。用户无需立即动作。未重导192/复制650/做新PDF/重复浏览器，不把接口恢复写成新的浏览器验收。

未完：R2验证侧准则删除/权重扰动/患者缺模态消融、完整同协议自动/参考队列对照；R1临床极性/预训练重叠与独立队列，R3完整多种子联邦，R4患者区间/校准/解释。P3真实匹配四序列/E5系统授权仍受阻；P4/E6异机/可见人工等剩余保持，既有本机部署不再循环重跑。动态质量权重无代理继续延期。

抽查最多三步：①看R2_ENTROPY_VALIDATION及28测试与六方法负结果；②看observed-comparison-final/comparison.json的21验证/22探索、SHA和未激活；③当前UI上述两来源只读查询/切序列，原正式记录保持，恢复API不是新截图验收。

下一轮第一步：先核恢复后服务是否仍在及最新反馈/锁；读已冻结R2协议和observed-comparison-final，仅用已登记验证矩阵预先冻结准则逐列删除/权重扰动规则，补来源可追溯稳定性与缺模态消融；不按22人结果改熵方案/调参，不因R1临床解释条件拖延独立工程。源码408交付组合是本轮新增研究代码之前的历史，未重新打包。

## 2026-10-16 08:13接续：E6直接CPU/PACS HTTP与重启回原

run_id `20261016T081638_cpulive`。已实现受固定轮子/基础解释器/293文件字节指纹约束的`-PacsRuntimeLayer`，直接CPU Python持有服务PID/端口，venv重定向仍拒绝，额外模块/.pth/pyc/篡改不接纳。五项边界检查和五项源码检查通过；真实Edge155 headless首启/实际服务重启后两来源三视图/已存相机窗值、192帧/36既有距离、19病例及代表NIfTI科学API、恢复账户登录/旧Cookie失效/重登退出、原7历史/actor/报告SHA均通过，业务写0。正确复用/漏声明拒绝与正常停止/回原也实际验证。

[当前运行组合证据](E6_CPU_PACS_LIVE_VALIDATION.md)明确本轮使用原持续运行Orthanc，归档未重启、未重新复制650/导192/新推理/特征/PDF或安装依赖。正式17表和已恢复17表/7复核、52基环境元信息与RECORD、293补充文件保持；finally回原CUDA/八路径/四配置，PACS ready/账户configured。当前源码9文件进一步增量组合408文件校验通过，冻结ZIP不改；不是独立新机/容器或四序列DICOM AI验收。

P4/E6整体仍进行中，P3/E5及异机/可见人工条件仍保留；本机上述子项已验不循环重跑。下一轮转R2独立熵权融合工程，先读冻结协议与现有topsis实现/队列角色，只有证据后才变更展示/论文结论；不宣称第一阶段完整交付或已正式进入完整第二阶段。无需立即用户动作，无长任务。

## 2026-10-16 07:16接续：E6当前CPU/PACS命令行依赖与启动身份保护

run_id `20261016T071748_cpupacs`。补requirements-core必需pydicom3.0.2和httpx/pydicom启动前检；复用可信52包CPU基环境，只建小型venv并从原已验缓存安装这一包，新53包CLI实际只读模型/研究/数据库前检、隔离app17表/匿名状态和128相关检查通过（4既有警告），原主4项账户快照回归通过。原CPU/CUDA/worker/正式17表与原服务保持；没有重装52轮子、重抄650或导192/新推理/特征/PDF/前端构建。

首轮127通过/1失败已因果复现为测试手工加入无domain重复Cookie遮住登录，不是账户恢复数据丢失；改成保留原作用域Cookie后通过，生产鉴权未放宽。实际发现Windows venv launcher PID不同于执行进程，现start_local在任何服务动作前明确拒绝这类入口，原直接解释器实际ReuseExisting正常。本机CLI补齐不等于HTTP联合/异机部署，下一步接通有来源约束的直接解释器补充模块路径或可信父子进程管理，再在既有恢复副本验证。

[操作/证据与限制](CPU_PACS_RUNTIME.md)明确基环境仍是外部前提。保留06:15冻结402源码ZIP，8文件源码增量按旧/新SHA实际组合成404文件目录；没有再压整包。P3/E5原条件不变，P4/E6仍进行中，无需立即用户动作，无长任务。

## 2026-10-16 06:15接续：当前源码候选及CPU环境差异

run_id `20261016T061912_source`。E6[当前源码候选](E6_SOURCE_CANDIDATE_VALIDATION.md)子项已验：402文件/逐文件SHA和实际ZIP解包、128相关后端检查（4既有警告）、明确8012 API的43文件构建及六个当前图稿/公开指南；私有数据/环境/账户密码排除、实际三密码无泄漏。正式17表/配置/登记与原三服务保持，不切库/导入/推理/特征/PDF或新安装。旧10/10源码ZIP仅历史，当前包亦不是独立安装器。

接续实际核对旧CPU交付环境缺当前pydicom3.0.2，其余本轮17项观测除预期torch CPU/CUDA角色外相同；不能把旧52轮子锁叫作当前环境完整。下一步复用官方缓存/SHA补当前CPU依赖增量并独立验证，不重抄650或重探来源。P3/E5仍受阻，P4/E6整体和研究R项未全完，无需立即用户动作，无长任务。失败的活SQLite文件哈希读取和合成URL凭据审计均保留，改用只读全表签名/运行时合成URL后通过，扫描规则未放宽。

## 2026-10-16 05:18接续：含账户19病例完整数据组合恢复

run_id `20261016T052133_fullaccount`。E3/P4/E6的[本机完整数据组合子项](E6_FULL_ACCOUNT_RECOVERY_VALIDATION.md)已验：19病例/17表、650应用文件521478562字节、196归档配置、5导入文件及原两账户，真实CLI新备份/恢复到独立目录，模型/研究/产物路径完整迁移；真实192实例SHA/关联、NIfTI两病例与DICOM、科学API/保存视图及账户复核/重启/幂等通过。原正式数据、650原文件及归档/账户保持，已回正式服务。

这是一轮新完整数据组合，区别此前最小2文件DICOM/账户接线；不是代码/二进制/环境独立安装包。源码、Python/Node环境、Orthanc程序/插件及再导入所需已复核源材料仍为明确外部前提，已记录实际本地依赖；P3/E5和整套交付剩余不冒称完成。无新推理/特征/PDF/导入/下载/训练/产品构建。

## 2026-10-16 04:13接续：分层性能与交付范围纠偏

run_id `20261016T041517_viewperf`。已装Edge/只读真实两来源新增[P4分层观测](P4_VIEWER_PERFORMANCE_VALIDATION.md)：NIfTI/DICOM初次三视图分别2.295/4.894秒，查询/切片/切序列与Windows进程工作集/私有提交/页面堆分开，192真实帧完整载入，退出engine/cache0、业务写0。新浏览器禁HTTP缓存但OS/服务可热，单病例/固定次数不作性能保证；旧导入/AI/特征计时按窗口引用，未重跑。

接续E6重写[当前范围/浏览器矩阵](RELEASE_SCOPE.md)，修复旧10/10仍把已授权实现的成组DICOM/PACS写为排除、演示页仍称Edge落库/PDF未验的问题；旧范围逐字节归档，固定演示与启动复用说明同步。实际现有服务复用PID保持，原17表/八路径/影像/账户/配置不变。P4/E6整体未完，P3/E5原条件保留，无新PDF/导入/下载/AI/产品构建或长任务。

## 2026-10-16 03:08接续：Edge NIfTI关闭恢复与工程图稿

run_id `20261016T030947_edgenifti`，对应10/15晚至10/16凌晨。[Edge NIfTI保存/关闭恢复](P4_EDGE_NIFTI_VALIDATION.md)已验：真实三平面毫米距离落库、T1n/隐藏原mask与三相机/窗值保存、完整关闭重开、四序列物理点一致、删除后再次关闭保持空及显式Canvas回退。仅副本最终新增一个视图，原17表全行/八路径、四MRI/原mask及原账户/归档配置保持。

接续E6生成并实际渲染/查看[当前架构与DICOM关系两张图](E6_ARCHITECTURE_FIGURES.md)，各有SVG与PNG，明确真实四序列桥受阻、声明关系/运行时核对和库外账户，不扩大研究结论。P4/E6整体未完，P3/E5原条件保留。无新PDF/导入/下载/推理/特征/训练/产品构建；无需用户立即动作。

## 2026-10-16 02:07接续：Edge复核、身份PDF与关闭恢复

run_id `20261016T021054_edgewrite`，对应10/15晚至10/16凌晨。已装Edge155 headless与E盘独立持久配置完成两批真实行为：本地账户另存第6条复核、身份文本三页PDF逐页查看、完整浏览器进程关闭重开保留登录/记录、显式退出后再重开保持退出；随后真实DICOM三相机/窗值保存、28.274mm工程距离保存/关闭恢复/删除及来源复核过期通过。仅写本轮数据库副本，旧36距离/6复核保持，仅另存一个视图版本；原正式17表全行/八路径及原账户/登记/源副本不变，正式PACS ready。详见[Edge持久化验收](P4_EDGE_PERSISTENCE_VALIDATION.md)。

这不代替Edge NIfTI保存/关闭恢复、可见窗口人工操作、其他浏览器、匹配真实DICOM四序列或最终部署；P4/E6整体未完，P3/E5原阻塞保留。账户只是本机角色，未核医师资质。无新导入/下载/AI/特征/训练/产品构建，无当前长任务或立即用户动作。

## 2026-10-16 01:05接续：账户联合接线及Edge只读子项

run_id `20261016T010830_jointauth`，对应10/15晚至10/16凌晨。新版联合工具已在真实DICOM-only最小组合实际CLI备份/恢复并启动：17表/1病例、36距离/1视图/4旧复核、196归档配置、2应用文件/5导入文件及自动账户收录；损坏账户在创建输出前拒绝，恢复账户另存第5条/刷新/实际重启后归属/内容/幂等和重登通过。AI模型/研究/原队列作为原目录明确外部前提，未重复650文件或冒称完整多病例AI包新验收。修复声明的空运行目录未恢复，17项相关检查通过/4既有警告。详见[账户最小联合恢复](P4_JOINT_ACCOUNT_RECOVERY_VALIDATION.md)。

接续实际已装Edge155.0.4283.45的headless只读回归：真实NIfTI四序列/非空mask像素开关及真实DICOM三视图，两种来源鼠标工具/毫米草稿、本地删除、跨病例引擎/缓存清理通过，0业务写/0页面异常。仅此范围，不代替Edge落库/复核/PDF/自然关闭或其他浏览器。见[Edge验收](P4_EDGE_READONLY_VALIDATION.md)。原17表/八路径/归档/账户/来源保持、正式PACS ready；P3真实四序列/E5原阻塞及P4/E6整体剩余仍保留。

## 2026-10-16 00:03接续：P2受支持范围已验及账户备份增量

run_id `20261016T000514_p2v2`，对应10/15晚至10/16凌晨。补此前缺失的来源绑定v2真实分支：隔离归档新增192/回读192，PNG变化实际409拒绝/无新增回执，running刷新与同回执成功；显式病例关联后192帧/9,437,184体素三视图与独立解码一致，后台及归档重启后回执/关联保留。P2在已登记公开CC BY4.0、受支持经典MR及本机受控准备/导入范围已验收，不代表任意DICOM上传/自动像素脱敏或四序列AI。原17表/八路径/归档原件/来源包/登记与账户保持。详见[P2新版真实分支](P2_V2_REAL_IMPORT_VALIDATION.md)。

接续E3新增账户私有快照/恢复及联合bundle自动收录代码，18项/4既有警告与真实两账户配置SHA恢复通过；旧bundle继续兼容且不凭空补账户。新完整联合bundle活服务恢复尚未重做，不用组件通过替代。无新模型/特征/训练/下载/PDF或前端产品构建；P3匹配真实四序列、E5原授权仍受阻，P4/E6及研究未整体完成。

## 2026-10-15 23:11接续：P4本地账户与复核归属

run_id `20261015T231143_p4identity`。现有DICOM报告已接本地账户登录，只有本机doctor角色能新增人工复核，署名固定并记录账户ID/角色；研究员/匿名、伪造署名及缺CSRF均拒绝。旧历史保持未认证，新账户不等于医师资质；权限只覆盖此复核POST。相关24项与构建、真实副本UI、实际重启/独立账户配置恢复、正式两角色只读登录通过；原17表全行/八路径不变。详见[本地账户验收](P4_LOCAL_REVIEW_IDENTITY_VALIDATION.md)和[账户操作](LOCAL_REVIEW_ACCOUNTS.md)。正式私有配置已另存备份，旧17表联合bundle尚不自动收录；未本轮新导出PDF。P4整体/P2范围收尾/E6继续，P3匹配真实四序列与E5原阻塞保持。

## 2026-10-15夜间：第17表完整联合恢复

run_id `20261015T224154_p4joint17`，10/15夜间22:39接续。第17表含复核的新完整联合恢复子项已验：196归档/配置、650应用文件及5导入文件离线备份/独立恢复后实际启动；192字节SHA/关联、17表科学版本字段、36工程距离/1视图/3复核完整快照、4000字当前复核及导出SHA与真实浏览器一致。原日常17表所有行、原八路径及原归档保持，回正式目录只读0写/0异常。详见[17表联合恢复](P4_JOINT17_RECOVERY_VALIDATION.md)。按新同步包装器执行，失败/成功步骤均finally回正式服务并释放锁，旧后台等待不再调用。P4整体仍进行中，身份/角色、其他浏览器/最终部署及P3真实四序列桥未完。

## 2026-10-15 22:35 自动化锁恢复与后续入口

用户要求检查连续跳过。旧 run `20261015T195156_p4joint17` 的 owner23492/holder11780 身份确实一致且有实际锁，但 owner 命令只有等待 holder 退出，holder 只检查 owner 存活/释放文件，形成互相保活；无实际工作子进程，未建立该轮结果目录，不能当作17表联合恢复正在进行。已核对精确启动时间，通过对应 release 文件正常释放；两进程自然退出，独占探针通过，没有停止应用服务或删除锁。

新增 `backend/tools/run_development_step.ps1`：同一实际执行进程持锁、同步完成步骤、finally释放；4项跨进程测试通过，涵盖竞争拒绝/元信息保护、正常释放、异常释放及外部命令失败。旧 runtime holder 脚本退役为明确报错，原版保存在本轮证据目录。更新 DAILY_SYSTEM_COMPLETION_TASK 的 C 节，所有后续开发步骤遵循该节，不再后台空占锁。仅更新项目提示词和兼容入口，未通过应用接口修改保存的定时配置或触发频率；若保存的提示词包含旧规则，应替换为最新版。

当前8012后端OpenAPI、5179前端可访问；Orthanc11240、后台21520、前端11560身份仍匹配之前登记。PACS实际连通检查见本轮summary。本轮未做17表完整联合恢复、未改数据库/患者数据/产品功能，不冒称P4完成。

下一轮首要实际工作：读取18:51交接，复用该轮隔离业务库的36距离/3复核，补已有真实视图版本；将“正常停机→17表与PACS原件/索引/应用/回执联合备份→独立目录恢复验证→恢复正式八路径和服务”的依赖步骤放进一个同步工作脚本，在新包装器下执行，try/finally恢复原配置。不要再重复PDF长文或192实例导入；P3真实匹配四序列、身份角色、其他浏览器/最终交付仍待推进，E5既有环境阻塞保持。

证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-15/20261015_lock_recovery/`，含before/after-lock、旧脚本、测试日志与summary。下一步无需用户再次批准常规本地开发。

## 2026-10-15 18:51 P4多测量与长意见边界

run_id `20261015T185100_p4bounds`，10/15傍晚窗口。现有DICOM报告修复长病例意见裁字、多距离行切分及强制复核新页标题残片；36条真实归档绑定工程夹具+精确5000字无换行病例意见，以及随后4000字无换行复核，两批最终各六页、共12页逐页查看通过。真实病例意见变更阻断旧PDF/复核过期/历史原文保留及相关NIfTI切换通过，构建通过。所有写入仅副本，原日常17表所有行不变，原八路径已恢复；当前后台21520/前端11560/Orthanc11240，端口8012/5179/8042。详见[P4报告边界验收](P4_REPORT_BOUNDARIES_VALIDATION.md)。P4整体仍进行中；下一项含复核/距离/视图的17表完整联合恢复，本机身份/角色单列，P3/E5原阻塞保持。

## 2026-10-15 03:20 P4本机人工复核与版本失效

run_id `20261015T032046_p4review`，对应10/14晚→10/15凌晨。现有DICOM报告页可保存本机署名/意见/已核对或需修改，绑定来源及阅片内容，不可改写且保留当时快照。距离、病例意见或元数据变化后旧复核过期；重新核对另存，最新需修改不被旧确认遮盖。导出摘要包含复核，复核单独变化也阻止旧PDF。真实192实例在副本完成响应丢失幂等、实际距离删除/历史保留/再复核、刷新及服务重启，原NIfTI报告切换通过。身份/医师资质未认证，测试为非医生工程记录，不作临床评价。见[P4复核验收](P4_DICOM_REVIEW_VALIDATION.md)。

接续3879字/40段长复核意见和跨页排版：实际两页常规及五页长文PDF，共7页渲染/查看通过。后端当前100项一次通过/4既有警告，最终构建通过。第17表先副本迁移、4条实际来源工程复核单库快照恢复逐字段一致；回原八路径后新表空，原16表所有行不变。原服务后台31712/前端30736、原Orthanc20264，5179/8012/8042，无AI等长任务。P4整体仍进行中：身份/角色、大量测量/长病例意见、其他浏览器、真实四序列与最终部署未全验。完整16表联合恢复保留为历史，未宣称本轮重验17表新组合；P3/E5原阻塞保持。

## 2026-10-15 02:15 P4 DICOM阅片记录/PDF及新版联合恢复

run_id `20261015T021538_p4report`，对应10/14晚→10/15凌晨。现有病例归档面板/报告页新增DICOM阅片记录入口：实际来源UID/空间、当前已保存毫米距离/LPS端点、病例级独立医生意见、版本摘要及PDF。源/测量/意见变化在导出前与异步渲染后再核对，不导出旧内容；单序列不借用NIfTI模型结果。真实192实例三平面记录、最终一页PDF视觉核对、实际重启与原NIfTI页面切换通过。后端39+46两组通过，前端最终构建通过。见[P4阅片记录及验收](P4_DICOM_READING_REPORT_VALIDATION.md)。

成功后接续当前16表+三条真实距离/一条视图+导入回执的新组合联合恢复：196归档/配置、650应用文件及导入补充5文件在独立目录启动，192归档字节SHA/关联、测量/相机/报告内容摘要、实际浏览器通过。57行操作路径正常重定位，科学版本字段一致；原16表全部行/原650源文件/归档与配置不变，原库距离/视图仍空。原目录服务恢复为后台15852/前端11240/Orthanc20264，5179/8012/8042，无AI等长任务。P4整体仍进行中：来源绑定人工复核、长报告、多浏览器/最终部署及真实四序列闭环未全验；P3/E5原阻塞保持。

## 2026-10-15 01:11 P4真实DICOM视图保存与恢复

run_id `20261015T0112_p4view`，对应10/14晚→10/15凌晨。现有Cornerstone DICOM工作站新增保存三相机/位置/缩放/三组窗值，绑定病例关联、归档、Study/Series/FrameOfReference及元数据版本；显式保存形成不可变版本，响应丢失重试不重复，来源过期提示且不应用旧视图。真实192实例三平面鼠标改变后，保存/刷新及实际前后端重启恢复通过。详情见[P4视图验收](P4_DICOM_VIEW_STATE_VALIDATION.md)。

最终后端87项通过，相关真实NIfTI保存/刷新/重启及Canvas切换、旧只读合成DICOM与原目录只读浏览器回归通过；前端构建通过。先备份15表并只在副本写入，第16表真实保存记录的快照恢复逐字段一致；回原八路径后仅新增空表，原15表全部行/原源192及派生192 SHA不变。后台25780/前端29268、原Orthanc20388，地址8012/5179/8042，无下载/导入/AI长任务。P4整体仍进行中，下一项DICOM来源/测量进入现有报告；P3匹配四序列及E5授权仍受阻，不把本批当完整系统交付。

## 2026-10-15 00:13 P4真实DICOM距离测量

run_id `20261015T0013_p4measure`，10/14晚至10/15凌晨窗口。现有DICOM Cornerstone路径可在默认三正交平面实际绘制毫米距离、保存/刷新、服务重启恢复与删除，记录绑定病例关联、归档、Study/Series/FrameOfReference及成组元数据版本，旧版本不叠加。真实192实例在隔离业务库用鼠标三平面验证，独立原始pydicom几何对照小于1e-5mm；响应丢失重试不重复、已保存只读、Esc和跨病例清理通过。共享会话的NIfTI相关浏览器回归也通过，详见[P4 DICOM距离验收](P4_DICOM_MEASUREMENTS_VALIDATION.md)。

先14表备份/副本迁移再上线新`dicom_world_measurements`空表，原14表所有行/源192及派生192的SHA不变；原运行目录已恢复，后台28668/前端6396、Orthanc20388，端口8012/5179/8042。原目录只读生命周期浏览器写0/异常0；新表三记录的独立快照/恢复检查通过。API回归57项、最终距离含撤权12项、额外备份1项分别通过，前端最新构建通过；没有新下载/归档/推理/提取/训练/PDF。P4整体仍进行中，视图状态保存及DICOM来源/测量报告未完，P3匹配真实四序列仍受阻。下一步DICOM视图保存/恢复，不重做本192导入或原PDF/特征。

## 2026-10-14 23:12 P2来源绑定准备流程修复

run_id `20261014T2313_p2review`。修复准备工具对任意资料固定声称“已看六张联系表”的错误：新增逐份源SHA/患者/Study/Series/份数核对、原像素联系表和显式技术复核，v2准备包保存来源/渲染/复核/PNG并在新登记和导入时校验。新登记只收v2，既有已固定原登记/报告不变。真实192实例完成新流程准备及隔离登记，未新归档或激活AI；新17+原17共34项通过，最后类型收紧后新17项重验通过。具体范围见[P2来源绑定准备](P2_SOURCE_BOUND_PREPARATION_VALIDATION.md)。

旧三项服务开工时均已不存在；先备份后按原配置恢复8012/5179/8042。14表逐行摘要、原登记/复核及原192源/派生SHA均不变；实际只读浏览器原回执192/192、查询200、写请求0，截图已看。后台18656/前端23464、Orthanc20388，精确身份见process登记。本批无新下载/推理/训练/特征/PDF或安装。P2总体仍进行中；P3匹配真实四序列仍受阻，现单序列也不满足1mm/轴对齐模型网格，P4/E5/E6未完。下一步P4真实DICOM工具/版本和报告集成，不重复原导入或来源探测。

## 2026-10-14 21:03 受控DICOM导入入口已接通

run_id `20261014T203619_p2import`，北京时间20:36:20获锁。现有病例归档面板可以选择本机已登记、来源/像素技术复核记录已固定的公开MR派生资料，实际导入、逐份回读、显示实际份数和可恢复失败；CLI共用同一服务与OS锁。病例19的真实192份重导入全部AlreadyStored/新增0；running时刷新同一任务，随后192/192成功，再入Cornerstone全部体素/三视图一致。实际后端重启后新浏览器恢复同一成功回执，14表业务行与192源/派生文件SHA不变。详见[P2受控导入验收](P2_CONTROLLED_IMPORT_VALIDATION.md)。

实测修复Windows JSON读写共享冲突，失败74/192回执保留并在重启后明确中断，重试成功；真实Windows句柄、并发/部分失败/篡改/损坏回执保护均验证。原协议/派生44项保留、导入11项及快照9项通过，前端本次变更构建通过。导入登记/回执5文件的补充备份、独立API副本恢复已验；新联合快照包含分支未重做完整500MiB演练。当前唯一服务仍8012/5179/8042，无下载/训练/推理，P2总体收尾、P4/E5/E6未完；P3真实匹配四序列分支明确受阻，不能借用其他病例输入或根据名称猜角色。

## 2026-10-14 20:23 PACS与业务联合恢复、状态修复

run_id `20261014T200622_p4joint`，北京时间20:06实际获锁。P4联合恢复子项当前重新通过：离线备份原SQLite归档索引/存储/私有配置及完整应用，196归档/配置文件、650应用文件；独立恢复目录实际启动Orthanc与业务服务，192原始归档字节SHA、14表业务科学字段/版本及病例关联一致。新浏览器从恢复病例19页面进入Cornerstone，192帧200、9,437,184体素和独立参考一致、三视图/滚动/窗值通过；截图已保存并查看。随后正常停止副本并恢复原运行目录。详见[P4联合恢复验收](P4_PACS_JOINT_RECOVERY_VALIDATION.md)。

另修复归档已支持真实阅片但状态仍显示“DICOM阅片尚未验收”的陈旧提示：按像素授权和服务标识固定两个条件报告受支持阅片可用，病例页面实际显示正确；四组合及原协议回归38通过/4既有警告，快照安全8项通过。浏览器导入和AI桥接仍未开放，不将配置开关当逐样本验收。未重复推理/特征/PDF、下载/安装/全包构建，无新模型或科学结论。P2仍需可操作导入入口，P3真实四序列桥及P4整体/E5/E6未完成；最新进程以local/processes.json、orthanc-local/process.json为准，端口仍8012/5179/8042。历史下文按当时记录保留。

## 2026-10-14 19:35 真实DICOM归档与Cornerstone阅片里程碑

run_id `20261014_real_dicom_6f9cbbff`。本轮在已运行Orthanc上实际导入192层公开MR的白名单元数据派生副本，逐份读取归档原字节核SHA，全部通过；原192源文件SHA不变，像素和几何未改。新建独立演示patient18/case19，年龄null/性别unknown，未借病例17临床数据、原MRI/mask/概率。使用现有API绑定新Study/Series，所有历史业务行不变，仅patients/cases/pacs_study_links各增加1。

修复真实Orthanc1.24 quoted type内嵌transfer-syntax与旧WADO代理不兼容的问题，保留Little Endian、单part/边界/字节长度约束。相关52测试通过，最终派生/API14子集通过、4既有警告；前端构建通过，已有大包/编解码提示保留。新增元数据派生/实际导入工具与真实浏览器脚本；技术联系表查看不冒称医生认证或全PS3.15符合，未知BurnedInAnnotation不伪造NO。

实际病例页查询→选检查/序列→核对空间→Cornerstone路径通过，192真实帧均200，三MPR、9,437,184体素的规范SHA与独立pydicom参考一致、滚动/窗值变化。Orthanc实际停止/重启后192实例与病例关联保留，再从病例页面真实重验通过；单实例重复上传AlreadyStored、总数不增。证据根E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014_real_dicom_6f9cbbff，最终浏览器在post-restart-ui。阶段文档P2_REAL_DICOM_VIEWING_VALIDATION.md。

当前frontend5179/backend8012（26892/12224，精确身份见local/processes.json）；Orthanc另有orthanc-local/process.json，继续复用，不重复下载安装。后台allow_pixel_read=true，当前本地归档只含192份上述派生实例；新归档样本仍按来源/处理范围核对。P2仍进行中，但真实单序列阅片不再受阻；P3匹配四序列AI未完成，E5 Docker与P4联合备份恢复仍待验。不提交/推送，未产生新模型训练/预测结论。

抽查 http://127.0.0.1:5179/case/19 ，查询检查→选择唯一检查/序列→核对空间→Cornerstone阅片。下一轮优先可操作导入入口与归档/业务联合恢复，再匹配真实四序列/来源转换与模型激活；不要重复已通过原病例PDF、特征或本192层下载。缺四序列不阻塞单序列阅片。首次临时目录和API脚本字段错误、首轮MIME超时均已记录，最终验收不混用失败证据。

## 2026-10-14 19:08 本机Orthanc环境解除与项目连接验收

run_id `20261014_manual_orthanc_b392fd6e`。用户已通过浏览器把官方候选两文件下载到既定目录。本轮静态大小/x64 PE/本地SHA核对通过，实际Orthanc --version=1.13.0；Authenticode为NotSigned，未把本地SHA当发布者签名。正常启动Windows本机进程，实际DICOMweb插件1.24加载；匿名/system返回401，后台鉴权/system与QIDO查询通过，归档实例0。新随机凭据只存在Runtime私有文件，不输出或进入源码。

项目在先SQLite备份后按既有runtime-supported配置恢复，现backend6164/frontend2748、8012/5179；原业务所有表内容与备份一致。/pacs/status=ready/read_available=true，pixel_read_enabled=false。真实浏览器病例17归档查询按钮可见、实际查询HTTP200、pageErrors0、写请求0。无新DICOM导入、关联、像素读取、推理/特征训练或PDF。P2-env已解除，P2总体仍进行中，E5 Docker阻塞不受此次影响。证据：E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014_manual_orthanc_b392fd6e/summary.json、pacs-readiness.json、browser-pacs-ready.json。

新增prepare_local_orthanc.py与start_orthanc_local.ps1，prepare/语法/schema已核；actual start/connect通过。配置/索引/文件/日志在E:/BrainFusion-Runtime/orthanc-local；backend归档配置E:/BrainFusion-Runtime/local/pacs-config.json。Orthanc独立进程登记在orthanc-local/process.json，不误当项目start/stop_local的一部分；不注册系统服务，重启电脑后需按正常脚本重启。未提交/推送。

下一轮先核对开发锁/实际PID/健康，复用已启动归档，不再重试下载或将环境标受阻。优先192层真实MR的有记录脱敏派生副本及明确入库执行路径，原件/UID映射保留。来源/像素处理完成后验证实际导入→病例关联→Cornerstone，再开放像素；当前不把技术联系表查看冒充临床认证或模型四序列确认。可先用明确合成工程材料验真实归档持久化，但不能代替真实样本阅片。

## 2026-10-14 18:08更新（实际有限DICOM、当前台账及R3组件）

P2样本条件有实际进展：公开NBIA的192实例CaPTk处理临床来源MR已全部取得，19,432,662字节、源UID/本地SHA/像素解码与当前成组几何验证通过；192×256×192、spacing 0.9765625/0.9765625/1mm，经典单帧非MOSAIC。六张原像素联系表覆盖192层，源默认窗技术观察未见身份文字；仍保留私有/日期等元数据预检项，未批准归档，也没有实际DICOMweb/Cornerstone或AI验收。另60实例候选声明1mm/实测约3mm，继续拒绝。全部252源文件不变。详见[P2实际样本记录](P2_PUBLIC_MR_SAMPLE_20261014.md)。

按进度复核将主清单整理为P/F/E/R共20项唯一当前行，原82,833字节及完整历史证据路径已保存在`docs/history/`且SHA一致。等待有界逐实例下载期间补R3独立FedProx近端局部更新组件，14项相关合成测试通过、4既有警告；未接入simulate完整对照、未训练患者或改变科学结论。R3改进行中，其余状态见主清单。

证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T180828_p2sample/`。检查时原8012/5179无监听、登记旧PID不存在；本轮没有启停服务或重新加载页面。PACS仍需正常获准环境，历史Orthanc环境命令被自动审批拒绝的限制保留；P2/P3/P4整体未完成。下一步针对已取得样本的实际元数据准备可审计派生副本/产品导入路径，并独立续接R3完整对照。

## 2026-10-14 08:10更新（P4-n4 API验收断言加固）

P4-n4只读浏览器工具新增明确API成功条件：至少3个相关响应、全部HTTP 200且包含病例特征端点。复用现存隔离环境服务，实际再次打开Research页成功：2次临床输入GET及1次特征GET均200，5行自动结果可见，未保存输入警示false，pageError 0、非GET/HEAD请求0、未截图。Node语法和git diff检查通过（后者仅出现既有行尾转换提示）。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T0810_p4browserassert/`。没有病例/API/数据库/模型/依赖改动或任务提交；只是加固已验收的P4-n4本地NIfTI浏览恢复检查。P2/P3仍缺真实本地PACS和获准匹配四序列DICOM，P4整体进行中。

## 2026-10-14 07:09更新（P4研究页状态恢复）

根据当前运行登记确认服务使用E盘隔离验证数据库/feature-job目录。病例17已有自动掩膜特征状态通过只读API查询为成功且非失效，临床输入可用；没有提交新任务。全新headless浏览器上下文打开当前Research页后，成功状态、选中特征摘要与5行结果可见；相关GET为200、未保存输入警示false、页面异常0，加强复测实测非GET/HEAD请求0，无截图或病例内容留证。可复现工具`frontend/tools/verify_live_feature_persistence.mjs`，Node语法检查通过；首次工具因模块解析位置未运行，修正位置后通过，错误原因已留在证据目录。最终证据`E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T0709_p4featureapi/live-research-feature-browser-verified.json`。这是既存NIfTI任务的浏览器刷新展示局部验收，不代表新推理/提取、DICOM/PACS或科学验证。P2/P3实际链路仍受归档和匹配数据阻塞，P4整体进行中。

## 2026-10-14 06:15更新（P4隔离特征提取计时及互斥复核）

首次06:11的执行壳提前退出，FileShare.None锁自动释放，所以该尝试不作为验收证据；之后以长驻owner核实owner和holder存活、锁state=held后复测。复用E盘最近成功的固定协议PyRadiomics请求，确认没有活动feature job，现存4序列和mask SHA与原成功请求期望值全部匹配。提取器3.529秒、完整Python子进程墙钟6.079秒；2秒间隔粗采样的Working Set峰值321.3MB，Private Bytes峰值约1.09GB。Python3.9.13/PyRadiomics3.1.0/NumPy1.26.4/SimpleITK2.5.2，20/20特征非空，未使用GPU。有效证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T0615_lockaudit/`。为避免保留个体特征，本轮仅存计时、版本和完整性布尔值；未写数据库或正式job目录。该一次单例测量不代表队列或产品端到端性能。P2/P3真实DICOM链路仍受归档及获准样本条件阻塞，P4整体进行中；产品代码、依赖、数据、模型和服务状态未改。

## 2026-10-14 05:12更新（R1官方来源刷新）

重新核对Zenodo v3官方记录后，当前页面显示`Open`并列出当前文件指纹；E盘现存临床数据表、官方字典、术前coreg检查元数据的文件大小及MD5与在线清单相符。03:02所见Restricted状态不再代表当前页面。直接下载探测因本机DNS失败而未到达Zenodo，也没有重新下载或查看标签值/分布。官方字典仍没有说明IDH 0/1分别对应突变还是野生型；页面显示的检查编号规则与本地检查元数据文件可供检查归属核对。R1-source-refresh已验收，但R1整体仍受阻于目标编码、MONAI训练病例重叠和未查看独立评价角色冻结。许可仅由E盘当前保留的v3快照元数据支持，本轮未从在线Rights区域重新读到许可文字。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T0511_r1labelverify/source-refresh-audit.json`。没有代码、数据库、数据文件、模型、依赖或服务改动。

## 2026-10-14 04:07更新（P2公开DICOMweb来源探测）

从NCI IDC官方说明找到只读公开DICOMweb proxy，并实际发起QIDO-RS查询：HTTP 200、`application/dicom+json`，响应443条研究元数据（尽管请求limit=1）。为最小化处理，仅记录状态、类型、计数，响应体未落盘/打印，未保存UID或患者标识；未请求帧像素、未下载文件，也没有产品病例关联。结果只验收“公开QIDO来源可达”，不等于真实DICOM阅片、归档入库或模型桥接。当前产品入口仍要求本地病例、归档fingerprint、元数据SHA及本地PACS路由，IDC proxy为viewer-only/no-downloads且无本地持久化。TCIA候选UPENN-GBM虽标CC BY 4.0，但全量原始DICOM约139.4GB；先前一个候选实例被预检拒绝，本轮未重复使用或下载。证据在`E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T0406_p2publicdicom/idc-dicomweb-probe.json`。P2/P3/P4真实影像链路仍未通过；无产品代码/DB/依赖/模型/业务数据改变。

## 2026-10-14 03:02更新（R1来源审计）

审计当前Zenodo DOI 10.5281/zenodo.22205631与E盘现有元数据/字典，不看标签频数、不下载新数据。E盘2026-09-01 `zenodo_record.json`登记access_right=open、CC BY 4.0；临床字典本地MD5与记录中的md5一致，字典列拼为`iidh1/2`，描述IDH1/2突变状态，但没有声明0/1分别代表突变/野生型。当前Zenodo页面索引则将文件区显示为Restricted并提示登录，和本地快照冲突；按当前限制状态处理，在访问许可/镜像来源核实前暂停新队列下载和新增重拟合。没有申请或联系发布者。详细来源与证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T0302_r1label/source-audit.json`及`docs/RESEARCH_PROTOCOL_NEXT.md`。R1审计子任务已验收，R1整体受阻，未产生新科学结论。PACS/DICOM真实链路状态不变；本轮无代码、数据库、模型、依赖或服务更改。

## 2026-10-14 02:06更新

修正docs/SYSTEM_ARCHITECTURE.md中的过时架构说明：现状是Vue3/Vite病例流程、Canvas默认阅片及已验收的显式Cornerstone NIfTI入口；固定MONAI BraTS SegResNet分割、独立串行研究任务与CPU PyRadiomics子进程、SQLite元数据和E盘文件产物；医生意见与版本绑定报告独立于探索性研究概率。加入病例/当前MRI/分析版本/研究任务文件/医生意见/报告关系图，并注明部分版本关系是字段逻辑绑定而非外键。用虚线表示尚未接通的Orthanc/DICOMweb与模型桥，不把接口或组件存在写成真实归档能力。源码与P1/P3/P4记录人工交叉核对，git diff --check通过。证据在E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T0206_p4restore/。仅文档变更；P2/P3真实DICOM路径与P4联合归档恢复依旧未验。


## 2026-10-14 01:05更新

新增P4-n2：使用现有登记病例的NIfTI输入执行一次隔离固定模型推理。batch=1、ROI 128×128×96、GPU预算6000 MB；CUDA无CPU回退。runner计时1.38秒，包含推理/后处理写盘/哈希但不含进程启动、MRI归一化、网络/权重初始化；CLI完整进程14.45秒。PyTorch分配峰值505.23 MB；进程RSS采样峰值1621.9 MB；整卡采样总占用峰值2022 MB、空闲最低9923 MB，系统级数据不等于任务独占用量。输出网格240×240×155匹配输入，标签域和checkpoint校验有效。临时输出已删除，已有分析/数据库未改变。无参考mask，因此不报告Dice/准确率；单例不作一般性能推断。

证据：E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T010509_p4timing/。复用服务PID 2860/33200，8012/5179 HTTP 200。P4仍进行中；DICOM阅片/模型桥接、特征性能及PACS与业务库联合恢复未验。下一步若有条件，核对获准脱敏四序列DICOM路径；否则继续可在隔离环境完成的P4恢复一致性检查。


## 2026-10-14 00:12记录核验

P4报告PDF局部验收的交接记录已核准：主run实际独占锁在2026-10-13T16:11:12.0800374Z释放，owner/holder均退出；证据摘要只列后端2860和前端33200两个复用服务。个案PDF/临时图不存在，证据中只保留去内容结构摘要。该记录整理窗口没有新增产品改动或测试；功能验收见下方00:01更新及主run证据目录。

## 2026-10-14 00:01更新

完成P4本机当前版本绑定报告的真实PDF导出与打开复核：Playwright使用已登记的本机病例17，校验当前模型修订/权重SHA/mask与四序列输入摘要后，通过实际“导出PDF”按钮生成报告。Poppler确认2页A4、未加密；临时渲染后检查两页文字和追溯区可读、无分页截断。该PDF含个案内容，视觉复核后删除PDF与渲染图；证据只保留测试通过日志、页数/纸张/加密及已清理声明，不保留病例内容。第一次测试因Playwright默认C盘浏览器不存在而失败，随后显式复用E盘既有浏览器缓存通过；未安装浏览器或依赖。

证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T000136_p4restore/`。本轮只对现存NIfTI模型报告路径验收；不代表DICOM/PACS端到端、归档业务联合恢复或临床报告认证。P4整体进行中，P2/P3真实归档和匹配四序列仍受阻。

## 2026-10-13 23:01更新

P4报告来源显示的真实字段映射已纠正。检查本机实际模型runner可知`revision`是40位源码修订标识，checkpoint文件SHA-256在`checkpoint_sha256`字段；上一窗口合成测试未暴露该字段差异。现在报告分别展示模型修订标识与模型权重SHA-256，再显示mask和四序列输入SHA-256。新增隔离合成与当前已有病例17的浏览器检查；病例17只读、没有截图/PDF导出/写入，页面当前分析与报告版本匹配，所有7个摘要长度/类别正确、无本地路径显示。前端生产构建通过；合成报告PDF两页A4渲染复核通过。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-13/20261013T1500_p4currentreport/`。

P4仍进行中：该检查是现存单例的报告显示，不是PACS/DICOM路径、真实性认证、端到端AI或联合归档恢复。服务沿用2860/33200、8012/5179，无重启或长任务。P3真实归档/匹配四序列仍受阻。下一步按交接先查新的合规样本/用户反馈，否则做隔离恢复与报告一致性小批次。

## 2026-10-13 22:29更新（前一轮）

完成一个P4报告/PDF来源谱系UI工程小批次：报告增加分析运行ID、真实模型标识、模型权重修订SHA-256、mask SHA-256和四序列输入SHA-256；格式不合法/缺失的摘要显示“未记录”，并提示哈希不能认证数据来源。无本地路径/私有标签/审核者声明泄露。Playwright使用明确合成报告夹具验证五个SHA与运行ID可见、路径不泄露并实际导出PDF；Poppler核实A4两页、无加密，渲染两页目视检查文字与哈希均未截断。前端构建成功。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-13/20261013T142913_p4lineage/`。

这只是报告组件和合成PDF工程验收，不是患者病例PDF、PACS/DICOM来源认证或P4整体完成。服务沿用后端2860/前端33200、8012/5179，无重启和长任务；无真实推理/提取/数据库变更。P2/P3真实归档与匹配四序列仍受阻，P3/P4整体进行中。下一步先查看用户是否提供合规路径；无新条件时继续独立P4剩余回归，不重试被拒Orthanc安装。

## 2026-10-13 22:04更新（前一轮）

P3-b3本轮完成了工程侧端到端核对：从病例绑定与只读转换版本索引进入来源核对API，连接合成localhost DICOMweb协议服务，核验四个序列及12个原实例的层级UID、元数据、服务身份、原始字节SHA/大小，并执行两轮原字节观察。新增的集成测试最终纳入64项P3来源/注册/归档回归，全部通过。接口响应明确保持 `model_input_eligible=false`、`current_mri_replaced=false`、`reviewer_authenticated=false`、`archive_written=false`；病例状态和study link行数不变。详细证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-13/20261013T140457_f768f1d9/`。

这只是合成协议工程验收：没有真实Orthanc/PACS读取，没有真实采集或匹配四序列，没有许可/像素/审核者身份认证，也没有模型激活。当前本地PACS配置与转换版本索引文件均不存在，故P3-b3-real及P2-real/P3-real仍受阻，P3总体进行中。既有Orthanc安装审批阻止未改变，本轮未重试或绕过。用户已获知最有帮助的是提供经授权脱敏DICOM的本地路径；本轮无新反馈或病例路径。

当前沿用后端PID 2860（约13:43:37Z启动）、前端PID 33200（约13:43:37Z启动），地址为 `http://127.0.0.1:8012/docs` 与 `http://127.0.0.1:5179/case/17`；本轮未重启。无下载、训练、推理或构建长任务。下一步先核对锁释放与用户反馈，再看真实样本路径是否可用；若仍无真实归档，推进独立P4版本/报告来源一致性验证，不重复环境安装。

## 2026-10-13 07:11窗口（对应10/12夜至10/13清晨）

run_id 20261013T071140_7484539d；FileStream FileShare.None实际持有者/owner29484，原生启动UTC2026-10-12T23:11:39.8113102Z，开始UTC2026-10-12T23:11:40.4313250Z/北京07:11:40，session63119。结束/耗时/正常释放见summary与lock-released。无新反馈，REVIEW_FEEDBACK不改；保护既有工作树，不提交、推送或发布。

P3-b2a/b2b仅工程已验：转换版本只读重开与完整性/来源失效守护，以及现有病例PacsPanel的转换来源状态。原四序列规划重新验证，使用外部保留报告SHA作本地审计锚（不是签名/身份认证）；检查报告、原字节快照、四NIfTI、UID/Frame/矩阵/mm/affine/qform/sform/全体素Rescale与SHA；读取结束再复查字节。缺失unavailable、来源版本变化stale、损坏invalid，固定版本内文件名/拒绝重定向、bounded JSON/单文件64MiB/原字节1GiB/有界float32 gzip展开，拒绝重复JSON键/NaN/解压越界；不写被检查版本或原文件，失败保留证据。

服务端只读索引DICOM_CONVERSION_INDEX_FILE默认E:/BrainFusion-Runtime/local/dicom-conversions.json，最多32版本、1MiB，仅本地配置，无公开登记/激活接口、无新DB表。病例存在/归档fingerprint与原关联检查在文件核对前执行，结束复查索引/配置/关联；来源JSON需单独SHA且匹配病例/归档/Study，显式synthetic-fixture不得登记到病例；本轮实际索引不存在，合成转换未关联病例17。浏览器仅用版本编号，不传路径/凭据，no-store响应不含磁盘路径/像素/私有标签。文件核对使用单进程互斥、忙时409可重试；可选pydicom缺失不使API启动失败。live_archive_reconciled、reviewer_authenticated、model_input_eligible始终false；当前真实归档元数据与原字节在线核对、许可/像素/角色实体审核及真正AI激活仍未完成。

验证：135相关后端检查通过/4既有警告（backend-registry-final.log），另1项独立进程可选DICOM依赖缺失导入检查通过（backend-optional.log）；76为较早子集历史。首次backend-registry.log测试清理对已关闭会话Patient取id导致DetachedInstanceError和后续重复UID约束错误；固定提前保存id后全通过，未修改真实库。上一轮真正保存的明确SYNTHETIC转换在本轮独立CLI新进程重开，外部上一轮输出报告副本SHA与Runtime版本一致，72体素0差；没有再转换/写原版本。错误的早期只读路径定位和CIM深度输出工具警告保留，最终服务身份用service-identity-compact.json，不用它们冒充产品失败或通过。

病例来源浏览器开发与实际最终构建HTTP预览通过（browser-conversion-source-dev/prod/validation.json）：真实病例无登记提示、明确合成UI状态verified_readonly/stale/unavailable/invalid、错版本拒绝、断连清旧状态/重试、SPA切病例时晚到响应不污染新病例；页面异常/写请求0。新增请求兼容既有PACS/DICOM浏览器夹具；相关已有DICOM工程UI实测回归通过（browser-dicom-source-panel-regression/result.json），仍是明确合成协议、不是实际归档。真实原NIfTI仍3canvas；截图已查看。仅因前端实际改动构建一次，chunk大小警告保留，无新依赖安装/多prefix/全包打包；不把旧交付包称本轮通过。

接续P4-n1独立小批次仅真实NIfTI单病例阅片观测已验：240×240×155、1mm、四序列实际加载/滚动/退出，首次三视图1.704s（初始t2f），未缓存三序列切换0.682/0.704/0.715s，缓存返回0.090s，单次滚动0.073s且层号77→78。四序列Cornerstone cache151776000 bytes（约144.7MiB），CDP renderer JS heap62982752 bytes（约60.1MiB）；退出engine0/cache0。新浏览器上下文但服务端/OS缓存可能已热、含自动化和轮询开销、单例单次，不代表统计性能或GPU/进程总内存。另记录服务进程单次WorkingSet快照，非推理峰值；未测DICOM上传/归档/查询/转换真实样本或模型/特征耗时，无低分辨率外推。

重载前活动分析/特征0，先备份并在副本验证14表全行/任务复制SHA，再用原项目脚本核验PID/启动时间停止/启动。最终原14表全行与本轮备份/恢复副本、上一轮快照一致，科学文件/MRI/mask/空间夹具/候选/隔离保管/featurejobs和包版本SHA不变，旧转换报告/原快照/输出SHA不变；无新业务schema、当前MRI替换、推理、特征重算或医生意见变化。只做现有业务库副本恢复，不是P4真实PACS联合恢复。

当前backend30436 UTC2026-10-12T23:22:24.4627486Z；frontend6772 UTC2026-10-12T23:23:54.8831968Z，已恢复原项目dev。地址http://127.0.0.1:5179/case/17、workstation/17?viewer=cornerstone，API8012/docs；Runtime/local/processes.json登记，后端日志Runtime/local/backend.{out,err}.log，前端本run/restored-dev-service/frontend.{out,err}.log。preview8108已按登记停止，单后端/前端、各一串行worker，无下载/训练/推理/构建长任务。保持10/10 01:06 runtime-supported.json的原DB/featurejobs/gate与00:06 relocated-runtime；PACS配置/转换索引仍不存在，不伪造凭据或真实审核。

P1已验；P2工程已验/总体进行中、P2-real受阻；P3-a/b1/b2仅工程已验/总体进行中、P3-real受阻；P4-n1局部已验、P4整体进行中，真实DICOM性能/方向/生命周期/归档联合恢复/来源报告待实施。E5受阻/E6进行中，F/E旧历史保留，R1待核查/R2–R4待实施，无研究结论或完成百分比更新。原UPENN单实例MOSAIC仍拒绝、无匹配真实四序列，不重复旧空查询/审计/下载。

下一轮第一步：核对本锁释放、新PID/启动时间、反馈和长任务并复用服务；真实归档或支持匹配样本可用优先P2/P3-real，否则P3-b3登记版本与当前归档UID/元数据/原字节在线再核对（不以本地索引替代真实来源）；为后续角色审核/激活绑定保留明确阻塞。P4继续独立NIfTI来源/报告与重启证据，真实归档联合恢复不能伪造。

Orthanc官方候选下载+版本执行此前自动审批仅“blocked by policy”；本轮未重试/换工具绕过。解除需可获批准安装或已有可用归档，独立工程当前不需要用户重复一般授权、账号、提权或重启。

证据：E:/BrainFusion-Runtime/results/nightly/2026-10-13/20261013T071140_7484539d；详细操作见P3_CONVERSION_INTEGRITY_VALIDATION.md，输出guide.md及JSON/真实页面截图。


## 以下为之前窗口的历史记录

## 2026-10-13 06:10窗口（对应10/12夜至10/13清晨）

run_id 20261013T061054_a3334597；FileStream FileShare.None实际持有者/owner15416，原生启动UTC2026-10-12T22:10:53.6629913Z，开始UTC22:10:54.2786787Z/北京06:10:54，session15354；结束/实际耗时/正常释放见summary/lock-released。无新反馈，不编造REVIEW_FEEDBACK；保护现有大量工作树变更，不提交/推送/发布。

本轮新增P3-a四角色来源规划/拒绝契约、P3-b1原字节到NIfTI轻量转换工程验收。新增services/dicom_input_plan.py、dicom_conversion.py及各自tests、tools/plan_dicom_model_input.py、convert_dicom_model_input.py；study_validation.py抽取模型几何契约并用affine运算替代头部检查时的as_reoriented数据实体化，48种轴排列/翻转与旧affine计算一致。原模型四角色、共同矩阵/affine、1mm、轴对齐、每序列3200万体素约束不改变，归一化/模型/分割原mask不改。

规划要求四个不同Series、各一次t1c/t1n/t2w/t2f、同Study和FrameOfReference/原网格，逐项明确加权/对比剂阶段/液体抑制声明及依据SHA/索引/审核者索引/带时区时间；不按SeriesDescription猜。病例/归档fingerprint/实例与序列版本、实例完整集合与实际元数据重算空间一起核对，派生源索引到RAS毫米affine。确认JSON仅是声明，不认证审核者或医生，不证明许可或真实病例归档绑定。metadata_plan_ready只表示本规划检查通过，model_input_eligible始终false，真实证据/人工审核仍待完成。

转换复用现有SimpleITK2.5.6/ITK5.4的GDCMImageIO、pydicom3.0.2、nibabel5.4.2/numpy2.2.6，无新安装/下载。每个原Part10绑定UID与SHA、FileMeta和白名单元数据语义，先拒压缩/Deflate再读数据集；仅未压缩Little Endian经典非MOSAIC单帧MR。按已核对的IPP物理UID顺序读取，显式float32与stored*RescaleSlope+RescaleIntercept，ForceOrthogonalDirection=false；不加载私有/元数据字典，不自动配准/重采样。完整原字节快照另存、输出全新版本目录，不改原DICOM；只去除派生图像元数据，不能称已完成DICOM脱敏。

转换后重新打开四个NIfTI，核对尺寸、mm单位、RAS affine、qform/sform、每层每个像素和Rescale、全体素SHA、原DICOM/输出文件SHA与旧模型几何契约，空序列/不一致明确失败，保留失败版本不作成功状态。原文件单个64MiB/总1GiB、全序列/模型原有上限以及磁盘余量检查；原OB标准奇数像素偶数VL零填充明确支持，不补齐非法数据。BurnedInAnnotation=NO只是声明门槛，不代替真实像素审核。转换产物未激活到病例、不触发AI/归档/业务库；model_input_eligible仍false。GDCM内嵌版本本Python API未暴露，明确未记录，不能由ITK版本推算。

补齐requirements-core.txt遗漏的直接依赖httpx==0.28.1；当前PACS及新CLI导入它，而现环境早已安装。仅改声明，无pip安装/升级或整包重制；旧源码/CPU/worker交付包均历史，E6最终包未冒称更新通过。

验证：最终287相关后端通过/4既有警告（backend-final-resource.log），覆盖新规划/真实GDCM转换合成行为与原PACS/WADO/几何/阅片序列/世界测量/任务交互/分析完整性/config回归。首次38规划+几何、50转换子集、284补充前为历史；backend-final.log两项故障注入先丢失毫米单位而被更早正确拒绝，保留单位再注入affine/像素，并新增单位/qform冲突检查后通过。首次AST演示helper缺SERIES变量，未生成任何原DICOM，改用新engineering-fixture-final目录，失败空目录/日志保留。重启后审计工具错假定普通start_local登记frontend_mode，查实际命令与原生PID/启动时间后确认dev，没改/伪造运行登记字段。

独立进程实际CLI规划和转换通过：自有像素函数生成12个明确SYNTHETIC Part10（4角色各3层，3×2×3矩阵），负方向/分层Rescale产生四个NIfTI，72体素0差异、源快照/派生SHA可重开核查；独立手算RAS角点(column2,row1,plane2)=(-8,-21,28)mm一致。另有8位奇数填充、12位符号/Rescale/布局的测试，不将它们当真实采集或MRI队列。合成病例编号字段17只是测试上下文，archive_case_binding_independently_verified=false，未与原病例库建立关联。

现有合法真实NIfTI四序列240×240×155单独复验新头部几何检查，实际header-only约4.98ms、禁止像素实体化时仍通过、原文件SHA不变；没有声称与合成DICOM匹配，未重跑分割/特征/预测。这个时间只含本机本次头部检查；转换timing_ms含本合成样本的读写与独立核对，不是PACS导入、整条AI链路或真实队列性能，不能外推。

因共享校验参与现有MRI入口，活动分析/特征任务0后先备份并在副本验证14表全行和featurejobs复制SHA，再按既有脚本核验停止/重启。实际浏览器新服务原真实NIfTI Cornerstone仍3canvas、PACS未配置/旧WADO503/no-store、页面异常/原库写0，截图已查看。没有前端源码改动/构建、依赖安装或PACS环境重试；这是原入口相关回归，不是新真实DICOM/转换UI验收。

最终原14表全行与本轮备份/恢复副本、上轮已验副本相同；原MRI/mask/空间夹具/候选/隔离保管/任务文件SHA、包版本不变，无新schema/当前MRI/模型激活。只验业务库副本恢复，真实PACS索引/原文件+业务联合恢复仍未做。state-validation.json为重启前，state-validation-final.json才是重启后最终证据。

P1已验、P2工程a/b/c已验但总体进行中/P2-real受阻；P3-a/P3-b1仅工程已验，P3总体进行中/P3-real受阻：尚无真实匹配四序列/归档、可靠来源许可/像素审核与角色证据认证、病例转换版本激活/队列/UI、真实DICOM→现有AI端到端。本工具的JSON声明和元数据哈希不是患者/审核者认证。原UPENN单实例仍MOSAIC拒绝，MR_small为处理工程数据；本轮无新的真实数据下载或重复候选审计。P4待实施，E5受阻/E6进行中，R1待核查/R2–R4待实施，F/E历史验收保留。SCI/新临床指标/论文正结论未扩展。

下一轮第一步：锁、反馈、上述PID/原生启动和长任务核对后复用服务。新失败或可用真实PACS/合法同检查四序列优先返回P2/P3-real；外部条件仍不变则P3-b2转换版本重开/产物失效与来源完整性守护，以及病例只读来源状态接入（无可靠审核时仍不激活AI）。继续核实支持真实样本和角色实体证据，不重复旧空查询、同一次被拒安装或无变化整包构建。

Orthanc官方候选下载+版本执行此前自动审批仅“blocked by policy”，本轮未重试/换工具绕过；当前无Orthanc进程/私有PACS配置。解除需可获批准安装或已有可用归档，独立工程无需立即用户重复授权/账号/提权/重启。


## 以下为之前窗口的历史记录
## 2026-10-13 05:14窗口（对应10/12夜至10/13凌晨）

run_id 20261013T051455_f13472c8；实际FileStream FileShare.None持有者/owner27576，原生启动UTC2026-10-12T21:14:54.7780683Z，开始UTC21:14:55.4033991Z/北京05:14:55，session74715。结束、实际耗时与正常释放见本run summary/lock-released。无新反馈，不编造REVIEW_FEEDBACK；保护既有工作树，不提交/推送/发布。

P2-c2成组像素接入工程已验收：复用当前CornerstoneViewer三视图及Workstation、病例PacsPanel，新增dicomVolume.js和病例绑定的manifest/frame读取。检查必须已与当前病例和归档配置核对关联，后台开启像素、固定逻辑服务标识，验证不覆盖/无摄入转码策略；逐帧核对来源fingerprint和白名单元数据SHA，旧空间或目标改变在读取像素前拒绝。图像ID含来源/版本及独立会话，缓存/请求/元数据按本视图清理，不全局过滤错误，不静默切Canvas或NIfTI。

DICOM仅支持已验c1的均匀、非MOSAIC、经典单帧MR成组原空间；1 mm四序列模型约束仍只属于现有AI输入，不强加于工程阅片或默许DICOM可推理。序列角色未确认、无自动配准/重采样，DICOM测量保存、mask叠加/编辑、视图持久化与AI提交未开放，原NIfTI工具/保存/原mask保持。满足来源门槛的已有面板提供“Cornerstone阅片（工程验证）”，未配置时不显示可用假象；用户可明确选择当前病例NIfTI。

本次214相关后端检查通过/4既有警告，8新增病例/来源/版本门槛（早期66为该子集）；上轮207为历史，不混称同一运行。浏览器明确SYNTHETIC 32×24×9协议夹具，经真正WADO multipart和现有解码工作器加载3MPR：全部6912有符号像素一致，负方向斜位LPS手算角点(-43.2,-17.6,104.75)mm一致，spacing(2,3.25,2.5)mm。窗值、平移焦点、缩放比例、十字线其他平面位置及滚动层号11→12实测变化。开发和一次最终构建的实际静态HTTP生产预览通过；生产做工具/生命周期冒烟，数值及缓存明细在开发检查，不夸称生产内部数值检查。

追加P2-c2-r回归小批次通过：直接SPA切错误Series时，旧清单在新帧之前拒绝；9帧仅1帧失败也保持error，完整成功后的缓存、失败/加载中退出及旧新帧元数据清理后engine0/cache0/remaining0。明确错误、无静默回退、用户手动NIfTI仍3视图；最终浏览器pageErrors/原库写入均0。合成截取像素是纯工程函数，未由NIfTI生成冒充患者DICOM，也未向真实归档/病例库写入测试关联。

首次发现解码工作器预优化/CommonJS导出不兼容：依官方Vite方向排除DICOM loader预优化、预优化现有CJS codec入口、worker ES格式/WASM资产，无新增依赖。5.7核心忽略缓存插入Promise会产生XMLHttpRequest未处理拒绝，已用本系统独立bfwado scheme接住缓存Promise，原像素Promise仍拒绝并显示error，无全局事件屏蔽。测试误取actor UID、导入第二份tools状态、返回router Promise被GC及在400ms单击窗口之前读相机，均保留失败日志，改用真实volumeId/当前组件/实际路由与已知体积点，600ms后有真实事件与相机变化；不是再次修坏或冒称工具通过。

重载前分析/特征活动任务0，14表全行备份/恢复副本相同、featurejobs复制/SHA相同；重载后新增实际病例绑定路由503/unconfigured/no-store，实际DICOM页面明确未配置、Canvas禁选、无NIfTI自动回退/像素请求。最终真实NIfTI3canvas通过。原14表全行与本轮及历史已验副本一致，原MRI/mask/空间夹具/候选/隔离保管与featurejobs SHA、主环境依赖版本不变；未替换原DB、未推理/重算、未改原mask。只验业务库副本恢复，不代替P4真实PACS+业务联合恢复。

P1支持NIfTI已验，P2-c2和c2-r仅工程已验，P2整体仍进行中/P2-env受阻：真实Orthanc/插件、支持的真实成组DICOM、来源/像素审核、真实导入/重复/持久化/重启未验。现有UPENN单实例MOSAIC仍明确拒绝，MR_small为处理测试数据，未新增真实下载或审核。P3真实匹配四序列链路受阻，P3工程转换/确认仍待实施；P4集成/性能/联合恢复/报告待实施，E5受阻/E6进行中，R1待核查/R2–R4待实施。F/E历史已验保留，不能凭本批次冒称系统交付或研究完整。

下一轮第一步：核对锁、反馈及上述服务启动身份并复用。优先处理新实际失败或可用真实PACS/样本；外部条件不变时推进P3-a来源UID/Frame/产物及四序列人工确认、原模型输入空间契约的小批次（不按名称猜、未满足具体拒绝），独立于尚未取得转换工具/真实队列的准备不能算真实端到端通过。P2后续仍需实际来源与归档验收，环境策略拒绝不重复绕过。

Orthanc官方候选下载+版本执行曾被自动审批拒绝，仅给出“blocked by policy”；本轮未重试/换工具绕过，解除需可获批准的安装路径或已有可用归档。当前独立开发不需要用户重复一般授权、账号、提权或重启。


## 以下为之前窗口的历史记录
## 2026-10-13 04:17窗口（10/12夜至10/13凌晨）

run_id 20261013T041702_3ff437ba；开始/原生锁PID精确值见lock-acquired.json，实际FileShare.None持有、session30030；结束/耗时/正常释放见summary/lock-released。无新反馈，不改REVIEW_FEEDBACK；不提交/发布。

P2-c1成组空间核对工程已验收：新增services/dicom_series.py、tests/test_dicom_series.py，pacs_wado.py抽取共享单帧guard、api/pacs.py新增GET /pacs/studies/{study_uid}/series/{series_uid}/view-manifest；现有PacsPanel.vue加入“核对序列空间”与结果/明确限制，新增浏览器检查工具verify_dicom_series_panel.mjs。未增加另一套UI或DICOM渲染入口，旧Canvas/Cornerstone NIfTI工具/原mask不改。

完整QIDO分页与整序列WADO元数据精确UID集合核对，跨页/单项重复拒绝，读后复查UID集合、元数据版本及固定服务标识；最多512实例、256MiB未压缩像素预算、单帧32MiB/元数据4MiB继承边界。经典非MOSAIC单帧MR要求同FrameOfReference/方向/PixelSpacing/矩阵位布局，按IPP投影到IOP法向排序，保留原DS与UID，不用InstanceNumber/文件名排序。重复层位、多时相/回波未分组、面内偏移/剪切、非均匀层距/疑似缺层、声明层距不符及单层三维入口明确拒绝，无配准/补层/重采样。SliceThickness不替代层间距。输出model_input_eligible/dicom_view_accepted=false、sequence_role=unconfirmed，原像素未取；完整性只针对当前归档UID集合，不声称原采集完整。

207相关后端检查通过/4既有警告，23新增成组行为；已知斜位/负方向、PixelSpacing行列对应、手算毫米点、归档乱序、预算与分页、头部/集合变化、MOSAIC/多帧/混合几何明确拒绝，既有PACS/WADO/保管/核对/世界测量/config/API回归通过。首批58含23成组+35WADO为历史；最终backend-accepted207。

真实浏览器现有病例页未配置状态、明确SYNTHETIC协议空间顺序/XYZ毫米、失败/错身份/重试、换序列/SPA换病例、断连刷新与恢复均通过，页异常/原库写/像素请求0。补充刷新失败清理旧空间和选择，避免残留。两次初版SPA脚本通过动态导入新router改变URL但未操作当前app，改用实际挂载router后通过（mounted-router）；这是工具问题，不改App/router，失败截图和日志保留。初版备份guard误用status而实际列名state，停止前失败，查模型修正，未绕过活动任务检查。

备份后重载实际服务，新view-manifest已注册且实际GET503/unconfigured/no-store，旧WADO边界仍503；真实现有NIfTI Cornerstone3canvas仍正常，0页面异常/写入。因前端改动执行一次最终build（VITE_API_BASE=8012），实际静态HTTP预览同空间UI/错误/清理通过，构建大chunk警告保留，不重复依赖安装或整套交付包。已核验停preview24868并恢复dev，当前backend25508 UTC2026-10-12T20:35:33.7567914Z、frontend23396 UTC20:37:40.5284109Z；地址5179/8012不变、单后端/前端及各一串行worker，无其他长任务。新PACS模块与此前可选pin源码已随新后端加载，但未有真实归档/pin浏览器验收。

重启前原分析/特征活动任务0，SQLite只读备份和恢复副本14表全行一致、featurejobs逐文件复制/SHA相同；重启和生产预览后原14表全行与本轮/旧已验快照完全相同、原MRI/mask/空间夹具/任务/真实候选/隔离目录SHA与依赖版本不变，source数据库未替换、无新表迁移、模型未推理。备份/恢复仅现有业务库副本；不得代替P4真实PACS+业务联合恢复。

P1支持NIfTI已验，P2整体进行中/P2-env受阻，P2-c2成组像素加载到既有Cornerstone入口待实施，P3/P4待实施；真实匹配四序列链路缺数据。F/E旧验收保留、E5受阻/E6进行中、R1待核查/R2–R4待实施。Orthanc官方下载+版本执行曾自动审批拒绝，仅blocked by policy；本轮未重试/绕过，无私有PACS配置或真实入库。当前UPENN MOSAIC拒绝、加工MR_small只作工程材料，没有新下载/安装/训练/推理，也没有真实DICOM浏览器/模型/PDF新路线通过。

下一轮第一步：锁/反馈/当前PID及启动时间核对后，继续P2-c2基于已装Cornerstone5.7的WADO-RS metadata provider、成组像素与既有CornerstoneViewer接入；图像缓存必须带来源/版本、加载取消/换病例清理，失败明确，不静默切Canvas，DICOM未证实的测量保存/编辑和AI提交不开放。真实归档/数据条件可用时优先验，不重复环境失败、空查询、安装或整包审计。


## 以下为之前窗口的历史记录
## 2026-10-13 03:18窗口（10/12夜至10/13凌晨）

run_id 20261013T031824_36706fc0；FileShare.None实际持有者/owner25212、原生UTC2026-10-12T19:18:23.8712271Z、开始UTC19:18:24.482057Z、session90335；结束/耗时/正常释放见summary/lock-released。无新反馈，不改REVIEW_FEEDBACK，不提交/发布。

P2-b4只读归档核对工程与P2-a1可选服务标识绑定已验收：新增 services/pacs_reconcile.py、tools/reconcile_pacs_candidate.py、tests/test_pacs_reconcile.py；pacs_client.py增加可选服务端 expected_database_server_identifier，并在连接时核对，显式设置后纳入现有病例关联fingerprint。未配置该字段仍保持旧origin SHA；加pin/改pin不自动重绑定旧记录，返回mapping_conflict。无数据库表迁移/浏览器凭据/自动首次信任。

核对工具从已验隔离收据只读取得UID/SHA/大小，经后台强制鉴权、固定逻辑服务标识，检查不覆盖/无摄入转码策略，用只读POST /tools/lookup取得唯一Instance，再核对Instance→Series→Study的UID与归档原文件完整字节SHA，结束时复查目标和UID映射。查询失败/404/空body/断连不是“不存在”；返回matched_existing、absent_at_check、conflict或unresolved。匹配只是时间窗口内已见相同文件，不表示本工具上传、候选批准或模型输入合格；upload_allowed和archive_imported_by_tool恒false。没有POST /instances、DELETE、修改/去标识/写回归档。

最终184相关后端检查通过/4既有警告，较上轮新增37行为（34归档核对含真实CLI/合成Part10、3旧关联pin回归），明确TCP协议夹具不是Orthanc。断连后新进程只读重查成功、首个失败观察文件不覆盖、父UID/hash/策略/目标变化和非法返回路径明确拒绝，旧配置fingerprint保持，同origin换pin不覆盖旧病例关联。首轮新测试误用confirmed字段，返回422；依据既有acknowledge_case_match契约修正测试，失败backend-related.log保留，最终backend-accepted.log通过。

真实UPENN候选只读收据核对实跑退出3、unresolved/unconfigured、verified_present_at_check=null、原preflight=rejected、candidate_approval_verified=false；没有私有PACS配置或真实服务，更不能称已保存/缺失。原隔离目录所有文件SHA不变，仍1实例/2收据，原候选字节SHA不变；原业务14表全行、MRI/mask/空间夹具/featurejobs SHA和依赖版本不变。backend34700/frontend22108的PID/原生开始时间/健康由既有脚本复用，未重启；本轮新pin API逻辑在隔离新进程验证，正在运行的PACS模块没有重载，不宣称真实归档或新pin浏览器验收。无新下载、安装、前端构建、模型长任务。

独立P2-data核实：复用已装官方pydicom3.0.2 wheel内MR_small.dcm，9830字节、64×64，原文件和README逐字节匹配发行wheel。发布者说明源为NEMA WG04 MR1_UNC、经过缩小处理；这是发布者加工的工程测试材料，不能称本系统取得了原始采集队列。经典MR头部布局检查与8192像素字节长度匹配，仅布局通过；原始患者许可/完整去标识、缩小后物理几何/像素复核/匹配四序列均未独立核实，原预检仍rejected/归档false，不伪造TCIA source-manifest、不复制/下载原文件、不加入病例或模型。本轮不据低分辨率样例报告临床性能。

P1 NIfTI已验、P2整体进行中/P2-env受阻、P3/P4待实施，匹配真实DICOM四序列端到端仍缺数据条件；F/E历史验收保留、E5受阻/E6进行中、R1待核查/R2–R4待实施。实际Orthanc部署/导入/真实DICOM浏览器、可信来源与复核、联合恢复/性能/报告未完成。自动审批曾拒绝Orthanc官方下载+版本执行，仅blocked by policy，本轮未重试/绕过；解除需可审核环境动作或已装服务，不要求用户重复一般授权，无即时用户动作/正在运行的长任务。

下一轮第一步：核对开发锁/反馈/服务，读pacs_wado与已装Cornerstone DICOM加载器，继续P2-c1受支持成组实例的FrameOfReference/方向/spacing/物理排序与明确拒绝，再接入既有阅片入口。归档/来源条件可用时优先真实验证，不反复空查询/安装/打包；不得把工程或加工样本冒充真实四序列闭环。


## 以下为之前窗口的历史记录
## 2026-10-13 02:15窗口（10/12夜至10/13凌晨）

run_id 20261013T021550_d6134bcb；操作系统 UTC 与原生锁进程启动值见 lock-acquired.json，FileShare.None holder/owner18708，session75448；结束/耗时/释放见 summary.json。P2-b3隔离保管工程已验收，P2整体仍进行中、P2-env受阻，P1受支持NIfTI已验收，P3/P4待实施；历史F/E验收保留，E5受阻/E6进行中、R1待核查/R2–R4待实施。无新用户反馈，不改 REVIEW_FEEDBACK，不提交/发布。

新增 backend/app/services/dicom_custody.py、backend/tools/retain_dicom_candidate.py、backend/tests/test_dicom_custody.py；预检增加 source_uid_binding_verified，仅表示文件UID与声明/文件元信息匹配，不代表发布者认证。新工具将有UID绑定的候选快照留在 E:/BrainFusion-Runtime/dicom-quarantine/<独立目录>，SQLite账本与业务库分离，内容SHA寻址、同卷原子无覆盖发布、BEGIN IMMEDIATE串行写。相同SOP/字节重试新增收据，不重写对象；SOP不同字节/父UID、Series改属Study明确拒绝；缺失/损坏对象不静默修复。manifest/review仅声明，所有结果 archive_eligible/archive_imported 恒false，私有属性候选仍只能隔离保管，不提供浏览器原文件或PACS上传入口。

最终147项相关后端检查通过、4既有警告；19个新增保管行为含真正跨Python进程重试与独立进程检查、父UID冲突、声明UID不能污染账本、审计/manifest/对象/父映射损坏检测、未提交完整对象重试接管、隔离副本恢复。第一次账本INSERT占位数量错误已定位修复，backend-first.log保留；139是补充前历史，最终backend-accepted.log为147。崩溃残留用明确夹具模拟，未声称真实断电恢复或对抗本机管理员篡改。

实际复用上一轮UPENN公开单实例，原字节1609460、SHA bd75b6ee1175a26d0b505035da1694a2c928c7c1a53344444b24b2ca8fc11443；首次/重复各独立CLI进程，1实例/2收据，source_uid_binding_verified=true但预检rejected、没有pixel-review，未进入PACS/病例/研究队列。继而用SQLite只读源backup API和字节文件复制备份，再恢复至新独立目录，独立进程检查通过，3张保管表全行与原源一致、对象与候选逐字节相同、原保管目录库存SHA不变。只验隔离保管恢复，不代替P4真实Orthanc索引/原文件与业务库联合恢复。

state-validation：原业务14表全行与已验快照相同、原MRI/mask/空间夹具和featurejobs SHA相同、依赖版本不变。现有后端34700（UTC2026-10-12T16:43:06.8049752Z）、前端22108（UTC16:43:06.8122342Z）身份/健康由既有脚本核验复用，无服务重启、新下载/安装/构建/浏览器重复验证/模型任务；无新的浏览器验收或截图，保持上一轮历史证据。

本轮不宣称真实PACS或DICOM阅片通过；完整抽查/剩余步骤见 P2_DICOM_CUSTODY_VALIDATION.md。

## 以下为之前窗口的历史记录
## 2026-10-13 01:19窗口（当前；10/12夜至10/13凌晨）

run_id20261013T011921_b6663451；系统UTC/原生PID精确值见本run lock-acquired，FileShare.None holder实际保持、session58224，结束/耗时/正常释放见summary。P2-b2只读递归预检工程已验，P2整体/导入仍进行中，P2-env受阻、P1 NIfTI已验、P3/P4待实施、E5受阻/E6进行中，R1待核查/R2–R4待实施。无反馈、不改REVIEW_FEEDBACK、不提交/发布。

新增services/dicom_preflight.py、tools/audit_dicom_preflight.py及tests/test_dicom_preflight.py：完整Part10/FileMeta/所有SQ/像素后属性，64MiB/10000元素/24层/1000命中上限，禁止重写/上传，报告/终端不输出字段原文。来源及像素review绑定SHA与UID/声明，标记嵌套ID/姓名/私有/日期文本/opaque/未知引用/烧录与缺复核；复用经典非MOSAIC布局/像素长度。archive_eligible、deidentification_complete恒false，自填manifest/review不等于独立认证或入库许可；可通过工程规则仍不能直接归档。标准FileMetaVersion精确例外与嵌套ID/加密SQ绕过保护已回归，初次标准版本误报日志保留。

官方PyPI固定pydicom3.0.2纯wheel2376822字节，发布SHA abf971a5440f84dbaf42c4b6758e30e62480902584f8b270b9a5d146e278a07b；E盘缓存、现用Python离线no-index/no-deps/no-compile只加一包，285个安装payload与wheel一致、所有旧包版本不变、torch2.11.0+cu128/CUDA正常。新增requirements-dicom-preflight.txt哈希锁，不改worker/PATH/系统证书/其他prefix，不重建旧环境。发行元数据license字段空，原LICENSE文本保存，不自行补SPDX。

最终134后端/4既有警告，34新合成Part10行为加100相关回归；真CLI拒绝/不覆盖、深层姓名ID/私有/引用/像素后字段/压缩/哈希/限制与脱敏。实际UPENN原候选复用，扫描169元素/83命中、退出3/rejected，33private等可能同标签多规则，不能称83项已证实泄漏，原SHA bd75b6ee1175a26d0b505035da1694a2c928c7c1a53344444b24b2ca8fc11443不变；没有像素review、不伪造医生或批准。state-validation原14表全行与上轮已验副本、科学/featurejobs SHA相同。无API/前端业务改动、不重启、不重复构建/浏览器/整包审计或推理/提取。

有限来源查找：TCGA-GBM一个候选ID和公开患者索引HTTP200空body，未取得患者/影像；两次无进展转查官方来源，不反复相同查询。Brain-Tumor-Progression索引也空，官方集合明确NIH受控申请，不下载或联系发布者；TCGA详情直接读取500，不仅由空body推断原因，未取得状态保持，无旧镜像/受限token尝试。空响应不是有效JSON或下载成功，本轮没有新DICOM下载。具体P2_DICOM_PREFLIGHT_VALIDATION。

- 改动：上述service/CLI/tests/requirements，P2_DICOM_PREFLIGHT_VALIDATION和本轮台账/阶段/交接/概要/README/发布/环境/PACS准备/daily；不修改旧mask/Canvas/Cornerstone/API业务。
- 当前服务34700 UTC2026-10-12T16:43:06.8049752Z、22108 UTC16:43:06.8122342Z，http://127.0.0.1:5179/case/17及workstation/17、API8012/docs；身份健康复用、PID不变、Runtime/local登记及{backend,frontend}.{err,out}.log。各一串行worker、无下载/训练/推理/构建长任务。
- 原配置仍10/10 01:06/runtime-supported.json/数据库/featurejobs/gate，00:06uploads/model/data/research；Radiomics311-candidate不变。主Python只新增pydicom3.0.2，旧CPU/worker/源码交付包未刷新，仅历史；新DICOM工具依赖在requirements-dicom-preflight.txt，不将其混入旧Radiomics或称容器已安装。旧preview联接不npm ci/递归删。
- 候选路径E:/BrainFusion-Data/PACS-candidates/UPENN-GBM/20261013T002126_88fd439c/single-instance.dcm，本run/candidate-source-manifest.json由上一轮真实download生成，真实最终拒绝report为real-candidate-preflight-final.json；未生成真实pixel-review。合成review仅测试夹具，不能移用于真实病例。输入/输出只读核查，无正式PACS配置或归档记录。
- 阻塞/未验：Orthanc官方候选下载+版本执行之前自动审批仅blocked by policy，本轮未重试或绕过；真实入库授权/来源审核/复核、重复UID冲突/归档持久化/支持DICOM样本/真实阅片、P3/P4/E5/E6/R余项未完成。当前CLI永不直接放行归档，符合本工程范围；无需立即用户动作/重复一般授权。
- 下一轮第一步：锁/反馈/上述PID及原生启动身份、ReuseExisting原01:06配置/8012/5179；复用新预检/候选/SHA，不重下。继续可信来源与像素复核证据/同文件SHA绑定的导入账本及UID重复冲突规则，审核authority不能由用户JSON自述替代；保持原文件与版本。支持的经典MR来源按当前许可筛选，受控集合只记录条件，不尝试旧镜像或联系发布者。
- 抽查01:19窗口：打开输出real-candidate-preflight.json，decision=rejected/archive_eligible=false且只有标签路径/原因；原候选1609460字节/SHA保持；case/17仍未配置/无候选关联。CLI复跑必须新E输出、真实无review不传pixel-review，退出3是明确拒绝。P2_DICOM_PREFLIGHT_VALIDATION包含精确步骤/证据；无本轮新浏览器证据，不冒用上轮截图为新验收。

## 以下为之前窗口的历史记录

## 2026-10-13 00:21窗口（当前；对应10/12晚至10/13凌晨）

run_id20261013T002126_88fd439c；系统UTC2026-10-12T16:21:26.4921910Z/北京00:21:26，FileShare.None holder/owner19652、原生16:21:26.0976807Z/session42261。结束/耗时/正常释放见本run summary。P1受支持NIfTI已验、P2进行中/P2-env受阻、P3/P4待实施、E5受阻/E6进行中，R1待核查/R2–R4待实施。无具体反馈，不改REVIEW_FEEDBACK；无提交/发布/模型或提取协议变更。

新增受限WADO metadata标准DICOM JSON数组与frame1，严格3UID/经典非MOSAIC单帧MR/方向/spacing/8或16bit/32MiB/MIME完整唯一part/未压缩LE/精确字节长度；不校正空间、补齐或截断。后台凭据隔离，移除外部BulkURI/姓名ID/private与自由描述，仅在allow_pixel_read严格bool开启时提供本站frame URI，默认false。status开关不是能力验收，DICOM viewer/AI仍false，无正式PACS配置。

最终100后端通过/4既有警告（35新WADO真实TCP合成夹具，不是Orthanc），原库只读快照/恢复副本先验证，实际重启后14表全行/原科学文件/所有featurejobs SHA相同。browser-wado-boundary实际新端点503/no-store/pixel=false、病例原UI未配置、NIfTI三canvas正常，异常/真实写0，截图已看。无前端业务变化，不重复构建/依赖安装/打包/推理或提取；96/99及更早测试是追加检查前历史。

官方公开NBIA v1返回UPENN-GBM匿名00001六Series六Study、CC BY4.0；四描述Processed_CaPTk不代表原始采集四序列/角色。扩散候选78对象125537564字节，先估单例1609456、cap8MiB/512MiB空间余量，实际只下一个1609460字节。完整URL/UID/许可/本地SHA与文件见P2_WADO_VALIDATION；没有官方该单实例SHA。真实DICOM留E:/BrainFusion-Data/PACS-candidates/UPENN-GBM/本run/single-instance.dcm，现用GDCM读出SIEMENS/MOSAIC896×896×1/33private/烧录缺、PatientIdentityRemovedYES及姓名等公开匿名ID，仍未证明完整脱敏或原始采集谱系。真实头部经最小协议对象验证422/unsupported_mosaic，不是实际WADO；原文件SHA不变，不入归档/病例/科研队列。源SHA bd75b6ee1175a26d0b505035da1694a2c928c7c1a53344444b24b2ca8fc11443。

首个数据helper不用Windows正常网络路由导致TLS首败，恢复正常系统网络路由后成功、仍验TLS、不改CA/系统代理。数据下载是新动作，不是重试被拒Orthanc二进制；失败及首败后检查不存在记录的日志保留，成功后才实际读头。partial/Range恢复实现但中断未验，不重复已完成下载。PyDicom主环境不存在，无新安装，GDCM有限诊断不能冒称递归脱敏审计。

- 已改backend/app/services/pacs_client.py/pacs_wado.py、api/pacs.py、tests/test_pacs.py/test_pacs_wado.py；frontend仅tools/verify_wado_boundary.mjs验证工具，无UI/依赖变化；本轮P2_WADO_VALIDATION及台账/阶段/交接/概要/README/发布/PACS准备/daily。
- 当前backend34700 UTC2026-10-12T16:43:06.8049752Z、frontend22108 UTC16:43:06.8122342Z，http://127.0.0.1:5179/case/17、workstation/17及API8012/docs；登记Runtime/local/processes.json，日志Runtime/local/{backend,frontend}.{err,out}.log。各一个串行worker、无下载/训练/推理/构建长任务，不沿用11936/25508或中间8680/31244。
- 原01:06/runtime-supported.json/数据库/featurejobs/gate与00:06uploads/model/data/research保持，Radiomics311-candidate不变。候选不纳入UPLOAD_DIR/DATASET_DIR；无正式配置、像素默认禁用。旧preview依赖联接不能npm ci/递归删。
- 未验：Orthanc/插件/实际导入/像素响应/真实DICOM阅片/重复/持久化，P3匹配四序列与转换模型、P4联合性能恢复PDF、E5/E6/R余项。环境自动审批仍仅blocked by policy，本轮没有重复下载/执行或换工具绕过，不需用户重复授权/立即动作。
- 下一轮第一步：锁/反馈/上述PID原生身份后ReuseExisting（原01:06配置/8012/5179），复用候选/清单不重下。继续P2递归DICOM标签/私有/像素审核和原文件保留的入库契约，选择有限非处理/非MOSAIC经典MR来源、先预算；完整parser依赖按官方固定来源配置，现有GDCM不冒称嵌套审核。不默认开像素、不按名称猜四序列或自动拆块/配准/重采样。
- 抽查10/12夜至10/13凌晨00:21窗口：status的unconfigured/pixel=false→新metadata/frames1均503→case/17归档未配置/候选未关联→原NIfTI Cornerstone三视图。完整P2_WADO_VALIDATION与本run summary。10/12旧日报保留，此轮记10/13，未跨午夜覆盖上一晚。

## 以下为之前窗口的历史记录

## 2026-10-12 23:25窗口：P2读取/关联工程验收（当前）

run_id20261012T232541_082a3a38；UTC15:25:42.0896792Z/北京23:25:42，独占FileShare.None holder16576，原生15:25:41.4686218Z。P2-a工程小批次通过，P2整项仍进行中/P2-env受阻，P1受支持NIfTI已验、P3/P4待实施、E5受阻/E6进行中、R状态未变。

实际接入后台loopback强制鉴权QIDO元数据读取/分页/UID父关系检查/4MiB限制/凭据隔离/no-store；新增独立pacs_study_links绑定病例，元数据快照与SHA，同检查重试去重、跨病例/地址改变409，不修改MRI。既有病例详情新增归档状态/层级清单/显式核对与关联UI，未配置/断连具体显示，未开放DICOM导入/像素/阅片/AI入口。

65后端通过/4既有警告，其中31PACS；loopback TCP协议夹具、隔离SQLite重开不是实际Orthanc/DICOM。旧库快照/恢复副本先迁移，正式原库仅加空表，全部旧13表行、原科学文件与featurejobs SHA相同。browser-pacs-final通过真实不可用/明确合成UI/病例清理/连接错误及重连；最终build-api-8012与实际HTTP生产页面及原NIfTI三canvas通过，0页面异常/真实写，恢复dev。初版忘构建API导致请求旧8000和其他脚本/夹具失败全部保留，不当作通过。详见P2_READ_PROXY_VALIDATION。

服务当前backend11936 UTC15:43:22.3357500Z/frontend25508 UTC15:46:50.5940729Z，http://127.0.0.1:5179/case/17/API8012/docs；前端本run/restored-dev-final日志，登记Runtime/local/processes.json。原01:06运行配置/数据库/worker/gate及00:06uploads/model/research/dataset保持。无真实PACS配置、长下载/训练/推理/构建，未提交/发布/变更科研结论。

Orthanc环境自动审批阻塞保持，本轮未重复下载+版本执行；真实样本、导入、像素/WADO与DICOM阅片、P3模型桥接/P4联合验收未完成。下一优先P2-b脱敏入库契约和受限WADO工程及有限真实数据来源；任何协议夹具不得替代真实归档/端到端证据。证据根E:/BrainFusion-Runtime/results/nightly/2026-10-12/20261012T232541_082a3a38，结束/耗时/锁释放见summary。当前仍不是完整系统交付。

## 以下为之前窗口的历史记录

## 2026-10-12 22:20窗口：P1 NIfTI新入口验收（当前）

run_id20261012T222030_9ac688e4，UTC14:20:30.6137176Z/北京22:20:30，FileShare.None holder/owner25680原生14:20:30.1968765Z。接续首批后完成P1-c并验收P1的受支持NIfTI路径。P2进行中，环境动作受阻；P3/P4待实施，E5/E6/R状态保持，尚未完整系统交付。

新增独立mri_world_measurements和mri_view_states表，原Canvas标注保留。Length为LPS毫米端点与方向，绑定MRI ID/几何hash/全部序列mtime-size revision/分析版本，服务器计算毫米、验证平面/体素边界与版本；相同UID重试去重，已保存记录只读，旧版本保留但不当前叠加。视图显式保存为新版本，含序列、三物理相机、按序列窗值、mask显隐；保存后URL明确保留Cornerstone入口，手动Canvas清除选择。方向标记由实际canvasToWorld计算，不依原数组轴名猜方向。

实际验证：43后端/4既有警告；原库快照/恢复副本迁移两表、旧表全行一致；独立副本真实三平面Length/工具mm与世界坐标相符、实际提交成功却丢响应的重复保存去重、浏览器刷新、实际后端/前端重启、删除后刷新；视图保存/刷新/重启恢复相机/位置/窗值/T1n与隐藏mask；实际病例17→1→17无草稿/引擎残留。明确合成3×4×5、1.5/2/3mm轴置换/翻转NIfTI在浏览器indexToWorld与nibabel参考相同、12方向标记/毫米创建删除通过，不冒称患者/DICOM/AI输入。最终build实际HTTP三视图/四序列/未保存测量/Canvas往返、最终core回归通过。早期绘制提示使viewport移位已修复，失败证据保留。

原库恢复且仅增加两个空表，原科学数据/旧标注/任务/worker/model/gate不变；service backend21840 UTC14:57:35.6727315Z、frontend24420 UTC15:00:57.6624339Z，http://127.0.0.1:5179/workstation/17，API8012/docs。生产preview曾单前端试运行20484，后恢复dev24420，后端不变；本run/restored-dev日志，登记Runtime/local/processes.json。独立副本保留测量/视图试验和显式合成病例19，仅用于证据。

P2官方Windows独立二进制core1.13.0/DICOMweb1.24已找到、HEAD大小/时间验证200；没有下载完成、版本/插件/归档未验。Python网络下载因环境CA失败而保留日志，未禁TLS或改证书；下载+运行版本探测复合命令自动审批拒绝，仅返回blocked by policy，未执行。无需重复用户授权；下一优先P2代理/UID映射等独立工程，并在可审核环境条件满足后继续本机归档。PACS_LOCAL_PREPARATION与本run orthanc-policy-rejection记录解除条件。

最终证据E:/BrainFusion-Runtime/results/nightly/2026-10-12/20261012T222030_9ac688e4，P1_MEASUREMENT_VIEW_VALIDATION/summary。以下段落均为历史，不能把其未实施状态或旧PID当当前。

## 2026-10-12 21:18窗口：PACS路线首批实施（当前）

run_id20261012T211814_d5bca694；系统UTC13:18:14.6986604Z/北京21:18:14，实际FileShare.None holder/owner24228，原生启动13:18:14.0824133Z。22:02触发续接同一活动批次，没有建立第二开发实例。P1-a/b小批次已验收，P1整项进行中；P2/P3/P4待实施。F/E原Canvas历史成果保留，迁移回归另列；E5仍受阻，E6进行中，R1–R4状态不变。

Workstation现在实际提供Cornerstone3D手动入口，Canvas为默认已验入口。已安装core/tools5.7.0；修复旧接口、滚轮未注册、异步叠加重置切片位置、组件切换生命周期及上下文累积。MRI原始字节接口绑定MRI ID和文件size/mtime revision；四序列通过既有空间契约再读取，不从显示名猜身份。读取已有nifti-reader-js0.6.9，显式原体素RAS→LPS几何适配，sform优先与nibabel一致，保持体素顺序/强度，不配准或重采样。模型mask单位缺失时仅在与毫米参考MRI完全同网格时允许只读叠加。

证据根E:/BrainFusion-Runtime/results/nightly/2026-10-12/20261012T211814_d5bca694。最终geometry/validation.json：4真实MRI与真实mask每体素SHA/独立点坐标一致，另2显式合成NIfTI1/2翻转/非单位spacing/缩放夹具通过；backend-final.log27通过/4既有警告。最终浏览器browser-final-complete：真实鼠标工具/四序列位置保持/非空叠加像素变化、明确拒绝、显式Canvas/刷新默认入口、加载中退出与SPA退出清理；主动上下文释放的已销毁engine库警告保存，不能称无警告。实际构建与最后源码绑定见summary.json。

当前服务5179/8012，backend17080 UTC13:39:51.6786448Z、frontend10052 UTC13:39:51.6863663Z，原配置及科学产物保持；重启前原库快照和恢复副本在本run/database-backup。无下载/训练/推理/提取长任务。测量持久化、视图刷新恢复、方向标记、其他病例和DICOM路径未验。下一步P1-c接入世界坐标测量与版本绑定。具体操作/失败历史见P1_CORNERSTONE_VALIDATION、NIGHTLY_HANDOFF；此前章节为历史。

## 2026-10-10第十二轮（08:11起，10/09晚间窗口，最新）

run_id20261010T081105_95f1c109；系统UTC00:10:51初检、正式run00:11:05.6865253Z/北京08:11:05，FileShare.None holder/owner34748原生启动00:11:05.2840076Z。E6独立受支持worker离线引导及小型入口/profile包与组成说明两小批次已验；整项仍进行中、E5受阻、F1–F6/E1/E2/E3/E4保持已验/R1待核查/R2–R4待实施。无新具体反馈、不改REVIEW_FEEDBACK，不提交/推送/发布/删除原数据。

新增prepare_radiomics_delivery/bootstrap_radiomics_delivery、10行为及RADIOMICS_DELIVERY_BOOTSTRAP，文档/源码白名单同步。旧setup入口是借调用者pip的3.9历史脚本，保持归档、不作为当前引导；新标准库入口+可信E盘Conda→20原SHA本地解释器包→新prefix自身pip无网络安装11wheel。15元信息/pip check、11实际安装报告SHA、20实际conda-meta SHA/版本、1102导入payload文件及python.exe/python311.dll与冻结已验worker一致。10官方原发行缓存（9wheel+docopt SDist），docopt缓存本地wheel来源/模块与SDist核对，PyRadiomics为已验原源码编译wheel，均不冒称上游二进制；全部缓存复用无新下载，31安装文件77440693字节非流量。

初版radiomics311-delivery-本run重建后发现验证隐式读取原环境目录，改冻结payload独立校验并在全新-independent prefix实际重建；原路径仅溯源，默认安装不要求原worker/来源锁/gate存在。最终profile SHA bcfe4fc9ae59e38f963361e685018338d1c3537e364d8db7883d033c20bee83c，新source身份不同，原worker/source/gate不改，不伪装兼容门槛或切换服务。真实解包的独立标准库入口及原路径不存在派生profile验证通过、当前入口坏profile SHA/自己损坏wheel cache实际CLI在输出/prefix前拒绝。初版ruamel.yaml分发名点号遗漏与Windows3.10 ZipInfo规范filename测试两次失败保留，读取标准库后增加orig_filename保护，最终120后端/4既有警告及CPU解释器10行为通过。

最终证据本run/final-validation-complete（不是初版final-validation的119门槛）；worker-bootstrap-independent真实Conda14300/pip35540/check31064均正常completed，原生时间/命令/日志留存。小型引导包77848字节SHA2027dd4e87ce88d3c5c799a0f5768fc9156fa63790746a9f6c28a75253e5d70b，5负载/manifest、ZIP成员和当前入口SHA/实际解包验证；不含11wheel/20Conda第三方二进制、数据/模型/库或完整项目。当前源码有限审计241文件1143892字节，无发现；07:05的237全源包有本轮增量，明确历史、不覆盖，不冒称小包是完整源码包。

原服务31840/8912及原生启动UTC21:30:04.2527517Z/23:22:16.1822222Z未动，5179/8012，01:06配置/现用worker/恢复库保持；全表与前轮、10API/53主包/C盘Conda登记不变。无新推理/特征/55/252/训练/病例PDF/UI或浏览器截图、科研结论。无持续任务；本轮锁仅自己release核验，实际结束/耗时见summary。新候选科学门槛/配置服务切换、异机及E5/Linux未验，第一阶段仍未完成。下一轮先锁/反馈/活动任务/服务，核查新来源门槛与隔离配置前检的最小必要验证及可用交付组成；不重复缓存安装或旧模型实验。

## 前轮历史（以下不替代08:11证据和引导边界）

## 2026-10-10第十一轮（07:05起，10/09晚间窗口，最新）

run_id20261010T070557_2d087f2d；系统UTC23:05:50初检、正式run23:05:57，FileShare.None holder/owner33176、原生启动23:05:57.9846583Z。E6独立前端引导与真实单前端服务/重启/回退两个小批次已验，整项仍进行中；F1–F6/E1/E2/E3/E4不变、E5受阻、R1待核查/R2–R4待实施，无具体反馈，不改REVIEW_FEEDBACK。

新增prepare_frontend_delivery、7项行为测试、verify_frontend_delivery_browser和start_frontend_only；既有start/stop脚本增加明确FrontendOnly路径，默认复用行为保持。官方Node24.21.0 ZIP37618919字节/SHA实下载核验后仅解包到全新E盘prefix，自身npm11.19.0/全新非联接frontend按06:06冻结官方resolved候选实际npm ci禁安装脚本；原422项身份/版本/SRI/别名不变，Windows实装396、26可选平台项省略、396对应tarball SHA512与包身份全匹配，文件总量67060361字节不是流量。原镜像锁/原node_modules/系统PATH不改，初次API默认为8000的构建仅保留历史；显式真实8012的独立构建及最终必填--api-base工具全新prefix构建29文件完全一致。最终396全缓存复用，不在同目录重试npm ci。

先做原库快照及副本完整性/逐表保护，再只切换登记前端17736→25300 preview→28276 preview重启→8912原开发服务；后端31840原生启动UTC21:30:04.2527517Z全程未变。占端口时新启动实际拒绝且登记不变。两轮真实HTTP读取构建资源SHA、病例17/三视图/四序列/自动特征与版本/报告独立意见四页面与截图通过，页面/console/网络/写请求均0；不用route模拟来源冒充部署，没有关闭浏览器安全或授予loopback权限。两次早期拦截来源LNA失败转真实HTTP策略、ZIP根目录/凭据扫描夹具/Win32长路径中间失败日志均保留。截图视觉已检查；当前中心层mask可能为空，不能写为分割准确性证据。报告入口不是本轮新PDF检查。

110后端通过/4既有警告、7新增检查、PS语法/实际试运行/默认复用通过。final-validation确认10个API与05:08相同、现用/备份/副本与06:06全表内容签名相同、53主包/C盘Conda登记/原62前端文件与镜像锁不变。源码/引导指南、README/环境/范围/发布清单已同步；最终新源码包及解包SHA见cpu-source-bundle-complete、source-package-validation与summary，旧包不覆盖、不含数据/模型/第三方二进制/环境/Node依赖。未重新推理/提取/训练/导出病例PDF或改研究结论。

当前5179/8012；backend31840保持、frontend8912实际UTC23:22:16.1822222Z（本轮前端身份更新，17736已停）；前端日志本run/restored-dev-service，后端日志Runtime/local。现用01:06 runtime-supported.json和既有3.11特征worker/恢复库不改。无持续下载/训练/推理/构建；锁仅自己release并核验，实际结束/耗时见summary。下一轮先锁/反馈/服务与任务身份，然后核查独立特征worker引导及CPU主/Node/恢复数据的组成角色，消除新机指南隐式借旧工程pip；不重复55/252或CPU模型对照。异机、Linux/E5与完整第一阶段仍未完成。

## 前轮历史（以下不替代07:05本轮证据）

07:31最终包补验：237源码1110055字节、cpu-source-bundle-complete外包489442字节SHA3394e40d5a1f76fa09363c069e9cc55f23e093087c7ec092c2506a1174850b5a，源ZIP SHAf1b2e4b98d1f08fe59b3a45eed171c4e9ffd6bfe29cc81d0d2ca02c29ed1e691。可信外SHA与全部外/内成员核验、当前/独立解包237逐SHA一致；独立解包复用06:06已验CPU解释器110后端/4既有警告通过，没有再安装环境/特征模型运行或Node联接。source-package-validation不升级为新机验收。

## 2026-10-10第十轮（06:06起，10/09晚间窗口，最新）

run_id20261010T060619_ce64597d；系统UTC22:05:51初检，正式run/独占锁22:06:19，holder/owner32236、实际启动UTC22:06:19.2548803Z。E6源码/完整CPU来源锁迁移包和独立stdlib离线新prefix重建小批次已验，整项仍进行中；F1–F6/E1/E2/E3/E4不变，E5受阻、R1–R4无新研究验收。无具体反馈，不改REVIEW_FEEDBACK。

新增bootstrap_cpu_delivery、prepare_cpu_delivery、11项行为测试及CPU_DELIVERY_BOOTSTRAP；修改源码白名单和README/运行/来源/环境/概要/范围/发布台账。实际不借旧工程pip，用E:/Anaconda3标准库入口+可信Conda从20Conda/52轮子SHA缓存完全离线引导新runtime311-cpu-delivery-20261010T060619_ce64597d；新prefix自身pip force-reinstall，52元信息和安装SHA全一致、pip check通过。现用主/既有CPU候选原树/新CPU独立解包副本各103后端通过、4既有警告；11依赖/既有工作器/模型/谱系/SQLite只读前检与全库不变通过。坏ZIP与坏轮子实际CLI在输出/prefix创建前拒绝；53主包与C盘Conda登记SHA未变，默认CUDA/服务不切换，无新推理/提取/训练/病例PDF/浏览器实验。

最终cpu-bundle-complete为232文件1063954字节源码、内部包470360字节SHA a65d16da31f793861a583b8272d28a7e0bd62cdcd7e116f1035d8d4ad8c205db；当前/嵌套ZIP/解包逐文件相同，后端/前端实现字节与测试的初版一致，CPU锁与实际重建初版一致。初版包留作历史、没有覆盖。包不含MRI/模型/数据库/第三方二进制/环境/Node依赖，不是完整新机开箱部署。

第二批前端来源预检：原422项npmmirror锁保持SHA16e27a2b8ab0d3078520170532e2df76281396c78bdd6eaf8b6a132fc4b9d2ab；官方固定版本元信息/SRI422匹配，外部候选仅resolved地址改变。初版按目录名漏掉Element Plus的@popperjs/core→@sxzz/popperjs-es明确npm别名，保留失败预检、只追加真实别名元信息后通过，未替换依赖。Node24.21.0官方manifest/ZIP HEAD预算37618919字节已记录、签名未验；没有Node/npm tarball下载、安装或构建。最终frontend-source-probe-complete不是实际安装验收。

证据根E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T060619_ce64597d：cpu-bootstrap-rebuild、三-suite日志、negative-cli-validation、cpu-bundle-complete、stdlib-unpacked-complete、isolated-readiness-complete、final-validation、frontend-source-probe-complete；summary保存实际耗时/锁释放与用户输出清单。病例17十个只读API与前轮完全相同、全库不变、服务31840/17736实际启动UTC21:30:04.2527517Z/21:30:04.2595763Z，5179/8012。无持续下载/训练/推理/构建进程，E5系统授权窗口仍缺，不重复失败安装或重启机器。下一轮先锁/反馈/任务/现有服务复用，再在无联接全新E目录按已核验Node来源与原SRI前端候选实际下载安装/构建；不对测试node_modules联接npm ci，不改原锁/默认服务，不重跑55/252或CPU模型对照。异机、独立特征环境引导与Linux/E5仍披露未验。

## 前轮历史（不替代本轮证据）

## 2026-10-10第九轮（05:08起，10/09晚间窗口，最新）

run_id20261010T050838_9f671276；系统UTC21:08:26/北京05:08:26，实际锁21:08:38/holder23824，结束/耗时/释放见summary.json。E6独立Windows CPU主候选与真实服务试运行/回退小批次验收，整项仍进行中；F1–F6/E1/E2/E3/E4不变，E5受阻、R1–R4无新研究结论。

新增prepare_cpu_runtime_candidate、5来源/兼容测试、CPU_RUNTIME_CANDIDATE；启动器增加可选PythonPath、复用实际解释器核对与登记，修订源码白名单/README/运行/来源/环境/范围/台账。52完整依赖缺项0；52官方轮子234201976字节、20Conda引导37182372字节，合计271384348文件字节（不是网络流量计量）；实际缓存SHA与发布值、安装52元信息/pip check通过。初版pip跳过同版本bootstrap pip/packaging，来源断言失败保留，随后只候选补装2项SHA锁轮子；最终50+2报告52项一致，未来安装force-reinstall。主53包/C登记未变，旧CUDA源仍未知，特征worker/提取协议不改。

双环境最终各92后端/4既有警告、候选11依赖/模型/谱系/原库前检通过；预冻结同公开WAW4病例17CPU串行对照，同四MRI/checkpoint/ROI128×128×96/4线程、独立输出、GPU分配0，240×240×155逐体素差0及affine/qform/sform一致；五开发样本25概率差0，只工程重现不作科学效果评价。副本两候选TestClient启动恢复10接口一致；随后另backup与任务副本，真实CPU首启4576/12800、重启33500/26376，首启4页与重启后四序列/研究/报告/未知临床11截图实看通过。再核验停止候选恢复旧CUDA/01:06配置，CUDA可用；最终31840/17736，startUTC21:30:04.2527517Z/21:30:04.2595763Z、5179/8012。三个服务阶段各10API与之前相同，原/副本全表及18任务文件SHA一致，病例17临床57male/分析/特征/概率/复核/报告不变。

证据根E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T050838_9f671276：cpu-plan/cpu-download/cpu-install、candidate-inventory-complete、双-suite-complete、cpu-model-comparison、candidate-recovery-validation、launcher-validation；final-validation为切服务前门槛，live-final-validation为最终回退、live-cpu-trial/cpu-after-restart-browser为真实截图。没有新特征/训练/病例PDF/前端构建或638全扫，历史55/252不是本轮新实验；225旧源ZIP不覆盖且不称当前。无具体反馈，不改REVIEW_FEEDBACK；保护脏树，无提交推送发布或数据删除。下一轮先锁/反馈/新PID服务与长任务检查，再继续可重建CPU源码/完整来源锁迁移包及隔离目录引导（同机不称异机）；E5仅系统授权窗口解除后，未反复安装/重启，R结论不升级。

## 前轮历史（不替代本轮证据）

## 2026-10-10持续开发第八轮（北京时间04:12起，10/09晚间窗口）

run_id20261010T041309_b7290097；系统UTC开工20:12:56/北京04:12:56、实际锁20:13:09/holder34500。E6两批交付核验验收，整项仍进行中；F/E已验状态不变、E5仍需系统授权窗口，R1–R4无新研究验收。工程论文图表素材已通过，完整研究论文不是额外第一阶段工程图表门槛。

新增verify_delivery_readiness.py/9项行为测试、LOCAL_DELIVERY_ACCEPTANCE，修改源包文档白名单与README/本机/源码/范围/清单/概要。源码ZIP和工程材料不解压执行，只检查显式成员/大小/路径/SHA；冻结旧包显示6新增/6变化、非当前，不覆盖旧包。当前材料27文件、14实现源码与3重现工具绑定相同；CPU来源指纹/20Conda与10PyPI/三锁文本及现存cp311自建轮子核对，无下载/安装/提取。CRLF语义等价比较但原字节SHA保留；故意改坏锁副本被拒且未运行前检，不改正式锁。

新source-candidate-current：225文件1003351字节、ZIP386419字节SHA f084ad1a4362e567821e0fe636cb1c87737d6d6a2ca0b5794cca05a3d3a05140，打包/解包/当前源逐文件一致。原树与解包87后端/4既有弃用警告、原树与解包联合核验和真实preflight通过；前检11主依赖、3.11.17 CPU导入、分割/研究权重与既有门槛、17当前模型记录的谱系和SQLite integrity。新前端node_modules仅自有解包目录到现有E盘依赖的联接，不在ZIP；不删除联接/原依赖，不冒称新机器安装。主53依赖元信息完全不变，DB全表签名与病例17分析/特征/57male/报告版本保持，服务19544/28164与supported配置不变。未重复638原件全遍扫描/快照、前端构建/浏览器截图/五例提取；无新模型/病例/科学结论。

续接第三批仅主CPU环境候选来源预检：复用Conda3.11.17方向，16项直接PyPI观测版本及PyTorch官方torch2.11.0+cpu/torchvision0.26.0+cpu cp311 Windows链接/发布SHA/metadata已核对，18直接轮子合计217287283字节（不含传递依赖/解释器，未下载二进制），E盘约420GB空闲。官方索引指向download-r2，初次严格主机拒绝后核对官方索引，CDN HEAD403；换策略到官方download.pytorch.org原站小metadata，SHA与索引精确一致，原站HEAD大小取得。runtime311-cpu-source-probe-origin是最终来源证据，不将初版incomplete/空final目录当成功。没有新环境/安装/推理；旧主环境原安装URL/SHA仍未知，不由候选新发行推断。

证据根E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T041309_b7290097：source-candidate-current、readiness-current/readiness-unpacked、invalid-worker-rejection、backend-suite-final/unpacked-backend-suite、final-validation、runtime311-cpu-source-probe-origin、service-reuse及最终进程/summary/释放。early CRLF测试失败、错误cwd导入失败、来源主机/403均留档，按日志缩小策略后成功。下一轮优先E6独立Windows3.11 CPU主候选依赖解析与完整字节预算/官方哈希下载/创建全新环境并验证，保持现用CUDA/特征worker，失败不切换；来源预检不算依赖解析或环境通过。E5不重复安装或重启、研究结论不升级。

## 2026-10-10持续开发第七轮（北京时间03:09起，10/09晚间窗口）

run_id20261010T030942_d136a5d2；系统UTC开工19:09:23/北京03:09:23，锁19:09:42实际holder23260，起止/耗时/释放见本轮summary.json。E6两批工程材料已验收，整项仍进行中；F1–F6/E1/E2/E3/E4不变、E5受阻、R1–R4未新增研究验收。

新增只读证据采集/工程绘图/页面截图三工具、THESIS_ENGINEERING_MATERIALS中文图注及来源说明，更新源码白名单/README/概要/范围/发布清单。本轮使用nature-figure和PDF技能约束事实、单画布、字体/矢量导出及实际渲染检查；不是新论文研究章节或期刊提交认证。两图183×120mm、PDF/SVG可编辑、PNG600dpi，最小6pt文字、最终严格碰撞PASS；对齐多面板不适用、非TIFF警告明确披露。独立E盘绘图venv有12官方轮子版本/URL/大小/SHA/许可元信息，49,096,410字节含缓存复用；不改主环境53安装包，快照SHA与02:07相同。新工具环境不属于Web/CUDA或CPU特征环境。

既有公开工程病例17的四张实际页面截图实看；三视图按当前mask最大WT轴面/其质心最近阳性点，选择原空间UI123/97/99层，阳性体素443/288/319，原图未修改，不用于准确性结论。页面与当前分析/临床57male/特征任务/报告绑定，浏览器变更请求0，没有新病例/推理/提取/报告PDF。27文件材料包1,974,040字节、ZIP1,698,988字节SHA ba63e21593633630a4ca464adc9944abaa36e7ae55f30b1cec3dd4a3342e183b，不含MRI/模型/库/依赖环境；输出副本哈希一致。图表原始数据和最终展示选择数据分别保留，不覆历史。

78后端回归通过/4既有弃用警告；当前222源码975814字节有限审计通过，未新打系统源码ZIP/重跑前端构建。final-state-audit核对638文件521278832字节/全表/旧任务/主CUDA不变、活动分析/特征0，读取既有55特征/概率差0及252规范不是本轮新提取。两服务复用19544/28164，实际5179/8012；runtime-supported.json和数据位置仍01:06/00:06轮。证据根E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T030942_d136a5d2；最终engineering-figures-final、engineering-browser-final-rendered、engineering-materials-validation、source-audit-current、final-state-audit、main-environment-unchanged。本轮早期图文线碰撞/截图加载态/测试路径错误均保留，最终修正证据单独命名。下一步E6安装/迁移交付清单与源码/材料联合复核，区分历史源包与增量、部署环境缺口；E5仅用户提供系统窗口后续接，不反复安装失败、不升级研究结论。

## 前轮历史（下方不替代本轮证据）

## 2026-10-10持续开发第六轮（北京时间02:07起，10/09晚间窗口）

run_id：20261010T020814_85dc6dc0；系统UTC开工18:07:57，北京02:07:57；实际起止/耗时见本轮summary.json。E6源码候选与操作/环境清单两个小批次通过，整项继续进行中；E5仍受系统授权前提阻塞，R1–R4无新增研究验收。

新增prepare_source_delivery.py/3项行为测试、两端.dockerignore、capture_environment_inventory.py、本机requirements-local-validated摘要、SOURCE_DELIVERY/ENVIRONMENT_INVENTORY和只读指南浏览器工具；修订README/用户/本机/研究/前端操作指南、范围/清单/概要。白名单含已修改与未跟踪真实源码，排除数据库/MRI/模型/环境/node_modules/内部反馈日报；有限六类凭据规则只脱敏输出，不冒称全面安全/PHI或许可认证。历史UTF16 requirements原字节保留，53已安装包元信息/core11+research5一致、主pip check通过；历史表29精确一致，原安装URL/SHA不全明确未知，不安装/升级主环境。

最终218源码/942155字节、ZIP360506字节SHA27b22382555d4882f3c57748dac71aa3aa2bca8cb8ae2271124e60973e164e36，逐文件打包/解包/测试后当前源SHA一致。原树78后端/2基础浏览器/构建，最终解包78后端/构建通过；解包依赖使用已有主解释器及指向现有node_modules的自有目录联接，不是新机器或容器安装。4弃用/大块提示保留。当前实际创建表单/保存研究结果浏览器无写入，最终截图实际查看；初次整页截图没捕获弹窗只作历史，已用弹窗截图补验。

final-state-audit读取已有门槛和保存状态，不重新提特征：638原件/快照521278832字节、全表/旧任务/版本/概率未变，主CUDA可用，活动分析/特征0。start_local安全复用PID19544/28164不变，runtime-supported.json仍01:06轮，前端5179/API8012；未启动第二服务/下载/训练/推理/PDF/容器。证据根E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T020814_85dc6dc0，final-candidate-verification.json/source-candidate-final、environment-inventory、delivery-guides-browser-final、最终解包日志/保存与进程审计。内部源码包不公开发布且非开箱系统部署包。下一轮优先E6系统架构/版本谱系/既有真实界面的毕业论文工程材料，按实证边界组织，不将原型研究结论升级；E5等管理员/合适重启窗口，不反复失败安装。交接详见NIGHTLY_HANDOFF。

## 2026-10-10持续开发第五轮（北京时间01:06起，10/09晚间窗口）

run_id：20261010T010640_a6ee8135；UTC系统开工17:06:20，北京01:06:20，实际结束/耗时以summary.json为准。E4本机Windows CPU环境已验收，继续完成E6固定演示/范围小批次；系统整体仍未完成（E5受阻、E6进行中），R1–R4无新增验收。

隔离Conda-forge Python3.11.17，原PyRadiomics3.1.0源码及精确提交遗漏头文件经Git blob/SHA核对，用官方Zig0.15.2便携C编译器构建cp311 Windows轮子；未提权/装系统SDK/重启。原源码不改、无fast-math/参数更换，主3.10.21/torch2.11+cu128和旧3.9保留。20Conda/10PyPI完整来源锁、pip check通过；新增source/header fetch、build、lock及migration/browser/audit工具与supported依赖摘要，复建步骤见RADIOMICS_ENVIRONMENT_MIGRATION。候选全部在E盘，Conda C盘用户登记文件SHA前后不变。

最终candidate-reference-gate-complete：五原参考MRI/mask、55有限特征及旧概率差0、252归一化/空区域规则。automatic-supported-complete：病例17同输入/原临床57岁male/分割和研究版本，新任务c913b7963dbe4d9e8014ea6487069946，20特征和五概率差0；1.763秒为内部提取非端到端保证，重复请求同缓存。实际重启后原/副本数据库全部行和18病例报告/意见/复核/标注/临床一致，四序列三视图/研究/报告/未知临床浏览器通过。638原件及快照SHA一致、旧任务/旧环境/协议不动、CUDA可用。75后端/4弃用警告、2基础浏览器/构建大块提示保留。补依赖前门槛/任务/截图仅历史，不能混同最终complete目录；初次pip check缺ruamel.yaml.clib已补并全部重验，不给无pip的旧环境安装工具。

当前配置本轮runtime-supported.json，DB/feature_jobs是原件备份的新副本，模型/上传/研究/数据继续引用上轮relocated-runtime（不可删除）。前端5179/API8012，backend19544/UTC17:47:12.5047176、frontend28164/17:47:12.5111247，精确身份见Runtime/local/processes.json。无训练/GPU推理/下载/提取长任务；保持一个后端/前端与后端串行分割/特征执行器。原库/源患者临床不改，未新增患者/研究数据、未重新导出PDF，不提交推送。

E6新增固定五步演示、失败操作/版本/范围说明及最终截图，对照实际页面；第一阶段仍须E5系统授权后Linux CPU容器/持久化实测和E6最终材料。WSL/Docker前提沿用上轮已确认事实，不重复安装尝试；下一轮先锁/反馈/复用当前配置，执行E6剩余交付文档/打包前只读敏感与大文件审计，可独立于Docker；不公开分发数据或等待SCI选题。

证据根E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T010640_a6ee8135：上述complete目录、dependency-locks-complete、conda-lock-parser-complete.log、candidate-pip-check-complete.log、native-build-record-fixed、build-sources-reuse、database-backup、backend-final.log、basic-browser.log、frontend-build.log。失败的编译选项/缺头文件/轮子RECORD、验证body/页面ID/缓存访问时间假设、锁格式与间接依赖检查保留。反馈台账无用户新反馈，未编造反馈条目。

## 00:06窗口历史（以下不是最新环境/服务状态）

## 2026-10-10 持续开发第四轮（北京时间00:06起，归属10/09晚间跨午夜窗口）

run_id：20261010T000643_ec1cf8da；系统UTC开工2026-10-09T16:06:24，锁实际持有进程8236。E3新增验收：上传/静态/读片/预处理/分析输出路径统一可配置，runtime.json相对路径安全解析，启动前严格只读依赖/模型/研究/工作器/SQLite/已存谱系检查，已有服务按全部路径及PID/启动时间/端口/健康安全复用。缺模型实际启动被拒、未产生监听服务；错MODEL_DIR复用不动作。

原服务先捕获18病例基线，再身份核对停机；快照638文件521,278,832字节以及SQLite，校验SHA256/行数。新独立relocated-runtime恢复57条操作路径及特征路径缓存键，两次实际启动/重启后18病例的分析/临床版本/概率/意见/复核/报告/标注相同；三视图MRI/mask图片SHA256相同，真实四序列与恢复静态地址读片通过，实际POST命中原特征任务。最终原638文件/快照/原数据库逐行不变。恢复是应用数据/模型/结果，不包含源码/可执行Python环境或未引用的全MRI研究队列，不冒称整机或Docker可移植性。

最终75后端、2基础浏览器、构建通过。首次审计用ORDER BY id遇到case_research_inputs主键case_id错误，保留失败后改按首主键列核对，通过；复现工具CLI局部默认变量错误在帮助命令中发现并修复，没有启动提取。未新增推理/提特征/训练/病例/研究数据；只有公开包元信息只读查找。主Python/CUDA、旧工作器、特征提取脚本/协议/模型均保持。

继续推进E4小批次：查官方PyPI/Radiomics频道可用版本，保存原元信息/URL/大小/SHA；新增支持源核查工具与候选复现的--output/--worker/--data-dir/--research-dir/--baseline，必须全新证据目录，直接比较旧特征及原概率，两个保护测试通过。尚未建立新支持环境；没有借旧门槛宣称新环境通过。主Python3.10与工作器3.9生命周期风险、官方Windows轮子缺3.11+及待核对构建工具记录在RADIOMICS_ENVIRONMENT_MIGRATION.md。

证据：E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T000643_ec1cf8da；system-snapshot/manifest.json、relocated-runtime/restore-validation.json、after-restore与after-second-restart/validation.json和四序列/研究/报告截图、post-restart-immutable-audit.json、missing-model-*.log、runtime-config-reuse-rejection.json、backend-final-with-candidate-gate.log、basic-browser-final.log、final-frontend-build.log、e4-official-support。失败记录不覆盖，旧日期日报保留。

服务仍前端http://127.0.0.1:5179、APIhttp://127.0.0.1:8012/docs；配置为本轮relocated-runtime/runtime.json。backend PID23824/UTC启动16:25:19.5788640，frontend PID1720/16:25:19.5844182，身份见Runtime/local/processes.json。无活动下载/训练/推理/提特征/构建。新增SYSTEM_BACKUP_RESTORE与E4迁移说明，同步README/本机/操作指南实际能力；E6仍未整体验收。E5已实际只读检查：Windows11/HypervisorPresent=true，wsl原生exit50明确未安装、Docker PATH/标准目录未发现，进程非管理员；状态受阻，待用户管理员WSL启用/合适重启窗口，未改系统/下载安装/重启，官方解除步骤见DOCKER_PREREQUISITES。第一阶段剩余E4/E5/E6；R1–R4未新增研究证据。下轮先现有构建工具/SDK与支持Python候选建立，再同协议五例直接复现；需要提权时通知并转独立任务。

本轮补验（00:48）：查看恢复序列截图发现加载态，定位验证工具empty.every提前通过，不是已确认的UI功能故障；修正为3切片+3mask+序列身份、等待菜单隐藏。after-restart-rendered-final/validation.json和四截图重新通过，FLAIR实际三视图已查看；旧截图保留且不作最终视觉证据。本轮实际耗时/完成时点以summary.json为准。

## 2026-10-09 持续开发第三轮（北京时间23:03起）

run_id：20261009T230333_01ec9298；系统UTC开工15:03:21.452，本轮新增验收E2、F6，第一阶段仍未完整交付。当前分析/病例详情/医生确认/报告/模型叠加/自动特征统一核对四序列与mask的保存来源和SHA256。文件变化、缺失、路径关系错误、缺谱系、坏结果JSON时当前结果不可用；历史状态和原结果不重写。指纹缓存仍是path/mtime_ns/size的非对抗性工程校验，不宣称安全防篡改。

先备份上一轮服务数据库并验证副本，再复制病例17真实成功的公开样本输入/掩膜/已存特征到本轮独立副本病例18。病例18是同患者的历史工程复制，不是新推理或独立研究患者；所有改内容/临时移开文件测试仅作用于本轮复制文件，最后按原SHA256恢复，原输入/模型/成功产物未修改。未新增下载、特征提取、训练或GPU推理。

最终63项后端全套、2基础浏览器、构建通过；真实副本MRI改字节、mask改字节、缺mask的API与病例/分析/研究/阅片/旧页面PDF浏览器保护通过。PDF异步渲染完成后新增下载前复核，渲染期间实际文件改变也零旧PDF下载。原病例17结果/概率和六原报告不变。最新病例17两页A4 PDF使用Poppler渲染并逐页实际查看，版本、6.283/3.376/0.008mL、北京时间、独立医生意见和研究限制正确；修复标题装饰线分页残片，不把研究概率放入诊断报告。

继续完成E3小批次：start_local.ps1新增-ReuseExisting，核对登记PID/精确启动时间、应用命令、监听端口归属和两服务健康；实际复用不变PID，错误端口、错误数据库和重复启动均拒绝。E3保持进行中，完整产物备份/离线路径恢复/可重定位配置与依赖前检未完成；E4/E5/E6及R1–R4未新增验收。

证据根：E:/BrainFusion-Runtime/results/nightly/2026-10-09/20261009T230333_01ec9298。e2-browser-final/validation.json与截图/最新PDF/两页PNG，pdf-visual-review.json，e2-backend-final.log，basic-browser.log，final-build-after-pdf-guard.log，e3-service-reuse/validation.json。失败环境/选择器/响应事件假设、诊断及早期PDF保留，不覆盖。

实际服务仍为前端http://127.0.0.1:5179、APIhttp://127.0.0.1:8012/docs，已切换本轮database-backup/restored-validation.db及feature_jobs；backend PID30696/UTC启动15:20:09.9364736，frontend PID24344/15:20:09.9421510，身份以Runtime/local/processes.json为准。下一轮先E3完整产物快照和副本路径恢复，在独立目录验证；不要重复已通过推理或改原数据库。下方旧轮状态为历史，最新以台账为准。

## 2026-10-09 持续开发第二轮（北京时间22:05起）

run_id：20261009T220645_757412b3。本轮新增验收F1/F3/F4/F5，第一阶段仍未完整交付。F1依据上一轮真实病例17闭环和本轮受影响流程回归，未重复推理。四序列T1c/T1n/T2w/FLAIR已支持切换，各视口身份明确；保持三视图位置/方向/交叉线/缩放/原掩膜/标注，记忆各序列窗宽窗位；几何不一致拒绝，不自动配准或重采样。旧单文件不冒称FLAIR。

F5修复迟到请求覆盖新状态、刷新失败留旧成功、错误恢复不清除及409不续接；新增具体工作器异常摘要和分割输入前置检查。活动任务的浏览器排队/运行/409/失败使用明确受控响应，不冒称新的真实推理；真实API并发去重与失败重试在独立pytest库验证。

F4用真实指针事件复现img原生拖拽→pointercancel把目标102.8mm线提前保存成12.8mm，已修复。10种工具在病例17当前1mm网格逐项实际创建/保存/刷新/渲染/删除，距离/双向mm、ROI mm²数值、角度°通过；矩形与自由ROI补面积。部分保存失败保留未保存草稿，重试不重复成功项；取消不提交。全部工程测试标注已按自身ID删除，原有记录未删除。

E2仅新增部分验收证据：自动特征GET核对保存的MRI/mask SHA256，文件变化/缺失/谱系缺失隐藏旧概率，历史state原件不改。指纹缓存以绝对路径/mtime_ns/size为键，非对抗性文件篡改防护。分割结果/复核/报告/PDF/叠加全路径漂移拦截仍待实施，E2保持待验证，不夸称完整一致性。

最终57项后端全套、2基础浏览器（复用现有前端）、构建通过；四序列/10工具/任务专用浏览器及实际重启输入/原概率/六报告一致通过。构建仍有大块提示，后端有弃用提示。失败夹具/选择器错误及原生拖拽复现均保留，修正后证据独立保存。没有新增下载、训练、GPU推理或环境切换，没有提交/推送。

证据根：E:/BrainFusion-Runtime/results/nightly/2026-10-09/20261009T220645_757412b3。服务仍为http://127.0.0.1:5179、API8012，使用上一轮restored-validation.db与feature_jobs；最终backend PID19280、frontend PID31448，UTC启动14:33:46，精确身份见Runtime/local/processes.json。尚无活动推理/特征/下载/训练。下一轮先E2统一分析/复核/报告/掩膜读取的文件漂移保护，在独立副本验证，不修改病例17真实成功文件。E3/E4/E5/E6/F6与R1–R4门槛保留。

## 2026-10-09 持续开发首轮（北京时间21:05起）

系统完成台账已建立，最新范围与状态见 SYSTEM_COMPLETION_CHECKLIST.md；交接见 NIGHTLY_HANDOFF.md，用户反馈见 REVIEW_FEEDBACK.md。当前第一阶段尚未全部交付，下面2026-10-07记录保留为历史证据。

run_id 20261009T210647_efc88446。本轮验收 E1（正式流程旧占位输出拦截）和 F2（关联患者→病例独立研究输入版本→失效/重算/恢复）。旧预测仅在明确历史归档接口可查；真实分割卡现在可通过页面医生确认，并有病例研究入口。当前报告拒绝失败/跨病例/过期来源，导出前复查版本，PDF时间按北京时间显示。F5新增模型过期及请求失败后的旧概率清除；全任务交互验收仍待完成。

实际浏览器新建公开样本4的病例17，上传四文件、真实MONAI推理、三视图叠加、20个自动掩膜特征、IDH原始值=1概率与融合、医生确认/意见、报告和PDF基线通路通过。两页PDF已渲染并逐页实际查看。推理记录1.45秒、PyTorch峰值505.23MB，CPU特征1.85秒；不是整卡用量或临床性能。病例研究覆盖年龄从56改57验证新版本，患者资料仍为56岁男性。

本轮后端全套41项通过，之后F5/E2变更分别11/13项相关回归通过；最终前端构建通过，2项基础浏览器通过，新增真实病例/临床版本/重启浏览器验证通过。实际服务重启后病例输入、特征概率、医生确认和六份成功报告一致。原演示库先只读SQLite备份，副本完整性/行数一致；新增表只在隔离测试和演示副本上实测，原workflow.db未迁移。

证据：E:/BrainFusion-Runtime/results/nightly/2026-10-09/20261009T210647_efc88446/。首个浏览器选择器失败、第二次任务ID选择器失败、备份工具Python3.10哈希兼容问题均保留说明；没有抹掉失败或重跑重复分割。

本轮保留前端 http://127.0.0.1:5179，API http://127.0.0.1:8012/docs。使用本轮restored-validation.db和隔离feature_jobs，含明确合成旧记录病例16及公开样本病例17，不是原workflow.db。服务PID/启动时间以Runtime/local/processes.json及交接为准。

下一轮先续F5活动任务/刷新/重复请求/失败重试的集中浏览器回归，然后F3四序列切换。E2文件变更读取失效、E4环境、E3完整备份/复用/迁移、E5容器、F4完整工具和E6交付尚待验。研究R1–R4未新增数据/训练/指标；编码与预训练重叠等事实问题保持未解决。

更新：2026-10-07。实施目录 E:/BrainFusion-AI；C 盘工作树未用于本轮编辑。数据、权重、缓存、测试库、实验产物均在 E 盘。Git 基线 d1bc7a0，本次改动尚未提交或推送。

## 五天冲刺状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| 1 数据与真实模型 | 通过 | 五例独立推理、几何、WT/TC/ET Dice/HD95；见 STAGE_1_VALIDATION.md |
| 2 上传与任务 | 再次通过 | 五例上传→真实推理→版本报告/确认，重复任务与重新分析保护 |
| 3 阅片与报告 | 再次通过 | 五例浏览器叠加、实际四文件推理、测距保存刷新、PDF |
| 4 IDH/TOPSIS/联邦 | CPU 原型通过 | 两分支、三种融合、IID/Non-IID 三轮同构模拟，五例接口/页面/重载；见 STAGE_4_VALIDATION.md |
| 5 回归与交付 | 本机通过，容器未验收 | 最新 26 后端测试、2 基础浏览器测试、构建、分割与研究模型重启读取、指南 |
| 后续 6 自动特征 | 本机工程迁移通过 | 参考特征复现、当前病例自动掩膜→特征→现有研究预测；五例 API/页面/缓存/重启 |

## 实验与资源

完整临床/公开参考掩膜特征表形成 141 名已知标签且无提取错误的研究患者，固定拆分 98/21/22；五个工程患者全部排除。预处理只在训练集拟合。分类/联邦 CPU 运行，无 GPU/全量训练。

当前实验版本 20261006T012431Z_0de5dbb8。探索性 AUC：临床 0.8843、影像组学 0.8182、平均 0.8926、固定 0.9008、TOPSIS 0.8182；TOPSIS 权重 0/1，没有证明优于平均。拆分已在原型阶段查看过，全部标探索性，不能称最终独立评估。

RTX 5070 Ti Laptop 12227 MiB，torch 2.11.0+cu128、MONAI 1.5.2。五例本轮分割 PyTorch 峰值分配 505.23 MB，无 OOM；不是全卡占用。batch=1、6000 MB 分配预算、CPU 拼接与 OOM 单次 CPU 回退。患者 4、16、17 参考 TC/ET 为空时模型有假阳性，保留 Dice=0 和空区域规则。

## 验证证据

E:/BrainFusion-Runtime/results 下：stage2/workflow_validation.json、stage3/browser_validation.json、stage4/api_validation.json/browser_validation.json、stage5/persistence_validation.json/cache_benchmark.json/verification_summary.json。研究模型、摘要、患者预测及冻结划分位于 results/research。数据原始校验在 E:/BrainFusion-Data/WAW-GliomAI-v3/sample_validation.json。

阶段说明见 STAGE_1/2/3/4/5 文档；本轮优化见 OPTIMIZATION_REPORT.md。五例阅片、上传推理、版本、测量和 PDF 均重新验收；重启后五例研究概率与保存记录一致。

## 使用与下一阶段

本轮保留演示前端 http://127.0.0.1:5179，研究页 /research，API http://127.0.0.1:8012/docs；进程存活时可直接使用。启动/停止见 LOCAL_RUN.md；完整指南 USER_OPERATION_GUIDE.md、RESEARCH_OPERATION_GUIDE.md；功能概要 FEATURE_OVERVIEW.md。

2026-10-07 已复现五例的 252 个一阶统计量和 55 个非空选中特征，原模型重提特征后的概率一致。新增隔离 CPU 特征工作器、后台任务与研究页入口；五例自动掩膜输入和重启通过，现有报告/确认未修改。见 STAGE_6_VALIDATION.md、AUTOMATIC_FEATURE_OPERATION_GUIDE.md；结果在 E:/BrainFusion-Runtime/results/stage6。

后续步骤、验收和预计工时见 POST_SPRINT_PLAN.md 与 RESEARCH_PROTOCOL_NEXT.md。数据登记已执行，正式研究还需确认目标编码、预训练重叠与未查看评估队列；自动掩膜同协议训练队列重提取/重拟合尚未完成。容器未安装/未运行；自动配准、斜切重采样、成组 DICOM、熵权/动态 TOPSIS、Local/FedProx、多种子和外部验证仍未完成。现有自动输入属于参考模型工程迁移，不能称已验证的端到端临床能力。

自动执行时先检查实际新失败和未完成门槛；无新变更不要重复训练或下载。保持单个后端、E 盘写入和资源预算。完整年度发布仍以 RELEASE_CHECKLIST.md 为准，不创建自动发布。





2026-10-17 S3增量：联合PACS恢复现生成统一13路径v2运行配置；联合恢复v2合成restore、缺配置拒绝及启动前本地账户/PACS有效性门槛23项通过，证据见20261017T1445_s3finalrepair。当前登记运行配置严格启动预检本批待验。真实私有bundle恢复及恢复目录服务启动待验证。详见docs/NIGHTLY_HANDOFF.md和docs/SYSTEM_BACKUP_RESTORE.md。






## 2026-10-18 公开DICOM候选复核更正

此前“优先候选为UPENN-GBM、需再查元数据”的结论已被IDC公开索引查询更新：UPENN-GBM原始MR在本轮未发现同一Study含所需四角色的病例（3,680 Series/3,301 Study，最多每检查2条MR Series）。ReMIND检出同检查四序列病例，但候选中存在轴位/矢状位混合。ACRIN-NSCLC-FDG-PET两个小脑MRI病例（099、134）已逐DICOM核验，Frame of Reference及层位基本对齐，但均因矩阵/间距差异不符合当前完全同网格约束；ACRIN是肺癌研究数据，仅可作为工程流程候选，不能支持胶质瘤效能结论。样本仍在隔离候选目录，未导入活跃Orthanc或启动模型任务。详见`docs/PUBLIC_FOUR_SERIES_DATA_SCREEN_20261018.md`及其中证据路径。

2026-10-18决策：在网页显式勾选后接受同Study/Frame下可审计的1 mm线性重采样，范围仅限纯影像工程验收；严格原网格仍为默认，不允许重采样版激活模型输入或推理。ACRIN-134的四序列几何规划成功，但真实转换因源DICOM缺少`BurnedInAnnotation=NO`而由既有像素审核门槛拒绝，没有生成NIfTI。实现/测试/阻塞证据见`docs/P3_DICOM_RESAMPLING_ENGINEERING_VALIDATION_20261018.md`。因此P3真实转换和病例页面验收仍未完成。





## 2026-10-18 E5 容器准备状态

静态容器配置已更新：前端使用 npm 锁文件安装；Compose 显式要求外部持久目录、只读配置/模型/研究/数据/工作器挂载，并配置服务健康检查。实际 Compose 解析和镜像构建未完成，因为当前没有 Docker CLI/WSL。静态审阅还发现 PACS、账户、DICOM 转换/审核及研究组件存在 Windows E: 路径约束，Linux 容器支持前必须完成跨平台路径改造和测试。此前源码候选因工作树变化已成为历史快照，待重新构建。

候选四序列影像仍因像素烧录文字未能人工确认而隔离，未导入、转换或推理。既有本机服务保持运行；等待数据人工检查及管理员安装/重启窗口，不用合成数据声称真实效能。

## 2026-10-20 E5 Docker/Linux 运行时增量

Docker Desktop 4.95.0 / Engine 29.8.2 已正常运行；hello-world 容器通过。后端 full (linux/amd64) 与前端 Nginx 镜像均实际构建成功。后端隔离容器导入/启动/health 与 OpenAPI 68 路径通过；前端隔离容器 HTTP 200。临时容器均停止，未挂载真实数据或更改现用服务。镜像摘要、npm audit 处理、完整限制见 docs/E5_DOCKER_RUNTIME_VALIDATION_20261020.md。

前端锁文件在现有 semver 范围内更新 21 项，package.json 不变，构建通过；npm audit 从 21 项降至 11 项，剩余高/中风险集中在 Cornerstone/DICOM 依赖树，需兼容性评估，不强行跨主版本。初次 E5 配置要求外部 Linux worker 挂载；本轮后续已将哈希锁定的 Linux worker 加入后端镜像并移除外部 worker 挂载变量，Compose 配置解析现已通过，服务仍未启动。真实 PACS/持久化、四序列人工图像确认及真实页面流程仍未验收。

用户新增收尾要求：项目验收完成后盘点并清理 C/E 盘冗余文件、把交付整理到单一项目目录；当前不移动/删除数据、模型、配置或备份。











## 2026-10-20 E5 Linux radiomics worker candidate

Linux CPython 3.9 / PyRadiomics 3.1.0 worker 已嵌入 Compose `full` 后端镜像，五参考病例的 100 个选定特征、5 个模型概率及 252 个归一化检查均通过；API Python 3.10 和 worker Python 3.9 双环境均通过导入/运行检查。Compose 前后端已用临时数据库目录启动，后端健康、前端 HTTP 200、OpenAPI 68 路径、挂载 Linux gate 与病例 13 worker 提取均通过，之后已停止并移除容器/网络。轻量 `core` 目标也已单独构建（约 945 MB，不含 radiomics worker）。持久化重建、PACS/Orthanc、真实病例页面流程仍未验收。新建 Linux worker gate 在 E:/BrainFusion-Runtime/local/radiomics-compatibility.json，不得复用于 Windows worker。证据见 docs/E5_DOCKER_RUNTIME_VALIDATION_20261020.md 与 E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T132214_linux-radiomics-e5/。

## 2026-10-20 当前更正：Docker 与目标 Orthanc 已可连通

用户安装 Docker Desktop 后，Linux Engine 已启动。用户确认当前 Orthanc 是目标归档并授权备份后重绑。PACS 配置、Orthanc 配置、SQLite 索引和影像存储已备份至 `E:/BrainFusion-Runtime/backups/pacs-identity-rebind-20261020/`（197 个文件，约 19.6 MB，带 SHA-256 清单）；PACS 数据库身份 pin 已更新并与运行中的 Orthanc 一致。主机端认证状态/QIDO 以及 Docker 容器端身份 pin/QIDO 查询均成功，容器 QIDO 仅取回 1 条 study 元数据；本轮没有读取像素或导入病例。详见 `docs/E5_DOCKER_RUNTIME_VALIDATION_20261020.md` 与 `E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T132214_linux-radiomics-e5/orthanc-rebind-verification.json`。

注意：实际 PACS 配置中的 `allow_pixel_read` 为 true，与旧记录不符。本轮保留了原值，验收未访问像素端点；是否关闭该配置需另行决定。新后端镜像构建在大体积锁定依赖下载过程中中断，容器连通测试使用旧镜像加只读源码覆盖，因此新补丁尚未封装进正式镜像，完整 Compose 重建验收仍待完成。上述信息覆盖本文件较早的 Docker/Orthanc “未验收”旧状态；真实病例像素烧录确认、数据许可/去标识审查、网页阅片验收仍未完成。

## 2026-10-20 更新：正式 Compose + 目标 Orthanc 联合验收通过

在重绑与备份后，已完成新 `full` 后端镜像构建，并用临时 runtime 完整启动 Compose。后端和前端均 healthy，OpenAPI 68 路径与前端页面均 HTTP 200；PACS status HTTP 200，后端容器身份 pin 校验通过并通过 QIDO 读取 1 条 study 元数据。五个只读挂载均实测拒写，数据集挂载为空。没有挂载既有业务数据库，没有取像素、导入病例或执行推理；验收后容器和网络已清理，临时 runtime 与镜像保留。报告与机器证据分别见 `docs/E5_DOCKER_RUNTIME_VALIDATION_20261020.md` 与 `E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T132214_linux-radiomics-e5/compose-e5-rebind-20261020.json`。此前记录的“新镜像未包含补丁、Compose 尚未补验”是重绑后首次尝试时的状态，现已被本次通过结果取代。

仍待人工完成：真实同检查四序列像素烧录文字确认、数据许可与身份/角色判断、真实病例页面阅片流程。另，PACS 的 `allow_pixel_read=true` 仍保留原值，本次未访问像素端点。

## 2026-10-20 M2 生命周期回归增量

后端定向回归覆盖转换来源完整性、角色复核、显式激活、转换登记/重试、分析输入失效与历史、当前输出以及 PACS runtime 层，**81 passed，4 条既有弃用警告**。前端 Microsoft Edge 合成页面场景覆盖“角色批准与模型输入激活分两步”及“旧分析归档但不展示旧结果”，**2 passed**。首次 pytest 临时目录落在 C 盘，受路径保护而无法建用例；将 `--basetemp` 明确指向 E 盘隔离目录后整批通过。证据及日志见 `E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T132214_linux-radiomics-e5/m2-regression-20261020.json`。这些结果证明工程隔离契约，不代表真实四序列来源的审核/激活/AI闭环；M2真实数据验收随M3输入门槛待办。

最终 full 镜像又完成一次隔离数据库、上传和特征任务目录持久化复建检查：创建三种仅用于测试的标记，Compose down/up 后均仍存在，前后端恢复 healthy，随后容器/网络已关闭。数据与报告见 E5 验收文档及同目录 `compose-persistence-final-image.log`。E5持久化重建门槛现在通过。

用户需要回答的像素隐私审核、像素读取授权、研究边界、带教和交付清理问题已整理在[用户待确认事项与正式验收问答](USER_ACCEPTANCE_QA_20261020.md)。
















