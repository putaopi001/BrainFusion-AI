# 独立 Windows CPU 主环境候选

2026-10-10 05:08窗口，E6本机独立CPU安装、模型、副本恢复、实际服务启动/重启/浏览器及CUDA回退已验收；不是默认环境永久切换、新机器安装或Docker验收。证据根：`E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T050838_9f671276`。

最终服务试运行证据`live-final-validation.json`：先SQLite backup与任务副本，再实际CPU首启4576/12800、重启33500/26376，首启/重启/回退各10接口与原/副本全表内容一致；18任务文件原/副本SHA相同。首启四页只读截图、重启后四序列/三视图叠加/研究/报告/未知临床共11截图实看通过。未新提特征/病例PDF或重训练。已核验停止CPU服务并恢复旧CUDA主环境及01:06原配置，CUDA可用；现用后端31840/startUTC2026-10-09T21:30:04.2527517Z、前端17736/21:30:04.2595763Z，实际5179/8012。下方安装门槛/TestClient记录是同轮试运行前的验收层次，不替代最终服务身份。


## 2026-10-17 S3依赖增量

原52项CPU候选快照保持历史不变。基于当前requirements-core要求，在已验证的runtime311-cpu-candidate中追加唯一包pydicom 3.0.2；使用E盘缓存wheel，SHA-256与PyPI官方发布一致（见来源链接及本轮cpu-pydicom-increment.json）。前后pip inventory仅pydicom新增，pip check与当前app.main/PACS激活路由导入通过。未改变torch CPU构建、CUDA主环境、特征工作器、活服务登记或固定模型/协议。首次当前源码导入误对工作区backend/brainfusion.db执行了幂等schema迁移，事后只读计数15病例/12 MRI/6分析，迁移后快照见20261017T1253_s3isolation；无预迁移副本，不回滚。活服务登记库路径不同，未触碰。第二次导入已显式改用新隔离库。该候选仍是本机既有环境增量，不代表异机/容器或干净prefix重建验收。
## 环境角色与边界

| 角色 | 解释器与实测版本 | 当前用途 |
|---|---|---|
| 现用主环境 | E:/BrainFusion-AI/.conda/brainfusion/python.exe；3.10.21、torch2.11.0+cu128 | 演示后端，CUDA仍保留可用；53包没有升级 |
| 新CPU主候选 | E:/BrainFusion-Runtime/envs/runtime311-cpu-candidate/python.exe；3.11.17、torch2.11.0+cpu、torchvision0.26.0+cpu | 独立安装/模型/副本恢复及实际CPU服务重启、浏览器通过；演示已回退CUDA |
| 现用CPU特征工作器 | E:/BrainFusion-Runtime/envs/radiomics311-candidate/python.exe；3.11.17、PyRadiomics v3.1.0 | 沿用01:06验收的来源与同协议门槛，不在本轮重新提取 |

主候选固定MONAI1.5.2、NumPy2.2.6、SimpleITK2.5.6、scikit-learn1.7.2、joblib1.6.0；特征工作器仍NumPy1.26.4、SimpleITK2.5.2，两者不能混装。未使用的torchaudio明确排除，不暗示音频能力。CPU主候选不能运行CUDA；不移除现用CUDA环境、不修改分割/提取/分类协议，不把IDH研究概率改成风险或治疗建议。

## 来源、容量及安装规则

`cpu-plan/plan.json`冻结完整52项Python包及标记条件下的传递依赖，缺项0；兼容目标cp311/Windows x64。52官方轮子234,201,976字节，解释器20项Conda引导文件37,182,372字节，总文件量271,384,348字节；含可复用缓存，不等同网络流量计量，安装占用另需空间。实际轮子/Conda缓存均按发布SHA与大小核验。PyPI下载仅files.pythonhosted.org，CPU torch/vision使用download.pytorch.org原站已核验链接，不重试已403的CDN；解释器沿用已核验conda-forge精确20文件锁。

Conda缓存E:/BrainFusion-Runtime/cache/conda；轮子缓存E:/BrainFusion-Runtime/cache/runtime311-cpu/wheels；解释器、临时目录与日志均E盘。C盘Conda用户登记文件SHA前后相同。新候选52项实际安装元信息与计划完全相同，pip check通过。Conda先引导pip/setuptools/wheel等，随后pip锁覆盖；初次50项pip报告另有同版本pip/packaging未重装，已在候选中用SHA锁轮子强制替换，最终报告是`cpu-install/pip-install-report.json`加`bootstrap-pip-install-report.json`共52项。最终`candidate-source.json`如实记录这两份来源；未来工具安装默认force-reinstall避免该遗漏。原CUDA环境历史安装URL/SHA仍不全，不能用新候选来源补写历史。

