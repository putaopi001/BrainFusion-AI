## 2026-10-20 最新现场状态（优先于下方旧快照）

隔离 Docker 前后端再次实测 healthy（前端 http://127.0.0.1:18180、后端 http://127.0.0.1:18100）；Orthanc 已由外部 PowerShell 前台运行，PID/启动时间/可执行文件/配置/8042监听身份匹配，认证 `/system` 版本1.13.0 与 DICOMweb QIDO 通过。后端只读归档列表查询200、1个检查；PACS `ready/read_available=true`。因人工烧录隐私复核尚未完成，已备份后将 `allow_pixel_read` 关闭；最新状态 `pixel_read_enabled=false`、`dicom_view_available=false`，导入和AI桥关闭。没有读取像素、导入或修改归档数据。前台终端必须保持打开；安全停止与复现命令见 [Orthanc前台恢复验收](ORTHANC_FOREGROUND_RECOVERY_VALIDATION_20261020.md)。

目前可重复演示范围为病例17的隔离 NIfTI 只读阅片，以及病例19的真实 PACS 检查、序列、实例和空间元数据查询。恢复副本Orthanc已在隔离8043通过身份/检查UID/实例UID核对并关闭；应用未切换到恢复副本验收，因此整体联合恢复仍未通过。PACS像素阅片、受控导入、真实四序列AI、合格人员数据/隐私审核及用户独立交付演练仍未通过。PACS像素开关为false。Compose状态检查须使用 `docs/LOCAL_RUN.md` 指定的 `--env-file`，裸跑 `docker compose ps` 会因必填路径变量未注入而报错，不代表容器停止。

本轮最新源码-only内部候选位于 `E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T211000_handover_public_data_candidate/`：466个白名单文件、受限扫描0发现、ZIP大小1,537,796字节；包状态为passed，SHA-256 `453f49c8492e1c575f44721a66bdf29ab1b0a98553082bae0f196a740d91208e`，逐文件解包核验见该目录 `validation.json`。本候选已纳入最新维护手册、交付范围、操作指南和用户决策Q&A；本轮仅做交付材料一致性及源码包构建/哈希核验，没有重复跑测试或全量回归。候选不含运行环境、数据或模型，也不等于最终异机部署或真实四序列AI验收。

操作指南已补充只读Compose的启停、病例页面操作及隔离可写副本中的NIfTI上传/分割流程；当前演示禁止写入。公开DICOM候选为TCIA UPENN-GBM，尚未下载或读取像素，需先通过许可与获准人员人工复核。最新源码-only候选见 E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T211000_handover_public_data_candidate/，466文件、0扫描发现，SHA-256 453f49c8492e1c575f44721a66bdf29ab1b0a98553082bae0f196a740d91208e。本轮未运行回归或触碰Orthanc。

上一份19:29收尾快照及其下方重复段落均为历史信息；当前现场以本文件顶部为准。病例详情页的真实PACS元数据流程已验收：检查、序列、实例及空间清单均可查询，阅片按钮因像素门控而禁用；0写入、0像素请求、0页面异常。恢复副本Orthanc的只读元数据恢复核对已通过，但应用级切换未验收；用户明确要求先完成项目主体，恢复切换后置，当前不得停用或切换原8042服务。后续是外部人工隐私/序列角色/许可审核、最终交付封版和负责人独立演练；大模型继续暂缓。
## 2026-10-20 19:29 历史快照（已被本文件顶部最新状态覆盖）

以下仅表示19:29当时情况。原Orthanc随后已由用户在Codex外PowerShell以前台方式启动；此前要求的Task Manager/Job诊断和重复启动命令均已过期。当前像素读取开关是false，实际状态以本文件顶部及Orthanc前台恢复验收为准。

Docker隔离演示前端 http://127.0.0.1:18180 返回200，后端 http://127.0.0.1:18100/ healthy；当前展示范围为病例17 NIfTI只读浏览。正式本机Orthanc目前未运行，PACS状态unavailable，8042未监听；这是恢复演练结束时Codex桌面进程Job清理后台进程所致，活动归档数据未损坏，Docker容器仍运行。

重绑后的私有联合快照与隔离恢复已完成：E:/BrainFusion-Runtime/backups/closeout-joint-20261020T110853Z/。196个归档/配置文件、702个应用文件；SHA-256、SQLite完整性、17张表科学/版本字段和13条统一运行路径通过；应用/归档文件哈希和应用数据库字段核对通过；恢复副本的Orthanc未能启动，因此Docker应用没有对恢复副本执行QIDO，joint-restore.json标明live_restoration_verified=false；全程未读取影像像素。请从Codex外的普通PowerShell运行：
    & 'E:\BrainFusion-AI\backend\tools\start_orthanc_local.ps1' -Root 'E:\BrainFusion-Runtime\orthanc-local'
本机启动器已补上适用时的CREATE_BREAKAWAY_FROM_JOB请求，仍验证目标脱离所有Job后才接受。专用回归2项通过；Codex托管会话仍被外层Job捕获并安全拒绝。更新脚本在Anaconda PowerShell中仍失败（0x1800，目标仍处于Job且已终止），所以当前PACS未恢复。当前Anaconda PowerShell已实测in_job=True；从该窗口调用脚本会被保护性拒绝。请用Ctrl+Shift+Esc独立打开Task Manager，选择“Run new task”并启动powershell.exe；先运行Job诊断。只有in_job=False时才运行上述启动命令，再检查 http://127.0.0.1:18100/pacs/status。若仍为True，请停止，不要从该窗口启动。

当前源码候选：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T1935_recovery_scope_refresh/candidate/；463个白名单文件、扫描0发现，ZIP SHA-256 1368f78e6dd32051a3610bcefac26dda031c990df6fa3ee6eea6ffd3bb368546。只读交付核验463/463匹配、SQLite签名未变、passed_existing_workstation_only。后端695项全回归通过；与上一候选的差异仅为两份恢复文档，代码哈希未变，复用同一695项回归证据。Docker/Linux Compose验收另有E5记录，不能由本机预检替代。

剩余优先项：①在Codex外启动Orthanc并复查PACS；②安排有权限人员核对同检查四序列图像烧录文字、数据许可和序列角色，当前无人可复核，因此真实DICOM→AI不能验收；③项目负责人按手册完成独立操作、故障排查、备份恢复及两次导师预演；④冻结后刷新最终交付材料，并仅清理有精确重复、无引用且非唯一备份/证据的文件。大模型按用户决定暂缓，SCI不是系统工程收尾门槛。

## 2026-10-20 手册草案增量

独立维护手册已补正文并进入463文件源码候选；候选解包后端694项全量回归通过。它仍是草案，待系统功能/配置冻结后校订并由项目负责人完成独立操作与恢复演练。详见 INDEPENDENT_MAINTENANCE_GUIDE.md 和 E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T2300_maintenance_guide_candidate/。大模型按最新决定暂缓。
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

