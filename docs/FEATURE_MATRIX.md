# BrainFusion-AI 功能矩阵

更新：2026-10-22（最终收尾）。状态含义：**已完成并验收**＝现有冻结/隔离路径有实测证据；**已实现未发布**＝修复版已构建/克隆验收，正式环境仍运行冻结版；**等待人工批准**＝需本人签署模型输入审核或批准正式发布；**BLOCKED_BY_DATA**＝数据口径/许可不足，不能开展研究建模；其他状态保持原定义。

## 最终交付分类

- **已完成并通过验收**：隔离 DICOM 导入/QIDO/WADO/Cornerstone 真实像素阅片；合格 WAW 工程样本 SegResNet、掩膜、WT/TC/ET、报告持久化及前端流程；现有冻结版正式服务健康。
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
| 9 | 四序列配准与标准化 | 后端审核/准备流程 | `backend/app/services/dicom_resampling.py`、`backend/app/services/dicom_input_plan.py`、`backend/app/services/study_validation.py` | **已实现未发布 / 等待人工批准**：geometry-fix 版修复了 FLAIR/T2 spacing 误判；UPENN T1c/T2w 三平面叠加、棋盘格、局部视野图已生成；候选网格和变换复算通过 | T2w 目标网格源覆盖 80.79%；红色为源视野外。疑似肿瘤邻近覆盖无法由现有代理证明；输入清单仍未签署，UPENN 推理未执行 |
| 10 | MONAI SegResNet 分割 | 病例分析入口/API | `backend/app/ai/imaging/monai_segmenter.py`、`backend/app/api/analysis.py` | **隔离真实推理通过**：RC Docker 对已许可 WAW-GliomAI 工程样本执行 MONAI BraTS SegResNet，无 fallback | 单个工程样本不代表临床精度；UPENN 未推理 |
| 11 | 掩膜可视化 | NIfTI 工作站“显示/隐藏分割” | `frontend/src/components/mri/CornerstoneViewer.vue`、`backend/app/api/mri.py` | **隔离实测**：工作站提供三正交 canvas；真实输出掩膜开关可用 | 结果须人工核对；演示标识不是临床审核签署 |
| 12 | WT/TC/ET 体积与分割评价 | 病例报告与结果区；工程评价 helper | `backend/app/services/segmentation_metrics.py`、`backend/app/api/analysis.py` | **体积隔离实测**：报告显示 WT 6.284、TC 3.374、ET 0.008 mL；Dice/HD95 已有实现，本轮补充 TP/FP/FN、precision/recall，并在容器内用合成掩膜通过边界 smoke check | 评价仅在提供人工参考掩膜时可用；本轮未计算真实样本准确率或任何临床性能指标 |
| 13 | 分析任务状态与失败处理 | `/analysis`、病例详情分析历史 | `backend/app/services/analysis_jobs.py`、`backend/app/api/analysis.py` | **部分隔离验证**：RC 运行记录 `succeeded` 并可在服务重启后读取；历史 `test_analysis_state.py` 存在 | 重试/崩溃恢复的全路径未在本次 RC 执行；失败任务须检查日志再重试 |
| 14 | Prediction 与生存研究 | `/analysis`、`/research`、病例详情 | `backend/app/api/predict.py`、`backend/app/api/predictions.py`、`backend/app/api/cases.py`、`backend/app/research/survival.py` | **真实研究 BLOCKED_BY_DATA**：无可用生存模型，个体预测 API 返回 503；现有 WAW 快照为工程 smoke test 且 OS 时间零点混合。终点契约、KM、Cox PH 拟合、C-index 与 Schoenfeld 残差趋势筛查仅在合成记录上执行 | 没有患者级拟合；Schoenfeld 趋势仅为未校正筛查，不是正式比例风险检验。RSF 依赖 `sksurv` 当前未安装。数据许可和逐例起点获核验前保持阻断，不输出个体预测 |
| 15 | 影像组学及研究分析 | `/research` | `backend/app/api/research.py`、`backend/app/services/feature_jobs.py`、`backend/tools/extract_selected_radiomics.py`、`frontend/src/views/Research.vue` | **工程样本真实提取 PASS；研究分支已实现、未发布**：已有 5 个隔离工程样本成功任务，每次 20 项 PyRadiomics 特征、带输入/掩膜哈希；SQL 幂等写入有合成 fixture 覆盖；Microsoft Edge 定向浏览器测试显示已保存特征并触发 CSV 下载（API 由测试夹具模拟） | 历史工程样本未回填；尚未在新隔离研究 DB 对真实结果执行 SQL 持久化/重启读取，也未做浏览器到真实 CSV API 的 live 联调。无正式 schema 变化 |
| 16 | 结构化报告 | `/report?case_id=1` | `backend/app/api/reports.py`、`backend/app/services/current_report.py`、`frontend/src/views/Report.vue` | **隔离实测**：Edge 展示该次分析的模型、体积、限制和来源追溯 | 医生复核显示“待复核”；报告不是临床诊断 |
| 17 | 结果与报告版本关联 | 报告页及病例分析历史 | `backend/app/models/analysis_run.py`、`backend/app/models/report.py`、`backend/app/services/artifact_integrity.py` | **隔离实测**：analysis run 与 report 同 ID 关联；后端重启后结果/掩膜/报告仍存在 | 当前新 RC 只演示一个分析版本；多版本比较场景未在本次彩排 |
| 18 | 用户身份、角色与审核权限 | 本地登录/复核界面 | `backend/app/api/local_auth.py`、`backend/app/services/local_auth.py`、`backend/app/core/dependencies.py` | **隔离代码与既有定向测试**：本地身份接口和权限门控存在；本次只通过 PACS/private-runtime 7 项测试 | 当前 RC 账户不可用性/角色全路径未彩排；账户验证不代表执业资质 |
| 19 | 前后端部署 | 正式/隔离 Docker Compose | `docker-compose.rc.yml`、正式审批包、`backend/Dockerfile`、`frontend/Dockerfile` | **正式冻结版已完成并验收**：当前正式 18100/18180 healthy；geometry-fix 两镜像在克隆正式库环境 18108/18188 均健康并已停止 | **修复版已实现未发布**：最终预检 GO；只有一次正式前后端替换审批尚待完成；PACS/像素/AI bridge 门控保持关闭 |
| 20 | 数据备份与恢复 | `E:\BrainFusion-Runtime\backups` | SQLite 官方在线备份；部署验收记录 | **已完成并验收**：geometry-fix 最终预检备份 `geometry-fix-preflight-20261022T20261022T122945` integrity/FK 通过；克隆 schema/状态/记录未变；197/197 运行文件哈希匹配 | 备份为回滚基线，不得覆盖；部署后 DB 恢复须另行批准 |
| 21 | 日志与错误处理 | Docker logs、PACS 状态与 API 错误 | `backend/app/core/logging.py`、`backend/app/services/worker_error.py` | **部分实测**：容器健康检查与 API fail-closed 状态可读；浏览器彩排无失败请求 | 未对所有故障注入；日志可能含敏感元数据，不应直接外传 |
| 22 | LLM 报告、RAG、多模态 MRI | 暂无产品入口 | 暂无本 RC 服务实现 | **本轮不实现；仅未来规划** | 后续需独立方案、数据授权、评测和安全边界；不能宣传为当前功能 |

## 当前 RC 复核记录

- RC 地址：`http://127.0.0.1:18184`；API `http://127.0.0.1:18104`。
- 演示病例：病例 1，`RC-Engineering-Smoke`。输入为已有四序列 WAW-GliomAI 工程样本，不是 UPENN。
- SegResNet 真推理、掩膜、体积、报告关联和重启后持久化：见 [`RELEASE_CANDIDATE_20261021.md`](RELEASE_CANDIDATE_20261021.md)。
- WAW 工程样本 Edge 彩排：四序列 NIfTI、三画布、真实分析掩膜和报告可见；这与 UPENN DICOM 浏览验收是两条不同数据路径。
- 本轮核心定向回归 196 passed、4 个既有 deprecation warnings；证据见 `E:\BrainFusion-Runtime\results\dicom-pacs-acceptance-20261021\evidence\core-pytest-20261022.xml`。前端生产构建通过；依赖 externalization/大 chunk 为构建警告。
- UPENN 浏览证据：`E:\BrainFusion-Runtime\results\dicom-pacs-acceptance-20261021\evidence\upenn-cornerstone-browser-fix.json`。模型输入审核未签字，因此无 UPENN SegResNet 结果。
