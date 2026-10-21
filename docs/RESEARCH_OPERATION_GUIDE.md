# IDH 与融合研究操作指南

更新：2026-10-10。旧指标/三轮联邦仍为探索原型，不是本轮新实验；22人已观察测试身份不变。数据范围见STAGE_4_VALIDATION，当前部署/输入/原IDH编码限制见FIXED_DEMO_GUIDE与RELEASE_SCOPE。

2026-10-07 新增当前病例自动掩膜特征卡及分割完成页入口，见 AUTOMATIC_FEATURE_OPERATION_GUIDE.md。以下五例源患者接口仍使用参考特征；自动病例接口是 /research/cases/{病例ID}/features，两种输入分别记录。

## 使用已保存模型

PowerShell：

```powershell
cd E:/BrainFusion-AI
./backend/tools/start_local.ps1 -ReuseExisting -RuntimeConfig E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T010640_a6ee8135/runtime-supported.json -BackendPort 8012 -FrontendPort 5179
```

若服务已在运行，直接访问 http://127.0.0.1:5179/research 。脚本会拒绝端口冲突或另一个登记的活动后端；不要同时启动共享数据库的服务。

1. 左侧点击“IDH 与融合研究”。顶部表格显示当前实验版本、队列人数及单模态/融合指标。
2. 在“开发样本”选择数据集患者 4、13、16、17、19，系统读取已下载特征并加载实际保存模型计算概率。这里输入的是源数据 ID，与病例系统的病例 ID 不同。
3. 比较临床、参考掩膜影像组学、平均、固定、TOPSIS 五个结果。概率目标为 IDH1/2=1；这些数值未经校准，不能用于诊断。
4. 临床基线表单输入年龄 0–120 及 male/female，点击“计算临床概率”。只有临床分支使用这些输入；不会修改源数据或病例信息。
5. 页面下方查看集中式与 IID/Non-IID 联邦结果、客户端人数及末轮聚合权重。全部轮次记录在 summary.json。

数据集患者 19 缺少参考 IDH 标签，但有可用输入，因此可以验证推理，不能判断其分类对错。缺失标签不会被填成 0。

## 重跑轻量实验

本机依赖已安装，不必重新安装或下载。需要生成新研究版本时执行：

```powershell
cd E:/BrainFusion-AI/backend
. ./tools/use_e_drive.ps1
../.conda/brainfusion/python.exe tools/run_research_smoke.py --rounds 3 --local-steps 2
if ($LASTEXITCODE -ne 0) { throw 'Research experiment failed' }
../.conda/brainfusion/python.exe tools/verify_research_workflow.py
```

每次生成新的 UTC 时间+随机后缀目录；既有版本保留。先验证模型重载，再原子更新 latest.json。默认数据目录 E:/BrainFusion-Data/WAW-GliomAI-v3，输出 E:/BrainFusion-Runtime/results/research。脚本允许 1–10 轮和每轮 1–10 步；这是功能验证保护，不用于完整训练。

第一次划分文件已冻结。若更换 CSV 或患者名单，脚本拒绝沿用旧划分；先编写新协议、使用独立输出目录。不要为绕过检查直接删除当前划分或根据测试结果调参。已有测试拆分属于探索性，新增版本不会自动获得独立测试资格。

## API 与产物

| 操作 | 接口 | 说明 |
|---|---|---|
| 查看实验 | GET /research/summary | 当前成功版本及验证/探索性指标 |
| 五例推理 | GET /research/patients/13 | 仅五个源患者 ID，实际模型重算 |
| 临床输入 | POST /research/clinical | JSON 例如 {"age":50,"female":false} |

接口文档 http://127.0.0.1:8012/docs 。summary.json 含拆分、指标、模型哈希、每轮权重与限制；models.joblib 含两个 Pipeline、联邦预处理器和参数；predictions.csv 含 22 名探索性测试患者的分支和融合概率。模型文件只能来自本地实验，不接受用户上传 pickle/joblib。

查看全部联邦轮次：

```powershell
$pointer = Get-Content E:/BrainFusion-Runtime/results/research/latest.json -Raw | ConvertFrom-Json
$summary = Get-Content "E:/BrainFusion-Runtime/results/research/$($pointer.run_id)/summary.json" -Raw | ConvertFrom-Json
$summary.federated.methods.label_skew_validation_topsis.round_trace | ConvertTo-Json -Depth 8
```

## 浏览器与重启验收

```powershell
cd E:/BrainFusion-AI/frontend
. ../backend/tools/use_e_drive.ps1
$env:BRAINFUSION_WEB_URL = 'http://127.0.0.1:5179'
node tools/verify_research_browser.mjs
```

脚本依次选择五例、核对显示概率、提交临床表单，保存 stage4/browser_validation.json 和截图。它读取研究数据，不修改源 CSV。

关闭并重启，再检验保存结果：

```powershell
cd E:/BrainFusion-AI
./backend/tools/stop_local.ps1
./backend/tools/start_local.ps1 -Demo -BackendPort 8012 -FrontendPort 5179
cd backend
. ./tools/use_e_drive.ps1
../.conda/brainfusion/python.exe tools/verify_saved_results.py --api-base http://127.0.0.1:8012
```

保存结果验证还需要 stage2 工程数据库与 stage4/api_validation.json。只检查读取与结果一致性，不重新分割或训练。

## 常见错误

| 现象 | 处理 |
|---|---|
| 503 研究产物不可用 | 检查 RESEARCH_DIR、latest.json 和依赖；运行轻量实验后验证 |
| 409 校验或版本不一致 | 保护原产物，核对 SHA256、CSV 与模型版本；不要直接修改摘要绕过检查 |
| 404 患者 ID | 只接受五个开发源 ID，不能输入系统病例编号 |
| 422 年龄输入 | 使用 0–120 的整数，female 使用 JSON 布尔值 |
| TOPSIS 只有一个分支权重非零 | 当前验证结果导致的正常退化，原样保留；不是代码故障 |
| 研究概率没有出现在病例报告 | 已验证自动掩膜特征的工程迁移，模型仍在参考特征上拟合，尚无同协议重拟合/独立评价；病例报告显示分割 |

整个功能基于 CPU 轻量模型；不要为了运行研究页面升级现有 CUDA torch。新环境的最小依赖见 requirements-core.txt 和 requirements-research.txt，安装前必须先运行 use_e_drive.ps1。
