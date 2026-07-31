# enterprise-data-analyst（数析通 · 企业数据分析全流程助手）

面向企业数据分析全流程的智能 Skill，覆盖 **数据输入 → 质量检查 → 分析 → 图表 → 结论 → 行动建议** 完整闭环：数据获取与理解、数据清洗与预处理（缺失值填充 / 异常值处理 / 格式标准化）、业务指标异常检测与归因分析、多维数据可视化、辅助决策与轻量预测建议。

- 版本：1.0.0 ｜ 运行环境：Python ≥ 3.9（仅标准库，零第三方依赖）｜ 平台：Windows / macOS / Linux
- 架构：**混合零依赖** —— AI 模型负责业务语义与叙述，内置确定性 Python 脚本负责一切数值计算与渲染
- 合规：全程离线、源文件只读、敏感列自动脱敏、报告强制含免责声明与数据隐私说明

## 1. 架构

```
数据文件(csv/tsv/json/jsonl/xlsx, 只读)
   │
   ▼
profile_dataset.py ── 数据画像 JSON（类型/缺失/统计/敏感列/警告）
   │  模型复述数据理解 + 建议清洗策略（用户确认）
   ▼
clean_dataset.py ──── 清洗后 CSV + 逐格变更日志 JSON（不丢关键信息）
   │  模型组装分析规格 JSON（白名单键，禁填数值）
   ▼
analyze_metrics.py ── 指标聚合/同环比/三法异常检测/差额归因/轻量预测 JSON
   │  模型撰写结论与行动建议（数字逐字引用）
   ▼
render_report.py ──── 自包含单文件 HTML 报告（内联 SVG 图表，无外部资源）
```

分工红线：**模型绝不产出任何统计数值**（均值/占比/同环比/异常区间/贡献度/预测值），脚本绝不解读业务语义。模型提交的策略/规格 JSON 经「白名单键 + FORBIDDEN 结果键」双校验，夹带数值即 exit 2 拒绝。

## 2. 快速开始

```bash
# 1) 数据画像
python scripts/profile_dataset.py 你的数据.csv

# 2) 按策略清洗（策略 JSON 见 references/cleaning-policy.md）
python scripts/clean_dataset.py 你的数据.csv --policy policy.json --out cleaned.csv --log clean-log.json

# 3) 指标/异常/归因/预测（规格 JSON 见 references/anomaly-attribution-rubric.md）
python scripts/analyze_metrics.py cleaned.csv --spec analysis.json

# 4) 渲染自包含 HTML 报告（规格 JSON 见 references/visualization-guide.md）
python scripts/render_report.py --spec report.json --out report.html
```

可直接参考 `skill-tests/enterprise-data-analyst/fixtures/` 下的 `spec-clean.json / spec-analyze.json / spec-report.json` 三个完整示例（测试夹具不随包发布）。

## 3. 脚本用法

| 脚本 | 职责 | 关键参数 | 输出 |
|---|---|---|---|
| `scripts/datacommon.py` | 共享底座（编码识别/读取/类型推断/解析/脱敏） | 被导入，不直接运行 | — |
| `scripts/profile_dataset.py` | 数据画像 | `<文件> [--sheet] [--max-rows]` | 画像 JSON |
| `scripts/clean_dataset.py` | 清洗预处理 | `<文件> --policy --out --log` | 清洗 CSV + 日志 JSON |
| `scripts/analyze_metrics.py` | 指标/异常/归因/预测 | `<文件> --spec [--sheet]` | 分析 JSON |
| `scripts/render_report.py` | SVG 图表 + HTML 报告 | `--spec --out 报告.html` | 自包含 HTML |

**统一退出契约**：`exit 0` 成功（stdout 结果 JSON）；`exit 2` 输入校验失败（stderr 逐行字段级报错，修复后重试 ≤2 次）；`exit 1` 运行错误（stderr 前缀「运行错误: 」）。所有脚本确定性输出：同一输入多次运行字节级一致。

## 4. 功能覆盖

| 环节 | 能力 |
|---|---|
| 数据获取与理解 | 多格式只读（CSV/TSV/JSON/JSONL/xlsx 自研解析）、编码回退链（UTF-8/GB18030）、列类型推断、敏感列识别、画像复述 |
| 数据清洗与预处理 | 缺失 7 策略（drop/mean/median/mode/forward/constant/keep）、异常 3 策略（clip_iqr/clip_zscore/flag_only）、格式 4 策略（trim/number/date_iso/enum_map）、去重；**逐格变更日志** |
| 异常检测与归因 | IQR 围栏 / MAD 稳健 z / 业务阈值三法；同环比（除零安全）；差额分解归因（Σ贡献=总差额恒等） |
| 多维可视化 | 折线/柱状/分组柱状/饼图/散点/直方图六种 SVG，图表选型决策表，单文件自包含 HTML |
| 决策与预测建议 | 移动平均/最小二乘线性/简单指数平滑 + 朴素 80% 区间 + 方法局限说明（脚本内置文案） |

