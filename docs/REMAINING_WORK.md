# 剩余工作与放行条件

## Survival research V2 — current handoff, 2026-10-27

The dedicated worktree `E:\BrainFusion-Survival-V2` on `codex/survival-research-v2` completes the requested V2 model comparison, isolated API scope, and Vue/Edge integration. The older engineering snapshots below are historical and must not be read as describing this worktree's current V2 software state.

### Completed in V2

- Four UCSF-PDGM v5 clinical Cox candidates were compared fairly on the same baseline GBM cohort (N=367; 223 events/144 censored), same patient-level five-fold outer split and fold-local preprocessing. No candidate passed the predeclared stable improvement gate; retained the age+sex Ridge baseline.
- Version `2.0.0` full-cohort artifact and integrity manifest created under the protected research runtime; no model or patient-level output is in Git.
- Research page exposes model comparison/evaluation, exact input schema, curve/probabilities, and limitations. `RESEARCH_CASE` is available only if `SURVIVAL_RESEARCH_CASE_ENABLED=true` is explicitly set for an isolated process. It requires UCSF cohort declaration and researcher attestation; the API cannot independently verify membership. UPENN and other out-of-cohort use is prohibited. Checked-in defaults remain disabled.
- Targeted backend tests: 18 passed; frontend production build passed; opt-in live Edge + real artifact/API test passed for `SYNTHETIC_TEST` and `RESEARCH_CASE`; isolated prediction row count was zero.

### Remaining research limitations (not software TODOs)

- Internal single-center validation only; no independent external validation, clinical utility or patient-specific clinical prediction claim.
- The model's OS clock begins at initial diagnosis while age is measured at MRI; the diagnosis-to-MRI interval is unavailable and unmodeled.
- RSF remains `NOT_RUN` because compatible `sksurv` is unavailable. UCSF radiomics fusion remains `NOT_RUN` because no verified patient-level UCSF radiomics table/crosswalk is present. No dependency was installed and no UPENN model was mixed into this comparison.
- RESEARCH_CASE cohort membership is asserted by the researcher, not independently authenticated by the API; do not send UPENN records or unverified cohort inputs.
- Formal production deployment and all security gates remain unchanged. The frozen original worktree remains on its prior branch; V2 requires separate review/merge if desired.

Evidence and aggregate comparisons: `E:\BrainFusion-Runtime\research-edition\results\ucsf-pdgm-survival-v2-20261027`; final live run: `E:\BrainFusion-Runtime\research-edition\results\survival-v2-live-e2e-20261027\run-20261027T141518-6128e721`.

## Current engineering handoff — 2026-10-26

This handoff is the current integrated demo status and supersedes older dated engineering snapshots below; historical research conclusions remain valid unless this section explicitly updates them.

The isolated demo now provides a usable Stage7 Orthanc study browser, a reviewed-source isolated import action, a separate UPENN sub-002 segmentation result entry, and a UCSF-PDGM GBM Cox option in the existing Research page. The latest live E2E confirms real DICOM pixels, pinned existing UPENN result/overlay/metrics, and artifact-backed synthetic prediction. No follow-up software implementation is needed for these paths.

Remaining limits: the UCSF model has internal validation only and demo requests must remain `SYNTHETIC_TEST`; it is not a clinical prediction tool or valid for UPENN cases. The official UPENN survival endpoint remains blocked by its unresolved censor-field dictionary. No authoritative DICOM-to-NIfTI case association was made. The currently registered DICOM bundle has one MR series; conversion waits for same-study verified T1/T1GD/T2/FLAIR inputs and the reviewed space contract. The archive page does not submit inference. Formal PACS/AI gates remain unchanged.

Latest integration evidence: `E:\BrainFusion-Runtime\research-edition\demo\unified-research-demo\evidence\final-integration-e2e-20261026-run4.json`. It records 192/192 isolated source instances verified, 192 real HTTP 200 DICOM frame responses, existing sub-002 artifacts displayed without rerunning inference, and an API-backed UCSF synthetic curve. Demo services stopped after acceptance; formal ports and gates were unchanged.

## Latest blocker resolution — 2026-10-26

This current snapshot supersedes older statements below that the crosswalk was unavailable or no real-data exploratory model had been run. Those older sections remain as dated history.

### Completed in this pass