# 当前系统收尾状态（2026-10-20，优先于下方旧环境快照）

## 2026-10-20 16:20 当前隔离 Compose 演示状态（覆盖此前“容器已停止”的状态快照）

当前用户可查看 http://127.0.0.1:18180。Docker Compose 后端与前端在本轮复核时均为 healthy，分别绑定本机 127.0.0.1:18100 和 127.0.0.1:18180。演示使用病例17现存 NIfTI 数据库的隔离副本及对应文件；源数据库前后 SHA-256 相同。范围仅为已存在 NIfTI 病例的容器页面/文件读取演示，不是四序列 DICOM、DICOM→AI 或模型效能验收。说明与停止命令见 COMPOSE_NIFTI_DEMO_GUIDE_20261020.md。不要另启第二套同端口 Compose，也不要把当前演示副本并入正式数据。

- **E5 Docker/Linux：** Docker Desktop 与 Linux engine 可用；新 full 后端镜像 `sha256:aa3711890c529ecafc64a5815d94a623a24df6e9c5fc70efd504520c54e63973` 已构建，目标 Orthanc 身份重绑已在备份后完成。隔离 Compose 中前后端均 healthy，前端 HTTP 200、OpenAPI 68 路径、PACS 状态与容器 QIDO 通过，五个只读挂载均拒写；最终镜像重建后数据库/上传/作业标记仍在。真实环境/数据依赖的人审门槛仍未通过。
- **回归：** 后端全套 694 passed、4 条既有弃用警告（最新 final5，195.99秒）；M2定向后端81 passed，Edge合成页面2 passed。后台进程在不可脱离的 kill-on-close job 下会安全拒绝启动；普通本机PowerShell后台成功启动仍待实测。隔离工程通过不等于真实四序列闭环。
- **真实数据门槛：** 目标 Orthanc 目前仅通过一次 study 元数据可达性检查；没有在本轮读取像素或导入病例。`allow_pixel_read=true` 按用户授权保留。候选序列仍需人工确认烧录文字、来源许可、四序列角色及共同空间；用户暂无法确认所示切片，因此未放行真实转换/AI验收。
- **未完成的最终交付：** M3真实四序列页面链路；当前版本新材料联合备份/恢复（需有真实新增材料）；最终冻结源码/配置/数据路径与交付包；一份脱离Codex可独立使用的详细阅读、操作、修改、测试、备份恢复及故障排查手册；用户实际带教、两次完整预演及正式导师展示；完成后再盘点并整理C/E盘冗余文件。SCI不作为工程完成前置。
- **最新证据：** `E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T132214_linux-radiomics-e5/`，交接见 `CURRENT_STAGE.md` 与 `E5_DOCKER_RUNTIME_VALIDATION_20261020.md`。下方日期早于本快照的 Docker/WSL 阻塞记录仅作历史，不再表示当前状态。
- **最新源码候选：** 解包源码后端694 passed，前端生产构建通过，E2E 8 passed/1 skipped（获准真实病例用例按条件跳过）；462个文件、零扫描发现，ZIP SHA-256 `dd9886ecf3e1c023acb32914aacbb45e6494a3adbb25209de010a330f9736fd6`，证据见 `E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T155438_source_candidate_current_status/candidate-regression.json`。E2E合成场景不证明真实影像链路。这是源码-only内部候选，不包含运行环境/数据/模型，最终配置与运行数据封版仍未完成。

## 2026-10-19 E5 root-cause evidence: Windows servicing rolled back WSL feature enablement

After the user ran the elevated DISM command and restarted, the Docker installer still reported VirtualMachinePlatform disabled. Read-only WMI now reports InstallState=2 (Disabled) for both VirtualMachinePlatform and Microsoft-Windows-Subsystem-Linux. The machine reports firmware virtualization enabled and a hypervisor present. DISM/CBS logs show the enable command set VirtualMachinePlatform to On and pended changes for reboot; during startup servicing, Network Drivers failed to load NetSetupAI.dll (0x8007007e), followed by CBS_E_INSTALLERS_FAILED / 0x800f0922 and a rollback transaction. This explains why the feature was still disabled after restart; do not treat the Docker installer as the root cause.

Recovery path for the device administrator: run DISM /Online /Cleanup-Image /RestoreHealth in elevated Command Prompt or PowerShell, wait for successful completion, then run sfc /scannow. Microsoft recommends DISM before SFC to repair the component image and protected system files. After both complete, enable Microsoft-Windows-Subsystem-Linux and VirtualMachinePlatform with DISM, verify each reports State: Enabled, restart, verify again, and only then retry the regular-user Docker Desktop installer. If Windows repair fails or the same CBS rollback recurs, retain the CBS.log lines for NetSetupAI.dll and 0x800f0922 for Windows servicing repair; do not repeatedly retry Docker.

No repair command or system-feature change was executed by Codex; these diagnostics and next steps are based on read-only logs and component-state queries. Docker/container acceptance remains incomplete.


## 2026-10-19 E5 environment update: WSL installed; VirtualMachinePlatform still requires administrator enablement

The user has installed WSL. In this session, wsl --version reports WSL 3.0.3 and wsl --list --verbose reports no user Linux distribution. The Docker Desktop 4.95.0 installer explicitly reports that the Windows optional feature VirtualMachinePlatform is disabled. This session is not elevated; the read-only DISM query returned exit code 740, and no system feature was changed. Docker CLI/Desktop are not yet successfully installed; the Docker terms have not been accepted and the computer has not been restarted.

The earlier status saying WSL was not installed is superseded. E5 is currently blocked on an administrator enabling VirtualMachinePlatform and restarting Windows. An administrator can run the following in elevated PowerShell:

    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

After restart, the regular user can install Docker Desktop per-user and personally review and accept its first-run terms. Compose parsing, image build/run and E5 project validation remain outstanding. This update does not claim Docker or container acceptance.

## 历史快照：2026-10-18 交付收口状态（已由2026-10-20当前摘要取代）

### 2026-10-18 23:01生产前端浏览器增量

按当前工作树在独立E盘目录新建生产前端包（43文件、约11.96 MB，API绑定8012），Edge只读运行通过：病例17详情、四序列NIfTI/mask、研究页面和报告页面均通过；页面/控制台异常、失败请求、拦截到的写请求均为0。运行使用Edge和同源测试路由提供生产资产，API请求到当前本机后端；没有部署静态HTTP服务器、重启服务、推理、提取或业务写入。构建仍有第三方`fs/path/url`外置及大分块提示。证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2258_frontend_edge_prod/`；详细范围和限制见`CURRENT_STAGE.md`。该同机浏览器增量不解除Docker/异机或真实四序列门槛。

### 2026-10-18 22:50当前交付候选

当前内部源码候选final12共459个白名单文件，受限审计0发现；ZIP SHA-256 `d7f118d8f392fc45d6e187d495f933d437dd82d69ff6064bf09a4b57a90791f8`，解包后全量后端回归694 passed、4条既有弃用警告。只读交付复验`passed_existing_workstation_only`，候选459/459与当前工作树一致；14项实现源码、3项再现工具匹配材料包，严格本机预检通过且数据库签名未变。证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2255_source_final12/`。该状态不包括Docker/Linux或异机验收，真实四序列与人工隐私/角色门槛仍未解除。

