# 本机运行与复现

## 当前可用入口：隔离 Docker NIfTI 演示（2026-10-20）

当前 Compose 前后端运行实例已复核为 healthy，前端地址 http://127.0.0.1:18180，后端仅本机 127.0.0.1:18100。它使用病例17的隔离 NIfTI 运行副本，不写正式数据库；页面操作请保持只读。配置文件解析有效，运行容器镜像ID、Compose 文件、E盘挂载路径与只读属性逐项匹配，后端配置/模型/研究/数据集/PACS派生五个挂载只读，只有隔离 runtime 数据挂载可写。环境文件只提供路径和端口，不把其中值复制到公开材料。核对结果：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T2040_compose_delivery_config/active-compose-config-audit.json。


## 2026-10-20 PACS运行补充

本机Orthanc当前在外部PowerShell以前台方式运行；PACS可查询元数据但像素读取关闭。不要按下方较早的8012/5179服务实例段落覆盖当前Docker演示端口18100/18180。现行Orthanc启停、身份与只读验收步骤见[前台恢复记录](ORTHANC_FOREGROUND_RECOVERY_VALIDATION_20261020.md)；页面演示只使用病例17 NIfTI只读流程。
### 只读检查当前 Docker 演示

在 PowerShell 中运行以下检查。环境文件只由 Compose 读取路径/端口；不要把它复制进源码目录、公开截图或消息。检查不会启动/停止服务或写入病例数据：

~~~powershell
$envFile = 'E:\BrainFusion-Runtime\results\nightly\2026-10-20\20261020T1815_real_nifti_compose_demo_fixed\compose-demo.env'
$project = 'E:\BrainFusion-AI'
docker compose --env-file $envFile --project-directory $project -f (Join-Path $project 'docker-compose.yml') config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose 配置检查失败' }
(Invoke-WebRequest 'http://127.0.0.1:18180/' -TimeoutSec 10 -UseBasicParsing).StatusCode
(Invoke-WebRequest 'http://127.0.0.1:18100/' -TimeoutSec 10 -UseBasicParsing).StatusCode
$openapi = Invoke-RestMethod 'http://127.0.0.1:18100/openapi.json' -TimeoutSec 10
@($openapi.paths.PSObject.Properties).Count
(Invoke-WebRequest 'http://127.0.0.1:18100/pacs/status' -TimeoutSec 10 -UseBasicParsing).StatusCode
docker inspect --format '{{.Name}} {{.State.Status}} {{.State.Health.Status}}' brainfusion-backend brainfusion-frontend
~~~

当前通过时，四个HTTP状态码为**200**，路由数为**68**，两个容器显示**running healthy**。后端根路由 / 是健康检查入口；本版本没有 /health 路由。若容器不存在、任一检查失败或显示非healthy，先保留错误输出，不要反复启动第二套同端口Compose；页面日常浏览仍按上面的只读边界操作。

本路径只证明当前机器上该隔离 Compose 演示可运行，不证明干净机器安装、真实四序列DICOM/AI、临床效能或最终交付包。演示浏览、启动和停止说明以隔离 Compose 演示指南为准；该容器已在运行时不要重复执行启动命令，结束时只按指南关闭此项目。下面按日期的Windows原生运行记录中，2026-10-20 19:29的Job限制和“PACS未恢复”仅是当时历史快照，已被本文件顶部状态及[Orthanc前台恢复验收](ORTHANC_FOREGROUND_RECOVERY_VALIDATION_20261020.md)取代；不要再按该旧段要求启动或诊断。当前Docker/Orthanc分别通过健康检查和PACS元数据查询，但像素读取仍关闭。
## 2026-10-17 S3 runtime 配置v2

`runtime.json`版本1保留原八个路径；版本2在同一受限解析器中增加PACS配置、导入登记/作业目录、本地账户文件和DICOM转换索引共五个路径键。`start_local.ps1`复用同一映射，把全部13个键传入后端并登记以支持精确复用比较。仅有路径不代表配置内容可恢复：PACS凭据、导入回执、账户哈希和转换索引仍需从私有恢复包按既有流程另行还原。旧v1可继续读，但在新部署中未显式提供v2键时仍使用应用默认值；新组合/实际重启验收尚未完成。

