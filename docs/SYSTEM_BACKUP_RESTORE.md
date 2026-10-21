## 2026-10-20 当前重绑后完整联合快照与离线恢复

**2026-10-20恢复演练更新：** 原Orthanc在8042正常运行；隔离恢复副本现已在8043以前台方式启动并通过认证元数据核对。副本与保存的身份pin及原服务标识一致，检查/实例UID集合相同，且未读取像素；临时副本已正常关闭。根因是新端口使Orthanc自动推导出的标识发生变化。已修复 `snapshot_pacs_joint.py`：之后的恢复会将快照PACS配置中的已保存pin写入恢复副本的Orthanc配置，并记录 `database_server_identity_pin_applied`；针对恢复测试16项通过。当前副本的验证记录见 `E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T210109_scope_closeout/restore-metadata-live/orthanc-live-metadata-validation.json`。应用病例关联指纹还绑定PACS地址；8043因此属于不同端点，应用不会自动沿用8042的病例关联。整体 `live_restoration_verified=false` 继续保留，直到在维护窗口用原端口8042完成只读应用级切换验收，或完成有审计的关联重绑。不得为此擅自停用当前原服务；也不要将Orthanc元数据核对表述为应用、病例关联和AI整链路恢复通过。

新建私有联合快照 E:/BrainFusion-Runtime/backups/closeout-joint-20261020T110853Z/，覆盖196个Orthanc归档/配置文件和702个应用文件。输出ACL限当前用户、Administrators、SYSTEM。恢复到同目录下的独立副本后，校验应用及归档副本SHA-256、SQLite完整性、17张表科学/版本字段和13项运行路径均通过；snapshot/restore CLI返回passed，原数据与活动库未改。恢复记录 joint-restore.json 明确 live_restoration_verified=false。

快照恢复副本使用8043与原归档隔离。由于原配置未显式固定 `DatabaseServerIdentifier`，Orthanc按网络接口、AET及端口推导身份，使用新端口后首次启动出现身份差异。现已仅在临时启动配置中显式沿用保存的身份pin，副本身份与原服务、应用配置pin一致；只读比较了检查/实例UID集合并正常关闭。原配置、原归档、恢复配置均未改写。应用的endpoint_fingerprint由PACS地址和身份pin共同计算，所以8043克隆端点不会匹配原来绑定8042的病例关联。要通过应用级恢复验收，需安排维护窗口短暂切换恢复副本到8042，或单独实施经过审核、留痕的关联重绑；不得自动更改旧病例链接。真实像素审核仍待具备权限人员完成。

## 2026-10-20 Compose 重绑后配置隔离恢复检查

从私有补充快照恢复到全新隔离目录，3/3配置文件的SHA-256与清单一致、JSON均可解析；本地账户结构及PACS必需字段检查通过，恢复目录ACL仅限当前用户、Administrators、SYSTEM。活动配置与快照哈希仍一致，Docker演示的原后端和前端容器仍健康。报告：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T2210_post_rebind_config_restore_check/recovery-check-report.json。

此项只验证三份配置的文件级恢复，不启动恢复服务，也不代表应用数据库、模型/数据集或Orthanc归档完整恢复。正式交付手册仍须在代码/配置冻结后编写，并由用户按手册独立完成启动、浏览、修改配置、测试、备份/恢复及故障排查演练；不得把本次小范围检查作为整机恢复通过。

# 应用数据快照、恢复与可重定位启动

## 2026-10-20 预重绑 Orthanc 备份 ACL 收紧

复核发现原有 pacs-identity-rebind 备份继承了 Authenticated Users 可修改、Users 可读权限。已仅修改该备份目录及其 197 个清单文件的 ACL，限定为当前用户、Administrators 和 SYSTEM；所有原始 SHA-256、字节数及 manifest SHA-256 收紧前后相同。没有删除/移动文件，也没有触碰运行中的 Orthanc、Compose 或当前配置。

验证结果：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T2130_secure_backup_acl/backup-acl-verification.json。此次仅改变备份副本权限，不代表完整恢复演练。



