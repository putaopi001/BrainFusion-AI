# BrainFusion AI v0.1 工程化收口 — 评估与实施记录

## 一、当前项目完整评估（收口前）

| 维度 | 收口前状态 | 收口后状态 |
|------|-----------|-----------|
| 后端分层 | api 层混杂业务/文件/AI 逻辑 | api → service → model 分层，core 统一配置/日志/异常 |
| 返回格式 | 部分 `{code,data}`，部分返回 ORM 对象/裸 dict | 统一 `{code,message,data}` + 统一异常处理 |
| 异常处理 | 无统一处理，错误格式不一致 | 统一 404/422/500 信封，兼容前端 detail |
| 日志 | 无结构化日志 | core/logging.py 统一日志 |
| 数据库时间戳 | 部分实体缺失 created/updated | 全实体补齐 created_time/updated_time + 迁移 |
| AI 模块 | 硬编码、无接口约束 | ai/interfaces.py 统一 Predictor/Segmenter 接口 + 注册表 |
| 状态管理 | 无（仅遗留 counter 示例） | Pinia：case/mri/ai/report 四个 store |
| 前端布局 | 简单横向菜单 | Header + Sidebar + Main 医疗风布局 |
| 部署 | 无 | Dockerfile + docker-compose + requirements-core |
| 测试 | 无 | pytest 接口测试（5 用例通过） |
| 文档 | 无 | README + 本文档 |

## 二、技术债务列表

1. `reports.py` 硬编码 `case_1` 路径，未走 DB/service（遗留接口）。
2. `preprocess` 与 `predict` 未打通：预处理结果 `processed_path` 未接入分析流程。
3. `predict_service.py`、`mri_viewer_service.py` 为死代码（已删除）。
4. `requirements.txt` 为完整 pip freeze，含 torch/nnunetv2/monai 等重型依赖，与 Web 服务耦合（已拆分 requirements-core.txt）。
5. 前端大 chunk（1.1MB），需路由级 `import()` 代码分割。
6. AI 结果仍为基线/占位数据，未接真实模型。
7. 分割掩膜为模拟椭球，非真实 MedNeXt/nnUNet 输出。
8. 体素间距未参与测距换算（当前 spacing=1.0）。
9. 无登录/权限体系。
10. SQLite 单文件，多并发/生产需升级 PostgreSQL。

## 三、必须修改的问题（本次已处理）

- [x] 统一返回格式与异常处理（main.py 统一 exception handler）。
- [x] api 层去业务化：标注/影像逻辑下沉 service。
- [x] 删除重复/死代码：predict_service、mri_viewer_service。
- [x] 补齐实体时间戳并增加字段说明。
- [x] AI 模块统一接口（ai/interfaces.py）与注册表。
- [x] 修复 patients/predictions 返回裸 ORM / model_name 字段 bug。
- [x] 引入 Pinia 状态管理并接入 CaseDetail。
- [x] 前端医疗风 Layout（Sidebar + Header + Main）。
- [x] Docker 部署与 requirements-core 拆分。
- [x] pytest 接口测试。
- [x] README 与架构文档。

## 四、推荐修改顺序（后续）

1. 打通 preprocess → predict 流程（用 processed_path 作为分析输入）。
2. 接入真实分割模型，替换 mock 掩膜。
3. 报告导出 PDF。
4. 前端路由级代码分割。
5. 登录/权限 + PostgreSQL 迁移。

## 五、本次涉及文件

后端：
- app/main.py（统一异常/日志/迁移）
- app/core/{config,logging,exceptions,response}.py
- app/database.py（使用 settings）
- app/models/*.py（时间戳 + 字段说明 + processed_path）
- app/schemas/{case,patient,annotation}.py
- app/api/{patients,debug,predictions,preprocess}.py（统一信封 + 修复）
- app/ai/interfaces.py（新增）
- app/ai/{imaging/mri_model,tabular/tab_model,fusion/fusion_model}.py（实现接口）
- tests/test_api.py（新增）
- requirements-core.txt、Dockerfile（新增）

前端：
- src/main.js（注册 Pinia）
- src/api/axios.js（VITE_API_BASE + 超时）
- src/App.vue（Sidebar + Header + Main 布局）
- src/views/Home.vue（Dashboard）
- src/views/Patients.vue（响应结构修复）
- src/views/CaseDetail.vue（接入 store）
- src/stores/{case,mri,ai,report}.js（新增）
- Dockerfile、nginx.conf（新增）

根目录：
- README.md、docs/ARCHITECTURE.md、docker-compose.yml

## 六、测试方案

- 后端：`pytest tests -v`（root / debug / 病例创建 / 病例列表 / 统一 404 错误，5 用例通过）。
- 前端：`npm run build`（编译通过）。
- 手工回归：上传 MRI → 预览 → 阅片（三视图/窗宽窗位/标注）→ AI 分析 → 报告 → 医生确认。

## 七、AI 可插拔接口

```text
ai/interfaces.py
  BasePredictor (abstract predict)   → MRIModel / TabularModel / FusionModel
  BaseSegmenter  (abstract segment)  → 预留 MedNeXt / nnUNet
  PREDICTOR_REGISTRY / SEGMENTER_REGISTRY（@register_predictor / @register_segmenter）
```

未来接入真实模型：实现 BasePredictor/BaseSegmenter 并注册，替换 ai_service 中的实例化即可。