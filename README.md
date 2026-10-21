# BrainFusion AI

当前新增[直接CPU/PACS HTTP组合验收](docs/E6_CPU_PACS_LIVE_VALIDATION.md)：真实两来源阅片、既有账户/来源结果、服务复用/重启/正常停机与回正式路径已验。它使用原CPU基环境和固定pydicom补充目录，源码按冻结ZIP及增量对应；不是独立新机/容器或真实DICOM四序列AI验收。下方各旧窗口按日期保留。

当前源码候选的白名单、PACS/账户/图稿组成及生成/验收边界见[源码交付](docs/SOURCE_DELIVERY.md)。完整数据恢复与源码/环境安装是分别验收的组成；第一阶段整体仍未完成。

当前[含账户19病例完整数据组合](docs/E6_FULL_ACCOUNT_RECOVERY_VALIDATION.md)已实际备份/恢复、启动两种来源并重启验证，正式数据保持。此组合含模型/研究/产物及私有账户，不是源码/二进制/环境安装包；当前源码交付候选及P3真实四序列/E5条件仍待完成，系统整体未交付。以下按日期保留历史。

[当前范围与浏览器矩阵](docs/RELEASE_SCOPE.md)已按PACS/Cornerstone/本地账户实证重整；[分层性能记录](docs/P4_VIEWER_PERFORMANCE_VALIDATION.md)补真实两来源开发服务初载/交互与进程内存。均为有限本机证据；完整交付及真实四序列DICOM模型桥/最终部署尚未完成。下方窗口保留历史，不以旧“PACS排除”或未验描述覆盖当前状态。

当前新增[Edge NIfTI保存/关闭恢复](docs/P4_EDGE_NIFTI_VALIDATION.md)及[两张架构/关系SVG与PNG](docs/E6_ARCHITECTURE_FIGURES.md)：前者仅副本完成三平面距离/四序列与视图恢复，后者按当前源码/实际边界导出并查看。原正式数据与影像保持；P4/E6整体及P3真实四序列/E5部署条件未全完成。下面各窗口按日期保留。

新增[Edge保存与关闭恢复验收](docs/P4_EDGE_PERSISTENCE_VALIDATION.md)：真实DICOM账户复核、三页身份PDF逐页查看、测量/三视图保存及浏览器关闭恢复通过，仅写隔离副本。Edge NIfTI落库/关闭恢复和最终部署仍待验；P3真实四序列桥/E5系统授权受阻，第一阶段整体未完成。下方窗口记录按各自日期保留。

当前新增[账户DICOM最小联合恢复](docs/P4_JOINT_ACCOUNT_RECOVERY_VALIDATION.md)及[已装Edge只读验收](docs/P4_EDGE_READONLY_VALIDATION.md)：自动账户收录/恢复/来源历史与重启已实际跑通，声明空运行目录恢复缺失已修复。最小组合不代替完整多病例/模型包；Edge只读不代替落库/PDF。第一阶段仍未整体交付。

P2在已登记公开CC BY4.0、受支持经典MR的本机受控准备/导入范围已验收：[来源绑定v2真实导入](docs/P2_V2_REAL_IMPORT_VALIDATION.md)新增192实例/全部回读、明确病例关联、三视图及重启通过；不包含任意DICOM上传、自动像素脱敏或四序列AI。账户快照工具/联合收录代码新增，组件已验，完整新版bundle恢复仍待验证。原数据/归档保持，第一阶段整体尚未完成。

当前DICOM人工复核新增本地账户登录与角色限制，历史自行署名仍标未认证。正式页两账户已配置，密码仅在本机私有文件；见[账户操作](docs/LOCAL_REVIEW_ACCOUNTS.md)和[当前验收](docs/P4_LOCAL_REVIEW_IDENTITY_VALIDATION.md)。原17表/八路径不变；匿名普通阅片继续可用。账户配置是联合备份之外的新补充文件，不能遗漏。下方旧窗口记录保留为历史。

## 当前可演示范围（2026-10-18）

