# BrainFusion-AI 功能矩阵

更新：2026-10-21。状态含义：**隔离实测**＝本机 RC/独立环境实测；**条件通过**＝实现或工程候选已验证但仍有人审/数据条件；**仅代码/历史测试**＝未在本次 RC 完整验证；**阻断**＝安全门控或外部条件不满足；**未实现/规划**＝没有可交付实现。

| # | 功能 | 用户入口 | 代码入口 | 状态及证据 | 限制与下一步 |
|---|---|---|---|---|---|
| 1 | 病例管理 | `/cases`、`/case/:id` | `backend/app/api/cases.py`、`backend/app/models/case.py` | **隔离实测**：RC 病例 API 与 Edge 病例详情可用，病例 1 有已分析状态 | 当前演示病例仅用于工程样本；正式病例访问未验证 |
| 2 | 影像上传与数据管理 | `/upload-mri/:case_id` | `backend/app/api/upload.py`、`backend/app/core/storage.py` | **隔离实测**：四个已存在 NIfTI 被上传到新 RC 病例并用于真实推理 | 只允许有许可、身份和来源记录的影像；DICOM 导入仍关 |
| 3 | NIfTI 浏览及四序列切换 | `/workstation/:id` | `frontend/src/components/mri/CornerstoneViewer.vue`、`frontend/src/views/Workstation.vue`、`backend/app/api/mri.py` | **隔离实测**：Edge 逐个切换 T1c/T1n/T2w/FLAIR，三画布保持 ready，无 JS/网络错误 | 仅同空间四序列样本；不自动配准或重采样 |
| 4 | DICOM 导入与审核 | 病例详情 PACS 面板 | `backend/app/api/pacs.py`、`backend/app/services/pacs_import.py`、`frontend/src/components/pacs/PacsPanel.vue` | **阻断且默认拒绝**：RC 状态为 `import_available=false`，导入候选数为 0 | UPENN 人工隐私、身份、序列和授权检查完成后才可在隔离环境试导入 |
| 5 | Orthanc PACS | 独立服务 `127.0.0.1:18142` | `backend/app/services/pacs_client.py`；`E:\BrainFusion-Runtime\stage7_orthanc_20261021\orthanc.json` | **隔离条件通过**：独立容器与独立卷仍运行；此前认证 `/system` 及空档案查询通过；本轮无凭据请求返回 401 | 本轮复用的认证凭据未通过；未改配置/卷。需要维护者按本机秘密管理流程验证凭据 |
| 6 | DICOMweb Study/Series/Instance 查询 | PACS 面板及后端 DICOMweb API | `backend/app/services/pacs_client.py`、`backend/app/services/pacs_wado.py`、`backend/app/api/pacs.py` | **空档案隔离实测**：历史 Stage 7 已认证 QIDO/REST 查询为空；RC `/pacs/studies` 返回 503 且 PACS 未连通 | 未对 UPENN 查询真实实例或像素；须先完成人工审核和认证联调 |
| 7 | Cornerstone DICOM 阅片 | `/workstation/:id?source=dicom...` | `frontend/src/components/mri/CornerstoneViewer.vue`、`backend/app/api/pacs.py` | **未实测真实 DICOM**：代码入口存在；NIfTI 工作站已实测 | 无获准导入的 DICOM 资料；不得把 NIfTI 画布演示描述为真实 DICOM 阅片 |
| 8 | DICOM→NIfTI 转换 | 病例详情“转换作业” | `backend/app/services/dicom_conversion.py`、`backend/app/services/dicom_conversion_jobs.py`、`backend/app/api/pacs.py` | **条件通过**：636 个 UPENN 实例完成解码；四候选序列逐序列转换已有记录 | 源序列各自空间不同；转换不等于空间配准或模型输入批准 |
| 9 | 四序列配准与标准化 | 后端审核/准备流程 | `backend/app/services/dicom_resampling.py`、`backend/app/services/dicom_input_plan.py`、`backend/app/services/study_validation.py` | **工程候选通过、人工复核阻断**：T1c 参考的刚体配准、统一网格和 QC 记录已生成 | 不作为医学合格输入结论；专家复核后再决定是否准入模型 |
| 10 | MONAI SegResNet 分割 | 病例分析入口/API | `backend/app/ai/imaging/monai_segmenter.py`、`backend/app/api/analysis.py` | **隔离真实推理通过**：RC Docker 对已许可 WAW-GliomAI 工程样本执行 MONAI BraTS SegResNet，无 fallback | 单个工程样本不代表临床精度；UPENN 未推理 |
| 11 | 掩膜可视化 | NIfTI 工作站“显示/隐藏分割” | `frontend/src/components/mri/CornerstoneViewer.vue`、`backend/app/api/mri.py` | **隔离实测**：工作站提供三正交 canvas；真实输出掩膜开关可用 | 结果须人工核对；演示标识不是临床审核签署 |
| 12 | WT/TC/ET 体积 | 病例报告与结果区 | `backend/app/services/segmentation_metrics.py`、`backend/app/api/analysis.py` | **隔离实测**：报告显示 WT 6.284、TC 3.374、ET 0.008 mL | 数值来自单次工程样本；区域定义/空间单位须随模型和 affine 核验 |
| 13 | 分析任务状态与失败处理 | `/analysis`、病例详情分析历史 | `backend/app/services/analysis_jobs.py`、`backend/app/api/analysis.py` | **部分隔离验证**：RC 运行记录 `succeeded` 并可在服务重启后读取；历史 `test_analysis_state.py` 存在 | 重试/崩溃恢复的全路径未在本次 RC 执行；失败任务须检查日志再重试 |
| 14 | Prediction 与研究模型接口 | `/analysis`、`/research` | `backend/app/api/predict.py`、`backend/app/api/predictions.py`、`backend/app/api/research.py` | **代码存在，未作为本次 RC 验收目标** | 传统预测/研究输出不可等同临床有效模型；需逐模型验证来源、标签与外部验证 |
| 15 | 影像组学及研究分析 | `/research` | `backend/app/research/`、`backend/app/services/research_service.py`、相关 `backend/tests/test_research.py` | **研究代码/测试资产存在；当前 RC 未实测科研队列** | 先完成特征定义、缺失处理、泄漏审查和预注册方案；不用于当前 10 分钟核心演示 |
| 16 | 结构化报告 | `/report?case_id=1` | `backend/app/api/reports.py`、`backend/app/services/current_report.py`、`frontend/src/views/Report.vue` | **隔离实测**：Edge 展示该次分析的模型、体积、限制和来源追溯 | 医生复核显示“待复核”；报告不是临床诊断 |
| 17 | 结果与报告版本关联 | 报告页及病例分析历史 | `backend/app/models/analysis_run.py`、`backend/app/models/report.py`、`backend/app/services/artifact_integrity.py` | **隔离实测**：analysis run 与 report 同 ID 关联；后端重启后结果/掩膜/报告仍存在 | 当前新 RC 只演示一个分析版本；多版本比较场景未在本次彩排 |
| 18 | 用户身份、角色与审核权限 | 本地登录/复核界面 | `backend/app/api/local_auth.py`、`backend/app/services/local_auth.py`、`backend/app/core/dependencies.py` | **隔离代码与既有定向测试**：本地身份接口和权限门控存在；本次只通过 PACS/private-runtime 7 项测试 | 当前 RC 账户不可用性/角色全路径未彩排；账户验证不代表执业资质 |
| 19 | 前后端部署 | RC Docker Compose | `docker-compose.rc.yml`、`backend/Dockerfile`、`frontend/Dockerfile` | **隔离实测**：RC 容器 healthy，API/web 可访问；端口 18104/18184 | 正式容器未重建，保持 Exited；不得把 RC 当正式部署 |
| 20 | 数据备份与恢复 | `E:\BrainFusion-Runtime\backups` | SQLite 标准库在线备份；本地备份清单 | **本轮恢复点通过**：RC DB 以 SQLite online backup 生成且 `integrity_check=ok`；E/C tracked patch reverse-check 通过，最终快照 E/C 的 434/10 个未跟踪源码哈希核对 | 尚未演练全量服务故障还原；正式数据库无本轮备份/写入 |
| 21 | 日志与错误处理 | Docker logs、PACS 状态与 API 错误 | `backend/app/core/logging.py`、`backend/app/services/worker_error.py` | **部分实测**：容器健康检查与 API fail-closed 状态可读；浏览器彩排无失败请求 | 未对所有故障注入；日志可能含敏感元数据，不应直接外传 |
| 22 | LLM 报告、RAG、多模态 MRI | 暂无产品入口 | 暂无本 RC 服务实现 | **本轮不实现；仅未来规划** | 后续需独立方案、数据授权、评测和安全边界；不能宣传为当前功能 |

## 当前 RC 复核记录

- RC 地址：`http://127.0.0.1:18184`；API `http://127.0.0.1:18104`。
- 演示病例：病例 1，`RC-Engineering-Smoke`。输入为已有四序列 WAW-GliomAI 工程样本，不是 UPENN。
- SegResNet 真推理、掩膜、体积、报告关联和重启后持久化：见 [`RELEASE_CANDIDATE_20261021.md`](RELEASE_CANDIDATE_20261021.md)。
- 本轮 Edge 彩排：四序列逐项 ready、三画布、报告中的模型权重和掩膜摘要均可见，0 page error、0 failed request。
- 本轮 7 个测试通过：`test_pacs_runtime_layer.py`、`test_private_runtime_preflight.py`。因现有 Python 环境缺少 `pydicom`，分析/报告/转换/存储测试集合未能启动；不把历史全量测试结果当作本次 RC 结果。
