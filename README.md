# AI Skills Collection

可复用的 AI Skill 作品集，支持源码浏览与 ZIP 包下载。

A reusable collection of AI Skills with browsable source code and
downloadable ZIP packages.

[中文](#中文) · [English](#english)

## 中文

### 项目简介

本仓库收录 10 个可复用的 AI Skill，覆盖数据分析、商业洞察、营销销售、
公共信息处理、职业发展、语言学习、技术决策和防御性安全审计等场景。

仓库采用源码与发布包并存的结构：

- `skills/`：用于浏览、审查和二次开发 Skill 源码。
- `packages/`：用于直接下载完整 ZIP 发布包。
- 每个 Skill 源码目录直接包含 `SKILL.md`，用于说明适用场景、工作流程、
  输入输出及安全边界。

### Skill 分类

#### 数据分析与商业洞察

| Skill | 功能说明 | 源码 | 发布包 |
| --- | --- | --- | --- |
| `enterprise-data-analyst` | 企业数据质量检查、确定性清洗、异常检测、归因、轻量预测及自包含 HTML 报告。 | [查看源码](./skills/enterprise-data-analyst/) | [下载 ZIP](./packages/enterprise-data-analyst-v1.0.0.zip) |
| `ecommerce-competitive-insights` | 电商竞品价格、评论情感、用户偏好、差评痛点及未满足需求分析。 | [查看源码](./skills/ecommerce-competitive-insights/) | [下载 ZIP](./packages/ecommerce-competitive-insights-v1.0.0.zip) |

#### 营销与销售赋能

| Skill | 功能说明 | 源码 | 发布包 |
| --- | --- | --- | --- |
| `optimize-seo-content` | 关键词发现、搜索意图分析、标题与元描述优化、页面检查及 SEO 质量评估。 | [查看源码](./skills/optimize-seo-content/) | [下载 ZIP](./packages/optimize-seo-content.zip) |
| `prospect-outreach` | 潜在客户研究、匹配度与外联准备度评估，以及证据化客户开发内容生成。 | [查看源码](./skills/prospect-outreach/) | [下载 ZIP](./packages/prospect-outreach-skill-standard.zip) |

#### 规划与公共信息处理

| Skill | 功能说明 | 源码 | 发布包 |
| --- | --- | --- | --- |
| `personalized-travel-planner` | 按预算、时间、兴趣、同行人和长期偏好生成国内多日旅行行程。 | [查看源码](./skills/personalized-travel-planner/) | [下载 ZIP](./packages/personalized-travel-planner.zip) |
| `policy-brief` | 生成政策摘要、条款级要点、多政策对比矩阵和基于原文的问答。 | [查看源码](./skills/policy-brief/) | [下载 ZIP](./packages/policy-brief.zip) |

#### 职业发展与语言学习

| Skill | 功能说明 | 源码 | 发布包 |
| --- | --- | --- | --- |
| `resume-job-fit-coach` | 分析简历与岗位描述的匹配度，提供证据化修改建议、面试题和定制简历。 | [查看源码](./skills/resume-job-fit-coach/) | [下载 ZIP](./packages/resume-job-fit-coach-v1.0.0.zip) |
| `spoken-english-coach` | 英语口语角色扮演、即时纠错、会话报告及跨会话学习档案。 | [查看源码](./skills/spoken-english-coach/) | [下载 ZIP](./packages/spoken-english-coach.zip) |

#### 技术决策与安全审计

| Skill | 功能说明 | 源码 | 发布包 |
| --- | --- | --- | --- |
| `tech-tradeoff-analysis` | 对开源技术方案开展证据化利弊分析，说明适用条件、风险和退出成本。 | [查看源码](./skills/tech-tradeoff-analysis/) | [下载 ZIP](./packages/tech-tradeoff-analysis.zip) |
| `server-vulnerability-evidence-auditor` | 仅针对已授权本机执行防御性漏洞证据核查，并生成结构化整改报告。 | [查看源码](./skills/server-vulnerability-evidence-auditor/) | [下载 ZIP](./packages/server-vulnerability-evidence-auditor.zip) |

### 目录结构

```text
.
├── README.md
├── LICENSE
├── skills/
│   ├── ecommerce-competitive-insights/
│   ├── enterprise-data-analyst/
│   ├── optimize-seo-content/
│   ├── personalized-travel-planner/
│   ├── policy-brief/
│   ├── prospect-outreach/
│   ├── resume-job-fit-coach/
│   ├── server-vulnerability-evidence-auditor/
│   ├── spoken-english-coach/
│   └── tech-tradeoff-analysis/
└── packages/
    ├── ecommerce-competitive-insights-v1.0.0.zip
    ├── enterprise-data-analyst-v1.0.0.zip
    ├── optimize-seo-content.zip
    ├── personalized-travel-planner.zip
    ├── policy-brief.zip
    ├── prospect-outreach-skill-standard.zip
    ├── resume-job-fit-coach-v1.0.0.zip
    ├── server-vulnerability-evidence-auditor.zip
    ├── spoken-english-coach.zip
    └── tech-tradeoff-analysis.zip
```

### 使用方法

#### 直接下载发布包

1. 在 Skill 分类中选择所需 Skill。
2. 点击对应的“下载 ZIP”链接。
3. 解压文件，并确认根目录或唯一子目录中存在 `SKILL.md`。
4. 将完整 Skill 目录导入兼容的本地 Skill 运行环境。
5. 按照 `SKILL.md` 提供输入，并遵循其中的安全和使用边界。

#### 浏览或二次开发源码

```bash
git clone https://github.com/Du-professor/ai-skills-collection.git
cd ai-skills-collection
```

进入 `skills/<skill-name>/`，先阅读 `SKILL.md`，再根据需要检查
`scripts/`、`references/`、`examples/` 等资源。

### 许可证

本仓库中的源码、文档和发布包采用 [MIT License](./LICENSE)。
使用、复制、修改、合并、发布或分发时，请保留版权和许可证声明。

### 维护者

[@Du-professor](https://github.com/Du-professor)

---

## English

### About

This repository contains 10 reusable AI Skills for data analysis, business
insights, marketing and sales, public information processing, career
development, language learning, technology decisions, and defensive security
auditing.

The repository provides both source code and release packages:

- `skills/`: browse, review, or extend the Skill source code.
- `packages/`: download complete ZIP release packages.
- Each Skill source directory directly contains a `SKILL.md` that defines its
  use cases, workflow, inputs, outputs, and safety boundaries.

### Skill Categories

#### Data Analysis and Business Insights

| Skill | Description | Source | Package |
| --- | --- | --- | --- |
| `enterprise-data-analyst` | Enterprise data quality checks, deterministic cleaning, anomaly detection, attribution, lightweight forecasting, and self-contained HTML reports. | [View source](./skills/enterprise-data-analyst/) | [Download ZIP](./packages/enterprise-data-analyst-v1.0.0.zip) |
| `ecommerce-competitive-insights` | E-commerce competitor pricing, review sentiment, customer preferences, pain points, and unmet-needs analysis. | [View source](./skills/ecommerce-competitive-insights/) | [Download ZIP](./packages/ecommerce-competitive-insights-v1.0.0.zip) |

#### Marketing and Sales Enablement

| Skill | Description | Source | Package |
| --- | --- | --- | --- |
| `optimize-seo-content` | Keyword discovery, search-intent analysis, title and meta-description optimization, page review, and SEO quality assessment. | [View source](./skills/optimize-seo-content/) | [Download ZIP](./packages/optimize-seo-content.zip) |
| `prospect-outreach` | Prospect research, fit and outreach-readiness assessment, and evidence-based outreach content generation. | [View source](./skills/prospect-outreach/) | [Download ZIP](./packages/prospect-outreach-skill-standard.zip) |

#### Planning and Public Information

| Skill | Description | Source | Package |
| --- | --- | --- | --- |
| `personalized-travel-planner` | Multi-day domestic itineraries based on budget, time, interests, companions, and long-term preferences. | [View source](./skills/personalized-travel-planner/) | [Download ZIP](./packages/personalized-travel-planner.zip) |
| `policy-brief` | Policy summaries, clause-level highlights, multi-policy comparison matrices, and source-grounded Q&A. | [View source](./skills/policy-brief/) | [Download ZIP](./packages/policy-brief.zip) |

#### Career Development and Language Learning

| Skill | Description | Source | Package |
| --- | --- | --- | --- |
| `resume-job-fit-coach` | Resume-to-job fit analysis with evidence-based revisions, interview questions, and tailored resumes. | [View source](./skills/resume-job-fit-coach/) | [Download ZIP](./packages/resume-job-fit-coach-v1.0.0.zip) |
| `spoken-english-coach` | Spoken-English role-play, immediate corrections, session reports, and cross-session learning profiles. | [View source](./skills/spoken-english-coach/) | [Download ZIP](./packages/spoken-english-coach.zip) |

#### Technical Decisions and Security Auditing

| Skill | Description | Source | Package |
| --- | --- | --- | --- |
| `tech-tradeoff-analysis` | Evidence-based trade-off analysis for open-source technologies, including fit, risks, and exit costs. | [View source](./skills/tech-tradeoff-analysis/) | [Download ZIP](./packages/tech-tradeoff-analysis.zip) |
| `server-vulnerability-evidence-auditor` | Defensive vulnerability evidence checks on authorized local machines with structured remediation reports. | [View source](./skills/server-vulnerability-evidence-auditor/) | [Download ZIP](./packages/server-vulnerability-evidence-auditor.zip) |

### Repository Structure

```text
.
├── README.md
├── LICENSE
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md
│       └── ...
└── packages/
    └── <skill-package>.zip
```

### Usage

#### Download a release package

1. Choose a Skill from the categories above.
2. Select its “Download ZIP” link.
3. Extract the archive and confirm that `SKILL.md` exists at the root or in
   the single top-level directory.
4. Import the complete Skill directory into a compatible local Skill runtime.
5. Provide the required inputs and follow the safety and usage boundaries in
   `SKILL.md`.

#### Browse or extend the source

```bash
git clone https://github.com/Du-professor/ai-skills-collection.git
cd ai-skills-collection
```

Open `skills/<skill-name>/` and read `SKILL.md` first. Then inspect
`scripts/`, `references/`, `examples/`, or other resources as needed.

### License

The source code, documentation, and release packages in this repository are
licensed under the [MIT License](./LICENSE). Retain the copyright and license
notices when using, copying, modifying, merging, publishing, or distributing
the contents.

### Maintainer

[@Du-professor](https://github.com/Du-professor)
