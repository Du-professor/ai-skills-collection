# spoken-english-coach · 英语口语陪练 Skill

> 赛事：2026 iFLYTEK AI 开发者大赛 · 教育智能辅助与个性化学习 Skill 开发挑战赛
> 方向：个性化学习 — 口语练习陪练

一个可复用的英语口语陪练能力包：以角色扮演对话为载体，逐轮给鼓励式纠错，会话结束产出**确定性**报告，并跨会话记住常错点与薄弱话题，下次自动针对出题（个性化学习）。

## 特性

- **角色扮演陪练**：按等级（A1–C2）× 话题（旅行/面试/职场/日常…）开启沉浸式对话。
- **逐轮即时纠错**：每轮 ≤3 条优先反馈，含「问题 / 原句 / 更好说法 / 为什么」，鼓励式、不改写原意。
- **确定性报告**：错误分类计数、词汇多样性 TTR、平均句长、等级适配度、A–E 档位分，全部由脚本按固定公式算出，模型不自行给分。
- **跨会话个性化**：本地进度档案记录常错类别与薄弱话题，自动生成下次针对性场景（紧扣赛事「个性化学习」主题）。
- **难度自适应**：根据近期错误密度实时升降陪练复杂度。
- **离线安全**：纯标准库 Python，无网络、无密钥、无越权；预留 TTS/ASR 语音接口说明。

## 安装与部署

1. 本地开发：`git clone` 或直接解包，确保目录含 `SKILL.md`。
2. 参赛提交：用仓库根目录的 `build_zip.py` 打包为 ZIP（根即 `SKILL.md`），在赛题页上传，作品名填 `spoken-english-coach`（须与 frontmatter `name` 一致）。
3. 平台部署：SkillHub / AstronClaw 自动建技能；模型按 `description` 触发词加载。

## 用法示例

```
用户：我想练英语口语，B1，旅行话题。
Skill：（布置机场值机场景）🗣️ Coach: Good morning! Are you checking in for the flight to Tokyo? ...
用户：I go to London yesterday.
Skill：时态小提醒——「yesterday」用过去时更自然：I went to London yesterday。继续～
...（6 轮后）
Skill：（自由表达 + 调脚本）→ 输出 HTML 报告 + 下次针对性练习预览
```

## 目录结构

```
spoken-english-coach/
├── SKILL.md                     # 主指令（frontmatter + 正文）
├── README.md                    # 本文件
├── references/                  # 规则唯一来源（按需加载）
│   ├── interaction-protocol.md  # 对话流程 / 难度自适应 / 语音接口
│   ├── feedback-rubric.md       # 错误枚举 / 纠错风格 / 评分档位
│   ├── scenarios-library.md     # 话题×等级场景卡
│   ├── output-contract.md       # JSON schema 与脚本契约
│   └── robustness-cases.md      # 异常场景处置
├── scripts/                     # 确定性、纯标准库、离线
│   ├── analyze_turns.py         # 指标 + A–E 档位分
│   ├── render_report.py         # 自包含 HTML 报告 + Markdown 回退
│   └── progress_store.py        # 跨会话进度记忆（不可写则降级）
└── examples/
    ├── session-sample.md        # 完整示例对话 + 报告
    └── progress-sample.json     # 示例进度档案
```

## 脚本契约（速览）

| 脚本 | 输入 | 输出 | 退出码 |
|------|------|------|--------|
| `analyze_turns.py` | 带标签转写 JSON（`--transcript`） | 指标 JSON | 0 成功 / 2 校验失败（字段级 stderr）/ 1 意外 |
| `progress_store.py` | 指标 JSON（`--merge`） | 合并后进度 JSON | 0（含降级）/ 1 意外 |
| `render_report.py` | 指标 + 进度（+ 转写）JSON | HTML 文件 + Markdown(stdout) | 0 / 1 意外 |

> 详细 schema 见 [references/output-contract.md](references/output-contract.md)。

## 评审维度映射

| 评审维度（满分） | 落点 |
|------------------|------|
| 稳定性/鲁棒性 (30) | robustness-cases 22 类异常、脚本重试降级、注入忽略、全程离线 |
| 创新性/应用价值 (30) | 跨会话个性化 + 难度自适应 + 确定性报告，紧扣「个性化学习」 |
| 结果质量 (20) | 错误分类准确、报告完整（总结/分类/强项/Top3/下一步）、示例可核验 |
| 技术设计与编排 (10) | 模型+3 脚本协同、references 渐进披露、语言无关可扩展 |
| 工程规范与文档 (5) | 本 README、代码注释、目录清晰、build 脚本 |
| 安全合规 (5) | 离线、无密钥、无越权、免责声明 |

## 局限与免责声明

- 本环境以**文本对话**为主；音频（TTS/ASR）来自宿主，Skill 本身不调用。
- 发音相关反馈为**文本近似提示**（音近词混淆提示），不代表真实发音评测。
- 报告为口语练习反馈，**非专业语言测评**，不用于任何正式考试判定。
- 跨会话记忆依赖本地可写路径；不可写时自动降级为单次报告，不影响使用。
