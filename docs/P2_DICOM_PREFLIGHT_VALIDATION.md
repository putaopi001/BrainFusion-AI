# P2 递归DICOM入库预检工具验收

## 2026-10-13 02:15窗口（10/12夜至10/13凌晨）

run_id 20261013T021550_d6134bcb；操作系统 UTC 与原生锁进程启动值见 lock-acquired.json，FileShare.None holder/owner18708，session75448；结束/耗时/释放见 summary.json。P2-b3隔离保管工程已验收，P2整体仍进行中、P2-env受阻，P1受支持NIfTI已验收，P3/P4待实施；历史F/E验收保留，E5受阻/E6进行中、R1待核查/R2–R4待实施。无新用户反馈，不改 REVIEW_FEEDBACK，不提交/发布。

预检新增 source_uid_binding_verified：仅校验声明3UID与已读取文件/文件元信息，不等于独立来源核实或归档授权。P2-b3对快照应用预检，候选拒绝仍只能隔离保管；147相关检查通过，详见 P2_DICOM_CUSTODY_VALIDATION.md。原预检历史证据保留。

## 以下为之前窗口的历史记录
北京时间2026-10-13 01:19窗口，run_id20261013T011921_b6663451，系统UTC2026-10-12T17:19:21（精确值见lock-acquired/summary）。独占FileShare.None全程持有。P2-b2只读预检工程小批次已验；完整脱敏、入库放行、真实Orthanc/DICOM阅片和P3/P4没有验收。

## 实际实现

新增backend/app/services/dicom_preflight.py与tools/audit_dicom_preflight.py。输入E盘Part10文件、来源manifest和可选像素复核记录，输出独立JSON；无归档上传、数据库操作、DICOM改写/UID替换或默认像素开启。CLI要求新E盘输出，拒绝覆盖既有报告。

读取完整文件并遍历File Meta、所有Sequence item及后续属性，**不使用stop_before_pixels**漏掉像素后的元素。64MiB输入、10000元素、24层、1000命中上限；不支持的文件压缩传输语法在解析完整dataset前拒绝，不解压或自动配准/重采样。报告只写标签路径/规则原因/严重级别和校验值，捕获pydicom警告只计数，解析错误不输出字段原文。

检查来源文件SHA、三个UID/PatientID是否匹配声明、源URL是否符合本批官方公开NBIA单实例形式及CC BY4.0、File Meta SOP一致性；源manifest与复核记录的JSON格式正确不等于外部来源已认证。标记非空PN（仅根PatientName等于声明匿名ID可作伪名）、嵌套PatientID/OtherPatientIDsSequence、直接标识、私有标签、日期/自由文本/未核引用UID、opaque属性、未知烧录状态与缺少像素复核。处理加密属性Sequence和非零preamble/尾填充，不能靠隐藏在SQ或像素后跳过。标准FileMetaInformationVersion的两个字节仅精确0001放行，不泛化豁免二进制字段。

复用P2-b1经典非MOSAIC单帧MR身份/空间/位布局契约，检查原PixelData长度（合法8位奇数像素可有一个零填充）并记录原PixelData SHA，没有解码成分类输入或修改强度。临床/模型/分割原结果不受影响。

结果为rejected、needs_review、engineering_fixture_pass或preflight_checks_passed。**archive_eligible始终false，deidentification_complete始终false**；后一结果仅指本工具规则未命中。来源manifest/像素review为调用者声明，未独立验证下载事实、操作者权限或像素证据真实性，不能由其自行授权入库。未来导入器必须绑定实际下载来源/许可账本、复核者与证据及同一文件SHA，且独立处理重复UID/不同字节、保存原文件和审计。此工具不是完整PS3.15去标识器或认证。

