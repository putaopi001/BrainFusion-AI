# BrainFusion-AI 功能矩阵

## Latest integrated delivery snapshot — 2026-10-26

This snapshot supersedes earlier entries below about archive import availability, missing sub-002 result navigation, or the prior archive inventory. Dated research summaries remain historical unless explicitly marked current.

- **Isolated DICOM archive: PASS.** `/dicom-archive` revalidates the pre-registered 192-instance public MR derivative. After explicit isolated-use acknowledgement it imported and verified 192/192 instances to Stage7; inventory is 6 studies / 6 series / 844 instances. Edge received 192 real frame responses (HTTP 200). The source contains one MR series, so four-sequence conversion remains blocked; no NIfTI mapping or AI submission was created. Formal PACS is unchanged.
- **UPENN sub-002 result entry: PASS.** `/research/upenn-sub002` reads the existing fixed-hash inputs, SegResNet prediction, overlay and WT/TC/ET `PUBLIC_REFERENCE_AGREEMENT` report. It does not rerun inference or map the result to DICOM/engineering cases. The NIfTI header units are unspecified; the displayed 1 mm grid is permitted only by the fixed-hash inference and spatial-QC contract. This single-case agreement is not independent external validation.
- **UCSF-PDGM clinical Cox: TRAINED / RESEARCH_ONLY.** Official TCIA v5 baseline GBM subset N=367 (223 events/144 censored), age-at-MRI and sex inputs, five-fold patient-level internal validation. Mean fold Harrell C-index 0.6373; pooled out-of-fold 0.6321. Mean-fold IPCW Brier at 365/730/1095 days 0.2082/0.2105/0.1648. Artifact SHA-256 `9ce60525516db23436e818d1e5f84dda71a6fc505889ffefb625bf77646d0016`; protected runtime only, not Git.
- **UCSF FastAPI/Vue integration: PASS for synthetic test.** The real API response drives relative risk, the survival curve and 1/2/3-year values. No prediction row was persisted. The model is single-center and internally validated only; requests remain `SYNTHETIC_TEST`, not clinical predictions and not applicable to UPENN cases.
- **Unified live evidence:** `E:\BrainFusion-Runtime\research-edition\demo\unified-research-demo\evidence\final-integration-e2e-20261026-run4.json` (aggregate-only, `status=PASS`). Formal backend/frontend, database and PACS/DICOM/pixel/AI gates were not changed.

## Latest blocker-resolution snapshot — 2026-10-26

This snapshot supersedes earlier 2026-10-26 research status blocks below; they remain historical records.

