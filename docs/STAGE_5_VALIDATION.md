# 第五阶段：回归、持久化与本机交付

验收更新：2026-10-06。本机分割主流程和 CPU 研究原型已验收；Docker 镜像/容器未运行验收。

## 完成与验证

- 后端最终 20 项测试通过：基础接口、医生意见、标注、方向/物理体积、空区域、错误掩膜保护、失败/中断、提前几何拒绝、缓存变更失效、研究白名单/拆分/权重与不可用/非法输入。日志 E:/BrainFusion-Runtime/results/stage5/backend-tests.log。
- 前端生产构建和 2 项基础 Playwright 测试通过；专用浏览器工具另覆盖五例叠加、真实四文件上传推理、负斜率测距刷新与 488541 字节 PDF，以及研究页五例概率与临床输入表单。
- 停止登记服务并重新启动后，五例当前分割掩膜、报告、确认版本和三个视图灰度/掩膜可读取，重算参考对照指标通过；五例研究模型冷加载后的概率与保存记录相同。
- 启动脚本检查 HTTP 就绪、E 盘目录、缓存与日志、端口及重复后端；停止脚本核对进程启动时间，已实际验证停止/重启。保留 8012/5179 演示服务。
- 本轮优化包括提前空间检查、固定权重 SHA 校验、有界元数据/掩膜缓存、路由按需加载和测试数据库隔离。缓存实测见 OPTIMIZATION_REPORT.md。
- Docker 增加 CPU 推理/研究依赖、数据/模型/研究只读挂载和 SQLite/uploads 持久化；没有安装 Docker，构建/运行/重建持久化仍未验证。不能为验收自动在 C 盘安装镜像/WSL。

## 证据与操作

汇总 E:/BrainFusion-Runtime/results/stage5/verification_summary.json；分割 stage2/workflow_validation.json；浏览器 stage3/browser_validation.json、截图和 PDF；研究 stage4/api_validation.json/browser_validation.json；重启 stage5/persistence_validation.json；性能 stage5/cache_benchmark.json。

使用 USER_OPERATION_GUIDE.md 与 RESEARCH_OPERATION_GUIDE.md；功能 FEATURE_OVERVIEW.md；启动/开发 LOCAL_RUN.md；后续步骤和工时 POST_SPRINT_PLAN.md。

## 准确边界

研究模型基于参考掩膜特征和单次已查看拆分，只能作为功能验证及探索结果。TOPSIS 没有证明优于平均。三轮模拟使用公共验证池，不提供真实跨院隐私保证；自动掩膜→IDH、完整联邦和独立实验仍需完成。五例分割也不是临床准确性证明，三例参考 TC/ET 为空时的假阳性已保留。

仍有非阻断弃用提示和前端大包警告；没有在本轮为消除提示升级现有 CUDA 环境。代码尚未提交、推送或发布。
