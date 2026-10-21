# E5 Docker/Linux 运行时验收进展（2026-10-20）

## 当前状态（2026-10-20，最新实机核对）

Docker Desktop 4.95.0 / Engine 29.8.2 正常；本机隔离 NIfTI 演示的前后端容器当前均 healthy，仅绑定 127.0.0.1:18180 与 127.0.0.1:18100，实际进程状态已在本轮复核。E5 的限定工程范围已通过：Linux full/core 镜像、API/前端健康、Orthanc 身份与 QIDO 元数据、五个只读挂载拒写、Linux 特征 worker 参考样本，以及最终镜像容器重建后的数据库/上传/作业持久化均有记录。详细验收见本文件后文 10 月 20 日更新与 E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T132214_linux-radiomics-e5/。

当前运行中的可见演示只用病例17的隔离 NIfTI 副本，操作说明见 COMPOSE_NIFTI_DEMO_GUIDE_20261020.md。它不代表真实四序列 DICOM 页面/AI闭环、干净机器安装、临床用途或模型效能验收。候选四序列尚未通过人工烧录文字/角色复核与许可确认，仍保持隔离。前端锁文件后续修复已使 npm audit 为0、npm ls --all 与生产构建通过，Edge E2E 为8通过/1跳过，见 NIFTI_DEMO_AND_FRONTEND_SECURITY_20261020.md；下方初始依赖安全段是修复前快照。

下方“尚未完成的 E5 门槛/下一步”属于早期实施计划，已由本节及后续 10 月 20 日验收记录覆盖；保留作过程历史，不作为当前任务清单。

## 初次静态与临时容器检查（历史快照，已由后文正式 Compose 验收覆盖）


- Docker Desktop 4.95.0 / Engine 29.8.2，desktop-linux，linux/amd64。hello-world 容器成功运行。
- 后端 INSTALL_PROFILE=full 镜像构建成功，使用固定 Python 基础镜像摘要；44 项哈希锁依赖在 Linux CPython 3.10 中安装成功，含 CPU PyTorch 2.11.0、MONAI 1.5.2、SciPy 1.15.3、SimpleITK 2.5.6。镜像 brainfusion-backend:e5-validation，digest sha256:b897b4782302bebfd88b6336963aaa42521133f42b727648a36dcd31f2e463d6，约 2.11 GB。
- 后端容器导入检查通过；FastAPI 临时容器在仅容器内 tmpfs 数据目录启动成功，/ 返回 healthy，OpenAPI 生成 68 个路径。未挂载病例、模型、数据库或本机运行目录。
- 前端 production 构建和 Nginx 配置检查通过。已在当前 semver 范围内更新 21 个锁定版本，package.json 未变；Vue/Axios 等可修复项更新后，锁定依赖重新构建成功。镜像 brainfusion-frontend:e5-validation-secfix，digest sha256:700ecdbdd765a4759928469df74e098f490cfb4179bf63abd222a5813ab2b800，约 117 MB。
- 前端临时容器 HTTP 200 并返回应用入口；API、OpenAPI 和 Nginx 静态服务均通过隔离冒烟。检查后已停止临时容器；当前没有运行中的项目容器。
- Dockerfile 的轻量 `core` 目标也单独构建通过：Python 3.10 / FastAPI 正常导入，镜像约 945 MB，未包含 PyRadiomics worker。构建时修复了 core 哈希锁里缺失的 `exceptiongroup` 和 `importlib_resources` 传递依赖；Compose 的 `full` 目标继续包含隔离 worker。
- 首次构建遇到 Docker Hub 授权端点连接超时。将固定摘要基础镜像逐个拉取后，构建通过；这属于本机到仓库授权端点的间歇网络问题，不是镜像配方失败。

## 依赖安全状态（修复前历史快照）