## 2026-10-17 独立后台启动与状态检查

[紧急修复及验证](URGENT_FIXES_20261017.md)：原三个启动脚本现通过同用户本地后台创建机制运行，保留实际服务PID/启动时间、环境与日志；不会依赖开发任务清理组存活。没有新增Windows计划或系统服务，也没有自动重启。已有start/stop/reuse调用入口继续使用，实际启停仍放在有限同步开发锁步骤中。缺pydicom会在业务库初始化前明确失败，使用既有受支持环境或独立候选，不升级主CUDA。

只读检查当前三服务、端口、HTTP/PACS及账户：`./backend/tools/status_local.ps1`，健康退出0、未就绪退出2；该入口不修改数据或启停服务。服务不再随开发聊天退出，需要停机时显式调用原停止脚本。长时观察看Runtime/local/service-observer.json当前身份/截止和实际输出，旧running元信息不能代替进程存在；退出历史与跨夜稳定结论以新证据为准。

## 2026-10-16 15:38当前服务恢复与退出诊断

[当前恢复/导航验收](LOCAL_SERVICE_RECOVERY_VALIDATION.md)：后台25128/前端14984/Orthanc21924恢复原8012/5179/8042与原数据，账户/PACS保护保持。旧15:30未运行是当时事实；本时点健康也不能保证永久存活。未来先保存日志/登记，按实际句柄/PID启动时间/监听核对再正常启动，不删锁、不盲重启。

新增只读有限watch_local_service_exits.ps1按JSON内精确name/pid/started_utc观察退出码，输出限E盘nightly新子目录，默认2小时、最大6小时；不启停目标、不写业务或持开发锁。现有本轮观测登记和截止见最新NIGHTLY_HANDOFF，未结束不重复开。其0/23/身份/到期边界已实际验收；退出码不等于终止者。人工演示从/cases正常详情进，错误链接明确返回管理，避免残留旧患者。现有配置/密码不贴到浏览器或日志。


2026-10-16 08:13：新增[直接CPU与固定PACS模块目录的本机运行组合](E6_CPU_PACS_LIVE_VALIDATION.md)已实际首启/复用/重启/浏览器/回原。用`-PythonPath <直接CPU基解释器>`并显式`-PacsRuntimeLayer <已登记补充目录>`，venv重定向入口继续拒绝；这不是新机安装，当前正式服务已回CUDA。所有切换/回原仍由有限同步工作脚本执行，不在已有端口叠起服务。

## 2026-10-16 当前启动/复用约定

当前实际地址仍5179/8012，Orthanc8042仅本机有鉴权。[当前交付范围](RELEASE_SCOPE.md)已含受支持成组DICOM与本地复核账户；下方10/10及以前端口/PID/Demo方式是历史，不能据此把当前服务切回旧库或称当前不支持PACS。

所有实际启停/复用放在有限同步包装器的工作脚本内。已在本轮实际核对的只读复用脚本是 `E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T041517_viewperf/reuse-existing.ps1`，包装器调用为：

```powershell
pwsh -NoProfile -File E:/BrainFusion-AI/backend/tools/run_development_step.ps1 -RunId manual.reuse-current -ScriptPath E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T041517_viewperf/reuse-existing.ps1
```

该脚本锁内重新核对当前八路径，显式给出三PACS路径和LOCAL_AUTH_FILE，然后调用start_local的ReuseExisting；实际核对原PID不变/未起第二服务，见reuse-existing-validation.json。仅适用于当前已登记服务/配置；状态已变化则明确拒绝，不据此启动新的部署。不要调用退役后台holder。

重新部署还须正常配置原八路径、上述四额外配置及模型/特征门槛，先备份再在副本验证；空环境变量不是缺省配置。现有nightly目录仍为运行依赖，不能清理。Docker/异机/完整新账户多病例包的待验状态见清单，不用旧环境包冒充当前可安装系统。

08:11独立特征worker引导见RADIOMICS_DELIVERY_BOOTSTRAP；最终radiomics311-delivery-20261010T081105_95f1c109-independent新prefix自身pip/20Conda/11wheel/15包/1102导入文件已验，不借旧工程pip/原worker目录。新来源尚无绑定科学gate，不直接替换当前RADIOMICS_PYTHON/旧gate身份，5179/8012服务仍原配置。

