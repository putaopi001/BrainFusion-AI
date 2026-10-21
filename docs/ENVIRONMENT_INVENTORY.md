## 2026-10-20 主环境 Python wheel 缓存只读核验

在不安装、不导入、不改动环境的前提下，扫描 pip HTTP 缓存中的 1354 个响应体（约 15.10 GB）。其中找到 52/54 个当前 Python 分发的名称与版本匹配候选；对候选 wheel 中可与已安装分发 RECORD 哈希对应的文件逐项核对，52 项候选均为零差异。证据报告含逐包 wheel SHA-256、缓存相对路径、比对文件数及候选数：E:/BrainFusion-Runtime/results/nightly/2026-10-20/20261020T1945_main_python_cache_audit/python-wheel-cache-matches.json。

这改善了现存安装文件与缓存 wheel 的内容对应证据，但 pip HTTP 缓存不能证明原始安装使用了该缓存文件，也不能证明该 wheel 的下载来源；未找到的分发也仍然缺少 wheel 候选。因此原始来源缺失的历史事实保持不变，本快照仍不是完整安装锁或新机器复建验收。

# 环境清单的角色与实测边界

## 2026-10-18当前主环境来源快照

当前服务使用的主CUDA环境`.conda/brainfusion`已生成只读来源快照：20个Conda包的已安装`conda-meta`记录均含官方包URL和SHA-256。原有16个缓存归档重算后与记录SHA-256一致；原先缺失的4个归档随后从已记录的`repo.anaconda.com`官方HTTPS URL单独下载到`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1300_main_env_conda_archive_recheck/verified-conda-archives/`，SHA-256全部匹配。因此20/20个Conda归档现在都有独立文件哈希核验。54项Python分发中，49项仍没有保留原始wheel来源；本地pydicom wheel可找到，重算摘要也与安装记录一致。Conda归档复核报告见同目录`validation.json`；原始快照位于`E:/BrainFusion-Runtime/results/nightly/2026-10-18/20261018T1655_main_env_provenance/cache-rehashed-final/`，由[来源快照工具](../backend/tools/capture_conda_provenance.py)生成。

20个Conda归档与1个pydicom wheel现已独立重算匹配；额外下载只保存原归档并核对哈希，没有安装、替换或改动当前CUDA环境。49个Python分发包的原始来源仍未知，已安装文件亦未与wheel逐文件比较。因此这是可追溯的观测清单，不是完整Python安装锁或新机器复建证明。原安装来源缺失的历史事实仍保留，不从版本号反推来源。

## 2026-10-13 01:19窗口（当前；10/12夜至10/13凌晨）

run_id20261013T011921_b6663451；系统UTC/原生PID精确值见本run lock-acquired，FileShare.None holder实际保持、session58224，结束/耗时/正常释放见summary。P2-b2只读递归预检工程已验，P2整体/导入仍进行中，P2-env受阻、P1 NIfTI已验、P3/P4待实施、E5受阻/E6进行中，R1待核查/R2–R4待实施。无反馈、不改REVIEW_FEEDBACK、不提交/发布。

新增services/dicom_preflight.py、tools/audit_dicom_preflight.py及tests/test_dicom_preflight.py：完整Part10/FileMeta/所有SQ/像素后属性，64MiB/10000元素/24层/1000命中上限，禁止重写/上传，报告/终端不输出字段原文。来源及像素review绑定SHA与UID/声明，标记嵌套ID/姓名/私有/日期文本/opaque/未知引用/烧录与缺复核；复用经典非MOSAIC布局/像素长度。archive_eligible、deidentification_complete恒false，自填manifest/review不等于独立认证或入库许可；可通过工程规则仍不能直接归档。标准FileMetaVersion精确例外与嵌套ID/加密SQ绕过保护已回归，初次标准版本误报日志保留。

官方PyPI固定pydicom3.0.2纯wheel2376822字节，发布SHA abf971a5440f84dbaf42c4b6758e30e62480902584f8b270b9a5d146e278a07b；E盘缓存、现用Python离线no-index/no-deps/no-compile只加一包，285个安装payload与wheel一致、所有旧包版本不变、torch2.11.0+cu128/CUDA正常。新增requirements-dicom-preflight.txt哈希锁，不改worker/PATH/系统证书/其他prefix，不重建旧环境。发行元数据license字段空，原LICENSE文本保存，不自行补SPDX。

最终134后端/4既有警告，34新合成Part10行为加100相关回归；真CLI拒绝/不覆盖、深层姓名ID/私有/引用/像素后字段/压缩/哈希/限制与脱敏。实际UPENN原候选复用，扫描169元素/83命中、退出3/rejected，33private等可能同标签多规则，不能称83项已证实泄漏，原SHA bd75b6ee1175a26d0b505035da1694a2c928c7c1a53344444b24b2ca8fc11443不变；没有像素review、不伪造医生或批准。state-validation原14表全行与上轮已验副本、科学/featurejobs SHA相同。无API/前端业务改动、不重启、不重复构建/浏览器/整包审计或推理/提取。

有限来源查找：TCGA-GBM一个候选ID和公开患者索引HTTP200空body，未取得患者/影像；两次无进展转查官方来源，不反复相同查询。Brain-Tumor-Progression索引也空，官方集合明确NIH受控申请，不下载或联系发布者；TCGA详情直接读取500，不仅由空body推断原因，未取得状态保持，无旧镜像/受限token尝试。空响应不是有效JSON或下载成功，本轮没有新DICOM下载。具体P2_DICOM_PREFLIGHT_VALIDATION。


## 以下为之前窗口的历史记录