### 2026-10-18 22:20增量：环境依赖恢复与ACRIN-134隐私预筛

独立E盘用户级Python环境从51个已核验wheel重建，`pip check`通过；Python 3.10.21主环境可导入torch 2.11.0+cu128且CUDA可用，Python 3.11.17特征环境可导入SimpleITK/PyRadiomics。严格只读预检通过，完整后端回归694 passed、4条既有弃用警告。证据位于`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2150_main_env_rebuild_candidate/`；原Conda环境未改，仍有49/54个分发缺少原始wheel来源证明。

ACRIN-134候选4个轴位MR序列共104张切片，逐张初步目视及边缘放大接触表未见明显身份烧录文字；DICOM均未提供`BurnedInAnnotation=NO`声明，且没有OCR复核。用户暂无法确认，故这只是预筛，病例仍隔离，未转换/导入/推理。完整图像与哈希清单见同证据目录下`pixel-review/README.md`。用户/合规人员仍需确认像素隐私；四序列角色、共同空间、许可和实际页面闭环均未验。

当前Codex会话无管理员权限，Docker CLI不存在且WSL2未安装。安装Docker Desktop/启用WSL2需Windows管理员在独立管理员流程中操作并按系统要求重启；之后再由普通Codex会话验证容器链路。Codex elevated sandbox需管理员预配置，且其中命令仍非管理员身份运行。

Docker权限路径已进一步核对：官方推荐的Docker Desktop per-user安装/更新无需管理员；首次启用WSL 2仍需管理员并按提示重启。故无需把整个Codex进程改为管理员。已补管理员与普通用户分工步骤，见[DOCKER_PREREQUISITES.md](DOCKER_PREREQUISITES.md)。转换作业相关定向回归本轮独立复跑50 passed、4条既有弃用警告；证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T_conversion_jobs_current_docs/pytest.log`。

### 当前状态校正

10月17日“S6带教入口地图”段落中“DICOM转换CLI尚无持久作业接口”是当时快照，已被10月18日M1网页方案增量覆盖：当前`PacsPanel.vue`及`backend/app/api/pacs.py`已提供作业创建、启动、列表、重试和进度接线，持久状态实现见`backend/app/services/dicom_conversion_jobs.py`。相关隔离工程测试不等于真实四序列验收；真实获取/转换/审核/激活/推理闭环仍未通过。当前容器权限安排见[DOCKER_PREREQUISITES.md](DOCKER_PREREQUISITES.md)。Docker Desktop/Linux Compose 隔离运行和持久化验收已于2026-10-20通过（见[E5验收记录](E5_DOCKER_RUNTIME_VALIDATION_20261020.md)）；该结果不等于干净机器安装验收或真实四序列AI闭环。

final9于2026-10-18完成构建、全量后端回归和只读交付复验：459项候选与源码一致，ZIP SHA-256 `cf134b73b7f130ea70cd3f8723cf7452ce0fc4b27b0704af4c7b6fb2952b288d`，694 passed/4条既有弃用警告；27项工程材料、14项实现源码和3项再现工具哈希匹配，严格本机预检通过，数据库签名不变。证据位于`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2315_source_final9/`。本次补充的ReMIND候选元数据筛查已进入final10文档候选`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2335_source_final10/`；该包回归/readiness以自身输出为准。

当前待完成功能/验收仍包括：取得并人工核实许可合适的同检查四序列；由获准人员查看相关序列像素并确认无烧录身份文字；确认角色和共同空间参照；完成真实转换、PACS导入、逐序列AI和页面闭环。用户对已展示候选的像素文字答复为“暂时无法确认”，因此候选保持隔离，未转换/导入/推理。Docker/Linux Compose 的隔离工程验收已通过；干净机器安装、本机普通交互PowerShell的后台启动仍待单独验收。用户带教及两次完整演练尚未完成。主环境49/54个Python分发的原始安装来源仍未记录；缓存中另找到52/54个名称/版本候选，其与已安装RECORD可比较文件均无差异，但不证明原始下载来源，详见ENVIRONMENT_INVENTORY.md。不得将合成数据、NIfTI或重采样验收表述为真实DICOM/胶质瘤效能。

## 2026-10-18 前端生产构建、指南核对与Q&A修订

Edge 155实际只读验收病例17 NIfTI与病例19 DICOM：四序列切换、非空只读mask、DICOM三视图/方向标签、跨病例缓存清理通过；测距草稿只在页面创建后删除，拦截日志为0写请求。指南浏览检查确认病例创建对话框字段与指南一致，取消不提交；病例17仅复看已有研究结果。Edge合成回归8 passed、1项按设计skip。生产构建成功，43文件/11.96 MB；入口11个脚本/样式引用无缺失，27个JS bundle含配置API地址。构建仍有第三方fs/path/url外置及大分块警告；生产bundle浏览器实际运行未验。证据分别在`20261018T2055_edge_readonly_refresh/edge-readonly/validation.json`、`20261018T2120_delivery_guide_edge/validation.json`、`20261018T2105_frontend_e2e_edge/`、`20261018T2130_frontend_production_build/`和`20261018T2145_frontend_asset_integrity/`。修订问答以澄清UCSF-PDGM的NIfTI用途和用户对展示图像的未确认答复；不改变真实数据隔离门槛。最新候选路径见本页20:35当前候选更新。

## 2026-10-18 20:35 E5依赖锁与候选交付更新

本次最终证据覆盖Linux amd64目标wheel锁、来源包审计和Windows全量回归，不代表容器或真实四序列验收。Compose现将前后端固定为`linux/amd64`，Docker core/full锁为28/44个SHA-256固定wheel；定向测试11 passed，工作树与最终候选均694 passed、4条既有弃用警告。最新候选`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2205_pixel_qna_final7/candidate/`有459个文件、审计0发现；包SHA、wheel核对和逐文件白名单一致性见相邻`candidate-regression.json`。本机Docker CLI不存在且WSL未安装，未进行容器构建/运行；E5仍未验。真实四序列像素烧录文字用户暂无法确认，候选仍未导入/转换/推理；带教及两次预演未开始。

以下较早快照仅作历史记录；当前状态以本节和后续新日期记录为准。

## 2026-10-18 20:40 服务退出观察交叉核对

正在运行的六小时只读观察进程PID16316（计划于UTC 14:22结束）已记录旧后端4108和前端21448于UTC 09:43:07退出，原样退出码均为4294967295。对照同秒的`20261018T1040_live_source_alignment/planned-restart.json`与`stop.log`，这是为加载当前已测试源码而执行的计划停止，不是新的未知退出。Orthanc未停止；后续后端28328/前端11988于UTC 10:27按原runtime配置启动，服务身份、页面/API/PACS/账户健康通过；数据库17表111行重启前后逻辑摘要相同。当前只读状态见本机`status_local.ps1`，监测原始事件见`20261018T0820_service_stability/observation/events.jsonl`。该窗口没有发现新的非计划退出，但观察进程仍只绑定旧服务身份中的Orthanc，尚未结束；不能据此推断长期稳定，也不解释10月16日那次历史三服务退出，旧根因仍未知。

## 2026-10-18 18:45 最新E5配方及交付检查

三阶段官方基础镜像现固定Docker Hub多架构SHA-256索引：Dockerfile含Python 3.10 slim Bookworm、Node 24 Alpine 3.24、NGINX 1.30.6 Alpine 3.24；基础镜像摘要回归8项通过。后端全套691 passed、4条既有弃用警告；454文件源码候选审计和解包回归通过，ZIP SHA-256 `a73030c528e1ad2927ce8dc13d2270e2ae9f895e09de4981d6f29b0dd8205561`，详见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1837_docker_base_lock/`。该变更提升基础镜像可复现性，但没有Docker CLI，未拉取/构建/运行；Python间接依赖hash-lock、运行态Linux/PACS/工作器验收仍待。真实四序列的像素与角色人工门槛也未解除。

