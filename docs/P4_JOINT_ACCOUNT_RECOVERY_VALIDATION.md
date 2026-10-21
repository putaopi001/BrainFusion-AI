# P4/E3 账户联合恢复接线：DICOM专用最小真实组合

run_id `20261016T010830_jointauth`；系统UTC2026-10-15T17:05:18（北京10/16 01:05:18）接续，属于10/15晚至10/16凌晨窗口。

## 本次验收范围

已实际执行新版 `snapshot_pacs_joint.py --action backup/restore`，自动收录并恢复私有账户、17表业务库、真实本机归档索引/实例、配置和导入回执；恢复目录启动真实归档/后端/现有报告页，账户登录、来源/历史归属、另存复核与重启恢复通过。损坏账户快照在创建恢复目录前被拒绝。

这是**DICOM专用的最小真实接线验收**，不是再次备份全部患者/模型/研究产物。以已有真实病例19的工程副本构造1病例/1患者、36距离/1视图/4份完整复核的17表数据库，其他病例仅从本轮自有副本排除，原库未删改。原始输入仍是获准192实例公开MR派生资料，不是合成DICOM；工程复核意见不是临床评价。

应用快照只含2个实际合同/环境文件187160字节，以及业务库；归档/配置196文件、导入状态5文件和账户配置另由真实联合工具收录。计划守卫明确拒绝扩展至旧650文件的重复复制。恢复后病例19只使用恢复的业务库/空上传目录/空任务目录，模型、研究、原数据表和科学gate继续作为明确的原目录外部前提通过启动检查；本轮无AI执行，不宣称整套NIfTI/模型/研究包重新恢复。10/15旧完整650文件组合仍是独立历史证据。

## 修复与实际行为

修复 `snapshot_system.restore` 没有恢复清单声明的空目录：即使无文件，也创建经safe_target限定的uploads/feature_jobs/model/research/dataset等根目录。以前这种合法快照恢复后会缺运行目录；不通过放宽启动前检或引用不存在模型来绕过。新增独立空目录/原库字节保护测试，保留原路径越界、覆盖和校验失败保护。

联合备份使用LOCAL_AUTH_FILE的既有自动收录分支，不手工给成功bundle拼账户。新manifest固定账户子清单SHA；恢复生成local-auth/runtime.json。读取该额外环境路径后实际登录已恢复的工程账户，账号ID与旧第4条复核actor一致；署名只读，保存新第5条后内容SHA不变、导出SHA更新。旧4条及其完整快照逐行保留，其余16表不变。实际后台重启后新记录/actor/来源/导出摘要保留，旧有效会话失效、重登成功、同UID重试仍5条。

正常回正式路径后实际核对PACS ready、原候选及账户配置，不仅检查PID/八路径。原17表全部行、原归档storage/index/配置、来源完整身份副本、工程账户、正式账户/登记均保持。额外PACS/LOCAL_AUTH_FILE在finally显式恢复已核对原路径，避免上一轮null被.NET转成空字符串的问题。

## 本次证据

证据根 `E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T010830_jointauth/`。

| 验证 | 实际结果 | 证据 |
|---|---|---|
| 相关测试 | 新空目录行为+原系统/账户/归档快照，共17通过/4既有弃用警告 | snapshot-tests.log |
| 最小应用范围 | 17表、1病例、36距离/1视图/4复核，只有2文件187160字节 | fixture-plan.json、minimal-plan-guard.json |
| 真CLI联合备份/恢复 | 196归档配置、2应用文件、5导入文件，自动账户manifest/字节/runtime路径通过 | joint-backup.log、joint-restore.log、joint-account-copy-audit.json |
| 账户损坏拒绝 | 复制必要清单构造明确损坏夹具，实际CLI非零退出1，未创建输出；成功快照不改 | joint-account-negative.json、bad-joint-account-restore.log |
| 旧科学/版本字段 | 原17表快照/恢复逐行与原缩小夹具一致，空目录恢复存在 | application-fields-audit.json |
| 真实浏览器 | 恢复账户登录、36距离/4旧复核/内容和导出版本一致；新增1条来源绑定复核、刷新 | joint-account-browser-save/validation.json |
| 实际后台重启 | actor及第5条不丢、旧活会话失效、重登及同UID幂等 | joint-account-browser-restart/validation.json |
| 行数据保护 | 旧4条原行/其他16表不变；原完整身份源库、工程账号和正式库/归档/配置原件不变 | restored-save-audit.json、source-and-original-offline-preserved.json、formal-original-preserved.json |
| 正式入口 | 回原目录病例19面板进入报告0写/0页面异常，无测试复核渗入 | dicom-report-readonly-after-joint-account/validation.json |

步骤全部有限同步包装器执行，成功退出0/finally释放；负例的预期CLI失败单独验明，不把它当整个步骤成功或吞掉未知错误。没有重试/绕过被拒Orthanc环境动作、没有新导入/来源探测/分割/特征/训练/PDF/构建或依赖安装。

私有bundle `E:/BrainFusion-Runtime/backups/20261016T010830_jointauth/` 含服务凭据/账户摘要及单独测试会话token，不公开。备份snapshot内不含明文初始密码或有效会话；恢复登录使用本机原已知工程密码。`restored-source-bound-review.png`为局部元素截图，已查看，只作本地账户/非医师资质说明的辅助图，不冒称完整报告/PDF排版验收。

## 最多五项抽查

1. 正式 http://127.0.0.1:5179/case/19 进入归档/报告，应仍原候选和正式空复核，不出现工程第5条。
2. 看CLI备份/恢复及joint-account-copy-audit，确认是自动账户收录、17表和2文件最小范围。
3. 看两次真实浏览器validation及局部状态图，确认恢复账户/来源/历史与重启后重登。
4. 看损坏账户负例未创建输出及旧4条/原17表/归档SHA保护，不公开私有bundle。
5. 本机已装Edge只读阅片子项见[Edge范围](P4_EDGE_READONLY_VALIDATION.md)，不把其只读通过外推到Edge保存/PDF。

本接线子项已验。完整多病例含账户的新联合bundle及异机/容器仍待最终交付窗口验证；不要因这个剩余项每轮重做650文件或同一192导入。P3真实匹配四序列及E5原系统授权阻塞继续保留，P4/E6整体未完成。
