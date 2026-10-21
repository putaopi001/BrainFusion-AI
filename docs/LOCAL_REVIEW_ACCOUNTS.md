# 本地复核账户与角色

## 10/16 05:18：原正式两账户在完整数据组合中恢复

[当前完整恢复](E6_FULL_ACCOUNT_RECOVERY_VALIDATION.md)收录650应用文件/19病例/17表、196归档配置、导入回执和原正式两账户，独立启动NIfTI/DICOM与科学API、账户登录/第7条工程复核、归档/应用重启及幂等通过。旧6条工程actor保持其历史归属，不改成当前账户或医师资质；新复核只写副本，正式库/账户不变。原件全SHA和规范化科学字段保护有证据。

仅数据组合，不复制源码/完整Python/Node环境/Orthanc程序；再导入来源材料是固定SHA的外部前提。私有snapshot不得公开，明文密码/会话不入snapshot，恢复后必须重新登录。不要把本轮通过写成所有部署/异机条件都满足，也不要再称完整新账户数据组合从未实测。

## 10/16 02:07：Edge关闭与退出语义已验

[实际Edge验收](P4_EDGE_PERSISTENCE_VALIDATION.md)使用新的E盘专用持久配置：关闭整个浏览器再开、原后端仍运行且会话未到期时，可恢复登录及已保存复核。显式退出后再关闭重开仍为未登录、不能保存。会话上限8小时，后端重启清会话，不能用“关闭恢复”保证永久免登录。新身份三页PDF已逐页查看，本地账户验证仍不等于医师资质/临床签章。私有测试profile不进入仓库或公开证据。

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

更新：2026-10-15 23:30窗口；run_id `20261015T231143_p4identity`。这是现有DICOM阅片报告的本地账户验证，不是医院全站权限系统、实名身份或医师资质认证。

## 使用

1. 打开 `http://127.0.0.1:5179/case/19`，归档面板查询检查、选择检查和序列、核对空间，进入“DICOM 阅片记录 / PDF”。匿名可继续阅读，保存人工复核需登录。
2. 下滚到“记录本版本人工复核”。本机已建立 `local-reviewer`（doctor角色）和 `local-researcher`（researcher角色）。初始随机密码只在本机E盘的 `E:/BrainFusion-Runtime/local/credentials/20261015T231143_p4identity-reviewer.password.txt` 和相应 `-researcher.password.txt`；未在日志、网页、仓库或本文写密码。请由本机使用者读取，勿公开分享这些文件。
3. 登录后署名由账户显示名确定，只读。研究员可读，不能保存此医生角色复核；本地复核账户核对来源/距离/病例意见后填写意见、选择结论并确认，保存会另存不可变版本。手动保存会写日常库；本轮自动验收只在副本保存。
4. 页面明确显示“本地账户已验证、未核验医师资质”。旧三条工程副本历史继续标为“未认证历史”，不会给历史自行署名补造认证。正式库没有工程复核/工程长意见。
5. 刷新保留有效登录；退出立即撤销。会话最长8小时，后台服务重启必须重新登录，已经保存的账户归属和内容/导出版本继续存在。更改账户配置也使已有登录失效。

当前权限只约束DICOM人工复核POST。普通DICOM阅片不要求IDH标签或四序列；其他病例/研究/意见等接口仍是本机原型访问范围，没有整体增加登录拦截。部署到多用户/公网前仍须另行完成全站授权与HTTPS部署验收。会话只支持当前单后端进程，不适用于多worker共享。

## 本机维护账户

账户配置默认 `E:/BrainFusion-Runtime/local/local-users.json`，可用进程环境变量 `LOCAL_AUTH_FILE` 指定另一个E盘私有JSON。配置保存盐化密码摘要，不在SQLite增加账户表；不得放入前端静态目录、Git或公开交付包。登录页没有自助注册或修改角色接口。

本机维护者在项目根使用主Python的 `backend/tools/manage_local_users.py`，指定 `--config`、`--username`、`--display-name`、`--role doctor|researcher`。不指定 `--password-file` 时用隐藏输入两次设12至128字符密码；自动化时只能用明确E盘私有小文件，不把密码放命令行。修改已存在账户需显式 `--replace`，保留原账户ID；默认拒绝覆盖。用户名限3至64个英文字母、数字、点、下划线或横线。更新时工具用独占字节锁与原子替换。

常规账户维护、测试及服务启停仍由 `backend/tools/run_development_step.ps1` 执行有限同步工作脚本，脚本内先核对当前配置/交接基线。不要直接替换已有配置，不调用退役的后台holder。要停用账户，由本机维护者在同一锁保护步骤将对应 `disabled` 设true并保存有效配置；勿删除历史复核记录。账户角色只是本机权限分配，不能将自动建立的“本地复核账户”解释为某位真实医生。

## 备份与恢复

账户文件是第17表联合备份之外新增的私有配置。本轮另存 `E:/BrainFusion-Runtime/backups/20261015T231143_p4identity-auth/local-users.json`，SHA一致；不包含明文初始密码或有效会话。历史联合备份工具尚未自动收录该文件。执行新的完整备份时必须补存当前 `LOCAL_AUTH_FILE`，或恢复后按本机工具重建账户；不能声称旧17表备份自带新账户。

复制账户配置须在本机配置维护锁保护的有限步骤完成，先确认无并行配置维护、源文件SHA/用户状态，再复制到新的私有备份目录并复核SHA，不覆盖旧快照。恢复到独立E盘路径后设置 `LOCAL_AUTH_FILE`，正常启动后重新登录；不从备份恢复内存会话。本轮工程配置复制到 `private/restored-local-users.json` 后实际后台重启/浏览器重新登录通过；正式账户补充备份做字节SHA核对，未冒称完整新联合bundle已再验。

## 实现与验证范围

PBKDF2-HMAC-SHA256采用600000次迭代、16字节随机盐；依据[Python hashlib API](https://docs.python.org/3.10/library/hashlib.html)与[OWASP密码存储说明](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)。Cookie使用HttpOnly、SameSite Strict，HTTPS请求时Secure；状态更改校验会话CSRF及允许Origin，参考[OWASP会话管理说明](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)。本机HTTP方案不等于已验公网安全部署。

相关24项后端检查及构建通过；真实浏览器角色、签名/CSRF拒绝、旧历史、重启/登录和正式只读验证见[P4本地账户验收](P4_LOCAL_REVIEW_IDENTITY_VALIDATION.md)。认证文字DOM与截图已核，未本轮重新导出/逐页检查PDF，不借用旧长PDF作为新身份文字的视觉证据。
