# BrainFusion AI

脑胶质瘤 AI 辅助诊疗平台（教学 / 科研原型系统 · v0.1.0）

> 面向脑胶质瘤辅助诊疗场景的多模态 AI 科研原型：融合医学影像分析、临床数据分析、多模型融合、AI 解释与智能报告生成，构建「患者管理 → 病例管理 → MRI 影像查看 → AI 分析 → 风险评估 → 报告生成 → 医生反馈确认」的完整闭环。
>
> **本系统为教学与原型工具，所有 AI 结果仅供演示与科研参考，不构成临床诊断或治疗建议，请以具有执业资质的医生阅片意见为准。**

## 一、功能特性

| 模块 | 能力 |
|------|------|
| 病例 / 患者管理 | 增删改查、搜索、状态筛选 |
| MRI 影像阅片 | NIfTI 上传、三视图（轴/冠/矢）、真实窗宽窗位（基于体素强度）、Crosshair 同步、缩放平移 |
| 医生标注 | 点 / 矩形 ROI / 测距 / 角度 / 自由绘制 / 文字，五类标注自动配色，体素坐标，删除单个 / 全部 |
| AI 分析 | MRI 基线 + TabICL-v2 临床风险 + 多模态融合 + Agent 报告（接口可插拔） |
| 诊断报告 | AI 总结、推荐措施、医生意见、AI 结果确认闭环（doctor_verified） |
| AI 分割叠加 | 模拟掩膜红色半透明叠加（预留 nnUNet / MedNeXt 接入） |

## 二、技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue3 + Vite + Element Plus + Pinia + Vue Router + Axios |
| 后端 | FastAPI + SQLAlchemy + SQLite + Pydantic |
| 医学影像 | NIfTI + SimpleITK + NumPy + Pillow |
| AI | PyTorch 预留（nnUNetv2 / MONAI / MedNeXt 依赖已预装） |
| 部署 | Docker + docker-compose + Nginx |

## 三、系统架构

```text
用户 → 病例管理 → MRI 上传 → 影像解析 → 阅片工作站 → AI 模型分析 → 结果融合 → 报告生成 → 医生确认 → 病例归档
```

```text
frontend (Vue3)                    backend (FastAPI)
  views / components                api/      → HTTP 接口
  stores (Pinia)                    services/ → 业务逻辑
  api (Axios)                       models/   → 数据模型 (SQLAlchemy)
         │                          schemas/  → 请求/响应 (Pydantic)
         │  统一信封 {code,message,data}   core/ → 配置/日志/异常
         └────────── HTTP ─────────→ ai/      → 可插拔 AI 接口
                                     utils/    → 公共函数

                               SQLite (brainfusion.db)
```

## 四、目录结构

```text
backend/
  app/{api,services,models,schemas,core,ai,utils}
  tests/           # pytest 接口测试
  requirements.txt          # 完整依赖（含重型 AI 依赖）
  requirements-core.txt     # Web 服务核心依赖
  Dockerfile
frontend/
  src/{views,components,stores,api,router}
  Dockerfile / nginx.conf
docker-compose.yml
docs/
```

## 五、快速开始（安装运行）

### 1. 后端

```bash
cd backend
python -m venv venv                    # 若尚未创建虚拟环境
venv\Scripts\activate                 # Windows 激活
pip install -r requirements-core.txt   # 仅 Web 服务核心依赖
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

> 若需本地训练 / 推理真实模型，改安装 `requirements.txt`（含 torch / nnunetv2 / monai 等重型依赖，体积较大）。

接口文档：启动后访问 http://127.0.0.1:8000/docs （Swagger UI）。

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173 。

## 六、使用指南（操作步骤）

### 第一步：启动系统

1. 启动后端（终端 A）：`cd backend` → `venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
2. 启动前端（终端 B）：`cd frontend` → `npm run dev`
3. 打开 http://localhost:5173

