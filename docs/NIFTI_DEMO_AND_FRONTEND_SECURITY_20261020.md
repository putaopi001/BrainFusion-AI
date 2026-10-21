# 2026-10-20 NIfTI Docker 演示路径修复与前端依赖安全更新

隔离演示 case 17 原本通过 Docker 健康检查，但业务接口返回 422：外部 staging 脚本漏改 mris.sequences_json 和分析掩膜路径。已修复所有 MRI、序列和 mask_path 到容器内路径，复制197个文件、约386.7 MB；源 SQLite 完整性检查为 ok，源库 SHA-256 前后相同。未改原归档、未导入病例、未读 PixelData、未推理。Compose 健康检查使用 /，不是 /health；修正后病例测量、视图状态接口 HTTP 200，前后端 healthy。

Docker 前端用最终依赖锁重建后，Edge 只读检查通过：NIfTI Cornerstone ready，三视图画布，t1c/t1n/t2w/t2f可切换；0写请求、0页面错误，无保存测量或视图状态。这是已有 NIfTI 工程链路，不代表真实 DICOM 或效能验证。

原锁文件 npm audit 有11项。五个 Cornerstone 包对齐到5.7.3，直接声明 @cornerstonejs/metadata 5.7.3；adm-zip固定0.6.1，uuid固定11.1.1。fflate采用包范围 override：仅为 @kitware/vtk.js 和 nifti-reader-js固定已修复的0.7.5，保留 jsPDF所需的0.8.3，避免全局 override 造成 npm ls invalid。GitHub Advisory 列出0.7.5和0.8.3均为该漏洞修复版本。

最终 npm audit 为0项，npm ls --all通过，npm ci、生产构建通过。Edge E2E最终8 passed、1 skipped；一次PDF下载等待超时后，PDF单测与完整E2E重跑均通过。Docker镜像按最终锁文件重建，生产页面复测通过。

证据：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T1815_real_nifti_compose_demo_fixed/。

仍未完成：公开数据烧录文字人审、真实四序列DICOM身份/授权/角色/共同空间及AI闭环；最终冻结和交付、材料恢复验证、独立维护手册、用户带教与导师预演。