现有Vue 3、FastAPI、SQLite系统可运行既有四序列NIfTI分割/研究流程；受控DICOM阅片已接入本机Orthanc、DICOMweb和Cornerstone三视图，支持测量、视图状态、本地账户复核、分析版本历史及PDF。完整数据组合和当前源码候选均已在本机做过有限恢复/交付核验；源码、数据、依赖环境是分开的交付部分，系统整体尚未完成。

病例PACS页已提供受控的四角色序列选择、几何预览、从固定归档捕获原始DICOM并创建持久转换作业入口。该页面交互和隔离工程用例通过，但本机真实PACS目前只有1项检查/1条序列，真实四序列获取、转换、角色审核、激活及由DICOM来源启动AI仍未验收。公开ReMIND候选的部分DICOM缺少BurnedInAnnotation字段；你对本轮展示的四张图中104层切片暂时无法确认，且答复未指定具体Study/Series UID，因此当前候选均未导入、转换或推理。ACRIN-134只可作非胶质瘤影像工程候选，不作效能验证。

普通DICOM阅片不要求IDH标签或四序列齐备；不能把既有NIfTI病例的模型结果填入DICOM病例。Docker/异机部署、完整新机安装、真实四序列到AI闭环以及用户带教和正式演示仍待完成。演示先看[固定流程](docs/FIXED_DEMO_GUIDE.md)，架构及逻辑边界见[当前架构](docs/SYSTEM_ARCHITECTURE_CURRENT.md)，最新工作边界看[系统台账](docs/SYSTEM_COMPLETION_CHECKLIST.md)与[交接](docs/NIGHTLY_HANDOFF.md)。所有开发、测试和服务切换仍按有限同步步骤执行。

## 2026-10-13 06:10窗口（对应10/12夜至10/13清晨）

run_id 20261013T061054_a3334597；FileStream FileShare.None实际持有者/owner15416，原生启动UTC2026-10-12T22:10:53.6629913Z，开始UTC22:10:54.2786787Z/北京06:10:54，session15354；结束/实际耗时/正常释放见summary/lock-released。无新反馈，不编造REVIEW_FEEDBACK；保护现有大量工作树变更，不提交/推送/发布。

P3-a来源/四角色声明规划与P3-b1轻量转换工程已验，287相关检查、实际GDCM合成原字节→NIfTI全72体素/毫米/哈希核对。模型输入未激活，真实匹配DICOM四序列仍受阻。共享头部检查保持旧空间契约并避免读入像素，原真实NIfTI/原14表/SHA回归通过；补HTTPX核心声明，无安装/前端构建/整包重制。详见docs/P3_DICOM_INPUT_CONVERSION_VALIDATION.md。


## 以下为之前窗口的历史记录
## 2026-10-13 05:14窗口（对应10/12夜至10/13凌晨）

run_id 20261013T051455_f13472c8；实际FileStream FileShare.None持有者/owner27576，原生启动UTC2026-10-12T21:14:54.7780683Z，开始UTC21:14:55.4033991Z/北京05:14:55，session74715。结束、实际耗时与正常释放见本run summary/lock-released。无新反馈，不编造REVIEW_FEEDBACK；保护既有工作树，不提交/推送/发布。

成组DICOM已接现有Cornerstone工作站并完成合成工程验证：214后端、6912像素/斜位毫米/工具数值、开发与生产、局部帧失败和清理。实际PACS仍未配置，真实DICOM及P3/P4没有通过。重启后原NIfTI/14表全行与产物SHA不变，无新依赖或推理；详见docs/P2_DICOM_VIEWER_VALIDATION.md，旧包仍历史。


## 以下为之前窗口的历史记录
## 2026-10-13 04:17窗口（10/12夜至10/13凌晨）

run_id 20261013T041702_3ff437ba；开始/原生锁PID精确值见lock-acquired.json，实际FileShare.None持有、session30030；结束/耗时/正常释放见summary/lock-released。无新反馈，不改REVIEW_FEEDBACK；不提交/发布。

成组DICOM空间/物理排序契约与现有归档面板核对工程已验（207相关检查、开发及实际生产预览），修复刷新失败旧结果清理；实际PACS仍未配置、新DICOM像素入口待P2-c2。实际服务已按备份/身份脚本重载、原NIfTI三canvas和数据全行/SHA不变，无依赖安装/模型任务/整包重制。详见docs/P2_DICOM_SERIES_VALIDATION.md，旧包仍历史。

