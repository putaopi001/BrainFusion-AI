# 真实 PACS 元数据页面只读验收（2026-10-20）

## 范围

在当前 Docker Compose 前端 `http://127.0.0.1:18180` 的病例详情页面执行真实 PACS 查询。浏览器自动阻断所有非 GET/HEAD/OPTIONS 请求和所有 `/frames`、`/wado` 像素请求；未点击病例关联、导入、转换、审核、激活、保存或阅片操作。没有读取或保存病例页面中的患者文字，也没有保存截图。

## 页面结果

- 病例详情页面 HTTP 200；PACS状态文案确认归档查询可用。
- 点击“查询检查”后，检查列表 HTTP 200，页面显示1行；选择检查后序列列表 HTTP 200，显示1行。
- 选择序列并点击“核对序列空间”后，实例清单和空间清单均 HTTP 200，页面明确显示“空间核对通过（仅元数据）”。
- Cornerstone 阅片按钮因像素门控关闭而处于禁用状态。
- 全程页面异常0、业务写请求0、像素帧请求0。

该结果证明真实归档的病例页元数据查询和空间清单流程可用；不证明病例关联正确、序列医学角色正确、图像隐私通过或真实 DICOM→AI 完成。

## 修复的阻断故障

病例详情初始化还会读取转换作业列表。新隔离运行卷不存在可选目录 `/app/runtime/local` 时，`dicom_conversion_jobs._root()` 对缺失父目录执行 `resolve(strict=True)`，触发未处理 `FileNotFoundError`；前端因整组初始化失败而隐藏“查询检查”。服务现已改为缺失目录时只读返回空作业列表；只有创建作业时才创建运行目录，不改变其他数据。

`backend/tests/test_dicom_conversion_registry.py` 回归 **23 passed**，其中新增测试证明运行目录不存在时返回空列表且不创建目录。隔离 Docker 后端仅重建/替换后恢复 healthy，当前镜像 ID：`sha256:689110273a52608c5cf5c1a580c16990a8a6a6685eebd218aa13a412ed095d3d`；前端容器未替换，仍为 `sha256:ba5ff46e3af0304819506af8c2958dd2e658ee0169f537d45ccbcdb0e1e99a07`。

## 当前运行边界

Orthanc 1.13.0 在本机8042经过认证运行。PACS 为 `ready/read_available=true`，`pixel_read_enabled=false`、`dicom_view_available=false`、`import_available=false`、`ai_bridge_available=false`。浏览器页面可用于只读查询检查、序列和空间元数据；影像阅片和四序列到AI流程仍须等待合格人工隐私审核、许可核对与序列角色判断。离线联合恢复副本的 `live_restoration_verified=false` 不因本次原归档验收而改变。
