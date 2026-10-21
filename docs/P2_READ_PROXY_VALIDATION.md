# P2 本地归档读取与检查关联：工程小批次验收

窗口：2026-10-12 23:25（北京），run_id `20261012T232541_082a3a38`。系统 UTC 开始15:25:42.0896792Z。P2-a 工程协议与页面小批次已验收；P2完整归档未验收，P2-env仍受阻。没有取得或运行Orthanc，也没有真实DICOM导入、像素获取、DICOM阅片或AI转换。

## 实际实现

FastAPI新增 `/pacs/status`，有明确read/import/view/AI可用性；未配置状态为unconfigured，读取清单返回503。连接失败、凭据错误、归档未强制鉴权、插件/资源缺失、非法元数据各有明确原因。状态查询本身200用于显示可用性，不把不可用当作空归档。成功响应和归档错误均no-store。

受限QIDO读取 `/pacs/studies`、`/pacs/studies/{study_uid}/series`、`/pacs/studies/{study_uid}/series/{series_uid}/instances`；Study UID过滤，limit1–100、offset0–100000分页，每次解码JSON上限4MiB。UID数字点分、最长64字符、非法/重复或父UID不一致拒绝。清单仅返回UID、日期、模态、编号与数量；实例请求FrameOfReference UID，不自动赋四序列身份，不获取像素。省略的父UID来自已验证的层级请求路径，不能当作实际实例完整几何证据。