项目 E:/BrainFusion-AI，数据 E:/BrainFusion-Data，模型、缓存和运行证据 E:/BrainFusion-Runtime。不要在默认 C 盘工作树执行安装、推理、构建。

2026-10-10最新：E3应用快照恢复与E4本机受支持CPU环境已验收；当前服务使用20261010T010640_a6ee8135/runtime-supported.json，独立Python3.11.17。主CUDA不变；上一轮relocated-runtime仍提供模型/上传/研究/数据，不可删除。范围和复建见SYSTEM_BACKUP_RESTORE、RADIOMICS_ENVIRONMENT_MIGRATION；固定演示见FIXED_DEMO_GUIDE。下方Demo/单库方式是历史，不切当前服务回旧库。

```powershell
cd E:/BrainFusion-AI
./backend/tools/start_local.ps1 -ReuseExisting -RuntimeConfig E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T010640_a6ee8135/runtime-supported.json -BackendPort 8012 -FrontendPort 5179
```

停机后去掉-ReuseExisting启动同一配置；不改为-Demo而误开旧演示库。当前前端5179、API8012，精确PID/启动时间以Runtime/local/processes.json及最新交接为准。

04:12新增源码/工程材料/CPU安装来源与现用环境联合核验工具，调用和安装迁移组成见LOCAL_DELIVERY_ACCEPTANCE。它不新建患者、不启动推理/提取、不安装升级主环境，成功状态仅已有本机，不把旧源码包或版本快照当开箱新机部署。

## 启动

2026-10-09新增副本数据库启动：先执行 `backend/tools/snapshot_database.py --source <E盘源数据库> --output <不存在的E盘备份目录>`，保存snapshot.db并验证restored-validation.db完整性和表行数，再启动 `./backend/tools/start_local.ps1 -DatabasePath <恢复副本绝对路径> -BackendPort 8012 -FrontendPort 5179`。`-DatabasePath`与`-Demo`互斥；不覆盖已有数据库。此工具目前仅备份数据库，不复制其引用的MRI/模型/产物，不能作为完整离线迁移验收。

最新保留服务使用本轮隔离恢复副本，具体路径及PID见NIGHTLY_HANDOFF.md/Runtime/local/processes.json。已有服务直接使用；2026-10-09 23:03轮新增显式复用：`./backend/tools/start_local.ps1 -ReuseExisting -BackendPort 8012 -FrontendPort 5179 -DatabasePath <登记的恢复副本路径>`。核对登记PID与启动时间、应用命令、两个端口的真实持有者及后前端健康；成功不另起进程，不改登记记录。指定的端口/数据库不一致、身份不可信或健康失败立即停止，不接管其他进程。无登记服务时请先普通启动；不带-ReuseExisting仍拒绝重复启动。实际复用和三种拒绝场景已验证，详见e3-service-reuse证据。本轮副本新增case_research_inputs表；正式原库尚未执行该新增表迁移。

PowerShell 执行：

```powershell
cd E:/BrainFusion-AI
./backend/tools/start_local.ps1 -Demo
```

前端 http://127.0.0.1:5173，接口 http://127.0.0.1:8000/docs。`-Demo` 使用五例工程演示数据库；去掉该选项使用独立的新数据库。端口冲突或已有登记后端时脚本停止，不关闭其他进程。服务健康检查通过后才报告启动成功。隐藏窗口运行，进程号和日志写入 E:/BrainFusion-Runtime/local；等待当前分析完成后使用 `./backend/tools/stop_local.ps1` 关闭，脚本核对 PID 和启动时间。

分析页从病例详情“AI 分析”进入：上传四个已配准 1 mm NIfTI 序列，启动真实分割，完成后进入病例阅片，点击“AI分割叠加”，核对结果，再确认当前版本、打开报告并导出 PDF。

## 验证

下方全流程/研究重跑工具会实际追加工程记录/推理，属于历史全流程入口，不是每轮健康检查。当前已验收链路不用重复执行；日常复用/前检，单元与构建在隔离数据库验证。依赖清单角色见ENVIRONMENT_INVENTORY，源码候选边界见SOURCE_DELIVERY。

