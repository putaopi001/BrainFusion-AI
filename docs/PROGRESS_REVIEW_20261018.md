## 2026-10-18 E5核心依赖锁增量

Docker core/full Python配置现分别固定28/44个CPython 3.10 Linux wheel哈希；完整配置含Torch 2.11.0+cpu、MONAI及研究包。Dockerfile采用core/full profile，Compose选full且两服务固定linux/amd64。Pillow Docker版为12.2.0，本机环境未改。定向11 passed，工作树与最终源码候选均694 passed、4条既有弃用警告。候选文件数、审计、ZIP SHA-256和当前白名单逐项一致性以机器报告为准。Docker/WSL运行仍待，E5未验；见E5验证文档及final5 candidate-regression.json。

## 2026-10-18 18:45 Docker基础镜像固定与交付候选更新

Python/Node/NGINX三阶段基础镜像已改为官方多架构清单SHA固定，并新增回归守卫（8项通过）。候选`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1837_docker_base_lock/candidate/`454文件，审计通过，SHA-256 `a73030c528e1ad2927ce8dc13d2270e2ae9f895e09de4981d6f29b0dd8205561`，解包全后端691 passed、4 warnings。容器未实际拉取/构建/运行，Python传递依赖闭包仍未固定；不能标为E5通过。具体摘要与平台子digest见`DOCKER_PREREQUISITES.md`及`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1837_docker_base_lock/base-image-digests.json`。

## 2026-10-18 18:34 当前服务完整性只读冒烟

修复后的常驻API对一份已存在、已验收的NIfTI模型分析执行只读检查：`/analysis`、病例详情、历史与分割状态均HTTP 200；当前分析未过期、历史标记当前、分割可用；4次请求未写业务数据，也未保存病例ID、结果值或路径。耗时约0.04、0.07、0.04及0.24秒。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T_integrity_live_readonly/validation.json`。这是当前NIfTI服务冒烟，不是新DICOM或四序列模型验收。

## 2026-10-18 文件完整性校验耗时测量

只读测量本机一个已验收模型分析所用的4个NIfTI输入与mask：共5个文件、20.28 MiB；首次顺序SHA-256为0.0178秒，第二次为0.0170秒，摘要重复一致。报告不保存病例ID或路径，见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T_integrity_hash_benchmark/validation.json`。这是一个本机NIfTI样本的文件读取性能量级，不代表更大DICOM病例、并发环境、Docker/Linux或医学效能验收；性能随盘、文件大小与缓存变化。尚无必要为少量重复哈希引入跨请求缓存，避免再次出现内容漂移漏检。

## 2026-10-18 文件完整性同元数据漂移修复

在分析/特征完整性接口中复现并修复：文件内容改动但字节数不变、修改时间恢复原值时，按路径/大小/mtime缓存摘要会漏掉漂移。`checked_digest`现每次读取文件内容计算SHA-256，再决定是否显示当前分析/特征；不重写已成功历史记录。新增同大小同mtime回归覆盖分析与特征API，隔离测试确认漂移后当前结果被隐藏、历史记录和状态文件保持不变。

验证：旧实现的定向复现按预期失败；修复后完整性定向13项通过；当前后端完整回归690 passed、0 failed、4条既有弃用警告。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T_integrity_hash_cache/`。每次核验会重新读取MRI/mask文件，换取内容级漂移识别；对大文件读时影响尚未在真实多序列数据或目标容器环境中实测。未改变正式病例、模型结果或业务数据库内容；本机前后端按原配置正常重启，Orthanc未重启。

## 2026-10-18 后续：分析历史请求独立与错误隔离

当前分析状态请求失败不再跳过历史读取；历史元数据可用时照常展示，并保留当前状态API错误提示。病例切换时，旧病例的迟到历史响应继续被丢弃。两个定向Edge场景通过；完整Edge回归8 passed/1个获准真实病例报告场景按设计跳过，生产构建通过；相同场景在当前5179服务上使用模拟API通过。日志见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1840_analysis_history_error_final/full-playwright.log`和`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1900_analysis_history_live_edge/playwright.log`。源码候选454/454与当前源码一致、数据库未变，ZIP SHA-256 `a3735d9f4c5b9e22221f4db4ee1820c8ee1377e6f29c347100271a28bd599322`，证据`E:/BrainFusion-Runtime/results/nightly/2026-10-18/analysis_history_error_final_v2/`。无真实病例读取或业务写入。