- **Scan-to-clinical crosswalk:** exact full scan key join against the pinned release manifest and official v1.2 clinical/availability assets, zero missing or duplicate IDs: 671 scans, 611 `_11`, 60 `_21`, 630 normalized people, 41 paired and 19 follow-up-only. The pinned mirror manual-mask object has a content-proven link to local `sub-002` reference mask under local-label `3→4` recoding (zero voxel differences). This does not link DICOM PatientID or assert MRI byte identity.
- **OS cohort reconciliation:** the current official `Overall Survival=available` flag marks exactly 452 baseline rows, all deceased with positive updated event time. This explains the flag count, not the historical paper's exact cohort-selection algorithm or the censoring rules. The published 668 count remains unreconstructed.
- **Exploratory fusion comparison:** complete four-feature cohort N=596 (574 candidate events, 22 candidate censors), 12 S1 records dropped for incomplete selected feature panel. Five-fold patient-level CV mean C-index (SD): clinical 0.649 (0.025), radiomics 0.527 (0.019), combined 0.651 (0.026). No demonstrated gain. Outcome is researcher-defined because censor field semantics remain unresolved; no individual risk estimates or external-validation claims.
- **Cox diagnostic fix:** corrected one averaged Schoenfeld residual being paired against repeated tied event times; targeted synthetic survival tests pass.

### Still blocked / next external evidence

1. `OFFICIAL_ENDPOINT_VALIDATED` requires written TCIA/UPENN dictionary or confirmation defining `Survival_from_surgery_days_UPDATED` transformation and `Survival_Censor` meaning, units, time origin and last-contact derivation, plus uncertain-death handling.
2. Reproducing the historical 452 cohort requires its row-level inclusion flow/list or full criteria mapped to the release. Reproducing BrainIAC N=668 requires its exact scan/person denominator rules.
3. Independent segmentation validation requires the checkpoint training-subject manifest. The present content-based reference bridge does not resolve training overlap.
4. A DICOM-specific link would require an authoritative release-to-DICOM identifier crosswalk; no number-based mapping is allowed.

