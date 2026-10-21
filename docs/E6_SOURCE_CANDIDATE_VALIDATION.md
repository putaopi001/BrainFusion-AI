# S4增量说明（2026-10-17 12:47）

原402文件候选及其逐文件/解包/构建结果仍是10/16冻结快照。后续B1/B2修改后，本次从12个相关源文件逐项与原ZIP比较：8个路径存在于原包，0个当前文件与原包字节相同，4个路径未收录。SHA-256清单见E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1247_s4delta/current-source-delta.json。本次没有更新或替代历史ZIP，也未对全仓库/隐私或完整发布做新审计；不得把历史候选当作B1/B2后的当前发行源码。等源冻结和常驻API正常启停验证后再重建完整候选。
# E6 当前源码候选验收

2026-10-16 06:15接续，run_id `20261016T061912_source`；对应10/15夜至10/16清晨，系统UTC开工22:15:54.964907。本窗口实际耗时10.2分钟，结束以本机summary为准。E6源码候选子项已验，E6/P4整体仍进行中，P3/E5条件未变。

本轮刷新源码白名单和公开指南/六个精确架构资产，增加敏感配置/密码/token与credentials/backups目录排除；原六类凭据扫描没有豁免。已包含当前PACS、Cornerstone、本地账户、来源/内容绑定复核、快照恢复和同步工作包装器的真实未提交/未跟踪实现。修正架构说明把真实四序列桥与19病例数据恢复混写的歧义。

唯一成功源码ZIP：`E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T061912_source/candidate-final/brainfusion-source-candidate.zip`。

- 402源码/文档/精确图稿文件，2,717,900原文件字节；ZIP 1,292,471字节，SHA256 `0b9482565466c542233cb743a20ef8af3ae3fbdfebf6750b1f948e261f8a4168`。
- 审计→ZIP→实际解包，402文件名称/长度/SHA一致；源码在验证前后仍与冻结包逐文件一致。Python逐文件AST通过；未知编码/超限/重解析源保护保留。
- 原目录5项打包行为检查通过；解包主环境Python3.10.21的10个相关测试文件128项通过，0跳过/失败，4个既有FastAPI on_event警告。128包含前述5项，不计成133个独立检查。覆盖PACS协议/UID/拒绝、账户与复核、距离/视图、私有快照和联合恢复；合成夹具检查不冒称新增真实归档验收。
- 解包前端用既有Node24.21.0与依赖只做本机构建，通过并生成43文件；API明确8012，Vite native配置加载避免在共享依赖中写配置缓存。node_modules仅验收目录的E盘联接、不在ZIP内；未重新安装/更新依赖。已有大chunk警告保留，不作性能优化验收。
- 六个架构SVG/PNG/来源/渲染记录在包内；SOURCE_DELIVERY与当前架构说明所有相对Markdown链接均指向包内文件。另7处旧内部台账/历史范围等引用按document-reference-audit列为外部/未随包历史引用，未复制私有目录。
- 未包入数据库/影像/模型/科学产物、私有账户/服务配置、明文密码、环境/依赖/日志/交接/反馈/自动化提示词。实际三条本机私有密码在全部402解包文件内（UTF8/UTF16）均未发现；仅输出数量/布尔，无值。仍不是任意秘密/隐私/许可全面认证，不公开发布。

正式SQLite17表逐行签名、原账户/PACS配置/登记与三服务登记SHA保持；后端30304/UTC21:26:25.6822586、前端20208/21:26:25.6851202、Orthanc28324/21:26:16.1338304仍原进程，未切库/服务或写患者。原八路径不变，正式PACS ready/账户configured。650原文件和归档联合恢复证据复用上一轮，不重新复制或新导入192，不重复推理/提取/PDF、训练或下载。

第二小批实际核对当前源码所需环境与10/10独立CPU交付环境：后者缺pydicom，现用主环境3.0.2；torch的CPU/CUDA构建不同是既定角色差异。本次17项观测中另外15项版本相同。app的pacs_import模块在导入时需要pydicom，不能把旧52轮子锁和旧CPU环境直接叫作当前可启动环境。此轮没有补装或假称异机安装通过，下一步按已有官方缓存/SHA准备当前CPU依赖增量，再在独立环境验证，不改原CUDA与特征协议。

失败均保留：初次只读Get-FileHash打开活SQLite被占用，尚未应用代码，改用只读SQLite全表签名后成功；首次候选审计因旧协议测试含字面合成URL凭据拒绝，无ZIP，随后只改合成URL运行时组装，同一实际拒绝分支包含在128通过内。不是跳过扫描或泄漏真实凭据。正常步骤finally释放锁，没有旧holder/空等待或重试拒绝环境动作。

证据根`E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T061912_source/`：candidate-final/audit、validation、ZIP/unpacked-source；source-unit.log、unpacked-pytest.log/XML、unpacked-frontend-build.log及43文件manifest；verification、document-reference-audit、known-credential-exclusion、formal-tables/formal-preservation、main-environment/historical-cpu-environment/environment-delta、final-health/services、summary及有限工作脚本。失败candidate/audit及对应工作脚本保留。结果文档/交接在包冻结后更新，不因此重新打包或把后续状态冒充包内版本。

未验：当前源码+完整新CPU环境与数据/Orthanc的联合安装、异机/容器、可见人工抽查及P3匹配真实四序列AI。源码候选不是独立安装器；数据/模型/账户私有组合和再导入外部复核材料边界沿用[完整恢复](E6_FULL_ACCOUNT_RECOVERY_VALIDATION.md)。无需用户立即操作，无长任务；R1事实/队列和R2–R4未完整。

抽查最多三步：①只读打开candidate-final/validation.json与verification.json，确认402/128/43、SHA及非独立安装边界；②打开解包docs/SYSTEM_ARCHITECTURE_CURRENT.md及两PNG，核P3仍受阻、图稿可读；③Edge访问http://127.0.0.1:5179/case/19查询原192实例，或workstation/17?viewer=cornerstone只读切四序列，正式库不应出现工程复核或工程距离。

下一轮第一步：读取当前源码候选及environment-delta，复用已验官方pydicom3.0.2缓存/SHA和旧CPU来源锁，设计明确增量/当前环境门槛后在独立E盘目标验证当前app导入与相关测试，不重建无变化的52轮子/422前端来源或650数据包。新增任何安装/来源动作仍遵循有限同步包装器和来源保护。
