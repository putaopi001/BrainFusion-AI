# P4 本地账户与不可变复核归属验收

run_id `20261015T231143_p4identity`，2026-10-15夜间。原先复核可自行填署名，本轮新复核须本地doctor角色登录，署名固定为账户显示名，记录绑定稳定账户ID/角色和原来源内容。普通匿名阅片、旧历史及现有NIfTI流程语义保持；不宣称医院身份核验或全站授权。

## 实际行为

- 新增本地账户配置/隐藏密码管理工具、登录/会话/退出API与现有报告页登录框。Cookie HttpOnly/Strict，CSRF/Origin校验；researcher无权保存医生角色复核，伪造署名被拒。
- 新复核在既有不可变snapshot_json追加review_actor，无表/列迁移。复核参与导出SHA，复核不加入被复核内容SHA；旧行无actor继续false/null，未重新标注旧署名。
- 本地配置更改、超时或退出撤销会话；后台重启需重登。归属及历史留在SQLite，角色分配不等于医师资质；professional_credential_verified始终false。
- 本机原配置缺账户，已按授权建立local-reviewer/local-researcher并生成随机密码，只留E盘私有文件；实际正式页两种登录和退出均通过，没有保存工程意见/复核。操作见[账户指南](LOCAL_REVIEW_ACCOUNTS.md)。

## 本次证据

证据根：`E:/BrainFusion-Runtime/results/nightly/2026-10-15/20261015T231143_p4identity/`，不覆盖旧结果。

| 验收 | 本次实际结果 | 文件 |
|---|---|---|
| 相关后端 | 新auth5、既有review15、report4，共24通过/4既有FastAPI弃用警告；含退出/过期/配置撤权、无秘密回显、失败限流、角色/CSRF/Origin/伪造签名、版本/历史/幂等 | tests-first.log |
| 前端 | 实际生产构建通过，保留既有大包/编解码提示 | frontend-build.log |
| 真实副本UI | 匿名401、研究员403，doctor登录、HttpOnly不可脚本读取、署名只读、伪造署名/缺CSRF403；实际表单保存新第4记录，刷新/退出重放拒绝；旧3条未认证 | identity-browser-save/validation.json |
| 实际重启 | 将工程账户配置复制到独立路径再重启，旧有效token失效，重新登录、同账户同UID仍1记录；actor/content/export/4历史一致 | identity-browser-restart/validation.json |
| 副本保存/恢复 | 17表全行快照恢复一致；其他16表全行不变，旧3复核逐字节行数据不变，只追加1条新账户复核 | identity-data-audit.json、identity-database-backup/validation.json |
| 回正式目录 | 原17表全行/原八路径保持，正常服务恢复；真实病例面板进入报告0写0异常 | original-preserved.json、dicom-report-readonly-identity/validation.json |
| 正式账户 | 默认私有配置两角色实际UI登录/按钮权限/退出，只有4次login/logout，无业务写入 | formal-account-browser/validation.json、original-preserved-after-formal.json |
| 私有账户补备份 | 正式配置独立快照SHA一致，不复制明文密码/会话；上述隔离恢复配置实际重登已验 | private-config-backup-validation.json |

截图已查看：identity-browser-save/logged-in-account.png、authenticated-review-status.png及formal-account-browser两账户PNG。截图仅对应账户框/状态区域，不假称整张报告全文或新PDF逐页通过。旧长报告PDF是上一窗口证据。

正式服务：后台10300启动UTC2026-10-15T15:26:34.1320423Z，前端22988启动15:26:34.1347366Z；Orthanc20924保持原UTC14:58:00.3932301Z。前端5179/API8012/归档8042，准确身份与日志见final-services.json及local/processes/orthanc-local/process登记。无训练/下载/推理/特征长任务。

## 执行、失败与界限

所有修改/验证/切换通过有限同步包装器。implement、browser两步退出0并finally释放；formal步骤的实际浏览器和私有配置备份已通过，但末尾审计试图用x模式再次写既有original-preserved.json，真实退出1并释放，未掩盖失败、未重复登录或备份。后续只改用新证据名做原17表/八路径审计，不覆盖原成功结果，见original-preserved-after-formal.json和文档步骤日志。此为辅助证据命名冲突，不是业务写失败。

当前P4仅此子项已验，整体仍进行中。全站病例/研究权限、实名/资质/跨机构认证、多worker共享会话、HTTPS/异机最终部署、新身份文字PDF逐页视觉、多浏览器未验。旧17表联合bundle不包含新账户配置，须补备份；没有重做650应用文件/192导入或同一来源探测。P3匹配真实四序列、E5系统授权、研究R1相关阻塞仍保持；普通DICOM不附加IDH标签要求。

## 最多五项抽查

1. 在5179的病例19归档面板查询、选检查/序列、核对空间进入阅片记录，应可匿名阅读、保存禁用。
2. 下滚用local-researcher及本机私有密码登录，应显示研究员、保存禁用；退出。
3. 用local-reviewer登录，应固定本地账户署名；不用实际保存即可核对登录/退出，正式库仍无工程复核。
4. 看本run副本save/restart截图和validation：新1条账户归属、旧3条未认证、重启后重登且重试不新增。
5. 看identity-data-audit及original-preserved-after-formal，确认17表副本恢复和原数据不变；不要公开private、credentials或backups目录。

下一轮先核对锁/原服务、反馈及Git，再收尾P2来源绑定v2真实导入分支的实际服务验证：复用获准192资料/已归档实例，不重新下载、不把协议合成通过当真实分支，不把匹配四序列门槛附加到单序列阅片。新账户补充备份自动收录仍可作为E3/E6独立后续，暂不再重复刚验的登录/PDF/17表联合恢复。