- **Imaging-to-clinical crosswalk: PASS at release scan-key level.** Exact full IDs, preserving `_11`/`_21`, joined 671 pinned manifest scans to official clinical v1.2 and availability rows with no unmatched/duplicate keys (611 baseline, 60 follow-up, 630 people; 41 paired and 19 follow-up-only). Pinned mirror manual-mask content proves local `sub-002` reference mask corresponds to `UPENN-GBM-00002_11` after exact local-label `3→4` recoding with zero differing voxels. This is not a DICOM PatientID crosswalk; the four MRI release variants share geometry but are not voxel-identical. The separate UPENN-GBM-00001 DICOM patient was not linked.
- **Official OS endpoint: BLOCKED_BY_DATA_DICTIONARY.** First-surgery context is described in the 2022 cohort paper, but exact updated event-time derivation and `Survival_Censor` unit/origin/last-contact rule remain undocumented in checked publisher assets. The official availability flag marks exactly 452 baseline rows, all deceased with positive updated time; this count alone does not reproduce the paper cohort flow or define a right-censored cohort. BrainIAC's published 668 denominator remains unreconstructed.
- **Researcher-defined OS and fusion: EXPLORATORY.** Using baseline-only candidate endpoint and four outcome-independent CaPTk first-order features, common feature-complete N=596 (574 candidate events, 22 candidate censors) had mean five-fold patient-level CV Harrell C-index: clinical 0.649 (SD 0.025), radiomics 0.527 (SD 0.019), combined 0.651 (SD 0.026). Pooled OOF C-index: 0.649 / 0.507 / 0.647. No fusion gain is demonstrated. These are internal CV results on an unvalidated researcher-defined endpoint, not clinical prediction or external validation. No patient-level risks were saved.
- **sub-002 segmentation:** one existing inference only. Prior WT-only public-reference agreement remains the reported metric; TC/ET are not recalculated in this crosswalk/OS task. The reference content bridge is stronger, but checkpoint training overlap remains unknown; no independent external-validation claim.
- **Formal engineering release:** geometry-fix remains verified from 2026-10-25 evidence; this science task did not deploy or alter production.
- Runtime evidence: `E:\BrainFusion-Runtime\research-edition\results\final-blocker-resolution-20261026\`; patient-level crosswalk is local-only and excluded from Git.

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
| 5 | Orthanc PACS | 独立服务 `127.0.0.1:18142` | `backend/app/services/pacs_client.py`；Stage7 独立配置/卷 | **隔离实测**：认证 `/system`；本轮将已登记并复核的 192 实例公开 MR 派生来源导入 Stage7，核验 192/192；当前 6 Study/6 Series/844 实例 | 只连接隔离 Orthanc；本轮正式服务未变；来源仅限已登记 bundle 与隔离用途 |
| 6 | DICOMweb Study/Series/Instance 查询 | `/dicom-archive` 与后端代理 | `backend/app/services/pacs_client.py`、`backend/app/services/pacs_wado.py`、`backend/app/api/pacs.py` | **隔离 Edge 实测**：当前归档 6/6/844；选定已登记来源检查后真实读取 192 帧，192 个响应 HTTP 200 | Study 保持独立；归档与正式 PACS、NIfTI 病例分离 |
| 7 | Cornerstone DICOM 阅片 | `/dicom-archive` / 隔离阅片页 | `frontend/src/components/mri/CornerstoneViewer.vue`、`backend/app/api/pacs.py` | **隔离真实像素 E2E PASS**：已登记来源可选择，真实 DICOM 帧加载至 viewer-ready；浏览器记录 192 个 HTTP 200 帧响应 | 单一 MR Series；不是四序列配准或临床阅片认可；无病例关联 |
| 8 | DICOM→NIfTI 转换 | 病例详情“转换作业” | `backend/app/services/dicom_conversion.py`、`backend/app/services/dicom_conversion_jobs.py`、`backend/app/api/pacs.py` | **条件通过**：636 个 UPENN 实例完成解码；四候选序列逐序列转换已有记录 | 源序列各自空间不同；转换不等于空间配准或模型输入批准 |
| 9 | 四序列配准与标准化 | 后端审核/准备流程 | `backend/app/services/dicom_resampling.py`、`backend/app/services/dicom_input_plan.py`、`backend/app/services/study_validation.py` | **正式 geometry-fix 已发布；sub-002 官方共配准输入 QC 通过** | 既有原始 DICOM 配准候选的覆盖局限仍不得推断为肿瘤 ROI 覆盖；本次推理直接使用官方共配准输入 |
| 10 | MONAI SegResNet 分割 | 病例分析入口/API；`/research/upenn-sub002` 只读研究入口 | `backend/app/ai/imaging/monai_segmenter.py`、`backend/app/api/analysis.py`、`backend/app/api/upenn_sub002_research.py` | **既有推理和评价复用，浏览器 E2E PASS**：固定哈希 sub-002 预测、四序列、三平面 viewer、叠加图、体积和 WT/TC/ET `PUBLIC_REFERENCE_AGREEMENT` 指标可查看；本轮未推理 | 公开单病例一致性，不是独立外部验证；训练重叠未知；不链接 DICOM `UPENN-GBM-00001` |
| 11 | 掩膜可视化 | NIfTI 工作站“显示/隐藏分割” | `frontend/src/components/mri/CornerstoneViewer.vue`、`backend/app/api/mri.py` | **隔离实测**：工作站提供三正交 canvas；真实输出掩膜开关可用 | 结果须人工核对；演示标识不是临床审核签署 |
| 12 | WT/TC/ET 体积与分割评价 | 病例报告、`/research/cases/{case_id}/analysis/{analysis_run_id}/segmentation-evaluation` 及 `.csv` | `backend/app/services/segmentation_metrics.py`、`backend/app/services/segmentation_evaluation.py`、`backend/app/api/research.py`、`frontend/src/views/Research.vue` | **合成软件验收 PASS**：受控 NIfTI 上传、登录/授权门控、病例与当前分析来源校验、shape/affine 检查、WT/TC/ET Dice、HD95(mm)、precision/recall、TP/FP/FN、幂等记录及 CSV；定向 pytest 22 passed；隔离 FastAPI→Vue→Edge→CSV 实测无浏览器/请求错误 | 仅合成工程标签，未评价真实患者参考标注，不能作为模型准确率；本地 doctor 会话不验证外部研究授权或专业资质。无标签时为 `NOT_AVAILABLE`；评价证据保存在隔离上传 runtime，不新增数据库 schema |
| 13 | 分析任务状态与失败处理 | `/analysis`、病例详情分析历史 | `backend/app/services/analysis_jobs.py`、`backend/app/api/analysis.py` | **部分隔离验证**：RC 运行记录 `succeeded` 并可在服务重启后读取；历史 `test_analysis_state.py` 存在 | 重试/崩溃恢复的全路径未在本次 RC 执行；失败任务须检查日志再重试 |
| 14 | Prediction 与生存研究 | `/research#survival-models`（侧栏“IDH 与融合研究”） | `backend/app/api/survival_prediction.py`、`backend/app/services/survival_model.py`、`frontend/src/views/Research.vue` | **隔离 Edge/API E2E PASS**：现有 UPENN 临床、CaPTk 融合及 UCSF-PDGM Cox 模型列表；UCSF 固定工件通过真实 API 对纯合成输入返回相对风险、365/730/1095 天概率及曲线 | UCSF 队列只对 UCSF 模型适用，不能用于 UPENN 个体；仅内部验证。UPENN 正式 OS 仍 `BLOCKED_BY_DATA_DICTIONARY`，预测仅限 `SYNTHETIC_TEST` 且不持久化 |
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

