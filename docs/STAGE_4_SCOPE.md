# 第四阶段范围与状态

更新：2026-10-06。此前按核心分割优先而暂缓的轻量 IDH、TOPSIS 和模拟联邦现已完成 CPU 原型及功能验证。

详细实施、实际指标、验收证据和限制见 STAGE_4_VALIDATION.md；操作及复现见 RESEARCH_OPERATION_GUIDE.md。

已经实现：患者级 CSV 读取与字段白名单、固定拆分、两分支 Logistic Regression、平均/固定/TOPSIS、集中式与 IID/标签偏斜 FedAvg/TOPSIS 三轮模拟；保存模型及全部权重、五例真实输入 API 与研究页、服务重启一致性。

没有实现：自动掩膜特征提取、深度影像分类、熵权 EWM/患者动态 TOPSIS、完整 Local/FedProx 对照、多种子、外部/封存最终实验和跨院隐私系统。当前影像组学来自参考掩膜；测试拆分已查看，指标均探索性。TOPSIS 未优于平均融合，保留负结果。

本轮没有大型或 GPU 训练，仅 CPU 轻量拟合。下一阶段具体步骤和工时见 POST_SPRINT_PLAN.md；核心分割继续使用单进程、batch=1、CPU 拼接、6000 MB 分配预算。