最新08:11：radiomics311-delivery-20261010T081105_95f1c109-independent，3.11.17/NumPy1.26.4/SimpleITK2.5.2/PyRadiomics3.1.0，20Conda/11wheel/15元信息/pip check与1102导入文件及两解释器二进制匹配。默认引导不借旧工程pip/原worker；新来源gate未验，现用worker与CUDA53包不改。120后端/4警告、独立CPU解释器10行为通过；77440693为缓存文件量而非流量，无新下载。见RADIOMICS_DELIVERY_BOOTSTRAP。

最新07:05增量：独立E:/BrainFusion-Runtime/envs/node24-delivery-20261010T070557_2d087f2d实际Node24.21.0/npm11.19.0，官方ZIP37618919字节/SHA与LICENSE SHA；396真实包缓存67060361字节/SRI/身份/冻结来源吻合、26跨平台optional未装。只核对许可元信息、没有数字签名/漏洞/再分发认证。原Node/前端依赖仍保留，6项主要库旧/新实际版本相同（Vue3.5.41/Router5.2.0/Vite8.2.1/PluginVue6.0.8/CompilerSFC3.5.41/Axios1.19.0）；不是把package.json范围当实测版本。禁install脚本，全新目录，E盘缓存/TEMP、非全局PATH；实际8012构建/HTTP重启浏览器与原开发回退通过，详FRONTEND_DELIVERY。默认CUDA主53包/CPU工作器不变，历史原来源未知事实不补造。

06:06历史增量：stdlib独立Conda引导从72项SHA缓存离线新建E:/BrainFusion-Runtime/envs/runtime311-cpu-delivery-20261010T060619_ce64597d，Python3.11.17/torch2.11.0+cpu、完整52项版本和每个实际pip来源SHA与前轮冻结锁一致。新prefix自己的pip，不借工程旧pip，C盘Conda登记SHA相同。新解包副本103后端与11依赖/工作器/模型/谱系前检通过；原树既有CPU候选及现用主各103后端通过。只工程安装/完整性与已有本机兼容，不重新推理或科研结论。52轮子与20Conda源锁迁移见CPU_DELIVERY_BOOTSTRAP；当时Node仅manifest/HEAD与前端422官方元信息/SRI预检，未下载安装；07:05才实际执行独立前端安装/构建，不混淆历史。

05:08历史增量：独立Windows CPU主候选3.11.17/torch2.11.0+cpu安装、完整52轮子与20Conda引导来源/SHA、模型工程对照/双环境92后端/副本恢复及实际服务重启/浏览器/回退已验，详见CPU_RUNTIME_CANDIDATE。本机默认仍旧CUDA主环境，53包元信息/旧CPU特征工作器保持不变；历史主安装来源缺口仍未知。下方02:07是历史观察，不代表本轮未执行候选安装。新候选不等于异机/Linux/所有依赖长期维护或临床认证。

更新：2026-10-10 02:07窗口，run_id20261010T020814_85dc6dc0。只读核对已安装元信息，没有安装、升级、卸载或CUDA推理。当前运行配置仍上一轮runtime-supported.json。

| 清单 | 实际角色 | 使用边界 |
|---|---|---|
| backend/requirements.txt | 历史扩展依赖表，UTF16原件保留 | 不是本机实测锁；列torch2.13.0/monai1.6.0/joblib1.5.3，但现用2.11.0+cu128/1.5.2/1.6.0；许多扩展未安装。不得为安装成功全量升级当前环境 |
| requirements-core.txt | 11项Web/影像直接依赖，本轮均与已安装版本一致 | 不是全部传递依赖或分割/研究/特征就绪证明 |
| requirements-research.txt | core加5项研究/测试声明，本轮逐项一致 | 不自动安装正确CUDA轮子或PyRadiomics，未列全部间接包 |
| requirements-local-validated.txt | 16项本机必需直接包的观测摘要 | 不含CUDA torch/torchvision、不是哈希锁或新机器安装成功验收 |
| requirements-radiomics-supported.txt | 受支持Windows独立CPU工作器版本摘要 | 源码轮子/20Conda/10PyPI URL与SHA完整锁在上轮dependency-locks-complete，不能普通pip替代构建 |
| requirements-radiomics-worker.txt | 旧3.9归档兼容环境 | 不作为新部署的支持解释器，不改旧环境来“修复”清单 |
| frontend/package-lock.json | 前端已保存依赖解析 | 本轮前端构建与基础浏览器检查使用既有E盘依赖；不等于新机器或Docker安装实测 |

主环境实际Python3.10.21、torch2.11.0+cu128/torchvision0.26.0+cu128、MONAI1.5.2、joblib1.6.0；主pip check通过，53个已安装包元信息保存于本轮environment-inventory/inventory.json和installed-main-snapshot.txt。核心11项/研究5项与元信息一致；历史全表仅29项精确匹配，其他为版本不同或未安装，完整差异留档。

历史主环境的原安装URL/发行文件SHA没有全部记录，明确未知，不能根据版本号编造来源或把pip freeze当供应链锁。本轮不改变主3.10生命周期风险；源包候选不包含任何Python环境。新主环境应独立候选/官方来源/锁定CUDA发行/实测模型与研究版本后再切换，不在本轮执行。CPU特征环境已验收的支持分支也不等于所有固定依赖获得长期维护或临床认证。

工具backend/tools/capture_environment_inventory.py默认使用当前运行解释器，只写全新E盘证据目录、对照清单并执行pip check，不安装依赖。它记录的是观测状态，不将差异自动改成安装指令。当前启动前检、模型/数据来源和成功产物恢复仍见LOCAL_RUN、SYSTEM_BACKUP_RESTORE；Linux容器依赖与特征工作器仍需E5实测。