锁文件更新前 npm audit 报 21 项（1 critical、13 high、6 moderate、1 low）；critical 项来自开发工具链 npm-run-all2 → shell-quote，不进入最终 Nginx runtime image。候选更新只改了 package-lock.json 中 21 个版本，未升级主版本，前端 production build 与 Docker build 均成功。更新后 audit 剩 11 项（6 high、5 moderate），集中于 Cornerstone/DICOM 传递链 dcmjs → adm-zip、@kitware/vtk.js → fflate、uuid；npm audit fix 报告这些项无兼容自动修复。是否通过 overrides 或升级 Cornerstone 解决，仍需单独兼容性评估和阅片回归，不应强行 --force。

构建仍显示 Vite 部分 JavaScript chunk 超过 500 kB、Cornerstone codec 的 fs/path/url browser externalization 提示，以及 core-js 安装脚本提示；它们没有阻止构建，但需结合真实浏览器 DICOM/NIfTI阅片继续检查。安全扫描和构建通过不等于完成医学影像功能验收。
### 历史快照：16:37 锁文件 production-only 安全审计（已由后续修复结果覆盖）

当前 package-lock 的 production-only 查询仍为 11 项告警（6 high、5 moderate、0 critical），与完整树数量相同；npm audit 未给出兼容自动修复。唯一可建议的 @cornerstonejs/tools 路径是降级到 0.27.2（跨主版本），未实施。证据、锁文件 SHA 和完整告警列表见 E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T1637_frontend_security_audit/summary.json。已保留已验收依赖组合，待单独做版本兼容与阅片回归后再决定升级；该审计不证明存在可利用漏洞，也不证明不可利用。

## 历史快照：尚未完成的 E5 门槛（已由后文 10 月 20 日验收覆盖）

- Docker Compose 已用 E 盘已有目录启动过前后端：后端健康检查通过，前端 HTTP 200，OpenAPI 68 路径可访问；Compose 内实际运行兼容性门槛检查并用挂载的公开病例完成一次 Linux worker 特征提取。数据库写入指向新建的临时 runtime 目录，模型、研究包、数据集、PACS 派生资料和配置按 Compose 声明只读挂载。测试后 Compose 容器和网络均停止/移除。持久化重建、恢复、只读拒写和 Orthanc 网络访问尚未验收。
- E4 worker 仍是 Windows CPython 环境，不能挂载到 Linux 容器，也不能把它的 source/gate 冒充 Linux 证据；Linux worker 已另行锁定并内置于 Docker 后端镜像。
- 当前真实同检查四序列资料的像素烧录文字仍待人工确认，ACRIN-134 的重采样纯影像工程验收不代表胶质瘤模型或临床效能。未导入、转换、推理或挂载这些候选资料。
- 持久化重建、只读挂载、真实 PACS/Orthanc 网络访问、真实数据页面阅片及许可/去标识确认未验收；隔离健康检查不得表述为完整项目 Compose 验收。

## 历史实施步骤（已完成项见后文 10 月 20 日验收）

1. 已通过后端 API/PyRadiomics 双解释器集成：默认 `core` 镜像保留轻量 Python 3.10 API；Compose 显式选择 `full` 目标，在 Python 3.10 API 镜像内置独立 Python 3.9.25 / PyRadiomics 3.1.0。Linux x86_64 依赖按 wheel SHA256 锁定，来源清单 `/opt/radiomics/source.json`。Compose 后端镜像 `brainfusion-ai-backend:latest` digest `sha256:048e2cc29eb5cbeafadfe5fc735735910c3e15540f9edde063b846c540801b8c`（约 2.63 GB）。5 个公开参考病例的 100 个特征、5 个模型概率及 252 个归一化检查通过；Compose 内的来源 gate、病例 13 worker 提取、前后端健康检查和 OpenAPI 68 路径通过。来源清单 SHA256 `849e37e7cde62e6e325db7060a4f710d668996f018c9dd1608b4f9d01d038d1d`。详细输入锁、病例输出和比较报告位于 `E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T132214_linux-radiomics-e5/`。验证 gate 已写入新建的 `E:/BrainFusion-Runtime/local/radiomics-compatibility.json`，没有覆盖其他私有配置。Linux worker gate 不得复用于 Windows 本机 worker。
2. 接下来复核 Orthanc 从容器访问的地址、挂载目录只读/读写边界，并测试数据库/上传/作业在临时 runtime 重建后的持久性。当前 Compose 冒烟使用了临时 runtime，不覆盖现有原生 runtime/数据库。
3. 用户真实同检查四序列资料仍需人工确认像素烧录文字、角色身份与授权；确认后再走网页阅片和真实病例工程流程。ACRIN-134 仍仅用于影像转换工程验收，不支持胶质瘤效能结论。
4. 对未修复的 Cornerstone/DICOM 依赖 advisories 做上游版本与兼容性评估，再决定是否更新或保留有证据的风险说明。

