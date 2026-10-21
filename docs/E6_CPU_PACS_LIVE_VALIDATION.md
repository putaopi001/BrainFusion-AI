# E6 当前CPU/PACS HTTP运行组合验收

2026-10-16 08:13接续，run_id `20261016T081638_cpulive`。当前本机直接CPU解释器+固定pydicom补充目录的HTTP/Edge/服务复用/重启/停机/回原子项已验；不把它称为独立新机或容器安装，P3匹配真实四序列仍受阻。

## 实施

新增`validate_pacs_runtime_layer.py`只接受已登记小型环境的固定pydicom3.0.2目录。基础CPU解释器/receipt须与原记录SHA相同、52包元信息吻合；固定官方缓存轮子大小/SHA吻合后，实际比较全部293个补充文件。包代码/元数据与原轮子逐字节比较，pip生成的RECORD/安装标记按明确边界处理；额外包、.pth、pyc、缺文件、重解析目录或同大小改写均拒绝。它不接受任意PYTHONPATH，不升级或覆盖原CPU/CUDA/特征环境。

现有start_local新增显式`-PacsRuntimeLayer`：使用直接CPU基解释器，临时为子进程设置仅含已验pydicom目录的PYTHONPATH，调用结束恢复调用者原变量。原venv Scripts/python重定向入口仍拒绝，未弱化上一轮保护；直接进程探针PID和实际新服务监听归属均核对。登记补充目录/内容指纹，复用时必须同样声明；缺声明实际拒绝且登记/PID不变。默认CUDA入口仍可启动和复用。stop_local沿用PID+启动时间身份检查，实际CPU停止后同步等待退出，未用手工第二后端绕过门槛。

调用须在有限同步工作脚本内，先核服务/输入/目标/配置基线，不直接对当前占用端口再起服务。示例仅描述候选组合，**本轮已回正式CUDA，不能照抄在原端口同时启动**：

```powershell
./backend/tools/start_local.ps1 -PythonPath E:/BrainFusion-Runtime/envs/runtime311-cpu-delivery-20261010T060619_ce64597d/python.exe -PacsRuntimeLayer E:/BrainFusion-Runtime/envs/runtime311-pacs-20261016T071748_cpupacs -RuntimeConfig <已验恢复副本/application/runtime.json> -BackendPort 8012 -FrontendPort 5179
# 已登记同一CPU组合才可按相同参数增加 -ReuseExisting。
```

另须显式配置恢复副本的PACS_CONFIG_FILE、PACS_IMPORT_REGISTRY_FILE、PACS_IMPORT_JOBS_DIR、LOCAL_AUTH_FILE。空环境变量不等于缺省配置，正常回原须恢复八运行路径和这四项。不能把工程恢复副本当正式默认库。

## 本轮实际结果

- 五项有行为的补充目录边界检查通过：固定字节/同大小篡改、额外.pth、pyc、其他模块、缺失文件。实际官方3.0.2文件与直接进程探针通过，未安装或下载任何依赖，也没新建prefix。
- 复用05:18已经恢复的19病例/17表数据与模型/产物/账户/导入记录，只启动一套CPU后端/前端；**Orthanc仍为原本机归档、PID28324持续运行**。本轮不称恢复归档新启/重启，也不再复制650文件/重新导入192；归档完整独立恢复证据沿用05:18窗口。
- Edge155.0.4283.45 headless真实HTTP两次通过：首次CPU启动与实际停止/重新启动后，NIfTI17恢复T1n/原mask隐藏/三相机和窗值，真实DICOM19三视图192帧/192×256×192、36条既有毫米距离/视图相同；19病例身份、代表NIfTI临床/原分析/报告/特征科学API经明确路径规范化一致。读取已有真实模型产物，不是本轮新CPU推理或重提特征。
- 恢复账户实际登录/固定署名，两次均未新增复核；原7条历史/actor及内容/导出SHA保持。首次活Cookie只保存私有backups目录，重启后真实失效，重新登录/退出正常。浏览器只允许登录/退出POST，业务写0、页面异常0。
- 正确声明补充目录的ReuseExisting实际成功，漏声明实际拒绝且登记未改；CPU服务OS PID直接持有对应端口。两次正常停止均验证退出；finally恢复原主CUDA解释器/八路径/四配置，PACS ready/账户configured。
- 正式17表与恢复副本17表所有行签名均不变，恢复7复核保持；原PACS/账户/登记配置、原Orthanc进程登记SHA保持。补充目录内容指纹前后相同，原基环境仍只读。全流程86.582秒包括停机/前检/首次浏览器/重启/回原，不能当AI、导入或纯加载性能。

六张NIfTI/DICOM/本地账户截图已逐图查看，重启前后相同；DICOM当前切面不必经过全部36条距离，36条由DOM/API和旧行签名核对。账户图只证明本机角色登录，不核医师资质。没有新PDF、可见人工窗口或所有工具重验，不把接口通过冒充浏览器通过。

当前正式后台32944/UTC2026-10-16T00:22:49.6178419Z，前端26632/UTC2026-10-16T00:22:49.6240322Z，原Orthanc28324/UTC2026-10-15T21:26:16.1338304Z。地址http://127.0.0.1:5179/case/19 与workstation/17?viewer=cornerstone，API8012/归档8042仅本机鉴权。日志Runtime/local/backend/frontend out/err和原orthanc-local/logs/20261015T212616131Z。CPU候选已停止，无下载/训练/推理/提取或构建长任务。

## 证据与下一步

本轮根`E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T081638_cpulive/`：layer-tests/layer-before-live/layer-after-live、CPU首次/重启服务登记与reuse/漏声明拒绝、两个cpu-browser-*/validation和六PNG、原科学API/CPU报告快照、data-baseline/data-final-preservation、live-timing/final-services、visual-review、源码增量及summary。私有活Cookie只在Runtime/backups/20261016T081638_cpulive/browser-state.json，不进入公共源码/日志。

源码继续使用06:15冻结402 ZIP+07:16的8文件增量作为前版；本轮只保存进一步源码增量和逐文件组合校验，不重新整包打包。启动脚本/新增验证工具/操作说明是当前增量，旧ZIP本身不会凭文档变成当前代码。环境、数据/模型/账户/缓存及Orthanc/浏览器二进制仍是明确外部前提。

E6/P4的这个本机运行组合已验；当前受支持NIfTI/PACS已有证据，但P3真实匹配四序列、E5正常系统授权/容器、异机/可见人工抽查与完整研究R项仍未全完。新增源代码组合与既有环境/私有数据的角色须保持可追溯，不能因局部通过称整系统或独立临床评价完成。普通单序列阅片不额外要求IDH标签/四序列。

抽查最多三步：①打开本轮两个cpu-browser验证和六截图，确认是实际CPU首启/重启、0业务写；②当前Edge访问上述正式两页只读查询/切序列，原库不应出现工程36距离/7复核；③核data-final-preservation及final-services，已回原八路径/CUDA，Orthanc未重启。不要把停止的工程副本切正式。

下一步先固定当前源码增量/启动配方和原交付组成；上述实际本机门槛已通过后不再循环测试或复制。P3/E5无新解除条件时继续保留一次阻塞，转可独立的R2熵权融合工程（先读冻结协议与现有融合实现，只在允许训练/验证信息拟合，不改展示/论文结论）。异机/人工/真实四序列条件另列，不因外部等待停下独立实现。