归档地址只接受含显式端口的127.0.0.1或[::1] origin，固定`/dicom-web`根；禁任意URL、路径、用户信息与跳转，不使用系统HTTP代理。每次连接先确认未鉴权`/system`为401，再用后台Basic凭据读取系统与QIDO。浏览器传入Authorization/Cookie/Forwarded不转发，配置/上游错误不输出凭据、配置原文或响应体；HTTPS仍正常验证证书，不改系统证书。上述接口按[Orthanc官方插件协议](https://orthanc.uclouvain.be/book/plugins/dicomweb.html)实现；真实发行兼容性仍待实测。

`GET/POST /pacs/cases/{case_id}/links`保存`pacs_study_links`。写入须明确核对病例并实际QIDO找到唯一检查，保存archive_id、origin hash、Study UID、最小元数据原文及SHA、确认方式/UTC时间。唯一(archive_id,study_uid)，同病例重试返回原记录，不改来源摘要；不同病例或地址改变409，不覆盖。数据库唯一约束及事务冲突分支保护并发。旧关联在当前配置不可用/不匹配时仍可读并明确标识；关联不创建MRI、不修改分析/研究或报告。此批没有提供重绑/删除关联，错误关联后续需要独立审计修订机制。

病例详情沿用原UI增加PacsPanel：状态/刷新、可用时查询检查、序列/实例分页、显式病例核对与关联、已关联清单。忙时禁止表格切换；取消请求/切换病例清理旧选择与提示，连接失败不持续显示“正在检查”。现有NIfTI与Cornerstone流程保持；DICOM导入/阅片/转换入口未开放。

## 后台配置契约（没有创建正式配置）

Settings的`PACS_CONFIG_FILE`默认`E:/BrainFusion-Runtime/local/pacs-config.json`；环境变量可选择其他E盘路径。不是原runtime JSON的第九个path key，现有8项配置格式不变。私有配置仅服务端读取，不放frontend/public或仓库、交付包。规范内容如下，placeholder不是实际凭据：

```json
{
  "format_version": 1,
  "archive_id": "local-orthanc-archive-v1",
  "base_url": "http://127.0.0.1:8042",
  "username": "<后台专用本地用户>",
  "password": "<本地私有凭据>"
}
```

archive_id须稳定唯一；替换归档数据源必须新ID，不能沿用同端口/ID冒用旧来源。本批只用origin hash防明显地址变化，不能检测同origin归档库被替换；P2正式部署须增加归档身份/恢复核验与操作记录。服务须限制本机、强制鉴权；不要为连接打开无鉴权远程服务。修改私有文件在后续请求读取，改环境变量则使用既有启动脚本与身份检查重启。正式导入前仍需合法真实样本、脱敏核查和来源清单，此契约不替代它们。

## 本轮证据与限制

证据根：`E:/BrainFusion-Runtime/results/nightly/2026-10-12/20261012T232541_082a3a38/`。

- `backend-final-complete.log`：65 passed，4既有弃用警告。31新增PACS行为通过，其余为世界测量/序列/配置/基础API相关回归。实际loopback TCP协议夹具包括Basic鉴权、拒无鉴权/错误密码、HTTP204、分页、多模态、父UID、malformed JSON与4MiB读取限制、凭据不转发/不输出、SQLite关联/重复/冲突/重开、原MRI不变。夹具全程标明SYNTHETIC，不是Orthanc或真实DICOM。并发唯一冲突分支有约束保障，未做多进程压力验收。
- `database-backup`：原库只读SQLite快照/恢复副本，完整性通过；`migration-validation.json`在真实旧库副本加一表、旧行相同、原库不变。正式重启后只增加空pacs_study_links；`original-accepted.json`旧13表全行/科学文件参考SHA/feature jobs所有文件SHA相同、活动任务0、6实际API通过、归档列表503/no-store。
- `browser-pacs-final/validation.json`：真实开发服务未配置显示；独立拦截的SYNTHETIC页面检查/序列/实例、显式核对、重复UI不重复行、刷新、409原关联保留、SPA病例17→1清理、受控连接拒绝/重连；0页面异常/真实写请求。页面模拟关联没有写原库；实际SQLite持久化属于上面的后端隔离库证据。
- `build-api-8012.log`及`browser-pacs-production-api-8012/validation.json`：最终构建明确`VITE_API_BASE=http://127.0.0.1:8012`，真实HTTP预览病例详情/不可用PACS/刷新、现有NIfTI Cornerstone三canvas正常；0页面异常/写请求。保留约3.4MB Cornerstone大chunk提示。已恢复dev，不重复安装、推理/提取或全包交付。
- 历史失败保留：backend-pacs-initial为空UID校验与测试病例临床字段缺失；migration-validation.log错误引用不存在`/sequences`，最终使用`/volume?sequence=t1c`；browser-pacs初版试图点Element隐藏input，最终点可见标签；start-preview传绝对PreviewDist路径不符合既有脚本，应为相对dist；首个静态build未提供API8012导致生产页面失败，最终显式API配置并补前端连接错误提示。启动补充检查误用残留LASTEXITCODE导致工具层异常，但真实preview进程/登记/HTTP均成功，保留日志。失败结果不当作最终通过。

当前服务backend11936 UTC15:43:22.3357500Z，frontend25508 UTC15:46:50.5940729Z，单实例、开发模式。地址5179/8012；登记Runtime/local/processes.json，backend日志Runtime/local/backend.{out,err}.log，frontend本run/restored-dev-final/frontend.{out,err}.log。生产preview2620已核验停止；不得复用旧PID。无下载/训练/推理/构建长任务。

## 抽查（当前没有真实DICOM输入）

1. 打开`http://127.0.0.1:5179/case/17`，查看“本地 DICOM 归档”：应明确尚未配置、DICOM导入/阅片/转换未开放，没有查询按钮和伪检查。
2. 点击“刷新归档状态”：仍明确不可用，病例已有MRI/研究/意见不变；不新增关联。
3. 打开`http://127.0.0.1:8012/pacs/status`：state=unconfigured/read_available=false；`/pacs/studies`应503，`/pacs/cases/17/links`空列表。
4. 打开`http://127.0.0.1:5179/workstation/17?viewer=cornerstone`：已有真实NIfTI三视图仍可读，明确属于NIfTI路径。

## 下一步

先核对锁/反馈/上述服务。继续P2-b可独立的脱敏DICOM入库契约与受限WADO元数据/像素代理，在明确隔离样本/协议夹具验证；正式导入与阅片仍以真实Orthanc+合法真实DICOM验收。P2-env保持上一轮自动审批阻塞：官方候选下载+版本探测被拒、仅`blocked by policy`，没有重新执行或换工具绕过。可审核环境动作/已安装可用服务出现后再运行归档；P3真实四序列和P4联合恢复/性能/PDF均未通过，E5/E6与R余项保持。