## 2026-10-20 Orthanc 重绑后 Compose 配置补充快照

原 pacs-identity-rebind 归档在重绑前生成，其中 pacs-config.json SHA-256 与当前值不同。现已为重绑后的 Compose 运行配置补存 PACS 配置、本地账户哈希和 radiomics gate 三个文件；逐文件 SHA-256 复核通过。新目录 ACL 只允许当前用户、Administrators 与 SYSTEM，未继承 Users/Authenticated Users 访问。

私有快照位置：E:/BrainFusion-Runtime/backups/compose-run-config-20261020/。其含 PACS 凭据/本地账户摘要，不得进入源码ZIP或公开材料；它只补足当前三份运行配置，不是应用数据/模型/Orthanc完整备份。需与原 Orthanc pre-rebind 197文件归档及 Compose runtime 持久化副本组合恢复。验证报告：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T2115_post_rebind_config_backup/backup-verification.json。



## 2026-10-18：联合收录并重定位转换材料

`snapshot_pacs_joint.py --action backup`目前将转换索引及其同级`dicom-conversion-plans/`、`dicom-conversion-jobs/`、`dicom-conversion-outputs/`逐文件收录进仅限`E:/BrainFusion-Runtime/backups/`的联合包，并对源与副本核字节数/SHA；转换暂存目录未完成时拒绝报成功。恢复至新目录后重写索引、任务与`source-files.json`中的旧服务器绝对路径，并更新受影响的源清单SHA。锁文件不纳入快照。联合包仍包含私有账户/PACS配置和可能的原始DICOM，严禁作为公开源码交付。

当前正式转换根为空（jobs目录也无文件），无真实方案、采集DICOM、作业或输出可恢复/交付；本轮仅新增隔离材料恢复回归（16项通过），没有停机或制作空转的全系统联合快照。真实材料产生后，按offline backup/restore流程独立恢复，再在启动恢复服务前核对每个作业输入、原始DICOM SHA、输出及索引关系；页面上的真实四序列操作仍须等待合格同检查数据，不得用夹具宣称通过。

## 2026-10-17：联合恢复直接生成统一v2运行配置

`tools/snapshot_pacs_joint.py --action restore` 在恢复独立目录后生成根目录 `runtime.json`（format_version=2），一次绑定应用八路径、PACS配置、导入登记/作业、本地复核账户及DICOM转换索引。相对路径统一落在恢复包内；辐射组学解释器继续指向已安装的E盘外部环境。旧快照仍可读取：缺少的导入历史/账户/转换索引不会被伪造为空历史，`joint-restore.json` 会逐项标明；缺少PACS配置或账户时 `runtime_config_ready_for_local_start=false`。文件路径可读不等于服务启动、归档UID关联或AI链路通过。

联合备份现在在转换索引存在时校验并收录其原始字节与SHA256；不存在时明确登记 `conversion_index_included=false`。该索引仍引用登记中的版本目录、proposal及snapshot绝对路径；本批没有把这些外部转换材料或源DICOM复制进包，必须另核完整性后才能恢复/激活相应模型输入。恢复运行配置后可用 `start_local.ps1 -RuntimeConfig <restored>/runtime.json`，但仍须按服务停止/启动规则做实际恢复验收，并核对 `joint-restore.json`、账户登录和来源映射。历史分离runtime文件保留供旧流程读取。

## 10/16 05:18：含原正式账户的19病例完整数据组合已验

[当前完整恢复](E6_FULL_ACCOUNT_RECOVERY_VALIDATION.md)收录650应用文件/19病例/17表、196归档配置、导入回执和原正式两账户，独立启动NIfTI/DICOM与科学API、账户登录/第7条工程复核、归档/应用重启及幂等通过。旧6条工程actor保持其历史归属，不改成当前账户或医师资质；新复核只写副本，正式库/账户不变。原件全SHA和规范化科学字段保护有证据。