## 2026-10-18 18:34 当前服务完整性只读冒烟

修复后的常驻API对一份已存在、已验收的NIfTI模型分析执行只读检查：`/analysis`、病例详情、历史与分割状态均HTTP 200；当前分析未过期、历史标记当前、分割可用；4次请求未写业务数据，也未保存病例ID、结果值或路径。耗时约0.04、0.07、0.04及0.24秒。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T_integrity_live_readonly/validation.json`。这是当前NIfTI服务冒烟，不是新DICOM或四序列模型验收。

## 2026-10-18 18:30 工程检查增量（早前快照）

分析/特征完整性修复同大小且恢复mtime的内容改写漏检；隔离定向13项通过、当前源码完整后端690 passed、最新454文件候选解包回归690 passed。候选ZIP SHA-256 `1ddd37f1df66d85bd1400c6fab7dc61d161bcea483d9618502f397a58046a365`；每次核验重新读取文件内容。本机单一已验收NIfTI样本5文件共20.28 MiB，两遍哈希约0.018秒；不代表更大DICOM或容器性能。前后端按原13路径配置重启，数据库17表111行逻辑摘要一致，PACS/账户/前端健康，Orthanc保持原PID。真实四序列仍待像素隐私人工确认和四角色判断；Docker/Linux未验，用户带教与预演未开始。

## 2026-10-18 文件完整性校验耗时测量

只读测量本机一个已验收模型分析所用的4个NIfTI输入与mask：共5个文件、20.28 MiB；首次顺序SHA-256为0.0178秒，第二次为0.0170秒，摘要重复一致。报告不保存病例ID或路径，见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T_integrity_hash_benchmark/validation.json`。这是一个本机NIfTI样本的文件读取性能量级，不代表更大DICOM病例、并发环境、Docker/Linux或医学效能验收；性能随盘、文件大小与缓存变化。尚无必要为少量重复哈希引入跨请求缓存，避免再次出现内容漂移漏检。

## 2026-10-18 文件完整性同元数据漂移修复

在分析/特征完整性接口中复现并修复：文件内容改动但字节数不变、修改时间恢复原值时，按路径/大小/mtime缓存摘要会漏掉漂移。`checked_digest`现每次读取文件内容计算SHA-256，再决定是否显示当前分析/特征；不重写已成功历史记录。新增同大小同mtime回归覆盖分析与特征API，隔离测试确认漂移后当前结果被隐藏、历史记录和状态文件保持不变。

验证：旧实现的定向复现按预期失败；修复后完整性定向13项通过；当前后端完整回归690 passed、0 failed、4条既有弃用警告。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T_integrity_hash_cache/`。每次核验会重新读取MRI/mask文件，换取内容级漂移识别；对大文件读时影响尚未在真实多序列数据或目标容器环境中实测。未改变正式病例、模型结果或业务数据库内容；本机前后端按原配置正常重启，Orthanc未重启。

## 2026-10-18 18:10 工程检查增量（早前快照）

当时内部源码候选`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1330_source_candidate_env20/candidate/`为454文件，受限凭据审计0项，ZIP SHA-256 `e31bf3c3fdc5d4f8bea0fb3f110a9c28f51c9030e5894125f6ef2a88f5dd2119`；解包候选全量后端回归688 passed、0 failed、4条弃用警告。主CUDA环境20/20个Conda原始归档现均有独立SHA复核；49/54个Python分发的原始wheel来源仍未知，尚非完整安装锁。Docker/WSL仍未安装，用户级Docker安装命令在执行前被Codex自动审批拒绝；数据像素仍未获人工确认。当前前后端和Orthanc状态健康。完整环境障碍、用户问答与带教顺序见`DOCKER_PREREQUISITES.md`、`PROJECT_DEMO_QA.md`及`PROJECT_HANDOVER_AND_FORMAL_DEMO.md`。本地Windows工程回归通过不替代真实四序列或Docker验收。

## 2026-10-18 工程检查增量（早前快照）

分析历史错误隔离与病例切换竞态两个Edge场景通过：当前状态接口失败时历史列表仍显示；旧病例迟到响应不会覆盖新病例。完整Edge E2E 8 passed/1按设计跳过，生产构建通过，当前5179服务模拟API Edge冒烟2 passed。最新源码候选454项与当前源码454/454一致，数据库签名未变；证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/analysis_history_error_final_v2/`。这是模拟API的页面工程验证，不是真实DICOM验收。用户目前无法确认ACRIN-134像素中的烧录文字，该病例继续未导入、转换或推理。新机/Docker/Linux、真实四序列闭环和用户带教/正式演示仍待完成。

# 系统完成台账

## 2026-10-18 真实分析历史页面只读冒烟

