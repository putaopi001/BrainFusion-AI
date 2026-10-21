# 独立前端环境与构建交付

2026-10-10 07:05窗口E6小批次：固定版本官方来源候选实际安装/构建、真实HTTP单前端试运行/重启/浏览器与原开发服务回退通过；不是新机器或Docker/Linux完整系统验收。默认CUDA主后端与独立特征worker不变，研究结论不升级。

## 来源与安装角色

原frontend/package-lock.json的422项镜像地址及SHA保留。06:06来源预检将官方固定版本元信息与原SRI逐项核对，候选只在外部证据目录替换resolved地址，保留版本/依赖图/全部flags和Element Plus明确的@popperjs/core安装目录→@sxzz/popperjs-es npm别名；不能以同版本另一包替换。07:05实际Windows安装396项、26项其他平台可选包未装，396实际包名/版本/隐藏锁来源/SRI及对应缓存tarball SHA512全部匹配，文件SHA256与许可元信息另存。最初已有SRI缓存匹配0，本次396文件总量67060361字节，不是网络流量计量。旧包的deprecated提示保留，未执行npm安全/签名审计，不据来源匹配宣称无漏洞。

Node24.21.0 Winx64 ZIP来自nodejs.org官方冻结URL，37618919字节，SHA256=158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541。实际prefix E:/BrainFusion-Runtime/envs/node24-delivery-20261010T070557_2d087f2d，Node v24.21.0/npm11.19.0与ZIP许可证SHA记录；未验数字签名/再分发许可。Node+396 tarball合计104679280文件字节，不能写成传输量。最初预算预留2GiB、E空闲约417GB；跨平台unpackedSize619375342字节为保守参考、非实际安装体积或流量。

工具backend/tools/prepare_frontend_delivery.py只使用标准库与仓库源码审计工具。目标是全新的nightly/frontend和node24-delivery-* prefix；不沿用/删除原node_modules、不对已有测试联接npm ci。原源码复制后只有候选package-lock的resolved地址改变，npm ci禁install脚本/审计/资金提示；自身Node/npm、TEMP/TMP/npm/浏览器缓存均E盘，空E盘用户/global npm配置，进程内PATH不改系统PATH、不自动起服务。记录长进程原生PID/启动时间/配置/日志和安装来源；失败保留部分目录，不能在同目录重复npm ci或删除成功产物。

## 实际API地址必须显式绑定

源码中的默认8000是历史回退值，不是当前8012服务。独立副本不包含私有.env；因此首个构建只作为构建证据保存，不能当当前部署通过。07:05另建dist-api8012，以VITE_API_BASE=http://127.0.0.1:8012构建，原dist保留。未来工具强制--api-base，不能从旧端口猜配置。

```powershell
# 全新输出/prefix，来源预检与候选锁须先核验原SHA；不会修改原锁或默认服务。
E:/Anaconda3/python.exe -B E:/BrainFusion-AI/backend/tools/prepare_frontend_delivery.py --source-probe <已验E盘来源预检目录> --output <全新E盘nightly目录> --node-prefix <全新E盘envs/node24-delivery-标识> --api-base http://127.0.0.1:8012
```

成功状态passed_isolated_frontend_install_and_build_not_browser_or_new_machine仅安装和构建。还需验证实际HTTP、浏览器及所用后端版本；缓存来源若历史未知，必须明确unknown，只能以官方SRI认定文件吻合，不能补造历史下载地址。

## 单前端试运行与回退

现有start_local/stop_local新增显式-FrontendOnly；默认行为未改。停止只核验登记PID与原生启动时间；独立前端启动核验现用后端PID/启动/路径/命令/监听所有权/健康及请求runtime路径，端口占用拒绝而不停止服务。候选通过显式FrontendProject/NodePath/PreviewDist选择，日志必须全新E盘nightly目录；隐藏启动，只更新前端登记，不创建或结束后端。错误地址/运行配置或已有前端不得假复用。默认-ReuseExisting不能把候选预览冒称原开发前端。

试运行必须先确认无活动任务/其他写者并备份SQLite，源表/任务签名前后核对，所有UI测试禁写。07:05真实预览25300→重启28276→回退开发8912；后端始终31840/UTC启动2026-10-09T21:30:04.2527517Z。当前开发前端8912/UTC启动2026-10-09T23:22:16.1822222Z、5179；旧17736/两个预览PID已核验停止，不可当现用。前端日志在本run restored-dev-service/{frontend.out.log,frontend.err.log}，后端仍Runtime/local原日志；实际身份见Runtime/local/processes.json。

```powershell
# 仅在已验来源/产物、确认无任务/备份/登记与锁后执行；不在原服务仍占用时强开。
./backend/tools/stop_local.ps1 -FrontendOnly
./backend/tools/start_local.ps1 -FrontendOnly -RuntimeConfig <现用runtime.json> -BackendPort 8012 -FrontendPort 5179 -FrontendProject <已验独立frontend目录> -NodePath <已验独立node.exe> -PreviewDist dist-api8012 -FrontendLogRoot <全新E盘nightly日志目录>
# 完成后再次只停前端；省略候选字段恢复原开发前端，仍需新日志目录。
```

生产静态资源拦截回放两次受Chromium本地地址空间安全限制，不能用这种失败冒充页面通过，也不关闭浏览器安全限制/自动授予网络权限。最终用真实HTTP预览，逐文件HTTP响应SHA等于构建manifest；病例17、四序列MRI与原mask、研究57male/任务版本/原概率、报告/独立意见/PDF入口实际浏览器检查，初启与前端重启各四截图，页面/console/网络错误及写请求均0。截图只是工程回归，中心层mask可能为空，不能称为分割准确率或肿瘤非空证明。报告页与入口不是本轮新PDF视觉验收；原PDF视觉证据保持历史。

证据以最新NIGHTLY_HANDOFF与20261010T070557_2d087f2d下frontend-delivery-candidate、api-bound-build、frontend-browser-realhttp/after-restart、三服务登记、备份与final-validation为准。最终shipping CLI另用全新frontend-delivery-final和node24-delivery-20261010T070557_2d087f2d-final，实际执行必填--api-base http://127.0.0.1:8012；396项全部复用已验SRI缓存，29个构建文件与实际HTTP前端重启前后提供的文件逐字节相同，不重新切换服务。final-validation确认原数据库与备份/前轮逐表签名、病例17十接口、主53依赖及C盘Conda登记均不变。根目录ZIP处理/凭据扫描夹具/Win32长测试路径中间失败保留；修复后7新增行为检查和110后端通过。Vite大chunk和deprecated警告披露，不因此升级所有依赖或研究协议。

## 未验与下一步

这只是Windows前端独立引导/真实本机服务的工程验收，不是完整异机、Linux容器、独立特征worker安装或数据/模型全自动迁移。Node/tarball/构建包不自动公开分发。E5管理员WSL/可能重启窗口仍缺，E6最终容器相关回归仍待E5。下一可独立批次整理CPU主/前端/已验worker和既有数据恢复的清晰组成/引导角色，减少新机指南对工程旧pip的隐式依赖；不重新运行已验55/252或CPU模型对照。
