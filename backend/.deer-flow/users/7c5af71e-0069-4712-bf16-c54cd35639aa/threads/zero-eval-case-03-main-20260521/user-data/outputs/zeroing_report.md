# Case 03 归零排故报告：电弧加热烧蚀异常

## 1. 问题概述

顶事件为：电弧加热热防护材料筛选试验后，样件P-3中央区域烧蚀深度达到1.42 mm，超过同批样件均值约65%，但喷流热流标定数据未显示明显超限。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/00_problem_statement.md，章节: 顶事件。

发生条件为2026-05-08进行的75 s电弧加热试验，目标冷壁热流2.4 MW/m2，异常样件为P-3，当前影响为P-3材料批次适用性和装夹重复性结论暂缓。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/00_problem_statement.md，章节: 发生条件。

按设计方案要求，单件烧蚀深度超过同组均值40%时必须进行归零复核。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/01_design方案.md，章节: 设计目标。

## 2. 输入资料清单

本次分析直接读取了 `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/` 下用户指定的全部现有资料：

- 文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/00_problem_statement.md
- 文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/01_design方案.md
- 文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/02_test_outline试验大纲.md
- 文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md
- 文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv
- 文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md

未使用 `06_expected_analysis.md`。

## 3. 事实归纳

### 3.1 异常数据事实

P-3烧蚀深度为1.42 mm，明显高于P-1/P-2/P-4的0.84/0.88/0.91 mm。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 异常现象；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。

P-3质量损失为5.6 g，也高于P-1/P-2/P-4的3.1/3.3/3.5 g。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。

P-3背温峰值421 C，也高于其余样件382/389/395 C。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。

P-3表面出现偏右侧条带状加深。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 异常现象。

### 3.2 试验输入与边界条件事实

设计目标热流为2.4 MW/m2，冷壁热流偏差不得超过目标值±5%，装夹偏角不得超过1.0 deg。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/01_design方案.md，章节: 关键判据。

P-3暴露期间热流均值2.43 MW/m2，峰值2.51 MW/m2；弧电流最大波动2.2%。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。

试前热流计标定偏差为+1.8%。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录。

P-3装夹偏角记录为0.8 deg，但照片显示边缘垫片疑似未完全贴合；数据备注为“right-side shim contact uncertain”。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。

### 3.3 材料批次事实

P-3与P-4同属材料批次B26-042，但P-4未见同类异常。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/01_design方案.md，章节: 样件信息；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。

P-3材料密度和孔隙率复测尚未完成。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/00_problem_statement.md，章节: 当前状态；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录。

## 4. 故障树分析摘要

故障树已另存为 `fault_tree.json`。其核心结构如下：

- 顶事件：P-3样件中央区域烧蚀异常加深。
- 第一类路径：外部热载输入异常。
- 第二类路径：装夹/入射条件异常导致局部热集中。
- 第三类路径：材料局部抗烧蚀能力异常。
- 第四类路径：测量或记录偏差。

结合证据强度，当前主分析路径集中在第二类与第三类，第一类整体热载超限路径证据较弱。

## 5. 根因归因分析

### 5.1 已排除或弱化的路径

喷流整体超限可能性较低。这一判断基于以下事实：P-3热流均值2.43 MW/m2、峰值2.51 MW/m2，仍处于目标2.4 MW/m2的±5%判据范围内；试验总结也明确写明“未超过热流判据”。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/01_design方案.md，章节: 关键判据；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 异常现象；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。

弧电流明显异常路径也缺乏支持，因为现有记录仅显示最大波动2.2%，未见与异常烧蚀对应的能量输入突变证据。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录。

B26-042批次系统性失效可能性较低，因为同批次P-4表现正常。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md，章节: 专家复核意见。

### 5.2 当前最可疑路径

当前最可疑路径为：P-3装夹局部接触异常或局部入射角异常，引起局部流场/边界层扰动，进而造成偏右侧条带状区域热集中和烧蚀加深。

支持证据包括：

1. P-3出现偏右侧条带状加深，形貌上更符合局部边界条件异常，而不是整体热流普遍抬升。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 异常现象。
2. 照片和数据备注均提示右侧垫片接触不确定或疑似局部间隙。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。
3. 历史案例曾出现“装夹垫片局部未贴合导致烧蚀条带加深”。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md，章节: 历史相似案例。
4. 试验专家复核意见认为，P-3条带状形貌更像局部入射角或边界层扰动影响。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md，章节: 专家复核意见。

但该路径尚未闭环，因为原始照片复判、夹具复测和复现实验尚未完成，因此该结论状态只能标记为“待验证”。

### 5.3 并列待验证路径

材料单件局部缺陷是并列待验证原因。依据是：虽然P-4正常削弱了“批次系统性问题”判断，但专家明确指出局部孔隙率异常仍可能只影响单件样件，而P-3对应材料密度/孔隙率复检尚未完成。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md，章节: 专家复核意见。

因此，当前不能把材料因素完全排除，只能将其列为与装夹因素并列的待验证次主因路径。

## 6. 归零结论

### 6.1 结论分级

**事实结论**