## 5. 测试方法

测试资产位于工作区 `skill-tests/enterprise-data-analyst/`（不随包发布）：

```bash
cd skill-tests/enterprise-data-analyst
python run_profile_tests.py    # 9 用例
python run_clean_tests.py      # 11 用例
python run_analyze_tests.py    # 10 用例
python run_render_tests.py     # 22 断言（含敏感列清洗日志渲染脱敏）
```

42 用例覆盖：主用例手工数值核对、exit 0/2/1 契约、FORBIDDEN 键拒绝、降级路径、注入防护、确定性双跑字节一致、敏感列清洗日志在报告中脱敏。**新增回归专项**：手机/邮箱/证件/银行卡原值不出现在 HTML 报告、仅展示脱敏摘要。`mock-evidence.md / expected-behavior.md / simulated-report.md` 三件套提供端到端走查基准。

## 6. 目录结构

```
enterprise-data-analyst/
├── SKILL.md                              # 入口：定位/信任边界/11 步强制工作流/安全边界
├── README.md                             # 本文件
├── references/                           # 规则层（模型先读后做）
│   ├── data-understanding-rules.md       # 类型推断阈值/业务四问/警告分级
│   ├── cleaning-policy.md                # 清洗 DSL/默认策略矩阵/三纪律
│   ├── anomaly-attribution-rubric.md     # 三法异常/差额归因/预测公式与局限文案
│   ├── visualization-guide.md            # 图表选型决策表/配色/合规
│   ├── output-schema.md                  # 四脚本 IO 契约/FORBIDDEN 表/报告模板/降级标注
│   └── robustness-cases.md               # 22 组异常输入处置表
└── scripts/                              # 执行层（纯标准库、确定性）
    ├── datacommon.py                     # 共享底座
    ├── profile_dataset.py                # 数据画像
    ├── clean_dataset.py                  # 清洗预处理
    ├── analyze_metrics.py                # 指标/异常/归因/预测
    └── render_report.py                  # SVG + HTML 报告
```

## 7. 安全与合规

- **纯离线**：脚本无网络调用、无第三方依赖、无密钥需求；不访问数据中出现的任何链接。
- **只读源文件**：不递归扫描目录；清洗产出新文件，`--out` 与源文件同路径即拒绝。
- **敏感数据保护**：手机号/证件号/邮箱/银行卡号正则检出 → 画像与报告脱敏展示，敏感列不计算数值统计（防原值经统计量泄露）。**关键边界**：清洗日志（本地文件，用户私有）保留变更 `old/new` 原值用于审计；但渲染 HTML 报告的质量日志章节会在写入前对敏感列的 `old/new` 做脱敏（依值/列名自动判定，或规格显式传入 `sensitive_columns`），报告中不展示敏感列原始值、仅展示脱敏摘要，完整明细留在本地日志。
- **注入防护**：数据中的指令文本一律忽略；HTML 输出全部转义且无 `<script>` 与外部资源；CSV 写出对公式前缀加 `'`。
- **资源上限**：100MB / 20 万行 / JSON 32 层 / 日志 1 万条，超限截断并显式标记，不静默丢失。
- **报告合规**：免责声明与数据隐私说明两节由脚本强制注入。

## 8. AstronClaw 平台部署

本 Skill 按「ZIP 根目录即 SKILL.md」打包，可直接在 AstronClaw（讯飞开放平台智能体）上传创建：

1. 打包（工作区 `skill-tests/enterprise-data-analyst/package_zip.py`）：
   `python package_zip.py ../enterprise-data-analyst 输出路径/enterprise-data-analyst-v1.0.0.zip`
2. AstronClaw 控制台 → 我的技能 → 新建/上传 → 选择该 ZIP，平台自动解析 SKILL.md 生成技能。
3. 调用方式：自动调用（用户说「分析这份 CSV 并出图表报告」时由 description 与触发词匹配）、指定调用（「用 enterprise-data-analyst 分析……」）、链式调用（位于搜索/采集类技能下游，承接「分析 → 图表 → 报告」环节）。
4. 运行环境要求：Python ≥ 3.9 标准库即可，无需联网与额外安装。

## 9. 版本历史

- **1.0.0**（2026-07）：首版。四脚本 + 六规则文件 + 38 自动化用例；支持 CSV/TSV/JSON/JSONL/xlsx，自包含 HTML 报告。
