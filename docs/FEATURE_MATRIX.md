# BrainFusion-AI 功能矩阵

## 2026-10-26 P0/P2 final research status

This snapshot supersedes the older 2026-10-25 snapshot below; those entries are retained as history.

- **SegResNet:** one approved isolated sub-002 CUDA inference remains the only run; no rerun. Public-reference **WT-only agreement PASS**: Dice 0.759799, HD95 20.074860 mm, precision 0.953595, recall 0.631468; prediction/reference volumes 140.221/211.751 ml. Same-grid and existing backend metric cross-check passed. This is a single-case agreement, not an external performance estimate.
- **TC/ET reference metrics:** `NOT_RUN`; public mask values are 0/1/2/3 but authoritative per-file class mapping/conversion from BraTS 0/1/2/4 is unavailable. Expert-reviewed status for sub-002 is unverified; training-set overlap is unknown.
- **UPENN clinical OS:** patient-level structural audit passed (611 baseline, 60 follow-up; 41 paired and 19 follow-up-only). A 608-row event/censor candidate is `PROVISIONAL` only. The endpoint is not validated, because v25 lacks authoritative censor semantics/time unit and the 452-vs-608 version difference is unreconciled. Real KM/Cox are `NOT_RUN`; synthetic software status remains separately passed. No patient risk estimate was generated.
- **Formal release:** geometry-fix release `VERIFIED` by 2026-10-25 acceptance evidence. Not redeployed or re-tested in this science-only pass.
- Reproducibility evidence and hashes: `E:\BrainFusion-Runtime\research-edition\results\p0-p2-final-science-20261026\`.

更新：2026-10-25（最终冲刺授权后复核）。下方较早条目保留历史；如与“2026-10-25 当前核验快照”冲突，以该快照和对应运行证据为准。

## 2026-10-25 当前核验快照

- **正式发布 PASS**：按获批 Runbook 将 `bf-rc-20261022.1-geometry-fix` 部署到正式 backend/frontend。容器健康，18100/18180 HTTP 200；目标镜像 ID、回滚镜像、数据库备份及 197 个运行文件均已核验。SQLite `integrity_check=ok`、零 FK 违规；病例 17/19 与备份逻辑记录一致；没有执行数据库恢复或迁移。正式 PACS、DICOM view、pixel read、AI bridge 门控均保持关闭。证据：`E:\BrainFusion-Runtime\research-edition\evidence\release-geometry-fix-20261025.json`。
- **UPENN sub-002 单例探索性推理 PASS**：使用官方共配准 NIfTI、MONAI BraTS SegResNet 固定权重，在隔离科研环境的 RTX 5070 Ti Laptop CUDA 执行一次推理。输入/模型 SHA、版本、运行设备与输出已记录。输出是工程探索结果，不是临床验证。使用受显存约束的滑窗 ROI `[128,128,96]`，不同于官方 bundle ROI `[240,240,160]`；该差异必须在解释结果时披露。预测掩膜、WT/TC/ET 体积和三平面叠加图见 `E:\BrainFusion-Runtime\research-edition\results\upenn-sub002-segresnet-20261025\run-20261025T222645`。
- **真实标签评价 NOT_RUN**：候选参考标签与 MRI 共空间，但该受试者的人工/算法标签来源及整数类别语义尚未确认；未计算 Dice、HD95、precision 或 recall。不能把这一预测作为模型性能声明。
- **生存软件 PASS / 真实队列 BLOCKED_BY_DATA_DICTIONARY**：IDC v25 聚合复核为 671 行/630 个 DICOM PatientID，611 条基线影像记录；按尚未确认的列映射得到 608 条候选 OS（585 候选事件、23 候选删失、3 条状态不确定）。官方队列论文报告 OS 可用人数为 452；现有证据不能逐列解释两者差异。未拟合真实 KM/Cox，也未建立 sub-002 与临床表的患者级 crosswalk。
- **影像组学与分割评价软件**：影像组学新任务 SQL/API/进程重启/CSV 核验 PASS（20 项特征，未重跑分割）；同一新任务 Edge 回放因本机执行策略拒绝后台监听启动而未运行，未绕过策略。分割评价 API/UI 的隔离合成数据验收 PASS，不代表真实标签性能。
- **Git**：本轮文档完成后记录最终提交与远程核验 SHA；既有未跟踪 `data/` 不纳入提交。

## 最终交付分类

- **已完成并通过验收**：隔离 DICOM 导入/QIDO/WADO/Cornerstone 真实像素阅片；合格 WAW 工程样本 SegResNet、掩膜、WT/TC/ET、报告持久化及前端流程；影像组学 SQL/API/Edge/CSV 集成回放；分割评价 API/UI 的合成工程验收；现有冻结版正式服务健康。
- **已实现但未发布**：`bf-rc-20261022.1-geometry-fix` 后端与前端镜像。克隆正式库启动及最终只读预检通过，正式替换未执行。
- **等待人工批准**：唯一正式部署操作仍需明确批准；UPENN 模型输入清单需本人实际审核签署后，才可决定是否批准隔离工程推理。
- **BLOCKED_BY_DATA**：生存研究/预测因 OS 起点不一致、无可验证共同时间零点及本地数据用途限制而阻断。

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
| 9 | 四序列配准与标准化 | 后端审核/准备流程 | `backend/app/services/dicom_resampling.py`、`backend/app/services/dicom_input_plan.py`、`backend/app/services/study_validation.py` | **正式 geometry-fix 已发布；sub-002 官方共配准输入 QC 通过** | 既有原始 DICOM 配准候选的覆盖局限仍不得推断为肿瘤 ROI 覆盖；本次推理直接使用官方共配准输入 |
| 10 | MONAI SegResNet 分割 | 病例分析入口/API | `backend/app/ai/imaging/monai_segmenter.py`、`backend/app/api/analysis.py` | **隔离真实推理通过**：WAW 工程样本，以及获批的一次官方 UPENN sub-002 CUDA 探索推理均有独立证据 | sub-002 使用显存约束滑窗 ROI，与官方配置不同；不是临床验证。无已核实参考标签语义/来源，未计算真实性能指标 |
| 11 | 掩膜可视化 | NIfTI 工作站“显示/隐藏分割” | `frontend/src/components/mri/CornerstoneViewer.vue`、`backend/app/api/mri.py` | **隔离实测**：工作站提供三正交 canvas；真实输出掩膜开关可用 | 结果须人工核对；演示标识不是临床审核签署 |
| 12 | WT/TC/ET 体积与分割评价 | 病例报告、`/research/cases/{case_id}/analysis/{analysis_run_id}/segmentation-evaluation` 及 `.csv` | `backend/app/services/segmentation_metrics.py`、`backend/app/services/segmentation_evaluation.py`、`backend/app/api/research.py`、`frontend/src/views/Research.vue` | **合成软件验收 PASS**：受控 NIfTI 上传、登录/授权门控、病例与当前分析来源校验、shape/affine 检查、WT/TC/ET Dice、HD95(mm)、precision/recall、TP/FP/FN、幂等记录及 CSV；定向 pytest 22 passed；隔离 FastAPI→Vue→Edge→CSV 实测无浏览器/请求错误 | 仅合成工程标签，未评价真实患者参考标注，不能作为模型准确率；本地 doctor 会话不验证外部研究授权或专业资质。无标签时为 `NOT_AVAILABLE`；评价证据保存在隔离上传 runtime，不新增数据库 schema |
| 13 | 分析任务状态与失败处理 | `/analysis`、病例详情分析历史 | `backend/app/services/analysis_jobs.py`、`backend/app/api/analysis.py` | **部分隔离验证**：RC 运行记录 `succeeded` 并可在服务重启后读取；历史 `test_analysis_state.py` 存在 | 重试/崩溃恢复的全路径未在本次 RC 执行；失败任务须检查日志再重试 |
| 14 | Prediction 与生存研究 | `/analysis`、`/research`、病例详情 | `backend/app/api/predict.py`、`backend/app/api/predictions.py`、`backend/app/api/cases.py`、`backend/app/api/research.py`、`backend/app/research/survival.py` | **研究数据 BLOCKED_BY_DATA；软件 API/UI 已联调**：状态、终点校验、Kaplan–Meier、Cox PH API 均可用；Research 页面从真实 API 显示数据阻断；合成 API 计算与未授权请求拒绝已通过 | 没有患者级拟合；Schoenfeld 趋势仅为未校正筛查，不是正式比例风险检验。RSF 依赖 `sksurv` 当前未安装。数据许可和逐例起点获核验前不提交真实队列，不输出个体预测 |
| 15 | 影像组学及研究分析 | `/research` | `backend/app/api/research.py`、`backend/app/services/feature_jobs.py`、`backend/tools/extract_selected_radiomics.py`、`frontend/src/views/Research.vue` | **隔离新任务 SQL→FastAPI→CSV PASS；Vue/Edge 既有 live E2E PASS**：2026-10-25 使用已有获准工程 MRI/模型掩膜创建新特征任务，20 项 PyRadiomics 特征成功写入隔离 SQLite；重试复用同一 job ID，第二个 FastAPI 进程重启后仍能读取，20 行 CSV 数值与 SQL/API 的任务、模型、输入及掩膜指纹一致。既有 Edge live API E2E 回放证据仍有效 | 新任务本轮因本机策略拒绝后台服务启动，未在 Edge 中重新打开该任务；TestClient 验收不冒充浏览器网络测试。正式数据库、病例及服务未改；详细范围见 runtime evidence `radiomics-live-20261025` |
| 16 | 结构化报告 | `/report?case_id=1` | `backend/app/api/reports.py`、`backend/app/services/current_report.py`、`frontend/src/views/Report.vue` | **隔离实测**：Edge 展示该次分析的模型、体积、限制和来源追溯 | 医生复核显示“待复核”；报告不是临床诊断 |
| 17 | 结果与报告版本关联 | 报告页及病例分析历史 | `backend/app/models/analysis_run.py`、`backend/app/models/report.py`、`backend/app/services/artifact_integrity.py` | **隔离实测**：analysis run 与 report 同 ID 关联；后端重启后结果/掩膜/报告仍存在 | 当前新 RC 只演示一个分析版本；多版本比较场景未在本次彩排 |
| 18 | 用户身份、角色与审核权限 | 本地登录/复核界面 | `backend/app/api/local_auth.py`、`backend/app/services/local_auth.py`、`backend/app/core/dependencies.py` | **隔离实测**：合成本地 doctor 会话完成登录、CSRF 保护的评价读取/上传/CSV；未登录与未授权写入有 401/403 定向测试 | 本地账户只作操作归属，不代表执业资质、数据许可或第二审核人；正式账户环境未在本轮操作 |
| 19 | 前后端部署 | 正式/隔离 Docker Compose | `docker-compose.rc.yml`、正式审批包、`backend/Dockerfile`、`frontend/Dockerfile` | **正式 geometry-fix 发布 PASS**：18100/18180 healthy，镜像与 Runbook 目标匹配；SQLite、病例 17/19、197 个运行文件验收通过 | 回滚镜像及 Runbook 保留；正式 PACS/像素/AI bridge 门控仍关闭 |
| 20 | 数据备份与恢复 | `E:\BrainFusion-Runtime\backups` | SQLite 官方在线备份；部署验收记录 | **发布前后验收通过**：备份 `integrity_check=ok`/零 FK 违规；正式 DB 与备份逻辑表内容一致；197/197 运行文件哈希匹配 | 回滚基线保留；本次未执行数据库恢复或迁移 |
| 21 | 日志与错误处理 | Docker logs、PACS 状态与 API 错误 | `backend/app/core/logging.py`、`backend/app/services/worker_error.py` | **部分实测**：容器健康检查与 API fail-closed 状态可读；浏览器彩排无失败请求 | 未对所有故障注入；日志可能含敏感元数据，不应直接外传 |
| 22 | LLM 报告、RAG、多模态 MRI | 暂无产品入口 | 暂无本 RC 服务实现 | **本轮不实现；仅未来规划** | 后续需独立方案、数据授权、评测和安全边界；不能宣传为当前功能 |

## 当前 RC 复核记录

- RC 地址：`http://127.0.0.1:18184`；API `http://127.0.0.1:18104`。
- 演示病例：病例 1，`RC-Engineering-Smoke`。输入为已有四序列 WAW-GliomAI 工程样本，不是 UPENN。
- SegResNet 真推理、掩膜、体积、报告关联和重启后持久化：见 [`RELEASE_CANDIDATE_20261021.md`](RELEASE_CANDIDATE_20261021.md)。
- WAW 工程样本 Edge 彩排：四序列 NIfTI、三画布、真实分析掩膜和报告可见；这与 UPENN DICOM 浏览验收是两条不同数据路径。
- 本轮核心定向回归 196 passed、4 个既有 deprecation warnings；证据见 `E:\BrainFusion-Runtime\results\dicom-pacs-acceptance-20261021\evidence\core-pytest-20261022.xml`。前端生产构建通过；依赖 externalization/大 chunk 为构建警告。
- UPENN 浏览证据：`E:\BrainFusion-Runtime\results\dicom-pacs-acceptance-20261021\evidence\upenn-cornerstone-browser-fix.json`。模型输入审核未签字，因此无 UPENN SegResNet 结果。

