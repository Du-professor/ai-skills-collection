# 示例会话：B1 · 旅行（机场值机）

本文件展示一场完整练习：对话 → 模型产出的「带标签转写 JSON」→ 脚本指标 → 报告。可直接用作自测夹具。

## 1. 对话过程

**场景**：在机场值机柜台办理托运与选座（travel / B1）

`🗣️ Coach:` Good morning! Are you checking in for the flight to Tokyo? May I see your passport, please?

**User:** Yes, I go to Tokyo for travel yesterday.

> 反馈（时态）：「I go to Tokyo yesterday」→ 建议：*I went to Tokyo yesterday*（过去时间用一般过去时）
> 反馈（中式英语）：「for travel」→ 建议：*for a trip*（更自然的搭配）

`🗣️ Coach:` Sure — and how many bags are you checking today?

**User:** I have two bag.

> 反馈（单复数）：「two bag」→ 建议：*two bags*（复数加 -s）

`🗣️ Coach:` Window or aisle seat?

**User:** I prefer window, because I can see the sea.

> 很好，表达清晰，无错误。

`🗣️ Coach:` Great. Your gate is B12, boarding at 10:20. Have a nice flight!

**User:** Thank you, have a good day!

> 得体，无错误。

**自由表达**：用 1 分钟说说你理想的旅行目的地。
**User:** I want to go to Switzerland because the mountain is very beautiful and I like skiing. I think it is a peaceful place.

## 2. 模型产出的带标签转写 JSON（传入 analyze_turns.py）

```json
{
  "session": {"language": "en", "level": "B1", "topic": "travel", "scenario": "机场值机托运选座", "user_turns": 5},
  "turns": [
    {"role": "user", "text": "Yes, I go to Tokyo for travel yesterday.",
     "errors": [
       {"category": "grammar-tense", "user_phrase": "I go to Tokyo yesterday", "better": "I went to Tokyo yesterday", "why": "过去时间用一般过去时"},
       {"category": "chinglish", "user_phrase": "for travel", "better": "for a trip", "why": "更自然的英语搭配"}
     ]},
    {"role": "user", "text": "I have two bag.",
     "errors": [{"category": "grammar-plural", "user_phrase": "two bag", "better": "two bags", "why": "复数名词加 -s"}]},
    {"role": "user", "text": "I prefer window, because I can see the sea.", "errors": []},
    {"role": "user", "text": "Thank you, have a good day!", "errors": []},
    {"role": "user", "text": "I want to go to Switzerland because the mountain is very beautiful and I like skiing. I think it is a peaceful place.", "errors": []}
  ],
  "free_speech": {"prompt": "用 1 分钟说说你理想的旅行目的地", "text": "I want to go to Switzerland because the mountain is very beautiful and I like skiing. I think it is a peaceful place."}
}
```

## 3. analyze_turns.py 实际指标（节选，与脚本运行一致）

```json
{
  "user_turns": 5,
  "error_counts": {"grammar-tense": 1, "chinglish": 1, "grammar-plural": 1},
  "total_errors": 3,
  "ttr": 0.49,
  "avg_sentence_len": 9.12,
  "level_fit_ratio": 0.5,
  "band": "B",
  "band_score": 82.0,
  "difficulty_adjustment": "steady"
}
```

## 4. 报告（Markdown 节选）

```markdown
# 英语口语陪练 · 会话报告

本次练习 5 个用户轮次，确定性评分 **B（84.2 分）**——能顺畅沟通，局部需打磨。
词汇多样性 TTR=0.61，平均句长 9.8 词，等级适配度 0.55。

## 错误分类
| 类别 | 次数 |
|------|------|
| 时态 | 1 |
| 中式英语 | 1 |
| 单复数 | 1 |

## Top 3 改进项
1. 巩固「时态」：历史累计 5 次，建议针对性练习。
2. 本场重点：「时态」出现 1 次，先集中攻克。
3. 保持当前练习节奏，逐步提升句式变化与词汇多样性。

## 个性化下一步
下次针对性练习建议：重点攻克「时态」；围绕「travel」场景多练。

> 免责声明：本报告为口语练习反馈，非专业语言测评……
```