```powershell
cd E:/BrainFusion-AI/backend
. ./tools/use_e_drive.ps1
../.conda/brainfusion/python.exe -m pytest -q -p no:cacheprovider
../.conda/brainfusion/python.exe tools/verify_core_workflow.py
../.conda/brainfusion/python.exe tools/verify_research_workflow.py
cd ../frontend
npm run build
```

浏览器完整验证工具 `frontend/tools/verify_core_browser.mjs` 当前使用验证服务端口 8011/5178，后端数据库指定为 E:/BrainFusion-Runtime/results/stage2/workflow.db。它会使用下载好的四序列上传并实际再次推理，创建工程标注、确认工程结果、导出 PDF，不应指向真实患者数据库。

## 依赖与显存

本机 Python：E:/BrainFusion-AI/.conda/brainfusion/python.exe。CUDA torch 2.11.0+cu128 已运行通过，保持已有 torch，不用全量 requirements.txt 升级环境。MONAI 1.5.2、scipy 1.15.3；研究/测试依赖见 requirements-research.txt。所有操作前先 dot-source use_e_drive.ps1 重定向临时目录与缓存到 E 盘。

单服务进程、单推理 worker、滑窗 batch=1，CPU 输入和拼接输出，GPU 分配预算默认 6000 MB。空闲显存少于 3 GB 时直接 CPU；CUDA OOM 时单次 CPU 重试并记录原因。本次只有 CPU 轻量研究拟合，无 GPU/大型训练。不要同时启动其他训练任务；实际显卡占用需同时查看 nvidia-smi，PyTorch 分配峰值不是全卡使用量。

当前模型仅支持已配准、1 mm、正交三维 MRI；自动配准、斜切重采样、DICOM 序列导入尚未实现。

## 历史 Docker 状态快照（2026-10-10；已由顶部 2026-10-20 Compose 记录覆盖）

05:08窗口新增可选Windows CPU主环境（Python3.11.17/torch2.11.0+cpu），独立安装/同模型CPU对照/副本恢复及实际服务重启、浏览器/回退通过。`start_local.ps1 -PythonPath <E盘python.exe>`可指定主解释器；默认不变，`-ReuseExisting`严格核对实际解释器，不自动切换或停止服务。所有试运行先备份、无活动任务、使用新数据库/任务副本。当前演示已回退CUDA主环境及01:06原配置；操作与完整来源锁见CPU_RUNTIME_CANDIDATE。新候选不包含PyRadiomics，独立特征工作器配置保持原门槛。

06:06补独立离线引导见CPU_DELIVERY_BOOTSTRAP：内部源码/来源锁包与外部可信SHA、E盘可信Conda/已核验缓存，fresh prefix中重建52项CPU主依赖，不借旧工程pip、不启停服务、不自动覆盖/切换默认。模型/数据/兼容工作器与Node必须分别准备。前端原镜像锁422项官方元信息/SRI预检保留npm别名，只外部候选resolved改变、未下载安装；不能对指向原node_modules的测试联接执行npm ci，后续必须全新独立目录。

已补模型、研究、数据只读挂载，uploads 和 SQLite 持久化，推理工具复制与 CPU/研究依赖。2026-10-10只读实查WSL未安装、Docker PATH/标准目录未发现、当前非管理员；E5受阻，不是构建或容器验收。当前用户已授权必要官方安装/配置，但首次WSL需要管理员启用/可能重启，须用户系统授权窗口；不绕过授权或自动重启。镜像/WSL数据/缓存先配置E盘，不在长任务期间重启。E4还须受支持Linux工作器与同协议契约。解除条件与官方参数见DOCKER_PREREQUISITES。当前本机GPU路径已验证，Docker配置仅待实测CPU路径。`MODEL_HOST_DIR`、`RESEARCH_HOST_DIR`、`DATASET_HOST_DIR`可覆盖宿主目录。

## 最新前端环境/服务增量（07:05）

