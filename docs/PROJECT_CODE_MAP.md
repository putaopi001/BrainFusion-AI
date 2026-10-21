# 项目入口地图（带教版）

更新：2026-10-18（北京时间）。本图用于带教时从页面追到接口和保存位置。最新版本已加载网页四序列方案/持久作业入口；具体版本和证据见当前阶段记录。真实DICOM→四序列AI闭环仍待合格同检查样本，合成测试不替代真实验收。

## 从页面找到实现

| 用户看到的入口 | 前端起点 | 后续代码与用途 |
|---|---|---|
| 检查/病例列表 | `frontend/src/router/index.js` 的 `/cases` → `frontend/src/views/Cases.vue` | 选病例进入 `/case/:id`，用于病例上下文；病例详情含影像来源、分析状态和医生复核入口。 |
| 病例详情 / DICOM来源 | `/case/:id` → `frontend/src/views/CaseDetail.vue`，其中加载 `frontend/src/components/PacsPanel.vue` | `PacsPanel.vue` 调用 `/pacs/status`、病例检查关联、转换版本、角色审核与激活路由。DICOM阅片可用与四序列模型输入可用是两个独立条件。 |
| 工作站 / Cornerstone | `/workstation/:id` → `frontend/src/views/Workstation.vue` → `frontend/src/components/mri/CornerstoneViewer.vue` | `frontend/src/api/axios.js` 将请求指向后端；MRI/NIfTI和PACS帧读取各有不同API。十字线、空间测量和mask显示绑定相应来源/几何信息。 |
| 分割分析 | `/analysis?case_id=…` → `frontend/src/views/Analysis.vue` | `POST /analysis/{case_id}` 创建任务，页面轮询 `GET /analysis/{case_id}`；服务入口在 `backend/app/api/analysis.py`，串行执行与结果落库在 `backend/app/services/analysis_jobs.py`，固定分割输入/模型由 `backend/app/ai/imaging/monai_segmenter.py` 处理。 |
| 自动掩膜特征研究 | `/research?case_id=…` → `frontend/src/views/Research.vue` | API在 `backend/app/api/research.py`，特征任务及临床输入与分析版本关联；这是研究输出，不能当诊断或通用风险。 |
| 报告/PDF | `/report?case_id=…` → `frontend/src/views/Report.vue` | 使用当前成功且未过期的分析和报告API；DICOM阅片报告是独立的来源报告。两类报告不能互相替代。 |

## 后端入口与数据落点

FastAPI在 `backend/app/main.py` 挂载API路由并载入模型表。病例/患者、MRI、分析、研究、PACS与审核、账户、报告分别从 `backend/app/api/` 与 `backend/app/models/` 进入。当前常用表包括 `patients`、`cases`、`mris`、`analysis_runs`、`mri_features`、`reports`、`doctor_opinions`、`pacs_study_links`、`dicom_reading_reviews`、`dicom_world_measurements`、`dicom_view_states`。数据库主要保存关系、版本、任务状态及来源元数据；MRI、mask、转换文件与运行日志保存在登记的E盘数据目录。`analysis_runs.mri_id`绑定任务输入MRI；结果失效时历史记录保留，但不作为当前成功结果展示。

## DICOM转换与当前边界

转换器 `backend/app/services/dicom_conversion.py` 从经审核的计划和原DICOM文件生成四个NIfTI衍生物，并比较原始像素、空间几何和输出哈希；命令行入口是 `backend/tools/convert_dicom_model_input.py`。转换版本只读索引及完整性复核在 `backend/app/services/dicom_conversion_registry.py` 与 `backend/app/services/dicom_conversion_integrity.py`。病例侧角色确认和激活路由位于 `backend/app/api/pacs.py`：角色确认依赖本地医生账户，激活只替换病例当前MRI并保留旧分析，不会自动推理；分析提交进一步核对审核时记录的四个文件哈希。

当前状态与缺口：病例PACS页面现可在同一关联检查内选择四个不同序列、预览空间合同、核验并捕获归档原始字节、创建持久作业，医生可显式启动、查看进度并重试。版本登记、角色审核、激活及分析入口间的哈希绑定有隔离工程链测试；成功转换不会自动激活/推理，激活后分析还会校验审核时四个文件的哈希。联合快照也已纳入转换索引、草稿、捕获原文件、作业和输出的路径重定位。以上组件仍未通过真实四序列链路验收：本机最近一次只读PACS清点为1检查/1序列；没有真实角色复核、转换、AI分析或真实转换材料恢复。禁止从另一病例借用结果、猜测角色或静默重采样。

## 如何带教时追一条请求

1. 在浏览器打开病例详情，确认病例编号，再看 `PacsPanel.vue` 中请求路径。
2. 用路径在 `backend/app/api/` 定位处理函数，继续追到 `services/`，最后在 `models/` 查保存字段和关联表。
3. 对工作站路径，追 `Workstation.vue` → `CornerstoneViewer.vue` → `/mri` 或 `/pacs` 路由；比较 `nifti` 与 `dicom` 的来源参数，不把同一页面误认为同一数据链。
4. 只读排查先用 `backend/tools/status_local.ps1` 看真实服务身份和健康；需要重启、备份或数据库操作时按操作指南和交付流程执行，不要手工终止不明PID。

## 常用运行/排错入口

| 目的 | 入口 | 注意事项 |
|---|---|---|
| 启动/复用本地服务 | `backend/tools/start_local.ps1` | 会复用已登记实例；先看控制台摘要与登记路径。 |
| 只读健康和PID核验 | `backend/tools/status_local.ps1` | 同时核后端、前端、PACS端口及登记进程；HTTP成功不等于数据库/归档数据可读。 |
| 受控停止 | `backend/tools/stop_local.ps1` | 只使用登记的服务身份，不按端口随意杀进程。 |
| 日志/登记 | `E:/BrainFusion-Runtime/local/` 与对应nightly证据目录 | 先从本轮启动记录定位具体日志；不要猜文件名或展示账户密钥。 |

## 本轮基线

2026-10-17 16:02检查：backend PID 6744、frontend PID 27024、Orthanc PID 12432，状态脚本报告三者健康且实际拥有监听端口；退出观察PID 15108实际存在，原截止UTC 2026-10-17T09:17:10.678743Z（北京时间17:17:10），`holds_development_lock=false`。这是单次实况，不构成跨夜稳定性验收。源码工作区含大量既有未提交改动；无提交或发布。


## 本图所核查的源码文件

前端：frontend/src/router/index.js、frontend/src/api/axios.js、frontend/src/views/Cases.vue、frontend/src/views/CaseDetail.vue、frontend/src/views/Workstation.vue、frontend/src/views/Analysis.vue、frontend/src/views/Research.vue、frontend/src/views/Report.vue、frontend/src/components/PacsPanel.vue、frontend/src/components/mri/CornerstoneViewer.vue。

后端：backend/app/main.py、backend/app/api/pacs.py、backend/app/api/analysis.py、backend/app/api/research.py、backend/app/api/reports.py、backend/app/api/local_auth.py、backend/app/services/analysis_jobs.py、backend/app/services/dicom_conversion.py、backend/app/services/dicom_conversion_registry.py、backend/app/services/dicom_conversion_integrity.py、backend/app/services/artifact_integrity.py、backend/tools/start_local.ps1、backend/tools/status_local.ps1、backend/tools/stop_local.ps1。


