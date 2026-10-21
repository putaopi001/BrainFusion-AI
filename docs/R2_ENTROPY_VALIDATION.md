# R2 熵权融合组件与旧模型离线复核

2026-10-16；实现run_id `20261016T101158_entropy`，10:28续接整理run_id `20261016T103011_resume`。R2整体进行中，以下工程子项已验收；不是同协议自动掩膜全队列或独立临床评价。

先冻结[R2工程协议](R2_ENTROPY_PROTOCOL.md)，UTC02:13:07、SHA256 `B1739A8479F9ACE52C033E4CD29CB006B423ED12EDB785EC1EB12AA9AEEE2617`，再实施/计算。新独立模块entropy_topsis.py实现三准则熵权、旧向量TOPSIS距离、全局分支权重、NaN整列弃用/常量/零熵/零距离/并列/极端/缺分支回退；每次应用核冻结状态与分支顺序，保存每患者有效权重/原因。无患者标签或真实Dice生成部署动态权重。JSON重载全状态复算是内部一致性校验，不是来源签名。

新增compare_entropy_fusion.py仅重放受信本地旧bundle；核原指针/summary/model/CSV SHA、原98/21/22名单与完整互斥、特征顺序、分支身份、验证三指标和旧22人逐概率/标签/患者顺序。熵状态先冻结/写盘/重载再算已观察22人的融合；六方法同人同终点，阈值0.5。旧模型/指针/源码topsis.py和experiment.py不改，不训练/重分/激活。原始事件idh1/2=1的临床极性未解决，只是发布者参考掩膜特征，不是自动掩膜分类结果。

| 方法 | 临床/影像组学权重 | AUC | 平衡准确率 | Brier |
|---|---|---|---|---|
| clinical | [1.0, 0.0] | 0.884298 | 0.863636 | 0.170598 |
| reference_mask_radiomics | [0.0, 1.0] | 0.818182 | 0.772727 | 0.203399 |
| average | [0.5, 0.5] | 0.892562 | 0.727273 | 0.163918 |
| fixed_clinical_0.6_radiomics_0.4 | [0.6, 0.4] | 0.900826 | 0.772727 | 0.161561 |
| validation_topsis | [0.0, 1.0] | 0.818182 | 0.772727 | 0.203399 |
| validation_entropy_topsis | [0.0, 1.0] | 0.818182 | 0.772727 | 0.203399 |

熵准则权重为AUC 0.179902、平衡准确率0.525887、Brier 0.294211；验证侧影像组学三项都支配临床，旧/新TOPSIS均坍缩为[0,1]并记录extreme_branch_weight。22人已有观察，熵权没有带来优势；这不构成显著性、泛化或两方法等效证据。没有按结果改准则、裁剪极端权重或挑选较好结果覆盖原方案。

验证：22项组件+5项既有研究回归=27项通过/4条现有弃用警告；补充独立距离上界手算的零距离容差回归1项通过，合计28个不同用例（不是再次全跑28）。运行时另验5个拒绝场景：协议SHA不符、已有输出、summary不符、同大小模型篡改、元数据SHA自洽但患者跨集合重叠，均在对应不安全读取/新输出前拒绝；还核零距离明确均匀回退。首次两个测试命令因PowerShell参数拆分退出4/0用例，修正命令后通过；两个补充夹具误以为成本质量零/距离和会退化，读实际熵与距离并依距离上界构造1.1e-12差值后通过，算法未为夹具改动。所有失败日志和非零包装器退出均保留。

实现证据 `E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T101158_entropy/`：protocol-freeze、component-tests-final2.log/XML、zero-distance-test.log/XML、guard-checks、observed-comparison-final下comparison/entropy-state/predictions/application-audit及源码SHA；旧observed-comparison是工具来源清单补齐前的首次复核，数值相同，不算独立重复样本。

剩余：验证侧准则删除/权重扰动及患者缺模态消融、同协议自动/参考全队列重拟合对照、R4区间/校准和解释。患者动态质量权重继续延期，标签/预训练重叠/未查看外部评价门槛保持。产品页和论文结论没有更新，旧408文件交付组合早于本轮研究组件，不冒称已重新打包。

## 中断后当前服务

10:28续接发现原后台32944/前端26632/归档28324均不存在，三端口无监听；日志无明确退出原因，系统上次启动为UTC2026-10-14T20:32:40.5，不能归因为本轮系统重启或R2代码。保留旧日志/登记，10:31仅用原启动脚本与原八路径/四配置正常启动；未安装、提权或重试历史被拒Orthanc环境动作。首次恢复验收脚本误读归一化series_uid为原始DICOM标签，退出1；改核实际API契约后通过，没有重启第二次或修改产品。

恢复证据 `E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T103011_resume/`：recovery-baseline、旧日志、archive/app-start、guard-after（失败）/guard-after-final、recovery-validation、reuse-after-recovery及final-services。17表/19病例全行、四份真实配置SHA/原八路径前后相同；PACS ready、账户configured、原关联192实例元数据/192×256×192网格可查询、匿名归档401、页面HTTP200及实际进程归属复用通过。没有重新导入、复制650、推理/特征/PDF/浏览器或构建；未新增阅片像素/人工验收。

抽查：①打开本目录协议与本报告，看28项和六方法负结果；②打开observed-comparison-final/comparison.json核21人拟合/22人探索、SHA与未激活；③访问http://127.0.0.1:5179/case/19查询原192层，或/workstation/17?viewer=cornerstone切序列，预期原数据仍在。无新截图；本轮只核恢复接口，已有浏览器证据保留历史。
