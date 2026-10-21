# Orthanc 与当前阻塞项的解决步骤

更新：2026-10-14。目标是先完成Windows本机PACS，不把Docker作为前置条件。本轮准备配置和工具，未下载或执行Orthanc，未导入DICOM。

## Orthanc实际问题

历史复合动作“下载官方Orthanc.exe/DICOMweb DLL→核验→运行--version”被自动审批在进程创建前拒绝，仅返回blocked by policy。没有进一步原因，不能猜测为软件恶意或官方禁止下载。另有Python缺requests和证书链失败，这与审批拒绝不是同一问题。官方HEAD曾正常返回，两文件总约32.6MB。

本轮不重复或换工具执行该被拒动作。建议用户通过浏览器从官方入口取得文件，留在既有E盘候选目录，然后接续静态检查、实际启动和后端鉴权/DICOMweb健康核对。不要禁用TLS、关闭杀毒或使用未知镜像。

## 已准备的成果

- backend/tools/prepare_local_orthanc.py：--prepare仅创建本机配置；--check-files仅检查两份字节大小、x64 PE和本地SHA，不执行；--connect仅读取实际归档，要求匿名401、已鉴权Orthanc1.13.0和QIDO数组成功后才新建后端配置。已有后端归档配置拒绝覆盖，像素开关仍关闭。
- backend/tools/start_orthanc_local.ps1：仅用户明确执行时启动本机进程；检查所需文件、8042占用及已有进程身份，隐藏窗口保存日志；不注册Windows服务、不需要先安装Docker。
- 已生成E:/BrainFusion-Runtime/orthanc-local/orthanc.json和brainfusion-pacs-candidate.json，随机凭据只存在本机私有配置，不在文档/终端打印。HTTP仅本机、8042、强制鉴权，DICOM网络接收关闭；文件/索引/日志都留E盘。不是完整用户权限体系。
- 本轮Python语法、两个JSON、现有PacsConfig校验、匹配凭据和PowerShell语法通过。未启动或实际加载插件，所以不宣称归档已经可用。正式PACS_CONFIG_FILE仍不存在、未改变后端行为。

## 用户最小操作

先从官方Windows入口核对候选，浏览器下载以下两份文件到：

E:/BrainFusion-Runtime/toolchains/orthanc-1.13.0-dicomweb-1.24/

前次官方目录已核对的固定候选：
- https://orthanc.uclouvain.be/downloads/windows-64/orthanc/1.13.0/Orthanc.exe
- https://orthanc.uclouvain.be/downloads/windows-64/orthanc-dicomweb/OrthancDicomWeb-1.24.dll

本轮web工具无法重新打开该二进制目录，故不把前次HEAD称为本轮实时可达。若候选无法下载，使用官方Windows入口选择可访问发行，记录实际版本；工具严格1.13.0假设需按实际发行更新和复验，不能把其它版本改名冒充。

只下载即可，不需要用户先上传数据、关闭系统保护或运行安装器。取得后下一次由Codex按正常工具审核规则继续静态核对/配置/实际启动；不能承诺后续执行审核一定通过。若选择完整Windows安装器，可能需要用户交互安装与服务目录配置，作为备选，不混用便携候选配置。

## 接续步骤（未执行）

1. 读取最新交接/锁，核对两文件官方来源、版本说明及本机静态检查；本地SHA只是内容标识，不冒称发布者签名。
2. 在允许执行的条件下用start_orthanc_local启动，再用prepare_local_orthanc --connect校验。需要实际插件加载和鉴权QIDO成功才安装backend配置；不把启动进程当健康通过。
3. 启动/复用项目时先核对真实服务登记。18:08交接表明旧PID和端口已经不在运行，不能仍提供旧页面为在线地址。沿既有运行配置恢复，不覆盖数据库。
4. 用明确SYNTHETIC工程DICOM检验真实Orthanc入库、查询与重启（工程标记保持）；然后用来源/许可已记录且完成必要去标识处理的192层真实MR派生副本验收阅片。原文件保留，只改派生副本，不把工程样本当临床队列。
5. 核对UID关联、帧像素和Cornerstone显示，再按实测开放像素读取。归档恢复需与病例库一起验证；同机重启通过不能冒称异机迁移完成。

## 其他阻塞项

真实样本：18:08已取得支持几何的192层UPENN经典MR、19,432,662字节，全部源UID/像素解码/几何通过；另60层FLAIR的声明1mm/实测约3mm冲突仍保留拒绝。现在不再重复下载同一组或全量139GB数据。路径与技术查看范围见P2_PUBLIC_MR_SAMPLE_20261014.md。普通阅片无需IDH标签或四序列齐全。

数据去标识：现有预检只会检查/保管且archive_eligible恒false，不是可执行完整脱敏/入库工具。下一批针对已获192层样本的实际字段建立有记录的派生处理与明确工程/真实数据角色，保留原件/映射/哈希；必要的像素人工抽查应在已有联系表基础上完成，不声称AI技术观察等于医生认证，也不凭未验证声明自动批准。

模型桥：该单序列spacing并非当前1mm四序列契约，先用于阅片；完整模型桥另找匹配四序列或另行明确重采样范围，不改元数据伪装满足契约。已有NIfTI模型路径继续可用。

研究：标签极性、预训练重叠与独立评价拆开处理；已有原始0/1可用于清楚标记的探索性工程验证，不能猜突变含义。FedProx组件已开始，Local-only/完整预算/多种子可独立推进，独立泛化结论仍需真实门槛。

Docker：Windows本机PACS先通；WSL授权/重启窗口后再做容器部署，不让它阻塞本机归档。

## 官方依据

- https://www.orthanc-server.com/download-windows.php
- https://orthanc.uclouvain.be/book/users/configuration.html
- https://orthanc.uclouvain.be/book/plugins/dicomweb.html

后续只修改有实际必要的入口与结果，避免再次每小时重复来源/旧模型/旧PDF检查。
