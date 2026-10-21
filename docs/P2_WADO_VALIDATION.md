# P2 WADO 单帧读取与真实候选数据核查

北京时间2026-10-13 00:21窗口（对应10/12晚至10/13凌晨），run_id `20261013T002126_88fd439c`。UTC开始2026-10-12T16:21:26.4921910Z，FileShare.None holder/owner19652、原生16:21:26.0976807Z。P2-b1受限WADO工程小批次已验收；P2整体进行中、真实归档未部署。候选数据仅核查，不是脱敏导入、原始采集四序列或DICOM阅片验收。

## 实际变化

- 新增`GET /pacs/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/metadata`，返回标准`application/dicom+json`数组，不使用业务包裹。精确验证Study/Series/SOP UID、经典MR SOPClass/ImageType/FrameOfReference、有限LPS位置、正交单位IOP、正PixelSpacing与像素布局。保留方向/毫米值及DS顺序，没有重采样或自动空间校正。仅返回受检字段，患者姓名/ID、私有标签、自由描述和归档BulkDataURI不转发。
- 新增该实例`/frames/1`。仅经典非MOSAIC单帧MR、单通道MONOCHROME1/2、8/16位低位对齐、最大32MiB；明确拒绝增强MR/多帧/MOSAIC、其他像素布局或不合法几何。向归档请求未压缩Explicit VR Little Endian，严格验证唯一完整multipart part、编码、字节长度和头部上限；拒绝截断、额外字节、多part、JPEG/大端/base64、重复MIME或额外HTTP压缩，不补齐或截断。输出重新构造单part响应，不转发上游Location/ContentLocation、Cookie或凭据。
- 私有配置可选`allow_pixel_read`严格布尔值，**默认false**。关闭时像素请求在连接归档前503/pixel_read_disabled，元数据不提供PixelData URI；开启后仅生成本站受限frame URI。`/pacs/status`增加pixel_read_enabled（配置开关，不是实际像素能力验收），dicom_view_available和ai_bridge_available仍false。正式配置文件没有创建。后续只有完成合法来源/原文件/私有嵌套标签/烧录文字核查后才能为该本地归档显式启用，不能仅凭头部声明放行。