## 2026-10-18 真实分析历史页面只读冒烟

当前5179前端读取8012真实后端的只读Edge检查通过：既有病例页面HTTP 200、历史列表有1条记录、无页面异常和历史读取警告；验证仅保存计数/状态，不保存记录内容，不进行业务写入。证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/analysis_history_live_case_readonly_retry1/`。

# 2026-10-18 增量进度复核：网页四序列方案

## 2026-10-18 后续：分析历史在页面可见

分割分析页开始显示当前及历史任务列表；旧成功任务只以历史版本/状态/时间显示，不展示旧结果内容。模拟API Edge场景通过；完整Edge回归6 passed/1按设计跳过，Vite生产构建通过，现有5179前端服务模拟API冒烟通过。全部为工程/UI覆盖，未读取或改写业务病例。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1200_analysis_history_final/`。


## 2026-10-18 后续：激活后历史及旧报告可见性

激活接口隔离回归新增公开状态断言：原成功AnalysisRun保留但在历史API标为非当前，当前病例详情不再展示原分析/报告，旧报告API返回404，旧记录与旧MRI仍保留。整个`test_dicom_conversion_activation.py`为3 passed/4弃用警告，证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1010_activation_history_api/pytest.log`。仅合成/隔离机制验证，不是实际病例。


## 2026-10-18 后续：角色审核与激活 Edge 流程覆盖

新增 Playwright/Edge 合成API场景，覆盖版本四角色展示、本地医生登录、角色批准、绑定计划/角色摘要、批准前不激活、显式确认后提交激活及旧分析历史保留/未推理回执。单场景1 passed，日志见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T0900_role_review_e2e/playwright.log`。初次失败是选择隐藏复选框原始input，改为点击可见标签后通过。该场景仅验UI/请求契约，真实归档、账户和AI输入仍未触碰/验收；因此只提高M2工程路径覆盖，不改变M3数据门槛。README当前演示范围同步至10月18日。


## 2026-10-18 后续增量：转换材料恢复范围

M4恢复工具现在覆盖转换索引、网页方案草稿与原始DICOM采集副本、持久作业输入/状态和转换输出；备份逐文件核对SHA，恢复副本会重定位服务端路径及更新作业源清单哈希。若作业源清单引用恢复包之外的文件，备份会拒绝报成功。16项隔离恢复用例通过。

当前正式转换索引/方案/输出不存在，作业目录为空，因此没有真实转换材料可恢复或交付；本轮未停机创建空联合备份。M4仍待符合条件的真实材料出现后进行联合快照和独立恢复核验；真实四序列页面流程同样等待同检查合格数据，不使用合成资料替代。盘点及验证证据见`E:/BrainFusion-Runtime/results/nightly/2026-10-18/conversion_recovery/`。

---


本次把新建受控转换作业从CLI推进到病例页面。页面选择同一归档检查的四条不同Series并提交非患者识别的来源编号；预览阶段服务端读取元数据并验证现有模型几何契约。医生确认创建后，服务端重新验证病例关联和当前归档版本，按UID逐份取回原始DICOM，检查Part10内容与计划身份/几何，再创建持久排队作业；原字节路径与清单不回传。用户还需单独启动任务，之后仍须转换版本来源核对、角色审核和显式激活。角色信息是人工声明，不能视为AI识别、影像科医生实体认证或许可审查。

后端新增工作流定向用例和现有任务启动回归共16项通过、4条已有弃用警告；覆盖捕获SHA、幂等及失败清理、病例/用户/CSRF和拒绝客户端路径。Vite构建成功（沿用项目大chunk提醒）；Edge真实页面配合模拟接口走通四角色选择、预览及创建，0页面异常。常驻服务重启后新路由已加载，匿名访问401；backend/frontend PID 29080/20576，Orthanc 14640保持运行。更新前数据库备份，17表摘要和完整性重启前后相同。实际归档只读清点为1检查/1序列，AI桥接未开放。

因此当前增加的是可用的受控入口，不是DICOM→AI真实闭环。因为没有真实四序列，M1真实来源作业链仍待实际验收；M2生命周期关联与失效历史、M3真实模型输入、M4恢复/交付、E5容器/目标环境和带教预演均留在计划中。优先排期不变：当授权的真实四序列到位即走真实流程；等待期间推进新增转换材料的联合恢复/交付范围，并保持当前MRI和AI未被改变。本次未下载或使用Kaggle/E:/archive数据，未改自动化任务频率、未生成源码包、未做真实推理。