当前5179前端读取8012真实后端的只读Edge检查通过：既有病例页面HTTP 200、历史列表有1条记录、无页面异常和历史读取警告；验证仅保存计数/状态，不保存记录内容，不进行业务写入。证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/analysis_history_live_case_readonly_retry1/`。

## 2026-10-18 E5 Docker核心依赖锁子项

已为Docker CPython 3.10 Linux x86_64提供core/full两种二进制wheel SHA-256锁，分别28/44项；Dockerfile强制哈希校验，Compose选择含CPU Torch/MONAI/研究闭包的full profile。Pillow目标调整为12.2.0。定向11项、工作树及最终459文件候选全量694项通过，4条既有弃用警告；候选审计无发现、ZIP SHA-256 `e933dd0dbfabc2c526fe0c8c0a2ac5f743d9f9b7d7de539afe01b8db99c6e0c0`。44/44 wheel版本与SHA已核对。apt、镜像构建运行、持久卷/PACS/工作器Linux验收仍缺。E5保持未验。

## 2026-10-18 既有源码候选与环境来源补充（早前快照）

当前内部源码候选按白名单冻结454个源码文件，受限凭据扫描0项，ZIP与逐文件解包SHA校验通过，该候选是18:02之前的早前快照，当前候选与哈希见本页18:10最新增量；源码包不含数据、模型、运行环境/依赖或私有PACS/账户配置。材料包在`20261018T1610_materials_refresh/`，27项材料及ZIP成员校验通过，PDF文字/严格碰撞审计和人工渲染复看通过。最终只读交付核验见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/analysis_history_error_final_v2/readiness/`：当前源码454/454与候选完全一致、现有运行时预检通过、数据库签名未变；新增角色审核→显式激活Edge合成场景1项通过、分析历史列表Edge场景通过、激活后历史/报告隔离模块3项通过（均不代表真实来源验收）；Edge全套8项通过、1项按设计跳过。新增`capture_conda_provenance.py`读取20个Conda包已登记URL/SHA-256，其中16个本机缓存包重算匹配，剩余4个未在缓存；pydicom wheel重算匹配，49/54个Python分发的其他原始wheel来源仍未知，不能称完整安装锁。替代集合的人工/元数据待查项见`PUBLIC_FOUR_SERIES_DATA_SCREEN_20261018.md`。E6仍进行中：新机/容器、真实四序列DICOM到AI、用户人工演示仍未验。

## 2026-10-18 P3显式重采样及常驻服务版本对齐

显式重采样仅作为用户勾选后的工程转换路径，默认严格网格仍保持；任何重采样方案在当前版本均不能激活为模型输入或启动推理。常驻本机前后端已通过既有E盘Runtime配置更新，启动前数据库快照恢复校验通过；更新前后17张表逐行摘要一致，PACS/账户配置SHA-256不变，Orthanc身份未变。更新后健康检查、PACS/账户就绪和OpenAPI重采样字段通过，Edge重采样页面测试1 passed。后端全回归686 passed；源码候选453文件、0项凭据扫描发现，最终解包目录15项交付策略测试通过。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1540_backend_resampling_live/`、`20261018T1518_current_source_candidate_final/`。ACRIN-134仍因缺少BurnedInAnnotation=NO且用户暂不能人工确认烧录文字而未转换；ReMIND-013首个四序列候选角色的176张DICOM也全部缺少该字段，故未继续下载/导入。P3真实来源桥仍受阻，筛查证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/remind013_dicom_screen_retry1/`。

## 2026-10-18 B2持久转换作业工程子项

