# 底事件评估

## 1. 评估对象与方法

本评估围绕顶事件“第4工况保持阶段HF-07热流读数连续上升并超过设计判据，且邻近测点和喷流总压未同步变化”展开。评估依据采用“证据强度 + 机理一致性 + 反证情况 + 复现实验情况”四项原则。根据资料约束，当前没有行业统计、历史频次或专家打分表，因此**不提供精确数值概率**，仅给出高/中/低倾向与置信度。  
证据来源包括问题描述、设计方案、试验大纲、试验总结、原始试验数据和历史复核记录：
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/00_problem_statement.md`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/01_design方案.md`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/02_test_outline试验大纲.md`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/04_test_data.csv`
- 文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/05_historical_or_review_notes.md`

## 2. 顶事件事实基础

事实1：第4工况保持阶段T+118 s至T+164 s，HF-07由约1.03 MW/m2持续升至1.24~1.25 MW/m2，并超过1.12 MW/m2判据。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/00_problem_statement.md`，章节: 顶事件；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 异常现象；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/04_test_data.csv:4-8`。  
事实2：同期HF-06与HF-08基本保持在1.01~1.06 MW/m2范围，没有与HF-07同步抬升。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 异常现象；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/04_test_data.csv:4-8`。  
事实3：同期总压波动小于1.1%，总温波动小于9 K，均满足稳定性约束。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 初步排查；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/01_design方案.md`，章节: 约束和判据；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/04_test_data.csv:2-8`。  
事实4：关车后HF-07零点回读偏移+8.4%FS，且停机记录中HF-07为0.09，明显高于其他腹部热流点0.01量级。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 初步排查；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/04_test_data.csv:9`。  
事实5：T+154 s开始出现`ch07_noise_flag`，停机后CH-07状态为`zero_offset`。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/04_test_data.csv:7-9`。  
事实6：HF-07对应区域未见烧蚀、剥落或异常变色。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 初步排查。  
事实7：HF-07复标未完成，CH-07屏蔽层接地状态尚未拆检。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 未关闭问题。  

## 3. 底事件逐项评估

### BE1：HF-07位置真实局部热流升高

