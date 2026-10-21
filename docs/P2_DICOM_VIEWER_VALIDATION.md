# P2-c2 成组DICOM Cornerstone工程验证

## 2026-10-13 05:14窗口（对应10/12夜至10/13凌晨）

run_id 20261013T051455_f13472c8；实际FileStream FileShare.None持有者/owner27576，原生启动UTC2026-10-12T21:14:54.7780683Z，开始UTC21:14:55.4033991Z/北京05:14:55，session74715。结束、实际耗时与正常释放见本run summary/lock-released。无新反馈，不编造REVIEW_FEEDBACK；保护既有工作树，不提交/推送/发布。

P2-c2成组像素接入工程已验收：复用当前CornerstoneViewer三视图及Workstation、病例PacsPanel，新增dicomVolume.js和病例绑定的manifest/frame读取。检查必须已与当前病例和归档配置核对关联，后台开启像素、固定逻辑服务标识，验证不覆盖/无摄入转码策略；逐帧核对来源fingerprint和白名单元数据SHA，旧空间或目标改变在读取像素前拒绝。图像ID含来源/版本及独立会话，缓存/请求/元数据按本视图清理，不全局过滤错误，不静默切Canvas或NIfTI。

DICOM仅支持已验c1的均匀、非MOSAIC、经典单帧MR成组原空间；1 mm四序列模型约束仍只属于现有AI输入，不强加于工程阅片或默许DICOM可推理。序列角色未确认、无自动配准/重采样，DICOM测量保存、mask叠加/编辑、视图持久化与AI提交未开放，原NIfTI工具/保存/原mask保持。满足来源门槛的已有面板提供“Cornerstone阅片（工程验证）”，未配置时不显示可用假象；用户可明确选择当前病例NIfTI。

本次214相关后端检查通过/4既有警告，8新增病例/来源/版本门槛（早期66为该子集）；上轮207为历史，不混称同一运行。浏览器明确SYNTHETIC 32×24×9协议夹具，经真正WADO multipart和现有解码工作器加载3MPR：全部6912有符号像素一致，负方向斜位LPS手算角点(-43.2,-17.6,104.75)mm一致，spacing(2,3.25,2.5)mm。窗值、平移焦点、缩放比例、十字线其他平面位置及滚动层号11→12实测变化。开发和一次最终构建的实际静态HTTP生产预览通过；生产做工具/生命周期冒烟，数值及缓存明细在开发检查，不夸称生产内部数值检查。

追加P2-c2-r回归小批次通过：直接SPA切错误Series时，旧清单在新帧之前拒绝；9帧仅1帧失败也保持error，完整成功后的缓存、失败/加载中退出及旧新帧元数据清理后engine0/cache0/remaining0。明确错误、无静默回退、用户手动NIfTI仍3视图；最终浏览器pageErrors/原库写入均0。合成截取像素是纯工程函数，未由NIfTI生成冒充患者DICOM，也未向真实归档/病例库写入测试关联。

首次发现解码工作器预优化/CommonJS导出不兼容：依官方Vite方向排除DICOM loader预优化、预优化现有CJS codec入口、worker ES格式/WASM资产，无新增依赖。5.7核心忽略缓存插入Promise会产生XMLHttpRequest未处理拒绝，已用本系统独立bfwado scheme接住缓存Promise，原像素Promise仍拒绝并显示error，无全局事件屏蔽。测试误取actor UID、导入第二份tools状态、返回router Promise被GC及在400ms单击窗口之前读相机，均保留失败日志，改用真实volumeId/当前组件/实际路由与已知体积点，600ms后有真实事件与相机变化；不是再次修坏或冒称工具通过。

重载前分析/特征活动任务0，14表全行备份/恢复副本相同、featurejobs复制/SHA相同；重载后新增实际病例绑定路由503/unconfigured/no-store，实际DICOM页面明确未配置、Canvas禁选、无NIfTI自动回退/像素请求。最终真实NIfTI3canvas通过。原14表全行与本轮及历史已验副本一致，原MRI/mask/空间夹具/候选/隔离保管与featurejobs SHA、主环境依赖版本不变；未替换原DB、未推理/重算、未改原mask。只验业务库副本恢复，不代替P4真实PACS+业务联合恢复。

当前backend13272 UTC2026-10-12T21:49:59.6640498Z；frontend33136 UTC21:51:59.0620783Z，原项目dev。http://127.0.0.1:5179/case/17、workstation/17?viewer=cornerstone，API8012/docs。Runtime/local/processes.json登记；后端日志Runtime/local/backend.{out,err}.log、前端本run/restored-dev-service/frontend.{out,err}.log。已核验停止短暂preview4804；单后端/前端及各一串行worker，无其他下载/训练/推理/构建长任务。原10/10 01:06 runtime-supported.json、DB/featurejobs/gate和00:06 relocated-runtime配置不改；没有PACS私有配置、凭据或依赖安装，旧交付包保持历史。

