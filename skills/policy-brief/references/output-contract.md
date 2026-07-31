# 输出契约（Output Contract）

本文件定义模型在四类模式下**必须产出**的 JSON 结构。所有结构必须可被 `scripts/validate_policy.py` 校验通过（exit 0）。`examples/` 目录提供对应可运行样例。

**通用约束（所有模式）：**
- JSON 顶层必须含 `mode` 字段，取值为 `summary`/`extract`/`compare`/`qa` 之一。
- 文本字段不得为空字符串（缺失信息用「未明确」「未标注」「原文未提及」等占位，而非空串）。
- **禁止输出任何分数、评分、星级、匹配度等量化结论**。
- 所有 `quote` / `citation.quote` 必须是原文中真实存在的逐字片段。
- 数组类型字段不得为空数组（除非 qa 的 citations 在「原文未提及」时为空）。

---

## 1. summary（政策摘要）

```json
{
  "mode": "summary",
  "title": "政策标题（从原文提取或用户提供）",
  "issued_by": "发布机关（可选，未知写「未明确」）",
  "issued_date": "发布日期（可选，未知写「未明确」）",
  "sections": [
    {"key": "background", "heading": "背景与目标", "content": "……"},
    {"key": "targets",     "heading": "适用对象",   "content": "……"},
    {"key": "measures",    "heading": "主要措施",   "content": "……"},
    {"key": "support",     "heading": "支持方式与标准", "content": "……"},
    {"key": "timeline",    "heading": "时限与流程", "content": "……"},
    {"key": "impact",      "heading": "影响与注意事项", "content": "……"}
  ],
  "source_refs": ["关键原文片段1", "关键原文片段2"]
}
```

- `sections` 必须恰好包含 6 项，且 `key` 取自 `background/targets/measures/support/timeline/impact`（顺序不限，但 6 个都要有）。
- 每项 `content` 非空。
- `source_refs` 可选，为字符串数组。

---

## 2. extract（要点提取）

```json
{
  "mode": "extract",
  "title": "政策标题",
  "categories": [
    {
      "category": "fiscal_subsidy",
      "label": "财政补贴",
      "points": [
        {"point": "对符合条件的企业给予一次性奖励", "quote": "对首次升规入统的工业企业给予一次性奖励 20 万元", "location": "第二章 第六条"}
      ]
    }
  ],
  "total_points": 3
}
```

- `categories` 为非空数组；每项 `category` 必须属于 KEYPOINT_CATEGORIES 枚举，`label` 与 rubric 对应中文一致。
- 每个 `points` 为非空数组；每条含 `point`(非空)、`quote`(非空、须为原文逐字)、`location`(非空)。
- `total_points` 为整数，等于全部 `points` 条数之和。

---

## 3. compare（对比分析）

```json
{
  "mode": "compare",
  "policies": [
    {"id": "P1", "title": "政策A", "issued_by": "机关甲", "issued_date": "2025-01-01"},
    {"id": "P2", "title": "政策B", "issued_by": "机关乙", "issued_date": "2025-06-01"}
  ],
  "dimensions": [
    {
      "dimension": "target",
      "label": "适用对象",
      "rows": [
        {"policy_id": "P1", "value": "……"},
        {"policy_id": "P2", "value": "……"}
      ]
    }
  ],
  "diff_summary": "两份政策在……方面存在核心差异……",
  "recommendation": "建议……（可选）"
}
```

- `policies` 为**非空且 ≥2** 的数组；每项 `id` 唯一，`title` 非空。
- `dimensions` 为非空数组；`dimension` 属于 COMPARE_DIMENSIONS 枚举。
- 每个 dimension 的 `rows` 必须对**每一份** policy 各有一行，`policy_id` 与 `policies[].id` 对应，`value` 非空。
- `diff_summary` 非空；`recommendation` 可选（空串或省略均可）。

---

## 4. qa（政策问答）

```json
{
  "mode": "qa",
  "qa_pairs": [
    {
      "question": "该政策对小微企业的补贴标准是多少？",
      "answer": "根据原文，对小微企业按……给予补贴。",
      "citations": [
        {"quote": "对年营业收入不超过 2000 万元的小微企业，按实际支出 30% 给予补贴，最高 50 万元", "location": "第三章 第九条"}
      ]
    },
    {
      "question": "政策是否提到海外分支机构？",
      "answer": "原文未提及",
      "citations": []
    }
  ]
}
```

- `qa_pairs` 为非空数组。
- 每条 `question` 非空、`answer` 非空。
- `citations` 为数组；当 `answer` 为「原文未提及」时**必须为空数组**；其余情况每项含 `quote`(非空) 与 `location`(非空)。
- 不得出现原文中不存在的信息；不得外推、不得编造条款编号。
