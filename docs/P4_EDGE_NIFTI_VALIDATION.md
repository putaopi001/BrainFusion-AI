# P4 Edge真实NIfTI保存与正常关闭恢复

2026-10-16凌晨，run_id `20261016T030947_edgenifti`，属于10/15晚至10/16凌晨；系统UTC19:08:48.9062596Z（北京03:08:48）实际开工，03:09:47创建本轮目录。仅本轮新SQLite备份/恢复副本允许业务写入，现有MRI/模型/研究/产物保持原位置，只读复用；没有复制650文件、导入DICOM或重算AI。

## 当前已验行为

已装Microsoft Edge 155.0.4283.45，Playwright msedge通道/headless、E盘全新专用持久配置，未读个人profile。自然关闭是关闭整个浏览器进程，再用同一配置启动新的进程；不是仅刷新标签页。服务保持运行，本次不代替崩溃/断电或后台重启。

- 真实病例17、MRI ID16、分析a3ab2210c797490e960a9b6107fd61c8；三正交平面分别用鼠标创建/保存毫米距离，轴/矢/冠长度依次35.340902698、34.006004134、34.006004134mm。每条端点与独立canvasToWorld计算误差小于0.001mm，长度与欧式距离一致。
- 切T1n后实际滚层、平移、缩放、调窗，三个相机和三个窗值均改变；隐藏原分割叠加，只保存展示开关及来源版本，不改mask。明确点击保存视图，记录sequence=t1n、segmentation_visible=false及三相机/VOI。
- 第一次关闭整个Edge再开恢复同一视图版本/来源，三个物理相机字段误差小于0.001、三窗值完全一致、仅MRI actor，三条锁定测量LPS点完全一致。已保存/重开两张三视图截图实际查看，T1n和隐藏mask恢复一致；该保存位置不一定经过三条线所在切面，未用截图看不到线来冒充长度验证。
- 再依次切T1c/T2w/FLAIR/T1n，物理焦点误差小于0.001，三条锁定端点及数据库记录保持。实际从界面只删除本批3条，第二次关闭重开仍为空，保存视图保持；旧Canvas标注逐字段不改。最后明确选择Canvas并刷新，仍走Canvas，没有静默回退。

共7个业务写请求：3次距离POST、1次视图POST、3次仅本批新距离DELETE；pageError0。不是在正式库写工程测量，不把headless当人工可见窗口验证。此前DICOM/账户/PDF的Edge证据另见[P4另一批](P4_EDGE_PERSISTENCE_VALIDATION.md)，本次没有重导PDF。

## 数据和环境保护

先用snapshot_database.py备份原业务库并恢复新副本。最终本轮副本17表仅mri_view_states新增1条；三条试验距离已删除，其余16表逐行完全一致，包括旧Canvas标注、分析、研究、DICOM记录/复核。正式17表全部原行、原八路径、选定四MRI/原mask共5文件及本机账户/PACS配置/候选登记SHA不变。只验这五个影像产物，没有冒充650文件重新全验。

有限同步包装器内核对交接/产品文件基线及PID精确启动时间，finally恢复正式八路径和明确PACS/导入/账户额外配置，实际步骤退出0/释放。当前正式后台7708/UTC2026-10-15T19:11:35.2800703Z、前端18792/UTC2026-10-15T19:11:35.2829502Z，原Orthanc7328/UTC2026-10-15T17:13:37.285544Z保持。PACS ready/账户configured；UI http://127.0.0.1:5179/workstation/17?viewer=cornerstone ，API8012、归档8042本机鉴权。无下载、推理、提取、训练或构建长任务。

## 证据

根 `E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T030947_edgenifti/`：edge-nifti/validation.json和edge-nifti.log记录真实行为与数值；edge-nifti-saved-view/reopened-view.png已查看；database-backup/validation、isolated-row-audit、formal-preservation、source-context、final-services记录版本与原件保护。E盘专用浏览器profile位于Runtime/backups/20261016T030947_edgenifti，不入仓库/公开材料。

新增frontend/tools/verify_edge_nifti_persistence.mjs仅验收工具，产品代码/依赖未改，因此未重复全套pytest/生产构建。没有新分割、IDH模型/患者或临床结论。当前已知受支持浏览器自动化为现有Chromium历史和已装Edge明确路径，Firefox/Safari/其他版本、可见人工窗口/异常崩溃没有据此验收。

抽查：①Edge打开上述工作站地址，当前正式库没有本批保存视图/距离；②切T1n并开关原mask，三视图可读，普通抽查不保存；③看本轮两个视图截图及validation的35.341/34.006/34.006mm和关闭重开断言。工程写行为应在隔离库抽查，不能要求正式库出现本批记录。

P4整体仍缺最终性能/部署整合及P3真实四序列分支，E5原授权仍受阻；下一轮可做两种真实来源首次加载/切片与切序列延迟、运行进程内存的有界分层实测，复用既有导入/AI计时，避免重复导入或旧推理。
