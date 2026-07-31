# 输入输出契约（Input-Output Contract）

> 本文件是 `optimize-seo-content` Skill 的输入类型、缺失处理、JSON Schema、状态码与错误消息的**唯一来源**。
> 模型产出与所有脚本均须严格遵循本契约；脚本改动若影响结构，必须同步更新本文件。

## 1. 输入类型

| 输入类型 | 形态 | 处理入口 |
|---|---|---|
| 纯文本 | 产品介绍 / 文章 / 服务说明 / 页面正文 | 直接作为 `body` |
| Markdown | 含标题层级与链接 | `extract_page_fields.py`（保留 `#` 层级） |
| HTML | 网页源码 | `extract_page_fields.py`（提取 title/meta/h1/h2/body） |
| DOCX | Word 文档 | `extract_page_fields.py`（zipfile+ElementTree 零依赖） |
| URL | 公开可访问页面 | 由 Agent 用自身 web 工具抓取后交 `extract_page_fields.py`；脚本**不联网** |
| PDF | —— | **不支持自动解析**，提示用户复制正文粘贴 |
| 批量文件 | ≥2 份内容 | 逐份处理后交 `check_batch_duplicates.py` |
| 用户关键词 | 候选词 | 仅作候选，不自动视为最终主关键词 |

### 必填信息（至少其一）
- 页面正文（text / markdown / html / docx 提取后的 body）
- 内容文件
- 可公开访问的 URL

### 可选信息
- 目标受众（audience）
- 目标地区（region：`us` / `uk` / `cn` / `global-en`）
- 页面类型（page_type）
- 核心业务目标（business_goal）
- 用户已有关键词（seed_keywords）
- 竞品 URL（competitor_urls，仅作参考信号，不复制其正文）
- 品牌语气（brand_tone）
- 禁用词与合规要求（banned_terms / compliance_notes）

## 2. 缺失输入处理

- 完全缺失必填项 → 返回结构化错误（`status: "fail"`，`error.code: "EMPTY_INPUT"`），**不进入生成流程**。
- 仅缺失可选项 → 使用默认值并在报告中标注 `assumptions`：
  - `page_type` 默认 `article`
  - `language` 默认 `auto`（由 `extract_page_fields.py` 或 `normalize_keywords.py` 检测）
  - `region` 默认 `global-en`
- 内容过短（< 50 字符正文）→ 标记 `evidence_insufficient: true`，限制关键词数量，不强行生成大量建议。
- 内容过长（> 20000 字符）→ 分块分析后汇总（实现层处理，对模型透明）。

## 3. 输出 JSON Schema（顶层）

脚本 `validate_seo_output.py` 以此为校验基线。

```json
{
  "status": "pass | review | fail",
  "language": "zh-CN | en-US | auto",
  "page_type": "product | article | category | service | landing",
  "input_summary": {
    "source_type": "text | markdown | html | docx | url",
    "char_count": 0,
    "assumptions": [],
    "evidence_insufficient": false
  },
  "search_intent": {
    "primary_intent": "what_is | how_to | best | versus | price | review | installation | troubleshooting | commercial_inquiry",
    "secondary_intent": "同上枚举或 null",
    "decision_stage": "awareness | consideration | decision",
    "match_level": "strong | partial | weak",
    "content_gaps": ["..."],
    "suggested_modules": ["..."]
  },
  "keywords": [
    {
      "keyword": "string",
      "language": "zh-CN | en-US",
      "category": "primary | secondary | long_tail | question",
      "search_intent": "informational | comparison | commercial_investigation | transactional | navigational",
      "funnel_stage": "awareness | consideration | decision",
      "relevance": "High | Medium | Low",
      "evidence": "measured | trend_signal | observable_phrase | model_inference",
      "priority": "High | Medium | Low",
      "recommended_placement": "title | h1 | body | faq | alt | internal_link",
      "risk_note": "string",
      "recommendation_reason": "string"
    }
  ],
  "title_candidates": [
    {
      "title": "string",
      "character_count": 0,
      "primary_keyword": "string",
      "search_intent": "string",
      "differentiation": "Low | Medium | High",
      "claim_risk": "Low | Medium | High",
      "quality_score": 0,
      "recommendation_reason": "string"
    }
  ],
  "recommended_title": {
    "title": "string",
    "selection_reason": "string",
    "quality_score": 0
  },
  "meta_candidates": [
    {
      "meta_description": "string",
      "character_count": 0,
      "covered_intent": "string",
      "included_keyword": "string",
      "value_proposition": "string",
      "cta_type": "none | learn_more | shop_now | contact | download | subscribe",
      "claim_risk": "Low | Medium | High",
      "quality_score": 0
    }
  ],
  "recommended_meta": {
    "meta_description": "string",
    "selection_reason": "string",
    "quality_score": 0
  },
  "content_gaps": [
    { "module": "string", "reason": "string" }
  ],
  "risks": [
    { "type": "string", "severity": "Low | Medium | High", "detail": "string", "location": "string" }
  ],
  "validation": {
    "passed": true,
    "score": 0,
    "issues": [],
    "checked_at": "ISO8601"
  },
  "error": { "code": "string", "message": "string" }
}
```

## 4. 状态码

| status | 含义 | 触发条件 |
|---|---|---|
| `pass` | 校验通过，可直接交付 | 必需字段完整、无致命合规项、候选数量达标 |
| `review` | 有条件通过，需人工复核 | 存在 `Medium` 风险或证据不足，但结构完整 |
| `fail` | 不通过 | 空输入 / JSON 非法 / 必需字段缺失 / 存在 `High` 未支持声明风险 |

## 5. 错误消息（error.code）

| code | message（示意） |
|---|---|
| `EMPTY_INPUT` | 未提供任何正文、文件或 URL |
| `UNSUPPORTED_FORMAT` | 不支持的文件类型（如 PDF 自动解析） |
| `URL_UNREACHABLE` | URL 无法访问，请粘贴正文 |
| `URL_BLOCKED` | URL 被 robots / 访问控制阻止或属私有地址 |
| `JSON_INVALID` | 模型输出非合法 JSON |
| `SCHEMA_INVALID` | 字段缺失或枚举非法（详见 stderr 字段级报错） |
| `CONTENT_TOO_SHORT` | 正文过短，证据不足 |
| `MODEL_FORMAT_ERROR` | 模型输出结构异常，已重试仍失败 |

> 所有错误消息均为中文说明，不泄露内部路径或系统细节。
