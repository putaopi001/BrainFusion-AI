# P4 Microsoft Edge 实机只读阅片验收

10/16 02:07增量：[Edge持久化验收](P4_EDGE_PERSISTENCE_VALIDATION.md)已补DICOM实际测量/视图/账户复核、三页身份PDF及正常关闭恢复；以下只读窗口保留为原范围。Edge NIfTI落库/关闭恢复仍待验证。

2026-10-16凌晨，run_id `20261016T010830_jointauth`。复用已安装Microsoft Edge 155.0.4283.45，Playwright的msedge通道、headless及E盘临时独立配置；未安装浏览器、未访问用户已有个人配置。

在实际正式HTTP服务检查真实NIfTI病例17与真实归档DICOM病例19，不模拟像素/元数据，不运行新推理。整个浏览器拦截所有非GET/HEAD业务请求，最终写请求0、页面异常0。

已验：

- 两条真实入口各三视图；鼠标滚层、窗宽窗位、平移、缩放、十字线改变实际相机/窗值。
- 两种来源各画1条未保存距离，显示毫米与独立canvasToWorld端点距离误差小于0.01mm，再从界面删除草稿；没有保存/删除业务记录。
- NIfTI四序列切换保持同一物理焦点和MRI/只读mask两actor；选择原mask非零点LPS(106,-132,131)，开/关叠加实际像素不同，隐藏时仅MRI actor。
- DICOM显示受支持192×256×192体积及12个方向标记；没有mask按钮，不把单序列当模型角色已确认。
- NIfTI→DICOM→NIfTI及退出路由清理引擎、缓存和草稿。两次退出均engine0/cache0，返回不串病例或未保存测量。

证据根与本轮共同：`E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T010830_jointauth/`，见edge-readonly/validation.json和edge-readonly.log；nifti-nonempty-mask.png、nifti-mask-hidden.png、dicom-edge-three-views.png、nifti-return.png已保存，非空mask和DICOM图已查看。非零点是为可见性检查挑选的现有分割体素，不是新临床判读或分割精度评价。

这只验当前已装Edge的headless只读路径。既有Chromium保存/恢复等证据另列；Edge的实际落库、账户复核/报告/PDF、自然关闭恢复，以及Firefox/Safari/其他版本/触摸设备没有据此通过。未改前端产品代码，无重复生产构建。

抽查可用本机Edge打开 http://127.0.0.1:5179/workstation/17?viewer=cornerstone ，切四序列/叠加，返回病例19归档面板选原检查/序列/核空间再进入DICOM；普通抽查无需点保存。完整自动化步骤和截图来自明确headless环境，不能冒称人工可见窗口也验收了。
