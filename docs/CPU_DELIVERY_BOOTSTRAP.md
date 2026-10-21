# CPU源码与来源锁迁移包

08:11补独立worker引导及组成指南RADIOMICS_DELIVERY_BOOTSTRAP，标准库/可信Conda/新prefix自身pip，无旧工程pip/原worker安装前提；20Conda/11wheel/15实际包/1102导入文件通过，科学门槛/服务切换未验。CPU主锁与worker NumPy1.26.4协议隔离，不混装；旧07:05源码包因本轮增量保留历史。下方未独立引导为历史边界。

07:05最新前端增量独立安装/构建、真实HTTP初启/重启浏览器已验，详FRONTEND_DELIVERY；下方06:06“仅前端预检”是该轮历史边界，不能当07:05仍未安装。CPU包角色不变，仍不包含Node/npm二进制或独立PyRadiomics环境；本轮源码有新工具/文档，06:06冻结包保留历史、不覆盖。

本工具用于E6可重建Windows CPU主环境，不是成组MRI/DICOM/临床模型扩展，也不是异机或Linux容器已验收声明。现用CUDA和CPU特征工作器保持原配置；前轮CPU模型与真实服务通过见CPU_RUNTIME_CANDIDATE。

## 包内与包外

`prepare_cpu_delivery.py`绑定当前白名单源码、52项官方CPU发行来源锁、20项Conda解释器锁、独立stdlib引导入口与前轮真实CPU工程验收。所有成员逐文件SHA，外层ZIP与嵌套源码ZIP均检查成员集合/大小/重复/路径/软链接/内容SHA。外部可信bundle SHA必须独立传入；SHA仅完整性，不是签名、来源身份或全面安全认证。源码来自保护的脏树，包括真实未提交实现，不提交或发布。

不包含：数据库、MRI、患者记录、模型权重、结果/报告、Python环境、任何第三方发行二进制、Node依赖、内部反馈/日报。必须另有可信E盘Conda引导解释器、已核验52轮子和20Conda缓存；安装器完全离线、缺缓存拒绝，不能伪造下载成功或用未知镜像。CPU主包不包含PyRadiomics，独立特征worker/兼容门槛/数据与模型仍需按对应指南迁移；不能据此称完整系统开箱即用。

## 使用

从可信本地原始包取实际SHA，先运行与冻结源码相同的`bootstrap_cpu_delivery.py`入口。包被改或SHA不符时，在写解包/环境之前拒绝；缺缓存或prefix已存在也拒绝。不执行包中的数据集脚本；只有经过明确安装调用的可信Conda/pip会运行。

```powershell
# 替换实际bundle、SHA和全新的nightly目录；不要复用已存在环境。
E:/Anaconda3/python.exe -B E:/BrainFusion-AI/backend/tools/bootstrap_cpu_delivery.py --bundle <E盘已核验bundle.zip> --expected-bundle-sha256 <原始可信SHA256> --output <E盘nightly新目录> --install-prefix E:/BrainFusion-Runtime/envs/runtime311-cpu-delivery-demo
```

仅验证/解包时省略install-prefix；解包到output/project，入口与来源锁到output/bundle。安装使用E:/Anaconda3/python.exe的Conda（可显式conda-python覆盖已核验E盘解释器），不导入工程内旧主环境或借用其pip；Conda从20项实际SHA缓存文件显式离线引导，再用新解释器自己的pip、force-reinstall/no-index/no-deps/require-hashes安装完整52项。TEMP/TMP/Conda/pip缓存与结果均E盘，不登记C盘用户Conda环境。失败保留目录/日志/进程记录，不在同一partial prefix盲重跑、不删旧环境或数据。

阶段状态分别为verified_and_unpacked_no_install、rebuilt_from_verified_local_caches_not_model_or_deployment_accepted。安装后检查52实际元信息、pip check、52pip安装报告全部发布SHA；版本匹配不能代替文件来源锁。模型/病例/保存/工作器/浏览器和前端依赖另验，缺项具体报错，不跳过前检假成功。Windows x64/CPython3.11.17为唯一已冻结目标，不能把win_amd64锁用于Linux。

## 验收与限制

2026-10-10 06:06窗口实际重建prefix为E:/BrainFusion-Runtime/envs/runtime311-cpu-delivery-20261010T060619_ce64597d。引导解释器是E:/Anaconda3/python.exe，不是工程旧环境；72份缓存通过SHA，完整52项实际安装报告/元信息/pip check一致。现用主3.10与CPU候选原树、新重建CPU环境的独立解包副本均103后端通过，副本已有本机前检/数据库全表签名不变；新增11项检查与实际CLI损坏外层包/缓存轮子拒绝均通过，拒绝时无输出目录或prefix。C盘Conda登记SHA不变，原服务/默认CUDA与特征worker保留。

前端目前不能视为本包已独立安装：原package-lock有422项registry.npmmirror.com发行URL；仅官方registry.npmjs.org固定版本元信息/原SRI预检吻合，外部候选仅替换resolved。Element Plus在@popperjs/core目录使用明确的npm:@sxzz/popperjs-es别名，需按锁内name保持真实发行身份，不能替换为另一同版本包。Node v24.21.0 Windows x64官方SHASUMS与HEAD为37618919字节预算，未下载/运行/验数字签名；全部npm unpackedSize合计包含跨平台可选/重复，不是网络流量或待下载文件量。未下载安装Node或npm包、未新构建。现有测试联接只复用原E盘node_modules，不能对联接执行npm ci；新前端环境必须另选无联接的独立目录，以原SRI验证所有实际下载文件、初始禁安装脚本并记录来源/构建。

本轮执行证据以最新NIGHTLY_HANDOFF与run_id下CPU bundle validation、stdlib解包/离线重建日志、安装元信息、来源报告、包内容SHA/后端测试为准；同机缓存重建不是异机安装。新环境不启动第二服务、不改变默认CUDA、不再重复前轮CPU模型推理或55特征提取；对已验证固定发行以真实安装身份及源码回归检查本次引导路径。

源包是冻结版本。包生成后若文档/源码有增量，必须明确历史/漂移，不覆盖旧包或冒称当前；最终候选应在本轮交付文档冻结后另建目录核验当前/解包一致。第三方许可元信息不等于数据/模型/依赖再分发认证，无自动发布。E5的管理员WSL/Docker/可能重启窗口未解决，CPU Linux服务/重建持久化仍未验；新机Conda/Node/特征worker/模型数据引导仍待真实验证。
