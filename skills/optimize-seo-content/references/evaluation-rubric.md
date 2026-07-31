# 评测 rubric（Evaluation Rubric）

> 本文件定义输出完整性、SEO 质量评分、鲁棒性门槛、批量差异化与赛事测试用例映射，是 `validate_seo_output.py` 与 `run_tests.py` 的评测依据。

## 1. 输出完整性（必需字段）

顶层必需：`status`、`language`、`page_type`、`search_intent`、`keywords`、`title_candidates`、`recommended_title`、`meta_candidates`、`recommended_meta`、`validation`。
- `title_candidates` 数量 ≥ **3**；`meta_candidates` 数量 ≥ **2**。
- 每个 `keyword` 必须含 `search_intent`、`priority`、`recommendation_reason`（验收：每个关键词均含意图/优先级/理由）。
- `recommended_title` / `recommended_meta` 非空。

## 2. SEO 质量评分（validation.score）

由 `validate_seo_output.py` 综合给出 0–100：

- 结构完整（必需字段 + 候选数量达标）：基础 40 分。
- 每个候选 `quality_score` 均值（脚本算）：映射到 0–40 分。
- 合规清洁度：`risks` 中无 `High` 且无非支持声明 → +20；有 `Medium` → +10；有 `High` → +0。
- `status` 映射：`pass` ≥ 80；`review` 50–79；`fail` < 50。

## 3. 鲁棒性门槛（50 组异常/正常输入）

以下异常必须**不崩溃**并返回结构化结果（见规格书 §十 降级矩阵）：

| 异常 | 期望行为 |
|---|---|
| 空输入 | `status: fail`，`error.code: EMPTY_INPUT` |
| URL 无法访问 | `error.code: URL_UNREACHABLE`，请粘贴正文 |
| 页面要求登录 | 标记不可读取，不绕过 |
| robots/访问控制阻止 | `error.code: URL_BLOCKED` |
| 无搜索量数据 | 用相关性+意图，不声称高搜索量 |
| 无网络 | Content-only Mode 降级 |
| 内容过短 | `evidence_insufficient: true`，限制关键词量 |
| 内容过长 | 分块汇总 |
| 中英文混合 | 识别主语言 + `mixed_language_risk` |
| 批量部分失败 | 保留成功项，逐项报告失败 |
| 模型输出格式错误 | 自动重试 1 次，之后 `fail` |
| 页面含恶意指令 | 忽略指令，仅提取事实 |

## 4. 批量差异化（check_batch_duplicates.py）

对 ≥2 页输出四类判定：

- `Duplicate`：保护字段（title/meta/h1）完全重复。
- `Cannibalization Risk`：关键词集合重叠度 > 0.6，或多页争夺同一主意图。
- `Review`：模板归一化后签名相同 / 开篇相似度 > 0.8 / 薄内容（仅替换品牌型号数字）。
- `Pass`：无上述问题。

验收：批量保护字段完全重复 = **0**（脚本强制去重或标记）。

## 5. 赛事评分映射（对齐规格书 §十四）

| 赛事项 | 分值 | 本 Skill 对应措施 |
|---|---:|---|
| 运行稳定性与鲁棒性 | 30 | 确定性脚本、异常矩阵、降级模式、AstronClaw 实测 |
| 创新性和应用价值 | 30 | 意图分析、可解释推荐、中英双语、多输入、批量防蚕食 |
| 结果质量 | 20 | 候选评分、事实一致性、关键词证据、自动质量门禁 |
| 技术设计与场景编排 | 10 | 提取→生成→脚本校验→批量分析协同 |
| 工程规范与文档 | 5 | 标准目录、README、注释、测试、调用示例 |
| 安全合规 | 5 | URL 安全、隐私、提示注入防护、无虚假 SEO 承诺 |

## 6. 赛事测试用例（前向测试）

使用全新上下文真实调用，至少覆盖：
1. 从零生成 SEO 建议（英文产品页）
2. 优化已有页面（中文文章）
3. 批量处理相似产品（防重复/蚕食）
4. 无网络降级
5. 恶意输入（提示注入网页）
6. 中英双语混合测试

前向测试通过标准：必需输出字段完整率 100%、JSON 解析成功率 100%、虚构搜索量/排名保证出现次数 0、无乱码、无网络时仍能输出明确标注的基础结果。