独立Node24.21.0/npm11.19.0官方SHA与396实际包SRI安装、明确8012 API构建、真实HTTP初启/前端重启各四页浏览器通过，已恢复原开发前端8912（UTC23:22:16.1822222Z），后端31840保持UTC21:30:04.2527517Z；地址仍5179/8012。FrontendOnly启动/停止只处理核验身份的前端，不默认切换Node/源码或重启后端；日志必须全新nightly目录，旧17736不能沿用。源码/镜像锁不改，数据版本不变。操作、失败/回退与局限见FRONTEND_DELIVERY；此后章节为对应历史窗口，不替代当前runtime-supported.json。

## 本次保留的演示服务（历史10/06）

2026-10-06 停机/重启验收后保留前端 http://127.0.0.1:5179 和 API http://127.0.0.1:8012/docs，使用工程演示数据库。进程退出后端口会关闭，可使用 `start_local.ps1 -Demo -BackendPort 8012 -FrontendPort 5179` 重新启动；若仍在运行则直接访问。验证专用的 8011/5178 服务已关闭。研究页面 http://127.0.0.1:5179/research，具体操作见 RESEARCH_OPERATION_GUIDE.md。

运行 `verify_core_workflow.py` 前先关闭演示服务，避免两个后端共享 workflow.db。pytest 已使用自有临时库，与演示库隔离；所有测试前仍应运行 use_e_drive.ps1。

## 当前病例自动特征（10/07）

分割完成页点击“自动掩膜特征研究”，或在 /research 选择已分析病例。当前独立CPU工作器E:/BrainFusion-Runtime/envs/radiomics311-candidate，门槛和任务目录由上述runtime-supported.json指定。radiomics39、stage6/compatibility.json、results/feature_jobs是归档环境/旧默认，不能混同当前配置。配置RADIOMICS_PYTHON、RADIOMICS_COMPATIBILITY、FEATURE_JOBS_DIR必须同版本通过门槛。

新环境使用 tools/setup_radiomics_worker.py 和 tools/verify_feature_extraction.py；五例接口 tools/verify_automatic_features.py；页面 frontend/tools/verify_automatic_features_browser.mjs；重启 tools/verify_feature_persistence.py。详细执行顺序见 AUTOMATIC_FEATURE_OPERATION_GUIDE.md。Windows 本机已验收，Docker 不包含该归档兼容工作器。


## 准备转换任务后从病例页启动（2026-10-18）

使用已核对的同检查四序列proposal、快照及原文件清单运行转换工具时，可加`--prepare-only`，仅生成持久化queued任务；其余原有`--proposal`、`--snapshots`、`--source-files`、`--output-dir`参数仍必需。需要转换完成后进入审核列表时显式指定`--register-version-id`。不加prepare-only仍创建并同步执行；准备和转换都不自动激活MRI或推理。

在对应病例详情的“本地DICOM归档→转换作业”刷新后，等待执行项显示“启动转换”；点击后需要本地医生账户。失败/中断项使用“重新排队”，不会覆盖旧输入。成功但未登记的转换明确显示未登记，不能当作角色审核通过。API仅接受服务端作业ID和expected_attempt；不接收客户端本机路径。

当前真实作业列表为空时应显示暂无准备好的任务；不为演示添加合成记录到正式账本。尚不支持在网页直接选择四序列创建proposal。真实来源/共同网格/原字节审核仍需逐项验证。

## 2026-10-18 网页创建DICOM转换作业

病例详情的“本地DICOM归档→转换作业→创建转换方案”提供同一关联检查的序列选择。请按采集记录或公开协议逐一确认T1c/T1n/T2w/FLAIR，不要按序列名称自动猜测；证据栏只能填不含患者信息的短编号。先点“检查转换方案”，系统会核对病例归档关联和空间；确认后点“创建转换任务”，服务器再核验并保存当前归档原始DICOM字节，建立待执行作业。创建完成后还须在作业列表登录本地医生账户并显式“启动转换”。转换成功不等于角色审核或AI激活；需后续单独审核/激活，且本功能本身不运行模型。

浏览器不得提供服务器路径。当前归档实测只有1检查/1序列，无法实际创建四序列作业；只有获得合法、同一检查且四序列空间受支持的资料后才能完成真实验收。若来源改变、原件缺失、文件不匹配或账户/归档核验失败，页面会拒绝创建/启动并要求重新核对；普通DICOM阅片与现有NIfTI不受影响。