## 以下为之前窗口的历史记录
## 2026-10-13 03:18窗口（10/12夜至10/13凌晨）

run_id 20261013T031824_36706fc0；FileShare.None实际持有者/owner25212、原生UTC2026-10-12T19:18:23.8712271Z、开始UTC19:18:24.482057Z、session90335；结束/耗时/正常释放见summary/lock-released。无新反馈，不改REVIEW_FEEDBACK，不提交/发布。

新增只读PACS核对CLI及可选服务pin工程已验，184相关检查；真实PACS仍未配置，现后端未重载新pin，未宣称归档/真实DICOM阅片通过。原文件、业务库、依赖不变；加工MR小样例仅工程资料。完整边界、证据、抽查见 docs/P2_PACS_RECONCILIATION_VALIDATION.md，旧交付包仍历史，不重新打包。

## 以下为之前窗口的历史记录
## 2026-10-13 02:15窗口（10/12夜至10/13凌晨）

run_id 20261013T021550_d6134bcb；操作系统 UTC 与原生锁进程启动值见 lock-acquired.json，FileShare.None holder/owner18708，session75448；结束/耗时/释放见 summary.json。P2-b3隔离保管工程已验收，P2整体仍进行中、P2-env受阻，P1受支持NIfTI已验收，P3/P4待实施；历史F/E验收保留，E5受阻/E6进行中、R1待核查/R2–R4待实施。无新用户反馈，不改 REVIEW_FEEDBACK，不提交/发布。

新增隔离候选保管/UID冲突/收据/备份恢复工程已验（147相关检查），实际PACS归档未通过。工具、边界、证据及抽查见 docs/P2_DICOM_CUSTODY_VALIDATION.md；无API/前端/依赖/模型变化，旧交付包仍为历史，未重新打包。

## 以下为之前窗口的历史记录
2026-10-13 01:19当前：[递归DICOM只读预检](docs/P2_DICOM_PREFLIGHT_VALIDATION.md)新增来源/哈希/嵌套标签/像素后属性及明确拒绝报告，134检查通过。只安装必要官方pydicom3.0.2，既有数据/CUDA/服务保持；工具不改写或直接授权归档。真实PACS/脱敏导入/DICOM阅片和P3/P4仍未验，当前5179/8012。

## 以下为之前窗口的历史记录

2026-10-13当前：[WADO工程与真实DICOM候选核查](docs/P2_WADO_VALIDATION.md)。受限单帧MR metadata/frame契约已验，像素默认关闭；官方一个DICOM候选已取得且UID/SHA可追溯，实际MOSAIC/private/烧录待核，未入库。实际Orthanc/DICOM阅片/四序列AI桥接仍未验。原NIfTI保持可用、当前5179/8012。

## 以下为之前窗口的历史记录

2026-10-12 23:25当前：[本地归档读取与病例关联工程验收](docs/P2_READ_PROXY_VALIDATION.md)。既有病例详情新增归档状态/层级清单/明确核对关联；后台凭据隔离、重复/冲突保护。**实际PACS未部署、真实DICOM/导入/阅片/AI桥接尚未验收**，当前页面明确未配置。原NIfTI Cornerstone已验成果保持。当前5179/8012；构建必须明确实际VITE_API_BASE，勿把旧默认8000当当前地址。

## 以下为之前窗口的历史记录

2026-10-12当前：[Cornerstone NIfTI路径已验收](docs/P1_MEASUREMENT_VIEW_VALIDATION.md)，支持三视图/四序列、只读真实mask、毫米距离测量保存/刷新/重启/删除、显式视图保存恢复、方向标记和病例切换清理。打开http://127.0.0.1:5179/workstation/17选择Cornerstone；Canvas保留兼容入口。PACS/DICOM与最终集成仍待完成，P2官方Windows环境动作受自动审批限制，未部署归档。当前PID/日志以docs/NIGHTLY_HANDOFF为准，下面旧交付增量为历史。