P1支持NIfTI已验，P2-c2和c2-r仅工程已验，P2整体仍进行中/P2-env受阻：真实Orthanc/插件、支持的真实成组DICOM、来源/像素审核、真实导入/重复/持久化/重启未验。现有UPENN单实例MOSAIC仍明确拒绝，MR_small为处理测试数据，未新增真实下载或审核。P3真实匹配四序列链路受阻，P3工程转换/确认仍待实施；P4集成/性能/联合恢复/报告待实施，E5受阻/E6进行中，R1待核查/R2–R4待实施。F/E历史已验保留，不能凭本批次冒称系统交付或研究完整。

下一轮第一步：核对锁、反馈及上述服务启动身份并复用。优先处理新实际失败或可用真实PACS/样本；外部条件不变时推进P3-a来源UID/Frame/产物及四序列人工确认、原模型输入空间契约的小批次（不按名称猜、未满足具体拒绝），独立于尚未取得转换工具/真实队列的准备不能算真实端到端通过。P2后续仍需实际来源与归档验收，环境策略拒绝不重复绕过。

Orthanc官方候选下载+版本执行曾被自动审批拒绝，仅给出“blocked by policy”；本轮未重试/换工具绕过，解除需可获批准的安装路径或已有可用归档。当前独立开发不需要用户重复一般授权、账号、提权或重启。

用户抽查（05:14窗口，最多五项）：

1. 打开 http://127.0.0.1:5179/case/17，刷新“本地DICOM归档”，应明确尚未配置，不出现成功归档或可用阅片假象。
2. 打开 http://127.0.0.1:5179/workstation/17?viewer=cornerstone&source=dicom&study_uid=1.2.3&series_uid=1.2.4，应明确未配置/error、Canvas禁选，不自动显示原MRI。
3. 点击“打开当前病例NIfTI”，应进入真实原影像三视图，NIfTI测量/保存与掩膜只读边界仍保留。
4. 查看输出SYNTHETIC-three-views.png、partial-frame-refusal截图和browser-SYNTHETIC-validation.json：合成身份、6912像素0差异、毫米位置一致、1/9帧失败仍error，不是实际DICOM病例通过。
5. 查看state-validation.json及live-source-boundary.json：原14表全行/必要产物SHA不变、新路由503/no-store，不是PACS联合恢复。

## 接口、工具版本和证据

病例绑定GET /pacs/cases/{case_id}/studies/{study_uid}/series/{series_uid}/view-manifest；单帧GET同层级instances/{sop_uid}/frames/1，必须带metadata_sha256和archive_fingerprint。BulkDataURI只能是本站对应病例/UID/版本，不跟随外部地址；后台凭据不交浏览器。pin是配置约定的逻辑标识，不是密码学数据库身份；不能证明管理员复用标识替换库，或原采集完整/像素审核有效。逐帧SHA针对呈现元数据，不假称原DICOM文件/像素字节已由发布方认证；实际原文件核对需P2-b4及真实归档证据。

Cornerstone core/tools/dicom-image-loader均复用本机5.7.0，Vite8.2.1、Vue3；无安装@originjs插件或重装依赖。依据[官方Vite框架说明](https://www.cornerstonejs.org/docs/getting-started/vue-angular-react-etc/)排除loader预优化以保留worker模块URL，再为当前已有CJS codec入口做明确预优化；实际本版本开发及生产皆已验证。解码器中有其他格式代码不表示本后端支持压缩/多帧/MOSAIC，边界不扩大。

本run证据目录：E:/BrainFusion-Runtime/results/nightly/2026-10-13/20261013T051455_f13472c8/。backend-final.log为214最终通过；backend-first.log首批unpinned夹具关联错位失败、backend-source-retry.log66通过；backend-accepted.log是错写测试文件名而未运行的失败记录，不能引用为通过。browser-dicom-dev-tools-accepted/result.json为最终工具数值，browser-dicom-dev-series-partial/result.json为新增换序列/局部失败及全部新旧帧清理；browser-dicom-production/result.json为实际静态HTTP构建冒烟；browser-dicom-unconfigured/result.json及browser-wado-boundary/validation.json为真实未配置/旧NIfTI；live-source-boundary.json为真实新接口。此前失败目录/日志全部保留，不覆盖。

build-final.log为唯一相关构建（API8012），大chunk警告保留；preview-frontend/dist保留已验构建，node_modules是原依赖联接，不能npm ci/递归删。database-backup/validation.json、restart-guard.json、feature_jobs_snapshot、state-validation.json为只读备份与全行/文件核对。SYNTHETIC-view-manifest.json和prepare_view_fixture.py仅自有合成协议，没有真实患者影像/标签。原实际公开候选、保管收据和原文件不变。

已改文件：backend/app/services/pacs_wado.py、dicom_series.py、backend/app/api/pacs.py、backend/tests/test_dicom_view_source.py；frontend/src/components/mri/dicomVolume.js、CornerstoneViewer.vue、components/PacsPanel.vue、views/Workstation.vue、vite.config.js、tools/verify_dicom_viewer.mjs及verify_dicom_unconfigured.mjs；本指南及清单/交接/阶段/daily/README/概要/发布/PACS计划增量。没有第二套UI、医院权限管理或自动模型提交。