- P-3确实发生异常烧蚀，且异常不仅体现在烧蚀深度，还体现在质量损失、背温峰值和条带状表面形貌。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 异常现象；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。
- 当前证据不支持将顶事件优先归因为喷流整体超限或弧电流显著失稳。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv。
- 当前证据也不支持直接判定B26-042批次存在系统性失效。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md，章节: 专家复核意见。

**推断结论**

- 最可疑原因为P-3装夹局部未贴合或局部入射条件异常，导致局部流场扰动和热集中。该推断具有中等证据支撑，但仍待验证。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md，章节: 历史相似案例；文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md，章节: 专家复核意见。

**假设/待验证结论**

- P-3单件材料局部密度或孔隙率异常仍可能为根因之一，但目前缺少复检数据。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 排查记录。
- 烧蚀深度测量或记录偏差目前无直接证据支持，也无复测结果，保留为低优先级待验证项。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/02_test_outline试验大纲.md，章节: 数据记录。

### 6.2 当前归零状态

本案例尚不能宣布完全归零关闭。依据现有资料，只能形成“阶段性归零判断”：

- 已基本压低系统级热输入异常路径；
- 已识别装夹局部异常为首要怀疑对象；
- 材料单件局部缺陷仍未排除；
- 关键验证动作尚未完成。

因此本案例状态建议定为：**归零分析已形成，根因待验证关闭**。

## 7. 验证计划

### 7.1 装夹路径验证

1. 调取P-3原始装夹照片，由试验、结构、质量三方独立复判，确认是否存在右侧垫片未贴合、局部翘起或接触间隙。
2. 使用原夹具进行几何复测，测量P-3对应安装面的局部平面度、垫片贴合度和等效偏角；必要时复做装夹偏角不仅记录单值，还记录边缘间隙分布。
3. 在可控条件下对备件复现实验：一组按标准贴合装夹，一组引入受控微小边界间隙，比较是否能复现“偏右侧条带状加深”。

验证判据：若受控间隙能够稳定复现条带状加深，且标准装夹下不复现，则装夹局部异常可升级为高置信根因。

### 7.2 材料路径验证

1. 对P-3对应母材或余料开展密度、孔隙率、显微缺陷复检。
2. 对P-4及同批次备件同步抽检，用于判断是单件局部异常还是批内离散性问题。
3. 若条件允许，对P-3烧蚀异常区与非异常区进行截面比对，观察是否存在局部孔洞、分层或浸渍不均。

验证判据：若P-3异常区存在显著局部结构缺陷，而同批其他区域或P-4无同类特征，则材料单件局部缺陷可升级为主因或并列主因。

### 7.3 测量路径验证

1. 复核P-3五点烧蚀深度原始测量记录和测点位置。
2. 复核质量损失称量记录与天平校验状态。
3. 若样件尚保留，建议重复测量中央区深度并与形貌照片配准。

## 8. 建议纠正与预防措施

1. 在异常关闭前，暂停以P-3结果直接评价B26-042批次适用性。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/00_problem_statement.md，章节: 发生条件。
2. 强化装夹记录方式：除单值偏角外，增加装夹界面照片、边缘贴合检查单和复核签字。
3. 对条带状烧蚀类异常建立标准化复判流程，要求同步保留原始照片、热像和夹具状态记录。该建议来源于本次“照片线索不足以闭环”的教训。文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md，章节: 历史相似案例。
4. 对材料复检项目增加“单件局部异常”识别手段，避免仅以批次平均特性做放行判断。

## 9. 遗留风险

1. 若未完成装夹复测，则未来重复试验仍可能因同类边界条件问题导致误判材料性能。
2. 若未完成P-3局部材料复检，则单件局部缺陷风险仍未识别，后续筛选结论存在不确定性。
3. 若不补做同批次备件复验，则装夹因素与材料因素之间仍难形成证据闭环。上述风险均来自文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 未关闭问题。

## 10. 证据附录

### 10.1 关键原始证据

- 文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/00_problem_statement.md，章节: 顶事件、发生条件、当前状态
- 文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/01_design方案.md，章节: 设计目标、样件信息、关键判据
- 文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/02_test_outline试验大纲.md，章节: 数据记录、异常处置
- 文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/03_test_summary试验总结报告.md，章节: 异常现象、排查记录、初步判断、未关闭问题
- 文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/04_test_data.csv
- 文件: /home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-03-main-20260521/user-data/uploads/05_historical_or_review_notes.md，章节: 历史相似案例、专家复核意见

### 10.2 证据闭环检查

- 顶事件：有原始异常数据支撑，闭环完整。
- “喷流整体超限可能性低”：有A类试验数据支撑，闭环基本完整。
- “装夹局部异常最可疑”：有形貌、照片线索、历史案例、专家意见支撑，但缺复测/复现实验，闭环未完成，标记待验证。
- “材料单件局部缺陷可能存在”：有专家意见和未完成复检支撑，但缺检测结果，闭环未完成，标记待验证。

## 11. 最终意见

基于现有资料，建议将本次异常的阶段性主因指向**P-3装夹局部接触/入射条件异常导致的局部热集中**，并将**P-3单件材料局部缺陷**列为并列待验证原因。当前不建议将异常归因为喷流系统超限或材料批次系统性失效。由于关键验证尚未完成，本报告结论状态为**待验证关闭**，不能作为完全归零结案依据。