08:11交付增量：独立受支持特征worker标准库/新prefix自身pip离线引导、20Conda/11wheel SHA和15包/1102导入文件匹配，120后端通过/4既有警告；默认安装不借旧工程pip或要求原worker存续。现用来源/科学gate/服务不变，新来源部署门槛尚未验。CPU主/Node/worker/合法数据恢复组成见docs/RADIOMICS_DELIVERY_BOOTSTRAP.md，不宣布完整交付。

脑胶质瘤 AI 辅助诊疗平台（教学 / 科研原型系统 · v0.1.0）

07:05窗口补[独立前端环境与构建交付](docs/FRONTEND_DELIVERY.md)：官方Node便携发行与422项固定来源候选实际安装396项、26可选跳过，396缓存文件SRI/身份/来源吻合。全新目录禁安装脚本，明确绑定实际8012 API构建；真实HTTP单前端预览/重启各四页浏览器通过后恢复开发前端，后端未重启。当前前端8912/后端31840、5179/8012；原源码/镜像锁/数据库保持，不混同历史17736。CPU主/特征协议/研究结论不变，E5受阻与E6整项未完成。

06:06窗口新增[CPU源码/来源锁迁移包与离线引导](docs/CPU_DELIVERY_BOOTSTRAP.md)：独立标准库入口不借用旧工程pip，从已核验的20项Conda/52轮子缓存实际重建全新E盘CPU环境；安装元信息/52来源报告、原树与独立解包副本后端测试、只读前检通过。现用CUDA/特征工作器/服务不切换，迁移包不含MRI、模型、数据库、第三方二进制或Node依赖，不冒称异机/完整部署验收。前端原422项镜像锁保留；官方元信息/SRI逐项预检及明确npm别名已核对，候选仅在证据目录替换resolved地址，未下载或安装前端依赖。E5受阻、E6整项仍进行中。

> 当前实际链路：患者/病例 → 同患者四序列MRI → 真实MONAI分割 → 阅片/测量 → 自动掩膜特征与IDH研究预测/融合 → 医生复核/独立意见 → 报告/PDF → 保存和恢复。研究概率不是通用风险、肿瘤检测概率或治疗建议；未解决IDH编码时按原始目标值=1描述。
>
> **本系统为教学与原型工具，所有 AI 结果仅供演示与科研参考，不构成临床诊断或治疗建议，请以具有执业资质的医生阅片意见为准。**

2026-10-10：系统任务F1–F6、E1/E2/E3/E4已验收；E5实际Docker和E6最终交付仍未完成，R1–R4完整研究未完成。01:06窗口独立CPU特征环境迁至Python3.11.17，原协议/模型不变，五参考特征/概率及病例17实际自动任务/重启/缓存复现通过。02:07窗口源码候选白名单/编码/有限凭据检查与逐文件打包解包通过；78后端、2基础浏览器、构建及638原件审计通过。源包不含数据/模型/环境/依赖，不是开箱部署版；历史requirements.txt不是当前环境锁。主CUDA环境未升级，本窗口未新分割/提特征/训练/导出PDF。见[系统台账](docs/SYSTEM_COMPLETION_CHECKLIST.md)、[交接](docs/NIGHTLY_HANDOFF.md)、[固定演示](docs/FIXED_DEMO_GUIDE.md)、[实际交付范围](docs/RELEASE_SCOPE.md)。

03:09窗口新增[毕业论文工程材料说明](docs/THESIS_ENGINEERING_MATERIALS.md)：两张可编辑系统架构/版本谱系图、四张既有病例真实页面截图、中文图注与来源/哈希清单。图表与PDF逐项视觉/文字/碰撞检查通过，78后端回归通过；当前病例、原数据库/638文件、主环境与服务保持不变，没有新病例分割/特征提取/报告PDF。本轮不重跑已通过的前端构建；02:07源码ZIP是冻结的历史候选，不包含本轮新工具。E6材料小批次通过，不等于完整论文、容器或新机器安装验收。

## 一、功能特性

