# 当前系统架构与DICOM结果关系

## 2026-10-16 已导出并查看的当前图稿

[两张SVG/PNG与来源说明](E6_ARCHITECTURE_FIGURES.md)已通过实际源码关系核对、Edge渲染/文字边界与逐图查看。下面Mermaid仍保留可编辑关系源，旧“未渲染”文字仅为当时记录。账户DICOM最小组合已实际CLI/活服务/重启验证，完整新账户19病例数据组合已实际恢复/重启，独立安装交付另待最终验收；当前Edge NIfTI与DICOM保存/正常关闭、DICOM账户/PDF明确范围已有证据。

![当前架构](assets/architecture-20261016/architecture-current.png)

![DICOM关系与来源](assets/architecture-20261016/dicom-data-relations.png)

当前P2受支持经典MR本机导入/关联/Cornerstone范围已验，来源准备v2真实分支证据见[P2验收](P2_V2_REAL_IMPORT_VALIDATION.md)。新私有账户最小联合组合已实际接通，旧17表全量bundle历史不变；两张当前图稿如上。完整新账户19病例数据组合已实际恢复；真实匹配四序列模型桥仍受阻，代码/环境联合安装及异机部署待验。

2026-10-15夜间工程材料。以代码、已验范围和17表联合恢复为依据；这是Mermaid源图，未在本轮导出/审核位图或论文排版，不把源图存在当图稿验收。

## 运行与数据路径

```mermaid
flowchart LR
  N[受支持四序列NIfTI] --> API[FastAPI 现有服务]
  D[获准公开MR派生资料及固定复核证据] --> I[受控导入与持久回执]
  I --> O[本机Orthanc与DICOMweb]
  O --> P[后端来源核对与鉴权代理]
  P --> V[现有Vue工作站 Cornerstone3D]
  API --> V
  V --> Q[来源绑定距离与视图]
  Q --> DB[SQLite 业务库]
  DB --> R[现有报告页 内容复核与PDF]
  API --> S[固定MONAI分割器]
  S --> A[版本化分割产物与只读mask]
  A --> V
  A --> F[自动掩膜特征工作器]
  F --> X[原始目标值IDH研究与融合]
  X --> DB
  P -. 真实匹配四序列及激活尚受阻 .-> B[DICOM到模型输入桥]
  B -. 未完成真实端到端 .-> S
```

浏览器不持有Orthanc服务凭据；后端保留受支持像素、来源与归档身份保护。图中受控资料入口不是任意文件自动脱敏。普通单序列阅片不依赖IDH标签或四序列齐备。DICOM病例19当前没有模型分割/预测，不能借用NIfTI病例17的结果填入其报告。真实NIfTI模型与研究结果保持原来源；未知IDH编码仅按原始目标值解释，非临床风险。

## 数据库声明关系及跨归档绑定

```mermaid
erDiagram
  cases ||--o{ pacs_study_links : case_id
  cases ||--o{ dicom_world_measurements : case_id
  cases ||--o{ dicom_view_states : case_id
  cases ||--o{ dicom_reading_reviews : case_id
  cases ||--o| doctor_opinions : case_id
  pacs_study_links {
    int id PK
    int case_id FK
    string archive_id
    string study_uid
    string endpoint_fingerprint
  }
  dicom_world_measurements {
    int id PK
    int case_id FK
    string study_uid
    string series_uid
    text context_json
    text points_lps
    float length_mm
  }
  dicom_view_states {
    int id PK
    int case_id FK
    text context_json
    text state_json
  }
  dicom_reading_reviews {
    int id PK
    int case_id FK
    string content_sha256
    text snapshot_json
    string reviewer
    text opinion
    string decision
  }
```

图示SQLAlchemy声明关系，不据此声称跨归档由SQL外键自动强制一致。距离/视图的context与复核snapshot还绑定病例检查关联ID、归档指纹、Study/Series/FrameOfReference UID及元数据摘要；没有额外的SQL序列表或Instance表。归档实例由Orthanc管理，导入回执及来源证据保存在E盘文件中，不能只备份SQLite。

病例医生意见是独立病例级记录，未自行变成序列复核。复核另存不可变完整快照；来源、距离或意见变化后历史过期，原文不丢。内容SHA不包含复核本身以避免循环；导出SHA包含最新复核状态，导出前后重新核对，旧页不能将过期内容当当前结果。当前新复核在snapshot_json绑定本地账户ID/角色，doctor角色方可POST；旧行继续未认证。独立LOCAL_AUTH_FILE保存盐化摘要/账户配置，内存会话重启失效，不新增SQL表。此权限仅覆盖DICOM复核，不是全站医院RBAC，不能作为实名/医师资质证据。

## 恢复与交付边界

完整恢复组合是Orthanc索引/实例/私有配置、业务17表、应用产物/模型来源、导入登记/回执及运行路径；当前账户配置另作私有补充备份（10/15旧bundle未收录；10/16新工具自动收录的最小DICOM/账户组合已活服务验收，完整新19病例含账户数据组合已在05:18窗口通过，源码/环境安装交付另验）。正常停机、离线核对复制、独立目录实际启动、来源/版本/世界坐标及浏览器核对后，恢复正式配置；私有凭据不随公开材料分发。已验同机17表组合，不宣称Docker、异机环境、医院现网PACS或DICOM SEG/SR回写。

最新实证见 [17表联合恢复](P4_JOINT17_RECOVERY_VALIDATION.md)、[报告边界](P4_REPORT_BOUNDARIES_VALIDATION.md)、[P1测量与视图](P1_MEASUREMENT_VIEW_VALIDATION.md)。旧论文图表仅代表当时工程版本；现有SCI/外部独立评价、四序列桥和全站/多用户部署的门槛分别保留，本地复核账户最小范围见[当前验收](P4_LOCAL_REVIEW_IDENTITY_VALIDATION.md)。
