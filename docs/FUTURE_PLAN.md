# BrainFusion AI — 未来规划

## 一、v0.2 规划（工程演进）

- [ ] 打通 preprocess → predict 流程（用 processed_path 作为分析输入）
- [ ] 报告导出 PDF
- [ ] 前端路由级代码分割（减少首屏体积）
- [ ] 登录与权限体系（角色：医生 / 研究员 / 管理员）
- [ ] SQLite → PostgreSQL 迁移
- [ ] 清理遗留接口（reports.py 硬编码路径）

## 二、真实模型接入路线

### 1. 分割模型（肿瘤区域勾画）

```text
当前：模拟椭球掩膜（ensure_segmentation_mask）
目标：nnUNet / MedNeXt 输出 mask.nii.gz

接入方式：
  实现 ai/interfaces.py 的 BaseSegmenter.segment(mri_path) -> mask_path
  注册到 SEGMENTER_REGISTRY
  替换 mri_service.ensure_segmentation_mask 为真实模型产物
```

### 2. 分类 / 风险模型

```text
当前：MRIModel 基线占位（按体素数阈值）
目标：MedNeXt / Transformer 影像分类模型

接入方式：实现 BasePredictor.predict，注册到 PREDICTOR_REGISTRY
```

### 3. 临床 / 多模态模型

```text
当前：TabICL-v2 测试结果占位（固定 risk_score=0.78）
目标：真实临床结构化数据 + 多模态融合
```

## 三、AI 能力升级

- 分割：多类别（肿瘤核心 / 水肿 / 增强区 / 坏死）
- 影像：3D 卷积 / Transformer 分类与分割
- 可解释：Grad-CAM / 注意力热力图叠加
- 报告：接入大语言模型（LLM）生成结构化诊断报告
- 评估：Dice / IoU / AUC 等指标评测面板

## 四、医学影像能力升级

- 体素间距参与测距换算（mm 单位）
- 窗宽窗位预设（脑窗 / 骨窗 / 自定义）
- 多序列融合（T1 / T1c / T2 / FLAIR）
- 后续可评估 Cornerstone3D / OHIF 迁移（数据层已按体素强度建模）

## 五、目标愿景

将 BrainFusion AI 打造为一个**面向脑胶质瘤多模态 AI 辅助诊疗场景的科研原型平台**，具备：

- 完整医疗 AI 工作流
- 医院级医学影像浏览能力
- 可插拔的真实 AI 模型接口
- 工程化、可部署、可测试的软件架构