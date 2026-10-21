

# 当前状态覆盖（2026-10-20）

Docker Desktop 4.95.0 与 Linux Engine 29.8.2 已在本机正常运行。正式 Compose full 后端/前端镜像均已构建，并在隔离 runtime 完成健康检查、API/OpenAPI、前端HTTP、Orthanc身份/QIDO元数据连通、只读挂载拒写和容器重建持久性验收。当前不得再按下文历史步骤安装Docker或启用WSL；最新结论及机器证据见[2026-10-20 E5验收记录](E5_DOCKER_RUNTIME_VALIDATION_20261020.md)。

这些结果只覆盖隔离Compose和本机Docker环境，不代表干净机器安装、实际业务病例阅片或真实四序列AI链路验收。正式运行仍须由部署者提供持久runtime目录、私有账户/PACS配置、已验证模型与研究包、获准数据集及Linux工作器；不要将Windows Python工作器或未审核病例挂载为已验收输入。当前工程收尾及剩余人工判断以[系统当前阶段](CURRENT_STAGE.md)和[用户验收问答](USER_ACCEPTANCE_QA_20261020.md)为准。

以下10月19日及更早的安装故障和权限说明是历史诊断，仅解释Docker安装过程，不再表示当前机器状态。

## 2026-10-19 E5 root-cause evidence: Windows servicing rolled back WSL feature enablement

After the user ran the elevated DISM command and restarted, the Docker installer still reported VirtualMachinePlatform disabled. Read-only WMI now reports InstallState=2 (Disabled) for both VirtualMachinePlatform and Microsoft-Windows-Subsystem-Linux. The machine reports firmware virtualization enabled and a hypervisor present. DISM/CBS logs show the enable command set VirtualMachinePlatform to On and pended changes for reboot; during startup servicing, Network Drivers failed to load NetSetupAI.dll (0x8007007e), followed by CBS_E_INSTALLERS_FAILED / 0x800f0922 and a rollback transaction. This explains why the feature was still disabled after restart; do not treat the Docker installer as the root cause.

Recovery path for the device administrator: run DISM /Online /Cleanup-Image /RestoreHealth in elevated Command Prompt or PowerShell, wait for successful completion, then run sfc /scannow. Microsoft recommends DISM before SFC to repair the component image and protected system files. After both complete, enable Microsoft-Windows-Subsystem-Linux and VirtualMachinePlatform with DISM, verify each reports State: Enabled, restart, verify again, and only then retry the regular-user Docker Desktop installer. If Windows repair fails or the same CBS rollback recurs, retain the CBS.log lines for NetSetupAI.dll and 0x800f0922 for Windows servicing repair; do not repeatedly retry Docker.

No repair command or system-feature change was executed by Codex; these diagnostics and next steps are based on read-only logs and component-state queries. Docker/container acceptance remains incomplete.


## 2026-10-19 E5 environment update: WSL installed; VirtualMachinePlatform still requires administrator enablement

The user has installed WSL. In this session, wsl --version reports WSL 3.0.3 and wsl --list --verbose reports no user Linux distribution. The Docker Desktop 4.95.0 installer explicitly reports that the Windows optional feature VirtualMachinePlatform is disabled. This session is not elevated; the read-only DISM query returned exit code 740, and no system feature was changed. Docker CLI/Desktop are not yet successfully installed; the Docker terms have not been accepted and the computer has not been restarted.

The earlier status saying WSL was not installed is superseded. E5 is currently blocked on an administrator enabling VirtualMachinePlatform and restarting Windows. An administrator can run the following in elevated PowerShell:

    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

After restart, the regular user can install Docker Desktop per-user and personally review and accept its first-run terms. Compose parsing, image build/run and E5 project validation remain outstanding. This update does not claim Docker or container acceptance.

# 2026-10-18：当前权限安排（覆盖下方较早的安装障碍描述）

当前Codex桌面会话以普通用户权限运行，不能在对话内自行提权；重启/重新打开Codex为管理员也会扩大整个进程权限，因此不作为默认方案。若验收目标是Linux容器，不必把Codex设为管理员：请管理员只完成一次WSL 2系统功能启用并按提示重启；其后由当前普通Windows账号按Docker官方推荐的per-user模式安装和运行Docker Desktop。Docker官方说明per-user安装/更新不需要管理员权限，首次在本机启用WSL 2仍需要管理员权限。若暂时不能启用WSL 2，可评估Docker VMM（Beta）per-user后端，但它必须在本项目实际构建、运行和PACS连通测试中通过才算验收。

