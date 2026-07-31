# 输出契约（Output Contract）

> 本文件定义**模型必须输出的行程 JSON 结构**，是 `scripts/validate_itinerary.py` 与 `scripts/render_itinerary.py` 的接口契约（唯一来源）。模型**只输出枚举值 + 文本，禁止输出任何分数/评分/主观打分**。所有枚举取值见 `itinerary-rubric.md`。

---

## 1. 顶层结构

```json
{
  "meta": { ... },
  "days": [ ... ],
  "budget_breakdown": { ... },
  "weather_traffic_notes": [ ... ],
  "preferences_applied": [ ... ],
  "data_source_note": "realtime"
}
```

## 2. meta 字段

| 字段 | 类型 | 约束 |
|---|---|---|
| `title` | string | 行程标题 |
| `origin` | string | 出发地（国内城市） |
| `destination` | string | 目的地（**必须国内**，跨国→合规错误） |
| `start_date` | string | ISO `YYYY-MM-DD` |
| `end_date` | string | ISO `YYYY-MM-DD` |
| `days` | int | 天数，= len(days) |
| `companion_type` | string | 枚举见 rubric §7 |
| `budget_tier` | string | `economy` / `comfort` / `luxury` |
| `total_budget` | number | 总预算（CNY） |
| `currency` | string | 固定 `CNY` |
| `interest_tags` | array<string> | 兴趣标签 |
| `dietary_restrictions` | array<string> | 饮食禁忌，可空 [] |

## 3. days[].segments[] 通用字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 段 ID，如 `d1s1`（第1天第1段） |
| `type` | string | `transport` / `accommodation` / `attraction` / `meal` / `free` |
| `start_time` | string | `HH:MM`（24h） |
| `end_time` | string | `HH:MM`（24h），`start_time < end_time` |
| `title` | string | 段标题 |
| `cost` | number | ≥ 0；`free` 段可省略或 0 |
| `notes` | string | 备注（可空） |
| `cross_midnight` | bool | 仅跨午夜交通段设 true，避免误报时间冲突 |

### 各 type 额外字段
- `transport`：`transport_mode`(枚举) / `from` / `to`
- `accommodation`：`accommodation_type`(枚举) / `location`
- `attraction`：`category`(枚举) / `location`
- `meal`：`meal_type`(枚举)
- `free`：无额外必填

## 4. budget_breakdown 字段

```json
{
  "transport": 480,
  "accommodation": 1200,
  "ticket": 300,
  "meal": 900,
  "contingency": 620,
  "total": 3500
}
```

- 键固定上述 5 类 + `total`。
- `total == Σ(transport+accommodation+ticket+meal+contingency)`。
- `total ≤ total_budget`。
- `contingency ≥ total_budget × 10%`（否则警告）。

## 5. weather_traffic_notes[] 字段

```json
{
  "scope": "day1 杭州",
  "source": "realtime",
  "text": "午后雷阵雨概率60%，建议室内备选",
  "amap_hint": "建议在高德地图查看：搜索『杭州 实时天气』"
}
```

- `source`：`realtime`（高德实时）/ `estimate`（知识库估算）。
- `estimate` 口径下，每条须随附降级提醒文案（见 `interaction-protocol.md` §3）。

## 6. preferences_applied / data_source_note

- `preferences_applied`：array<string>，如 `["budget_tier=comfort","dietary=不吃辣","interest=亲子"]`，展示已应用的长期偏好。
- `data_source_note`：`realtime` / `estimate`，整单主口径，由 SKILL 步骤 4 写入。

## 7. 字段约束（validate 据此判 exit=2）

1. 必填缺失 → 错误：`missing field: meta.destination`
2. 枚举非法 → 错误：`unknown enum transport_mode: X`
3. 目的地非国内 → 错误：`destination not domestic: X`
4. `cost` 负值 → 错误：`negative cost in segment d1s3`
5. 同 day 内时间段重叠（忽略 `cross_midnight` 段）→ 错误：`time overlap day1 seg d1s2 vs d1s3`
6. 连续不同 `location` 的 segments 间隔 < 最小中转分钟（默认 30）→ 警告：`transfer gap < 30min ...`
7. 预算超支 / 合计不一致 → 错误：`budget exceeded: total 5200 > limit 5000`
8. 备用金 < 10% → 警告（stdout 提示）

> 警告（warning）只输出到 stdout，不影响 exit 0；错误（error）累计后 exit 2。