仅数据组合，不复制源码/完整Python/Node环境/Orthanc程序；再导入来源材料是固定SHA的外部前提。私有snapshot不得公开，明文密码/会话不入snapshot，恢复后必须重新登录。不要把本轮通过写成所有部署/异机条件都满足，也不要再称完整新账户数据组合从未实测。

## 10/16 01:05：自动收录接线已实际跑通

当前[DICOM最小真实联合组合](P4_JOINT_ACCOUNT_RECOVERY_VALIDATION.md)已由真正的联合backup/restore CLI自动收录账户并恢复到独立路径，启动真实归档/业务库，浏览器登录/另存/重启/重登和不可变历史通过；损坏账户预检拒绝且未创建输出。声明的空运行根目录现在也被恢复，原路径保护保持。此组合仅1个真实DICOM病例/17表/2应用合同文件，原模型/研究/原队列是明确外部前提；旧650文件全量恢复继续是另一历史证据，不混成完整新版全量包验收。

实际启动必须读取三组额外配置：恢复pacs-config.json，import-state/runtime.json，以及local-auth/runtime.json；后两者不属于原八路径JSON。当前实际工作脚本见本run/run_joint_auth.ps1，有限同步持锁、finally显式回原额外路径，并实际检查PACS ready/原候选/本地账户，避免null环境转空字符串。恢复后需重登，不能恢复有效会话。私有snapshot不含明文初始密码；本轮单独的测试token留在私有bundle父目录，勿公开任何backups内容。

只需要DICOM/账户接线验收时应明确缩小自有夹具，保留源库/源账户与原归档，使用计划守卫核实不会重复650文件；不能在原库删病例或把最小夹具当全患者备份。完整新多病例含账户/模型包留最终交付验证窗口，不每轮重抄。以下00:03“新接线尚未实测”为当时历史，本段更新了最小真实组合的结论。

## 2026-10-16增量：账户私有快照与联合收录

新增backend/tools/snapshot_local_auth.py，只备份有效账户配置及盐化密码摘要，不复制初始明文密码或有效会话。输出/恢复仅限E:/BrainFusion-Runtime/backups的全新私有子目录；同本机账户管理工具使用同一配置字节锁，拒绝并行维护、覆盖、错SHA或被改清单。真实两账户配置已备份/恢复且SHA一致；4新行为+5auth+9归档快照共18项通过，4既有警告。TestClient实际恢复后重新登录/账户ID一致通过；本轮没有新活浏览器登录验收。

在有限同步工作脚本内可调用：

```powershell
& E:/BrainFusion-AI/.conda/brainfusion/python.exe -B E:/BrainFusion-AI/backend/tools/snapshot_local_auth.py --action backup --source E:/BrainFusion-Runtime/local/local-users.json --output E:/BrainFusion-Runtime/backups/全新目录/snapshot
& E:/BrainFusion-AI/.conda/brainfusion/python.exe -B E:/BrainFusion-AI/backend/tools/snapshot_local_auth.py --action restore --snapshot E:/BrainFusion-Runtime/backups/全新目录/snapshot --output E:/BrainFusion-Runtime/backups/全新目录/restored
```

新snapshot_pacs_joint默认读取LOCAL_AUTH_FILE（可用--local-auth-file显式指定），文件存在时收录local-auth目录及清单SHA，恢复时先验证账户清单/内容再写输出；旧manifest缺local_auth_included仍可恢复，不伪造账户。恢复得到local-auth/runtime.json是独立的额外环境路径，和导入回执runtime.json一样不属于原八路径配置；启动前将其LOCAL_AUTH_FILE设到恢复文件，服务重启需重登。需要与正常归档/应用停机、切换、验证和回正式服务一起放在同一同步工作脚本，仍不能用后台holder跨调用保活。额外变量原先不存在/空时用Remove-Item Env:删除，勿通过.NET SetEnvironmentVariable把null变成空字符串；本轮曾导致八路径正确但PACS invalid_config，已独立复现并显式原路径重启修复。恢复后实际检查PACS ready/原候选及账户配置，不能仅看进程/SQLite。