Evidence and aggregate results: `E:\BrainFusion-Runtime\research-edition\results\final-blocker-resolution-20261026\`. Patient-level crosswalk remains local-only. Formal deployment, production DB and security gates were not touched; no SegResNet inference was rerun.

## 2026-10-26 final research blockers

This is the latest state; older dated sections below are retained as historical records.

Completed in the latest science pass:

- Public reference source and local label histogram were checked. A valid **WT-only** sub-002 agreement was calculated without integer relabeling; it was independently cross-checked against the existing backend metric function. Results and script are under `E:\BrainFusion-Runtime\research-edition\results\p0-p2-final-science-20261026\`.
- IDC v25 baseline/follow-up cohort structure, status, candidate event/censor availability and covariate missingness were audited without emitting patient identifiers. No KM/Cox was fitted.
- Existing geometry-fix production release evidence remains verified; this pass did not deploy or alter production.

Remaining external evidence needed:

1. **TC/ET and expert-reference classification:** obtain an official per-file integer label dictionary/conversion statement for the exact `sub-002_seg.nii.gz`, plus a subject-level indicator for whether sub-002 is among the 232 manually reviewed/refined masks. Do not infer class mapping from overlap with the model. Training-subject overlap information is separately needed before an independent-validation claim.
2. **Validated clinical OS:** obtain publisher/TCIA confirmation of `Survival_from_surgery_days_UPDATED` event-time unit/definition and `Survival_Censor` meaning, unit and start/last-contact rules; explain treatment of 3 uncertain-date deaths; obtain a cohort-flow reconciliation for paper N=452 vs the updated candidate N=608. The official v1.2 attachment timed out on one bounded download attempt and was not saved. Until definitions are validated, keep KM/Cox `NOT_RUN` and candidate records `PROVISIONAL`.
3. **Imaging-clinical fusion:** acquire an authoritative sub-002↔DICOM PatientID mapping; no ordinal join. This does not block a future clinical-only model once OS endpoint conditions and analysis approval are met.

Potential preregistered sensitivity scenarios after endpoint verification: primary confirmed status/time mapping; exclude uncertain-death cases; and, only if the source defines last-contact censor time, include the three uncertain cases censored at that time. Freeze age/sex/IDH/resection as a sparse clinical baseline; MGMT/KPS require missing-data planning (only 53 candidate complete cases when both are required).

更新：2026-10-25（授权后收尾）。以下表格中的早期“等待批准”描述保留作历史记录；最新状态以本节为准。

## 当前剩余事项

- **已完成：正式发布**：获批 Runbook 的 `bf-rc-20261022.1-geometry-fix` 已部署并通过健康、目标镜像、DB/病例、197 个运行文件、几何 API 及 68 项定向 pytest 验收。安全门控关闭，回滚资产保留。证据：`E:\BrainFusion-Runtime\research-edition\evidence\release-geometry-fix-20261025.json`。
- **已完成：一次 sub-002 隔离推理**：官方共配准 NIfTI 上完成真实 CUDA SegResNet 探索运行，掩膜/体积/叠加图/哈希已保存。推理配置 ROI 有 GPU 资源约束差异；不得视为官方配置复现或临床验证。
- **BLOCKED：真实分割指标**：需要核实 sub-002 参考标签的准确数值语义、逐例标注来源/人工复核状态，并确认 checkpoint 与目标病例的训练重叠。当前不计算 Dice、HD95 等指标。
- **BLOCKED_BY_DATA_DICTIONARY：真实生存分析**：IDC v25 的 608 条候选 OS 与论文报告的 452 人 OS 队列未能由已取得来源逐列解释；时间起点、事件/删失时长定义也没有权威映射。需要 TCIA 原始 clinical v1.2 CSV/数据字典或发布方确认，并建立可靠影像-临床 crosswalk。未完成前不拟合真实 KM/Cox。
- **受本机执行策略阻断：影像组学新任务 Edge 重放**：该任务的 SQL、API、重启持久化和 CSV 核验 PASS；启动隔离后台监听被策略拒绝，未尝试绕过。若要求同一任务浏览器展示，需在允许的启动方式下单独完成。
- **可选 NOT_IMPLEMENTED：RSF**：环境没有 `sksurv`，不安装或替换主环境依赖。

历史实现和软件验收状态见下表；表中状态不覆盖以上当前快照。

| 状态 | 事项 | 具体未完成内容 | 下一步/限制 |
|---|---|---|---|
| 等待人工审核 | UPENN 模型输入候选 | 序列角色、三平面局部解剖、本人关注异常区域和 T2w 红色缺失视野影响；确认是否接受 1 mm/线性插值的隔离工程用途 | 在既有未签署清单实际勾选、签名、注明日期；清单批准隔离推理后才可运行。无肿瘤 ROI 时不声称已验证肿瘤附近覆盖 |
| 等待正式发布批准 | 几何修复版 `bf-rc-20261022.1-geometry-fix` | 镜像、Compose、正式库备份及克隆启动验收已准备；正式服务仍使用冻结版 | 只需批准现有 Runbook 中的一次正式 backend/frontend 替换；不重复请求批准已完成的预检；批准前不执行 |
| BLOCKED_BY_DATA | 生存分析与个体预测 | 192 条 OS 记录的起点混合；统一可验证时间零点样本数为 0。PFS 有效时间/状态 72 条（24 事件），其余记录时间缺失或状态不完整 | 保留既有审计报告；先确认数据研究用途、诊断/切除起点、末次随访、事件/删失规则。条件统一前不对真实数据运行 KM/Cox/RSF，不产生启发式生存月份 |
| BLOCKED_BY_DATA / LABELS | 模型性能研究 | 分割评价 API/UI 已完成合成工程验收；没有可用于本轮的真实人工参考标签，未计算真实患者 Dice/HD95 | 若开展论文实验，需另定方案、患者级拆分、合规参考标注、资源计量和预注册指标；不从工程验收推断模型准确度 |
| 软件通过、研究数据阻断 | 生存数据管理与分析 API/UI | `/research/survival/status`, `/validate`, `/kaplan-meier`, `/cox` 已接入；Research 页面真实读取并显示 `BLOCKED_BY_DATA`；合成 KM/Cox API、校验拒绝与前端构建通过 | WAW 的共同时间零点及数据用途未核实；不读患者级行、不拟合真实队列、不提供个体预测。`sksurv` 未安装，RSF 不可用 |
| 新任务持久化/API/重启/CSV 通过；同任务 Edge 待执行策略允许的启动方式 | 影像组学 SQL/API/浏览器/CSV | 2026-10-25 新隔离任务在隔离 SQLite 中成功提取并保存20项特征；幂等重试返回同一任务；第二个 FastAPI 进程读取持久化结果；20 行 CSV 与 SQL/API 的值和指纹一致。另有 2026-10-22 Microsoft Edge live API/CSV E2E 证据，但使用既有任务 | 2026-10-25 后台启动监听服务被本机执行策略拒绝，本轮未用其他方式规避，因此没有把新任务再跑一遍 Edge。任务实现及 API 已验证；若需证明同一新任务贯通 Edge，需在允许的本机服务启动方式下重做该单项。证据：`E:\BrainFusion-Runtime\research-edition\evidence\radiomics-live-20261025`；正式数据库和服务未改 |
| 软件通过；真实研究评价需标签 | 参考掩膜分割评价 | 上传式、来源受限的 API/UI、物理空间验证、幂等持久化和 CSV 已实现；22 项定向测试通过；隔离 Edge E2E 使用合成样本完成 | 当前没有真实授权的参考标签评价记录；空状态为 `NOT_AVAILABLE`。真实指标研究需确认标注来源、研究许可与评价方案；本地登录不代替该确认 |

## 研究方案与软件完成边界

- 数据准入、患者级隔离、泄漏控制、指标报告与复现记录的研究准备见 [`EXPERIMENT_PROTOCOL.md`](EXPERIMENT_PROTOCOL.md) 的 2026-10-22 补充。
- 已完成的软件演示包括现有合格工程样本 SegResNet 闭环、影像组学隔离 SQL/API/重启/CSV 新任务验证及先前 Edge live API/CSV E2E，以及合成样本上的生存软件 API。新任务本轮未重做 Edge；合成结果和单样本工程输出不构成研究性能结论。
- 参考掩膜评价 API/UI 的软件链路已完成合成工程验收；当前没有真实参考标签评价。RSF 因缺少兼容 `sksurv` 依赖不可用；也没有真实合格生存建模。研究代码任务不能把这些状态标为科研结果已完成。

## 当前交付结论

- 科研工程演示：具备条件。既有冻结系统的病例、四序列 NIfTI、SegResNet 工程样本、掩膜、WT/TC/ET、持久化报告，以及隔离真实 DICOM/PACS 阅片均有验收证据。
- 正式运行：当前冻结版保持健康；geometry-fix 版仅完成构建、克隆验证及只读预检，尚未替换正式服务。
- 临床/医学输入认可：未完成。UPENN 清单仍未签署且没有 UPENN SegResNet 推理结果。
- 生存研究：`BLOCKED_BY_DATA_DICTIONARY`。IDC v25 汇总已重新计算，但原 TCIA 表格精确字段语义及可靠图像-临床患者 crosswalk 尚未找到。

## 研究增强版分割评价收尾

- 软件功能：参考 NIfTI 上传、当前分析掩膜来源与空间检查、WT/TC/ET 指标、CSV、无参考标注 `NOT_AVAILABLE` 状态通过定向测试和隔离 Edge 实测。
- 数据结论：本次仅使用合成影像、合成标签、隔离 SQLite、独立端口和本地测试账户；没有访问正式数据库、病例 17/19、UPENN 数据，也没有运行 SegResNet。不得把合成指标用于模型准确率或论文性能结论。
- 证据目录：`E:\BrainFusion-Runtime\research-edition\evidence\segmentation-evaluation-live-20261022`（浏览器 JSON、截图及 CSV 均为合成工程材料）。
- 后续仅剩真实标注的来源/许可与研究方案确认、独立正式发布批准、UPENN 输入审核、生存队列数据条件；无需继续扩展分割评价软件。


## Latest final science state — 2026-10-26

Completed: one-case sub-002 `PUBLIC_REFERENCE_AGREEMENT` evaluation for WT/TC/ET; exact 3↔4 reference recoding proved by 0-mismatch voxel cross-tab; versioned PNG/CSV/JSON and SHA256 manifest. Completed: privacy-preserving audit of current UPENN OS mirror vs IDC v25 and explicitly exploratory baseline-only KM/Cox sensitivity analysis; synthetic survival software checks 4/4. Full details: `E:\BrainFusion-Runtime\research-edition\results\p0-p2-final-science-20261026-v2\FINAL-RESEARCH-CLOSEOUT.md`.

Remaining blockers: (1) authoritative field-level definition of `Survival_Censor` (meaning, unit, origin and last-follow-up derivation), uncertain-death handling, and exact reconciliation of published OS denominators 452 vs current candidate 608 / published BrainIAC 668; (2) checkpoint training-subject manifest to assess overlap before independent segmentation validation; (3) authorized image-to-clinical crosswalk before fusion. Until item 1 is resolved, formal KM/Cox and one-year survival evaluation remain blocked; current results are exploratory only.

## Official v1.2 survival follow-up — 2026-10-26

The official-designated CSV is now locally available and matches the pinned mirror byte-for-byte (SHA-256 `fd5749ae5a8d77e599e02264d961d94107752f0244e34bf0bc711a75fe0e2ec5`); its 671 scan rows and 11 comparable fields match IDC v25. This resolves the source-content comparison, not the data dictionary. The endpoint remains `BLOCKED_BY_DATA_DICTIONARY`: no authoritative definition was found for `Survival_Censor` unit/origin/last-contact rule, exact updated-time derivation, or the three uncertain deaths; published 452 vs 608/668 denominators remain unreconciled.

Exploratory KM sensitivity was completed on baseline-only candidates: N=608 (585/23 event/censor) and N=611 (585/26 when uncertain-death records are provisionally censored), both median 409 days (95% CI 376–443). The prior Cox fit on byte-identical input is retained as exploratory, not refit. One-year prediction remains NOT_RUN. Obtain written TCIA/UPENN field clarification and inclusion criteria before formal survival analysis. Evidence: `official-survival-audit-20261026-v1`.

## Latest survival status and sole endpoint blocker — 2026-10-26

This current summary supersedes older dated progress snapshots; historical entries are retained as records of prior state.

- Official CSV integrity/cohort reconstruction: `PASS`.
- Exploratory KM: `EXPLORATORY_COMPLETE`, N=608 (585 candidate events/23 candidate censored) and N=611 sensitivity (585/26), median 409 days for both (95% CI 376–443).
- Cox: `EXPLORATORY_RESULT_REUSED_NOT_REFIT`, complete-case N=570, 551 candidate events/19 censored, five-fold patient-level CV C-index ≈0.634. No refit; age PH diagnostic is a trend screen only.
- Formal OS endpoint: `BLOCKED_BY_DATA_DICTIONARY`; obtain authoritative definitions for `Survival_Censor` meaning/unit/origin/last-contact derivation, the updated event-time rule and uncertain-death handling. Historical 452 vs current candidate 608 vs BrainIAC 668 denominator reconciliation is unresolved; do not force a 452 match.
- One-year classification: `NOT_RUN`; patient-level risk prediction: `NOT_GENERATED`; imaging-clinical fusion: `BLOCKED` until an authoritative patient crosswalk exists.
- Overall: `EXPLORATORY_COMPLETE_WITH_ENDPOINT_LIMITATIONS`. No external-validation or clinical-utility claim.

## Survival prediction prototype — 2026-10-26

The software prototype, clinical Cox fit, and final clinical+CaPTk Cox fit are complete; earlier statements that no cohort fit existed describe an earlier audit snapshot and remain historical. The clinical fit uses audited S1 (N=608; 585 candidate events/23 candidate censors), with age, gender, IDH1 and resection. The fusion fit reuses the existing feature-complete cohort N=596 (574/22) and exactly four official CaPTk features; prior CV is reused rather than rerun. Its prior mean fold C-index was clinical 0.6495, CaPTk-only 0.5273, combined 0.6510, so no fusion gain was demonstrated. Both runtime-only artifacts are exploratory and do not validate the endpoint.

Still blocked: authoritative `Survival_Censor` meaning/unit/origin/derivation, exact updated event-time definition, and uncertain-death handling. Formal OS interpretation remains `BLOCKED_BY_DATA_DICTIONARY`. A CaPTk fusion software/model exists, but it is exploratory, showed no demonstrated gain, and is not a BrainFusion-feature model. One-year classification is `NOT_RUN`; no real-patient predictions were generated. RSF is `NOT_IMPLEMENTED` because compatible `sksurv` is unavailable. Prediction API/UI are opt-in and synthetic-only; checked-in defaults are disabled.

See [`SURVIVAL_PREDICTION_CLOSEOUT.md`](SURVIVAL_PREDICTION_CLOSEOUT.md) and the runtime-only model package. No production deployment/configuration changes are part of this implementation.

## Engineering demo closeout — 2026-10-26

The software integration closeout is complete. Start the isolated demo with `scripts/start-unified-research-demo.ps1`; use the printed frontend URL and one-run local password, then stop with Ctrl+C. The launcher retains its runtime copy and logs, does not install packages, and never targets formal ports. See [`DEMO_GUIDE.md`](DEMO_GUIDE.md) and [`FINAL_ENGINEERING_CLOSEOUT.md`](FINAL_ENGINEERING_CLOSEOUT.md).

Remaining work is scientific or approval-bound: authoritative OS censoring/time-field definitions, independent external validation and clinical authorization, and any use of this model outside explicit synthetic demonstration. No further non-LLM/RAG software blocker was found in this integration pass. The unified demo clone contains no saved feature rows for its one engineering case, so radiomics extraction remains disabled there rather than manufacturing a result.
