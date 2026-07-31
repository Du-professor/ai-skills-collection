# 政策解读规则源（Rubric）

本文件是 `policy-brief` Skill 的**唯一规则来源（single source of truth）**。所有枚举值、结构定义、分类维度都在此定义；`scripts/` 中的常量必须与本文件保持同步。若本文件变更，必须同步修改 `scripts/*.py` 顶部常量并重新自测。

---

## 一、四类功能模式（MODES）

| 模式 key | 中文 | 说明 |
|---|---|---|
| `summary` | 政策摘要 | 对单份政策生成结构化六段摘要 |
| `extract` | 要点提取 | 按分类提取要点并附条款级原文引用 |
| `compare` | 对比分析 | 对 ≥2 份政策做多维度矩阵对比 |
| `qa` | 政策问答 | 仅基于原文作答，未提及明确说明 |

---

## 二、摘要固定结构（SUMMARY_SECTIONS，6 段，顺序固定）

| key | heading（标题） | 内容要求 |
|---|---|---|
| `background` | 背景与目标 | 政策出台背景、要解决什么问题、总体目标 |
| `targets` | 适用对象 | 谁可以享受/需要遵守（主体、行业、区域、规模等） |
| `measures` | 主要措施 | 核心条款、举措、行动项（逐条，避免遗漏关键动作） |
| `support` | 支持方式与标准 | 补贴/奖励/优惠的具体标准、额度、比例、条件 |
| `timeline` | 时限与流程 | 生效/截止时间、申报/审批流程节点 |
| `impact` | 影响与注意 | 对相关主体的影响、常见误区、需特别留意事项 |

六段 **全部必填**，每段 `content` 不得为空；缺失信息写「未明确」，不得编造。

---

## 三、要点分类枚举（KEYPOINT_CATEGORIES）

提取要点时必须从以下枚举选择 `category`；`label` 为其中文名。

| category | label |
|---|---|
| `fiscal_subsidy` | 财政补贴 |
| `tax_pref` | 税收优惠 |
| `reg_compliance` | 监管合规 |
| `approval_flow` | 审批流程 |
| `support_target` | 支持对象 |
| `time_limit` | 时限要求 |
| `penalty` | 罚则 |
| `other` | 其他 |

每条要点必须包含：
- `point`：提炼后的要点（一句话，客观陈述）
- `quote`：**来自原文的逐字片段**（用于可追溯，禁止改写或虚构）
- `location`：在原文中的大致位置（如「第三章 第五条」「第二节」「全文第 2 段」），无法确定写「未标注」

---

## 四、对比维度枚举（COMPARE_DIMENSIONS）

对比分析时，每个维度须对**每一份**政策各填一行 `value`。

| dimension | label |
|---|---|
| `target` | 适用对象 |
| `support_strength` | 支持力度 |
| `threshold` | 门槛条件 |
| `timeline` | 时限 |
| `region` | 地域 |
| `authority` | 主管部门 |
| `diff` | 核心差异点 |

此外须输出：
- `diff_summary`：跨政策的整体核心差异总结（一段话）
- `recommendation`：适用建议（可选；指明不同主体/场景分别适合哪份政策，或并列适用）

---

## 五、问答格式（QA）

每条问答：
- `question`：用户的问题（原样保留）
- `answer`：基于原文的回答。**仅可使用原文中存在的信息**
- `citations`：引用数组，每项含 `quote`（原文片段）+ `location`（位置）

兜底规则：原文**未提及**的问题，必须将 `answer` 设为「原文未提及」，且 `citations` 置为空数组，不得猜测或外推。

---

## 六、政策领域枚举（POLICY_DOMAINS，用于跨会话记忆）

`policy_store.py` 记录用户关注领域时使用：

`tech_innovation`(科技创新)、`industry`(产业发展)、`fiscal_tax`(财政税收)、`talent_employment`(人才就业)、`livelihood`(民生保障)、`agriculture`(农业农村)、`ecology`(生态环境)、`opening_up`(对外开放)、`other`(其他)

---

## 七、脚本常量同步表（务必与本文件一致）

| 常量名（脚本中） | 取值 |
|---|---|
| `MODES` | `{"summary","extract","compare","qa"}` |
| `SUMMARY_SECTIONS` | `{"background","targets","measures","support","timeline","impact"}` |
| `KEYPOINT_CATEGORIES` | 见第三节 8 项 |
| `COMPARE_DIMENSIONS` | 见第四节 7 项 |
| `POLICY_DOMAINS` | 见第六节 9 项 |

> 任何枚举增删都需：①改本文件 ②改 `scripts/validate_policy.py` 顶部常量 ③改 `scripts/render_report.py` 顶部常量（如渲染需要）④重跑 `skill-tests/policy-brief/run_tests.py`。
