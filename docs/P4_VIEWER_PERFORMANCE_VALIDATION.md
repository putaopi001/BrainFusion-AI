# P4 真实NIfTI / DICOM分层阅片性能观测

2026-10-16 04:13窗口，run_id `20261016T041517_viewperf`，属于10/15晚至10/16凌晨。实际开工UTC20:13:22.0948202Z，04:15创建证据目录。本批补的是已装Edge、真实DICOM查询/完整帧载入与Windows进程内存；10/13已有NIfTI/Chromium缓存及JS堆观察保留为历史，不把两种浏览器/计时终点不同的结果作为优化前后对照。

## 方法和边界

已装Edge 155.0.4283.45 headless，1600×1100，每种来源各启动一个全新浏览器进程/上下文、禁HTTP缓存，后端和OS/文件缓存不清。不是操作系统冷缓存，也不是生产构建：当前Vite开发服务启动/模块加载在初次阅片时间内。每种来源1病例/1次初载，切片各3次；这些是有限工程观测，不估计p95、吞吐、统计置信区间或临床队列性能。

首次加载：Node单调时钟从导航到当前来源ready、3张canvas及再两次动画帧；已捕获3视口真实IMAGE_RENDERED。切序列使用UI选择到ready/两帧，含自动化与来源状态核对。切片使用浏览器单调时钟，从发轮动作前标记到轴位第一个图像索引已改变的IMAGE_RENDERED事件，含命令传递；不含后续内存采样启动。该终点与旧轮询索引法不同，不称切片性能突然提升。

## 当前实测（本轮新增）

| 动作 | NIfTI病例17 | DICOM病例19 | 分层范围 |
|---|---|---|---|
| 首次三视图ready加两帧 | 2.295秒 | 4.894秒 | 新浏览器/禁HTTP缓存；服务/OS可热 |
| 首次选择T1c/T1n/T2w | 0.810 / 0.768 / 0.787秒 | 未测 | DICOM只有1个受支持序列，不能编造四序列切换 |
| 已在内存的序列切换，3次 | 69.0–75.2毫秒 | 不适用 | 仍执行版本状态核对，不能写成纯GPU时间 |
| 连续滚动3次到相应渲染 | 10.9–12.3毫秒，77→80 | 15.0–16.3毫秒，95→98 | 每次1层；不是所有交互/极端体积保证 |

真实检查查询37.18ms、序列列表47.15ms，各一次HTTP及JSON完整读取，经过既有鉴权代理/DICOMweb。DICOM完整首次阅片实际完成192个帧请求，体积192×256×192、spacing约0.976563/0.976563/1mm；NIfTI240×240×155、1mm及现有原mask。图像未模拟、没有新导入或AI。

## 进程内存与缓存（MiB）

Windows Get-Process按阶段边界采样；Edge PID集合由该专用浏览器SystemInfo.getProcessInfo返回，服务PID及精确启动时间先核对。以下Edge合计只是CDP暴露进程的工作集相加，共享页可重复计入，不是独占RAM或绝对全浏览器内存；renderer也为暴露的renderer进程合计。JS堆是页面目标Performance指标，不是全进程。原始CSV另保留private commit与进程全生命周期peak working set，后者不能当本任务峰值或GPU显存。

| 来源 | 边界 | Edge工作集合计 | renderer工作集合计 | 后端WS | Vite WS | Orthanc WS | Cornerstone缓存 | 页面JS堆 |
|---|---|---|---|---|---|---|---|---|
| nifti | first-ready | 915.1 | 364.1 | 236.6 | 533.3 | 115.9 | 42.57 | 49.88 |
| nifti | four-sequences-ready | 1260.2 | 574.0 | 236.7 | 533.3 | 115.9 | 144.74 | 65.94 |
| nifti | after-three-slices | 1260.3 | 575.6 | 236.7 | 533.3 | 115.9 | 144.74 | 60.99 |
| nifti | after-route-exit | 1209.3 | 574.1 | 239.2 | 523.4 | 115.9 | 0.00 | 62.72 |
| dicom | first-ready | 1011.7 | 506.7 | 266.2 | 490.5 | 116.6 | 18.00 | 57.69 |
| dicom | after-three-slices | 1018.5 | 508.6 | 266.2 | 490.5 | 116.6 | 18.00 | 60.04 |
| dicom | after-route-exit | 1001.8 | 501.4 | 266.3 | 491.3 | 116.6 | 0.00 | 64.31 |

阶段采样最大Edge工作集合计：NIfTI 1260.3MiB、DICOM 1018.5MiB；不是连续采样峰值，不测显存/驱动分配。两来源离开工作站后engine0/cache0；浏览器仍活时JS堆/工作集不立即为0，不以缓存清零宣称操作系统全部内存释放。没有强制GC或修改浏览器/系统缓存策略。

## 其他阶段仅引用历史，未本轮重跑

- [10/16 v2真实导入](P2_V2_REAL_IMPORT_VALIDATION.md)：192实例受控归档服务1.345秒，包含写入、逐份回读和末核，UI至成功2.777秒。不是纯网络上传时间。本次只读，未重导192，不补造单独上传/归档写入计时。
- [既有隔离NIfTI推理](PACS_COMPLETION_PLAN.md)：固定CUDA runner1.38秒，CLI总墙钟14.45秒，PyTorch分配峰值505.23MB；约2秒采样进程RSS最大1621.9MB。全卡总占用2022MB含系统基线，不能解释为任务专属显存。本轮没有推理，不能把阅片时间当推理时间。
- [既有CPU自动mask特征](RADIOMICS_ENVIRONMENT_MIGRATION.md)：内部提取1.763秒，不含HTTP/启动、不是队列保证，本轮未重提取。

纯上传独立耗时、多病例并发/生产构建性能、连续精确进程峰值、DICOM四序列AI均未据此通过。P4整体仍有P3/最终部署集成门槛，不因观测数据完整而勾选整个P4。

## 证据与保护

根 `E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T041517_viewperf/`。viewer-profile/validation.json保留分阶段网络计数、每次动作、每个PID工作集/私有提交/CPU秒/启动时间和JS指标；timings.csv与process-memory-samples.csv是原始可读表，profile-summary.json为同一原始数据汇总。两张profile-view.png已查看，显示真实三视图，不作为分割准确性证明。

两个浏览器非GET/HEAD请求被阻止，最终业务写0/pageError0。原17表所有行、八路径、四MRI/原mask5文件及账户/PACS配置/登记SHA不变；既有后台7708、前端18792和Orthanc7328未切换。formal-preservation/final-services有证据。新增benchmark_cornerstone_sources.mjs、measure_viewer_memory.ps1；产品代码/依赖不变，没有重复构建/全套pytest、PDF、训练/数据下载。有限同步锁内实际步骤退出0并释放，浏览器和内存读子进程均同步结束。

普通抽查：打开 http://127.0.0.1:5179/workstation/17?viewer=cornerstone 切序列/滚动，再由 http://127.0.0.1:5179/case/19 原检查/序列核空间进入DICOM并滚层；正常显示，正式库不增加测量。数值以本窗口日志为准，不要求人工秒表逐毫秒相同。
