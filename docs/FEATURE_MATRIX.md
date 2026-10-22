# BrainFusion-AI 功能矩阵

更新：2026-10-22。状态含义：**隔离实测**＝本机 RC/独立环境实测；**条件通过**＝实现或工程候选已验证但仍有人审/数据条件；**仅代码/历史测试**＝未在本次 RC 完整验证；**阻断**＝安全门控或外部条件不满足；**未实现/规划**＝没有可交付实现。

| # | 功能 | 用户入口 | 代码入口 | 状态及证据 | 限制与下一步 |
|---|---|---|---|---|---|
| 1 | 病例管理 | `/cases`、`/case/:id` | `backend/app/api/cases.py`、`backend/app/models/case.py` | **隔离实测**：RC 病例 API 与 Edge 病例详情可用，病例 1 有已分析状态 | 当前演示病例仅用于工程样本；正式病例访问未验证 |
| 2 | 影像上传与数据管理 | `/upload-mri/:case_id` | `backend/app/api/upload.py`、`backend/app/core/storage.py` | **隔离实测**：四个已存在 NIfTI 被上传到新 RC 病例并用于真实推理 | 只允许有许可、身份和来源记录的影像；DICOM 导入仍关 |
| 3 | NIfTI 浏览及四序列切换 | `/workstation/:id` | `frontend/src/components/mri/CornerstoneViewer.vue`、`frontend/src/views/Workstation.vue`、`backend/app/api/mri.py` | **隔离实测**：Edge 逐个切换 T1c/T1n/T2w/FLAIR，三画布保持 ready，无 JS/网络错误 | 仅同空间四序列样本；不自动配准或重采样 |
| 4 | DICOM 导入与审核 | 病例详情 PACS 面板 / 隔离导入流程 | `backend/app/api/pacs.py`、`backend/app/services/pacs_import.py`、`frontend/src/components/pacs/PacsPanel.vue` | **隔离实测**：UPENN-GBM-00001 人工隐私/用途审核后导入独立 Stage7 Orthanc，636/636 SOP UID 匹配；正式导入门控未变 | 仅限隔离阅片验收；未批准送入模型，不代表临床用途授权 |
| 5 | Orthanc PACS | 独立服务 `127.0.0.1:18142` | `backend/app/services/pacs_client.py`；Stage7 独立配置/卷 | **隔离实测**：认证 `/system`、保留合成 Study 并存储 UPENN；独立网络和数据卷 | 不连接正式 Orthanc；凭据仅由本机秘密管理 |
| 6 | DICOMweb Study/Series/Instance 查询 | 隔离阅片工作站及后端代理 | `backend/app/services/pacs_client.py`、`backend/app/services/pacs_wado.py`、`backend/app/api/pacs.py` | **隔离实测**：四序列 QIDO 计数和 SOP UID 集合核验通过；WADO 实例及帧像素读取通过 | 只证明该隔离归档/测试路径可用；正式 PACS 未验收 |
| 7 | Cornerstone DICOM 阅片 | `/workstation/:id?source=dicom...` | `frontend/src/components/mri/CornerstoneViewer.vue`、`backend/app/api/pacs.py` | **隔离真实像素实测**：T1c/T1 各192层、T2 192层、FLAIR 60层；滚动、窗宽窗位及序列切换通过，无浏览器/网络错误 | 三平面渲染不等同于跨序列配准质量或临床阅片认可；仅隔离环境 |
| 8 | DICOM→NIfTI 转换 | 病例详情“转换作业” | `backend/app/services/dicom_conversion.py`、`backend/app/services/dicom_conversion_jobs.py`、`backend/app/api/pacs.py` | **条件通过**：636 个 UPENN 实例完成解码；四候选序列逐序列转换已有记录 | 源序列各自空间不同；转换不等于空间配准或模型输入批准 |
| 9 | 四序列配准与标准化 | 后端审核/准备流程 | `backend/app/services/dicom_resampling.py`、`backend/app/services/dicom_input_plan.py`、`backend/app/services/study_validation.py` | **工程候选通过、人工复核阻断**：刚体变换重放与轴对齐1 mm输入契约通过；覆盖率/QC已保存 | 真实模型输入审核清单尚未签署；不作为医学合格输入结论 |
| 10 | MONAI SegResNet 分割 | 病例分析入口/API | `backend/app/ai/imaging/monai_segmenter.py`、`backend/app/api/analysis.py` | **隔离真实推理通过**：RC Docker 对已许可 WAW-GliomAI 工程样本执行 MONAI BraTS SegResNet，无 fallback | 单个工程样本不代表临床精度；UPENN 未推理 |
| 11 | 掩膜可视化 | NIfTI 工作站“显示/隐藏分割” | `frontend/src/components/mri/CornerstoneViewer.vue`、`backend/app/api/mri.py` | **隔离实测**：工作站提供三正交 canvas；真实输出掩膜开关可用 | 结果须人工核对；演示标识不是临床审核签署 |
| 12 | WT/TC/ET 体积 | 病例报告与结果区 | `backend/app/services/segmentation_metrics.py`、`backend/app/api/analysis.py` | **隔离实测**：报告显示 WT 6.284、TC 3.374、ET 0.008 mL | 数值来自单次工程样本；区域定义/空间单位须随模型和 affine 核验 |
| 13 | 分析任务状态与失败处理 | `/analysis`、病例详情分析历史 | `backend/app/services/analysis_jobs.py`、`backend/app/api/analysis.py` | **部分隔离验证**：RC 运行记录 `succeeded` 并可在服务重启后读取；历史 `test_analysis_state.py` 存在 | 重试/崩溃恢复的全路径未在本次 RC 执行；失败任务须检查日志再重试 |
| 14 | Prediction 与生存研究 | `/analysis`、`/research`、病例详情 | `backend/app/api/predict.py`、`backend/app/api/predictions.py`、`backend/app/api/cases.py`、`backend/app/services/survival_service.py` | **个体生存预测阻断**：生存 API 返回 503；病例页说明没有已验证生存模型；占位启发式无调用方 | 本地 WAW 生存标签时间起点混合/不明确，当前快照限工程 smoke test；不训练、不显示个体风险 |
| 15 | 影像组学及研究分析 | `/research` | `backend/app/research/`、`backend/app/services/research_service.py`、相关 `backend/tests/test_research.py` | **研究代码/测试资产存在；当前 RC 未实测科研队列** | 先完成特征定义、缺失处理、泄漏审查和预注册方案；不用于当前 10 分钟核心演示 |
| 16 | 结构化报告 | `/report?case_id=1` | `backend/app/api/reports.py`、`backend/app/services/current_report.py`、`frontend/src/views/Report.vue` | **隔离实测**：Edge 展示该次分析的模型、体积、限制和来源追溯 | 医生复核显示“待复核”；报告不是临床诊断 |
| 17 | 结果与报告版本关联 | 报告页及病例分析历史 | `backend/app/models/analysis_run.py`、`backend/app/models/report.py`、`backend/app/services/artifact_integrity.py` | **隔离实测**：analysis run 与 report 同 ID 关联；后端重启后结果/掩膜/报告仍存在 | 当前新 RC 只演示一个分析版本；多版本比较场景未在本次彩排 |
| 18 | 用户身份、角色与审核权限 | 本地登录/复核界面 | `backend/app/api/local_auth.py`、`backend/app/services/local_auth.py`、`backend/app/core/dependencies.py` | **隔离代码与既有定向测试**：本地身份接口和权限门控存在；本次只通过 PACS/private-runtime 7 项测试 | 当前 RC 账户不可用性/角色全路径未彩排；账户验证不代表执业资质 |
| 19 | 前后端部署 | 正式/隔离 Docker Compose | `docker-compose.rc.yml`、正式审批包、`backend/Dockerfile`、`frontend/Dockerfile` | **实测**：正式 18100/18180 healthy 且 HTTP 正常；新修复候选 18106/18186 healthy 后已停止；原 `brainfusion-rc-20261021` 容器本来 Exited | 本轮未替换正式/RC 容器；修复候选尚未正式晋级 |
| 20 | 数据备份与恢复 | `E:\BrainFusion-Runtime\backups` | SQLite 官方在线备份；部署验收记录 | **正式部署验收 PASS**：发布前 DB 备份完整；部署后 integrity/外键和预部署逻辑内容/记录数相同，上传文件引用匹配；病例17/19核验通过。证据在 `production-preflight-20261021T205339` | 本轮修复候选仅使用新的空 SQLite；不得覆盖正式备份 |
| 21 | 日志与错误处理 | Docker logs、PACS 状态与 API 错误 | `backend/app/core/logging.py`、`backend/app/services/worker_error.py` | **部分实测**：容器健康检查与 API fail-closed 状态可读；浏览器彩排无失败请求 | 未对所有故障注入；日志可能含敏感元数据，不应直接外传 |
| 22 | LLM 报告、RAG、多模态 MRI | 暂无产品入口 | 暂无本 RC 服务实现 | **本轮不实现；仅未来规划** | 后续需独立方案、数据授权、评测和安全边界；不能宣传为当前功能 |

## 当前 RC 复核记录

- RC 地址：`http://127.0.0.1:18184`；API `http://127.0.0.1:18104`。
- 演示病例：病例 1，`RC-Engineering-Smoke`。输入为已有四序列 WAW-GliomAI 工程样本，不是 UPENN。
- SegResNet 真推理、掩膜、体积、报告关联和重启后持久化：见 [`RELEASE_CANDIDATE_20261021.md`](RELEASE_CANDIDATE_20261021.md)。
- WAW 工程样本 Edge 彩排：四序列 NIfTI、三画布、真实分析掩膜和报告可见；这与 UPENN DICOM 浏览验收是两条不同数据路径。
- 本轮核心定向回归 196 passed、4 个既有 deprecation warnings；证据见 `E:\BrainFusion-Runtime\results\dicom-pacs-acceptance-20261021\evidence\core-pytest-20261022.xml`。前端生产构建通过；依赖 externalization/大 chunk 为构建警告。
- UPENN 浏览证据：`E:\BrainFusion-Runtime\results\dicom-pacs-acceptance-20261021\evidence\upenn-cornerstone-browser-fix.json`。模型输入审核未签字，因此无 UPENN SegResNet 结果。
