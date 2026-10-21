# P2-c1 成组DICOM空间核对验证

## 2026-10-13 04:17窗口（10/12夜至10/13凌晨）

run_id 20261013T041702_3ff437ba；开始/原生锁PID精确值见lock-acquired.json，实际FileShare.None持有、session30030；结束/耗时/正常释放见summary/lock-released。无新反馈，不改REVIEW_FEEDBACK；不提交/发布。

P2-c1成组空间核对工程已验收：新增services/dicom_series.py、tests/test_dicom_series.py，pacs_wado.py抽取共享单帧guard、api/pacs.py新增GET /pacs/studies/{study_uid}/series/{series_uid}/view-manifest；现有PacsPanel.vue加入“核对序列空间”与结果/明确限制，新增浏览器检查工具verify_dicom_series_panel.mjs。未增加另一套UI或DICOM渲染入口，旧Canvas/Cornerstone NIfTI工具/原mask不改。

完整QIDO分页与整序列WADO元数据精确UID集合核对，跨页/单项重复拒绝，读后复查UID集合、元数据版本及固定服务标识；最多512实例、256MiB未压缩像素预算、单帧32MiB/元数据4MiB继承边界。经典非MOSAIC单帧MR要求同FrameOfReference/方向/PixelSpacing/矩阵位布局，按IPP投影到IOP法向排序，保留原DS与UID，不用InstanceNumber/文件名排序。重复层位、多时相/回波未分组、面内偏移/剪切、非均匀层距/疑似缺层、声明层距不符及单层三维入口明确拒绝，无配准/补层/重采样。SliceThickness不替代层间距。输出model_input_eligible/dicom_view_accepted=false、sequence_role=unconfirmed，原像素未取；完整性只针对当前归档UID集合，不声称原采集完整。

207相关后端检查通过/4既有警告，23新增成组行为；已知斜位/负方向、PixelSpacing行列对应、手算毫米点、归档乱序、预算与分页、头部/集合变化、MOSAIC/多帧/混合几何明确拒绝，既有PACS/WADO/保管/核对/世界测量/config/API回归通过。首批58含23成组+35WADO为历史；最终backend-accepted207。

真实浏览器现有病例页未配置状态、明确SYNTHETIC协议空间顺序/XYZ毫米、失败/错身份/重试、换序列/SPA换病例、断连刷新与恢复均通过，页异常/原库写/像素请求0。补充刷新失败清理旧空间和选择，避免残留。两次初版SPA脚本通过动态导入新router改变URL但未操作当前app，改用实际挂载router后通过（mounted-router）；这是工具问题，不改App/router，失败截图和日志保留。初版备份guard误用status而实际列名state，停止前失败，查模型修正，未绕过活动任务检查。

备份后重载实际服务，新view-manifest已注册且实际GET503/unconfigured/no-store，旧WADO边界仍503；真实现有NIfTI Cornerstone3canvas仍正常，0页面异常/写入。因前端改动执行一次最终build（VITE_API_BASE=8012），实际静态HTTP预览同空间UI/错误/清理通过，构建大chunk警告保留，不重复依赖安装或整套交付包。已核验停preview24868并恢复dev，当前backend25508 UTC2026-10-12T20:35:33.7567914Z、frontend23396 UTC20:37:40.5284109Z；地址5179/8012不变、单后端/前端及各一串行worker，无其他长任务。新PACS模块与此前可选pin源码已随新后端加载，但未有真实归档/pin浏览器验收。

重启前原分析/特征活动任务0，SQLite只读备份和恢复副本14表全行一致、featurejobs逐文件复制/SHA相同；重启和生产预览后原14表全行与本轮/旧已验快照完全相同、原MRI/mask/空间夹具/任务/真实候选/隔离目录SHA与依赖版本不变，source数据库未替换、无新表迁移、模型未推理。备份/恢复仅现有业务库副本；不得代替P4真实PACS+业务联合恢复。

P1支持NIfTI已验，P2整体进行中/P2-env受阻，P2-c2成组像素加载到既有Cornerstone入口待实施，P3/P4待实施；真实匹配四序列链路缺数据。F/E旧验收保留、E5受阻/E6进行中、R1待核查/R2–R4待实施。Orthanc官方下载+版本执行曾自动审批拒绝，仅blocked by policy；本轮未重试/绕过，无私有PACS配置或真实入库。当前UPENN MOSAIC拒绝、加工MR_small只作工程材料，没有新下载/安装/训练/推理，也没有真实DICOM浏览器/模型/PDF新路线通过。