**事件定义**：HF-07位置在第4工况保持阶段发生真实局部热流上升。  
**支持证据**：HF-07读数确实持续升高并超过判据。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/00_problem_statement.md`，章节: 顶事件；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/04_test_data.csv:4-8`。  
**反证**：邻近HF-06、HF-08未同步升高；总压、总温无同步变化；表面检查未见烧蚀、剥落或异常变色；专家复核认为真实局部热流升高通常至少伴随相邻测点趋势变化、热痕迹或喷流参数变化。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 异常现象；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 初步排查；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/05_historical_or_review_notes.md`，章节: 专家复核记录。  
**机理一致性判断**：偏弱。若真实热流升高仅局限于HF-07单点，需要额外证明存在很强的局部流动非均匀性或局部结构变化，但现有资料未提供此类直接证据。  
**复现实验情况**：暂无。  
**综合判断**：低倾向。  
**置信度**：low。  
**状态**：待验证。  
**待验证动作**：复查风洞流场均匀性记录、试件局部几何/表面状态、必要时安排复测或对比件试验。  

### BE2：HF-07传感器本体零点或灵敏度漂移

**事件定义**：HF-07薄膜热流计在高温保持阶段发生本体漂移，导致示值虚高。  
**支持证据**：关车后HF-07零点回读偏移+8.4%FS；停机记录中HF-07残余读数0.09明显高于其他测点；历史案例曾出现高温保持后单个薄膜热流计灵敏度漂移7.6%，最终判为无效数据；现场当前判断也将测量链路漂移列为高可能性。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 初步排查；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/04_test_data.csv:9`；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/05_historical_or_review_notes.md`，章节: 相似问题；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 当前判断。  
**反证**：尚无复标结果，无法直接把零点偏移等同于本体灵敏度漂移。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 初步排查。  
**机理一致性判断**：强。单点持续缓慢上升、邻近点不跟随、停机后零点残留偏高，与传感器受热漂移机理相容。设计方案还规定热流计复标偏差超过±6%时不得作为定量判据。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/01_design方案.md`，章节: 约束和判据。  
**复现实验情况**：本次尚未复现；历史上存在相似先例，但只能作为相似性支持，不能直接证明本次故障。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/05_historical_or_review_notes.md`，章节: 相似问题。  
**综合判断**：高倾向。  
**置信度**：medium。  
**状态**：待验证。  
**待验证动作**：优先完成HF-07复标，对比零点、灵敏度、线性和滞回；必要时进行高温暴露后再标定。  

### BE3：CH-07通道噪声或接地/屏蔽异常

**事件定义**：CH-07采集通道在高温保持阶段出现噪声、接地或屏蔽异常，导致HF-07示值抬高。  
**支持证据**：T+154 s起数据状态出现`ch07_noise_flag`；停机后通道状态为`zero_offset`；试验总结明确指出CH-07屏蔽层接地状态尚未拆检。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/04_test_data.csv:7-9`；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 未关闭问题。  
**反证**：试验大纲规定试前完成采集链路绝缘检查，但该信息只能说明试前静态检查已做，不能证明高温保持阶段通道无异常。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/02_test_outline试验大纲.md`，章节: 试验流程。  
**机理一致性判断**：较强。单通道噪声标记与单点异常抬升相匹配，且该异常出现在后段。  
**复现实验情况**：暂无。  
**综合判断**：中到高倾向。  
**置信度**：medium。  
**状态**：待验证。  
**待验证动作**：拆检CH-07接地、屏蔽、连接器、采集板卡；对传感器与通道实施互换试验以区分“传感器问题”与“通道问题”。  

### BE4：HF-07贴装热接触异常

**事件定义**：HF-07贴装界面或热接触状态异常，使热流计响应偏离真实热流。  
**支持证据**：试验总结明确指出“不能排除局部贴装热接触异常”。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 当前判断。  
**反证**：表面检查未见烧蚀、剥落或异常变色，缺乏直接物证支持。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 初步排查。  
**机理一致性判断**：中等。贴装问题可引起局部响应异常，但目前缺乏安装记录、拆解照片、界面检查或复现实验支持。  
**复现实验情况**：暂无。  
**综合判断**：中倾向。  
**置信度**：low。  
**状态**：待验证。  
**待验证动作**：检查HF-07拆解状态、安装工艺记录、胶层/界面完整性，并与合格样件对比。  

## 4. 底事件排序

按当前证据支持强弱排序如下：  
1. **BE2 传感器本体零点或灵敏度漂移**：高倾向，medium。  
2. **BE3 CH-07通道噪声或接地/屏蔽异常**：中到高倾向，medium。  
3. **BE4 HF-07贴装热接触异常**：中倾向，low。  
4. **BE1 HF-07位置真实局部热流升高**：低倾向，low。  

该排序依据如下：设计方案明确要求当单点热流异常而邻近测点、总压、总温无同步变化时，应优先排查测量链路。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/01_design方案.md`，章节: 约束和判据。与此同时，本次存在零点偏移、通道噪声标记和停机残余偏高等直接异常迹象。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 初步排查；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/04_test_data.csv:7-9`。  

## 5. 当前可成立的阶段性结论

结论1：**现有资料更支持“HF-07测量链路异常”而非“真实局部热流异常升高”**。这是基于A/B级证据的阶段性推断。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/01_design方案.md`，章节: 约束和判据；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 当前判断；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/05_historical_or_review_notes.md`，章节: 专家复核记录。  

结论2：**在HF-07复标和CH-07拆检完成前，根因不能关闭**。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 未关闭问题；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/05_historical_or_review_notes.md`，章节: 专家复核记录。  

结论3：**HF-07当前数据不宜直接作为定量判据输入复核结论**，至少应先等待复标结果。若复标偏差超过±6%，按设计要求该测点数据不得作为定量判据。证据：文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/01_design方案.md`，章节: 约束和判据；文件: `/home/wangyh/workspace/deer-flow/backend/.deer-flow/users/7c5af71e-0069-4712-bf16-c54cd35639aa/threads/zero-eval-case-01-20260521/user-data/uploads/03_test_summary试验总结报告.md`，章节: 初步排查。  

## 6. 待验证清单

1. 完成HF-07复标，判断零点、灵敏度、线性是否超差。  
2. 完成CH-07接地、屏蔽层、连接器与板卡拆检。  
3. 开展传感器/通道互换验证，隔离“传感器故障”与“通道故障”。  
4. 复查HF-07安装工艺、拆解状态和界面热接触。  
5. 如以上均不能闭环，再考虑复测或数值/流场佐证，以验证是否存在真实局部热流异常。  
