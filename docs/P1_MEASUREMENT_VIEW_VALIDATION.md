# P1 NIfTI阅片、测量与保存恢复验收

窗口2026-10-12 22:20，run_id20261012T222030_9ac688e4。P1受支持NIfTI路径已验收；PACS/DICOM和完整系统交付尚未完成。证据根E:/BrainFusion-Runtime/results/nightly/2026-10-12/20261012T222030_9ac688e4。21:18首批体素/空间证据保留在P1_CORNERSTONE_VALIDATION，本次没有重复推理或特征实验。

## 用户抽查（原业务库）

1. 打开http://127.0.0.1:5179/workstation/17，选择Cornerstone3D。预期三视图及R/L/A/P/S/I方向标记、明确四序列与原模型分析版本。
2. 选择距离测量，在任一视图按住左键拖出线段，点击保存测量。预期显示mm与已保存编号；已保存测量只读。未完成绘制按Esc取消。
3. 切换另一序列，再刷新并重新选择Cornerstone。预期测量坐标/毫米不变，在对应物理平面显示。点击删除测量，再刷新，预期该记录不再显示。
4. 切换T1n、滚动/平移/缩放/调窗或隐藏mask，点击保存视图。预期显示版本编号，地址带viewer=cornerstone；刷新后恢复序列/三相机/窗值/mask显隐。没有保存视图的默认页面仍为Canvas。
5. 手动选择Canvas，再刷新，预期Canvas；返回病例页再选择其他病例，预期不残留本病例的测量/引擎。原mask始终只读。

测量保存与视图保存是两个明确操作；未保存的草稿退出不保留。这里只开放Cornerstone距离工具，ROI/角度/自由绘制及mask编辑未开放；Canvas原十工具仍属于已验历史路径。坐标/版本工程通过不代表临床测量认证。

## 实施与数据边界

新增mri_world_measurements、mri_view_states两个表，不修改/混用原归一化Canvas标注表。记录LPS毫米端点/平面方向、来源序列、MRI ID、geometry_id（原shape/affine）、study_revision（全部输入文件size/mtime）、analysis_run_id。服务器计算Euclidean毫米、检查空间单位/同平面/体素边界与当前版本。相同UID/相同内容重试复用原记录；改变已保存内容或旧版本提交409，不覆盖。旧记录保留，当前MRI的旧分析/文件版本测量不叠加；更旧MRI记录仍在数据库，当前界面不提供单独历史浏览入口。

视图按明确保存生成新不可变版本，保存序列、三相机的LPS位置/法向/上向/缩放、各序列三窗值和mask显隐。服务器验证有限数值、正窗宽、相机方向与版本；旧版本不能自动恢复到新影像。保存成功后URL保留明确渲染入口，手动Canvas清除该偏好。截图方向字母来自实际canvasToWorld屏幕方向，可随相机方向更新，不按数组轴名猜测。

采用已安装5.7.0 [LengthTool](https://www.cornerstonejs.org/docs/api/tools/classes/lengthtool/)及annotation.state/locking接口，加载记录使用实际hydrateBase的viewplaneNormal参数。所有录入/改动/删除浏览器试验限定本run/database-backup/restored-validation.db；生产构建试验恢复原业务库并阻止业务写请求，仅绘制/删除本地未保存草稿。原库增加两个空表供用户使用，原表所有行/原标注/分析/研究/报告保持，见summary最终审计。没有新增患者队列、真实标签、模型或科学结论。

## 当前证据

- backend-final.log：43通过、4既有FastAPI弃用警告。新增真实SQLite行为16项：合成非单位spacing/翻转10mm长度、重试/UID冲突、持久记录、无效方向/平面/边界/零长度/序列拒绝、真实文件/分析版本变化、Canvas删除互不干扰、跨病例隔离、视图版本/边界拒绝。不是测试实现字符串。
- database-backup/validation.json、migration-validation.json、migration-view-state-validation.json：原库快照/恢复副本完整性与原旧表全行一致，再在恢复副本迁移新表；原库在试验阶段不写入。
- browser-measurements-create-stable-layout：真实病例17在三平面实际鼠标Length，服务毫米与canvasToWorld距离及工具缓存mm一致；约35.34/34.01/34.01mm只是本次任意工程线段。首次真实POST已提交后故意丢响应，再重试仍只有一条记录；刷新与序列切换坐标不变、保存线锁定；两截图实际查看。
- browser-measurements-restart：真实stop/start至新backend/frontend PID，再实测3记录恢复、实际删除、刷新无记录，Canvas旧标注一致。试验后没有把这3条测量移入原库。
- browser-view-save/restart：实际T1n切换/滚动/平移/缩放/调窗/隐藏mask→保存→刷新及真实服务重启，3相机与窗值、序列/显隐恢复；手动Canvas/刷新仍Canvas。相机数组按1e-3mm/缩放容差核对，窗值原值相同。
- browser-measurement-lifecycle：不完整绘制Esc退出恢复工具；控制409保留未保存草稿、明确错误；实际同一Vue路线病例17→病例1→17清理草稿/Frame/引擎，各自视图隔离；控制旧视图标记被拒绝。控制异常只用于交互，真实版本变化在后端检查，不伪装真实坏病例。
- browser-nonunit：明确SYNTHETIC病例19，旧库副本中的3×4×5 NIfTI轴置换/翻转、1.5/2/3mm，3个indexToWorld与独立nibabel sform LPS参考一致，12个屏幕方向字母符合物理视图，约0.651mm线段创建/保存/删除通过。合成数据小尺寸仅验证几何/工具，不是病人、DICOM、AI输入或性能样本。
- build-final.log、browser-production：最终构建成功且大chunk提示保留；单前端真实HTTP preview实测4真实序列、三canvas、12方向、未保存Length mm/本地删除、Canvas往返；pageErrors/consoleErrors/业务写请求0。之后恢复原开发前端，未复制部署依赖、未安装环境。
- browser-core-regression：变更相关真实四序列/窗宽窗位/滚动/缩放/平移/十字线/原mask非空与显隐/空间位置/加载取消/退出缓存回归通过；4预期主动销毁上下文的库警告与控制422日志保留。原mask/MRI未修改。

## 失败与限制

第一次浏览器绘制中动态提示把viewport推移，独立世界坐标断言发现端点偏移；修复为预留提示高度、测量列表放在图像下方，最终坐标一致。旧失败目录browser-measurements-create保留，不能当最终通过。源码与最终构建/测试日志的SHA绑定见summary。

其他浏览器/自然关闭、性能与内存完整基准、DICOM归档/真实DICOMweb、四序列转换到AI、归档和业务联合恢复、PDF中新测量来源展示及完整交付归P2–P4/E6。旧Canvas报告PDF历史通过不升级为这些新回归。原MRI/模型/特征协议/临床输入/概率/医生意见均无本轮科学重算。

生产验证自己的preview-frontend/node_modules为指向原E盘依赖的联接，仅复用，不是独立安装；不对该联接npm ci或递归清理。证据副本和合成病例19仅留在自己的trial库，不导入科研队列。
