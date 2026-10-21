# P2-b4 只读归档核对与病例关联标识验证

## 2026-10-13 03:18窗口（10/12夜至10/13凌晨）

run_id 20261013T031824_36706fc0；FileShare.None实际持有者/owner25212、原生UTC2026-10-12T19:18:23.8712271Z、开始UTC19:18:24.482057Z、session90335；结束/耗时/正常释放见summary/lock-released。无新反馈，不改REVIEW_FEEDBACK，不提交/发布。

P2-b4只读归档核对工程与P2-a1可选服务标识绑定已验收：新增 services/pacs_reconcile.py、tools/reconcile_pacs_candidate.py、tests/test_pacs_reconcile.py；pacs_client.py增加可选服务端 expected_database_server_identifier，并在连接时核对，显式设置后纳入现有病例关联fingerprint。未配置该字段仍保持旧origin SHA；加pin/改pin不自动重绑定旧记录，返回mapping_conflict。无数据库表迁移/浏览器凭据/自动首次信任。

核对工具从已验隔离收据只读取得UID/SHA/大小，经后台强制鉴权、固定逻辑服务标识，检查不覆盖/无摄入转码策略，用只读POST /tools/lookup取得唯一Instance，再核对Instance→Series→Study的UID与归档原文件完整字节SHA，结束时复查目标和UID映射。查询失败/404/空body/断连不是“不存在”；返回matched_existing、absent_at_check、conflict或unresolved。匹配只是时间窗口内已见相同文件，不表示本工具上传、候选批准或模型输入合格；upload_allowed和archive_imported_by_tool恒false。没有POST /instances、DELETE、修改/去标识/写回归档。

最终184相关后端检查通过/4既有警告，较上轮新增37行为（34归档核对含真实CLI/合成Part10、3旧关联pin回归），明确TCP协议夹具不是Orthanc。断连后新进程只读重查成功、首个失败观察文件不覆盖、父UID/hash/策略/目标变化和非法返回路径明确拒绝，旧配置fingerprint保持，同origin换pin不覆盖旧病例关联。首轮新测试误用confirmed字段，返回422；依据既有acknowledge_case_match契约修正测试，失败backend-related.log保留，最终backend-accepted.log通过。

真实UPENN候选只读收据核对实跑退出3、unresolved/unconfigured、verified_present_at_check=null、原preflight=rejected、candidate_approval_verified=false；没有私有PACS配置或真实服务，更不能称已保存/缺失。原隔离目录所有文件SHA不变，仍1实例/2收据，原候选字节SHA不变；原业务14表全行、MRI/mask/空间夹具/featurejobs SHA和依赖版本不变。backend34700/frontend22108的PID/原生开始时间/健康由既有脚本复用，未重启；本轮新pin API逻辑在隔离新进程验证，正在运行的PACS模块没有重载，不宣称真实归档或新pin浏览器验收。无新下载、安装、前端构建、模型长任务。

独立P2-data核实：复用已装官方pydicom3.0.2 wheel内MR_small.dcm，9830字节、64×64，原文件和README逐字节匹配发行wheel。发布者说明源为NEMA WG04 MR1_UNC、经过缩小处理；这是发布者加工的工程测试材料，不能称本系统取得了原始采集队列。经典MR头部布局检查与8192像素字节长度匹配，仅布局通过；原始患者许可/完整去标识、缩小后物理几何/像素复核/匹配四序列均未独立核实，原预检仍rejected/归档false，不伪造TCIA source-manifest、不复制/下载原文件、不加入病例或模型。本轮不据低分辨率样例报告临床性能。

P1 NIfTI已验、P2整体进行中/P2-env受阻、P3/P4待实施，匹配真实DICOM四序列端到端仍缺数据条件；F/E历史验收保留、E5受阻/E6进行中、R1待核查/R2–R4待实施。实际Orthanc部署/导入/真实DICOM浏览器、可信来源与复核、联合恢复/性能/报告未完成。自动审批曾拒绝Orthanc官方下载+版本执行，仅blocked by policy，本轮未重试/绕过；解除需可审核环境动作或已装服务，不要求用户重复一般授权，无即时用户动作/正在运行的长任务。

下一轮第一步：核对开发锁/反馈/服务，读pacs_wado与已装Cornerstone DICOM加载器，继续P2-c1受支持成组实例的FrameOfReference/方向/spacing/物理排序与明确拒绝，再接入既有阅片入口。归档/来源条件可用时优先真实验证，不反复空查询/安装/打包；不得把工程或加工样本冒充真实四序列闭环。