管理员操作：在开始菜单搜索PowerShell，右键“以管理员身份运行”，执行`wsl --install`，按Windows提示重启。若系统说明WSL已安装，则以`wsl --status`核对并根据提示更新；不要把管理员密码发送给Codex。重启后，以普通用户交互式运行Docker Desktop安装器，选择推荐的per-user安装和WSL 2后端，首次启动时由用户审阅并接受Docker Desktop条款。然后在Codex普通会话中通知“Docker Desktop已启动”，由Codex核对`docker version`、`docker compose version`并按E5清单执行容器验收。参考：[微软WSL安装](https://learn.microsoft.com/en-us/windows/wsl/install)、[Docker Desktop Windows安装与权限模式](https://docs.docker.com/desktop/setup/install/windows-install/)。

此前Codex自动审批曾在执行前拦截一次用户级安装尝试；当时没有下载或安装软件。该历史事件不表示官方per-user安装本身要求管理员，也不改变当前会话权限。若实际执行仍被本机策略拦截，请由用户交互式运行官方安装器，不要尝试绕过策略。

## 2026-10-18 固定容器基础镜像摘要

Dockerfile已固定三个官方多架构基础镜像索引摘要：后端 `python:3.10-slim-bookworm@sha256:5be5aaecb962a41567bc8041f1e9e3432cb085b037fe057f9a562630b2e4b370`；前端构建 `node:24-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f`；前端运行 `nginx:1.30.6-alpine3.24@sha256:970364228b1e4f932abc22d321932816782cca8a20b85a77552a7cfe9acfb3b5`。三个索引分别指向linux/amd64和linux/arm64的不可变子清单；完整索引及平台SHA来自Docker Hub Registry v2，只读记录见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1837_docker_base_lock/base-image-digests.json`。官方镜像目录：[Python](https://hub.docker.com/_/python)、[Node](https://hub.docker.com/_/node)、[NGINX](https://hub.docker.com/_/nginx)。回归测试会拒绝不含sha256摘要的FROM行。

这只固定基础镜像，不代表已拉取、构建或运行容器。2026-10-18已为Docker专用CPython 3.10/Linux x86_64提供core与Compose默认full两种哈希锁配置：核心锁28个wheel；完整锁44个wheel，含CPU Torch 2.11.0+cpu、MONAI、scikit-learn/joblib及传递依赖。Compose把前后端都固定到linux/amd64，与锁目标一致。Pillow因12.3.0没有Python 3.10 Linux wheel而使用12.2.0。apt包未额外安装；Docker Desktop/WSL、镜像拉取构建运行、PACS和工作器Linux实测仍待完成。

# E5 本机容器前提与解除条件

## 2026-10-18 当前账号复核

当前机器为 Windows 11 专业版 build 26200，内存31.2 GB、固件虚拟化已启用；本机仍没有 Docker CLI、Docker Desktop 或可用的 WSL 发行版，当前用户不是管理员。Windows版本和硬件满足 Docker Desktop 文档列出的基础条件，但首次启用 WSL 2 需要管理员权限；Docker Desktop当前用户安装可免管理员，官方也列出 Docker VMM（Beta）供当前用户模式使用。参见[Windows安装说明](https://docs.docker.com/desktop/setup/install/windows-install/)和[Windows权限说明](https://docs.docker.com/desktop/setup/install/windows-permission-requirements/)。

已尝试执行经WinGet当前清单核对的官方per-user安装流程；Codex自动审批在命令执行前以`blocked by policy`拒绝，运行目录未创建、安装器未下载、软件未安装，也未接受Docker服务条款。后续需由用户手动安装Docker Desktop per-user并在首次启动时审阅/接受协议；若选择WSL 2，须由管理员启用一次并按提示重启；若使用per-user Docker VMM，仍需在桌面实际启动后验证项目兼容性。未完成这些步骤前继续使用原生Windows环境验收，不宣称E5通过。

更新：2026-10-18。Compose/Dockerfile 仅完成静态准备；未构建镜像或运行容器，现有本机服务不受影响。

此前只读环境检查显示 WSL 未安装、Docker CLI 不存在，且当前进程无管理员权限。系统安装和重启窗口未安排。安装依据：[微软 WSL 安装说明](https://learn.microsoft.com/en-us/windows/wsl/install)和[Docker Desktop Windows 安装说明](https://docs.docker.com/desktop/setup/install/windows-install/)。

Compose 现在要求提供外部持久运行目录、私有配置、模型、研究包、获准数据集、已准备 DICOM 派生资料和已验证 Linux PyRadiomics 工作器。上传、数据库、作业、隔离区和导入/转换记录持久化；模型、数据、配置和工作器只读。前端使用 `npm ci`。Linux 工作器的 `source.json` 及兼容性哈希门槛须重新验证；不得挂载 Windows Python 工作器。

账户、PACS 配置、PACS 导入、转换、隔离和派生资料读取的盘符判断已改为跨平台绝对路径规则；Windows 仍只允许 E:，POSIX 允许绝对路径，并继续检查目录归属、路径解析和符号链接。该改动通过本机回归，但不代表 POSIX/Docker 实测。Orthanc/PACS 仍需由容器外部提供并可达。

路径兼容性更新：账户、PACS 配置/导入、转换/作业/审核、隔离和派生资料读取的路径限制已改为跨平台绝对路径规则；Windows 仍只允许 E:，POSIX 允许绝对路径，同时保留目录归属、解析结果和符号链接校验。已加入仅在显式配置时允许 `host.docker.internal` 的门槛，Compose 开启该开关，任意远程主机仍拒绝；Docker 官方文档说明该名称映射到宿主机地址。当前解包源码候选的本机回归 215 passed；这不代表 POSIX/Docker 网络实测。Docker/WSL 缺失仍阻断实际构建。

容器验收还须验证：缺少 Compose 必需变量时安全失败；前后端健康；上传、数据库和作业在重建后保留；只读挂载不可写；CPU 分割、研究流程、PACS、阅片、审核与报告在 Linux 用受控数据通过；重建前后结果一致。未人工确认无烧录文字且未授权的影像不得导入。合成数据只能验证工程行为，不能证明胶质瘤模型效能。本机验收不能替代 Docker/Linux 验收。
