# AI Skills Collection · AI Skill 作品集

本仓库收录 10 个可复用的 AI Skill，覆盖数据分析、商业洞察、
营销销售、公共信息处理、职业学习、技术决策和安全审计等场景。
你可以直接浏览每个 Skill 的源码，也可以下载对应的 ZIP 包导入兼容的
本地 Skill 运行环境。

维护者：[@Du-professor](https://github.com/Du-professor)

## Skill 分类列表

每个 Skill 都提供源码目录和可下载的 ZIP 包。源码目录中的
`SKILL.md` 描述触发条件、工作流程、输入输出和安全边界。

### 数据分析与商业洞察

这一类别将结构化数据转化为可追溯的指标、洞察和行动建议，适合经营分析、
数据质量检查和竞品研究。

| Skill | 功能说明 | 源码 | 下载 |
| --- | --- | --- | --- |
| `enterprise-data-analyst` | 完成企业数据质量检查、确定性清洗、异常检测、归因、轻量预测和自包含 HTML 报告。 | [查看源码](./skills/enterprise-data-analyst/) | [下载 ZIP](./packages/enterprise-data-analyst-v1.0.0.zip) |
| `ecommerce-competitive-insights` | 分析电商竞品价格、评论情感、用户偏好、差评痛点和跨竞品未满足需求。 | [查看源码](./skills/ecommerce-competitive-insights/) | [下载 ZIP](./packages/ecommerce-competitive-insights-v1.0.0.zip) |

### 营销与销售赋能

这一类别支持内容增长和客户开发，强调证据约束、合规输出和可复用的业务流程。

| Skill | 功能说明 | 源码 | 下载 |
| --- | --- | --- | --- |
| `optimize-seo-content` | 执行关键词发现、搜索意图分析、标题与元描述优化、页面检查和 SEO 质量评估。 | [查看源码](./skills/optimize-seo-content/) | [下载 ZIP](./packages/optimize-seo-content.zip) |
| `prospect-outreach` | 研究潜在客户、评估匹配度与外联准备度，并生成证据化的客户开发内容。 | [查看源码](./skills/prospect-outreach/) | [下载 ZIP](./packages/prospect-outreach-skill-standard.zip) |

### 规划与公共信息处理

这一类别将用户约束或政策原文转换为结构化结果，适合个人规划和公共信息解读。

| Skill | 功能说明 | 源码 | 下载 |
| --- | --- | --- | --- |
| `personalized-travel-planner` | 按预算、时间、兴趣、同行人和长期偏好生成国内多日旅行行程。 | [查看源码](./skills/personalized-travel-planner/) | [下载 ZIP](./packages/personalized-travel-planner.zip) |
| `policy-brief` | 生成政策摘要、条款级要点、多政策对比矩阵和基于原文的问答。 | [查看源码](./skills/policy-brief/) | [下载 ZIP](./packages/policy-brief.zip) |

### 职业发展与语言学习

这一类别提供个性化学习反馈和求职支持，帮助用户持续改进表达和职业材料。

| Skill | 功能说明 | 源码 | 下载 |
| --- | --- | --- | --- |
| `resume-job-fit-coach` | 分析简历与岗位描述的匹配度，提供证据化修改建议、面试题和定制简历。 | [查看源码](./skills/resume-job-fit-coach/) | [下载 ZIP](./packages/resume-job-fit-coach-v1.0.0.zip) |
| `spoken-english-coach` | 提供英语口语角色扮演、即时纠错、会话报告和跨会话学习档案。 | [查看源码](./skills/spoken-english-coach/) | [下载 ZIP](./packages/spoken-english-coach.zip) |

### 开发决策与安全审计

这一类别服务于技术选型和防御性安全工作，帮助团队整理证据、风险和决策边界。

| Skill | 功能说明 | 源码 | 下载 |
| --- | --- | --- | --- |
| `tech-tradeoff-analysis` | 对开源技术方案开展证据化利弊分析，说明适用条件、风险和退出成本。 | [查看源码](./skills/tech-tradeoff-analysis/) | [下载 ZIP](./packages/tech-tradeoff-analysis.zip) |
| `server-vulnerability-evidence-auditor` | 仅针对已授权本机执行防御性漏洞证据核查，并生成结构化整改报告。 | [查看源码](./skills/server-vulnerability-evidence-auditor/) | [下载 ZIP](./packages/server-vulnerability-evidence-auditor.zip) |

## 目录结构

仓库同时保留可浏览源码和可下载发布包。每个 `skills/<name>/`
目录直接包含该 Skill 的 `SKILL.md`，不会额外嵌套同名目录。

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

`skills/` 用于阅读和审查实现，`packages/` 用于下载完整发布包。
不同 Skill 可能包含 `scripts/`、`references/`、`examples/` 或其他资源，
具体要求以各自的 `SKILL.md` 为准。

## 使用方法

你可以按以下流程选择并使用 Skill。导入位置和启动方式取决于你的本地
Skill 运行环境。

1. 浏览上方分类，选择与你的任务匹配的 Skill。
2. 打开“查看源码”链接，阅读 `SKILL.md` 中的适用场景和输入要求。
3. 使用“下载 ZIP”链接获取完整发布包。
4. 解压 ZIP，并确认根目录或唯一子目录中存在 `SKILL.md`。
5. 将完整 Skill 目录导入兼容的本地运行环境。
6. 按 `SKILL.md` 提供必要输入，并遵循其中的安全和使用边界。

如果你只需要审查或二次开发，可以克隆仓库后直接使用 `skills/`
中的源码，不必再次解压 `packages/` 中的发布包。

## License

本仓库中的源码、文档和发布包采用
[MIT License](./LICENSE)。你可以在保留版权和许可证声明的前提下使用、
复制、修改、合并、发布和分发这些内容。
