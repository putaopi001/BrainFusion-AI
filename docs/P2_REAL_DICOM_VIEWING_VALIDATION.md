# 真实公开DICOM归档到Cornerstone阅片验收

日期：2026-10-14。run_id：20261014_real_dicom_6f9cbbff。完成P2真实单序列阅片里程碑，P2整项仍进行中，P3匹配四序列AI链路未完成。

## 实际效果与抽查

打开 http://127.0.0.1:5179/case/19 。这是新建独立公开数据演示病例，BF-PACS-001，年龄null、性别unknown；没有借用原病例17的临床信息、NIfTI、mask或预测。

在本地DICOM归档点“查询检查”→选择检查→选择唯一序列→“核对序列空间”→“Cornerstone阅片（工程验证）”。可看到真实三视图、滚动、窗宽窗位等操作。系统不自动把单序列解释为四序列输入；本病例无AI结果。

## 来源和派生处理

来源为已下载UPENN-GBM 192层CaPTk处理/去面部临床采集来源DICOM，CC BY4.0来源记录与下载账本保持。原件在E:/BrainFusion-Data/PACS-candidates/UPENN-GBM/20261014T180828_p2sample/t1/instances，全部192文件SHA未变。

派生目录E:/BrainFusion-Data/PACS-derived/20261014_real_dicom_6f9cbbff。新增classic-mr-local-viewing-metadata-v1白名单处理：仅保留必要像素、数值几何/呈现/MR信号字段；所有原私有字段、日期、身份自由文本和序列引用排除；生成新本地Patient/Study/Series/SOP/Frame标识，原UID映射仅保存在派生目录私有文件。逐文件重新读取确认像素原字节、解码数值及几何一致，原件再次SHA核对。

这是有限经典MR本地科研阅片派生处理，不是通用PS3.15脱敏器/临床认证。没有像素修改、配准、重采样或完整去面部操作；原BurnedInAnnotation缺失不伪造NO。六张联系表的技术观察没有见到身份文字，但不冒称医生认证。患者年龄允许null以保留真实缺失，研究输入仍使用既有完整性门槛；不能补造年龄后用于训练。

## 实际验收

- Orthanc1.13.0/DICOMweb1.24实际导入192实例，每份存储原文件GET字节SHA与派生文件一致。
- 单实例重复上传返回AlreadyStored，归档总数仍192。
- 后端现有检查关联API将新Study关联独立病例19，固定服务identity与fingerprint，读取192层manifest成功。
- 真实浏览器无mock，从病例页查询/选序列/核对空间/点击阅片进入工作站。192个真实帧响应全部200，3个MPR canvas，pageErrors0、业务写请求0；全9,437,184个体素的Float64规范字节SHA与独立pydicom物理排序/显式缩放参考一致，dimensions/spacing一致，滚动与窗值实际变化。
- 实际停止并重启Orthanc后192实例、服务标识和病例关联仍有效，再从病例页重复新路径浏览器验收通过。进程重启不是PACS+业务联合备份恢复或异机迁移。
- 当前业务库完整性ok，所有历史行保留，只增加patients/cases/pacs_study_links各1行。未修改原分析/特征/报告/标注、未新推理/训练。
- 相关后端52项通过、4既有警告；最后派生校验从assert改成显式异常后复验派生/API14项通过，未重复全套。前端生产构建通过，保留大chunk/编解码外置Node模块提示，不声称所有压缩格式已验证。

## 发现并解决的实际兼容问题

Orthanc1.24响应type参数为带transfer-syntax的quoted media type；旧代理只接受裸application/octet-stream，真实帧因此502。现在独立解析内层media type，只允许单个明确未压缩Little Endian语法，仍保留边界、单part、字节长度与编码约束；新增合法及Big Endian/JPEG拒绝测试，真实浏览器全体素复验通过。没有关闭检查或静默解码。

首次测试临时目录父路径缺失导致初始化错误；两次临时API协调脚本误把case_id/患者详情字段当id，已按现有接口纠正并复用已创建病例，没有重复创建。初次实际浏览器因上述MIME错误超时，失败JSON保留；修复后最终证据在post-restart-ui，原通过截图留作历史。所有失败不作通过证据。

## 工具与运行

新增dicom_viewing_derivative.py、prepare_public_mr_viewing.py、import_local_viewing_derivative.py及verify_real_local_dicom.mjs。工具保留原件、拒绝混合序列/重复SOP/不支持格式/已有派生目录；导入前核对全部派生身份/哈希和真实归档鉴权/固定身份，每实例确认原字节，记录可续接进度。元数据工具不按名称判断T1/T1c角色，不直接激活模型。

服务当前frontend5179/backend8012，PID和精确启动时间见Runtime/local/processes.json；Orthanc另有orthanc-local/process.json。像素读取开启，仅本机鉴权归档中当前192份白名单派生影像，凭据不在源码/浏览器。新数据进入归档前仍需按来源/处理流程核对。

证据根：E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014_real_dicom_6f9cbbff；summary.json、business-preservation.json、archive-restart.json、post-restart-ui/real-dicom-browser.json及real-dicom-three-views.png。派生目录另有准备/导入与私有映射记录。

下一步：补可操作的导入入口及恢复一致性；再寻找/确认匹配真实四序列，完成DICOM到NIfTI来源桥接与模型输入激活。P2单序列阅片已不是合成协议，仍不能称临床有效性、完整PACS或四序列AI系统全部完工。
