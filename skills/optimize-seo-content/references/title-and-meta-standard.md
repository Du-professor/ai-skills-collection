# 标题与元描述规范（Title & Meta Standard）

> 本文件是候选标题/元描述规则、字符统计、多语言处理、评分模型与推荐选择逻辑的**唯一来源**。
> **模型禁出数值分数**：模型只产出定性枚举字段，`score_seo_candidates.py` 依据本文件的权重矩阵确定性计算 `quality_score`。

## 1. 标题候选规则（title_candidates）

每页生成 **3–5** 个候选 SEO Title。每个候选含：

| 字段 | 来源 | 说明 |
|---|---|---|
| `title` | 模型 | 候选标题文本 |
| `character_count` | 脚本计算 | 实际字符数（脚本复算校验） |
| `primary_keyword` | 模型 | 该标题主打的主关键词 |
| `search_intent` | 模型 | 对应搜索意图（枚举） |
| `differentiation` | 模型 | `Low`/`Medium`/`High` 页面差异化程度 |
| `claim_risk` | 模型 | `Low`/`Medium`/`High` 事实/合规风险 |
| `quality_score` | **脚本** | 0–100 确定性评分 |
| `recommendation_reason` | 模型 | 推荐理由（含依据类别） |

标题生成约束：
- 与页面主题一致，包含主关键词且位置自然。
- 不堆砌关键词、不过于宽泛、不做标题党。
- 不得包含正文未支持的承诺（如"免费""第一""官方授权"无依据时）。
- 不与其他页面重复（批量场景由 `check_batch_duplicates.py` 校验）。
- 清晰表达页面类型与核心价值。

## 2. 元描述候选规则（meta_candidates）

每页生成 **2–3** 个 Meta Description。每个候选含：

| 字段 | 来源 | 说明 |
|---|---|---|
| `meta_description` | 模型 | 完整自然句，不机械截断 |
| `character_count` | 脚本计算 | 实际字符数 |
| `covered_intent` | 模型 | 覆盖的搜索意图 |
| `included_keyword` | 模型 | 自然包含的核心关键词 |
| `value_proposition` | 模型 | 价值主张一句话 |
| `cta_type` | 模型 | `none`/`learn_more`/`shop_now`/`contact`/`download`/`subscribe` |
| `claim_risk` | 模型 | `Low`/`Medium`/`High` |
| `quality_score` | **脚本** | 0–100 |
| （注：`recommendation_reason` 在批量或报告中补充） | | |

元描述约束：
- 完整自然句，准确概括页面内容，自然包含核心关键词。
- 不重复标题、不复制其他页面元描述。
- **不虚构**价格、销量、认证、排名或效果。
- **不保证**搜索排名或点击率。
- 英文以 **140–160 字符**为编辑目标（非硬限制）；中文采用语言适配目标（见 §4），不生搬英文字符限制。

## 3. 字符统计

- 字符数 = `len(text)`（含空格，按 Unicode 码点计）。
- 标题长度仅为编辑目标，不宣称为搜索引擎硬限制；报告标注"编辑目标"。
- 截断检测：标题/元描述末尾不以连字符 `-` 或残缺词结尾（脚本检测 `validation` 标记）。

## 4. 多语言规则

| 语言 | 标题编辑目标 | 元描述编辑目标 |
|---|---|---|
| `en-US` | 50–60 字符（软） | 140–160 字符（软） |
| `zh-CN` | 20–30 汉字（软） | 50–80 汉字（软） |
| `auto` | 按检测语言取对应目标 | 同上 |

多语言页：分别给出对应语言候选；中英混合正文标注 `mixed_language_risk`。

## 5. 评分模型（quality_score，0–100）

### 5.1 标题权重矩阵

| 维度 | 权重 | 脚本可观测信号 |
|---|---:|---|
| 主题相关性 | 30 | 主关键词是否出现在标题（含模糊匹配）；`differentiation` 枚举映射 |
| 搜索意图匹配 | 20 | `search_intent` 是否非空且与页面意图一致 |
| 清晰度与可读性 | 15 | 无全大写滥用、无过度标点、词数合理 |
| 关键词自然度 | 15 | 主关键词出现次数 ≤ 2，无连续重复 |
| 页面差异化 | 10 | `differentiation` 枚举：High=10 / Medium=6 / Low=2 |
| 事实与合规安全 | 10 | `claim_risk` 枚举：Low=10 / Medium=5 / High=0（-额外扣分项另计） |

### 5.2 元描述权重矩阵

| 维度 | 权重 | 脚本可观测信号 |
|---|---:|---|
| 内容准确性 | 30 | 长度在编辑目标带内、完整句（以句号/。结尾或无截断） |
| 关键词覆盖 | 20 | `included_keyword` 非空且出现在描述中 |
| 价值主张清晰 | 15 | `value_proposition` 非空 |
| CTA 合理 | 10 | `cta_type` 合法且非强制承诺型 |
| 清晰度与可读性 | 15 | 无全大写滥用、无过度标点 |
| 事实与合规安全 | 10 | `claim_risk` 枚举映射（同标题） |

### 5.3 计算步骤（确定性）

1. 各维度得原始分 0–权重值（由可观测信号打分）。
2. 求和得 `quality_score`（四舍五入整数，截断到 [0,100]）。
3. `claim_risk = High` 时，总分额外 `-15` 并在 `risks` 记录未支持声明风险。
4. 含排名保证/虚构搜索量文本 → 该候选判 `quality_score = 0` 且 `claim_risk = High`。

## 6. 推荐选择逻辑

- `recommended_title`：在 `title_candidates` 中取 `quality_score` 最高者；并列时取 `claim_risk` 最低、其次 `character_count` 最接近编辑目标者。
- `recommended_meta`：同理取 `meta_candidates` 最高分。
- 若最高分 < 50 → `status` 降为 `review`，`selection_reason` 注明"候选质量偏低，建议人工润色"。
- 选择理由写入 `selection_reason`，引用评分维度而非凭空断言。