### Latest official v1.2 survival status — 2026-10-26

This status supersedes earlier dated progress snapshots; those remain historical.

| Feature | Current status | Evidence / boundary |
|---|---|---|
| Official clinical CSV integrity and aggregate cohort reconstruction | `PASS` | 671 records; 630 people; 611 baseline; 60 follow-up; 41 paired; official-designated CSV SHA and IDC v25 comparison verified. |
| Exploratory KM | `EXPLORATORY_COMPLETE` | N=608 (585 candidate events/23 candidate censored) and sensitivity N=611 (585/26); both median 409 days (95% CI 376–443). |
| Cox | `EXPLORATORY_RESULT_REUSED_NOT_REFIT` | Complete-case N=570 (551 candidate events/19 censored); five-fold patient-level CV C-index ≈0.634. Prior result reused, not refit. |
| Formal OS endpoint | `BLOCKED_BY_DATA_DICTIONARY` | Censor semantics/time rules and exact updated event-time derivation remain unresolved. |
| One-year survival classification | `NOT_RUN` | Endpoint not validated. |
| Patient-level risk prediction | `NOT_GENERATED` | No patient-specific predictions. |
| Imaging-clinical fusion | `BLOCKED` | Authoritative patient crosswalk unavailable. |
| Overall research status | `EXPLORATORY_COMPLETE_WITH_ENDPOINT_LIMITATIONS` | Exploratory association only; no clinical or independent external validation claim. |

C-index is not classification accuracy. The age Schoenfeld result is a trend screen, not a formal PH test. No cases were removed to force a match to the paper’s 452-patient denominator. Evidence: `official-survival-audit-20261026-v1`.

### Survival prediction software prototype — 2026-10-26

