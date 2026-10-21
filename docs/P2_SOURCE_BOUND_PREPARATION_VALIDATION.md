# P2 公开MR准备与像素技术复核绑定

2026-10-14，北京时间23:12开始；run_id `20261014T2313_p2review`。本批修复准备工具把“看过六张联系表”固定写入任意资料的问题，并验证真实准备→隔离登记。P2整体仍进行中，P3真实四序列仍受阻。

## 实际改变

原工具只检查集合名/许可，未将公开来源的患者、Study/Series、份数与实际输入逐份核对，也没有核验技术复核对应的像素。现将集合名解耦，仍仅接受明确记录的CC BY 4.0公开经典MR；使用现有元数据派生、像素和成组空间契约，不扩大到MOSAIC、多帧、压缩或自动配准。

新增渲染工具为每份源DICOM保存文件名、大小、SOP UID和SHA，绑定来源记录原字节SHA。全部源文件按文件名顺序放进原像素大小的联系表，序号写在像素外；这不是临床切片排序。固定一次源窗、逐实例应用原rescale，MONOCHROME1反相显示。每张PNG记录SHA及覆盖的源文件；渲染前后核对来源。空模板的复核者、时间、已查看表和观察结果不能作为通过。

准备工具要求显式来源、渲染目录和技术复核记录。逐份核对患者/Study/Series/FileMeta SOP、份数、原字节、完整覆盖、PNG和复核时间，再生成新UID的元数据派生副本；原像素/几何不变。报告v2附带完整`review-evidence`：来源JSON、渲染清单、明确复核记录和全部PNG，复制到新目录仍可核验，不依赖原审核文档绝对路径。新登记必须使用v2和其内置复核记录；导入服务在首次归档写入前及末核阶段校验该包。

既有已固定SHA的历史登记、原报告及病例19保持原样，不重写旧的技术观察。仅历史登记继续兼容旧报告；新登记不能借用旧无绑定的准备流程。技术记录由本机操作者提供，SHA用于一致性，不是发布者签名、独立审核者身份认证或临床脱敏保证。

## 使用顺序

在backend目录，先执行`tools/use_e_drive.ps1`，使用现有主Python。下例路径需换成已核实来源；输出目录必须全新、在E盘、与原件分开。

```powershell
python tools/render_public_mr_review.py --source-dir E:/资料/instances --source-record E:/资料/source-manifest.json --output-dir E:/复核/本次
```

实际查看所有联系表后，把`review-template.json`另存为`technical-review.json`，填写真实复核者、带时区的RFC3339时间、全部`sheets_checked`及观察范围。只有实际未见身份文字时才填写`identifying_text_observed: false`；不能把模板或历史其他序列的观察套用过来。临床认证字段保持false。工具支持Windows七位小数时间，精确到微秒比较。

```powershell
python tools/prepare_public_mr_viewing.py --source-dir E:/资料/instances --source-record E:/资料/source-manifest.json --review-dir E:/复核/本次 --review-record E:/复核/本次/technical-review.json --output-dir E:/BrainFusion-Data/PACS-derived/新资料 --patient-id BF-PACS-LOCAL
python tools/register_pacs_import.py --directory E:/BrainFusion-Data/PACS-derived/新资料 --review-record E:/BrainFusion-Data/PACS-derived/新资料/review-evidence/technical-review.json --label 公开MR派生资料 --acknowledge-source-and-pixel-review
```

来源记录格式沿用已核实的`collection/collection_doi/expected_instances/source`；`source`包含`Collection/PatientID/StudyInstanceUID/SeriesInstanceUID/Modality/ImageCount/LicenseURI`。这些记录不自动证明授权；使用前仍须核实官方来源与处理说明。迁移或备份新登记资料时，保留整个派生目录、`review-evidence`及私有UID映射，另保留原件与下载来源材料；不能只复制DICOM或登记JSON。

## 本次验证及证据

