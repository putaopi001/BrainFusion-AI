# BrainFusion-AI 空间与恢复清单（2026-10-21）

只覆盖项目明确关联的路径、容器和挂载；未扫描无关个人文件，也未读取医学影像体素做重复分析。历史/未知内容默认保留。

## 位置与使用状态

| 分类 | 路径/对象 | 本次核对 |
|---|---|---|
| ACTIVE | `E:\BrainFusion-AI` | 唯一主源码；本轮冻结为 tag `bf-rc-20261021.1-frozen`（精确 commit/hash 在 E 盘 closeout 恢复包清单记录） |
| ACTIVE | RC 容器 `brainfusion-rc-20261021-backend/frontend` | Healthy；`127.0.0.1:18104/18184`；分别使用隔离镜像和 RC runtime |
| ACTIVE | `E:\BrainFusion-Runtime\release-candidate\brainfusion-rc-20261021` | RC runtime、私有配置、空 dataset/research/PACS-derived 占位目录；数据库 237,568 bytes；演示病例文件和分割输出约 26 MB 量级 |
| ACTIVE | `E:\BrainFusion-Runtime\stage7_orthanc_20261021` 与容器 `brainfusion-stage7-orthanc` | Orthanc 运行于 18142，config 只读；独立命名卷 `brainfusion-stage7-orthanc-data`，测试档案为空。无凭据访问 `/system` 为 401 |
| ACTIVE | 模型只读挂载 `E:\BrainFusion-Runtime\results\nightly\2026-10-10\20261010T000643_ec1cf8da\relocated-runtime\model` | RC/旧正式 Compose 都引用；`model.pt` 18,840,620 bytes，SHA-256 `860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae` |
| ACTIVE / REQUIRED | 正式容器原挂载 `E:\BrainFusion-Runtime\results\nightly\2026-10-20\20261020T1815_real_nifti_compose_demo_fixed\runtime` | 正式 backend/frontend 当前 Exited；原数据库和数据路径未读写；保留以支持回滚 |
| REQUIRED | `E:\BrainFusion-Runtime\local` | 本地 PACS 配置、账户和任务配置；可能含秘密，不应公开或搬移 |
| REQUIRED | `E:\BrainFusion-Data\WAW-GliomAI-v3` | 许可工程样本来源；本次只复用已存在的四个 NIfTI 到隔离 RC，未重新下载数据集 |
| REQUIRED | `E:\BrainFusion-AI\data\external\UPENN-GBM` | 636 个实例既有数据与元数据；尚待人工隐私/序列/配准复核；未导入 Stage 7 Orthanc |
| REQUIRED / UNKNOWN | `E:\BrainFusion-AI\.conda\brainfusion` 与 `E:\.conda\envs\brainfusion` | 两个环境目录都存在，工具和依赖不同；本轮未安装、移动或删除，不能按重复目录处理 |
| BACKUP | `E:\BrainFusion-Runtime\backups\closeout-20261021T194500` | C/E 状态快照、最终当前差异快照、RC SQLite 在线备份、RC uploads/config、RC Compose/版本说明及 SHA-256 清单；约 40.4 MB 数据文件，另有索引清单 |
| BACKUP | `C:\Users\mechrevo\AppData\Local\Temp\brainfusion-rc-source-snapshots-20261021-192342` | 原始 E/C 源码快照保留于 C；完整副本也在 E 盘备份目录，未删除 C 原件 |
| UNKNOWN / REQUIRED | `C:\Users\mechrevo\.codex\worktrees\1924\BrainFusion-AI` | 与 E 同 HEAD 但有 20 个变更路径（含 10 个未跟踪项）和独有 DICOM/PACS/task 实现；已快照，不是可直接删除的冗余目录 |
| UNKNOWN / REQUIRED | `C:\Users\mechrevo\.codex\worktrees\b4ad\BrainFusion-AI` | 与 E 同 HEAD、detached；11 个未跟踪文件共 57,885 bytes，其中 7 份文档与 E 不同；已将 11 个文件逐项哈希快照到本恢复包，不是可直接删除的冗余目录 |
| UNKNOWN / BACKUP | `E:\BrainFusion-Runtime\results\nightly` | 存有 12 个历史日期目录。Oct 10 模型和 Oct 20 正式 runtime 确有活动 Compose 引用；其他 nightly 未逐一清理，全部保留 |

