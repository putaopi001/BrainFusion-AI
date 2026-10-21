# 2026-10-17 紧急问题修复及验证

2026-10-17 11:17完成本批。修复缺依赖启动契约、后台进程与开发任务生命周期耦合，并新增只读真实状态检查；已恢复原服务和数据目录。没有下载数据、重训模型、改变业务库或放开DICOM-AI门槛。

## 1. 本轮开工的事实

10/16最后登记的后台25128、前端14984、Orthanc21924，以及只读监测22672均已不存在；三个端口无监听、HTTP连接被拒。电脑未重启；旧监测只有running的job.json，没有summary/退出事件，说明观测中断，不能据此编造历史退出时间、退出码或终止者。历史日志保留在本轮previous-logs/和previous-processes/previous-orthanc-process.json。

## 2. 修复缺pydicom仍能导入的旧契约

当前requirements-core已要求pydicom3.0.2，PACS受控导入启动时会加载它；旧测试还把它视为可选，因而上轮635项中有1失败。明确采用现有受支持环境的必需依赖契约：新增app/core/dependencies.py，app.main在数据库初始化之前、PACS路由加载服务之前检查，缺少时给出依赖名称和受支持环境/独立候选安装说明，不自动安装或升级主CUDA。

旧可选测试替换为真实子进程的两入口缺依赖拒绝及正常环境契约检查：人为阻断pydicom时，两个入口均明确失败，专有测试数据库不会创建；正常安装可载入转换路由且版本与requirements一致。没有skip、删除失败保护或把缺依赖当正常运行。

## 3. 修复后台启动生命周期

本轮在真实命令进程中查到Windows任务组的kill-on-close标志。普通子进程默认继承开发任务组；仅设置隐藏窗口/新进程组、或单独breakaway，不能证明已离开所有外层清理范围。受控复现可验证这一类清理路径，但此前每次退出的具体触发者仍无历史证据。

新增background_process.ps1与start_background_process.py：用同一用户的本地Windows进程创建服务启动隐藏bootstrap，再用结构化参数创建独立后台目标。保留当前环境、工作目录、标准输出/错误日志，并返回实际目标PID/100ns启动时间；现有复用/停止脚本继续校验该直接服务身份，不把短命bootstrap当服务。若正常创建被拒则报错，不提权、不创建定时任务/系统服务、不改PACS访问权限。启动回执不保存环境变量。

start_local、start_orthanc_local、start_frontend_only均使用相同函数。Orthanc参数由列表逐项传递，不再加旧Start-Process字符串所需的额外引号。Windows提供者本身仍可能有不带kill-on-close的正常任务组，因此不声称目标完全不在任何Windows任务组；本次修复的是与调用开发任务清理的关联。

实际自建kill-on-close测试组：在其中启动父脚本和普通子进程，同时通过新方式启动后台进程。关闭该测试组后父脚本和普通子进程结束，新后台目标仍活；中文/空格/引号/字面&/$()参数和内存传递环境保持一致，再用测试释放文件让目标自然退出。另验缺失可执行文件在创建日志/进程前拒绝。所有测试进程有期限并已结束。

参考：[Windows任务组](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)、[本地进程创建](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/create-method-in-class-win32-process)。未使用管理员权限或改变系统启动设置。

## 4. 新增只读状态入口

backend/tools/status_local.ps1核对三个服务的精确PID/启动时间、实际监听归属、后端根健康、页面、PACS状态和账户配置。健康退出0，缺项退出2；不启停服务、不修改业务库。它不会把旧JSON的running或PACS接口仅HTTP200误当实际可用。

## 5. 当前验证和服务

- 针对性18项通过；其中项目与生命周期用例包含在后续全套中，不加总成更多独立测试。
- 本轮后端全套639项通过，失败0，保留4项既有弃用警告；耗时184.23秒。完整输出full-tests.log/full-tests.xml。随后新增只读Python监测入口，另对实际0/23退出、到期不停目标及身份错拒绝四种行为单独验证，结果observer-validation.json，不累计为项目全套用例。
- 实际Edge六组浏览器回归通过：19病例列表详情、10无效路由、真实404、晚到旧响应、明确503夹具恢复、真实NIfTI和DICOM三视图与清理；业务写0/页面异常0/新增422为0。结果browser-after-accepted/validation.json，截图为真实页面，不代表新分割/临床评价。
- 服务已按原runtime八路径及默认PACS/账户配置恢复；精确身份和时间见services-final.json，PID按后台/前端/归档为19944/17580/12432。前端http://127.0.0.1:5179，API8012，归档8042仅本机鉴权；PACS ready、账户configured、复用核对通过。
- 正式17表全行/选定配置指纹/八路径在启动和全部回归前后一致，19病例/quick_check ok。没有切工程库、导入192、重算概率/特征或运行GPU。前端产品源码未改，没有重复构建。

## 6. 稳定性边界与下一步

新启动机制和任务组清理的受控复现已验；不能由短时测试断言所有历史退出都因此发生或跨夜稳定已通过。独立只读Python监测PID15108已启动，截止UTC 2026-10-17T09:17:10.678743Z，注册Runtime/local/service-observer.json，输出E:\BrainFusion-Runtime\results\nightly\2026-10-17\20261017_urgent_fixes\service-exits-independent。该监测不持开发锁、不重启目标，到期/全部退出即结束；下轮续读，不再沿用已消失的22672。实际前端单独重启首步因缺少已有规则要求的日志目录而拒绝，显式指定本run新日志目录后正常启动/复用；独立PowerShell监测未生成job且进程退出，未冒称运行，改用已验证的标准库Python监测。两个中间失败保留日志/请求回执，没有隐藏为通过，也没有修改权限/安全边界。

S0依赖失败已解决；S1启动机制已修、长期观察仍待完成；S2病例导航修复保留并本轮实际回归。下一步优先续读监测，推进当前配置/源码交付收尾和B1/B2角色/输入激活组件。真实四序列数据不足、P3真实端到端、Docker/新机器、研究队列扩充仍未完成，不宣称本轮全面完工。

用户抽查：①首页/病例管理正常打开；②/workstation/17?viewer=cornerstone三视图；③/case/19查询原检查/序列后DICOM三视图，不点保存。需要关闭系统时继续用项目原停止脚本，进程不再依赖开发聊天保持运行。

证据根：E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017_urgent_fixes。包含旧源字节备份、探测/目标测试、全部回归、状态/身份、正式库签名和有期限监测。本批不提交/推送、不改定时频率或私有应用配置。
