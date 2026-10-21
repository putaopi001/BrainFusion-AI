# P3转换版本重开与病例来源工程验收

窗口：2026-10-13 07:11；20261013T071140_7484539d。P3-b2a/b2b工程通过，真实归档/匹配四序列/审核/AI激活未验；P4-n1为单个真实NIfTI病例阅片观测。

实际页面：http://127.0.0.1:5179/case/17；http://127.0.0.1:5179/workstation/17?viewer=cornerstone；API：http://127.0.0.1:8012/docs。

本轮新增backend/app/services/dicom_conversion_integrity.py、dicom_conversion_registry.py、tools/inspect_dicom_conversion.py及行为检查；app/api/pacs.py、core/config.py、原PacsPanel.vue接入；frontend/tools/verify_conversion_source_panel.mjs、benchmark_cornerstone_nifti.mjs与既有三个PACS/DICOM夹具新增无转换版本响应。未新增另一套UI、业务表、依赖或模型。

本地核对始终是只读；成功verified_readonly不表示已认证医生、真实归档/许可/像素审查通过，model_input_eligible=false。索引是本地服务端保留的声明，默认不存在；无浏览器路径参数、公开登记/激活接口或合成病例绑定。登记在metadata-snapshot分支的API测试仍用自有合成像素与隔离库，不能当真实DICOM。

报告需要外部保留SHA，重新核对当前四序列规划/来源、原快照与NIfTI每体素，并在结束复查文件；missing/unavailable、stale、invalid分开。固定版本文件名，拒绝路径重定向，预算与有界gzip展开防止异常文件无限读取。仅支持原转换器生成的NIfTI1单文件float32/mm/352偏移/无扩展/显式不再缩放协议；不尝试修复、重采样或转换任意NIfTI。原临床NIfTI入口不受此派生版本限制。

新增只读接口：GET /pacs/cases/{case_id}/conversions；GET /pacs/cases/{case_id}/conversions/{version_id}/inspection。前者只列登记状态，integrity_status=not_rechecked，不凭文件存在判通过；后者核对病例/当前配置/检查关联后检查本地版本，结束复查登记/配置/关联。单后端进程文件检查互斥、忙时409重试；所有结果no-store，服务端路径/私有内容不返回。live_archive_reconciled仍false，没有把固定配置对应说成实际归档字节一致。

服务端DICOM_CONVERSION_INDEX_FILE可由环境/.env显式配置，默认E:/BrainFusion-Runtime/local/dicom-conversions.json；最多32条、1MiB、strict JSON。格式dicom-conversion-index-v1/entries；每条version_id、case_id、archive_id、archive_fingerprint、study_uid、version_dir、report_sha256、proposal_path/proposal_sha256、snapshots_path/snapshots_sha256。路径只在服务端E盘，不允许重定向；SHA是审计锚不是签名。真正来源审核/登记写入/当前归档重核对与AI激活还要后续实现，本轮没有创建实际索引。

独立CLI：E:/BrainFusion-AI/.conda/brainfusion/python.exe E:/BrainFusion-AI/backend/tools/inspect_dicom_conversion.py --version-dir <版本E盘目录> --report-sha256 <外部保留64位SHA> --proposal <当前声明JSON> --snapshots <当前来源JSON> --output <全新E盘JSON且位于版本目录外>。不覆盖任何输入或已有结果；输出以外不写源文件；exit0为verified_readonly，exit3为失效/不可用/无效，已有输出exit2。不能重新计算刚被改过的报告SHA就称其可信来源。

验证：135相关检查+额外1项可选依赖缺失隔离检查通过（不同日志，不重复计已有子集）；4既有警告。首次测试清理DetachedInstanceError已修正并保留日志。上一轮外部副本报告锚6e0991a3e7d454b44ce6713d72c5a5ca510d3979b9fceb025748eb40ba78927b，新进程重开原合成版本72体素0差，原版本未改。

真实页面dev/生产预览通过；合成协议只用于成功/失效/无效/断连/错身份/晚响应的UI行为，未写实际病例。一次实际构建成功（chunk警告保留），预览服务已停止、原dev已恢复；相关旧DICOM工程阅片UI回归也通过。图片actual-case-source.png与existing-real-nifti.png已实际查看。

P4单病例实测：240×240×155、1mm；首次FLAIR三视图1.704s，T1c/T1n/T2w初次切换0.682/0.704/0.715s，缓存返回0.090s，滚动0.073s（77→78）；四序列Cornerstone缓存约144.7MiB，Chromium renderer JS heap约60.1MiB，退出engine/cache0。新浏览器但服务器/OS缓存可能已热，时间含轮询/自动化；非统计性能，不含DICOM上传/归档/查询、AI或特征耗时，也不是GPU/进程总内存。

最终业务14表全行、科学与任务/候选/隔离/原mask/上一轮转换SHA及依赖保持。新后端30436、前端6772；原DB配置，单服务/串行worker，无长任务。真实PACS联合恢复与报告/PDF新DICOM来源绑定仍未验。

抽查（本07:11窗口）：

1. 打开病例17，刷新归档：显示未配置、没有归档检查关联；DICOM转换来源明确“尚无登记”，不把合成转换当当前影像。
2. 打开上面的Cornerstone工作站，四序列/三视图仍正常、分割只读；返回病例后来源区仍无登记。
3. 查看prior-version-inspection.json：verified_readonly、synthetic-fixture、72体素0差，model_input_eligible=false/live_archive_reconciled=false。
4. 查看dev/prod浏览器JSON：passed、0页面异常/写请求；合成协议状态不能当真实归档通过。
5. 查看state-validation-final.json及real-nifti-performance.json：原14表/必要产物和包保持，实测缓存退出归零；并没有完成真实DICOM端到端。

下一步：先锁/反馈/新服务身份；优先解决真实归档或受支持四序列来源，再P3-b3当前归档原UID/元数据/字节与登记版本重核对。Orthanc既有自动审批拒绝只给blocked by policy，本轮没有重试或绕过，需可批准安装或已有归档；无需重复一般授权。

全部证据：E:/BrainFusion-Runtime/results/nightly/2026-10-13/20261013T071140_7484539d。P1旧验保留；P2/P3整体仍进行中并有真实路径阻塞；P4仅本单例子项验收；E5/E6及R余项保持。
