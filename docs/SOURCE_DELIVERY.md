# 当前源码交付候选

## 当前源码候选与版本规则

候选文件清单、逐文件SHA、ZIP校验和与解包验证应以本次单独生成的E盘nightly证据目录为准；本说明不嵌入其自身的候选哈希或输出路径，避免源码文档进入白名单后形成自引用旧版本。只读交付就绪报告仅证明其明确标出的本机范围，不替代新机部署或真实影像/效能验收。

每次源码/受控交付说明变化后，之前的ZIP即成为历史快照，不能代表当前工作树。当前最新内部候选目录、实际文件清单、逐文件SHA和解包验证以E盘nightly目录下最新的`prepare_source_delivery.py`输出为准；目录必须同时有`audit.json`、`validation.json`和`unpacked-source/`，且其解包回归日志成功。不可用本说明中的旧版本段落推断最新候选。

当前包版本由E盘nightly证据判定，不从本说明里的固定编号推断：每次修改白名单内源码或交付说明后，生成新候选，并核对同一run目录中的`candidate/audit.json`、`candidate/validation.json`、解包全量后端回归日志和`readiness/result/validation.json`；只有readiness的`source_candidate_vs_current.is_current=true`才可称为工作树对应的当前候选。此前final10保持历史快照。final11曾完成459项白名单审计、ZIP/逐文件哈希校验、解包694项后端回归及本机只读预检；其SHA和结果保存在相邻证据目录。该说明本身也在源码白名单中，因此后续候选必须重新打包并复验，不能沿用final11的当前性结论。

当前工程材料包：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T2240_materials_rebind_final7/`。22:40只读刷新源码/API/数据库证据，27项及ZIP哈希通过；截图与图表文件沿用16:10已验材料，本轮没有重新截图或重新渲染。交付复验确认14项实现源码和3项再现工具与工作树一致、严格本机预检通过、数据库签名不变。该状态只覆盖现有工作站；真实四序列DICOM到AI仍因影像内文字暂无法确认而未验。

历史快照（2026-10-18）：容器交付与跨平台存储准备修改了后端路径策略、PACS/DICOM服务、`backend/Dockerfile`、`frontend/Dockerfile`、`docker-compose.yml` 和验收文档；Compose 另设显式 Docker 宿主机 Orthanc 地址开关。此前 454 文件源码包已成为历史快照。本轮已重新生成内部源码候选；当前文件清单、逐文件SHA、ZIP校验和与解包验证见 E 盘 nightly 目录最新候选的 `audit.json` 与 `validation.json`。该包仅为源码交付候选，Docker/WSL 与 Linux 运行未实测。

2026-10-18此前内部源码候选纳入显式重采样、病例页四序列方案/转换作业、角色审核与显式激活页面覆盖、分析历史只读列表及病例切换迟到响应隔离；白名单454个文件，受限凭据扫描0项，逐文件打包/解包校验通过。完整Edge E2E现为8 passed/1个需要获准真实病例的场景按设计跳过；分析历史状态接口故障下仍可查看历史、病例切换迟到响应隔离两个Edge场景通过。交付就绪状态为`passed_existing_workstation_only`，当前源码454/454一致、数据库未变；这些数据仅描述旧候选。该内部源码包不含运行环境、数据、模型或私有配置，不等于新机/Docker/Linux安装、真实DICOM或研究效能验收。
# 当前源码交付候选

## 2026-10-16 研究源码与协议增量

既有408文件组合早于R2/R3/R4新增实现。当前精确白名单新增八份冻结协议/有界验收和[离线重放指南](RESEARCH_OFFLINE_REPLAY.md)，不递归收录研究结果或患者表。此次需实际新审计/增量组合和解包研究测试后才称新组合通过；旧402 ZIP/404和408增量保持原字节，不追改旧验收。运行所需源数据/拆分/可信模型/config/R3结果仍为外部前提，不随源码复制。


2026-10-16 更新，run_id `20261016T061912_source`。此前10/10的237文件ZIP仅为历史，不包含当前PACS、Cornerstone、来源保护、距离/视图/复核、本地账户和恢复工具。当前工具直接读取工作目录中的真实源码，包括未提交和未跟踪实现；不用git archive、不提交或发布。

## 组成与边界

`prepare_source_delivery.py`按白名单收录README/Compose、backend的app/tools/tests/requirements和构建配置、frontend的src/public/tools/e2e/锁及构建配置、明确列出的操作/范围/有限验收说明。当前包括独立维护手册、PACS操作与本次PACS元数据页面验收、导师演示问答和待办问答，以及本地复核账户、当前架构说明、P1–P4有界验证说明；架构图只从`docs/assets/architecture-20261016`六个固定SVG/PNG/来源与渲染记录中选择。不会递归收录任意截图、患者图像或内部夜间交接。

排除Git历史、环境/依赖、dist、数据库、DICOM/NIfTI/mask、模型/队列/研究产物、私有账户和归档配置、初始密码/活token、日志/浏览器配置、nightly交接、每日记录/反馈/自动化提示词。即使私有配置放入通常允许的源码树，也按明确敏感文件名、credentials/backups目录和.password.txt/.token.txt拒绝收录。此规则不能识别所有任意命名的业务JSON，交付前仍须查看audit文件清单。

每文件上限2MiB，文本接受UTF8/BOM或带BOM的UTF16并保留原字节；未知编码/超限/重解析源文件拒绝。Python AST逐文件解析；六类有限凭据模式（私钥、AWS、GitHub、HuggingFace、OpenAI及URL内凭据）只输出路径/行/规则，不输出值。不是完整秘密、身份信息、恶意代码或再分发许可认证。源码/第三方许可仍不等于获准公开发布。

## 有限同步生成

先在全新E盘证据目录准备工作脚本，脚本内重核交接/源码基线，设置E盘临时和缓存目录，再运行下列命令；由`backend/tools/run_development_step.ps1 -RunId <唯一.step> -ScriptPath <E盘脚本>`执行整个有限步骤。不要调用退役后台holder，也不要在锁外打包或测试。

```powershell
Set-Location E:/BrainFusion-AI
. ./backend/tools/use_e_drive.ps1
./.conda/brainfusion/python.exe -B ./backend/tools/prepare_source_delivery.py --output <不存在的E盘nightly子目录> --build-local-candidate
```

本轮先前审计因旧合成协议测试含字面URL凭据而拒绝，未生成ZIP；已改为运行时组装同一合成URL，扫描规则没有豁免。唯一打包候选输出：`E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T061912_source/candidate-final/`。`audit.json`列所有允许文件的大小/编码/SHA与排除目录；`validation.json`确认ZIP和解包逐文件名称/长度/SHA。构建前重读SHA防止审计后变更，失败保留输出，不覆盖旧候选。ZIP旁的unpacked-source用于代码验收，不自动切正式服务。

本轮新增5项源码交付行为检查已通过，覆盖私有配置排除、精确图稿/指南、凭据脱敏与阻断、编码和打包解包。候选的实际解包测试、前端构建、文件/引用审计及正式服务保护结果以本轮`verification.json`和各日志为准；未出现结果文件或状态失败时不能称已验。打包后文档/代码再变化属于工作目录后续版本，不修改既有ZIP；内部交接/日报不进入候选。

## 与数据/环境组装

源码候选不含Python、Node、已安装依赖、Edge、Orthanc/插件和数据/模型，不是独立安装器。解包验证使用本机既有主Python、已安装前端依赖和Node24，明确不等于新机安装。Vite构建须显式设置`VITE_API_BASE=http://127.0.0.1:8012`，该地址仅本机验收用途。

