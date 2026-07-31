# policy-brief · 政策解读 Skill

> 参赛作品：2026 讯飞 AI 开发者大赛 · 政务公文智能处理 Skill 开发挑战赛（方向：政策解读）
> 作品名（须与 `SKILL.md` 的 `name` 一致）：**policy-brief**

## 一、概述

`policy-brief` 是一个面向政务与政策法规场景的智能解读 Skill，对用户提供或本地读取的政策原文执行四类能力：

| 能力 | 模式 key | 说明 |
|---|---|---|
| 政策摘要 | `summary` | 结构化六段摘要 |
| 要点提取 | `extract` | 按分类提取要点，附条款级原文引用 |
| 对比分析 | `compare` | ≥2 份政策的多维度矩阵对比 |
| 政策问答 | `qa` | 仅基于原文作答，未提及明确说明 |

**设计原则**：模型只负责产出结构化 JSON（枚举 + 文本，**禁止任何分数/评分**），所有确定性逻辑由纯标准库 Python 脚本完成——校验、渲染、跨会话记忆。所有结论严格锚定原文、不编造条款，报告强制注入免责声明与数据隐私说明，全程**零联网、零第三方依赖、零密钥**。

## 二、目录结构

```
policy-brief/
├── SKILL.md                  # 技能主文件（frontmatter + 工作流）
├── README.md                 # 本文档
├── references/               # 规则与协议（按需载入上下文）
│   ├── policy-rubric.md      # 枚举与结构唯一来源（脚本常量同步源）
│   ├── output-contract.md    # 四模式 JSON Schema
│   ├── interaction-protocol.md
│   ├── robustness-cases.md   # ≥22 异常场景
│   ├── policy-schema.md      # 跨会话记忆结构
│   └── disclaimer-template.md
├── scripts/                  # 纯标准库脚本（零依赖）
│   ├── validate_policy.py    # 校验模型 JSON（exit 0/2/1）
│   ├── render_report.py      # 自包含 HTML + Markdown 回退
│   ├── policy_store.py       # 跨会话记忆（路径防护 + 降级）
│   └── read_docx.py          # 零依赖 .docx 文本提取
└── examples/                 # 四模式样例 JSON + 渲染 MD
```

> 测试与打包辅助文件位于顶层 `skill-tests/`（不进入 ZIP）与 `build_zip.py`。

## 三、架构：混合零依赖

```
用户原文 ──▶ [读取/解析] ──▶ 模型产出 JSON ──▶ validate_policy.py ──▶ render_report.py ──▶ 报告
                                        │                        │
                                        └── policy_store.py ────┘（跨会话记忆）
```

- **模型**：产出符合 `references/output-contract.md` 的结构化 JSON；不输出分数。
- **validate_policy.py**：字段级校验，`exit 0` 通过 / `2` 需重试 / `1` 致命；失败信息到 stderr 供模型修正（≤2 次）。
- **render_report.py**：生成自包含 HTML（内联 CSS、零外链、确定性、无时间戳）或 Markdown，强制注入免责声明与隐私说明。
- **policy_store.py**：本机记录已解读政策元信息与关注领域，支持连续对比；含路径穿越防护，不可写时降级不中断。
- **read_docx.py**：标准库提取 `.docx` 文本，无第三方依赖。

## 四、使用流程

1. 确定模式与原文来源（粘贴文本 / 本地 `.txt`·`.md`·`.docx`）；对比模式需 ≥2 份。
2. 读取并解析原文（`.docx` 用 `read_docx.py`；`.pdf` 提示粘贴）。
3. 模型按契约产出 JSON（禁分数；`quote` 须为原文逐字）。
4. `python scripts/validate_policy.py --mode <mode> --input <json>` 校验。
5. `python scripts/policy_store.py --action record ...` 记录（可选，降级安全）。
6. `python scripts/render_report.py --mode <mode> --input <json> --output report.html` 渲染交付。

## 五、合规与安全（对应赛事"安全合规 5 分"）

1. **境外关键词零命中**：全文用"模型"泛称，不出现任何境外商用大模型/平台服务名称；仅面向国内政策。
2. **无真实密钥**：无任何密钥/凭据。
3. **无命令注入/SSRF/SSL 禁用**：脚本纯标准库，无 `subprocess`、无网络、无 `eval`；`read_docx.py` 防 Zip Slip。
4. **联网白名单**：脚本零网络请求。
5. **报告含免责声明与数据隐私说明**：`render_report.py` 强制注入。

## 六、鲁棒性（对应"运行稳定性与鲁棒性 30 分"）

覆盖 ≥22 类异常（空输入、非政策文本、超长文档、矛盾条款、缺失字段、单份对比、外文/境外内容、文件损坏、PDF 不支持、HTML 注入转义、追问超范围、幻觉引用、JSON 非法、重试耗尽降级等），详见 `references/robustness-cases.md`。

## 七、本地测试

```bash
python skill-tests/policy-brief/run_tests.py
```

该自测会遍历 `examples/` 四模式 JSON，跑通 `validate_policy.py` → `render_report.py`，并校验关键合规点。

## 八、打包与部署（ AstronClaw / SkillHub ）

```bash
python build_zip.py          # 生成 policy-brief.zip（ZIP 根即 SKILL.md，排除 skill-tests/）
```

参赛提交：在赛题页"作品提交"处上传 `policy-brief.zip`，填入作品名 **policy-brief**（须与 `name` 一致），作品将自动同步 SkillHub 审核。

## 九、评分对应速查

| 评审维度（分值） | 本作品对应设计 |
|---|---|
| 运行稳定性与鲁棒性（30） | 脚本校验 + 22+ 鲁棒性案例 + 异常兜底 |
| 创新性与应用价值（30） | 条款级引用可追溯、跨会话记忆、多维度对比矩阵 |
| 结果质量（20） | 锚定原文、不编造、结构化六段/分类/矩阵 |
| 技术设计与场景编排（10） | 混合零依赖、模型/脚本职责清晰、四模式编排 |
| 工程规范与文档完整性（5） | 本 README + 清晰目录 + 注释 + 测试 |
| 安全合规（5） | 见第五节五类自查 |