项目工具`backend/tools/prepare_cpu_runtime_candidate.py`提供plan/download/install三阶段。输出目录必须在nightly下且全新；安装prefix必须是E:/BrainFusion-Runtime/envs/runtime311-cpu-candidate开头的不存在目录。不会覆盖环境；失败保留.part/日志，续传下载先验证，不能反复在部分安装prefix盲目重装。读取可信本地冻结计划；不执行数据集脚本，来源许可元信息记录不等于第三方再分发许可审查。

本机重建使用已有来源计划和精确解释器锁，选新的prefix与证据目录，不能照抄当前已存在路径重复安装：

```powershell
Set-Location E:/BrainFusion-AI
. ./backend/tools/use_e_drive.ps1
$cpuEvidence = 'E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T050838_9f671276'
# 本机缓存仍在时无需重新下载；重建输出/prefix必须全新。
./.conda/brainfusion/python.exe -B ./backend/tools/prepare_cpu_runtime_candidate.py install --plan "$cpuEvidence/cpu-plan/plan.json" --downloads "$cpuEvidence/cpu-download/validation.json" --prefix E:/BrainFusion-Runtime/envs/runtime311-cpu-candidate-rebuild --output "$cpuEvidence/cpu-rebuild"
```

依赖E盘已配置Conda及可信启动解释器、原计划/元信息/缓存，并非新机一键安装配方。跨机器须补工具引导与来源文件迁移，重新验证，不复用本机路径冒称已验。

## 本轮实际验收

- 主/候选后端各92项通过，4项既有弃用警告；核心11项、研究5项清单匹配，旧UTF16全表仍不是安装配方。
- 候选真实启动前检：11依赖导入、模型SHA与研究版本、现用特征工作器和谱系、SQLite检查通过；读取前后原库内容签名一致。
- 预先冻结cpu-migration-contract.md：真实WAW4工程病例17，同四MRI/权重/ROI128×128×96/非零z归一化，OMP/MKL4线程；旧主环境强制CPU后新候选CPU串行，独立输出，不使用参考mask输入或改病例分割。两环境各自GPU分配0、mask240×240×155、逐体素差异0、affine/qform/sform一致；标签1/2/3体素3366/2910/8。日志MONAI多维索引警告保留，固定版本结果通过，不静默升级协议。
- 五开发样本各五概率，新旧最大绝对差0；只验证同模型工程重现，不是新的科学效果统计，也不恢复独立测试身份。
- 数据库和特征任务先复制到本轮副本，再用两次全新候选进程的TestClient执行启动恢复；10个病例/分析/临床/任务/报告/标注/四序列接口返回完全一致，副本库与原库内容均不变。没有第二网络后端，不代替实际浏览器与服务重启验收。
- start_local新增可选PythonPath。默认仍现用主环境；实际default复用通过、请求候选复用现用后端按解释器不符拒绝、缺解释器拒绝，服务登记SHA及PID/start不变。`-ReuseExisting`不会切环境。

最终证据以`final-validation.json`、`candidate-inventory-complete`、`*-backend-suite-complete.log`、`cpu-model-comparison.json`、`candidate-recovery-validation.json`、`launcher-validation.json`为准。初次来源断言失败和补装日志保留，不以中间记录替代最终来源验收。旧04:12源码ZIP是225文件冻结历史，新增工具/指南后不再是当前源码，不覆盖或重新称为当前。

## 实际CPU服务试运行与回退流程（本轮已完成）

以下是试运行前冻结的安全流程，本轮已完成，最终结果见文首与live-final-validation；后续不得再次照搬已存在证据目录重复验收。先统一开发锁，核对服务PID/start与无活动分析/特征；先备份库和任务，使用已验副本配置。用stop_local核验停止当前登记服务，再由start_local显式指定候选，仅保留一个后端/一个前端以及各一个串行工作器。

```powershell
# 仅在独占锁、完整备份、无活动任务及受控试运行准备后执行。
./backend/tools/start_local.ps1 -RuntimeConfig E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T050838_9f671276/live-cpu-trial/runtime-cpu-trial.json -PythonPath E:/BrainFusion-Runtime/envs/runtime311-cpu-candidate/python.exe -BackendPort 8012 -FrontendPort 5179
```

运行中的端口会拒绝启动，不会自行停止或覆盖。上例只示解释器参数；实际试运行须换新副本配置，不直接沿用现用库做迁移验证。试运行后检查四序列、研究输入/版本/概率、复核/报告，刷新和实际重启；失败保留证据，核验停止候选后用旧主解释器与此前配置恢复，不删新旧环境或成功产物。

下一批可独立完成CPU源码/来源锁迁移包与隔离目录引导验证（同机不称异机）。Linux容器CPU、容器重建持久化仍归E5，需管理员WSL/Docker/可能重启窗口；未授权窗口不绕过或反复安装。完整E6仍进行中，第一阶段未全部完成，R研究结论不变。
