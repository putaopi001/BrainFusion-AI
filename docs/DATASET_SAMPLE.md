# WAW-GliomAI v3 测试样本

官方链接：https://zenodo.org/records/22205631

DOI：10.5281/zenodo.22205631。发布：2026-09-01，符合当前 2026-10-03 往前两年的条件。最新版本为开放下载，许可 CC BY 4.0；旧版 restricted 记录不作为本次下载来源。

## 下载范围与用途

数据根目录：E:/BrainFusion-Data/WAW-GliomAI-v3，位于 Git 仓库外。

2026-10-03 已完成下载与验证：20 个影像文件和 5 个参考 mask，共 108.81 MiB；完整辅助下载约 5.6 MiB。五例均通过哈希、四序列完整性、shape/affine、有限值、标签和临床 ID 检查。详见根目录 sample_manifest.json 与 sample_validation.json。

- 五个患者：4、13、16、17、19，各四个术前配准序列 T1n/T1c/T2f/T2w。
- 对应人工修订参考分割：label 1 坏死核心、2 FLAIR 异常区、3 增强区；官方 label 4 为切除腔，术前与术后必须区分。
- 完整临床/分子表、变量字典、术前配准影像元数据、术前影像组学表和术前参考 mask 压缩包。

这里是工程 smoke-test 子集，不是完整影像数据集下载，也不是随机/代表性科研测试集。患者按完整序列和 mask 可配对的 ID 升序选取，不可据此宣称泛化性能。

## 模型与参考标签对应

WAW 术前标签为 1/2/3；可在明确记录约定后构建参考区域 TC={1,3}、WT={1,2,3}、ET={3}。不要直接套用其他 BraTS 版本的 ET=4 规则。WAW 的坏死核心描述与其他模型的非增强/坏死核心语义可能存在差异，比较时需披露。

MONAI 备用模型输出三路重叠区域（TC、WT、ET），不是三类互斥整数标签。区域输出、阈值、嵌套修正与 WAW 整数 mask 的转换需单独验证；不能直接 argmax 后套 1/2/3。官方模型通道顺序为 T1c/T1/T2/FLAIR，与归档文件按名称排序不同。

五例工程样本中 IDH 已知阴性 1 例、阳性 3 例、缺失 1 例；缺失用于验证 unavailable 分支，不填造标签。

官方整体文件约 18.2 GB，术前配准影像归档 3,164,137,716 字节。本次通过公开 HTTP Range 下载所选 ZIP 成员，避免为了五例下载全部扫描。辅助文件校验发布方 MD5；选取影像成员校验 ZIP CRC32 并记录本地 SHA256，未校验完整影像归档 MD5。

## 使用与归属

下载和实验使用时引用官方 DOI 和作者；遵循 CC BY 4.0 归属要求。保持公开脱敏病例 ID，不尝试重识别。报告中的 reference 与 predicted mask 必须分开存储、显示和评估。

## 重复下载与验证

```powershell
python backend/tools/download_waw_gliomai_sample.py --output E:/BrainFusion-Data/WAW-GliomAI-v3 --cases 5
E:/BrainFusion-AI/.conda/brainfusion/python.exe backend/tools/verify_waw_gliomai_sample.py --root E:/BrainFusion-Data/WAW-GliomAI-v3
```

下载器保存 zenodo_record.json、image_archive_inventory.json、sample_manifest.json；验证器检查校验值、四序列完整性、与参考 mask 的 affine/shape、有限值、标签集合和临床 ID 匹配，生成 sample_validation.json。验证不会训练模型或把参考 mask 复制成推理结果。

需要完整数据时，按官方记录下载术前配准归档及对应标签即可启动主线，不必先下术后和未经配准的全部影像。公开表的全队列可先用于特征管线开发；正式拆分和预测实验遵循 DATASET_PLAN 与 EXPERIMENT_PROTOCOL。