### 第二步：完整诊疗流程

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| 1 | 左侧栏「患者管理」→ 填写姓名/年龄/性别 → 创建患者 | 列表出现新患者 |
| 2 | 「病例管理」→ 创建病例 → 选择患者并填写描述 | 列表出现新病例（待上传） |
| 3 | 病例行「上传 MRI」→ 选择 .nii/.nii.gz 文件 | 提示上传成功并跳详情 |
| 4 | 病例详情「MRI 影像信息」 | 状态显示「阅片就绪」 |
| 5 | 「MRI 影像浏览」区 | 三视图显示，可切层/滚轮/缩放平移 |
| 6 | 底部「窗宽/窗位」滑块或「窗宽窗位」工具拖拽 | 灰度按体素强度实时变化 |
| 7 | 工具栏选「标记点/矩形ROI/测距/角度/自由ROI/文字」并在图上绘制 | 图上出现对应图形 |
| 8 | 「保存标注」→ 刷新页面 | 标注重新出现（持久化） |
| 9 | 标注列表「删除」或「删除全部」（二次确认） | 标注被移除，刷新后不再回显 |
| 10 | 工具栏「AI 分割叠加」 | 红色半透明掩膜叠加 |
| 11 | 「重新 AI 分析」或病例行「AI 分析」 | 显示概率/风险/融合评分 |
| 12 | 「查看完整报告」→ 填医生意见 → 「确认 AI 结果」 | 报告展示 + 显示已确认 |
| 13 | 返回「病例管理」 | 病例状态变为「已分析」 |

### 第三步：接口自测（可选）

后端启动后可用 Swagger 或 curl 自测，例如：

```bash
# 健康检查
curl http://127.0.0.1:8000/
# 病例列表
curl http://127.0.0.1:8000/cases/
# MRI 体素元数据
curl http://127.0.0.1:8000/mri/1/volume
# 真实窗宽窗位切片（返回 PNG）
curl "http://127.0.0.1:8000/mri/1/slice/axial/80?ww=238&wl=119"
```

## 七、接口规范

统一返回格式：

```json
{ "code": 200, "message": "success", "data": {} }
```

统一错误（404 / 422 / 500 同构信封，兼容前端 detail）：

```json
{ "code": 404, "message": "MRI not found", "detail": "MRI not found", "data": null }
```

MRI 状态机：`uploaded → processing → preview_ready → analyzed → doctor_verified`（失败 → `failed`）。

## 八、测试

```bash
cd backend
venv\Scripts\python.exe -m pytest tests -v
```

预期 6 个用例全部通过（root / debug / 病例创建 / 病例列表 / 统一 404 / 删除全部标注）。

## 九、注意事项

1. **医学免责**：本系统为教学科研原型，AI 结果仅供参考，不构成诊断或治疗建议。
2. **数据与隐私**：上传的 MRI 与数据库（brainfusion.db）含患者信息，仓库已通过 .gitignore 排除，请勿将真实患者数据提交到公开仓库或部署到公网。
3. **依赖体积**：`requirements.txt` 含 torch/nnunetv2/monai 等重型依赖（数 GB），日常运行后端仅需 `requirements-core.txt`。
4. **端口占用**：后端默认 8000、前端默认 5173，如被占用请修改启动参数或 `frontend/.env` 中的 `VITE_API_BASE`。
5. **前端配置**：后端地址通过环境变量 `VITE_API_BASE` 配置，默认 `http://127.0.0.1:8000`。
6. **常见问题**：标注点/ROI 无反应多为后端未启动；页面显示旧版多为运行旧构建，请重启 `npm run dev`。
7. **时间戳**：首次从旧库升级后，历史数据的时间戳字段可能为空，属正常迁移现象，新增数据自动填充。

## 十、Docker 部署

```bash
docker-compose up --build
```

- 后端：http://localhost:8000
- 前端：http://localhost

## 十一、未来规划

详见 `docs/FUTURE_PLAN.md`：接入真实分割模型（nnUNet / MedNeXt）、报告导出 PDF、登录权限、SQLite → PostgreSQL、前端代码分割等。