证据根：`E:/BrainFusion-Runtime/results/nightly/2026-10-14/20261014T2313_p2review/`。

- 新17项加既有导入11/派生6，最终一次34项通过；4条既有FastAPI/Starlette弃用警告。最后仅收紧复核字段类型后，新17项重验通过。覆盖源患者/Study/Series/份数/许可不匹配、字节或来源记录变化、PNG替换、漏看、重复覆盖、过早时间、发现身份文字、模板拒绝；独立像素显示对照、可重定位证据包和真实本地HTTP合成导入/变更后零POST均通过。合成来源明确命名，不当真实采集证据。
- 真实已取得的UPENN-GBM 192实例被新工具重新渲染，六张新表逐张技术查看；未见身份文字，仅Codex AI在一个记录窗的观察，不是医生认证。新派生验证目录`E:/BrainFusion-Data/PACS-derived/20261014T2313_p2review_validation/`，全部192源SHA与先前审计及当前源件相同，全部原像素/几何保留。新CLI只写本run隔离登记`isolated-registry.json`，不加入日常候选、不产生新归档实例/病例/模型输入。`real-validation.json`记录实际校验。
- 源192、原派生192、原登记及固定旧复核文档均未变。14表逐行摘要与启动前备份完全一致。没有新导入、关联、推理、提取、训练、PDF或依赖安装。未用新v2资料重做真实Orthanc导入，不能把合成协议导入等同该分支实测。
- 首次真实准备暴露Python3.10不能直接解析Windows七位小数时间；保留`real-prepare.log`，修复RFC3339解析和两项Windows时区测试后`real-prepare-final.log`通过。首次批量补丁因同文件重复操作被工具整体拒绝，拆分后实施，无部分改动。
- 开工发现旧登记的三项服务与开发锁owner/holder均已不存在。核对旧PID与端口、独占探针后按相同机制获锁；先备份业务库，复用既有脚本恢复原目录服务。首次启动调用误传平铺路径JSON被拒，未启动应用；改成标准`format_version/paths`格式后成功。归档没有重复启动。未安装或重试历史被拒环境动作。
- 恢复后API归档ready、原成功回执192/192、病例19的192实例view-manifest可读。只读浏览器显示原回执、未确认时导入按钮禁用、实际查询200，pageError0/写请求0；`resumed-ui.json`和`resumed-import-panel.png`已保存并查看。没有重新加载全部帧或测量，沿用之前相应历史验收。

当前后台18656/前端23464启动UTC15:26:27.8783976Z/15:26:27.8857243Z，Orthanc20388启动UTC15:25:34.0766139Z。地址仍为5179/8012/8042；以两份process登记和实际进程为准。无运行中的下载/训练/推理/导入。

## 抽查与剩余

1. 打开`http://127.0.0.1:5179/case/19`，归档面板仍只有原192层候选和原成功回执；新验证副本不出现在页面。
2. 点击“查询检查”，应取回原归档；无需重复导入。截图见本run的`resumed-import-panel.png`。
3. 查看新派生目录的v2报告及`review-evidence`，核对不是固定“六张”字符串或空模板审批。
4. 查看`preparation-tests-final.log`、`preparation-review-final-strict.log`和`real-validation.json`，区分合成协议、新真实准备、历史真实归档证据。

P2仍限定明确登记的公开经典MR派生资料；任意浏览器上传与自动像素脱敏不在已验范围。P3没有获得匹配四序列；当前单序列约0.9766/0.9766/1mm且轻微斜位，不满足现模型1mm/轴对齐契约，不能靠补标签或放宽空间检查通过。22:16被中断窗口对另一患者的单次元数据请求遇到TLS EOF，未取得新数据；本批没有重复探测。后续优先对P4尚未覆盖的真实DICOM工具/版本与报告集成动手，遇到新的可审计四序列解除条件再恢复P3，不重复本192导入/原PDF/来源探测。
