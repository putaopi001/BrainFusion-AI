# B1 四序列角色审核接口：工程验收与边界

运行批次：2026-10-17 20261017T1140_b1roles。此批实现受版本绑定的角色审核API和E盘追加审计日志；没有把审批接到MRI当前输入或AI执行器。

## 实现行为

- GET /pacs/cases/{case_id}/conversions/{version_id}/role-review读取锚定的转换声明，列出T1c、T1n、T2w、FLAIR四个唯一映射、Study/Series UID、元数据版本、FrameOfReference、几何摘要及角色声明证据。响应不返回本机路径或像素。
- POST只接受approve/reject、当前plan revision、四角色集合摘要和明确确认。要求现有本地医生角色会话；记录账户ID/用户名、决定、时间以及转换报告/提案/快照SHA。声明或版本改变时拒绝旧确认。
- approve先要求本地转换完整性通过，再通过既有来源核对核实当前归档实例字节及序列元数据；缺失/陈旧/不可用时不写审核记录。合成夹具不能获真实角色审批。
- 审核历史写入与索引并列的E盘dicom-conversion-role-reviews.json，追加JSON事件以临时文件原子替换；损坏、超限、写失败不覆盖历史。审核记录明确标示本地账户角色，不证明专业资质。
- 批次没有新增数据库表或修改正式病例/MRI。返回值始终为model_input_eligible=false、current_mri_replaced=false；没有激活AI。

## 验证

定向命令：从E:/BrainFusion-AI/backend运行主解释器 -B -m pytest tests/test_dicom_role_review.py -q，退出码0，3 passed，4既有依赖弃用警告。正向归档回执由测试替身提供，身份使用测试依赖覆盖；它验证API核对/持久记录路径，不是本机真实DICOM来源或真实登录的端到端验收。另有真实HTTP未认证401、旧摘要先于归档读取被拒绝、合成角色审批被拒绝、MRI/PACS数据库行数不变的断言。具体日志与各次迭代失败保留在E:/BrainFusion-Runtime/results/nightly/2026-10-17/20261017T1140_b1roles/，最终日志role-review-tests-final.log。

## 未完成及下一步

- 这是B1后端审核组件；尚未将审核流程接入现有PacsPanel的可见交互，因此当前网页不能直接执行此审核。
- 真实DICOM四序列身份/像素来源审核未执行，当前正式转换登记是否存在匹配样本需实际准备；不能用协议夹具替代。
- B2转换作业与审核后原子激活尚未实现。审核决定不会改当前NIfTI/MRI、旧分析、特征或报告。
- 现运行后台服务按本轮前已有健康状态继续；没有为热加载本批新代码重启服务。API部署可用性需正常受控后端重启后核对。

后续先在同一PacsPanel接入本地账户状态/角色确认界面并做真实浏览器交互验证，然后才推进B2转换作业/激活。真实四序列不足时，B4保持待真实样本验证。

