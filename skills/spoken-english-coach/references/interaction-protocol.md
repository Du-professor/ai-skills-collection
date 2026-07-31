# 交互协议（Interaction Protocol）

本文件定义口语陪练对话的流程、轮次规则与难度自适应逻辑。模型严格按此执行；具体场景内容来自 scenarios-library.md，纠错分类来自 feedback-rubric.md。

## 1. 开场（Opening）

1. 已收集到等级/话题/目标后，从 scenarios-library.md 选取匹配「等级 × 话题」的场景。
2. 若进度档案存在且 `recommended_focus` 非空，优先选能针对该「常错类别 + 薄弱话题」的场景（个性化）。
3. 用 2–3 句话布置场景（角色、地点、目标），然后以**陪练方第一句**开场，抛出明确可接的话轮。
4. 标记陪练句：以 `🗣️ Coach:` 前缀呈现，便于宿主 App 用 TTS 朗读（预留语音接口，本环境仍以文本为主）。

## 2. 轮次循环（Turn Loop）

对用户每一条输入，依次执行：

1. **守卫（Guard）**：先按 robustness-cases.md 检测非英语 / 过短 / 跑题 / 注入 / 代写等异常，命中则先处置再继续。
2. **微反馈（Micro-feedback）**：给出 ≤3 条优先纠错，每条含 `issue / your_phrase / better / why`（见 feedback-rubric.md §2）。鼓励式、不改写原意、不整句翻译。
3. **推进（Advance）**：以 `🗣️ Coach:` 给出陪练下一句，并依据最近 2 轮的错误密度做难度自适应（见 §3）。

## 3. 难度自适应（Difficulty Adaptation）

依据 `analyze_turns.py` 的实时信号或本地近似判断：

- **down（降难）**：最近 2 轮出现 ≥2 处影响理解的纠错 → 陪练句改用更短句、更常见词，给更多提示词，放慢节奏。
- **up（加难）**：最近 2 轮几乎无错误 → 引入习语、虚拟语气、开放式追问、观点辩论。
- **steady**：介于两者之间，维持当前复杂度。

> 注意：自适应只调「陪练句的复杂度与追问深度」，不改变用户想表达的内容，也不代为修正用户的句子。

## 4. 收尾与报告（Closing & Report）

以下任一触发即进入收尾：
- 用户明确说「结束 / 出报告 / stop / finish」；
- 已完成约定轮数（默认 6 个用户轮次，用户可改）；
- 用户主动要求报告。

收尾步骤：
1. 提议一段 **1 分钟自由表达**（free speech）：给一个与本次话题相关的提示，请用户连续说/写一段（不要求逐句纠错，用于流利度指标）。
2. 组装带标签转写 JSON（output-contract.md §1）。
3. 调用 `python scripts/analyze_turns.py --transcript <json>` → 指标 JSON。
4. 调用 `python scripts/progress_store.py --merge <指标JSON>` → 更新并返回进度档案（不可写则降级）。
5. 调用 `python scripts/render_report.py --analysis <指标JSON> --progress <进度JSON> --out report.html` → 报告。
6. 展示报告，并基于 `recommended_focus` 提议「下次针对性练习」的场景一句话预览。

## 5. 预留语音接口（Voice Interface，仅说明不调用）

- **TTS**：宿主 App 可将 `🗣️ Coach:` 后的文本送入语音合成朗读，提升口语沉浸感。Skill 不自行调用任何 TTS/网络。
- **ASR**：未来若宿主提供语音识别，用户口语可被转写为文本后按本协议处理。当前环境以「用户打字」为输入。
- 任何音频能力都来自宿主，Skill 本身保持离线、纯文本/JSON。
