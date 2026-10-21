# 最新：Orthanc环境已解除，实际证据见P2_ORTHANC_ENV_VALIDATION.md

## 2026-10-14 23:12 新资料准备方式更新

新增资料使用[来源绑定准备流程](P2_SOURCE_BOUND_PREPARATION_VALIDATION.md)：先render_public_mr_review生成逐份源SHA和全部原像素联系表，实际技术查看后填写独立复核记录，再prepare_public_mr_viewing生成可重定位的v2证据包；register_pacs_import只接受该包内复核。源患者/Study/Series/份数不一致、漏看/像素或来源变动、空模板均拒绝。旧工具固定“已看六张”的描述已删除；原已固定历史登记保持不变。真实192新准备和隔离登记通过，未再真实归档，不把本次验证副本加入日常候选。完整命令、证据和范围见上述文档。

## 2026-10-14 19:08 本机Orthanc环境解除与项目连接验收

run_id `20261014_manual_orthanc_b392fd6e`。用户已通过浏览器把官方候选两文件下载到既定目录。本轮静态大小/x64 PE/本地SHA核对通过，实际Orthanc --version=1.13.0；Authenticode为NotSigned，未把本地SHA当发布者签名。正常启动Windows本机进程，实际DICOMweb插件1.24加载；匿名/system返回401，后台鉴权/system与QIDO查询通过，归档实例0。新随机凭据只存在Runtime私有文件，不输出或进入源码。

项目在先SQLite备份后按既有runtime-supported配置恢复，现backend6164/frontend2748、8012/5179；原业务所有表内容与备份一致。/pacs/status=ready/read_available=true，pixel_read_enabled=false。真实浏览器病例17归档查询按钮可见、实际查询HTTP200、pageErrors0、写请求0。无新DICOM导入、关联、像素读取、推理/特征训练或PDF。P2-env已解除，P2总体仍进行中，E5 Docker阻塞不受此次影响。证据：E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014_manual_orthanc_b392fd6e/summary.json、pacs-readiness.json、browser-pacs-ready.json。

新增prepare_local_orthanc.py与start_orthanc_local.ps1，prepare/语法/schema已核；actual start/connect通过。配置/索引/文件/日志在E:/BrainFusion-Runtime/orthanc-local；backend归档配置E:/BrainFusion-Runtime/local/pacs-config.json。Orthanc独立进程登记在orthanc-local/process.json，不误当项目start/stop_local的一部分；不注册系统服务，重启电脑后需按正常脚本重启。未提交/推送。

下一轮先核对开发锁/实际PID/健康，复用已启动归档，不再重试下载或将环境标受阻。优先192层真实MR的有记录脱敏派生副本及明确入库执行路径，原件/UID映射保留。来源/像素处理完成后验证实际导入→病例关联→Cornerstone，再开放像素；当前不把技术联系表查看冒充临床认证或模型四序列确认。可先用明确合成工程材料验真实归档持久化，但不能代替真实样本阅片。

## 以下记录为历史，不代表当前环境仍受阻

# 本地PACS环境与真实DICOM候选

## 2026-10-14 18:08实际有限MR序列取得

从公开NBIA实际取得同一匿名受试者两组CaPTk处理的临床来源MR候选。192实例组共19,432,662字节，源UID/本地SHA/全部像素解码及当前成组几何契约通过；192×256×192、spacing 0.9765625/0.9765625/1mm，非MOSAIC。六张联系表覆盖全部192层，技术查看在源默认窗未见身份文字；私有/日期等元数据待处理，未批准归档。另一60实例组发布者MD5全部匹配，但声明1mm与实测约3mm不符，保留拒绝。详见[P2实际公开样本记录](P2_PUBLIC_MR_SAMPLE_20261014.md)。这次取得实际像素，不再只做来源可达性探测；没有宣称实际PACS/Cornerstone或AI闭环通过。源文件与清单位于`E:/BrainFusion-Data/PACS-candidates/UPENN-GBM/20261014T180828_p2sample/`，证据位于同名run的Runtime目录。Orthanc被拒环境动作保持，不重试；检查时原5179/8012服务未运行，未启停服务。

