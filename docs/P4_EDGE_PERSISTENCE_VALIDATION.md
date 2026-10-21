# P4 Edge账户、PDF及DICOM保存/关闭恢复验收

2026-10-16凌晨，run_id `20261016T021054_edgewrite`；实际开工UTC2026-10-15T18:07:49.6990958Z（北京02:07:49），属于10/15晚至10/16凌晨。证据目录 `E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T021054_edgewrite/`。本次是此前Edge只读之外的两个未验行为批次，不重新下载/导入192实例或复制650应用文件。

使用已装Microsoft Edge 155.0.4283.45、Playwright msedge通道、headless及E盘新建持久配置；不安装浏览器、不使用个人配置。自然关闭指await context.close关闭整个专用浏览器进程，再以同一测试profile启动新进程；后端保持运行。不是仅刷新或创建另一标签页，也不代替断电、浏览器崩溃或人工可见窗口操作。

## P4账户/导出批次：已验收

从上轮账户最小联合恢复库新做SQLite备份/恢复副本，17表、36条距离/1个视图/5条复核原行保留。原模型/研究/队列目录作为既有启动前提复用，未执行AI。

1. 真实Edge表单登录engineering-doctor，固定署名“身份工程验收（非医师认证）”，另存第6条来源/内容复核，稳定actor ID、角色、reviewer_authenticated=true及professional_credential_verified=false。内容SHA不变，导出SHA随复核变化。旧5行和其余16表逐行不变。
2. 真实“导出 PDF”下载，纸面含当前署名/本地账户说明、复核意见、36条毫米距离、UID及完整来源/内容/导出SHA。使用PDF技能要求的操作标记后才导出，Poppler重新打开/渲染共3页A4；最终三张PNG均已逐页查看：表格续行、完整SHA、复核署名/意见/教学限制均可读，无裁字或重叠。PDF为现有html2pdf栅格化导出，未以空文字提取代替视觉验收；不是临床签章PDF。
3. 第一次完整关闭再重开后，持久cookie仍有HttpOnly/SameSiteStrict/到期时间，原服务会话有效，页面登录及同一第6条/来源/导出SHA恢复，没有新增复核。显式退出后第二次关闭再开，账户保持退出、保存按钮禁用，已有复核仍可读。

本批业务请求只有登录、一次复核POST、退出；页面异常0。服务会话仍是单进程内存/8小时上限；这里不保证过期或服务重启后免登录，重启清会话已有上一轮实际证据，本次没有冒充重做。

## P4 DICOM落库与视图批次：已验收

继续同一本轮自有副本；复用现有原归档服务，不新导入或切换Orthanc。真实鼠标分别改变三个平面的滚层/平移/缩放/窗值，保存为新视图#2；旧#1不覆盖。另画轴位距离#37，两个LPS端点与canvasToWorld独立计算差小于0.001mm，长度28.273695819mm。新增距离改变报告内容，旧账户复核变为current=false。

完整关闭Edge再重开同一profile后，三相机的焦点/位置/方向/缩放误差小于0.001，三组窗值精确一致，#37患者LPS点及锁定状态恢复。实际从界面仅删除新增#37，刷新后原36条仍逐字段一致，新视图仍恢复；离开工作站后engine0/cache0。两张三视图截图已查看，28.3mm显示和物理位置一致，线颜色因选中/恢复变化不作像素一致要求。

本批只有一次视图POST、一次距离POST及仅新#37的DELETE，页面异常0。最终17表逐行核对：只有dicom_view_states新增1条，原36距离、全部6复核及其余16表均不改。轴位的实际保存被验证；不能写成三个平面各新增距离，其他平面旧Chromium工程证据另列。

## 原件与实际服务

所有真实开发/测试/服务切换在有限同步run_development_step.ps1内重新核对输入/交接/进程身份，finally回正式八路径及明确原PACS/导入/账户额外路径，两个工作步骤均成功退出0并释放。原正式17表所有行、原八路径、原账户/候选登记/PACS配置及上轮5复核源库SHA不变。Orthanc PID7328自UTC2026-10-15T17:13:37.285544Z保持运行；本次没有原归档重启或存储全量复制，未把本次读取当索引离线SHA重验。

当前后台21076 / UTC2026-10-15T18:15:51.074127Z，前端20880 / UTC2026-10-15T18:15:51.0768841Z；UI http://127.0.0.1:5179/case/19 ，API http://127.0.0.1:8012 ，归档8042仅本机且有鉴权。正式PACS ready/账户configured/原候选可读；工程复核/距离/视图不出现在正式库。实际进程/日志以Runtime/local/processes.json、backend/frontend out/err及orthanc-local/process.json为准。无下载、推理、特征、训练或构建长任务。账号密码与测试浏览器profile只在私有backups目录，不公开。

## 证据与范围

- edge-account/validation.json、edge-account.log、edge-after-save.json、isolated-rows-audit.json；PDF及pdf-page-1/2/3.png、pdfinfo.log、pdf-render.log、visual-review.json。
- edge-dicom-persistence/validation.json、edge-dicom-persistence.log、edge-saved-view.png、edge-reopened-view.png、edge-views-row-audit.json。
- database-backup/validation.json、formal-preservation.json、final-after-views-preservation.json、final-after-views-services.json及两个实际步骤日志。

新增frontend/tools/verify_edge_account_persistence.mjs及verify_edge_dicom_persistence.mjs，仅验收工具；前后端产品代码/依赖未改，没有重复生产构建或旧全套pytest。真实行为检查和git diff --check通过；先前17项快照测试是历史，不算本轮重跑。PDF技能原说明位于C:/Users/mechrevo/.codex/plugins/cache/openai-primary-runtime/pdf/26.1013.11914/skills/pdf/SKILL.md，本轮未因此要求额外审批。

未验：Edge NIfTI距离/视图落库与关闭恢复、可见窗口人工操作、其他浏览器/异常崩溃；完整多病例含新账户全量交付包/异机/容器。P3仍缺匹配且网格可审计的真实四序列；E5正常系统授权条件未变，不重试被拒环境动作。P4/E6整体未完成。

## 抽查（本窗口）

1. 正式Edge打开上述病例19，选择原检查/序列并核对空间，进入DICOM：仍是原192层，普通抽查不保存。
2. 从面板进入DICOM阅片记录/PDF：正式库没有本批工程复核；核对来源/限制说明。
3. 打开本轮PDF，逐页检查36条距离、第三页本地账户署名/意见/完整SHA和教学限制。
4. 对照edge-saved-view/edge-reopened-view截图与validation，28.3mm工程线和相机/窗值恢复相符；原36/6历史保护见行审计。

下一轮先核对锁/反馈/原三服务，再用正式业务库的新SQLite副本补Edge真实NIfTI距离/视图保存与浏览器关闭恢复；不重抄650产物、不重复DICOM PDF/导入/来源探测。该路径过后进入E6明确本机支持范围和最后部署材料，P3/E5受阻项继续单列。

收尾记录：文档已写后，首次summary耗时计算遇Python3.10不接受PowerShell七位小数ISO时间，实际步骤退出1且释放。原日志record-edge.log保留；改用明确微秒datetime只补摘要/收尾说明，不重跑业务、导出或覆盖三页证据。正式服务一直正常。
