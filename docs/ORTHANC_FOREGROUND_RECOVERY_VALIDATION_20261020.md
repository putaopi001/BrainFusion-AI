# Orthanc 前台恢复与 PACS 查询验收（2026-10-20）

## 当前结论

后台启动脚本在 Codex/Anaconda PowerShell 中曾检测到子进程仍在 Windows Job 中并安全终止。即使从任务管理器启动的新 PowerShell 自身 Job 限制为 `0x00000000`，后台启动器仍拒绝该子进程。因此改用外部普通 PowerShell 前台运行 Orthanc；不要再重复触发已知会安全拒绝的后台启动流程。

当前 Orthanc 已由 `E:\BrainFusion-Runtime\toolchains\orthanc-1.13.0-dicomweb-1.24\Orthanc.exe` 加载 `E:\BrainFusion-Runtime\orthanc-local\orthanc.json`，PID 8168，UTC 启动时间 `2026-10-20T12:10:43.9635728Z`，独占监听本机8042。认证 `/system` 检查得到版本1.13.0、数据库身份匹配；DICOMweb QIDO 查询成功。进程登记 `E:\BrainFusion-Runtime\orthanc-local\process.json` 已更新到这个已核验身份；旧记录备份为 `E:\BrainFusion-Runtime\orthanc-local\process.pre-foreground-20261020T121700318Z.json`。

Docker 隔离演示前后端容器均 healthy（本机端口18180/18100）。通过后端 `/pacs/studies?limit=50` 的只读查询返回200、1个检查；`/pacs/status` 返回 `state=ready`、`read_available=true`。未读取图像像素、未导入或写入检查。

复核发现运行配置此前 `allow_pixel_read=true`，但用户尚无法确认候选影像中的烧录个人信息。为遵守既有隐私门槛，已将 `E:\BrainFusion-Runtime\local\pacs-config.json` 的该字段改为严格布尔值 `false`，原配置备份为 `pacs-config.json.pre-pixel-gate-20261020T121738748Z.json`。变更后再次实测：PACS仍 `ready`、归档读取可用、`pixel_read_enabled=false`、`dicom_view_available=false`，导入与AI桥均不可用。只改功能开关，未改归档身份、凭据、Orthanc配置或影像数据。

## 复现运行

在普通 PowerShell 外部窗口直接前台运行：

```powershell
& 'E:\BrainFusion-Runtime\toolchains\orthanc-1.13.0-dicomweb-1.24\Orthanc.exe' 'E:\BrainFusion-Runtime\orthanc-local\orthanc.json'
```

保持该窗口打开。另一个 PowerShell 可只读检查：

```powershell
(Invoke-RestMethod 'http://127.0.0.1:18100/pacs/status').data |
  Select-Object state,read_available,pixel_read_enabled,dicom_view_available,import_available,ai_bridge_available
```

需要停止时，使用已核验PID/启动时间/命令行/监听端口和配置的身份安全脚本：

```powershell
& 'E:\BrainFusion-AI\backend\tools\stop_orthanc_local.ps1' -Root 'E:\BrainFusion-Runtime\orthanc-local'
```

它通过认证的 Orthanc 正常关机接口停止已登记实例，不应手工结束不明PID。前台服务退出后终端返回提示符。

## 尚未验收

此前“没有进行病例页验收”的状态已被2026-10-20的真实浏览器只读验收覆盖：检查/序列/实例/空间元数据流程已通过，具体证据见 `PACS_METADATA_PAGE_VALIDATION_20261020.md`。本次没有读取像素、关联病例、导入、转换、激活、推理或生成新报告。ACRIN-134的烧录文字及序列角色仍缺合格人工审核；不得将本次状态标成真实四序列DICOM→AI完成。当前可演示NIfTI只读路径和PACS元数据页面；未经像素审核不可演示PACS图像阅片。