本次实际私有输出E:/BrainFusion-Runtime/backups/20261016T000514_p2v2-auth/{snapshot,restored}。旧20261015T224154完整17表bundle继续是历史、不含账户；本轮仅新组件和收录代码，没有重做650文件/完整新版bundle活服务恢复。下一批应针对新组合验证后再更新完整验收，不能只看字段存在勾选。证据见[P2本轮附带E3小批](P2_V2_REAL_IMPORT_VALIDATION.md)。以下“尚未收录”段落属于10/15旧工具历史。

## 新增账户配置必须补备份

本地DICOM复核使用独立 `LOCAL_AUTH_FILE`（默认E:/BrainFusion-Runtime/local/local-users.json），存盐化密码摘要/账户ID/本机角色，不新增SQLite表。当前旧17表联合快照工具不自动收录它；原联合恢复验收保留，但以后备份须另存该私有配置并核对SHA。本文不能据旧bundle宣称账户一起恢复。当前正式配置补充快照在E:/BrainFusion-Runtime/backups/20261015T231143_p4identity-auth，工程配置独立恢复后实际重登已验；没有备份明文初始密码/有效会话。恢复到另一E盘路径后设置LOCAL_AUTH_FILE，正常重启再登录；内存会话应失效。详见[账户指南](LOCAL_REVIEW_ACCOUNTS.md)和[本轮证据](P4_LOCAL_REVIEW_IDENTITY_VALIDATION.md)。统一自动收录仍待后续独立小批，不重复整套650文件联合恢复。

## 2026-10-15夜间：17表完整组合已验

run_id `20261015T224154_p4joint17`，10/15夜间22:39接续。第17表含复核的新完整联合恢复子项已验：196归档/配置、650应用文件及5导入文件离线备份/独立恢复后实际启动；192字节SHA/关联、17表科学版本字段、36工程距离/1视图/3复核完整快照、4000字当前复核及导出SHA与真实浏览器一致。原日常17表所有行、原八路径及原归档保持，回正式目录只读0写/0异常。详见[17表联合恢复](P4_JOINT17_RECOVERY_VALIDATION.md)。按新同步包装器执行，失败/成功步骤均finally回正式服务并释放锁，旧后台等待不再调用。P4整体仍进行中，身份/角色、其他浏览器/最终部署及P3真实四序列桥未完。

快照包含复核完整snapshot/context、36距离、1视图、3历史和5份导入文件。实际恢复目录启动时同时切换八路径、PACS_CONFIG_FILE、PACS_IMPORT_REGISTRY_FILE及PACS_IMPORT_JOBS_DIR；完成或失败均在同一个有限同步脚本finally回正式目录。私有目录`E:/BrainFusion-Runtime/backups/20261015T224154_p4joint17/`含凭据不公开。启动服务、离线复制、恢复、验证与回正式服务必须作为同一个工作脚本，由run_development_step.ps1执行；禁止先后台空占锁再跨调用切换配置。旧16表/17表单库证据只代表当时范围。


## 2026-10-15 03:20：第17表复核快照

run_id `20261015T032046_p4review`，对应10/14晚→10/15凌晨。新增dicom_reading_reviews保存来源/阅片内容快照及本机人工意见，旧16表列/记录不变。先原16表备份、在副本建立第17表及4条工程复核，再用既有snapshot_database实际快照/另目录恢复；17表全部行逐字段一致，旧三距离快照/当前两距离/3879字原文保留。回原八路径后正式新表0行，原16表全行不变。证据review-migration-and-backup、review-state-backup及[P4复核验收](P4_DICOM_REVIEW_VALIDATION.md)。

上轮16表+PACS+导入回执完整联合恢复是当时真实证据；本轮仅新17表单库恢复及服务重启，没有重复完整新组合/AI运算，不冒称已验。恢复需保留review snapshot/context与原病例检查/归档、测量版本关系；单独意见文本不能证明当前来源有效。

## 2026-10-15 02:15：当前16表与导入补充的新组合已验