## 研究增强版分割评价验收

- 评价接口需要本地 doctor 会话、显式研究用途确认和用户上传的 NIfTI 参考标注；服务不接受任意磁盘路径。预测掩膜由已成功且仍关联当前 MRI 的分析任务解析，所有四序列、预测和参考标注必须处于同一 shape/affine 物理空间。
- 各病例/分析任务的评价记录与上传标注保存在配置的隔离 upload runtime，不修改正式数据库 schema。标注编号和授权凭据正文不持久化，只保存摘要；本地登录只作操作归属，不代表核实外部授权或专业资质。
- 22 个定向后端测试通过；生产前端构建通过；Microsoft Edge 对隔离 synthetic backend 完成登录、读取分析历史、上传合成标签、显示三分区指标并下载三行 CSV。证据位于 `E:\BrainFusion-Runtime\research-edition\evidence\segmentation-evaluation-live-20261022`。没有计算真实患者 Dice/HD95。


## Final science closeout — 2026-10-26

| Area | Current evidence status | Boundary |
|---|---|---|
| UPENN sub-002 segmentation | PASS — one-case `PUBLIC_REFERENCE_AGREEMENT`; WT/TC/ET metrics and overlay saved under `E:\BrainFusion-Runtime\research-edition\results\p0-p2-final-science-20261026-v2` | Not independent external validation: checkpoint training overlap unknown; one subject only. Reference per-case named reviewer record unavailable.
| Clinical OS cohort audit | PASS for source/version and cohort-flow audit; 671 scan rows, 630 normalized persons, 611 baseline, 60 follow-up | Candidate endpoint remains unvalidated; baseline-only 608 is provisional, not a formal cohort.
| KM/Cox on clinical mirror | EXPLORATORY only | Provisional mapping; not a validated endpoint, not clinical prediction. Age PH trend screen flags concern.
| One-year survival classification | NOT_RUN | Censor-time semantics lack authoritative definition.
| Synthetic survival software checks | PASS, 4/4 | Engineering-only fixtures, no clinical inference.
| Imaging-clinical fusion | BLOCKED | Authoritative patient crosswalk unavailable.
| Formal geometry-fix release | PASS read-only current check | Containers healthy; PACS import/read/DICOM/pixel/AI gates remain disabled. Current DB integrity was not retested in this snapshot; prior release acceptance evidence retained.

See `FINAL-RESEARCH-CLOSEOUT.md` in the versioned runtime evidence directory for exact methods, counts, sources and limitations.

### Official clinical v1.2 survival audit update — 2026-10-26

| Feature | Current status | Evidence / boundary |
|---|---|---|
| Clinical v1.2 source and cohort audit | PASS (aggregate only) | 671 rows; 630 people; 611 baseline; 60 follow-up; official-designated CSV byte-identical to pinned mirror; all scan keys and comparable fields agree with IDC v25. No patient rows are in repository. |
| Candidate OS endpoint | BLOCKED_BY_DATA_DICTIONARY | `Survival_Censor` unit/origin/last-contact rule and updated-time derivation remain undefined; 452/608/668 denominators unreconciled. |
| KM sensitivity | EXPLORATORY_COMPLETE | N=608 (585 events/23 censored) and N=611 sensitivity (585/26); both median 409 days, 95% CI 376–443. Not validated clinical OS. |
| Cox | EXPLORATORY, reused | Prior complete-case N=570 result references byte-identical source content; no refit and no individual predictions. |
| One-year survival prediction | NOT_RUN | Endpoint and censor semantics not validated. |
