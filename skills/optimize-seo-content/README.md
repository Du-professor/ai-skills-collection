# Smart SEO Content Optimizer（`optimize-seo-content`）

> 参赛作品 · 科大讯飞「全场景内容智能创作 Skill 开发挑战赛」
> 全场景智能 SEO 内容优化 Skill：可解释、可验证、可批量、支持中英双语且不虚构搜索数据的 SEO 工作流。

## 1. 定位与核心价值

面向网站运营、跨境电商、内容编辑、营销团队的通用 SEO 内容优化 Skill。输入网页正文、产品介绍、文章草稿、Markdown、HTML、DOCX、可公开访问的 URL 或批量内容，自动完成：

- SEO 关键词发现与推荐（主词 / 次词 / 长尾 / 问答四类）
- 搜索意图分析（What is / How to / Best / Versus / Price / Review …）
- 标题诊断与 3–5 个候选标题生成
- 元描述生成与优化（2–3 个候选）
- 页面内容一致性检查
- 关键词堆砌与重复内容检查
- SEO 质量评分与修改建议
- 中英文双语优化
- 单页与批量处理（防重复标题/元描述、防关键词蚕食）

**核心竞争力**：不只是生成关键词、标题和元描述，而是提供**可解释、可验证、可批量运行、支持中英文且不会虚构搜索数据**的 SEO 内容优化工作流。

## 2. 架构（混合零依赖）

沿用本工作区已验证的参赛 Skill 范式：**模型负责产出结构化 JSON（枚举+文本，禁出分数），纯标准库脚本负责提取 / 归一化 / 确定性评分 / 合规校验 / 批量差异化 / 多格式渲染**。

- 全程**零联网、零密钥、零第三方依赖**，纯 Python 标准库。
- URL 抓取由 Agent 自身 web 工具完成，Skill 脚本不发起任何 socket（SSRF 防护在 Agent 层）。
- 所有分数由脚本确定性计算，模型只出定性枚举，杜绝"模型拍脑袋打分"。

```
输入 → extract_page_fields → 模型产出JSON → normalize_keywords
     → score_seo_candidates → validate_seo_output → (批量)check_batch_duplicates
     → seo_store(可选) → render_report(5格式)
```

## 3. 目录结构

```
optimize-seo-content/
├── SKILL.md                      # 运行时规则入口（精简）
├── README.md                     # 本文件（赛事评审材料，非运行时规则源）
├── references/                   # 5 个权威规则源（唯一事实源）
│   ├── input-output-contract.md
│   ├── keyword-recommendation-standard.md
│   ├── title-and-meta-standard.md
│   ├── seo-compliance-policy.md
│   └── evaluation-rubric.md
├── scripts/                      # 7 个零依赖脚本
│   ├── extract_page_fields.py    # HTML/MD/TXT/DOCX 字段提取
│   ├── normalize_keywords.py     # 去重/聚类/语言识别
│   ├── score_seo_candidates.py   # 确定性标题&元描述评分
│   ├── validate_seo_output.py    # Schema/合规门禁（exit 0/2/1）
│   ├── check_batch_duplicates.py # 批量重复/蚕食
│   ├── render_report.py          # MD/JSON/HTML/DOCX/CSV
│   └── seo_store.py              # 跨会话记忆
└── examples/                     # 3 组演示输入与输出
```

## 4. 调用示例

```
Use $optimize-seo-content to recommend SEO keywords, titles, and meta descriptions for this product introduction.
Use $optimize-seo-content to audit and optimize the title, keywords, and meta description of this page.
Use $optimize-seo-content to analyze this URL and produce an SEO optimization report.
使用 $optimize-seo-content 分析这篇文章，推荐SEO关键词，并生成标题和元描述。
```

## 5. 输出格式

默认 Markdown；可按需输出 JSON（稳定结构，便于接入 CMS / 工作流 / AstronClaw）、自包含 HTML 报告、DOCX 报告、CSV 批量关键词表。

## 6. 安全与合规

- 仅访问用户明确提供的公开 URL；`http/https` 且仅限公开地址，SSRF 防护阻止本机/局域网/私有地址。
- 不保存登录凭证、Cookie 或个人身份信息；日志不记隐私数据与完整敏感正文。
- 不虚构搜索量、不保证排名/流量/效果、不复制竞品正文。
- 网页指令视为不可信数据，仅提取事实，渲染前 HTML 转义。
- SKILL/references/README **不出现任何境外商用大模型或平台服务名称**（境外关键词零命中）。

## 7. 测试与验收

- `skill-tests/optimize-seo-content/`：单元测试 + 20 类功能测试 + 50 组鲁棒性测试 + 前向测试；含合规扫描占位。
- 验收指标（对齐赛事）：`quick_validate` 通过、ZIP 根即 `SKILL.md`、名称与提交页一致、AstronClaw 成功部署调用、50 组无崩溃、必需字段完整率 100%、标题候选 ≥3 / 元描述候选 ≥2、关键词含意图/优先级/理由、虚构搜索量/排名保证/批量完全重复出现次数 0、JSON 解析 100%、无乱码、无网络可出基础结果。

## 8. 打包与部署

```bash
python build_zip.py          # 生成 optimize-seo-content.zip（ZIP 根即 SKILL.md，排除 skill-tests/）
```

从赛事页面上传 ZIP，核对 SkillHub / AstronClaw 审核结果。

## 9. 赛事评分映射

| 赛事项 | 分值 | 对应措施 |
|---|---:|---|
| 运行稳定性与鲁棒性 | 30 | 确定性脚本、异常矩阵、降级模式、AstronClaw 实测 |
| 创新性和应用价值 | 30 | 意图分析、可解释推荐、中英双语、多输入、批量防蚕食 |
| 结果质量 | 20 | 候选评分、事实一致性、关键词证据、自动质量门禁 |
| 技术设计与场景编排 | 10 | 提取→生成→脚本校验→批量分析协同 |
| 工程规范与文档 | 5 | 标准目录、README、注释、测试、调用示例 |
| 安全合规 | 5 | URL 安全、隐私、提示注入防护、无虚假 SEO 承诺 |
