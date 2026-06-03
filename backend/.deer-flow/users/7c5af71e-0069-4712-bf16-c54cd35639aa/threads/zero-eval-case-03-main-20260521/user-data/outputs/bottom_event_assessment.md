# Case 03 底事件评估

## 1. 评估范围与方法

本评估针对顶事件“P-3样件中央区域烧蚀异常加深”展开。依据“证据强度 + 机理一致性 + 反证情况 + 复现实验情况”进行定性判断。根据资料限制，当前不给出精确数值概率；仅给出高/中/低倾向、置信度和状态。

顶事件证据：
- P-3烧蚀深度1.42 mm，显著高于P-1/P-2/P-4的0.84/0.88/0.91 mm。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 异常现象；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv
- 设计要求指出，单件烧蚀深度超过同组均值40%时必须归零复核。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/01_design方案.md，章节: 设计目标

## 2. 底事件逐项评估

### BE-01 试前热流计标定异常导致热流判断失真

事实：试前热流计标定偏差为+1.8%。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录。

评估：设计判据要求冷壁热流偏差不超过目标值±5%。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/01_design方案.md，章节: 关键判据。现有标定偏差处于判据范围内，因此不足以支持“热流判断失真并掩盖异常热载”的主因结论。

结论：低倾向，置信度高，状态为 unlikely。

### BE-02 P-3试验期间喷流整体热流超限

事实：P-3暴露期间热流均值2.43 MW/m2、峰值2.51 MW/m2。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。

评估：目标热流为2.4 MW/m2，允许偏差±5%，上限约为2.52 MW/m2。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/01_design方案.md，章节: 关键判据。P-3峰值2.51 MW/m2未见超出该范围，且总结报告明确写明“未超过热流判据”。

反证：同次试验其余样件未出现接近P-3的异常加深。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 异常现象；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。

结论：低倾向，置信度高，状态为 unlikely。

### BE-03 弧电流异常波动导致能量输入异常

事实：P-3暴露期间弧电流最大波动2.2%。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。

评估：资料中无证据表明该波动已构成异常，也无对应喷流超限联动证据。现有证据更支持供能总体稳定。

结论：低倾向，置信度高，状态为 unlikely。

### BE-04 P-3装夹偏角或局部垫片未贴合导致局部入射角异常

事实：装夹偏角记录为0.8 deg，未超过1.0 deg判据。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/01_design方案.md，章节: 关键判据；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。与此同时，试验总结记录“照片显示边缘垫片疑似未完全贴合”，数据备注也出现“right-side shim contact uncertain”和“suspected local gap in fixture photo”。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。

机理一致性：异常样件存在“偏右侧条带状加深”，与局部接触不良、入射角局部改变、边界层受扰后的局部热集中机理相符。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 异常现象。

旁证：历史相似案例已出现过“装夹垫片局部未贴合导致烧蚀条带加深”的情况，但本次尚缺装夹复测和热像证据。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md，章节: 历史相似案例。

反证：现有装夹偏角记录数值本身未超限，且照片证据等级仅为C级。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录。

结论：中高倾向，置信度中，状态为 to_verify。

### BE-05 局部流场扰动在装夹边界处引起条带状烧蚀加深

事实：P-3表面出现偏右侧条带状加深。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 异常现象。

专家意见：试验专家认为，P-3条带状形貌更像局部入射角或边界层扰动影响。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md，章节: 专家复核意见。

评估：该事件与BE-04高度相关，可视为装夹/边界条件异常的机理展开。现有证据能支持其作为强可疑路径，但仍缺原始照片复判、夹具复测或复现实验闭环。

结论：中等倾向，置信度中，状态为 to_verify。

### BE-06 B26-042批次存在系统性材料性能异常

事实：P-3和P-4同属B26-042，但P-4烧蚀深度为0.91 mm，未表现异常。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。

专家意见：若B26-042存在系统性问题，P-4也应表现出明显烧蚀加深。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md，章节: 专家复核意见。

评估：该路径受到直接反证，不支持作为当前首要根因。

结论：低倾向，置信度中，状态为 unlikely。

### BE-07 P-3存在局部密度/孔隙率缺陷等单件材料局部异常

事实：总结报告明确指出材料复检尚未完成密度和孔隙率复测。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录。专家同时指出，局部孔隙率异常仍可能只影响单件样件。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md，章节: 专家复核意见。

评估：该路径与“同批另一件P-4正常”并不冲突，因此不能排除。另一方面，尚无A/B级检测结果支持，当前只能列为待验证的并列原因。

结论：中等倾向，置信度低，状态为 to_verify。

### BE-08 烧蚀深度测量或记录偏差

事实：试验大纲要求每件进行5点烧蚀深度记录，但当前资料未给出P-3五点原始分布、复测记录或测量不确定度。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/02_test_outline试验大纲.md，章节: 数据记录。

评估：由于P-3异常量级较大，且伴随条带状形貌和质量损失5.6 g偏高，单纯测量记录偏差不足以优先解释全部异常。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 异常现象。

结论：待验证，置信度低，状态为 to_verify。

## 3. 当前综合判断

基于现有证据，最可疑路径为：

1. 装夹局部未贴合/局部入射条件异常；
2. 由此引起的局部流场扰动与条带状热集中；
3. 材料单件局部缺陷为并列待验证原因。

不支持优先归因为：

1. 喷流整体热流超限；
2. 弧电流明显异常；
3. B26-042批次系统性失效。

该综合判断与试验总结中的“喷流整体超限可能性较低，P-3装夹局部偏差和材料局部缺陷均需进一步验证”一致。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 初步判断。

## 4. 建议验证项

1. 调取P-3原始装夹照片，做独立复判，并对同一夹具/垫片进行复测，确认是否存在局部间隙或贴合不良。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 未关闭问题。
2. 对B26-042批次，尤其是P-3对应取样区域，开展密度、孔隙率复检。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 未关闭问题。
3. 补做同批次备件复验，并尽量复现原装夹边界条件，以区分“装夹因素”与“材料单件因素”。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 未关闭问题。
4. 复核P-3烧蚀深度5点原始数据和质量损失称量记录，排除测量误差放大。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/02_test_outline试验大纲.md，章节: 数据记录。
