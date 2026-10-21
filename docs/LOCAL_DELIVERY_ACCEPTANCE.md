# 本地交付联合核验与安装边界

更新：2026-10-10 04:12窗口。E6交付核验小批次，不是新机器安装或容器验收。正式状态以SYSTEM_COMPLETION_CHECKLIST为准；工程论文图表素材已有独立验收，完整研究论文与R1–R4不属于本次核验结果。

## 2026-10-20 19:30只读交付预检快照

最终源码候选463/463与当前白名单源码一致，扫描0发现；后端全量回归695 passed。当前只读核验为passed_existing_workstation_only，SQLite数据库签名未变，14项实现源码和3项再现工具与工程材料匹配。证据：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T1930_final_closeout_candidate/readiness/。Docker/Linux Compose范围已有独立E5通过记录；此预检不代表真实四序列、干净新机或临床/模型效能验收。Orthanc须在Codex外安全启动后再复查PACS；合法数据人工隐私审核和用户独立演练仍待完成。本条是19:30候选快照；后续源码包版本以新的nightly证据为准。


## 可执行核验

backend/tools/verify_delivery_readiness.py使用当前运行解释器和显式runtime.json，核对：

- 源码候选ZIP外层/逐文件SHA、成员白名单与危险路径；不解压执行包内脚本，拒绝额外/重复/过大成员。对比当前源码，列新增/变化/移除，不将冻结历史候选称作当前源码。
- 工程材料ZIP/目录27项原始文件、材料清单、14项图示实现源码与3项重现工具SHA；不修改、重绘或重复截取已经验收的图像。
- CPU工作器source.json、现存cp311 Windows自建轮子、20Conda/10PyPI来源锁和三安装锁文本的一致性。LF/CRLF只在读取语义比较时统一，原文件不改、真实字节SHA记录；不重新下载、安装或提取。
- 实际启动前检：11项主依赖导入、分割权重/研究模型与既有特征门槛、CPU工作器导入、SQLite完整性和当前模型产物谱系。通过不导入app.main迁移、不运行推理/训练/特征提取。
- 数据库所有表的只读内容签名在核验前后相同，queued/running分析或特征存在则停止；不输出患者行原值。当前源码在结束时再次核对SHA，防止检查过程中换版本。

仅写全新E盘证据目录。先取得统一FileShare.None开发锁、核对任务/服务身份；工具不接管服务或抢占其他执行者。调用示例（使用真实已登记配置，不切回旧Demo库）：

```powershell
cd E:/BrainFusion-AI
. ./backend/tools/use_e_drive.ps1
./backend/tools/start_local.ps1 -ReuseExisting -RuntimeConfig E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T010640_a6ee8135/runtime-supported.json -BackendPort 8012 -FrontendPort 5179
./.conda/brainfusion/python.exe -B ./backend/tools/verify_delivery_readiness.py --runtime-config E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T010640_a6ee8135/runtime-supported.json --source-candidate <已验源码候选目录> --materials E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T030942_d136a5d2 --worker-locks E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T010640_a6ee8135/dependency-locks-complete --output <不存在的E盘nightly目录>
```

成功状态特意使用`passed_existing_workstation_only`。`source_candidate_vs_current.is_current`才说明该候选与本次完整允许源码一致；`database_unchanged`与`preflight.status=passed`只说明本机已有环境和数据当前可用，不保证异机安装、长期依赖维护或临床有效性。failure.json/标准输出/错误日志保留失败，不覆盖输出目录。

## 交付组成与迁移顺序

1. 源码候选：源码/前端依赖解析/操作说明，须逐文件验证；不含患者库、MRI、模型、Python环境、node_modules或内部反馈。02:07候选是历史版本；新增工具后的候选须另命名生成，旧包不覆盖。源码打包不等于再分发许可或公开发布授权。
2. 应用数据：依SYSTEM_BACKUP_RESTORE先备份，再在隔离副本恢复数据库、引用MRI/模型/成功产物和新runtime.json。已验638原件恢复可复用证据，不每轮复制一次；全研究MRI队列不属于该应用快照。恢复后不把历史失效记录当当前成功结果。
3. 主运行环境：当前Python3.10.21、torch2.11.0+cu128/MONAI1.5.2等53安装包在ENVIRONMENT_INVENTORY有观测快照；原始安装URL/发行文件SHA不全，明确未知。requirements-local-validated只列直接依赖摘要，不是传递哈希锁；不得照历史requirements.txt全量升级CUDA主环境。新主环境必须独立官方来源候选、冻结版本与实际模型/研究回归后切换；本轮未安装新候选，也不声称完成可离线异机部署。
4. CPU特征环境：按RADIOMICS_ENVIRONMENT_MIGRATION精确来源锁及本机自建轮子复建全新环境；新路径/依赖须重验同协议参考门槛、自动任务、缓存与重启。不盲复制旧source.json作为新环境来源，不编辑compatibility.json绕过验证。Windows cp311轮子不能用于Linux容器。
5. 前端与启动：当前解包验证复用既有E盘主Python及前端依赖，明确不是新安装；正常新机需合法取得对应依赖。使用LOCAL_RUN同一显式配置，启动前检/端口健康通过才报成功；不重复启动第二后端、分割或特征执行器。
6. 工程材料：THESIS_ENGINEERING_MATERIALS的PDF/SVG/PNG/原始UI截图及图注，材料包与运行源码互相绑定；不包含依赖安装环境、MRI或完整研究统计。完整研究论文结论待R1–R4证据后写。

状态更新（2026-10-20）：E5 Docker/Linux 已完成本机 Linux full 镜像、Compose/Orthanc 元数据联通、只读挂载和重建持久性验收，见 E5_DOCKER_RUNTIME_VALIDATION_20261020.md。此处交付预检仍只覆盖现有 Windows 工作站，不是新机器安装或真实四序列验收；普通交互 PowerShell 原生常驻启动仍待单独验证。