证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/web_conversion_plan/`。

---

# 项目检查与本轮推进：2026-10-18 12:49

系统仍在集成收尾，实际服务健康。本轮补齐“准备任务后从页面启动”的操作缺口，未宣称整个系统完成。

## 已完成

- 复用现有账本，CLI可只准备任务；页面可登录本地医生后启动，保留列表、轮询和失败重试。
- 启动绑定病例/尝试次数、准备输入摘要和当前归档关联；浏览器不能传服务器路径。
- 重复提交同一attempt只排一次；重试可排新attempt；切病例期间的旧登录/列表响应不触发错误操作。
- 路径过深等错误落为失败；未登记的转换不显示为已可审核。
- 修复持久CLI对旧体素核对统计输出的兼容性；加强测试子进程转换账本隔离。

## 验证与数据保护

应用整体672项通过，4条既有弃用警告；初次1失败671通过的日志保留，修复后整体通过。之后仅调整测试隔离，相关35项通过；不是把重叠测试相加。最终构建和Edge四项合成任务场景通过；真实既有NIfTI/DICOM只读检查通过，0业务写、0页面异常，不含真实四序列转换或推理。

本轮三条合成CLI测试作业曾写入默认任务目录，已证明属于本轮且未登记/未激活，原字节移入独立证据目录保留；新独立测试根及子进程继承已实测。业务库未因此改变。服务更新前另有SQLite快照；更新后17表逐行摘要一致，Orthanc PID 14640保持，后端/前端PID 18296/13252。新启动路由已加载，匿名请求401，实际真实转换作业仍0。

## 下一步

1. 网页直接选择四序列并创建来源方案仍未实现；当前创建/准备用受控CLI，网页负责启动与重试。
2. 当前PACS只有一检查一序列，须取得角色和空间符合要求的真实四序列，再做转换→审核→激活→模型→特征→复核/报告。
3. 新增转换任务/索引/外部产物及来源材料完整恢复、跨日稳定性、容器/异机和最终交付仍需验收；带教和预演等待稳定版本及本人参与。

未新打源码包、未改模型或应用定时设置。证据目录：E:/BrainFusion-Runtime/results/nightly/2026-10-18/user_next_step/；主要结果为regression-verification.json、isolated-tests.log、test-job-quarantine.json、live-verification.json、browser-final/validation.json及edge-readonly/validation.json。


## 2026-10-18 后续环境、回归及公开数据核查

本节覆盖上文较早快照中“网页仍不能创建四序列方案”的描述：该入口现已实现并完成页面模拟验收。

- 完整后端回归使用项目Runtime解释器和E盘隔离pytest目录通过：680 passed，4条框架弃用警告。M1/M2定向46项也通过。完整日志：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/full_backend_regression_final/pytest.log`；定向证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/m1_m2_integration/`。首次运行发现测试对子进程输出使用系统GBK解码会产生线程告警，已改为按字节捕获；聚焦2项通过，完整复跑后该告警消失。均为工程隔离用例，不是临床数据验收。
- 目标环境改以原生Windows本机为月底可交付范围：backend/frontend/Orthanc进程身份与监听端口一致，三个服务、PACS、账户状态健康。Docker CLI不存在，WSL未安装；普通安装入口无法在当前非管理员会话完成，且可能需要系统重启。本轮未提权、未重启。容器/异机标记仍未验收。证据：`E:/BrainFusion-Runtime/results/nightly/2026-10-18/environment_native/`。
- 数据首选筛选到TCIA UPENN-GBM：DICOM公开并为CC BY 4.0，全库约139.4 GB，队列描述有T1、T1-Gd、T2、T2-FLAIR；但官方元数据端点从本机请求超时/404，尚未验证单个StudyInstanceUID下四序列与几何。其配准NIfTI衍生物不与原DICOM空间对齐，不能代替DICOM来源验收。详见`PUBLIC_FOUR_SERIES_DATA_SCREEN_20261018.md`。

本轮没有下载、导入或改变正式病例、AI输入、转换产物或数据库；截止10月31日约余26–39小时（按用户每天2–3小时）。下一项依赖数据来源核验；其余冻结回归、真实材料恢复、熟悉项目和两次演练继续排在真实闭环之后。