04:12窗口补[本地交付联合核验](docs/LOCAL_DELIVERY_ACCEPTANCE.md)：可执行检查源码/材料版本、CPU依赖锁/轮子和现用启动前检，并记录数据库前后相同。成功仅表示已有本机环境可用，不冒称新机器安装/Docker通过；历史候选与新增源码严格分开。工程论文图表素材已验收，完整研究论文仍需R1–R4证据，不将其误设为第一阶段系统功能的额外门槛。

| 模块 | 能力 |
|------|------|
| 病例 / 患者管理 | 增删改查、搜索、状态筛选 |
| MRI 影像阅片 | NIfTI 上传、三视图（轴/冠/矢）、真实窗宽窗位（基于体素强度）、Crosshair 同步、缩放平移、PACS 四角信息叠加、方位标记（A/P/L/R/S/I）、键盘快捷键（方向键切层/Esc 取消） |
| 独立阅片工作站 | 全屏阅片（患者信息栏、MRI体素强度、单/三视图布局、/workstation/:id）；不是PACS服务 |
| 医生标注 | 点 / 矩形·椭圆·圆形 ROI / 测距 / 双向测量 / 角度 / 自由绘制 / 探针 / 文字，五类标注自动配色，体素坐标，删除单个 / 全部 |
| AI 分析 | 固定官方MONAI BraTS SegResNet真实分割；排队/运行/成功/失败/重试与保存版本 |
| 诊断报告 | 当前真实分割体积、模型/分析版本、医生独立意见与确认、PDF；失效结果拒绝新导出，不生成治疗建议或LLM报告 |
| AI 分割叠加 | 当前真实模型mask、四序列T1c/T1n/T2w/FLAIR、三视图/物理位置/方向一致；不自动配准或重采样 |
| 默认阅片 | 服务器真实体素切片；安装的Cornerstone依赖不等于高级渲染已验收 |
| 自动掩膜影像组学与IDH研究 | 独立CPU PyRadiomics，20个模型选中特征、年龄/性别病例版本、Logistic Regression、平均/固定/TOPSIS；参考模型自动输入迁移尚未队列重拟合 |
| 保存与恢复 | 可重定位路径、启动前检、安全复用、SQLite/引用产物校验快照及副本恢复；环境迁移/Docker另行验收 |

## 二、技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue3 + Vite + Element Plus + Pinia + Vue Router + Axios |
| 后端 | FastAPI + SQLAlchemy + SQLite + Pydantic |
| 医学影像 | NIfTI + SimpleITK + NumPy + Pillow |
| AI | 实际PyTorch/MONAI SegResNet；CPU PyRadiomics/Scikit-learn；不使用旧占位MRI/0.78风险/生存入口 |
| 部署 | 本机隐藏启动/前检/健康/PID保护已验收；Docker Linux 前后端镜像已构建、隔离 HTTP 冒烟通过；Compose 持久化、Linux影像组学工作器、PACS与真实数据验收仍未完成 |

## 三、系统架构

```text
用户 → 病例管理 → MRI 上传 → 影像解析 → 阅片工作站 → AI 模型分析 → 结果融合 → 报告生成 → 医生确认 → 病例归档
```

```text
frontend (Vue3)                    backend (FastAPI)
  views / components                api/      → HTTP 接口
  stores (Pinia)                    services/ → 业务逻辑
  api (Axios)                       models/   → 数据模型 (SQLAlchemy)
         │                          schemas/  → 请求/响应 (Pydantic)
         │  统一信封 {code,message,data}   core/ → 配置/日志/异常
         └────────── HTTP ─────────→ ai/      → 可插拔 AI 接口
                                     utils/    → 公共函数

                               SQLite (brainfusion.db)
```

## 四、目录结构

```text
backend/
  app/{api,services,models,schemas,core,ai,utils}
  tests/           # pytest 接口测试
  requirements.txt          # 历史扩展清单，不是当前环境锁
  requirements-local-validated.txt # 本机观测直接依赖摘要，CUDA/CPU worker分开
  requirements-core.txt     # Web 服务核心依赖
  Dockerfile
frontend/
  src/{views,components,stores,api,router}
  Dockerfile / nginx.conf
docker-compose.yml
docs/
```

## 五、快速开始（安装运行）

