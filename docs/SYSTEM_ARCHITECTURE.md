# BrainFusion AI — 系统架构

## 一、系统架构图

```text
┌──────────────────────────── Frontend (Vue3 + Vite) ────────────────────────────┐
│  views/            components/           stores/           api/       router/   │
│  Dashboard         mri/MRIViewer         case/mri/ai/      axios      路由      │
│  Cases/Patients    mri/Toolbar           report (Pinia)                           │
│  CaseDetail        mri/Viewport ...                                              │
└──────────────────────────────────┬──────────────────────────────────────────────┘
                                   │ HTTP (统一信封 {code,message,data})
┌──────────────────────────────────▼──────────────────────────────────────────────┐
│                              Backend (FastAPI)                                   │
│  api/          services/        models/         schemas/         core/            │
│  HTTP 接口     业务逻辑          SQLAlchemy 模型  Pydantic 校验    配置/日志/异常   │
│                ai/              utils/                                             │
│                可插拔 AI 接口    公共函数                                          │
└──────────────────────────────────┬──────────────────────────────────────────────┘
                                   │ SQLAlchemy ORM
                          ┌────────▼────────┐
                          │   SQLite 数据库   │
                          │ brainfusion.db  │
                          └─────────────────┘
```

## 二、技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue3 + Vite + Element Plus + Pinia + Vue Router + Axios |
| 后端 | FastAPI + SQLAlchemy + SQLite + Pydantic |
| 医学影像 | NIfTI + SimpleITK + NumPy + Pillow |
| AI | PyTorch 预留（nnUNetv2 / MONAI / MedNeXt 已预装） |
| 部署 | Docker + docker-compose + Nginx |

## 三、数据流（核心闭环）

```text
创建患者 → 创建病例 → 上传 MRI（.nii/.nii.gz）
   ↓
影像解析 → 生成三视图预览 + 体素元数据
   ↓
阅片工作站（三视图 / WW-WL / Crosshair / 标注）
   ↓
AI 分析（MRI 基线 → 临床风险 → 多模态融合 → Agent 报告）
   ↓
结果展示 + 分割叠加 + 报告生成
   ↓
医生意见 + 确认 AI 结果（doctor_verified）
   ↓
病例归档
```

## 四、数据库模型关系

```text
Patient 1 ─── N Case 1 ─── 1 MRI
                           1
                           │
                           N
                       MRIAnnotation

Case 1 ─── N Prediction
Case 1 ─── 1 Report
Case 1 ─── 1 DoctorOpinion
```

## 五、MRI 状态机

```text
uploaded → processing → preview_ready → analyzed → doctor_verified
                              ↘ failed
```

## 六、AI 可插拔接口

```text
ai/interfaces.py
  BasePredictor (abstract predict)   → MRIModel / TabularModel / FusionModel
  BaseSegmenter  (abstract segment)  → 预留 nnUNet / MedNeXt
  PREDICTOR_REGISTRY / SEGMENTER_REGISTRY（装饰器注册）
```

## 七、目录结构

```text
backend/
  app/{api,services,models,schemas,core,ai,utils}
  tests/           # pytest 接口测试
  requirements.txt / requirements-core.txt / Dockerfile
frontend/
  src/{views,components,stores,api,router}
  Dockerfile / nginx.conf
docker-compose.yml
docs/
```