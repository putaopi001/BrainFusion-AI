# 本地PACS与业务联合恢复验收

日期：2026-10-14，北京时间20:06开始；run_id `20261014T200622_p4joint`。这是P4联合恢复子项，P4整体仍进行中。

本轮首次实际将已运行归档的SQLite索引、192份真实公开MR元数据派生DICOM、两份私有服务配置，与当前完整应用数据库/产物快照一起备份，再恢复到另一套目录。按[Orthanc官方备份流程](https://orthanc.uclouvain.be/book/users/backup.html)先停归档再复制索引/存储/配置；本地后端同时停止，开始前确认没有分析或特征任务。停止过程核对PID、启动时间、可执行路径、配置及端口所有者，再调用官方关闭接口；没有强杀其他进程。独占开发锁在整个实施和验证期间保持。

## 当前重新通过

- 完整应用650份文件的源/快照SHA不变；恢复副本仅按既有E3规则改运行路径和特征缓存绑定。全部14张业务表的科学字段、版本字段、行数及源库内容核对通过，包括19病例、18患者、17MRI、24分析记录、25报告、1条PACS检查关联。没有重新分割或提取特征。
- PACS与配置196份文件逐份SHA复制/恢复。快照成功后才写成功清单；篡改、路径越界、重复目标、已有目标或正在运行的服务不能报成功。备份包含服务凭据，留在Runtime私有备份目录，未放到项目或本轮公开证据中。
- 原归档停止后，在原8042地址启动**恢复目录**中的索引与文件，保留原数据库服务标识，后台切至恢复数据库/文件路径及恢复的私有PACS配置。实际192份`/instances/{id}/file`SHA、Study UID、归档指纹和病例关联，与停机前观察全部一致。
- 全新真实浏览器从恢复的病例19页面查询、选检查/序列、核对空间、进入Cornerstone，三视图加载，192帧均200；9,437,184体素的规范Float64 SHA、尺寸及毫米间距与独立pydicom参考一致。滚层/窗宽窗位变化、零页面异常、零浏览器写请求；截图已查看。
- 随后正常停止恢复服务，按原配置/原目录重新启动唯一归档、后端和前端；192实例及病例关系再次与备份前一致。副本保留，不作为日常演示服务。成功演练阶段原服务切离到恢复原服务共61.64秒，包含复制、两套启动和浏览器检查，**不是归档吞吐/推理时间**。

## 新增工具和范围

`backend/tools/snapshot_pacs_joint.py`复用既有全应用快照，增加离线PACS文件/配置及联合清单。只支持本机当前SQLite+文件存储、Orthanc1.13.0/DICOMweb1.24、HTTP8042/后端8012、单服务账户配置；不是任意Orthanc插件/集群的通用备份器。`start_orthanc_local.ps1 -Root`支持独立恢复目录，新增`stop_orthanc_local.ps1`用于核对身份后的正常退出。`verify_pacs_joint_restore.py`只读核对实际归档字节和业务关系。8项新的文件完整性/不覆盖/路径保护测试通过。

第一次停止尝试因将真实`0.0.0.0`监听误当成非本地配置而拒绝，没有关闭归档；finally已恢复原前后端。改为核对实际监听所有者，并保留`RemoteAccessAllowed=false`及强制鉴权检查后，第二次完整演练通过。原配置未改，未变更防火墙；不宣称进程仅绑定loopback网卡。首次失败日志单独保留，不混入成功证据。

## 证据与限制

本轮证据根：`E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T200622_p4joint/`。关键文件：`before-backup.json`、`application-restore-audit.json`、`restored-live.json`、`restored-ui/real-dicom-browser.json`、`restored-ui/real-dicom-three-views.png`、`joint-live-validation.json`、`original-resumed.json`、`recovery-timing-attempt2.json`、`snapshot-safety-tests-final.log`。

私有快照/恢复副本：`E:/BrainFusion-Runtime/backups/20261014T200622_p4joint/{snapshot,restored}`。不得把含凭据的整个目录直接作为公开交付包。源码、Python两环境、Orthanc可执行文件/插件仍为本机外部前提；数据源许可/原始UID派生审计保留在既有Data与证据目录，未声称本备份包含完整原始研究队列及全部来源材料。

此次仅证明当前192实例单序列及既有应用在同机副本恢复后可用；没有新的四序列DICOM→模型验收、DICOM测量/叠加/保存、异机部署、Docker或研究结论。下一批优先补现有UI中的受控导入入口；P3仍需匹配真实四序列、可审计身份/空间及明确激活流程。

抽查：打开`http://127.0.0.1:5179/case/19`，查询检查，选择唯一检查/序列，核对空间后进入Cornerstone，应显示三视图。日常服务已回到原目录；恢复副本的截图/数据比较在上述证据根。