协议依据：[DICOM PS3.18检索资源](https://dicom.nema.org/medical/dicom/current/output/chtml/part18/sect_10.4.html)、[JSON模型](https://dicom.nema.org/medical/dicom/current/output/chtml/part18/sect_F.2.html)、[Bulk Data编码](https://dicom.nema.org/medical/dicom/current/output/chtml/part18/sect_8.7.3.3.html)。选择单帧未压缩边界；没有增加压缩解码器、多帧解释、自动配准、修订mask或AI桥接。脱敏不能由筛选显示字段替代，[PS3.15保密规范](https://dicom.nema.org/medical/dicom/current/output/chtml/part15/chapter_E.html)仅用于后续核查方向，本批不宣称完整profile合规。

## 实际公开数据：一个受试者清单、一个候选实例

[TCIA UPENN-GBM官方页面](https://www.cancerimagingarchive.net/collection/upenn-gbm/)列出的Version2数据，DOI `10.7937/TCIA.709X-DN49`；使用[官方公开NBIA v1接口](https://wiki.cancerimagingarchive.net/display/Public/NBIA%2BSearch%2BREST%2BAPI%2BGuide)，没有账号/受限token、付费或联系发布者。查询匿名ID UPENN-GBM-00001后实际返回六个MR序列、六个不同Study UID，许可各为CC BY4.0。匿名ID最初作为查询候选，只有返回记录核对一致后才作为来源；不制造受试者或标签。

四个序列描述含Processed_CaPTk，其他两个描述为灌注/扩散；描述仅用于候选核查，不赋T1c/T1n/T2w/FLAIR模型身份，不把处理后DICOM称为原始采集四序列。完整返回清单、URL、HTTP状态在本run/tcia-series-candidate.json与tcia-query-status.json。没有下载四个处理序列或全队列，没有恢复研究测试身份。

选择一个扩散候选序列，SOP清单返回78对象。源清单总量125,537,564字节，单实例均量约1,609,456；计划只取一个，传输硬上限8MiB、磁盘512MiB余量检查，实际约416GB空闲。GET单实例成功，1,609,460字节，ContentType application/dicom，Part10 DICM标记及现用SimpleITK/GDCM可读取，实际三个UID及患者匿名ID与公开清单一致。下载不执行任何数据集代码；partial保留/Range恢复路径已实现但本轮未实测中断恢复。SHA是本地校验值，未取得官方该单实例SHA，不能称与发布端哈希逐项相符。

| 来源字段 | 实测 |
|---|---|
| 来源匿名ID | UPENN-GBM-00001 |
| Study UID | 1.3.6.1.4.1.14519.5.2.1.193084931700557478622366870650889741468 |
| Series UID | 1.3.6.1.4.1.14519.5.2.1.40067253395349591373441931744246881031 |
| SOP Instance UID | 1.3.6.1.4.1.14519.5.2.1.41695845638989036675068252022560298539 |
| 许可 | https://creativecommons.org/licenses/by/4.0/；须保留来源/数据集引用 |
| 文件位置 | E:/BrainFusion-Data/PACS-candidates/UPENN-GBM/20261013T002126_88fd439c/single-instance.dcm |
| SHA256 | bd75b6ee1175a26d0b505035da1694a2c928c7c1a53344444b24b2ca8fc11443 |

这是官方实际发布的DICOM候选，不是本项目从NIfTI生成的示例；**原始采集谱系尚未验收**。GDCM读出SIEMENS、经典MR、ImageType声称ORIGINAL/PRIMARY/M/ND/MOSAIC；头部ORIGINAL单独不作为谱系证明。实际896×896×1拼块、reader spacing2.34375/2.34375/3mm，不能当普通3D切片或满足本模型四序列同网格1mm契约。新运输检查对该真实头部明确422/unsupported_mosaic；此验证仅将真实头部读成最小协议对象执行拒绝，**不是实际Orthanc/WADO请求**。

PatientIdentityRemoved=YES；PatientName非空但等于公开匿名ID，报告只记录比对布尔值，不输出原字段；33私有标签，BurnedInAnnotation缺失。GDCM头部检查不能遍历证明全部嵌套属性安全；未做完整私有/嵌套/像素文字复核。文件只读留候选目录，未改写或导入正式库/归档/科研队列。解码SHA只用于读成功诊断，GDCM可能自动应用rescale，不当作原WADO字节。所有原文件SHA再次核对一致。

首个下载helper主动不用Windows常规代理路由导致TLS握手失败；改用和成功元数据请求一致的系统默认网络路由后成功，仍正常验证证书，未禁TLS/改CA/系统代理。两日志/失败记录保留。这是数据读取的新授权动作；没有重新下载/运行此前被自动审批拒绝的Orthanc候选。

## 验证与证据

证据根`E:/BrainFusion-Runtime/results/nightly/2026-10-13/20261013T002126_88fd439c/`。

- `backend-accepted.log`：100 passed、4既有弃用警告。35新增WADO检查及原PACS31/相关NIfTI与测量/配置/API回归。真实本机TCP合成协议：16位signed字节及末尾CRLF保持、8位unsigned/MONOCHROME1无隐式反相、rescale元数据保持、外部URI不转发、默认关闭、各不支持/破损数据明确拒绝。没有真实Orthanc响应、压缩/多帧或真实DICOM浏览器验收。
- `database-backup`先只读快照/恢复，`restore-validation.json`恢复副本启动和新WADO不可用语义及原API；正式重启前无活动任务。`original-accepted.json`全部14表全行/科学参考MRI-mask/所有featurejobs文件SHA相同，原关联表仍空，新候选SHA不变。没有新增数据库结构/病例/研究结果。
- `browser-wado-boundary/validation.json`实际服务重启后两个新端点503/no-store、pixel flag false、病例原UI仍明确未配置，NIfTI Cornerstone三canvas正常，页面异常/写请求0；状态截图已查看。前端未改业务组件，本轮不重复构建/安装或生产打包，上轮实际8012生产证据保持历史。
- `single-instance-download-plan.json`、`single-instance-download.json`、TCIA系列/SOP原响应及各query URL；`candidate-inspection.json`/log；`real-candidate-guard-validation.json`/log，全部区分来源核查、实际头部拒绝和合成运输测试。早期62/96/99测试是新增检查前的历史，最终100。
- 本轮原有PyDicom不存在，未为此安装新依赖；复用现有SimpleITK/GDCM做有限候选诊断，不将其冒称完整DICOM脱敏审计。检查脚本在下载首败时误调用、文件不存在日志保留，随后成功下载才重新执行实际读取。

当前服务backend34700 UTC2026-10-12T16:43:06.8049752Z，frontend22108 UTC16:43:06.8122342Z；5179/8012，日志Runtime/local/{backend,frontend}.{out,err}.log，登记Runtime/local/processes.json。原01:06运行配置/数据库/工作器/gate与00:06模型/上传/数据/研究保持。无下载/推理/训练/构建长任务，未提交/推送/发布；锁正常释放/耗时见summary。

## 抽查与接续

1. 打开`http://127.0.0.1:8012/pacs/status`：应unconfigured、pixel_read_enabled=false、dicom_view_available=false。
2. 打开`http://127.0.0.1:8012/pacs/studies/1.2.3/series/1.2.4/instances/1.2.5/metadata`或`/frames/1`：均503/unconfigured，不能返回伪影像。
3. 打开`http://127.0.0.1:5179/case/17`：归档明确未配置，不出现候选DICOM关联。
4. 打开`http://127.0.0.1:5179/workstation/17?viewer=cornerstone`：已有真实NIfTI三视图仍正常。

下一轮先锁/反馈/服务身份并复用34700/22108；继续P2脱敏导入预检契约（可递归标签审计、私有/像素复核、原文件保留、明确不支持拒绝），选择有限非处理/非MOSAIC的经典MR来源支持真实阅片样本；不扩下整125MB扩散或全队列，不默认开启像素，不把Processed_CaPTk自动映射四序列。实际Orthanc环境仍受上轮自动审批阻塞（下载+版本执行，仅blocked by policy），未重试/绕过、不需用户重复授权。P2真实归档/导入/持久化、P3可审计转换与匹配四序列、P4联合恢复/性能/PDF、E5/E6/R余项仍未完成。
