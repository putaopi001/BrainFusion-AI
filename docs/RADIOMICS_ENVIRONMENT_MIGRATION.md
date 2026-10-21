# E4受支持特征环境迁移工作台

08:11新增独立worker离线引导RADIOMICS_DELIVERY_BOOTSTRAP，20Conda/11wheel/15元信息/1102导入文件与原已验worker匹配；标准库入口不借旧工程pip/原worker存续。现用01:06源/科学gate不变，新prefix为未切换候选，不能冒用旧来源身份或将安装证明写为新特征/概率复验。

更新：2026-10-10 01:40北京时间；E4本机Windows CPU环境已验收。最新run_id：20261010T010640_a6ee8135。历史“未安装”记录以下按时间区分，不代表当前状态。

## 当前已验收环境和范围

独立工作器已切换为E:/BrainFusion-Runtime/envs/radiomics311-candidate/python.exe：Conda-forge CPython3.11.17、NumPy1.26.4、PyRadiomics v3.1.0、SimpleITK2.5.2。主Python3.10.21/torch2.11.0+cu128不升级，CUDA导入/可用性检查通过；旧radiomics39环境和结果保留。Python分支生命周期的“受支持”不表示所有固定依赖仍有上游长期维护保证，也不是临床或安全认证。

证据根（下文R）：E:/BrainFusion-Runtime/results/nightly/2026-10-10/20261010T010640_a6ee8135。

- candidate-reference-gate-complete/compatibility.json：原五参考病例4/13/16/17/19，相同MRI/mask/参数/模型/归一化协议；55个有限特征逐项与旧重提取直接比较，最大绝对差0，五个旧重提取概率最大差0；252项归一化检查、空区域null规则通过。没有改变extract_selected_radiomics.py、feature_contract.py、分类模型或标签。
- automatic-supported-complete/validation.json及completed.json：病例17实际CPU自动掩膜提取，20特征、五种概率与旧任务差0；1.763秒为该次提取内部时间，不含HTTP/启动，也不是性能保证。新工作器来源生成新任务c913b7963dbe4d9e8014ea6487069946，不误用旧工作器缓存；重复请求同ID。临床仍57岁male、原分割/研究版本不变。
- restarted-supported-complete/validation.json、supported-browser-complete-final/validation.json：实际停启后全部18病例/原库和副本逐行/报告/确认/临床/标注/意见一致；新任务科学输出与谱系恢复，重复提交只更新访问时间不重新提取。四序列三视图真实切片/叠加、研究结果与报告页面通过；研究和FLAIR截图实际查看。五个当前性别未知的旧演示病例POST无body返回409，不用旧归档年龄覆盖患者资料。
- immutable-cuda-audit-complete/validation.json：638原件及快照SHA一致；旧特征文件、副本中旧任务、旧解释器/协议不改，主CUDA可用。75后端/2基础浏览器/构建通过，4后端弃用警告及大块构建提示保留。

以上是工程环境兼容验收，不是全队列/自动掩膜分类重拟合/外部评价。病例17来自既有公开开发样本，不增加独立研究患者。Linux/容器工作器未验，归E5；主3.10生命周期风险尚未解决，不能说全系统运行时均已升级。