run_id `20261015T021538_p4report`，对应10/14晚→10/15凌晨。使用既有joint工具实际备份/恢复当前16表（三条真实DICOM距离、一条来源视图）、650应用文件/521478562字节、196归档/配置及5份导入登记/回执；恢复目录启动归档和应用后192原字节SHA/关联、保存相机/窗值/世界测量/报告内容摘要及回执均通过。57行操作路径按原规则重定位，16表科学/版本字段一致；源650文件及原日常16表所有行不变。下方历史“新完整组合未重复”仅代表早先窗口，不覆盖本次验收。

私有快照`E:/BrainFusion-Runtime/backups/20261015T021538_p4report/{snapshot,restored}/`含凭据，不公开。启动恢复目录时将PACS_CONFIG_FILE设为恢复pacs-config，PACS_IMPORT_REGISTRY_FILE/PACS_IMPORT_JOBS_DIR从恢复import-state/runtime.json加载；八路径应用runtime用既有加载器解析相对路径，不能直接把database.db当当前工程目录文件。完成后正常停恢复服务、清除临时额外路径，原归档/八路径已恢复。详情[P4新组合验收](P4_DICOM_READING_REPORT_VALIDATION.md)。本次没有在恢复目录重跑推理/特征/概率，不宣称新的AI计算复现。

## 2026-10-15 01:11：新增DICOM视图表

run_id `20261015T0112_p4view`，对应10/14晚→10/15凌晨。当前16表，新增`dicom_view_states`，与上一窗口距离表分开；create_all只建新表，不改原15表行。先15表备份和副本迁移，真实浏览器保存一条DICOM视图及一条NIfTI回归视图，再用既有snapshot_database工具实际快照/恢复；原15表历史行保留、两份视图逐字段一致。回原八路径后新表为空、原15表全行一致。完整归档联合快照的新组合没有重复实测，不能用这次数据库恢复冒称新完整联合验收。

恢复必须保留病例关联、归档身份/元数据上下文及实际归档；单独相机值不证明当前来源有效。证据见[P4视图验收](P4_DICOM_VIEW_STATE_VALIDATION.md)及本run `view-state-snapshot/`、`migration-and-real-view-backup.json`；下方15表为上一窗口历史范围。

## 2026-10-15：新增DICOM距离表

当前业务库在历史14表之外增加`dicom_world_measurements`（共15表）；使用启动时create_all建新表，不改原表列或旧记录。已先在副本完成迁移/真实浏览器写入、重启/删除及原14表全行一致，再恢复原运行目录创建空表。现有snapshot_database工具对新表三条合成协议测量的快照/副本恢复逐字段一致已验证；真实测量服务重启用副本实测。保留新表、病例检查关联、归档服务指纹及相应源/索引；单独导出坐标不能证明当前版本有效。此次没有重做全套PACS联合恢复或容器部署，历史联合恢复范围保留。见[P4距离与证据](P4_DICOM_MEASUREMENTS_VALIDATION.md)。

## 2026-10-14 本地PACS联合恢复补充

20:36窗口又新增受控导入登记/回执的备份：`tools/snapshot_pacs_import_state.py --action backup --output E:/BrainFusion-Runtime/backups/<新run>/import-snapshot`，再以`--action restore --snapshot <import-snapshot> --output .../import-restored`恢复到新目录。实际5份文件与独立API读取通过，见[P2导入验收](P2_CONTROLLED_IMPORT_VALIDATION.md)。互斥文件不能复制；来源DICOM/复核记录依然是固定的外部前提。新`joint`快照在登记存在时会包含该补充块，兼容旧清单；此新组合分支尚未重复完整归档演练，既有联合恢复证据保留为当时范围。

恢复新快照后，还需从`<restored>/import-state/runtime.json`把`PACS_IMPORT_REGISTRY_FILE`及`PACS_IMPORT_JOBS_DIR`设到后台进程环境，再启动原八路径应用runtime；这两项与`PACS_CONFIG_FILE`同为额外归档配置，不把补充runtime交给八路径加载器。若未切换，会读到原目录回执，不能算恢复通过。本轮独立恢复验证显式指向了副本。