### 1. 已配置本机启动

```powershell
cd E:/BrainFusion-AI
# 当前服务已运行时只复用；不启动第二服务：
./backend/tools/start_local.ps1 -ReuseExisting -RuntimeConfig E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T010640_a6ee8135/runtime-supported.json -BackendPort 8012 -FrontendPort 5179
# 停机后去掉-ReuseExisting，仍使用同一个runtime.json启动。
```

保持现有主Python/CUDA环境，不为安装成功全量升级历史requirements.txt。新机器需要模型/研究数据/工作器与独立环境，单装Web核心依赖不等于真实分割已就绪。实测版本/未知来源与各清单角色见[环境清单](docs/ENVIRONMENT_INVENTORY.md)，内部源码候选范围见[源码交付](docs/SOURCE_DELIVERY.md)。启动/恢复/特征环境见[本机指南](docs/LOCAL_RUN.md)、[备份恢复](docs/SYSTEM_BACKUP_RESTORE.md)、[特征迁移](docs/RADIOMICS_ENVIRONMENT_MIGRATION.md)。文件/模型/缓存保留E盘。

当前前端 http://127.0.0.1:5179 ，API http://127.0.0.1:8012/docs；其他配置启动的实际地址以进程登记与启动输出为准。

### 2. 数据保护

启动脚本同时管理一个后端、一个前端，核对实际端口和进程启动时间；不误杀用户进程。备份与迁移先在副本验证，原MRI/数据库/成功产物不清理。当前使用明确工程恢复副本，而不是原患者库；本轮没有提交或推送。

## 六、使用指南（操作步骤）

### 第一步：启动系统

按上方脚本启动/复用，打开 http://127.0.0.1:5179；当前可抽查病例17，病例18仅同一公开患者的工程副本，不能计为新独立研究患者。

### 第二步：完整诊疗流程

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| 1 | 病例管理→创建病例→姓名/年龄/性别/描述 | 同时创建关联患者和病例，不先重复创建患者 |
| 2 | 患者管理核对资料，或打开既有病例 | API支持patient_id关联；当前创建页面没有既有患者选择控件 |
| 3 | 病例「AI分析」→ 上传同患者四个配准1mm正交3D NIfTI：T1c/T1n/T2w/FLAIR | 序列明确；缺失/非法/错网格具体提示；单文件上传仅供阅片 |
| 4 | 病例详情「MRI 影像信息」 | 状态显示「阅片就绪」 |
| 5 | 「MRI 影像浏览」区 | 三视图显示，可切层/滚轮/缩放平移 |
| 6 | 底部「窗宽/窗位」滑块或「窗宽窗位」工具拖拽 | 灰度按体素强度实时变化 |
| 7 | 工具栏选「标记点/矩形ROI/测距/角度/自由ROI/文字」并在图上绘制 | 图上出现对应图形 |
| 8 | 「保存标注」→ 刷新页面 | 标注重新出现（持久化） |
| 9 | 标注列表「删除」或「删除全部」（二次确认） | 标注被移除，刷新后不再回显 |
| 10 | 「AI分析」启动真实分割；完成后打开阅片「AI分割叠加」并切换四序列 | 当前真实mask、体积与分析版本，不是模拟叠加 |
| 11 | 病例「自动掩膜特征研究」→核对/保存年龄性别→提取 | 原始IDH目标值=1研究概率与融合、模型/特征/临床来源；输入修改旧结果失效 |
| 12 | 当前成功分析「确认」→报告→独立医生意见→PDF | 复核绑定版本，过期结果拒绝新导出；研究结果与诊断报告独立 |
| 13 | 返回「病例管理」 | 病例状态变为「已分析」 |

### 第三步：接口自测（可选）

后端启动后可用 Swagger 或 curl 自测，例如：

```bash
# 健康检查
curl http://127.0.0.1:8012/
# 病例列表
curl http://127.0.0.1:8012/cases/
# MRI 体素元数据
curl http://127.0.0.1:8012/mri/1/volume
# 真实窗宽窗位切片（返回 PNG）
curl "http://127.0.0.1:8012/mri/1/slice/axial/80?ww=238&wl=119"
```

