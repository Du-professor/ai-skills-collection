# personalized-travel-planner（个性化旅行规划 Skill）

2026 讯飞 AI 开发者大赛 · 智慧生活助理 Skill 开发挑战赛（SLA-Skill）参赛作品。根据预算、时间、兴趣与同行人，自动生成含交通/住宿/景点/餐饮的详细行程单，并附天气与路况提醒；跨会话记住长期偏好实现「个性化」；支持通过高德地图 MCP 获取实时数据，不可用时降级为知识库估算并明确标注。

## 特性

- **个性化输入**：一次性收集出发地、目的地、日期、预算、同行人、兴趣、忌口；默认值取自长期偏好档案。
- **跨会话记忆（默认关闭）**：仅在您明确选择保存时才把偏好写入本机 JSON 档案（预算档位、常去城市、忌口、兴趣等）；缺省不落盘，本次个性化仅作用于当次对话；不可写则静默降级不中断。
- **实时/估算双模**：检测高德地图 MCP 可用时取实时路况与天气；不可用时降级估算并在行程单明确标注「非实时」。
- **自包含 HTML 行程单**：内联 CSS、可离线打开，含时间轴、地图卡片、天气路况提醒、预算摘要、偏好标签、强制免责声明与隐私说明。
- **高鲁棒性**：预算超支/时间冲突/枚举非法等由确定性脚本校验（exit 0/2/1），异常输入不崩溃。

## 安装与部署

1. 本地打包：`python build_zip.py`（位于仓库根，手工 zipfile，ZIP 根即 `SKILL.md`，自动排除 `skill-tests/`）。
2. 先跑官方快检确保 frontmatter 合规：`python <skill-creator>/scripts/quick_validate.py personalized-travel-planner`。
3. 在赛题页面「作品提交」上传 `personalized-travel-planner.zip`，作品名须与 `SKILL.md` 的 `name` 一致（即 `personalized-travel-planner`）。
4. 在 AstronClaw / SkillHub 部署后，对话中触发词即可调用。

## 用法示例

> 用户：帮我规划杭州 3 日亲子游，预算 5000，从上海出发，8 月初，爱吃但不要吃辣。
>
> 助手：读取偏好 → 一次性确认缺失项 → 判定高德 MCP → 生成行程 JSON → `validate_itinerary.py` 校验 → `preference_store.py` 记忆 → `render_itinerary.py` 生成 `itinerary.html` → 展示行程单。

## 目录结构

```
personalized-travel-planner/
├── SKILL.md                  # 主指令（4 字段 frontmatter + 9 步工作流）
├── README.md                 # 本文档
├── references/               # 规则唯一来源（按需加载）
│   ├── itinerary-rubric.md   # 枚举 + 预算公式 + 兴趣→场景映射
│   ├── output-contract.md    # 行程 JSON schema + 字段约束
│   ├── interaction-protocol.md # 输入顺序 + 高德 MCP 条件调用与降级话术
│   ├── robustness-cases.md   # 22 类异常处置
│   └── preference-schema.md  # 跨会话偏好 JSON 结构
├── scripts/                  # 确定性、纯标准库、离线
│   ├── validate_itinerary.py # 校验/归一化，exit 0/2/1
│   ├── render_itinerary.py   # 自包含 HTML + Markdown 回退
│   └── preference_store.py   # 跨会话偏好读写（降级 + 路径防护）
└── examples/                 # 样本（参与打包）
    ├── itinerary-sample.json
    ├── preference-sample.json
    └── itinerary-sample.md
```

## 脚本契约速览

| 脚本 | 入参 | 出参 | 退出码 |
|---|---|---|---|
| `validate_itinerary.py` | `--plan <json|->` / `--preferences` / `--out` | 归一化 JSON 到 stdout/`--out`；错误到 stderr | 0 成功（含警告）/ 2 校验错误 / 1 意外 |
| `render_itinerary.py` | `--plan <json>` / `--preferences` / `--out` | HTML 到 stdout/`--out`；异常降级 Markdown | 0 成功 / 1 意外 |
| `preference_store.py` | `--read` / `--merge <json|->` [--consent] / `--clear` / `--preferences` | 偏好 JSON 到 stdout；缺省 `--merge` 不写盘 | 0（含降级）/ 1 意外 |

## 偏好存储与隐私（默认关闭）

本 Skill **默认不把任何偏好写入本机**。仅当您在对话中明确表示「保存我的偏好」时，才会经 `--consent` 落盘；否则本次个性化仅作用于当次对话。

- **存储路径（Windows）**：`%APPDATA%\personalized-travel-planner\preferences.json`
- **其它系统**：回退到 `~/.local/share/personalized-travel-planner/preferences.json` 或 `~/.config/personalized-travel-planner/preferences.json`，再回退到系统临时目录
- **保留周期**：无自动过期，除非您清除
- **查看**：`python scripts/preference_store.py --read`
- **导出**：直接复制上述 JSON 文件
- **删除 / 清除**：`python scripts/preference_store.py --clear`，或手动删除该文件
- 偏好仅存本机、不上传任何服务器；行程单不嵌入个人身份信息（PII）

> 设计取舍：跨会话个性化是加分项，但持久化涉及本机文件写入，故默认关闭，把控制权交还给用户。

## 评审维度落点

| 评审维度（满分） | 落点 |
|---|---|
| 稳定性/鲁棒性（30） | robustness-cases 22 类、exit 2 重试 ≤2、注入忽略、偏好不可写降级、高德部分可用降级、全程仅高德白名单 |
| 创新性/应用价值（30） | 跨会话个性化偏好 + 高德实时/估算双模 + 自包含 HTML 行程单（时间轴/地图卡/天气路况） |
| 结果质量（20） | 预算不超支、时间无冲突、枚举合规、行程单信息完整可核验 |
| 技术设计与编排（10） | 模型 + 3 脚本协同、references 渐进披露、枚举/公式唯一来源、零依赖离线 |
| 工程规范与文档（5） | 本 README、SKILL.md 精简、build_zip.py、skill-tests 三件套 |
| 安全合规（5） | 免责+隐私强制注入、无境外关键词、无真实密钥、联网仅高德、无注入/SSRF |

## 局限与免责声明

本行程单由 AI 自动生成，仅供参考，不构成专业旅行/票务/安全建议。实时交通、天气、票价与开放信息请以高德地图及官方渠道为准；出行前请自行核实证件、票务、天气与当地规定，并对自身安全负责。长期偏好仅存于本机本地文件，不会上传任何服务器。

> 作品名须与 `SKILL.md` frontmatter `name` 保持一致：`personalized-travel-planner`。