## 容量、内容数量与边界

- C 原始快照约 70,195 bytes（13 文件）；E 原始快照约 4,546,070 bytes（428 文件），不含 DICOM、模型、数据库和运行日志。
- 当前恢复包约 42.7 MB；包含 RC runtime uploads 及 SQLite 一致性备份、三个工作区快照、冻结源码 bundle 与源文件清单、关键 Compose/config。完整逐文件大小与 SHA-256 在 `sha256-manifest.json`。
- RC 数据库在线备份 `PRAGMA integrity_check` 返回 `ok`。E/C tracked patch 均通过只读反向适用检查；最终快照 E 434、C 10 个未跟踪源码文件均经哈希核对。恢复包不会覆盖原工作区。
- 冻结前 E/C(1924)/C(b4ad) 均以 `d1bc7a0` 为基线。E 主源码现由冻结 tag 唯一标识；C(1924) 20 条变更和 C(b4ad) 11 个未跟踪文件在原目录及恢复包保留，不覆盖、不丢弃。
- E 项目内 `.conda`、C worktree、Docker 镜像层和大型医学影像树未做全量递归体积统计，避免对大数据和环境做无关深扫；未知容量不构成删除依据。

## 重复与清理候选

| 分类 | 对象 | 证据 | 处理 |
|---|---|---|---|
| DUPLICATE（文件内容） | `E:\BrainFusion-Runtime\models\monai-brats\models\model.pt` 与 RC/正式 Compose 使用的 nightly 模型文件 | 两者均 18,840,620 bytes，SHA-256 完全相同 | 暂不删除：默认配置/操作手册引用 runtime/models 路径，Compose 仍引用 nightly 路径。待路径统一、引用切换演练并经用户批准后，理论可释放 18,840,620 bytes |
| REBUILDABLE | `backend\v` 的 pytest `nodeids` 缓存（约 2 bytes） | 纯测试索引缓存 | 本轮未删；释放空间可忽略 |
| UNKNOWN / 需批准 | C Codex worktree、两个 Conda 环境、历史 nightly、Docker 镜像/卷、DICOM 和数据库 | 有独有修改、运行引用或唯一数据；部分还未逐项确认用途 | 仅列候选，不执行删除。不得使用 `git clean`、Docker prune 或递归清理 |
| 精确重复文件（候选） | `C:\Users\mechrevo\.codex\worktrees\b4ad\BrainFusion-AI\backend\tools\download_waw_gliomai_sample.py`；`C:\Users\mechrevo\.codex\worktrees\b4ad\BrainFusion-AI\backend\tools\verify_waw_gliomai_sample.py`；`C:\Users\mechrevo\.codex\worktrees\b4ad\BrainFusion-AI\docs\DATASET_SAMPLE.md`；`C:\Users\mechrevo\.codex\worktrees\b4ad\BrainFusion-AI\docs\EXECUTION_PLAN.md` | 与 E 主源码相对路径文件 SHA-256 相同；同一 worktree 另外 7 份文档不同 | 仅报告，未经用户批准不删；清理前仍需确认该 worktree 后续不使用这些独立副本 |
| 历史快照（候选） | `C:\Users\mechrevo\AppData\Local\Temp\brainfusion-rc-source-snapshots-20261021-192342` | E 盘恢复包保留完整副本；C 原始副本不动 | 仅报告，待逐文件验证后由用户批准；恢复包继续保留 |

**本轮实际清理：0 bytes。** 当前没有已确认既无引用又无需保留的历史项目目录。可评估的具体项见上表；模型副本仍有活动引用，不属于当前可安全删除项。正式数据库、Orthanc 卷、模型权重、影像数据、两个 C worktree 和恢复快照全部保留。