新增本机SQLite归档与完整应用的离线联合快照，已实际恢复到独立目录并启动归档、后端、前端；192份真实MR派生实例、病例UID关联、全部体素及三视图通过，随后回到原运行目录。详见[P4联合恢复验收](P4_PACS_JOINT_RECOVERY_VALIDATION.md)。下方E3历史范围保留，不能把它当作此前已包含PACS。

操作时先持有既有开发独占锁，确认没有分析/特征任务；用`stop_local.ps1`及`stop_orthanc_local.ps1`正常停止登记服务。调用主环境Python的`tools/snapshot_pacs_joint.py --action backup --runtime-config <当前八路径runtime.json> --output E:/BrainFusion-Runtime/backups/<唯一run>/snapshot`，再以`--action restore --snapshot <snapshot> --output E:/BrainFusion-Runtime/backups/<唯一run>/restored`恢复到全新目录。正在运行、已有目标、未知归档配置或校验不符会拒绝；不覆盖原件。

恢复演练先用`start_orthanc_local.ps1 -Root <restored>/orthanc`，后台进程环境的`PACS_CONFIG_FILE`设为`<restored>/pacs-config.json`，并给`start_local.ps1`传`<restored>/application/runtime.json`。地址保持8042/8012/5179，因为归档指纹包含地址；不能与原服务同时启动。用`verify_pacs_joint_restore.py`对照停机前观察，另做真实浏览器验收。完成后停止副本、清除临时环境切换，以原PACS配置和原runtime重新启动；本轮已实际验证该回退。快照包含服务凭据，只用于私有恢复，不放进公开交付包；代码/二进制/环境及原始数据来源材料仍为外部前提。

更新：2026-10-10；E3本机验收证据：E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T000643_ec1cf8da。

## 已验收范围

快照包含SQLite、上传MRI、分割掩膜/预览/分析产物、特征任务及结果、当前分割模型与来源、研究模型/数据表/来源说明、特征复现契约；扫描数据库引用的额外本地产物。原库先只读备份，恢复只修改副本中的操作路径及特征缓存键，原数据与快照不改。

这是应用数据/模型/结果的恢复，不是整机镜像：项目代码、主Python/CUDA环境、独立特征解释器仍是外部前提，快照记录特征解释器来源但不复制其可执行环境；不复制未被应用使用的全MRI研究队列。E4环境迁移、E5容器、E6完整交付仍有独立门槛。新增原MRI/模型推理和PDF导出没有在本轮重复执行；相关历史验收见系统台账。

## 操作

先确认没有排队/运行中的分割或特征、没有其他开发锁持有者；使用既有stop_local.ps1核验身份后停服务，避免备份期间文件变化。每个输出目录必须不存在；不覆盖旧快照/恢复目录。

```powershell
cd E:/BrainFusion-AI/backend
. ./tools/use_e_drive.ps1
# 把路径换为当前登记的数据库、uploads和feature_jobs；模型/研究/数据/契约环境变量必须与当前服务一致。
# 使用相同运行配置时，先读取runtime.json，再把它的八个路径设置到本命令的进程环境；DATABASE_PATH对应DATABASE_URL。
../.conda/brainfusion/python.exe tools/snapshot_system.py --action plan --source-db <源数据库> --uploads <源上传目录> --features <源特征目录>
../.conda/brainfusion/python.exe tools/snapshot_system.py --action backup --source-db <源数据库> --uploads <源上传目录> --features <源特征目录> --output <全新E盘快照目录>
../.conda/brainfusion/python.exe tools/snapshot_system.py --action restore --snapshot <快照目录> --output <另一全新E盘恢复目录>
../.conda/brainfusion/python.exe tools/verify_system_restore.py --snapshot <快照目录> --restored <恢复目录>
```

每条命令后检查退出码，失败时停止后续步骤并保留目录/日志。plan先报告文件/体积/行数和已有缺失；backup保存manifest.json、SQLite完整性、文件来源/大小/SHA256、数据库行数、模型来源及提取契约。restore逐个校验快照与副本；路径迁移后生成runtime.json和restore-validation.json。verify_system_restore还会核对源文件/原数据库未变、恢复副本的科学数值和版本未变。

