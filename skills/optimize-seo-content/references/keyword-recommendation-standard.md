# 关键词推荐规范（Keyword Recommendation Standard）

> 本文件是关键词分类、搜索意图、优先级、证据标签与去重聚类的**唯一来源**。
> 模型仅产出枚举与文本；`normalize_keywords.py` 负责去重、聚类、语言识别与枚举归一。

## 1. 四类关键词（category）

| category | 说明 | 示例 |
|---|---|---|
| `primary` | 页面核心主题词，1–3 个 | "wireless earbuds" / "无线耳机" |
| `secondary` | 支撑主题的相关词 | "bluetooth 5.3" / "降噪" |
| `long_tail` | 长尾、低竞争、高意图 | "best wireless earbuds for running" |
| `question` | 问答型词，对应 FAQ | "how to pair wireless earbuds" |

规则：
- 每个页面 `primary` ≤ 3 个；总关键词建议 8–20 个（内容过短时下调）。
- 不推荐页面正文或用户输入无法支持的**产品能力 / 服务 / 属性**。
- 不因关键词"热门"而偏离页面主题。

## 2. 搜索意图（search_intent）

| 枚举 | 含义 |
|---|---|
| `informational` | 了解信息 |
| `comparison` | 比较取舍 |
| `commercial_investigation` | 商业调查（准备购买前研究） |
| `transactional` | 交易意图 |
| `navigational` | 导航到特定站点/品牌 |

## 3. 决策阶段（funnel_stage）

`awareness`（认知） / `consideration`（考虑） / `decision`（决策）。

## 4. 相关程度（relevance）

`High` / `Medium` / `Low` —— 与页面主题的相关程度（枚举，非分数）。

## 5. 证据标签（evidence）—— 真实性铁律

| 枚举 | 含义 | 允许出现的表述 |
|---|---|---|
| `measured` | 实测搜索量数据 | **本 Skill 永不标记**（无搜索量工具） |
| `trend_signal` | 可观察的趋势信号 | "趋势上升""讨论度较高"等弱表述 |
| `observable_phrase` | 正文/用户输入中可观察到的措辞 | 引用页面实际用词 |
| `model_inference` | 模型基于语义的推断 | "推测相关""可能匹配" |

**强制规则：**
- **绝不虚构搜索量**：不得出现"月搜索量""搜索量 1 万""高搜索量"等数值或强断言，除非 `evidence = measured`（本项目恒不为）。
- 区分 `measured` / `trend_signal` / `observable_phrase` / `model_inference`，在 `recommendation_reason` 中注明依据类别。
- `risk_note` 必须标注是否存在：事实风险、合规风险、关键词堆砌风险。

## 6. 优先级（priority）

`High` / `Medium` / `Low` —— 由相关性、意图匹配与页面支撑度综合给出（枚举，非分数）。

## 7. 推荐投放位置（recommended_placement）

`title` / `h1` / `body` / `faq` / `alt` / `internal_link`。

## 8. 关键词对象字段（模型产出）

每个关键词必须包含：`keyword`、`language`、`category`、`search_intent`、`funnel_stage`、`relevance`、`evidence`、`priority`、`recommended_placement`、`risk_note`、`recommendation_reason`。
**缺少任一必填字段 → `validate_seo_output.py` 报 `SCHEMA_INVALID`（exit 2）。**

## 9. 去重与聚类（normalize_keywords.py）

- **精确去重**：同 `(keyword 小写, language)` 合并，保留 `priority` 最高者。
- **近义聚类**：对英文做小写+去标点+词序归一；对中文做全角转半角+去空格；签名相同者合并。
- **语言识别**：若 `language` 缺失，按字符中 CJK 占比判定（`≥0.3` → `zh-CN`，否则 `en-US`）。
- **排序输出**：`primary(High→Low)` → `secondary` → `long_tail` → `question`，同组按 `priority` 降序。
- **枚举校验**：非法枚举值改写为最近合法值并在 `risks` 记录，不终止流程。

## 10. 禁止

- 推荐正文无法支撑的能力/服务。
- 虚构任何搜索量数值或"高搜索量"强断言。
- 仅因热门而偏离主题。
- 在 `keyword` 字段堆砌逗号分隔的多个词（每个关键词独立成条）。
