# 偏好档案结构（Preference Schema）

> 跨会话长期偏好 JSON 结构，`scripts/preference_store.py` 读写依据。仅存于本机本地文件，不上传任何服务器。**默认不持久保存**：仅当用户明确同意（`--consent`）时才写盘，否则 `--merge` 仅在本次会话内合并、不落盘。

```json
{
  "version": 1,
  "updated_at": "2026-07-29",
  "budget_tier": "comfort",
  "budget_currency": "CNY",
  "frequent_cities": ["杭州", "成都"],
  "dietary_restrictions": ["素食", "不吃辣"],
  "companion_types": ["家庭"],
  "interest_tags": ["美食", "自然", "历史"],
  "preferred_transport": ["高铁", "打车"],
  "avoid": ["人流密集"],
  "last_destinations": ["西安"],
  "recommended_next": { "destination": null, "reason": null }
}
```

## 字段说明
- `version`：结构版本，固定 1。
- `updated_at`：最近更新日期（ISO）。
- `budget_tier`：默认预算档位（economy/comfort/luxury）。
- `budget_currency`：固定 `CNY`。
- `frequent_cities`：常去城市，用于默认值与推荐。
- `dietary_restrictions`：饮食禁忌集合。
- `companion_types`：常用同行人类型。
- `interest_tags`：长期兴趣标签。
- `preferred_transport`：偏好交通方式。
- `avoid`：希望回避的体验（如人流密集、高强度户外）。
- `last_destinations`：最近去过的目的地（最近在前）。
- `recommended_next`：由脚本按最近目的地/兴趣推导的下一步推荐（**非评分**，仅基于计数）。

## 合并规则（--merge）
- 标量（budget_tier 等）以本次为准覆盖。
- 数组（frequent_cities / interest_tags / dietary_restrictions / companion_types / preferred_transport）做**去重追加**，并保留最近 8 个。
- `last_destinations` 把本次目的地插到最前，去重，保留最近 6 个。
- `recommended_next` 由脚本按 `interest_tags` + `frequent_cities` 推荐一个尚未去过的城市（可空）。
- `updated_at` 更新为今天。

## 空档案（不可写 / 不存在）
返回所有字段为空值/空数组的结构，exit 0，不中断主流程。