依据：[pydicom3.0.2读取接口](https://pydicom.github.io/pydicom/stable/reference/generated/pydicom.filereader.dcmread.html)、[Sequence树结构](https://pydicom.github.io/pydicom/stable/tutorials/dataset_basics.html)、[DICOM PS3.15保密规范](https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_E.html)。规范指出属性处理不能替代完整去标识过程，本批按有限规则预检并保留未覆盖事实，不编造医生复核。

## 新增一个必要解析依赖

主环境此前无pydicom。由官方PyPI固定3.0.2（Python>=3.10），下载py3-none-any wheel2,376,822字节，发布SHA256 abf971a5440f84dbaf42c4b6758e30e62480902584f8b270b9a5d146e278a07b核对后，使用现用E盘Python离线no-index/no-deps安装。来源JSON/安装报告/锁见本run与backend/requirements-dicom-preflight.txt。缓存E:/BrainFusion-Runtime/cache/dicom-tools，未增其他依赖/前缀、未动Radiomics工作器或系统PATH/证书。

285个wheel安装payload逐文件匹配，全部既有包版本相同，新增只有pydicom3.0.2；torch2.11.0+cu128/CUDA仍可用。发行元数据license字段为空，wheel含原LICENSE文本（本run pydicom-LICENSE.txt），不把空元信息写成来源未知或自行补SPDX。安装pydicom.exe不在PATH的提示保留，调用Python CLI无需改PATH。此新增依赖是必要解析工作，不是重复安装既有环境或重试此前被拒Orthanc。

## 本轮实际验证

证据根E:/BrainFusion-Runtime/results/nightly/2026-10-13/20261013T011921_b6663451/。

- backend-accepted.log：134 passed/4既有弃用警告，34新预检行为及100相关PACS/WADO/测量/序列/配置/API回归。明确合成Part10夹具：多层姓名/私有/嵌套ID/引用、加密SQ、像素后属性、preamble、压缩/截断、来源与review版本、限制、真正CLI退出/不覆盖、输出/终端无敏感原文；合成成功不冒称真实人群或临床放行。
- real-candidate-preflight-final.json/log：复用上轮官方UPENN-GBM单实例，真实CLI退出3/rejected、archive_eligible=false，扫描169元素、83条规则命中。包括33private、12日期、30文本、3引用UID、其他待核项和MOSAIC，可能同一标签命中多个规则，不是83项已证实隐私泄漏。没有提供像素review，不伪造人或批准。原文件SHA仍bd75b6ee1175a26d0b505035da1694a2c928c7c1a53344444b24b2ca8fc11443。没有新增DICOM下载/归档/病例或研究队列。
- state-validation.json：实际原库14表全部行与上轮已验副本一致，MRI/mask及所有featurejob文件/候选SHA相同；既有主包与CUDA保持、只有上述新库；34700/22108服务身份和复用健康通过，未重启。没有修改前端业务/API路由、模型或提取协议，不重复构建/浏览器或全包来源审计。上轮实际UI/NIfTI浏览器属于历史，不冒称本轮新浏览器验收。
- backend-preflight-initial/positive-diagnostic保留一次保守误报标准FileMetaVersion的失败；缩小日志后修正精确标准例外并加反例，最终134通过。源manifest/复核JSON不自行放行和嵌套ID保护也已回归。

## 下一份真实样本的访问核查

官方公开NBIA v1对TCGA-GBM一个候选ID及患者索引均返回HTTP200空body；没有取得患者或影像，不能把猜测ID写成已确认来源。两次无进展后转查官方访问说明，不继续同一查询或尝试受限token。Brain-Tumor-Progression公开索引也空；[当前官方集合页](https://www.cancerimagingarchive.net/collection/brain-tumor-progression/)明确影像为NIH Controlled Data Access Policy且需申请。该集合不走自动下载、不联系发布者。TCGA当前集合详情本轮直接读取500，不能仅由空返回推断具体原因；维持未取得状态，不改用旧镜像。

查证URL/状态/真实空响应保存tcga-*/progression-*，这些空响应不是有效JSON清单或下载成功。没有下载受控数据，也没有声称所有公开经典MR都无法取得；下一轮从明确可直接访问、许可/谱系已核的有限样本候选继续。Orthanc先前下载+版本执行自动审批仍只给blocked by policy，本轮未重试/绕过；环境解除条件仍是可审核动作/可用已装服务。

## 用户抽查

1. 打开输出的real-candidate-preflight.json：应decision=rejected、archive_eligible=false；findings只有标签路径/原因，不含患者字段原文。
2. 原候选留E:/BrainFusion-Data/PACS-candidates/UPENN-GBM/20261013T002126_88fd439c/single-instance.dcm，文件大小1609460字节；如核SHA应与上述一致，不用导入。
3. 打开http://127.0.0.1:5179/case/17：原归档仍明确未配置，候选没有关联；http://127.0.0.1:5179/workstation/17?viewer=cornerstone是已验NIfTI入口，本轮未改变它。

可复跑只读CLI（输出必须是新文件；拒绝候选退出3是预期）：现用E:/BrainFusion-AI/.conda/brainfusion/python.exe执行backend/tools/audit_dicom_preflight.py，--input取上述候选、--source-manifest取本run/candidate-source-manifest.json、--output取新的E盘JSON路径。没有真实像素复核时不提供--pixel-review；合成测试记录不得给真实候选使用。

下一轮先锁/反馈/34700与22108原生启动身份并复用，继续可信来源/复核与文件SHA绑定的导入账本及UID重复冲突规则；本预检输出不能直接授权归档。有限经典MR来源继续核查，受控集合仅记录解除条件。P2实际归档/脱敏导入/真实阅片、P3四序列转换/模型、P4性能/联合恢复/PDF、E5/E6/R余项仍未完成，无立即用户动作或长任务。