本机已验完整数据组合见[E6完整恢复](E6_FULL_ACCOUNT_RECOVERY_VALIDATION.md)和[备份恢复指南](SYSTEM_BACKUP_RESTORE.md)；其650应用/196归档配置/5导入/两账户快照私有，不自动合入源码ZIP。再导入仍需登记的外部来源/技术复核材料，已归档阅片字节则在恢复归档中。不要把含工程记录的恢复副本切为正式默认库。

环境组成与历史离线引导分别见[主CPU](CPU_DELIVERY_BOOTSTRAP.md)、[前端](FRONTEND_DELIVERY.md)、[特征工作器](RADIOMICS_DELIVERY_BOOTSTRAP.md)。这些10/10环境证据不保证当前新增依赖在新机已安装；必须对当前requirements/锁及PACS依赖重新核对，不能借已有环境构建冒称安装通过。启动/复用见[本机运行](LOCAL_RUN.md)，PACS与账户见[PACS准备](PACS_LOCAL_PREPARATION.md)、[账户操作](LOCAL_REVIEW_ACCOUNTS.md)。这些指南中的历史本机证据/内部台账地址是外部引用，不是随包运行依赖或可公开资料；源码候选不自动复制这些目录。

当前支持范围见[交付范围](RELEASE_SCOPE.md)，演示见[固定演示](FIXED_DEMO_GUIDE.md)，图稿见[当前架构](SYSTEM_ARCHITECTURE_CURRENT.md)。P3匹配真实四序列模型桥、E5正常系统授权/容器、当前源码与完整新环境的联合安装及异机/可见人工抽查仍未完成，P4/E6整项不因源码包存在而通过。

