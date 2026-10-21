# P1 Cornerstone首批验收

2026-10-12 22:20已接续完成P1-c，受支持NIfTI路径P1通过；当前测量、视图保存恢复、方向与其他病例/生产HTTP证据见P1_MEASUREMENT_VIEW_VALIDATION。下方21:18首批记录保留为历史，其中“尚未接入/未验”不代表当前状态。

2026-10-12 21:18窗口，续接22:02触发；run_id20261012T211814_d5bca694。P1-a/b已验收，P1整项进行中。所有证据位于E:/BrainFusion-Runtime/results/nightly/2026-10-12/20261012T211814_d5bca694。

## 实际入口与操作

打开http://127.0.0.1:5179/workstation/17，选择“Cornerstone3D（迁移验证）”。默认入口是已验Canvas；刷新仍默认Canvas，不能称已恢复Cornerstone视图。输入为已有公开真实病例17四序列与原模型mask，不产生新分割。API为http://127.0.0.1:8012/docs。

1. 切换T1c/T1n/T2w/FLAIR：三视图明确当前序列，保持原物理切片位置、相机方向/缩放，按序列记住窗值。
2. 滚轮切层；选择窗宽窗位、平移、缩放后按住左键拖动。选择十字线后拖动其中心可改变另外两个平面。仅拖动已验；点击跳转未通过本轮检查，不列入验收。
3. 隐藏/显示分割：只读原模型结果，分析版本a3ab2210c797490e960a9b6107fd61c8可见。初始中心层可能没有肿瘤，证据中的非空层根据原mask确定性选点，不能作分割准确性证明。
4. 手动切Canvas、再切Cornerstone；返回病例页或加载过程中切Canvas。退出取消请求并释放引擎/体素缓存。错误留在Cornerstone明确显示，不静默切Canvas。

## 实施与依据

core/tools实际安装5.7.0。旧组件工具组叠加接口迁移为[viewport labelmap接口](https://www.cornerstonejs.org/docs/api/tools/namespaces/segmentation/functions/addlabelmaprepresentationtoviewport/)，滚轮工具明确注册。组件复用并改为三视图共享一个TiledRenderingEngine上下文。等待SEGMENTATION_RENDERED后恢复相机，避免异步添加mask重置物理切片。卸载禁用十字线监听、清理自己的volume/image缓存、销毁引擎后主动释放上下文。

使用当前已存在的nifti-reader-js0.6.9解析原字节并经Cornerstone5.7.0 createLocalVolume接入；没有调用旧组件的流式NIfTI加载路径。原因：需要明确保留体素顺序、RAS→LPS mm变换、sform优先、数据缩放/endian，以及模型mask缺失单位的可审计处理。适配代码niftiGeometry.js与独立nibabel参考逐体素验证。模型mask未知单位只在其shape/affine/spacing与明确毫米MRI相同时接受，不修改文件；其他未知单位MRI、剪切、非有限体素、多体数据及非法mask标签拒绝。

原字节GET /mri/{case_id}/nifti不接受任意文件路径；绑定latest MRI ID、指定审计序列与size/mtime revision，经既有四序列空间检查后读取，版本变化409，错网格422，Cache-Control:no-store。mtime/size保护是当前非对抗性版本保护，非安全防篡改认证。切换序列重新核查分割版本/有效性，不改分析/报告/概率。

events3.3.0为vtk.js传递XML依赖提供浏览器EventEmitter，官方npm源锁定；nifti-reader-js从既有传递包改为显式精确依赖，版本/SRI保持。只新增一个安装包，不升级其余依赖。Vite别名指向本地浏览器实现；没有改变浏览器安全设置。

## 本次证据

- geometry/reference.json、geometry/validation.json：4真实MRI及真实mask各8,928,000体素，所有体素SHA与nibabel相同，原始文件SHA不变；代表点LPS坐标一致。2明确合成NIfTI1/2夹具验证非单位spacing、轴置换/翻转、sform/qform优先和slope/intercept；不是患者或DICOM。
- backend-final.log：27通过、4既有FastAPI弃用警告；覆盖四序列原字节、MRI版本/文件revision拒绝及错位拒绝、既有空间/分析与报告保护。
- browser-final-complete/validation.json：真实HTTP病例17、三canvas、实际鼠标滚动/窗宽窗位/平移/缩放、十字线中心拖动、四序列保留完整相机参数、每视图MRI+mask actor；非空叠加开关改变实际像素，显式Canvas往返与刷新，加载中取消/重开及SPA退出后engine/cache=0。控制422和控制请求延迟仅验证异常交互，不冒充真实坏病例。
- browser-final-complete/*.png：原始截图，nonempty-overlay及overlay-hidden实际查看，四序列截图和explicit-error保留。未裁剪/修改科学图像强度/拼接。
- 主动WEBGL_lose_context后库记录4条属于已销毁引擎的context lost警告。限定已观察/已销毁ID的预期清理事件；没有“Too many active WebGL contexts”。pageErrors=0、业务写请求=0；控制422的HTTP控制台记录保留。
- build-final-verified.log/build-final-verified：最终渲染实现构建通过；Cornerstone异步chunk约3.4MB，体积警告保留，首加载时间仅本机病例/缓存条件下观测，不外推性能。
- database-backup/validation.json：重启前SQLite快照及独立恢复副本完整性通过。summary.json最终核对全表与快照一致、科学文件SHA、源码SHA及服务身份。

## 失败历史与剩余范围

截图复核发现初版隐藏只改变填充，仍残留轮廓；最终改为删除当前viewport的整个labelmap representation，显示时重建并等待渲染后恢复相机。browser-final-complete增加隐藏后仅1个MRI actor/显示后2个actor的检查，最终隐藏截图实际查看无分割轮廓。旧browser-lifecycle-accepted只作隐藏修复前历史，不作为最终该功能验收。最终构建命令一次cwd误用失败，保留build-final-complete.log，正确frontend目录的build-final-verified才是最终构建证据。

旧API/缺events导致真实模块加载失败；初次指定了错误Playwright缓存路径，复用既有正确E盘路径后解决；Vite别名初版在包安装完成前重启失败，已用绝对浏览器模块地址修复。模型mask未知单位初版拒绝，增加严格毫米参考处理。合成NIfTI2头类型检查初版错误已修复。十字线点击测试未改变视图，缩小为实测中心拖动；切序列位置重置由异步mask actor查明并修复。首轮生命周期检测出WebGL context累积；Tiled+主动释放后只有预期销毁警告。加载中诊断读取未创建VOI导致测试工具失败，改为允许尚未就绪的诊断字段，产品仍保持加载态；所有失败目录保留，不作为最终验收。

尚未验收：Cornerstone物理测量创建/数据库保存/刷新/删除，视图持久化恢复，方向文字标记与非单位spacing浏览器、另一病例切换、生产构建真实HTTP运行、自然浏览器关闭/其他浏览器，以及全部DICOM/PACS与DICOM到AI桥接。原Canvas十工具/报告PDF历史验收继续保留，但不能替代上述新路径。下一步P1-c首先设计世界坐标标注版本载荷，再在隔离库验证保存刷新，原mask始终只读。