下一轮第一步：锁/反馈/当前PID及启动时间核对后，继续P2-c2基于已装Cornerstone5.7的WADO-RS metadata provider、成组像素与既有CornerstoneViewer接入；图像缓存必须带来源/版本、加载取消/换病例清理，失败明确，不静默切Canvas，DICOM未证实的测量保存/编辑和AI提交不开放。真实归档/数据条件可用时优先验，不重复环境失败、空查询、安装或整包审计。


## 物理定义与支持边界

采用[DICOM Image Plane Module](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.6.2.html)的患者LPS毫米坐标：IOP前3量a、后3量b；PixelSpacing第1值为行间距、第2值为列间距。像素位置=IPP + 列索引×列间距×a + 行索引×行间距×b；以a×b的单位法向作IPP投影排序。法向归一仅用于投影计算，不重写原IOP；固定SOP参考确保归档返回顺序变化时稳定。

层间距由相邻IPP测量，SliceThickness不代替它；存在SpacingBetweenSlices时核对其绝对值。当前仅支持均匀直角网格经典MR，不默许非均匀体积、剪切、多时相/回波或缺帧。单层可保留元数据，但本三维契约拒绝，单层Stack入口未实施。阈值在geometry.validation_tolerances明确输出：IOP分量1e-5，面内漂移/重复层距阈值0.001mm，间距绝对0.001mm/相对1e-4；原DS和像素不改写，不能把容差内一致解释成原始采集独立认证。

合成斜位夹具为3×2×3，a=(0.6,0.8,0)、b=(0,0,1)、法向=(0.8,-0.6,0)，spacingXYZ=(2,3.25,2.5)mm；已知(column2,row1,slice2)手算LPS=(16.4,20.2,33.25)mm。这里只是明确合成空间行为，不是临床影像、配准或模型评价。

已核对本机Cornerstone core/tools/dicom-image-loader5.7 APIs和[官方Volume加载教程](https://www.cornerstonejs.org/docs/tutorials/basic-volume/)；未来入口会沿用现有Cornerstone组件。仅组件存在或当前manifest准备不能证明DICOM像素加载通过，本轮没有注册WADO加载器到当前页面。

## 证据

证据目录：E:/BrainFusion-Runtime/results/nightly/2026-10-13/20261013T041702_3ff437ba/

- backend-accepted.log：最终207通过，backend-first.log为首批58历史。
- browser-series-panel-mounted-router/validation.json：最终开发页面空间UI与清理；browser-series-panel-production/validation.json：最终build实际静态HTTP相同检查。截图标题明确SYNTHETIC，不能用于展示真实DICOM阅片通过。
- browser-wado-boundary/validation.json：重启后当前未配置PACS边界与既有真实NIfTI三canvas；live-manifest-unconfigured.json：新真实端点503/no-store。
- database-backup/validation.json、restart-guard.json、feature_jobs_snapshot、state-validation.json：原库副本恢复及最终全行/所有必要原科学文件/任务SHA一致。原数据库保留现址。
- build-final.log/build-final：实际变更相关一次构建，API8012和chunk警告；preview-service为短暂预览，已正常停止；restored-dev-service为当前前端。
- SYNTHETIC-browser-manifest.json：仅合成协议夹具；没有原患者原像素或归档凭据。

失败/纠正记录：browser-series-panel与browser-series-panel-final初版操作重新导入router未驱动挂载app，查router代码/截图后改用实际app router，最后通过；restart-guard.log列名错误查模型修正后restart-guard-final通过，未启动重启前的失败步骤。工具调用中初版patch未命中/JS字符串语法错误均未改项目，随后核查并纠正。

## 用户抽查（对应04:17窗口）

1. 打开 http://127.0.0.1:5179/case/17，刷新“本地DICOM归档”，应明确未配置；未配置时没有“核对序列空间”或假成功结果。
2. 在 http://127.0.0.1:8012/docs 执行新GET /pacs/studies/1.2.3/series/1.2.4/view-manifest，应503、reason=unconfigured；不自动回退到旧阅片器或生成空成功。
3. 打开 http://127.0.0.1:5179/workstation/17?viewer=cornerstone，原真实NIfTI加载后应有三视图，原掩膜只读；本轮没有将DICOM模型角色赋给旧NIfTI。
4. 查看同目录SYNTHETIC-spatial-order.png及browser验证：3层按2.25.500/501/502排序，X/Y/Z=2/3.25/2.5mm，明确仅元数据/未取像素/不代表AI通过。
5. 查看state-validation.json：原14表与原科学/任务/隔离文件不变，source_database_not_replaced=true，real_dicom_browser_or_pacs_import_verified=false。

实际归档可用后现有病例面板可查询检查→选序列→“核对序列空间”。应展示有UID来源的空间结果，错误时清除旧结果、拒绝不支持序列。正式数据许可/脱敏/来源/pin须按实际条件配置，本轮不修改allow_pixel_read或PACS私有配置，不编造医生复核。