## 七、接口规范

统一返回格式：

```json
{ "code": 200, "message": "success", "data": {} }
```

统一错误（404 / 422 / 500 同构信封，兼容前端 detail）：

```json
{ "code": 404, "message": "MRI not found", "detail": "MRI not found", "data": null }
```

MRI 状态机：`uploaded → processing → preview_ready → analyzed → doctor_verified`（失败 → `failed`）。

## 八、测试

```powershell
cd E:/BrainFusion-AI/backend
. ./tools/use_e_drive.ps1
../.conda/brainfusion/python.exe -B -m pytest -q -p no:cacheprovider
cd ../frontend
npm run build
$env:BRAINFUSION_WEB_URL='http://127.0.0.1:5179'
npm run test:e2e
```

2026-10-10本轮75后端、2基础浏览器和构建通过；专用真实流程/空间/版本/PDF/恢复证据见系统台账，基础浏览器不代替这些验收。未实现：同协议自动队列重拟合、熵权完整对照、多种子完整联邦、正式统计/解释及独立外部评价；不宣传研究版完成。

## 九、注意事项

2026-10-10 05:08窗口E6新增独立Windows Python3.11.17/torch2.11.0+cpu主候选：52轮子/20Conda文件来源与SHA、双环境92后端、同病例CPU掩膜逐体素差0/五开发样本概率差0、副本保存恢复、真实CPU服务启动/重启/四序列浏览器及CUDA回退通过。默认仍原CUDA主环境；新候选是可选CPU配置，不是异机/Linux部署验收。启动工具新增可选`-PythonPath`，复用时要求实际解释器一致；来源、重建与验收边界见docs/CPU_RUNTIME_CANDIDATE.md。当前服务已恢复5179/8012，PID与证据以最新交接为准。

1. **医学免责**：本系统为教学科研原型，AI 结果仅供参考，不构成诊断或治疗建议。
2. **数据与隐私**：上传的 MRI 与数据库（brainfusion.db）含患者信息，仓库已通过 .gitignore 排除，请勿将真实患者数据提交到公开仓库或部署到公网。
3. **依赖**：依赖清单与本机实测不等同；真实分割/特征/研究须各自依赖与模型。现用独立CPU特征工作器3.11.17已01:06验收，归档3.9保留；可选CPU主环境也已实测，不与特征依赖混装。旧门槛不覆盖，新候选先复现后切换。
4. **端口占用**：后端默认 8000、前端默认 5173，如被占用请修改启动参数或 `frontend/.env` 中的 `VITE_API_BASE`。
5. **前端配置**：后端地址通过环境变量 `VITE_API_BASE` 配置，默认 `http://127.0.0.1:8000`。
6. **常见问题**：标注点/ROI 无反应多为后端未启动；页面显示旧版多为运行旧构建，请重启 `npm run dev`。
7. **时间戳/历史**：新API明确UTC时区、页面北京时间；历史缺时间或谱系不能当当前成功结果。迁移前先备份，不直接在历史原库验证。

## 十、Docker 部署

现有Dockerfile/Compose仅为待验证配置。本机E5尚未验收，不把配置存在称为部署成功；先核实Docker/WSL/权限与E盘磁盘位置，再实际CPU构建、前后端/两工作器、只读模型和重建后数据一致性。需要系统授权/重启时暂停该步骤，不在长任务中重启。详见系统台账。

## 十一、未来规划

已批准范围与次序以docs/SYSTEM_COMPLETION_CHECKLIST.md、docs/POST_SPRINT_PLAN.md、docs/RESEARCH_PROTOCOL_NEXT.md为准；先稳定系统交付，再补原研究规划，不用SCI选题等待阻塞系统。真实模型统一为当前MONAI BraTS SegResNet；不新增Ki-67/生存/LLM报告/DICOM成组/自动配准/PACS/云服务。


2026-10-13 07:11：P3转换只读重开与现有病例来源状态工程通过，真实PACS/四序列/AI激活仍未验；单例真实NIfTI阅片性能记录另列，不代替完整P4。详见 docs/P3_CONVERSION_INTEGRITY_VALIDATION.md。