```powershell
cd E:/BrainFusion-AI
./backend/tools/start_local.ps1 -RuntimeConfig <恢复目录>/runtime.json -BackendPort 8012 -FrontendPort 5179
# 已经运行时显式复用，绝不另起第二套服务：
./backend/tools/start_local.ps1 -ReuseExisting -RuntimeConfig <同一恢复目录>/runtime.json -BackendPort 8012 -FrontendPort 5179
```

runtime.json的format_version=1支持八个主路径：DATABASE_PATH、UPLOAD_DIR、FEATURE_JOBS_DIR、MODEL_DIR、RESEARCH_DIR、DATASET_DIR、RADIOMICS_COMPATIBILITY、RADIOMICS_PYTHON。format_version=2向后兼容地增加PACS_CONFIG_FILE、PACS_IMPORT_REGISTRY_FILE、PACS_IMPORT_JOBS_DIR、LOCAL_AUTH_FILE、DICOM_CONVERSION_INDEX_FILE；这五个键对应PACS配置、导入登记/作业、本地账户和转换索引四类外部配置。启动器会把这些路径传入后端并纳入服务复用登记。runtime.json v2本身只登记路径，不复制配置内容；由joint快照生成的恢复包另按joint-manifest收录其实际存在的PACS配置、导入回执/作业、本地账户及转换索引。旧包缺项不补造；转换索引登记的proposal/snapshot/版本目录与源DICOM仍是外部材料。start_local严格预检拒绝没有可用本地复核账户或无效/缺失PACS配置的候选。相对路径基于配置文件目录且不允许越界；本机绝对路径须在E盘。RuntimeConfig与Demo/DatabasePath互斥。默认旧uploads相对数据库路径仍可读取；新上传存绝对路径，不把任意含uploads字样的外部文件暴露为静态地址。

启动前先只读检查依赖、模型/来源、研究校验和、特征复现契约、独立工作器导入、SQLite完整性、已存当前分析文件谱系及存储权限，失败不启动服务。显式复用还核对每个配置路径、PID/精确启动时间、应用命令、监听端口归属、前后端健康；不一致时拒绝，不结束/接管其他进程。

## 本次证据

638文件/521,278,832字节；18病例、17MRI、24分析、25报告及2研究输入版本/3标注/1意见均恢复。57条操作路径改写；当前结果与原基线逐项相等。两次真实启动/重启后，三视图MRI/mask图片SHA256、四序列、已存自动特征概率/版本、参考研究结果、医生确认/意见/报告/标注一致；实际特征POST命中原任务，无重提取。静态上传地址返回恢复文件真实字节。

missing-model-preflight.log和missing-model-no-services.log证明缺模型启动失败、端口未被新服务占用；runtime-config-reuse-rejection.json证明错MODEL_DIR复用被拒且登记/PID不变。post-restart-immutable-audit.json证明638原件/快照SHA256和原数据库行未变。after-second-restart保存validation.json、四序列/研究/报告截图。75后端全套、2基础浏览器、构建最终通过；警告保留。备份/恢复数据约占1.04GB新增E盘空间，没有清理旧成功产物。

路径已恢复不等于标签/模型泛化成立。病例18仅病例17同公开患者产物的工程副本，不计为独立患者。逐轮数据/配置/PID和未完成项以NIGHTLY_HANDOFF为准。

最终视觉补验：人工查看发现after-second-restart的序列截图可能停在加载态，原因是验证工具切序列时对空图像集合调用every会提前返回true。修复为三张真实切片、三张完整mask、当前序列身份同时就绪，并等待选择菜单隐藏。after-restart-rendered-final/validation.json重新通过且保存四张已渲染序列截图；FLAIR/研究/报告截图实际查看正常。旧加载态截图保留但不作为最终视觉验收，不把这一工具缺陷冒称系统阅片故障。

