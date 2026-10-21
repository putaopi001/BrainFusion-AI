# 自动掩膜特征研究详细操作

更新：2026-10-09。本机工程链路和病例输入版本已验证；这是参考掩膜模型的自动输入迁移实验，尚未重新训练或独立评价。

2026-10-10 01:06窗口补充：E4已验收；当前runtime-supported.json（20261010T010640_a6ee8135）配置独立Python3.11.17，五参考/病例17自动掩膜/缓存/实际重启通过。旧stage6与radiomics39是归档，不是当前工作器。病例17当前临床57岁male、患者资料56岁male，独立版本保持；旧病例11–15性别未知不能代填归档值。具体来源/复建见RADIOMICS_ENVIRONMENT_MIGRATION，当前固定操作见FIXED_DEMO_GUIDE。

## 一、启动并进入

已有服务在 http://127.0.0.1:5179 。没有运行时在 PowerShell 执行：

```powershell
cd E:/BrainFusion-AI
./backend/tools/start_local.ps1 -ReuseExisting -RuntimeConfig E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T010640_a6ee8135/runtime-supported.json -BackendPort 8012 -FrontendPort 5179
```

先打开分割完成的病例，进入“AI 分析”，点击“自动掩膜特征研究”。也可直接打开 http://127.0.0.1:5179/research ，在“当前病例：自动掩膜特征研究”选择已分析病例。仅上传了单序列或参考掩膜的病例不满足输入条件。

历史stage2/6演示对应：源患者4/13/16/17/19→系统病例11/12/13/14/15，但其当前导入临床资料不完整。当前固定演示系统病例17→源患者4；源患者ID与系统病例ID不同。无需重跑核心验证来追加病例或推理。

## 二、首次实际计算

1. 为新病例上传同患者的 t1c、t1n、t2w、t2f 配准、1 mm、正交 NIfTI，运行分割并等待成功。已有演示病例无需再推理。
2. 进入研究页，在“当前病例：自动掩膜特征研究”选择病例，年龄/性别默认来自关联患者。若需不同研究输入，在病例卡内修改并先保存独立研究版本；上方“临床基线输入”不改变病例任务。例如源患者13对应系统病例12，只有核对关联资料后才使用相应研究输入。
3. 在自动特征卡点击“提取自动掩膜特征”。后台使用当前真实预测掩膜和四序列；不会用参考掩膜代替。
4. 等待 queued（排队）、running（运行）变为 succeeded（成功）。页面自动轮询，也可点击“刷新任务”。本机五例提取约 2–4 秒，整个请求还包括启动/校验/轮询；时长不是保证值。
5. 查看临床、自动掩膜影像组学、平均、固定 0.6/0.4 和 TOPSIS 概率，以及此次临床输入、分割版本、研究版本。结果目标是原数据 IDH1/2=1，未经校准。
6. 刷新页面或重开病例研究入口可读取已存任务；重新选择对应病例查看。相同临床输入和版本再次提交会显示“读取已存结果”，不重复提取。

参考掩膜表格与自动掩膜表格显示的是两种输入，不自动判断哪一个正确。分割边界变化会改变特征及研究概率，例如源患者 17 为 53.8%→20.4%。五例是工程开发样本，不能据此获得独立准确率；19 的参考标签缺失。

## 三、与医生报告的关系

特征任务不改动分割掩膜、医生意见、确认或病例诊断报告。当前研究概率保存在研究任务中；正式加入临床报告前，需要同协议自动掩膜训练数据、重新拟合和独立评估。

重新上传 MRI、替换掩膜或重新分割后，旧输入上的任务不再作为当前版本显示。若输入在 CPU 提取过程中变化，该任务失败并保留日志，不能返回旧版本成功概率。新版本需要重新提交。

## 四、文件与接口

| 内容 | 位置 |
|---|---|
| 独立 CPU 提取解释器 | E:/BrainFusion-Runtime/envs/radiomics311-candidate/python.exe |
| 特征契约与复现检查 | 本窗口candidate-reference-gate-complete/compatibility.json（由runtime-supported.json指定） |
| 数据登记与未解决项 | E:/BrainFusion-Runtime/results/stage6/research_registry.json |
| 任务目录 | 本窗口feature_jobs/{病例ID}/{分析ID}/{任务ID}（由runtime-supported.json指定） |
| 每次输入/日志/特征/状态 | request.json、worker.log、features.json、state.json |
| API 文档 | http://127.0.0.1:8012/docs |

POST /research/cases/12/features，JSON {"age":39,"female":false}，HTTP 202 返回任务。GET 相同地址返回当前分割版本的最近任务，未提交时 data=null。result 内包含概率、选中特征、区域体素数、模型版本、输入哈希、环境版本和提取耗时。只提取模型用到的 20 个特征，不将 1134 个原始列全部重算。

## 五、首次新机器配置和复现：当前/历史区分

本机3.11工作器已就绪，无需重复安装。新机器按RADIOMICS_ENVIRONMENT_MIGRATION中的冻结来源/源码轮子/新候选复建和门槛，不在主CUDA安装降级依赖。以下是历史3.9离线兼容步骤，不推荐新部署；执行会建立旧环境，不会建立当前受支持工作器：

```powershell
cd E:/BrainFusion-AI/backend
. ./tools/use_e_drive.ps1
../.conda/brainfusion/python.exe tools/setup_radiomics_worker.py
if ($LASTEXITCODE -ne 0) { throw 'Worker setup failed' }
../.conda/brainfusion/python.exe tools/verify_feature_extraction.py --output E:/BrainFusion-Runtime/results/reference-gate-new
if ($LASTEXITCODE -ne 0) { throw 'Reference feature gate failed' }
```

