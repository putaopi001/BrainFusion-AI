# P2 来源绑定v2真实导入验收及支持范围

run_id `20261016T000514_p2v2`，系统UTC2026-10-15T16:03:46/北京时间10月16日00:03:46接续，属于10/15晚至10/16凌晨窗口。

## 本次结论

P2在下列明确支持范围内已验收：本机鉴权Orthanc1.13.0/DICOMweb1.24、登记过来源与完整像素技术复核的公开CC BY4.0经典MR派生资料、单帧/未压缩/非MOSAIC/统一规则空间序列；通过本机准备/登记工具导入现有病例面板，再显式检查关联后Cornerstone阅片。不要求IDH标签、四序列或模型输入身份。

新资料必须经过来源绑定准备v2；历史固定SHA登记继续兼容，不改写原来源或审批。当前受控导入最多512实例/256MiB未压缩像素等边界以实际代码为准。任意浏览器DICOM上传、自动像素脱敏、压缩/多帧/MOSAIC、不规则空间、医院现网PACS不在此验收范围。P2已验不代表P3真实四序列AI桥或临床脱敏认证已通过。

## 实际完成的行为

10/14真实v2资料之前只准备/隔离登记，本轮补其未覆盖的真实服务分支。复用已完成技术查看的192实例v2包，复制到新的E盘隔离资料目录；来源、准备报告、技术记录、六张PNG及原像素全部原字节保留，没有新下载、生成UID或重写观察/审批。技术复核仍是当时Codex AI工程观察，不是新医生审核。

在新的私有归档副本和业务库副本中，经实际登记CLI和病例页导入。先只改测试副本一张PNG的尾字节，实际POST被409拒绝，归档仍192实例、无新回执；finally恢复该PNG原SHA。随后真实UI导入v2，新增192/回读192/已存在0，隔离归档总数384，旧192实例ID保留；没有重做日常旧候选导入。

刷新时观察到running，随后同一持久回执成功。显式病例关联后通过现有空间入口进入Cornerstone三视图，192个实际帧请求全部200，9,437,184体素与独立pydicom按原IOP/IPP物理排序/原rescale解码的Float64摘要完全一致。实际后台及隔离Orthanc重启后同一回执、病例关联和192实例manifest保留，没有第二次导入请求。

当前新回执服务耗时1.345秒（含该192实例归档写入、逐份回读和末核，不是纯上传耗时）；UI观察至成功2.777秒，阅片入口至ready5.448秒。仅此小样本/本机观察，不能外推医院队列吞吐或模型推理速度；无模型/特征/GPU任务。

## 数据保护与证据

证据根 `E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T000514_p2v2/`。

| 检查 | 本次实际结果 | 文件 |
|---|---|---|
| 新v2来源包复制 | 原资料/试验副本全文件SHA一致，原审批/像素/几何不变 | copy-validation.json、v2-original-source-pins.json |
| PNG变化拒绝 | 实际服务409；实例/回执数量不变；只测试副本临时变化后复原 | real-v2-review-tamper.json |
| v2真实首导 | UI首次真实导入192新实例、回读192、running刷新后同回执成功 | v2-browser-import/validation.json、imports/*/state.json |
| 显式关联/三视图 | 新增1条工程关联，其余16表不变；192帧/全9,437,184体素一致，0页面异常 | v2-browser-resume/validation.json、v2-positive-state.json |
| 实际双服务重启 | 原v2回执/关联/manifest保留、0写请求/0页面异常 | v2-browser-restart/validation.json |
| 原目录保护 | 两轮切换都回正式服务；17表全行/八路径/原归档实例集合保持；停机期间原storage/index全文件SHA保持；原登记/账户/来源v2包不变 | original-offline-preserved[-retry].json、original-final-preserved[-retry].json |
| 正式UI | 现有病例19面板到报告只读，仍原候选/回执，无v2工程关联/测试资料 | dicom-report-readonly-after-v2/validation.json |

新试验归档仅复制原storage/index共194文件/19,576,832字节，另存两配置；业务17表小库单独快照，没有重复650应用文件的完整联合恢复。私有归档目录E:/BrainFusion-Runtime/backups/20261016T000514_p2v2/，含凭据不得公开。正式路径/候选仍原样，新v2工程记录不混入日常库。

最初浏览器工具在已成功导入/刷新后，对Element Plus隐藏原生checkbox使用check导致超时；保留失败validation和PNG，有限步骤真实退出1并finally回正式服务/释放锁。读取控件源码改点可见label后，仅续接已有成功回执完成关联/阅片，没有重复导入。resume最终通过，首次记录status failed不能单独当整条流程通过，组合证据见上表。没有更改产品或放宽来源保护来规避失败。

最终正式UI检查另发现：原八路径和文件虽一致，额外PACS环境变量用.NET恢复null后变成空字符串，PACS实际返回invalid_config；因此先前进程存活/底层行数检查不足以验收服务恢复。独立非敏感环境探针已复现null→空值。已显式恢复三个原PACS路径并正常重启应用，ready/原候选/本地账户配置及正式页面0写通过，见null-env-restore-probe、formal-pacs-restored、formal-account-restored与final-services-restored。原配置文件未改，未放宽鉴权。以后空值应Remove-Item Env:相应变量，或显式已核对原路径，不能只按空元信息启动就声称恢复。

截图：v2-browser-import/v2-new-import-receipt.png、v2-browser-resume/v2-three-views.png、v2-browser-restart/v2-restart-receipt.png已保存；前两图已查看。历史旧候选去重/失败恢复与来源防护测试是之前验收证据，本轮未重复并冒称新增。

## 接续独立E3小批

新增私有账户备份工具及联合快照自动收录/恢复代码，保持旧manifest兼容。4个新行为加5个auth及9个既有归档快照检查共18项通过/4既有警告；真实两账户配置backup/restore SHA一致，不包含明文密码或有效会话。首次测试把备份放在源目录之下，四项被保护拒绝；改为兄弟私有夹具目录后通过，生产约束未放宽，失败日志保留。详见[账户备份增量](LOCAL_REVIEW_ACCOUNTS.md)。没有本轮完整新版联合bundle重建/活服务恢复，不把组件通过当新版整体恢复。

## 抽查与下一步

1. 正式 http://127.0.0.1:5179/case/19 查询/选原检查与序列，应仍原192实例，不出现本轮v2工程关联。
2. 查看新v2导入回执PNG：新增192/回读192，且验证记录明确隔离目录。
3. 查看新v2三视图PNG、全体素独立摘要、重启0写validation。
4. 核原17表/八路径/归档/来源包保护记录，勿公开private/backups目录。
5. 查看auth-snapshot-tests-final及私有配置CLI成功摘要；旧联合bundle无账户不能当作新版。

P1/P2各受支持范围已验，P3真实匹配四序列/E5原系统授权仍受阻，P4/E6及研究R项未整体完成。下一轮不再重复192下载/旧导入/来源探测、这次v2分支或原PDF；先核对账户自动收录新组合的最小可独立验证，再推进P4剩余浏览器/交付项。没有新增外部数据解除条件时保留P3一次阻塞，继续独立系统工程。
