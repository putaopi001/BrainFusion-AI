# 独立特征工作器引导与交付组成

2026-10-10 08:11窗口，run_id20261010T081105_95f1c109。E6新增标准库/可信E盘Conda→新CPython3.11.17→新prefix自身pip离线引导，不借工程旧pip。默认安装不读取原工作器/原机器来源文件；冻结profile准备和可选compare-accepted才需要已验来源机器。不是异机、容器或现用服务切换验收。

## 组成边界

| 组成 | 已验来源/能力 | 尚需另行提供或验证 |
|---|---|---|
| CPU主后端/分割 | CPU_DELIVERY_BOOTSTRAP，52官方wheel/20Conda锁、05:08真实服务/模型工程对照、06:06独立引导 | 不含Node/特征worker；不能将主NumPy2.2.6混入特征协议 |
| 前端 | FRONTEND_DELIVERY，Node24.21.0/固定422锁及396实际包、API8012构建/HTTP重启 | Node/npm、来源候选、后端与数据是独立组成 |
| 特征worker | 本指南，20Conda/11安装wheel、15元信息/pip check、1102导入payload/两解释器二进制匹配 | 不是主Python/CUDA；新source身份/科学门槛/服务切换尚未验 |
| 数据/模型/结果 | SYSTEM_BACKUP_RESTORE，独立副本/路径重定位/重启已验 | 需合法持有/校验另行恢复，不能携入源码ZIP或删除原件 |
| 科学门槛 | 已验五参考/病例17仍绑定现用source.json | 安装匹配不自动获得新来源部署门槛，不复制旧source.json冒充 |

默认服务仍CUDA主3.10/53包、现用radiomics311-candidate和01:06兼容门槛；backend31840/frontend8912，http://127.0.0.1:5179 和 http://127.0.0.1:8012/docs。不改runtime.json、缓存键、临床输入、协议、旧来源或结果，不起第二服务/活跃特征任务。

## 两阶段操作

准备阶段在已验来源机器使用prepare_radiomics_delivery.py，传source.json可信SHA、dependency-locks-complete和passed/source指纹一致gate。20Conda/10PyPI源锁与自建wheel核验；按大小+发布SHA找E盘HTTP缓存，不猜URL或下载。9官方wheel复用；docopt0.6.2 SDist SHA、缓存wheel origin.json和docopt.py与SDist模块字节相同，未执行setup。PyRadiomics复用已验原源码CP311 Windows编译wheel，明确非上游官方二进制。11wheel内1102导入payload与原已安装文件一致后冻结profile。

```powershell
# 输出必须全新nightly目录，来源SHA以原始已验记录为准。
E:/Anaconda3/python.exe -B E:/BrainFusion-AI/backend/tools/prepare_radiomics_delivery.py --source E:/BrainFusion-Runtime/envs/radiomics311-candidate/source.json --expected-source-sha256 b729caa5734117a943a6d37e5054ea593349325612c13589ad52a44958d3d429 --dependency-locks E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T010640_a6ee8135/dependency-locks-complete --gate E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T010640_a6ee8135/candidate-reference-gate-complete/compatibility.json --output <全新E盘nightly目录>
```

安装阶段只需可信profile/外部可信SHA、可信E盘Conda和31份实际SHA缓存（20Conda+11wheel）。旧路径只是溯源，不是安装前提；可选--compare-accepted在本机额外核对原来源。缺缓存/损坏/profile不可信/已存在prefix在创建输出/环境前拒绝，不对partial prefix重试、删除或覆盖。缓存按照冻结profile提供，只支持Windows x64 CPython3.11.17，不静默替换Linux/镜像。入口需要backend/tools/bootstrap_radiomics_delivery.py与同目录bootstrap_cpu_delivery.py（仅标准库）。

```powershell
E:/Anaconda3/python.exe -B E:/BrainFusion-AI/backend/tools/bootstrap_radiomics_delivery.py --profile <可信worker-source-profile.json> --expected-profile-sha256 bcfe4fc9ae59e38f963361e685018338d1c3537e364d8db7883d033c20bee83c --output <全新E盘nightly目录> --install-prefix E:/BrainFusion-Runtime/envs/radiomics311-delivery-demo
```

Conda --offline/显式本地SHA/不登记C盘；新prefix自身pip --no-index/--no-deps/--no-compile/--require-hashes及pip check。实际报告11SHA、15元信息/核心版本、1102导入payload和python.exe/python311.dll须符合冻结profile。pip生成的RECORD/launcher/来源路径不冒称相同，不宣称整个环境文件逐字节一致。原生PID/启动时间/命令/日志/状态记录；TEMP/TMP/Conda/pip缓存和证据均E盘，不改系统/global PATH。

## 本轮证据与限制

初版prefix radiomics311-delivery-20261010T081105_95f1c109重建通过后，发现默认验证仍隐式依赖原worker存续；冻结payload独立验证改造后在全新radiomics311-delivery-20261010T081105_95f1c109-independent实际重建。第二次是前提变化后的验收，不在同目录重复安装；原证据保留。来源路径不可用的profile派生副本仍可验证，发行/来源SHA和payload保持，实际独立解包入口验证不借原项目模块。原source/gate未变、新source不同，不伪装原身份。

最终120后端/4既有警告、独立CPU解释器10行为通过；坏profile SHA/自己的wheel缓存实际CLI在输出/prefix创建前拒绝。20Conda+11wheel文件总量77440693字节不是传输量，全部缓存复用/无新下载。10份官方原发行（9wheel+docopt SDist）和2本地构建wheel（docopt/PyRadiomics）分开；缓存历史下载URL未知处不编造，许可在原来源/包/dist-info，哈希不等于签名、漏洞/供应链/再分发认证。

初版ruamel.yaml点号名称规范遗漏已修正并另建profile。Windows CPython3.10规范化ZipInfo.filename导致恶意反斜线夹具两次失败，读取标准库实现后改查orig_filename，原始路径防护/120测试通过，不放宽校验。未重跑55/252、推理/特征/病例PDF/训练/科研结论，无UI变化或新截图；07:05构建页是历史证据。

状态passed_offline_independent_worker_bootstrap_not_live_gate_or_new_machine仅安装/字节一致性。新candidate source.json尚无绑定科学门槛，不改现用RADIOMICS_PYTHON或冒用旧gate。下一批核对新来源门槛与隔离服务回归；按影响选择实际复验，不盲重跑旧实验。E5管理员WSL/可能重启窗口、Linux CPU/容器持久化重建，异机引导/缓存/合法模型数据恢复均未实测；E6仍进行中，第一阶段未完整交付。