输出目录reference-gate-new须不存在，并按此次运行改为新的唯一目录。成功后才允许配置RADIOMICS_COMPATIBILITY指向新compatibility.json；旧门槛保留，不能覆盖。新支持环境使用--worker/--baseline/--research-dir/--data-dir显式指定，不把setup_radiomics_worker.py建立的旧3.9环境当成已完成E4。

工作器独立固定 NumPy/PyRadiomics，不向主 CUDA 环境安装降级包，也不创建系统安装/注册项。Python 3.9.13 是归档离线兼容解释器；正式部署应升级到受支持的解释器，构建兼容扩展并重新复现，不能直接把它当生产服务环境。

更换研究模型、选中特征、提取代码或工作器后，旧复现门槛会失效。先重新运行 verify_feature_extraction.py，确认五例参考特征和原概率复现通过，再提交自动掩膜任务。不要手工修改 compatibility.json 绕过检查。

五例接口再验收时，先等待所有任务完成并关闭演示服务：

```powershell
cd E:/BrainFusion-AI
./backend/tools/stop_local.ps1
cd backend
. ./tools/use_e_drive.ps1
../.conda/brainfusion/python.exe tools/verify_automatic_features.py
if ($LASTEXITCODE -ne 0) { throw 'Automatic feature validation failed' }
cd ..
./backend/tools/start_local.ps1 -Demo -BackendPort 8012 -FrontendPort 5179
```

该脚本使用工程数据库与已存成功分割，会生成或复用五例特征任务；不重新训练/分割。不要同时运行共享工程数据库的后端。

旧五例浏览器工具verify_automatic_features_browser.mjs保留2026-10-07阶段的输出约定，勿为了本轮复验覆盖stage6历史证据。当前逐轮验证用verify_current_outputs_browser.mjs、verify_case_clinical_browser.mjs及verify_clinical_persistence_browser.mjs，须指定新的BRAINFUSION_EVIDENCE_DIR，并使用恢复副本/明确合成旧记录和可续接病例。具体本轮配置与已执行证据见NIGHTLY_HANDOFF；后续只复验变更及相关任务，不重复上传/推理全部五例。

## 六、重启验证与关闭

```powershell
cd E:/BrainFusion-AI
. ./backend/tools/use_e_drive.ps1
./.conda/brainfusion/python.exe backend/tools/verify_feature_persistence.py --capture
if ($LASTEXITCODE -ne 0) { throw 'Wait for feature jobs to finish' }
./backend/tools/stop_local.ps1
./backend/tools/start_local.ps1 -Demo -BackendPort 8012 -FrontendPort 5179
./.conda/brainfusion/python.exe backend/tools/verify_feature_persistence.py
```

关闭前等待分割与特征任务完成。成功结果重启后保留；中断任务重启标失败，需要重试。停止脚本通过 PID 和启动时间识别登记服务。

## 七、错误处理

| 现象 | 操作 |
|---|---|
| 404 MRI 不存在 | 使用系统病例 ID，核对已经上传 MRI |
| 409 需要当前成功模型分割 | 先完成真实四序列分割，参考 mask 上传不能代替 |
| 409 特征任务活动 | 等待当前任务完成，不重复提交 |
| 409 复现检查过期/失败 | 用同版本数据/模型运行 verify_feature_extraction.py，保留差异记录 |
| 503 工作器或兼容记录缺失 | 检查 RADIOMICS_PYTHON、RADIOMICS_COMPATIBILITY 和独立环境 |
| 422 年龄或性别 | 年龄用 0–120 整数，female 用 JSON 布尔值 |
| failed，输入/版本变化 | 查看本次 request.json/worker.log，核对新分割后重新提交 |
| failed，无可用选中特征 | 检查自动掩膜是否空或区域过小，不能伪造特征继续预测 |

配置可由 RADIOMICS_PYTHON、RADIOMICS_COMPATIBILITY、FEATURE_JOBS_DIR 覆盖，主模型/数据路径说明见 LOCAL_RUN.md。当前 Windows 本机自动特征功能已验证；Docker 中该独立工作器尚未接入，不能凭已有容器配置称其可用。
## 2026-10-09 病例临床输入更新

当前病例的自动掩膜特征使用病例卡内的研究年龄/性别，默认读取关联患者。上方“临床基线输入”是独立基线计算表单，不会改变病例输入。修改病例输入后先“保存病例研究输入”，会创建独立版本；患者原始年龄/性别不变。未保存修改隐藏旧概率，已保存的新版本使旧结果失效，需重新提取；历史任务文件保留。未知/other性别需要显式确认研究输入，系统不会当成男性。

GET/PUT `/research/cases/{case_id}/clinical-input` 读取/保存病例研究输入；POST `/research/cases/{case_id}/features` 可以不传临床body而使用已保存版本。旧客户端显式传age/female仍兼容，会保存为病例研究输入。任务记录来源、患者ID及临床输入版本，缓存包含该版本。

本轮演示副本病例17：患者原始56岁男性，研究覆盖57岁男性，用于验证输入变化；这是工程测试，不是患者资料纠正或研究结论。模型更换/不可用、临床版本变化时旧结果明确失效；请求失败清除旧概率，刷新可恢复。