## 2026-10-14 04:07公开DICOMweb来源核查

NCI IDC官方文档列有公开、只读、viewer-only的DICOMweb代理。本轮实际QIDO-RS查询返回HTTP 200与`application/dicom+json`，服务端对`limit=1`返回443条记录；响应体未落盘、未保留UID/患者标识、未请求DICOM帧或下载像素。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T0406_p2publicdicom/idc-dicomweb-probe.json`。此endpoint证明公开元数据查询服务可达，不证明系统的DICOM阅片或病灶数据使用条件通过。

产品现有DICOM入口需要本地病例绑定与归档身份校验，不能直接拿此公开查询结果伪装本地PACS病例。TCIA官方FAQ说明2026年期间正在迁移下载基础设施；UPENN-GBM搜索索引所列原始DICOM约139.4 GB，许可标为CC BY 4.0，但不据此自动下载全量或把先前拒绝的单实例再次导入。真实collection/series级样本需再次核实许可、数据大小和隐私，且依旧需要用户侧像素复核或既有可用的可信审核流程。Orthanc未安装/PACS配置缺失状态未变。

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
## 2026-10-13 01:19窗口（当前；10/12夜至10/13凌晨）

run_id20261013T011921_b6663451；系统UTC/原生PID精确值见本run lock-acquired，FileShare.None holder实际保持、session58224，结束/耗时/正常释放见summary。P2-b2只读递归预检工程已验，P2整体/导入仍进行中，P2-env受阻、P1 NIfTI已验、P3/P4待实施、E5受阻/E6进行中，R1待核查/R2–R4待实施。无反馈、不改REVIEW_FEEDBACK、不提交/发布。

新增services/dicom_preflight.py、tools/audit_dicom_preflight.py及tests/test_dicom_preflight.py：完整Part10/FileMeta/所有SQ/像素后属性，64MiB/10000元素/24层/1000命中上限，禁止重写/上传，报告/终端不输出字段原文。来源及像素review绑定SHA与UID/声明，标记嵌套ID/姓名/私有/日期文本/opaque/未知引用/烧录与缺复核；复用经典非MOSAIC布局/像素长度。archive_eligible、deidentification_complete恒false，自填manifest/review不等于独立认证或入库许可；可通过工程规则仍不能直接归档。标准FileMetaVersion精确例外与嵌套ID/加密SQ绕过保护已回归，初次标准版本误报日志保留。

官方PyPI固定pydicom3.0.2纯wheel2376822字节，发布SHA abf971a5440f84dbaf42c4b6758e30e62480902584f8b270b9a5d146e278a07b；E盘缓存、现用Python离线no-index/no-deps/no-compile只加一包，285个安装payload与wheel一致、所有旧包版本不变、torch2.11.0+cu128/CUDA正常。新增requirements-dicom-preflight.txt哈希锁，不改worker/PATH/系统证书/其他prefix，不重建旧环境。发行元数据license字段空，原LICENSE文本保存，不自行补SPDX。

最终134后端/4既有警告，34新合成Part10行为加100相关回归；真CLI拒绝/不覆盖、深层姓名ID/私有/引用/像素后字段/压缩/哈希/限制与脱敏。实际UPENN原候选复用，扫描169元素/83命中、退出3/rejected，33private等可能同标签多规则，不能称83项已证实泄漏，原SHA bd75b6ee1175a26d0b505035da1694a2c928c7c1a53344444b24b2ca8fc11443不变；没有像素review、不伪造医生或批准。state-validation原14表全行与上轮已验副本、科学/featurejobs SHA相同。无API/前端业务改动、不重启、不重复构建/浏览器/整包审计或推理/提取。

有限来源查找：TCGA-GBM一个候选ID和公开患者索引HTTP200空body，未取得患者/影像；两次无进展转查官方来源，不反复相同查询。Brain-Tumor-Progression索引也空，官方集合明确NIH受控申请，不下载或联系发布者；TCGA详情直接读取500，不仅由空body推断原因，未取得状态保持，无旧镜像/受限token尝试。空响应不是有效JSON或下载成功，本轮没有新DICOM下载。具体P2_DICOM_PREFLIGHT_VALIDATION。


## 以下为之前窗口的历史记录

## 2026-10-13 00:21窗口（当前；对应10/12晚至10/13凌晨）

run_id20261013T002126_88fd439c；系统UTC2026-10-12T16:21:26.4921910Z/北京00:21:26，FileShare.None holder/owner19652、原生16:21:26.0976807Z/session42261。结束/耗时/正常释放见本run summary。P1受支持NIfTI已验、P2进行中/P2-env受阻、P3/P4待实施、E5受阻/E6进行中，R1待核查/R2–R4待实施。无具体反馈，不改REVIEW_FEEDBACK；无提交/发布/模型或提取协议变更。

新增受限WADO metadata标准DICOM JSON数组与frame1，严格3UID/经典非MOSAIC单帧MR/方向/spacing/8或16bit/32MiB/MIME完整唯一part/未压缩LE/精确字节长度；不校正空间、补齐或截断。后台凭据隔离，移除外部BulkURI/姓名ID/private与自由描述，仅在allow_pixel_read严格bool开启时提供本站frame URI，默认false。status开关不是能力验收，DICOM viewer/AI仍false，无正式PACS配置。

最终100后端通过/4既有警告（35新WADO真实TCP合成夹具，不是Orthanc），原库只读快照/恢复副本先验证，实际重启后14表全行/原科学文件/所有featurejobs SHA相同。browser-wado-boundary实际新端点503/no-store/pixel=false、病例原UI未配置、NIfTI三canvas正常，异常/真实写0，截图已看。无前端业务变化，不重复构建/依赖安装/打包/推理或提取；96/99及更早测试是追加检查前历史。

官方公开NBIA v1返回UPENN-GBM匿名00001六Series六Study、CC BY4.0；四描述Processed_CaPTk不代表原始采集四序列/角色。扩散候选78对象125537564字节，先估单例1609456、cap8MiB/512MiB空间余量，实际只下一个1609460字节。完整URL/UID/许可/本地SHA与文件见P2_WADO_VALIDATION；没有官方该单实例SHA。真实DICOM留E:/BrainFusion-Data/PACS-candidates/UPENN-GBM/本run/single-instance.dcm，现用GDCM读出SIEMENS/MOSAIC896×896×1/33private/烧录缺、PatientIdentityRemovedYES及姓名等公开匿名ID，仍未证明完整脱敏或原始采集谱系。真实头部经最小协议对象验证422/unsupported_mosaic，不是实际WADO；原文件SHA不变，不入归档/病例/科研队列。源SHA bd75b6ee1175a26d0b505035da1694a2c928c7c1a53344444b24b2ca8fc11443。

首个数据helper不用Windows正常网络路由导致TLS首败，恢复正常系统网络路由后成功、仍验TLS、不改CA/系统代理。数据下载是新动作，不是重试被拒Orthanc二进制；失败及首败后检查不存在记录的日志保留，成功后才实际读头。partial/Range恢复实现但中断未验，不重复已完成下载。PyDicom主环境不存在，无新安装，GDCM有限诊断不能冒称递归脱敏审计。


## 以下为之前窗口的历史记录

## 2026-10-12 23:25窗口：读取/关联工程完成，环境阻塞保持

P2-a受限后台QIDO/UID关联和病例原UI已实施并通过65后端/隔离迁移/明确合成协议浏览器/实际未配置与最终8012静态HTTP；P2_READ_PROXY_VALIDATION定义配置/接口、证据与限制。配置PACS_CONFIG_FILE默认Runtime/local/pacs-config.json（本轮未创建），只loopback、后台Basic、主动拒无鉴权归档、固定DICOMweb根；不把凭据给浏览器。

没有新的二进制/真实DICOM下载或PACS进程。上轮环境动作自动审批受阻未变，不重复或换工具执行被拒命令。当前可独立继续P2-b脱敏入库规则/受限WADO元数据与像素代理；真实样本来源/几何/许可和归档部署仍需各自实际验收，不能用协议夹具冒充采集数据。

## 以下为之前窗口的历史记录

## 2026-10-12 22:20窗口当前来源预检

P1已验后进入P2准备。[官方Windows入口](https://www.orthanc-server.com/download-windows.php)链接到官方Windows64目录；该目录包含独立core及插件，不仅完整安装器。候选[Orthanc1.13.0](https://orthanc.uclouvain.be/downloads/windows-64/orthanc/1.13.0/index.html)的Orthanc.exe，以及[发布插件1.24](https://orthanc.uclouvain.be/downloads/windows-64/orthanc-dicomweb/index.html)的OrthancDicomWeb-1.24.dll（选固定发布版，不选mainline）。Windows证书校验HEAD为200，大小分别27,657,216与4,914,176字节，合计32,571,392；最后修改2026-08-15/08-19。具体完整URL/HTTP元信息在22:20 run/orthanc-source-head.json。

没有取得二进制、未核PE架构/发布校验和/签名/真实版本/许可内容或插件ABI。Pythonhelper缺requests，改标准库后缺本地证书issuer而失败；未安装依赖、禁TLS或改系统证书。随后下载+核验+版本探测复合命令被自动审批在CreateProcess前拒绝，仅给blocked by policy，没有进一步原因；未执行。orthanc-policy-rejection.md和失败日志保留，P2-env受阻但不重新要求已有用户授权。不能通过换工具执行同一被拒动作。下一步先推进代理/UID映射等独立工程；只有可审核动作/可用服务条件满足才做归档运行。

以下首轮候选数据准备保留；未下载真实DICOM。无需等待E5 Docker系统权限，但本轮也不能宣称Windows归档已验证。

记录：2026-10-12，run_id20261012T211814_d5bca694。仅准备，P2未验收。

有限本机探测：PATH未发现Orthanc、dcm2niix、Docker；C:/Program Files及E:/BrainFusion-Runtime/toolchains未发现Orthanc目录。Runtime中的少量.dcm来自Python/JS包测试夹具，未核实真实采集来源或四序列对应，不能用于真实患者PACS验收。已存在WAW-GliomAI NIfTI不冒充采集DICOM。此次没有下载安装器、启动归档或下载队列；E5的既有系统授权障碍保持。

优先走Windows本机Orthanc，无需等待Docker。官方[DICOMweb插件说明](https://orthanc.uclouvain.be/book/plugins/dicomweb.html)说明Windows安装包包含预编译插件；后续核对官方安装入口、具体版本/校验和/许可/是否需管理员权限，再选择可用E盘路径。[安全说明](https://orthanc.uclouvain.be/book/faq/security.html)用于冻结本地鉴权与端口边界：归档仅本机、注册凭据只在后端/本地私有配置、浏览器经现有后端代理；不公开无鉴权服务。尚未核验具体安装发行，不能写已取得/已部署。

真实脑MR候选：[TCIA UPENN-GBM](https://www.cancerimagingarchive.net/collection/upenn-gbm/)，官方列出630受试者的DICOM及CC BY 4.0，整集合约139.4 GB（页面所列总量，非计划下载量）。后续先用官方检索/下载接口选择单患者、有限序列，HEAD/清单估计实际大小；不下载全队列。保存具体患者研究匿名ID、Study/Series/SOP UID、文件数/大小/SHA、许可和引用、原始脱敏说明；再本地检查直接标识、私有标签、烧录文字与原图保留规则。未完成这些检查不导入正式归档。

四序列的角色仍需元数据与明确确认规则，不能靠SeriesDescription字符串猜。TCIA候选是否能满足现用模型同网格1mm契约尚未知；即便阅片成功也不能宣称AI桥接通过。若没有合格四序列，P3按真实解除条件报告受阻；继续P1/P2独立工程。