收尾pip check发现ruamel.yaml0.18.6需要间接依赖ruamel.yaml.clib；已从[该项目PyPI0.2.12原发行](https://pypi.org/project/ruamel.yaml.clib/0.2.12/)安装cp311 Windows原轮子并锁定URL/SHA/大小/许可。原九依赖来源档案先保存为candidate-provenance-before-clib.json，随后记录补依赖的新source.json并重跑五参考/自动任务/实际重启/浏览器/原件CUDA审计，最终pip check无破损依赖。早期candidate-reference-gate、automatic-supported-no-body、restarted-supported及其截图仅为补依赖前历史，不作最终当前门槛；新的complete目录才是当前证据。未修改提取参数或放宽容差。旧radiomics39本身没有pip，检查输出保留，不给旧环境安装pip。

## 源码构建与可维护来源

没有找到现成cp311 Windows官方PyRadiomics3.1.0轮子后，使用[Zig官方0.15.2](https://ziglang.org/download/0.15.2/zig-x86_64-windows-0.15.2.zip)便携C编译器，不需要MSVC安装、UAC或重启。下载前估计127075807字节源码/工具包、37MB解释器包及2GiB构建空间；所有缓存/工具链/候选/构建输出在E盘。源码来自[PyPI3.1.0发行](https://pypi.org/project/pyradiomics/3.1.0/)，SHA24722c962a6bbd09bc39c1c67dbffe92435f9692a421fabaae8a6b4511eb48e4；Zig ZIP SHA3a0ed1e8799a2f8ce2a6e6290a9ff22e6906f8227865911fb7ddedc3cc14cb0c。编译器许可和PyRadiomics BSD-3-Clause原文保留。

SDist缺cmatrices.h/cshape.h；补取其版本记录的上游提交6a761c4eb01905cfcb1139b0b158547c55edd4df，验证Git blob与SHA256，并确认四个C文件和SDist字节相同。头文件放独立证据目录，没有修改源码。C扩展使用x86_64-windows-gnu/O2、无fast-math，链接候选Python库；只构建原扩展，不执行数据集脚本。轮子cp311-cp311-win_amd64，SHA b1cd96b3c0cad43226fb0d7e39d49cb4cafee28b1594b29050abf358646e96e4（R/native-build-record-fixed）。这是本机原源码构建产物，不冒称上游官方发布轮子。

完整20项Conda构建/URL/大小/SHA/许可、10项PyPI元信息、编译命令/C源码哈希/扩展哈希/轮子记录在候选source.json；它是门槛指纹的一部分，验收后不改。R/dependency-locks-complete补官方PyPI文件大小/来源并导出conda-explicit.txt、pip-dependencies.txt、pyradiomics-wheel.txt。20项Conda显式URL/SHA通过本机Conda解析；没有再建第二套解释器。requirements-radiomics-supported.txt是版本摘要，不能直接用普通pip安装来替代源码轮子/完整来源锁。

## 复建流程（新唯一候选，不覆盖当前或旧环境）

1. 获取统一开发锁；确认没有GPU/提取/下载任务，设置tools/use_e_drive.ps1的E盘缓存。Conda设CONDA_PKGS_DIRS/CONDA_ENVS_PATH到E盘、CONDA_REGISTER_ENVS=false、CONDA_NUMBER_CHANNEL_NOTICES=0，不写C盘用户环境登记。
2. 在全新E:/BrainFusion-Runtime/envs前缀，按dependency-locks-complete/conda-explicit.txt创建精确环境（--file、--no-default-packages、--no-shortcuts）；隔离解释器用pip --no-deps --no-compile --require-hashes安装pip-dependencies.txt。docopt源包构建过程会使用构建工具，不向主环境安装。
3. 可复用记录的已校验本地轮子；若重新源码构建，依次运行tools/fetch_radiomics_build_sources.py --help、fetch_radiomics_headers.py --help、build_radiomics_candidate.py --help，在全新--output提供冻结元信息/SHA、sources.json、headers目录、依赖报告和候选python。下载支持.part续传；已有编译器树必须每文件与校验ZIP相同才复用；不覆盖未完整/不一致树。完整原命令见R/native-build-record-fixed/build-plan.json。最终通过后用lock_radiomics_candidate.py导出新来源锁。
4. 新worker/source.json就绪后重新执行下方五例门槛，--worker候选、--baseline旧保留门槛、--data-dir原MRI队列、--research-dir固定模型；成功才在独立DB/任务副本切换runtime.json。不要把旧source.json路径信息盲复制当新环境来源，也不要修改compatibility.json绕过检查。
5. 实际自动链路/重复缓存/临床缺失/重启/浏览器回归通过后保留旧环境回退。当前服务复用命令见LOCAL_RUN；回退应先核对空闲/停身份匹配服务，再启动上一轮relocated-runtime/runtime.json，恢复旧DB/旧任务视图，不能声称新环境任务已回到旧库。

尚未在第二台机器重建或Linux容器实测；上述锁和构建步骤是可维护本机来源，不把文档命令当异机验收。

## 00:06窗口历史核查（01:06窗口已完成后续）

当前CPU工作器为独立Python3.9.13、NumPy1.26.4、PyRadiomics3.1.0、SimpleITK2.5.2，旧五参考病例的归档复现证据仍有效。主Python3.10.21/torch2.11.0+cu128仍保持可运行。根据[Python官方版本状态](https://devguide.python.org/versions/)，3.9和3.10已到生命周期终点；不能仅因现有导入成功把它们称为受支持的长期部署环境。主环境升级应另建候选、回归后处理，不在特征迁移时直接升级CUDA环境。

本轮读取[PyPI3.1.0官方发行文件](https://pypi.org/project/pyradiomics/3.1.0/)、[Radiomics官方Conda频道](https://api.anaconda.org/package/radiomics/pyradiomics)，Windows已发布二进制最高到Python3.9，没有找到3.11+兼容包；conda-forge包元信息请求实际404，不能伪称已有包。安装页泛称Python>=3.5并不等于提供所有新版本二进制。元信息原文、URL/字节数/SHA256保存在本轮e4-official-support，查找脚本为backend/tools/probe_radiomics_support.py；没有下载执行未知二进制或改包标签绕过ABI。

本机PATH、标准Visual Studio安装器目录及已检查工具目录未找到cl/vswhere/clang-cl；不据此断言全机不存在编译器。下一步先核对其余现有官方编译工具/SDK。若确需提权安装，记录官方来源、E盘缓存/安装路径与用户动作，不自行绕过授权或重启；可转做E5/E6独立任务。

## 已实施的保护

verify_feature_extraction.py现在必须指定全新E盘输出目录，不再覆盖stage6历史门槛；支持独立候选解释器、数据/研究目录及旧环境基线。--baseline核对数据/模型/协议/契约一致，然后将候选特征与旧环境特征逐项比较，另外比较已存旧重提取概率。仍执行五病例4/13/16/17/19、四序列原归一化/区域体素/空区域及已发表特征检查。没有改extract_selected_radiomics.py或feature_contract.py，没有替换参数/模型/标签。

```powershell
cd E:/BrainFusion-AI/backend
. ./tools/use_e_drive.ps1
../.conda/brainfusion/python.exe tools/verify_feature_extraction.py --help
# 仅当新候选解释器/官方依赖和source.json已就绪，且没有另一提取任务时执行：
../.conda/brainfusion/python.exe tools/verify_feature_extraction.py --output <全新E盘候选证据目录> --worker <候选python.exe> --data-dir E:/BrainFusion-Data/WAW-GliomAI-v3 --research-dir <当前研究模型目录> --baseline <保留的旧compatibility.json>
```

选中特征相对容差1e-5、绝对1e-8，概率差<1e-6；归一化核验沿用旧规则。模型和数据指纹不一致拒绝比较；失败保留结果，不能把当前门槛指向失败候选。运行前核对磁盘、当前工作器任务、源及依赖版本并记录PID/启动/配置/日志。新工作器source.json应记录解释器和每个依赖URL/版本/大小/SHA256、构建工具/命令与许可证。本轮CLI帮助/不覆盖旧门槛/必须显式输出检查通过，不冒称新环境特征或概率已通过。

## 00:06窗口历史剩余门槛（本机E4现已通过）

1. 建立官方来源、版本冻结的Python3.11或更高隔离CPU候选；源编译时记录与旧PyRadiomics3.1.0的确切源码/扩展版本及构建工具。不得静默换提取协议。
2. 与保留旧环境同MRI/mask/参数完成五例特征/概率直接比较；失败定位具体特征，不为通过放宽协议。
3. 候选通过后用新配置验证自动掩膜任务、空区域/失败/缓存/重启一致性，再切换；旧环境/旧结果保留可追溯。
4. 更新可维护依赖清单和部署指南；E5容器CPU路径另行实测。当前没有新环境、没有新提取或训练、不需要用户本轮重启机器。
