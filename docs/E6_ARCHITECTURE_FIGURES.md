# E6 当前架构与DICOM关系图稿

2026-10-16凌晨，run_id `20261016T030947_edgenifti`。本批交付两张独立工程图，SVG可编辑/缩放，PNG供预览及毕业设计材料使用；最终论文排版和题目另定，不新增研究性能或临床结论。

| 图 | 矢量原件 | 预览 | 当前范围 |
|---|---|---|---|
| 当前系统架构 | [SVG](assets/architecture-20261016/architecture-current.svg) | [PNG](assets/architecture-20261016/architecture-current.png) | NIfTI真实模型路径、受支持DICOM归档/代理/现有工作站、业务/复核/PDF与备份；虚线真实四序列桥受阻 |
| DICOM数据关系与来源绑定 | [SVG](assets/architecture-20261016/dicom-data-relations.svg) | [PNG](assets/architecture-20261016/dicom-data-relations.png) | 17表中的DICOM子图，声明case_id关系与运行时逻辑核对区分；账户/归档仍为库外文件 |

图稿不是把NIfTI输出连入DICOM病例，不代表新UI/医院现网PACS/全站RBAC或医师资质；原始IDH目标值限制保留。病例意见和序列复核独立，内容SHA不含复核本身、导出SHA含最新复核；不声称SQLite已强制所有外键或逐次哈希全部像素。关系图省略其余NIfTI/患者/研究表，不能当完整数据库ER图。

实现：backend/tools/export_architecture_figures.py通过AST实际核对5个相关模型的cases.id声明外键和复核snapshot字段，并核对DICOM复核POST的require_doctor；source-manifest.json保存11个相关代码源SHA，不包含数据库/个人凭据。输出必须是全新E盘目录，不覆盖已有图。frontend/tools/render_architecture_figures.mjs使用已装Edge155渲染；104条文字全部在画布及所属框内，实际中文字体加载，最后两张PNG均已查看。初稿视觉检查后去掉易误读为NIfTI→DICOM的数据箭头、增大底边留白，并画出三张子表声明关系；最终使用figures-final，初稿不覆盖。

正式可复用文件位于docs/assets/architecture-20261016；同目录source-manifest.json与render-validation.json记录源码/输出SHA和渲染范围。证据根为E:/BrainFusion-Runtime/results/nightly/2026-10-16/20261016T030947_edgenifti/，见figure-export-final.log、figure-render-final.log、visual-review.json。无新依赖/下载/PDF/模型、业务写入或产品构建；图稿工具的实际生成/DOM边界/视觉检查即本批验证，不为低影响图稿另加镜像实现的测试。

这只完成E6图稿导出小项；完整新账户多病例包、最终部署/异机验收和P3/E5条件未完成。已有[最小账户联合恢复](P4_JOINT_ACCOUNT_RECOVERY_VALIDATION.md)实际通过，与旧650应用全量恢复证据分开；不能继续写成“账户接线从未活服务验证”，也不能称完整新全量包已经验证。
