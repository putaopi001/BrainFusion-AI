# BF-RC-20261021.1 源码冻结记录

## 固定标识

- 唯一主源码目录：`E:\BrainFusion-AI`
- 冻结 tag：`bf-rc-20261021.1-frozen`
- 冻结分支：`main`
- 冻结提交：以该 tag 在本地 Git 中解析出的 commit 为准；精确 SHA、文件清单 SHA-256、Docker image ID 和备份位置记录在 `E:\BrainFusion-Runtime\backups\closeout-20261021T194500\source-freeze.json`。
- 该 tag 仅标识本地发布候选，不会推送到远端。

## 构建与复现边界

- 发布候选使用仓库 Compose/Dockerfile 和已记录的依赖清单构建；容器镜像 ID、构建时间与运行端口在恢复包记录。
- 模型权重以现有文件 SHA-256 标识；复现推理时需使用同一只读权重、同一四序列工程样本和独立 runtime。医学影像结果不构成临床验证。
- 源码恢复优先从 E 盘恢复包的 Git bundle 克隆/检出冻结 tag，再依照同目录恢复说明恢复 RC SQLite、配置和演示上传文件。不得把 RC 数据库恢复到正式 runtime。
- `data/external/UPENN-GBM` 中的影像及元数据不属于发布源码快照，也不纳入 Git commit；使用仍受隐私、序列和配准审核约束。
- C 盘 Codex worktree 均保留原状并单独快照；只有 E 盘 tag 是本轮唯一发布候选。

## 本轮验证锁定

- 有针对性的 RC pytest 子集：51 passed，4 个上游 deprecation warning。
- RC 工程样本的四序列 NIfTI、真实 SegResNet 推理、掩膜、WT/TC/ET 体积及结构化报告已持久化；报告和任务仍待医生审核。
- Edge 实际页面流：病例详情、NIfTI 工作站、T1c/T1/T2/FLAIR 切片、掩膜显示切换、返回病例和完整报告均通过；页面错误和失败请求均为 0。
- UPENN 推理、真实 PACS 像素阅片和正式服务部署不属于此验证范围，分别保留为受限事项。

## 变更与恢复

提交内容只包含源码、测试和项目文档；本地 UPENN 文件、数据库、日志、模型权重和运行时数据不进入该提交。恢复包含冻结源码 bundle、文件哈希清单、工作区差异快照及 RC 数据的一致性备份。恢复前先核对 SHA-256；Git bundle 可用 `git bundle verify` 校验，RC SQLite 可用 `PRAGMA integrity_check` 校验。
