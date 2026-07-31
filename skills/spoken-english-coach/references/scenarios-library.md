# 场景库（Scenarios Library）

按「话题 × 等级」组织角色扮演场景。模型据此开场与推进。每个场景给：Premise（设定）、Coach 开场句、2–3 个 Follow-up（推进追问）、Focus（本场景重点练习的语法/词汇）。等级用 CEFR（A1–C2）；未指定时默认 B1。

> 个性化：若进度档案的 `recommended_focus.topic` 命中下表某话题，优先选该话题场景，并在 Follow-up 中加重对应 `category` 的练习。

## 话题索引

| topic key | 中文 | 典型场景 |
|-----------|------|----------|
| daily-life | 日常生活 | 周末计划、家庭、爱好 |
| campus | 校园 | 选课、小组讨论、社团 |
| travel | 旅行 | 值机、酒店、问路、点餐 |
| workplace | 职场 | 邮件、会议、请假、汇报 |
| business-meeting | 商务会议 | 提案、议价、电话会议 |
| job-interview | 求职面试 | 自我介绍、行为面试、谈薪 |
| shopping | 购物 | 退换货、比价、砍价 |
| dining | 餐饮 | 点餐、评价、忌口 |
| health | 健康 | 挂号、描述症状、建议 |
| social | 社交闲聊 | 破冰、观点、八卦 |

## 场景卡片（含分级变体）

### 1. travel（旅行）
- **A2/B1 Premise**：在机场值机柜台办理托运与选座。
  - Coach 开场：`🗣️ Coach: Good morning! Are you checking in for the flight to Tokyo? May I see your passport, please?`
  - Follow-up：询问行李件数/重量 → 选靠窗还是过道 → 确认登机口。
  - Focus：介词（at/on/in）、there is/are、礼貌请求（Could I…?）。
- **B2/C1 Premise**：在陌生城市向路人问路并应对临时变更。
  - Coach 开场：`🗣️ Coach: The museum you wanted is closed for renovation. I'd suggest the riverside gallery instead—shall I show you how to get there?`
  - Follow-up：用条件句规划备选路线 → 表达偏好与权衡 → 临时改约。
  - Focus：条件句、连接词、表达偏好的高级搭配。

### 2. job-interview（求职面试）
- **A2/B1 Premise**：电话筛选面试，自我介绍与离职原因。
  - Coach 开场：`🗣️ Coach: Thanks for joining. Could you tell me a little about yourself and why you're interested in this role?`
  - Follow-up：介绍经验 → 说 strengths/weaknesses → 问薪资范围。
  - Focus：现在完成时、情态动词、STAR 简化。
- **B2/C1 Premise**：行为面试，追问过往冲突处理。
  - Coach 开场：`🗣️ Coach: Tell me about a time you disagreed with a teammate. What did you do, and what was the outcome?`
  - Follow-up：用过去时态讲因果 → 反思与改进 → 反问公司文化。
  - Focus：过去时态链、因果连接、抽象名词。

### 3. workplace（职场）
- **B1 Premise**：向主管请假并说明安排。
  - Coach 开场：`🗣️ Coach: Hi, do you have a moment? I heard you might need next Friday off—what's the plan for your tasks?`
  - Follow-up：说明原因 → 交接安排 → 确认审批。
  - Focus：将来时、被动、礼貌邮件式表达。
- **B2/C1 Premise**：项目复盘会上汇报风险。
  - Coach 开场：`🗣️ Coach: Before we wrap up, I'd like your read on the top risk to the launch. How bad is it, and what's our mitigation?`
  - Follow-up：量化风险 → 给方案 → 争取资源。
  - Focus：虚拟语气、数据表达、正式语域。

### 4. daily-life / social（日常 / 社交）
- **A2/B1 Premise**：周末计划闲聊。
  - Coach 开场：`🗣️ Coach: Any fun plans for the weekend? I was thinking of hiking if the weather holds.`
  - Follow-up：说计划 → 邀约 → 改时间。
  - Focus：be going to、邀请与拒绝。
- **B1/B2 Premise**：就「远程办公利弊」交换观点。
  - Coach 开场：`🗣️ Coach: Do you think remote work helps productivity, or hurts team spirit? I'm torn.`
  - Follow-up：给立场 → 举例子 → 让步反驳。
  - Focus：观点表达、连接副词、让步从句。

### 5. shopping / dining（购物 / 餐饮）
- **A2/B1 Premise**：餐厅点餐与忌口。
  - Coach 开场：`🗣️ Coach: Welcome! Today's special is grilled salmon. Do you have any allergies or preferences?`
  - Follow-up：点主菜 → 要饮料 → 评价口味。
  - Focus：would like、some/any、评价形容词。
- **B1 Premise**：退换网购商品。
  - Coach 开场：`🗣️ Coach: Hi, I'd like to return this jacket—it doesn't fit. What do I need to do?`
  - Follow-up：说明问题 → 要退款/换货 → 确认流程。
  - Focus：退货句型、原因从句、礼貌坚持。

### 6. campus（校园）
- **B1 Premise**：小组讨论分工。
  - Coach 开场：`🗣️ Coach: So for the group project, who takes the introduction? I can do the research part if you want.`
  - Follow-up：认领任务 → 定 deadline → 约下次。
  - Focus：提议与同意、将来安排、情态动词。

> 说明：以上为「种子库」。模型可基于 `topic` 与 `level` 在同一框架内生成等价新场景，保持 Premise/Coach 开场/Follow-up/Focus 四要素完整即可。
