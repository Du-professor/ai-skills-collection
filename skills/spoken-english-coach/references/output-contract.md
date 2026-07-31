# 输入/输出契约（Output Contract）

本文件定义 Skill 内部所有 JSON 的结构，是 `analyze_turns.py` / `progress_store.py` / `render_report.py` 的接口契约。模型产出的 JSON 必须严格符合本节 schema，否则脚本以 `exit=2` 返回字段级错误，模型按 stderr 修复后重试（≤2 次）。

## 1. 模型产出的「带标签转写」JSON（传给 analyze_turns.py）

读取用户输入与对话后，模型组装如下 JSON，作为 `analyze_turns.py` 的 `--transcript` 参数（或 stdin）：

```json
{
  "session": {
    "language": "en",
    "level": "B1",
    "topic": "travel",
    "scenario": "在机场值机柜台办理托运",
    "user_turns": 6
  },
  "turns": [
    {
      "role": "user",
      "text": "I go to London yesterday.",
      "errors": [
        {"category": "grammar-tense", "user_phrase": "I go to London yesterday", "better": "I went to London yesterday", "why": "过去时间用一般过去时"}
      ]
    }
  ],
  "free_speech": {
    "prompt": "用 1 分钟说说你理想的旅行目的地",
    "text": "I want to go to ..."
  }
}
```

字段约束：
- `session.level` ∈ {A1,A2,B1,B2,C1,C2}。
- `turns[].errors[].category` 必须是 feedback-rubric.md §1 的枚举值；未知类别脚本报错。
- `free_speech` 可省略；省略时相关指标按空处理。
- 模型**不得**在 JSON 中写入任何分数或计数，这些由脚本计算。

## 2. analyze_turns.py 输出（指标 JSON）

```json
{
  "turns": 7,
  "user_turns": 6,
  "error_counts": {"grammar-tense": 2, "collocation": 1},
  "total_errors": 3,
  "ttr": 0.52,
  "unique_tokens": 83,
  "total_tokens": 160,
  "avg_sentence_len": 11.4,
  "level_fit_ratio": 0.71,
  "band": "B",
  "band_score": 81.0,
  "difficulty_adjustment": "steady"
}
```

- `ttr` = unique_tokens / total_tokens（词汇多样性，去标点、转小写、按空白切分）。
- `level_fit_ratio` = 适配等级的词汇/结构占比（脚本按内置分级词表粗估，仅供参考）。
- `band` / `band_score` / `difficulty_adjustment` 由脚本按固定权重计算（公式见脚本内注释，唯一来源）。

## 3. progress_store.py 的进度 JSON（个性化记忆）

路径：用户数据目录下 `spoken-english-coach-progress.json`（具体路径由脚本按平台决定；不可写时降级，见 §5）。

```json
{
  "version": 1,
  "updated_at": "2026-07-29",
  "total_sessions": 3,
  "error_profile": {"grammar-tense": {"count": 5, "last_seen": "2026-07-29"}, "collocation": {"count": 2, "last_seen": "2026-07-20"}},
  "weak_topics": {"travel": 2, "interview": 1},
  "strong_topics": ["daily-life"],
  "ttr_history": [0.48, 0.51, 0.52],
  "band_history": ["C", "B", "B"],
  "recommended_focus": {"category": "grammar-tense", "topic": "travel"}
}
```

- `error_profile`：跨会话累计各类别出现次数，用于识别「常错点」。
- `weak_topics`：各话题累计出错/困难次数。
- `recommended_focus`：下次场景自动针对的点（取 error_profile 最高频类别 + weak_topics 最高频话题）。

## 4. render_report.py 输出

- 主输出：自包含 HTML 文件（内联 CSS，**无任何外部网络请求**，无 `<script src>`、无外链字体/图片）。
- 回退：同内容 Markdown 文本（stdout 或 `.md`）。
- 报告章节顺序：会话总结 → 错误分类与示例 → 强项 → Top3 改进项 → 个性化下一步（来自进度档案）→ 进度快照 → 免责声明。

## 5. 脚本通用退出码与降级

- `0`：成功，stdout 为结果 JSON / HTML。
- `2`：输入校验失败，stderr 输出字段级错误（如 `missing field: session.level` / `unknown category: foo`），模型据此修复重试 ≤2 次。
- `1`：意外错误（如文件不可读），stderr 说明；Skill 降级为「仅当次报告、跳过进度读写」，不中断用户流程。
- 进度文件不可写：progress_store.py 返回空档案（`total_sessions:0`）并在 stderr 记 warning，Skill 继续，不报错退出。
