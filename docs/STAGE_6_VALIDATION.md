# 第六阶段：自动掩膜特征与研究迁移

完成：2026-10-07。实现当前病例的成功分割→真实特征提取→现有研究模型预测，并完成接口、浏览器和重启验证。模型仍在公开参考掩膜特征上拟合，本阶段没有重拟合或新增性能评估。

## 参数核查与参考复现

发布表 359 个区域行的非空提取配置只有一种，除区域标签外均一致：binWidth=0.02、normalize=False、resampledPixelSpacing=None、Original、distances=[1]、force2D=False、minimumROIDimensions=2。PyRadiomics 支持按特征类/名称和参数限制提取，设置方式见[官方配置文档](https://pyradiomics.readthedocs.io/en/latest/customization.html)。

下载 MRI 的原始强度与表中统计量不同。由数值比对推断，进入提取器前需要对每个完整 MRI 体积做 float64 min–max 到 [0,1]。五例、36 个序列/区域组合的 252 个一阶统计量最大误差 2.22×10⁻¹⁶；这一处理是数值推断与验证，尚未取得发布者的完整预处理代码。

固定提取契约 waw_selected20_minmax_v1。分类模型实际选中 20 个特征；只提取这些特征。未选列在原 1134 列输入矩阵中保持 NaN，经已拟合的独立插补/标准化后被 SelectKBest 排除，不重拟合预处理器。使用完整参考表与使用重提取选中特征时的预测一致，另有合成数据测试覆盖未选列变化不影响输出。

五例参考掩膜共有 55 个非空选中特征，其余为原来不存在的区域。特征最大绝对误差 4.55×10⁻¹³；五例概率最大差 2.78×10⁻¹⁶。非空特征判定 rtol=1e-5、atol=1e-8；概率差 <1e-6。空区域保持 null，由原训练插补器处理，不伪造零值。

## 实际自动掩膜输入

复用已有成功分割及四个上传序列，实际计算结果：

| 源患者 / 当前病例 | 参考掩膜影像组学概率 | 自动掩膜影像组学概率 | CPU 提取秒数 |
|---|---:|---:|---:|
| 4 / 11 | 0.5895 | 0.6927 | 1.982 |
| 13 / 12 | 0.3383 | 0.3435 | 2.643 |
| 16 / 13 | 0.9031 | 0.8066 | 2.752 |
| 17 / 14 | 0.5375 | 0.2043 | 2.187 |
| 19 / 15 | 0.2609 | 0.3437 | 3.667 |

这些是原研究模型更换输入后的工程结果，不能称自动掩膜模型已训练或已获得独立准确率。患者 17 的明显变化保留；患者 19 标签缺失。本阶段没有用五例调参或训练。

## 后台任务、缓存和版本

新增 POST/GET /research/cases/{case_id}/features。POST 输入明确年龄与 female，要求当前成功的真实模型分割；CPU 单 worker，状态 queued/running/succeeded/failed。校验四序列空间、输入和预测掩膜 SHA、研究模型、选中特征契约、提取代码和复现门槛。复现失败/过期、输入变化或任务中途版本变化均拒绝输出成功概率。

缓存键包含分析版本、研究版本、MRI/mask 哈希、临床输入和契约。相同输入读取已存结果，活动任务重复提交 409；新分割版本不展示旧特征。重启将中断特征任务标失败，已成功结果保留。提取不改动分割报告、医生意见或确认记录，研究概率只展示在研究页。

分割完成页新增“自动掩膜特征研究”入口，携带病例 ID；研究页选择已分析病例、提交临床输入、轮询、查看真实概率和保存结果。五例页面读取、实际表单提交、刷新、分割页跳转均通过。

## 环境与资源

E:/BrainFusion-Runtime/envs/radiomics39 是隔离的离线工作器：官方 Python 3.9.13 embeddable、PyRadiomics v3.1.0、NumPy 1.26.4、SimpleITK 2.5.2。版本及官方下载来源/本地 SHA 见 source.json。标准 PyRadiomics Windows 轮子没有当前 Python 3.10 的构建，所以使用独立兼容环境，主 Python/CUDA 未更换。安装/检查见 setup_radiomics_worker.py 和 requirements-radiomics-worker.txt。

该解释器是归档兼容运行时，仅用于本机离线子进程，不运行 Web 服务；正式部署前需在受支持解释器上构建并重新验收。单个特征 worker、SimpleITK 2 线程，没有 torch/CUDA 导入、GPU 训练或新增分割推理。

## 验证与证据

后端最终 26 项测试、前端生产构建及 2 项基础浏览器测试通过。五例真实自动特征接口、缓存、原报告/确认保留通过；浏览器五例、提交、轮询、刷新与跳转通过。实际停止/重启后五例特征、模型/分割版本、概率、报告和确认完全一致；原五例三视图/报告也重新读取通过。

E:/BrainFusion-Runtime/results/stage6：compatibility.json、normalization_checks.json、automatic_validation.json、browser_validation.json、automatic-features-page.png、persistence_validation.json、research_registry.json、backend-tests.log。每个特征任务文件在 results/feature_jobs/{病例ID}/{分割分析ID}/{特征任务ID}。

## 研究登记与待解决问题

登记脚本确认 141 人拆分互斥且与 152 个 MRI 归档 ID 匹配，保留 CSV/划分哈希和协议。原字典将目标写为 iidh1/2，实际临床列为 idh1/2，未明确 0/1 编码；正式临床解释需要发布者确认。MONAI 训练患者名单本机不可得，尚未排除队列重叠。原拆分已查看，只作探索性；完整队列同协议特征重提取、自动掩膜重拟合与独立最终评估仍未完成。
