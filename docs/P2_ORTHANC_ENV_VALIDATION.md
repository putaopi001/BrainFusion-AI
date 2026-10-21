# P2本机Orthanc环境实际验收

## 2026-10-14 19:08 本机Orthanc环境解除与项目连接验收

run_id `20261014_manual_orthanc_b392fd6e`。用户已通过浏览器把官方候选两文件下载到既定目录。本轮静态大小/x64 PE/本地SHA核对通过，实际Orthanc --version=1.13.0；Authenticode为NotSigned，未把本地SHA当发布者签名。正常启动Windows本机进程，实际DICOMweb插件1.24加载；匿名/system返回401，后台鉴权/system与QIDO查询通过，归档实例0。新随机凭据只存在Runtime私有文件，不输出或进入源码。

项目在先SQLite备份后按既有runtime-supported配置恢复，现backend6164/frontend2748、8012/5179；原业务所有表内容与备份一致。/pacs/status=ready/read_available=true，pixel_read_enabled=false。真实浏览器病例17归档查询按钮可见、实际查询HTTP200、pageErrors0、写请求0。无新DICOM导入、关联、像素读取、推理/特征训练或PDF。P2-env已解除，P2总体仍进行中，E5 Docker阻塞不受此次影响。证据：E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014_manual_orthanc_b392fd6e/summary.json、pacs-readiness.json、browser-pacs-ready.json。

新增prepare_local_orthanc.py与start_orthanc_local.ps1，prepare/语法/schema已核；actual start/connect通过。配置/索引/文件/日志在E:/BrainFusion-Runtime/orthanc-local；backend归档配置E:/BrainFusion-Runtime/local/pacs-config.json。Orthanc独立进程登记在orthanc-local/process.json，不误当项目start/stop_local的一部分；不注册系统服务，重启电脑后需按正常脚本重启。未提交/推送。

下一轮先核对开发锁/实际PID/健康，复用已启动归档，不再重试下载或将环境标受阻。优先192层真实MR的有记录脱敏派生副本及明确入库执行路径，原件/UID映射保留。来源/像素处理完成后验证实际导入→病例关联→Cornerstone，再开放像素；当前不把技术联系表查看冒充临床认证或模型四序列确认。可先用明确合成工程材料验真实归档持久化，但不能代替真实样本阅片。

本轮不声称P2/P3全链路完成。用户抽查：http://127.0.0.1:5179/case/17，归档显示可查询；空列表符合当前归档状态。
