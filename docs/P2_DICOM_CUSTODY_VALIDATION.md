# P2-b3 隔离保管与恢复验证

## 2026-10-13 02:15窗口（10/12夜至10/13凌晨）

run_id 20261013T021550_d6134bcb；操作系统 UTC 与原生锁进程启动值见 lock-acquired.json，FileShare.None holder/owner18708，session75448；结束/耗时/释放见 summary.json。P2-b3隔离保管工程已验收，P2整体仍进行中、P2-env受阻，P1受支持NIfTI已验收，P3/P4待实施；历史F/E验收保留，E5受阻/E6进行中、R1待核查/R2–R4待实施。无新用户反馈，不改 REVIEW_FEEDBACK，不提交/发布。

新增 backend/app/services/dicom_custody.py、backend/tools/retain_dicom_candidate.py、backend/tests/test_dicom_custody.py；预检增加 source_uid_binding_verified，仅表示文件UID与声明/文件元信息匹配，不代表发布者认证。新工具将有UID绑定的候选快照留在 E:/BrainFusion-Runtime/dicom-quarantine/<独立目录>，SQLite账本与业务库分离，内容SHA寻址、同卷原子无覆盖发布、BEGIN IMMEDIATE串行写。相同SOP/字节重试新增收据，不重写对象；SOP不同字节/父UID、Series改属Study明确拒绝；缺失/损坏对象不静默修复。manifest/review仅声明，所有结果 archive_eligible/archive_imported 恒false，私有属性候选仍只能隔离保管，不提供浏览器原文件或PACS上传入口。

最终147项相关后端检查通过、4既有警告；19个新增保管行为含真正跨Python进程重试与独立进程检查、父UID冲突、声明UID不能污染账本、审计/manifest/对象/父映射损坏检测、未提交完整对象重试接管、隔离副本恢复。第一次账本INSERT占位数量错误已定位修复，backend-first.log保留；139是补充前历史，最终backend-accepted.log为147。崩溃残留用明确夹具模拟，未声称真实断电恢复或对抗本机管理员篡改。

实际复用上一轮UPENN公开单实例，原字节1609460、SHA bd75b6ee1175a26d0b505035da1694a2c928c7c1a53344444b24b2ca8fc11443；首次/重复各独立CLI进程，1实例/2收据，source_uid_binding_verified=true但预检rejected、没有pixel-review，未进入PACS/病例/研究队列。继而用SQLite只读源backup API和字节文件复制备份，再恢复至新独立目录，独立进程检查通过，3张保管表全行与原源一致、对象与候选逐字节相同、原保管目录库存SHA不变。只验隔离保管恢复，不代替P4真实Orthanc索引/原文件与业务库联合恢复。

state-validation：原业务14表全行与已验快照相同、原MRI/mask/空间夹具和featurejobs SHA相同、依赖版本不变。现有后端34700（UTC2026-10-12T16:43:06.8049752Z）、前端22108（UTC16:43:06.8122342Z）身份/健康由既有脚本核验复用，无服务重启、新下载/安装/构建/浏览器重复验证/模型任务；无新的浏览器验收或截图，保持上一轮历史证据。


证据目录：E:/BrainFusion-Runtime/results/nightly/2026-10-13/20261013T021550_d6134bcb/

- backend-accepted.log：最终147项相关检查；backend-first.log保存已修复失败，backend-related.log保存139项历史。
- real-candidate-receipt-first.json / real-candidate-receipt-duplicate.json：真实候选的两张保管收据，均未归档且预检拒绝。
- real-custody-audit-1.json / real-custody-audit-2.json：与保管快照SHA绑定的脱敏报告，仅标签路径/原因，无字段原文；没有真实像素复核记录。
- real-custody-independent-inspection.json / custody-restore-validation.json / custody-restore-rows.log：独立进程、隔离备份与恢复；只证明隔离账本，不是实际PACS。
- state-validation.json / services-reuse.log：原业务/科学/任务/依赖和服务身份不变。

## 本地使用与抽查

该工具是本机隔离保管工具，不是脱敏器、审批系统或PACS导入器。原始候选可能含身份信息，隔离原字节不放浏览器、不复制到交付输出、不进入病例或科研队列。source/review和本地账本不是独立身份认证；管理员可修改本机文件，本轮未声称防篡改安全证明。真实Orthanc部署、可信来源与审核权威、支持DICOM、真实阅片及四序列AI仍未验收。

1. 打开 http://127.0.0.1:5179/case/17，刷新本地归档面板，预期仍明确未配置/不可用；本轮保管不会使PACS变成已连接。
2. 打开 http://127.0.0.1:8012/docs，GET /pacs/status 预期归档不可用、导入/真实阅片能力未开启；不把设置字段等同实际能力。
3. 在项目 backend 目录执行下方只读检查，输入本轮真实保管目录，预期 instances=1、receipts=2、integrity=verified、archive_imported=false。无须重新下载或重复保管。
4. 查看本指南同目录收据与恢复摘要：预检 rejected，没有像素批准；备份/恢复 all3_tables_all_rows_equal_source=true、actual_pacs_and_business_db_joint_restore_verified=false。

只读命令（不改变库或原文件）：

    & 'E:/BrainFusion-AI/.conda/brainfusion/python.exe' 'E:/BrainFusion-AI/backend/tools/retain_dicom_candidate.py' --store 'E:/BrainFusion-Runtime/dicom-quarantine/20261013T021550_d6134bcb-real' --inspect

如确需保管新合法候选，--input 和 --source-manifest 必须显式给出，--store 仅接受 dicom-quarantine 内独立目录。manifest SHA必须匹配原字节且其3UID必须匹配文件/文件元信息；私有/像素审核或布局失败仍记录为隔离，不允许上传。CLI退出0仅表示保管完成/检查成功，必须看 storage_role 和 archive_imported，不解释成脱敏通过。参数/存储/UID冲突退出3且只显示具体安全原因，不打印原字段/路径异常全文。

## 未完成及接续

P2-b仍需真正归档导入、可信来源/像素审核授权、实际Orthanc重复规则与持久化、支持的真实DICOM浏览器；当前真实候选是MOSAIC，不用于WADO/模型。P3匹配真实四序列、P4完整恢复/性能/PDF、E5/E6和R1–R4未完成。

Orthanc官方二进制下载及版本执行曾被自动审批拒绝，反馈仅 blocked by policy；本轮没有重试或换工具绕过。需可审核环境动作或已装可用服务解除，当前独立开发无需用户重复授权。没有正在运行的下载、训练、推理、构建任务。

下一步：核对同一开发锁、反馈和服务身份，继续P2实际导入前的归档目标身份、响应UID/文件SHA核对、重试与失败恢复契约；先在明确隔离协议夹具验证，不能把本机隔离账本冒充Orthanc已入库。来源/像素复核身份和审批不由调用者manifest自授权。
