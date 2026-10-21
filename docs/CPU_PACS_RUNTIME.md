# 当前CPU/PACS命令行环境

## 2026-10-16 08:13 当前HTTP入口已验

直接CPU基解释器加显式`-PacsRuntimeLayer`已通过实际HTTP/Edge首启、复用、重启、账户会话及回原验证，详见[E6当前运行组合](E6_CPU_PACS_LIVE_VALIDATION.md)。固定轮子内容逐文件核对，补充目录只提供pydicom；不再从venv重定向启动服务。该方法仍依赖原52包基环境及固定缓存，不是独立新机安装。

下面07:16记录为当时CLI验收及原venv入口限制；Scripts/python的拒绝继续有效，新增直接解释器方式按上述报告操作，不能在正式端口同时起第二服务。

2026-10-16，run_id `20261016T071748_cpupacs`。当前后端启动即导入PACS受控导入服务，pydicom不是仅预检时才需要的可选包；requirements-core补固定3.0.2，启动前检同时检查httpx和pydicom。主CUDA/特征工作器、模型/协议不变。

## 已验组成

本机复用已有52包CPU主环境`E:\BrainFusion-Runtime\envs\runtime311-cpu-delivery-20261010T060619_ce64597d\python.exe`，按delivery-source.json真实SHA核对元信息后，创建一份小型Windows venv（system-site-packages、without-pip）。只从已验官方缓存安装pydicom3.0.2，未复制或重装52包、未重新取422前端依赖，也不改原CPU/CUDA/特征环境。

新命令行解释器：`E:\BrainFusion-Runtime\envs\runtime311-pacs-20261016T071748_cpupacs\Scripts\python.exe`。它仍依赖原CPU基环境在原路径，不能单独搬到另一机器或删除基环境。不是新的完整独立安装器。

固定轮子2376822字节，SHA256 `abf971a5440f84dbaf42c4b6758e30e62480902584f8b270b9a5d146e278a07b`；官方URL及来源记录保存在本轮environment/pydicom-source.json，沿用10/13已核官方PyPI元信息与文件，不重新下载或执行数据集脚本。项目工具仅用标准库、不联网、失败保留部分目录，不在同一prefix盲重试。

生成命令须放在E盘工作脚本中，由run_development_step.ps1同步持锁执行，重核交接/基环境/目标和缓存。示例参数必须替换为真实可信receipt SHA及不存在的E盘目录：

```powershell
<可信E盘Python> -B E:/BrainFusion-AI/backend/tools/prepare_pacs_cpu_runtime.py --base-python <已验CPU基环境/python.exe> --base-receipt-sha256 <原始delivery-source.json真实SHA256> --wheel E:/BrainFusion-Runtime/cache/dicom-tools/pydicom-3.0.2-py3-none-any.whl --prefix E:/BrainFusion-Runtime/envs/runtime311-pacs-<唯一标识> --output <全新E盘nightly子目录>
```

安装前验证52包基元信息及固定轮子大小/SHA，pip no-index/no-deps/no-compile/require-hashes；安装报告只有这一条且SHA一致，pip check通过，结果53包。基解释器/receipt、52包元信息及RECORD哈希前后不变；这不是逐字节重审所有torch库或基环境来源重认证。

当前实际验证：原CPU严格前检明确因缺pydicom退出2；新环境同一真实模型/研究/数据库的只读前检通过，CPU torch无CUDA。当前app在全新隔离SQLite导入/创建17表，匿名账户无配置，根接口可用；相关10文件128项检查通过、原主环境4项账户快照回归通过，均有4个既有弃用警告。未执行新模型推理/特征提取/真实导入/报告PDF，不据此宣布HTTP联合部署通过。

## Windows启动限制

实际短进程探针证明venv的Scripts/python.exe返回launcher PID14912，而执行Python的原生子进程为22100，二者不同；父子已同步结束。这是本轮观测，不把固定PID作为后续身份。当前start_local/stop_local采用直接PID登记，尚不支持此重定向关系。

start_local对这类venv现在在启动前明确拒绝，未关闭/创建任何服务，避免把launcher误登记成服务。当前环境用于同步命令行验证；不要把它直接传给正式服务启动，也不靠手工启动第二后端绕过身份检查。原直接解释器ReuseExisting实际仍通过、PID保持。

下一步须实现有明确来源/模块路径约束的直接解释器运行方式，或可靠的父子进程登记/监听归属及正常停机，再在已恢复数据副本验证HTTP/重启/回原；这些尚未验收。P3匹配真实四序列/E5系统授权和最终异机仍保留。

## 源码版本与证据

06:15的402文件ZIP保持冻结。本轮core依赖/前检/CLI工具/Windows启动拒绝/合成Cookie夹具修正和本指南是之后的增量；不反复生成整包，使用本轮source-delta及source-delta-manifest.json核对原ZIP SHA、旧/新文件SHA，assembled-source为实际逐文件组合验证目录。它仍是源码，不含数据/模型/环境/凭据。

首轮CPU检查127通过/1失败，复现为测试人为加入无domain的重复会话Cookie导致旧值遮住新登录；改为保留原浏览器已有作用域Cookie后128通过。生产Cookie/CSRF/权限逻辑没有放宽，也未升级Starlette/httpx来掩盖问题。原失败日志与不含token值的两对照cookie-scope-reproduction.json保留。

本轮证据根`E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T071748_cpupacs/`：environment下来源/安装/元信息、两份preflight、隔离app导入、四种拒绝与Cookie复现、CPU最终pytest XML/日志、主环境4项、Windows PID探针/启动拒绝与原服务复用、源码增量及原17表/配置/服务保护。大数据/账户完整恢复复用上一轮，不重抄650应用或192归档。
