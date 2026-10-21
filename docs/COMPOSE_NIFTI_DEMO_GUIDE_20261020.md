# 隔离 Docker NIfTI 演示（2026-10-20）

## 当前入口

本机演示地址：http://127.0.0.1:18180；后端 API：127.0.0.1:18100。当前 Compose 前后端均 healthy，前端已按本项目当前 package-lock 重建。演示使用 case 17 的隔离 NIfTI 副本。

打开页面可查看已有病例详情、影像预览、历史分割和报告。Cornerstone 三视图可以显示并切换 t1c/t1n/t2w/t2f。已在 Microsoft Edge 对 Docker 生产前端实测，四序列均能切换、没有页面错误、没有写请求；测量和视图状态保持未保存。浏览时请只读，不要上传、删除、导入或重新运行分析。

## 演示范围

Compose runtime 使用修复后的独立副本：外部 staging 曾漏改 MRI 的序列路径和分析掩膜路径，已全部改写到容器内路径。副本包含 197 个所引用文件，源 SQLite 数据库 SHA-256 前后相同。源库未被修改。

本演示验证已有 NIfTI 案例的 Docker 页面、四序列查看、文件服务和只读 API；不代表真实四序列 DICOM、DICOM→AI 转换、临床效能、干净新机器安装或最终发布包已验收。历史结果不是本次重新推理生成。容器中的研究、模型、配置、数据集和 PACS 派生挂载为只读。

结构化记录：本目录下的 runtime-staging.json、compose-switch.json、compose-frontend-rebuild.json、compose-real-nifti-viewer.json。完整说明见 docs/NIFTI_DEMO_AND_FRONTEND_SECURITY_20261020.md。

## 结束演示

在 PowerShell 中执行：

    docker compose --env-file "E://BrainFusion-Runtime//results//nightly//2026-10-20//20261020T1815_real_nifti_compose_demo_fixed//compose-demo.env" down

这会停止并移除演示容器和网络，不会删除隔离运行目录或原始项目数据库。若只关闭浏览器，容器仍会继续运行。再次演示前先确认容器现状，不要同时启动另一套映射到相同端口的项目。

## 当前隔离目录

E://BrainFusion-Runtime//results//nightly//2026-10-20//20261020T1815_real_nifti_compose_demo_fixed//

所有演示数据写入都位于该目录的 runtime 克隆内。不要把其中数据库或上传目录复制回正式运行数据。