## 边界及官方接口

采用[Orthanc官方API](https://orthanc.uclouvain.be/api/)规定的系统状态、UID查询、父资源层级和原文件读取，固定官方OpenAPI副本及SHA见 primary-source-records.json/orthanc-openapi.json。/tools/lookup 虽使用POST，语义是查询，本工具不执行上传。此处强制不覆盖和不摄入转码是本系统准备契约，不声称所有Orthanc应用都必须如此配置。

DatabaseServerIdentifier 是可配置逻辑服务器标识，不是不可伪造的数据库UUID；同标识重建归档无法仅靠它识别。本轮输出 database_identity_cryptographically_verified=false，不宣称固定地址/pin即完整数据库身份或防篡改证明。核对结果只说明已观察时间窗口，不能锁住其他归档写入者，也不授权重发上传。

原[发布者MR测试数据说明](https://raw.githubusercontent.com/pydicom/pydicom/v3.0.2/src/pydicom/data/test_files/README.txt)记载縮小样例和测试分发用途；作者认为可测试的说明不是独立原患者许可，库的许可证也不自动替代原图像许可。详细角色和SHA见local-derived-mr-source-check.json，未取得原MR1_UNC。

## 证据与当前运行状态

证据目录：E:/BrainFusion-Runtime/results/nightly/2026-10-13/20261013T031824_36706fc0/

- backend-accepted.log：184通过/4既有警告；backend-first.log为初版32通过，backend-related.log为已修复测试字段误用的历史。
- real-candidate-reconciliation.json/.log：已保管真实候选、实际未配置环境，退出3且未核实结果。
- readonly-record-validation.json：旧隔离目录/候选SHA不变，1实例2收据，未真实归档。
- state-validation.json/services-reuse.log/live-pacs-status.json：原业务/科学/任务/依赖不变，真实当前PACS仍未配置/no-store。
- local-derived-mr-source-check.json/.log/local-derived-mr-preflight.json：已有加工测试材料的有限核查，不是采集/浏览器/AI验收。

服务仍 http://127.0.0.1:5179/case/17、http://127.0.0.1:8012/docs；无正式PACS配置。新CLI每次是新进程，可直接使用；正在运行的后端未重载新增pin代码。今后正式启用配置须按既有备份/启动脚本核对后重启、真实服务及相关浏览器验证，不将隔离API通过当当前浏览器通过。

## 抽查（对应03:18窗口）

1. 打开 http://127.0.0.1:5179/case/17，刷新归档面板，预期仍明确未配置。
2. 在 http://127.0.0.1:8012/docs 执行GET /pacs/status，预期state=unconfigured、read_available/import_available=false。
3. 打开同目录real-candidate-reconciliation.json：state=unresolved、reason=unconfigured、verified_present_at_check=null、candidate_preflight_decision=rejected、upload_allowed=false。
4. 查看readonly-record-validation.json，预期原隔离目录SHA未变、1实例2收据、真实PACS未验收；查看测试材料摘要，native_acquisition_verified=false、clinical_cohort=false。

如需自己重复只读核对，必须用新输出名（已存在会在网络请求前拒绝）：

    & 'E:/BrainFusion-AI/.conda/brainfusion/python.exe' 'E:/BrainFusion-AI/backend/tools/reconcile_pacs_candidate.py' --store 'E:/BrainFusion-Runtime/dicom-quarantine/20261013T021550_d6134bcb-real' --receipt-id '9f83341f0c2843359f42c5a006498c81' --output 'E:/BrainFusion-Runtime/results/nightly/2026-10-13/20261013T031824_36706fc0/user-readonly-check-01.json'

当前预期退出3并记录unconfigured；不要改成成功提示。输出不显示密码、归档原字段、像素或原文件；无论未来matched_existing或absent_at_check都没有上传许可。文件数增加仅为独立观察证据，不改变保管账本。

正式配置是本地服务端PACS_CONFIG_FILE；本轮只增加可选expected_database_server_identifier schema，不自动写pin或打开allow_pixel_read。默认像素/原文件核对禁用；两个字段需基于实际服务和数据审核配置，不能从浏览器/候选manifest自授权。旧关联因加pin失配时保留历史，审计重绑定尚未实现，不删除旧行来解决。