## 初次实施批次边界（历史记录）

本轮更改后端 Dockerfile、Linux radiomics 哈希锁、core 哈希锁和来源清单生成器、Compose target/worker 路径及验收记录；并新建 `local/radiomics-compatibility.json`。前端 package-lock 的 semver 内安全更新记录沿用本轮已有进展。没有改动业务数据库、模型、数据集、PACS 配置或本机原生服务，没有启动真实胶质瘤病例任务。Compose 测试 runtime 目录和 Docker 镜像保留供继续验收；用户要求的 C/E 盘最终清理及项目归整安排在工程验收完成后，届时先盘点并验证再迁移，不删除模型、原始数据、唯一备份或可复现证据。

## 2026-10-20 更新：Orthanc 身份重绑与 Docker 访问验收

- 用户确认当前运行的 Orthanc 是项目目标归档，并授权“备份后重绑”。操作前备份了 PACS 配置、Orthanc 配置、索引和影像存储到 `E:/BrainFusion-Runtime/backups/pacs-identity-rebind-20261020/`；共 197 个文件，19,578,101 字节，含逐文件 SHA-256 清单。旧配置另存为 `pacs-config-pre-rebind.json`。没有导入或删除任何病例。
- 将 `E:/BrainFusion-Runtime/local/pacs-config.json` 的数据库身份 pin 更新为当前 Orthanc 身份；用户名、密码、地址及 `allow_pixel_read` 原值均保留。主机端认证 `/system` 和 QIDO 均返回 HTTP 200；Docker 容器端 identity pin 校验通过，QIDO 返回 1 条 study 元数据。只读状态与元数据，不取像素。
- 发现现有配置 `allow_pixel_read=true`，与早期记录所述“false”不符；本轮刻意未更改该授权开关，只使用 `/system` 与 QIDO 验收，并已在证据中标明。后续若要关闭像素读取，应作为独立配置变更核对功能影响。
- Docker 主机网关补丁已通过容器内访问真实本机 Orthanc 的验证。该验证用旧后端镜像并只读覆盖最新 `pacs_client.py` 源文件；单位协议测试此前为 39 passed。新镜像重建因锁定依赖安装下载缓慢而中断，旧镜像仍保留，因此不能声称 `brainfusion-ai-backend:latest` 已包含此补丁。完整 Compose 端到端启动需待新镜像构建后补验。
- 结构化证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T132214_linux-radiomics-e5/orthanc-rebind-verification.json`。真实病例像素审阅、用户身份/数据授权确认及胶质瘤效能验证仍未完成。


## 2026-10-20 更新：重绑后的正式镜像与 Compose 联合验收通过

- 完成了 `brainfusion-ai-backend:latest` full 镜像重建，摘要为 `sha256:aa3711890c529ecafc64a5815d94a623a24df6e9c5fc70efd504520c54e63973`；该镜像包含 PACS Docker host-gateway 修复。Compose 前端镜像摘要为 `sha256:10ca43789559341220c35bcfa55c8cbdcda586af49c3a0e8a84bb9f7a7e4e013`。
- 在独立临时 runtime 目录启动完整 Compose：后端与前端 health 均为 healthy；OpenAPI HTTP 200、68 路径；前端 HTTP 200；PACS status HTTP 200。容器内对 Orthanc 完成身份 pin 核验，QIDO 返回 1 条 study 元数据。
- `/run-config`、`/models`、`/research`、`/dataset`、`/pacs-derived` 五个挂载均实测拒绝写入。数据集挂载为空；没有挂载既有业务 runtime，没有读取像素、导入病例或写入现有数据库。隔离验收后容器与 Compose network 已移除；临时 runtime 和镜像保留。
- 结构化结果见 `E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T132214_linux-radiomics-e5/compose-e5-rebind-20261020.json`。此结果补全正式 full 镜像的容器到目标 Orthanc 元数据连通验收；不能替代真实四序列人工审查、许可确认、网页阅片或胶质瘤效能验证。


## 2026-10-20 M2 生命周期回归

转换来源完整性、角色复核、显式激活、登记/重试、分析输入失效与历史、当前输出和 PACS runtime 层后端定向回归 81 passed（4条既有弃用警告）；Microsoft Edge 两个合成页面场景通过（角色批准/激活分步、归档旧分析不显示旧结果）。首轮测试路径在 C 盘，被 E 盘隔离规则拒绝；指定 E 盘 basetemp 后通过。报告 `E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T132214_linux-radiomics-e5/m2-regression-20261020.json`。仍须真实合法四序列来源与审核才能验收真实转换到激活链路。

## 2026-10-20 最终镜像重建持久性复验

在最终 Compose 镜像的临时 runtime 内写入专用 SQLite 标记、上传标记和 feature-job 标记；停止并重建前后端容器与网络后，后端/前端再次 healthy，三类标记均保留。容器和网络再次关闭；仅隔离 runtime 保留测试记录。验证日志 `E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T132214_linux-radiomics-e5/compose-persistence-final-image.log`，结果已并入 `compose-e5-rebind-20261020.json`。

## 2026-10-20 后续回归：全后端与后台进程约束

- 全量后端回归最终结果为 694 passed、4 条既有弃用警告，197.18 秒；日志 `backend-full-regression-final4.log`。最终从 `backend/` 目录运行，使用仓库的 `pytest.ini`。
- Docker摘要回归原先把多阶段 Dockerfile 中的内部 `api` 阶段也算作外部镜像，断言已改为只核对四个外部基础镜像。
- 后台服务进程验证发现 Windows Job 限制：旧 WMI bootstrap 的 limits 为 `0x00003000`，服务 PID被 `IsProcessInJob` 判为受 job 约束。启动器已改为 PowerShell内直接同步调用 Python 引导程序，绕过 WMI provider 的额外 job；同时核验最终服务 PID。若仍受 kill-on-close job 约束，会回收 PID并返回含 PID及`child_terminated=True`的原因，不会误报启动成功。对应的 fail-closed 回归通过。Codex 托管 PowerShell 仍位于受限 job，故普通交互 PowerShell 下的常驻服务启动尚未在本机独立验收；若需要该路径，仍需在用户普通会话验证真实启动和停止。
- 该问题不影响已通过的 Docker Compose容器生命周期/持久性验收，因为 Compose服务由Docker Engine管理。也不构成真实四序列或模型效能验收；候选影像仍未读像素。

## 2026-10-20 最终源码工作树全量回归（final5）

本轮在回滚一次失败的后台启动实验后，对当前完整后端源码重新执行全部回归：694 passed、0 failed、4条既有弃用警告，195.99秒。日志：`E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T132214_linux-radiomics-e5/backend-full-regression-final5.log`。独占开发锁已释放，退出码0。此次结果取代同路径下final4作为当前源码回归证据；它不改变真实四序列人工隐私审核、普通交互PowerShell常驻启动验证和正式用户演示尚未完成的状态。

