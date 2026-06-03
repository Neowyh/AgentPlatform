# 底事件评估

## 评估说明
本评估按“证据强度 + 机理一致性 + 反证情况 + 复现实验情况”进行。现有资料未提供统计频次、行业数据库或专家打分表，因此不输出精确概率值，仅给出倾向性和置信度。证据不足项统一标记为“待验证”。

## 顶事件与判据对比
顶事件为：热真空试验升温平台切换至保温阶段后，TC-12 温度超过目标上限 9.6C，持续 7 分 30 秒。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/00_problem_statement.md`，章节: 顶事件；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 异常现象；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/04_test_data.csv`。

设计/试验判据要求内部测点超调不超过 89C，持续不超过 180 s，且切保温后 60 s 内加热占空比低于 35%。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/01_design方案.md`，章节: 设计目标、控制约束；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/02_test_outline试验大纲.md`，章节: 判据。

## 底事件逐项评估

### BE-01 参数组B积分限幅或相关控制参数误配置
- 事实：试验前一日参数组 B 由 2026B-2 改为 2026B-3；未关闭问题中明确提出“参数组 B 的积分限幅值是否误配置，待软件配置复核”。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 排查记录、未关闭问题。
- 机理一致性：历史相似案例显示，保温参数切换后积分限幅未同步更新，会造成加热占空比下降滞后并导致内部测点超调。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/05_historical_or_review_notes.md`，章节: 历史相似案例。
- 反证情况：暂无直接参数导出比对结果，因此尚无A 级证据直接证明误配置已经发生。
- 复现实验情况：尚未完成参数组 C 对比复现实验，也未见参数回放结果。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 未关闭问题。
- 结论：倾向高，置信度中，状态为待验证。

### BE-02 保温切换逻辑使占空比下降过慢
- 事实：设计与试验大纲都要求切保温后 60 s 内占空比降至 35% 以下；实际记录显示切保温后 120 s 内仍保持 58% 以上。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/01_design方案.md`，章节: 控制约束；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/02_test_outline试验大纲.md`，章节: 判据；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 排查记录。
- 数据支撑：138 min 切换至 B 时占空比 88%，140 min 为 74%，142 min 为 66%，144 min 仍为 58%；人工切换至参数组 C 后，148 min 降至 28%，152 min TC-12 恢复至 87.2C。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/04_test_data.csv`。
- 机理一致性：加热输入持续偏高可直接解释内部测点继续升温，而外壁反馈仍处于目标范围，符合“内部热惯性滞后释放”的表现。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/01_design方案.md`，章节: 控制约束；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 初步判断。
- 反证情况：暂无明显反证。
- 复现实验情况：已有一次现场人工切换 C 后恢复的过程性证据，但仍缺规范化短时复现实验。
- 结论：倾向高，置信度高，状态为疑似成立。

### BE-03 TC-12导热胶层偏厚导致动态响应失真
- 事实：目视复查显示 TC-12 未脱落，但胶层偏厚需复测。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 排查记录。
- 机理一致性：专家复核意见认为胶层偏厚通常使读数上升变慢，不能单独造成内部实际温度持续高于外壁反馈。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/05_historical_or_review_notes.md`，章节: 复核意见。
- 反证情况：初步判断中已指出该因素“不能单独解释持续超调”。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 初步判断。
- 复现实验情况：未复测胶层厚度，未拆换后复测，证据不足。
- 结论：倾向低，置信度中，状态为待验证。更适合作为次要影响因素排查，而非当前首要根因。

### BE-04 热惯性模型与实际内部热响应不一致
- 事实：设计文件明确规定，若内部测点超调而外壁反馈正常，应检查热惯性模型和控制参数切换逻辑。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/01_design方案.md`，章节: 控制约束。
- 机理一致性：本次异常中 TC-09、TC-10 外壁反馈维持在 84.6C 至 86.2C，而 TC-12 升至 94.6C，说明内部与外壁之间存在显著动态差异。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 异常现象；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/04_test_data.csv`。
- 反证情况：暂无模型复核报告，也没有仿真/回放数据；因此尚不能确认模型失配是否真实存在。
- 复现实验情况：未见模型修订前后的对比试验。
- 结论：倾向中，置信度低，状态为待验证。

## 已筛除或暂不支持因素

### 真空度异常
异常期间真空度为 3.0e-3 Pa 至 3.5e-3 Pa，满足“大纲要求优于 5e-3 Pa”。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/02_test_outline试验大纲.md`，章节: 判据；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 排查记录；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/04_test_data.csv`。现有证据不支持其为主因。

### 外壁反馈测点失控
异常现象中 TC-09、TC-10 维持在 84.6C 至 86.2C，未超判据。证据见文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 异常现象；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-02-main-20260521/user-data/uploads/04_test_data.csv`。现有证据不支持外壁反馈失控导致本次异常。

## 综合判断
现有证据闭环最强的是“保温参数切换后控制输出下降过慢”，其上游最可疑诱因是参数组 B 新版本配置问题，尤其是积分限幅或同类控制参数误配置。该判断得到 A 级过程数据、B 级历史相似案例和 B 级专家复核意见共同支持；但由于缺少参数文件核对与规范化复现实验，最终根因仍应标记为待验证。