- **Software implementation: PASS (research-only prototype).** `GET /api/survival/status`, `GET /api/survival/models`, and `POST /api/survival/predict` use a SHA-256 checked, versioned Cox artifact. Prediction accepts only the literal `SYNTHETIC_TEST` scope, requires the existing local doctor session, has no patient-ID field, and does not persist inputs or scores. Checked-in defaults keep the model path empty and prediction disabled unless an isolated runtime explicitly opts in.
- **Model fit: EXPLORATORY / researcher-defined endpoint.** One final full-candidate-cohort Cox artifact was fit from audited S1: N=608, 585 candidate events, 23 candidate censors; variables are age, gender, IDH1 and resection categories. The official endpoint remains `BLOCKED_BY_DATA_DICTIONARY`; this is not a formal OS or clinical model.
- **Internal validation: EXPLORATORY only.** Five patient-level stratified folds, seed 20261026, fold-local scaling; mean Harrell C-index 0.6462 (SD 0.0147). This is ranking discrimination on the provisional cohort, not classification accuracy, external validation or clinical utility. The prior C-index ≈0.634 is a separate historical result, not this model's score.
- **Synthetic probability calculation: software PASS; clinical probability status BLOCKED.** The artifact has a Breslow baseline hazard and computes the Cox survival function in days. Output is limited to explicit synthetic examples and observed event follow-up; it must not be interpreted for a patient.
- **Fusion model: EXPLORATORY_COMPLETE.** A separate artifact reuses the already audited 596-row CaPTk cohort and requires exactly `T1GD_ET_Intensity_Mean`, `FLAIR_ED_Intensity_Mean`, `T2_ED_Intensity_Mean`, and `T1_NC_Intensity_Mean`. The prior five-fold comparison is reused (clinical 0.6495, CaPTk-only 0.5273, combined 0.6510 mean C-index); CV was not rerun and showed no demonstrated gain. BrainFusion's 20 features are not mapped or accepted. RSF remains not implemented because compatible `sksurv` is unavailable.
- See [`SURVIVAL_PREDICTION_CLOSEOUT.md`](SURVIVAL_PREDICTION_CLOSEOUT.md) and [`SURVIVAL_PREDICTION_MODEL_CARD.md`](SURVIVAL_PREDICTION_MODEL_CARD.md). The model artifact is runtime-only and is not committed.
- **Real artifact-to-Vue integration: PASS (synthetic-only).** Opt-in Edge test `frontend/e2e/survival-live-artifact.spec.js` used both expected-hash runtime artifacts through a separately launched real FastAPI process, with a temporary SQLite and temporary local doctor account. Clinical and CaPTk requests rendered API-returned 1/2/3-year values and curves; invalid feature/category/time inputs were rejected; prediction table stayed empty. Evidence is in the versioned runtime `survival-live-artifact-e2e-20261026` run directory. Formal services and gates were not touched.

## Unified research demo and engineering freeze — 2026-10-26

- **Isolated launcher: PASS.** `scripts/start-unified-research-demo.ps1` copies the reviewed RC engineering database/uploads into `E:\BrainFusion-Runtime\research-edition\demo\unified-research-demo`, verifies SQLite and uploaded-file hashes, pins both existing survival artifacts by SHA-256, allocates non-production loopback ports, and uses existing Python/Node environments. The source RC assets remain unchanged; SegResNet weights are not enabled in the demo process.
- **Unified routes: PASS.** Microsoft Edge exercised home, case detail, workstation navigation, saved report/export availability, and Research against the live isolated backend with 0 page errors and 0 failed loopback requests. The existing analysis and report remained current and visible.
- **Survival model presentation: PASS (synthetic only).** The live real-artifact clinical and CaPTk API/Edge flow passed with local login/CSRF and API-returned curves. Predictions are not persisted. The UI states that synthetic predictions are independent of the selected engineering case and disables new radiomics extraction, clinical-input writes, and reference-label uploads in demo mode.
- **Data separation:** the isolated clone contains one engineering case and no saved `mri_features` rows; its feature panel remains empty instead of attaching other cases/tasks. Existing aggregate research summaries remain separately viewable. Evidence: `E:\BrainFusion-Runtime\research-edition\demo\unified-research-demo\logs\unified-demo-acceptance.json` and `demo-copy-manifest.json`.
- Formal OS remains `BLOCKED_BY_DATA_DICTIONARY`; exploratory models are not clinically validated. Existing public-reference single-case metrics are not independent external validation.