B2新增工程子项：转换作业通过E盘作业目录持久保存状态及隔离输入哈希，支持失败/中断识别、attempt重试和短路径保护；病例范围清单API与医生CSRF重试API已加载常驻本地服务，现有PACS面板展示/轮询并可重试。后端定向测试22 passed、4条既有弃用警告；Microsoft Edge合成API交互、前端生产构建、严格启动预检及实际本机服务版本更新通过。活动数据库重启前后17表逐行摘要一致。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T032925Z_b2jobs/`及`.../20261018T035504Z_b2jobs_live/`。

此项只代表持久作业/状态查看/失败重试组件，不代表网页可创建全新作业、真实四序列转换、角色审批/激活、DICOM来源推理或B4。真实DICOM库存最近一次可核实证据为10/17的一项MR检查/一条序列；不满足角色映射。本轮正式DB无逻辑行变化，未导入真实数据。
更新：2026-10-18；B2作业重试子项在当前服务加载并通过定向验证；B2其余接线与P3真实来源门槛未完成。

## 2026-10-17 15:27 B2审核输入绑定与执行哈希守卫

B2工程组件新增验收：分析API只消费当前已激活MRI；提交前四个转换NIfTI必须逐字节匹配激活时审核SHA-256，哈希清单绑定到AnalysisRun，工作器加载前/后复核，结果返回后再次比对。激活后字节漂移在提交前拒绝；后台结果哈希不符时不应用分割/报告。隔离验证9项通过（4条既有弃用警告），包含审核输入绑定、漂移409拒绝和错误后台结果失败。证据：E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1458_b2reviewedinputguard/、20261017T1524_b2workerretry/。

此增量只验B2工程合同，不提升P3：真实归档仍仅有1项MR检查/1条序列，真实角色审核、转换、推理未做；四序列来源门槛待解除。
更新：2026-10-17 15:27；B2审核输入哈希绑定及当前源码候选解包回归通过；P3仍需真实四序列来源/实审/闭环。

原82,833字节台账已逐字节保留在 [历史详细台账](history/SYSTEM_COMPLETION_CHECKLIST_20261014_before_consolidation.md)，SHA-256 `54fec248ff272c79d4d364293d59e9b45d204029d5bd6a6753070aa0f27b8c32`。其中旧状态仅代表当时窗口；所有P1/P2/P3/P4细分项、F/E缺陷及原证据路径继续保留，不用旧表覆盖本表。归档一致性记录见本轮证据 `checklist-history-copy.json`。

## 当前状态

| 编号 | 状态 | 依赖 | 完成标准 | 已知证据及验收边界 | 剩余事项 | 上次更新 |
|---|---|---|---|---|---|---|
| P1 | 已验收 | 现有受支持真实NIfTI、Cornerstone5.7.0 | 三视图/四序列、方向/工具、只读mask、毫米距离保存、视图保存刷新/重启、病例切换清理及显式Canvas回退 | 历史：P1-a/b/c；[P1测量与视图验收](P1_MEASUREMENT_VIEW_VALIDATION.md)，包括独立空间参考、真实测量及非单位网格夹具 | 仅受支持NIfTI范围；Cornerstone只开放距离。当前[Edge NIfTI保存/关闭恢复](P4_EDGE_NIFTI_VALIDATION.md)三平面毫米/四序列/相机窗值/只读mask开关/删除和显式Canvas通过；可见人工窗口/其他浏览器另列，DICOM归P2–P4。 | 2026-10-16 |
| P2 | 已验收 | 已获准本机Orthanc、已登记CC BY4.0公开经典MR与来源/像素复核包 | 在明确支持范围内：受控导入、检查/序列/实例、UID病例关联、重复规则、Cornerstone阅片及重启持久化 | 历史旧候选192真实导入/去重/失败恢复及来源准备保留；当前[来源绑定v2真实分支](P2_V2_REAL_IMPORT_VALIDATION.md)新增192回读192、PNG变化拒绝、UI刷新/显式关联、全9,437,184体素三视图及双服务重启通过，原17表/八路径/归档不变 | 仅受支持经典单帧未压缩非MOSAIC及规则空间；任意浏览器上传/自动像素脱敏/医院现网PACS不在已验范围，不以技术复核冒充临床认证。真实四序列桥归P3 | 2026-10-16 |
| P3 | 受阻 | 真实归档、可核对来源UID/几何、符合既有模型输入的四序列 | 来源/转换版本可追溯，角色审计、网格契约、真实转换登记/激活、原空间分割与研究/报告闭环 | B1/B2及M1网页选序列→预览→原DICOM捕获→持久作业入口已接线；46项相关隔离回归通过；转换材料恢复工具16项隔离用例通过；显式1mm重采样仅工程验收路径已实现，相关88项回归和Edge重采样页面场景通过；ACRIN-134几何规划通过但真实转换因源DICOM缺少BurnedInAnnotation=NO而安全拒绝 | 真实PACS最近可核实库存仍为1检查/1序列；ACRIN-134未生成NIfTI/未登记/未激活，ACRIN-134及ReMIND-013未通过烧录文字门槛（ReMIND-013首序列176/176实例缺标签）；ReMIND-110的T2-FLAIR只读元数据检查33/33实例也缺BurnedInAnnotation（未请求像素）；待独立像素审核或找到含显式声明的来源；角色仅按序列描述暂列；真实转换→恢复→页面阅片/角色审核闭环、模型输入/推理/特征/报告仍未完成 | 2026-10-18 |
| P4 | 进行中 | P1–P3及F/E迁移回归 | NIfTI与DICOM空间/工具/生命周期/版本/性能、归档/业务/回执联合恢复、来源报告和演示材料 | 历史P1/距离/视图/复核/长报告保留；历史[17表完整联合恢复](P4_JOINT17_RECOVERY_VALIDATION.md)：196归档配置/650应用/5导入文件，实际独立服务192SHA及36距离/1视图/3复核快照/导出SHA/三视图一致，正式17表全行/原路径不变；架构源码与固定演示同步 当前账户最小联合接线与Edge155 headless两种真实来源只读/鼠标/毫米草稿/清理通过； 当前[Edge保存/关闭恢复](P4_EDGE_PERSISTENCE_VALIDATION.md)：真实账户第6条、三页身份PDF逐页查看、登录/退出关闭恢复、三相机/窗值及轴位距离保存/关闭恢复/删除通过。 当前[Edge NIfTI持久化](P4_EDGE_NIFTI_VALIDATION.md)亦通过；两种来源Edge明确范围已验。 当前[两来源分层性能](P4_VIEWER_PERFORMANCE_VALIDATION.md)：Edge单病例首载/切片/切序列、QIDO查询、阶段进程WS/私有提交/页面堆，0写/192帧与原件保护通过。 当前[19病例/账户完整数据组合](E6_FULL_ACCOUNT_RECOVERY_VALIDATION.md)650应用/196归档/5导入/两账户、两种真实来源与科学API、复核/双服务重启通过。 当前[服务恢复/导航一致性](LOCAL_SERVICE_RECOVERY_VALIDATION.md)：三服务原配置恢复、Edge六场景/真实NIfTI-DICOM三视图及0业务写通过；退出根因仍未知，观测不作长期稳定承诺。| 当前直接CPU/固定PACS补充目录HTTP与重启/回原已验；独立新机/容器、可见人工抽查及P3真实匹配四序列模型桥未完；单独纯上传/生产并发不由单例外推，其他浏览器不纳已验范围。 | 2026-10-16 |
| F1 | 已验收 | 合法真实NIfTI病例及模型/工作器 | 新建上传、真实分割、叠加、自动特征、研究预测、复核、报告/PDF闭环 | 历史：stage2/3/4/6及10/9真实病例17流程/PDF视觉核验；详见历史台账 | Cornerstone NIfTI迁移相关部分由P1承接；真实DICOM新闭环待P2–P4，不抹去原成果 | 2026-10-14 |
| F2 | 已验收 | 病例关联患者、版本化研究输入 | 默认输入有来源、修改新版本、旧结果失效，页面/数据库一致 | 历史：clinical-browser、clinical-persistence-f5及stage6；没有重算或改变病例 | 新DICOM接入后的病例关联回归归P4 | 2026-10-14 |
| F3 | 已验收 | 四序列同网格空间契约 | 序列切换保留物理位置、方向、叠加、窗值和测量坐标 | 历史：Canvas四序列回归；Cornerstone NIfTI对应项由P1验收 | 真实DICOM空间/序列切换回归待P2–P4 | 2026-10-14 |
| F4 | 已验收 | 阅片与标注API | 实际开放工具的创建/保存/刷新/删除及物理单位，未可靠功能披露 | 历史Canvas十工具/P1 NIfTI距离保留；当前P4真实DICOM默认三正交平面毫米距离保存/恢复/删除、重启与原NIfTI相关回归通过，原mask只读 | 不把Canvas十工具套用于Cornerstone；ROI/角度等未开放，旋转DICOM平面保存未支持；本轮独立DICOM阅片记录/PDF含当前距离已验，来源复核另验 | 2026-10-15 |
| F5 | 已验收 | 分割/特征及持久转换作业状态与版本保护 | 排队/运行/成功/失败/中断/可重试、刷新续接、去重及具体拒绝提示 | 转换方案创建、作业账本状态/中断识别、失败attempt重试、病例范围列表、医生CSRF启动/重试API及面板轮询提示纳入最新完整后端691项回归（含46项M1/M2定向用例）；Edge全套6项通过（含角色审核→显式激活及分析历史列表场景），1项需真实获准病例的报告场景按设计跳过 | 真正DICOM转换/角色审核与激活仍待真实同检查四序列；组件验收不等于模型运行成功 | 2026-10-18 |
| F6 | 已验收 | 当前版本分析、临床输入/研究结果、医生意见 | 真实来源/版本/限制可见，医生意见独立，失效报告/PDF不可用并视觉检查 | 历史：研究页、来源报告、PDF两页视觉核验；P4新增模型/权重/mask/四序列摘要 | 独立DICOM阅片记录/PDF来源及当前距离已验；来源/内容绑定人工复核已验；当前新复核绑定本地账户，旧历史未认证、均不代表医师资质；真实DICOM模型报告待验，研究摘要尚未纳入PDF（可选） | 2026-10-15 |
| E1 | 已验收 | 正式API及UI路径 | 禁用占位MRI/固定风险/旧融合/生存，保留历史且不当当前结果 | 历史：旧预测/生存503、旧记录归档与旧PDF保护；正式真实模型路径 | IDH编码未解时继续原始目标值语义，不写通用风险/治疗建议 | 2026-10-14 |
| E2 | 已验收 | 分析/特征/临床/报告版本及文件谱系 | 重分析/重提取/缓存/输入修改/中断/重启关系正确，历史保留 | 历史：10/9–10/10真实恢复与独立副本漂移、PDF导出期间再次校验；详见历史台账  当前[病例上下文导航回归](LOCAL_SERVICE_RECOVERY_VALIDATION.md)修无效ID/404/旧HTTP响应覆盖，真实延迟19→17/上下文/意见守卫通过；不改分析/报告历史。| 当前DICOM本机复核的距离/意见/元数据失效与历史已验；转换/模型关系待P3/P4，每次读取MRI/mask字节做SHA-256漂移检查；本机样本5文件/20.28 MiB两遍各约0.018秒；更大DICOM/Linux开销未测 | 2026-10-16 |
| E3 | 已验收 | 可重定位配置、原数据/模型/产物 | 前检、服务身份复用、先备份后副本恢复，原件不变 | 历史638文件/旧650应用及196归档配置/17表完整恢复保留；当前[账户DICOM最小联合接线](P4_JOINT_ACCOUNT_RECOVERY_VALIDATION.md)真实CLI/活服务、自动账户收录/损坏拒绝/另存复核/重启/原件保护通过，仅2应用文件；声明空目录恢复修复及17项检查通过  当前[19病例/原正式账户完整数据组合](E6_FULL_ACCOUNT_RECOVERY_VALIDATION.md)真正CLI和活服务/双服务重启、650原文件/科学字段与原库保护通过。 当前[恢复与身份](LOCAL_SERVICE_RECOVERY_VALIDATION.md)原三服务正常启动/复用、匿名归档401/账户配置及17表四配置八路径保持，原日志先存；退出码只读观察中，不声称退出根因修复。| 本机数据/模型/归档组合已验；源码/已安装环境和再导入来源材料仍为明确外部前提，独立新机安装归E6/E5；不再逐轮重抄650。 | 2026-10-16 |
| E4 | 已验收 | 固定提取协议与旧复现环境 | 受支持PyRadiomics环境及来源锁定，同MRI/mask/参数特征/概率复现后切换 | 历史：Conda-forge3.11.17+PyRadiomics3.1.0，五参考55有限特征/旧概率差0、自动mask20特征/五概率差0；旧环境/CUDA保留 | 仅本机CPU兼容；Linux/容器、异机最终验收归E5/E6，不静默换协议 | 2026-10-14 |
| E5 | 已验收（隔离Docker/Linux Compose范围） | Docker/WSL、E3/E4 | E盘镜像/缓存/数据、前后端/两工作器、只读模型、CPU执行、重建后持久化 | 2026-10-20实际full/core Linux镜像、双容器健康、OpenAPI/PACS QIDO元数据、五个只读挂载拒写、Linux特征worker参考样本、最终镜像数据库/上传/作业标记重建持久化均有验收证据；Orthanc身份重绑先备份后完成。详见`E5_DOCKER_RUNTIME_VALIDATION_20261020.md` | 不覆盖干净机器安装、普通交互PowerShell后台启动和真实四序列像素/AI验收；真实病例仍受许可、人工像素及角色复核约束 | 2026-10-20 |
| E6 | 进行中 | 全部系统交付项 | 最终构建/浏览器/真实病例、README/操作/部署/演示与论文材料一致 | 历史CPU/前端/worker引导与图包保留；当前README/分开演示/备份指南与PACS17表验收同步，新架构/声明关系Mermaid源码  当前[架构/关系图SVG与PNG](E6_ARCHITECTURE_FIGURES.md)已实际源码核对/渲染/逐图查看。 当前[范围与浏览器矩阵](RELEASE_SCOPE.md)纠正过时PACS排除/Edge未验表述，旧范围字节归档，演示和实际同步复用脚本已核对。 当前[完整账户数据组合](E6_FULL_ACCOUNT_RECOVERY_VALIDATION.md)19病例/两种来源/实际重启已验，外部程序/环境/再导入材料边界已核对。 当前[导航修复与构建](LOCAL_SERVICE_RECOVERY_VALIDATION.md)Edge155六场景、实际两来源、最终构建/截图与只读退出观察边界已验；429源码组合不含本轮新修复，未重打全包。| 历史[源码候选](E6_SOURCE_CANDIDATE_VALIDATION.md)402文件/逐文件解包、128相关检查和43文件构建已验；10/16冻结包不含B1/B2当前源码（12个选定路径中8个在包内、0个字节相同、4个缺失），须源冻结后重建；原52包CPU基环境保持只读；当前[53包CPU/PACS CLI](CPU_PACS_RUNTIME.md)及404文件源码组合已验，Windows venv启动PID差异已有明确拒绝保护。当前[直接解释器+固定补充目录HTTP组合](E6_CPU_PACS_LIVE_VALIDATION.md)和408文件源码增量已验，实际Edge首启/重启与账户/科学API/17表保护、复用/停止/回CUDA通过；当前[研究源码增量](E6_RESEARCH_SOURCE_DELTA_VALIDATION.md)408→429文件、25项增量/75解包检查和7实际CLI拒绝通过，R2–R4协议/指南精确收录；旧原ZIP不改、无新前端构建。独立新机/容器、可见人工及P3/P4/E5剩余门槛保持。 | 2026-10-16 |
| R1 | 受阻 | 合法数据、固定协议、患者检查归属/角色冻结 | 同协议参考/自动特征、训练内预处理、探索性重拟合及来源版本；临床解释和独立评价另设门槛 | 历史：141人98/21/22探索性登记、五例兼容；05:12保留的官方文件指纹刷新。原22人不能随机重分恢复独立性  当前[R1训练侧10例准备](R1_TRAINING_PILOT_VALIDATION.md)：冻结名单/40文件传输计划、10不同组件检查及4实际CLI写前拒绝通过；新增MRI实际0，官方TLS/DNS失败，已停止不变条件重试；先前152人是ZIP清单非本地完整队列。| 原始0/1工程验证可独立推进；临床编码极性、MONAI患者重叠及未查看独立评价仍缺证据，不能阻塞普通阅片/联邦算法开发 | 2026-10-16 |
| R2 | 进行中 | 同患者/原始终点/允许信息、固定队列协议 | 平均/固定/全局TOPSIS/熵权TOPSIS、验证侧拟合、退化/缺失回退、保留负结果 | 历史stage4负结果及上一轮[R2组件](R2_ENTROPY_VALIDATION.md)28分批用例/旧六方法复核保留；当前[R2敏感性/缺模态](R2_ABLATION_VALIDATION.md)：协议/配置先冻，15新检查/7拒绝，40验证变体/21权重点/六场景六方法完整失败分母，原服务/17表保持  当前[R4六法参考表格区间](R4_FUSION_INTERVAL_VALIDATION.md)22人/六法2000患者抽样及72000独立核对通过，不替代全自动参考队列/重拟合或本六法校准。| 同协议自动/参考完整队列重拟合对照及独立评价仍未验；R3表格产物的R4区间/校准已局部通过，不替代完整融合队列统计；本批已观察22人事后描述不选优，动态质量权重无代理延期；不把204模拟失败条目当独立患者 | 2026-10-16 |
| R3 | 已验收 | 冻结患者拆分/初始化/预算，可与临床编码核查独立 | Centralized/Local-only/FedAvg/FedProx/TOPSIS，IID/预定义Non-IID，至少3预定种子、各/最差中心、轮权重/时间/通信 | 历史FedProx9数值组件保留；当前[R3完整轻量模拟](R3_FULL_VALIDATION.md)：预冻3种子/2场景/6同构逻辑方法、36方法条件，26不同检查分批/7拒绝，21公共验证拟合、22已观察探索评价，108中心及最差定义数/每轮/通信/重载/原库保护均验 | 已验仅本机参考掩膜固定表格模拟；共享集中预处理/公共验证、训练侧标签偏斜与身份哈希评价中心已披露，无真实医院或隐私保证。R1/R2同协议自动队列和R4统计解释/独立评价仍未完成，不升级临床结论 | 2026-10-16 |
| R4 | 进行中 | R1–R3可用产物与患者级统计协议 | 患者级区间/校准/Brier/敏感特异、全部失败及适配表格模型解释 | 当前[R4局部验收](R4_STATISTICS_VALIDATION.md)：22已观察患者、24均值/校准向量、2000共同分层重抽样；14分批用例/7拒绝/288000指标独立核对、12验证温度及792个体逻辑解释通过。校准12条件Brier均变差，主差退化完整披露  当前[六法融合区间补充](R4_FUSION_INTERVAL_VALIDATION.md)复用原22人共享索引、六向量/四配对差/72000独立重算通过，负差与退化保留；参考表格范围，本六法校准及完整分割/独立评价仍缺。| 全同协议自动/参考队列与分割空区域/全部失败仍not_evaluated；临床极性/独立评价未解；条件区间不含训练/校准拟合不确定性，贡献不作因果，未激活 | 2026-10-16 |

## 当前阻塞及分开的解除条件

- R1新增MRI传输（14:32首次实际扩批）：官方API Python TLS EOF、Windows Schannel DNS无法解析，实际0新MRI。10训练人名单/协议已冻，解除需官方网络条件新证据或可核对官方ZIP后补本地读取；不在条件不变时按小时重试。当前转已完成R4六法区间及下一验证侧校准，旧五工程例不冒充新队列。

- P2环境：19:08人工正常提供官方候选并启动本机Orthanc后已解除；当前正常运行的既有可信环境继续复用，历史自动审批拒绝记录保留，不换工具重试该被拒动作。E5 Docker授权阻塞单独保留。
- P2样本：192实例经典非MOSAIC MR的白名单元数据派生副本19:35已实际归档/阅片，20:16独立副本联合恢复再验；源原件保留，技术查看不能冒称临床脱敏认证。同患者60实例FLAIR声明层距1mm/实测约3mm，继续拒绝。均为发布者处理的临床来源DICOM，非本地NIfTI生成；未绑定AI四序列身份。
- P3真实模型输入：需要匹配同一受支持网格的四序列、可审计身份和转换/版本激活路径；不由名称猜角色；此条件不附加到P2单序列阅片。
- R1临床解释/独立评价：原始0/1工程验证与算法开发可独立继续；未知数值极性/预训练重叠/外部未查看队列只能限制相应结论。

## 使用与证据规则

开工按最新交接、实际文件与进程判断，不把元数据文件存在当服务运行。所有实际写入/测试/启停/路径切换使用`backend/tools/run_development_step.ps1`执行有限同步脚本；同一实际进程持有`FileShare.None`并在finally释放。锁内重新核对基线，切换/验证/回正式目录放同一步；旧后台holder已退役，不再调用或通过等待会话保活。实际句柄而非仅JSON/PID存在决定互斥。

历史验收不自动等于本轮重新通过；详情见阶段文档、[每日记录](daily/2026-10-14.md)及原E盘证据。没有新失败时不重复安装、打包、原单例PDF/特征恢复或来源可达性探测。不新增恒false接口来代替实际导入/激活。连续两轮条件不变时记录一次阻塞，再转独立未完成任务。

本次接续服务恢复及新PID/日志见NIGHTLY_HANDOFF当前头部；仅重启原已获准本机服务，没有改Orthanc环境权限。R2新组件未纳入先前408源码交付组合。







## 2026-10-17 16:01 S6带教入口地图

状态：进行中（只完成带教材料子项，不改变S6最终验收状态）。实际行为：新增页面→API→服务/数据表和运行排错入口地图，并链接到带教计划。检查到当前DICOM转换CLI尚无持久作业接口，转换索引为只读消费端，作为B2剩余实施项；不将其伪装成真实闭环。服务身份核验见 E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1601_s6codemap/service-status.json；全套或模型测试未运行。



## 2026-10-17 B2显式转换版本登记

状态：进行中（登记子项通过；B2总体仍待完整作业/界面、旧结果与任务历史、真实输入验收）。已新增显式CLI登记入口，只有成功转换并通过完整本地复核后以锁+原子替换写E盘索引；重复登记幂等，失败不落索引；仅进入后续审核列表，不切换MRI。隔离定向及跨进程争用测试18 passed；未进行DICOM转换、AI推理或常驻服务重启。证据见 E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1609_b2locktest.retry1/verification.json。





## 2026-10-17 S4 B2源码候选

当前B2登记子项源码已纳入新内部候选并在解包副本复跑18项定向测试；完整转换作业、UI、常驻后端加载和真实DICOM→AI仍未验收。候选不对外发布。证据见 E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1612_s4current/verification.json。



## 2026-10-18 12:49 M1页面启动增量

截至12:49，当时新建四序列方案仍未实现；该状态由本文件后文“2026-10-18 M1网页方案创建增量”更新。此前已接入的页面启动/进度/失败重试、按job+attempt去重、切病例守卫和测试隔离仍有效。

## 2026-10-18 M1网页方案创建增量（子项通过，里程碑未验收）

病例页现在可明确选择同一检查四序列、服务端检查几何、从已绑定固定归档核验/保存原始字节并创建排队作业；医生登录/CSRF与病例绑定，页面不传本机服务器路径，另有显式启动转换步骤。16项合成后端回归和Edge交互、构建、在线路由加载通过；17表重启前后摘要相同，Orthanc未重启。当前归档只含1检查/1序列，所以真实取件和转换仍未验证；角色审核/激活/AI绝未因此自动通过。证据见`PROGRESS_REVIEW_20261018.md`及Runtime `20261018/web_conversion_plan`。M1仍在进行中。



## 2026-10-18 转换材料恢复与交付状态

联合快照已补齐索引、方案草稿、原始采集文件、作业和转换输出的同批收录，以及恢复时路径重定位和哈希更新；隔离用例16通过。当前正式转换索引/草稿/输出均不存在，作业目录为空，故没有真实转换材料可以交付，也未做停机全系统快照。仍需在合格同检查四序列拿到后按页面完成真实获取/转换/角色复核，并将产生的真实材料纳入私有联合备份后做独立恢复。证据和盘点见 `E:/BrainFusion-Runtime/results/nightly/2026-10-18/conversion_recovery/`。


















