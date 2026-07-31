# 清洗策略规则（clean 阶段）

本文件是「数据清洗与预处理」阶段的唯一规则来源。清洗由 `scripts/clean_dataset.py` 确定性执行；模型负责依据画像**建议**策略、向用户展示影响面并获确认，不得自行改动任何数据值。

## 1. 三条不可违背的纪律

1. **删除必记录**：任何被删除的行、被改动的单元格，必须出现在清洗日志（行号/列/原值/新值/规则）。日志截断时 `truncated=true` 必须在报告中声明。
2. **flag 优于改值**：业务含义不明的异常值优先 `flag_only`（新增 `__flag_<列>` 标记列，原值不动）；只有用户明确认可截断口径时才用 `clip_*`。
3. **策略需确认**：执行前向用户展示策略 JSON 与影响面（每列缺失数、预计改动口径），用户确认或用户事先声明「按建议执行」后方可调用脚本。

## 2. 策略 DSL 全字段表

```json
{
  "policy": {
    "dedup": true,
    "columns": {
      "<列名>": {
        "format":   {"type": "number", "prefer": "DMY", "mapping": {"旧值": "新值"}},
        "missing":  {"strategy": "fill_median", "constant": "0"},
        "outliers": {"strategy": "clip_iqr", "iqr_k": 1.5, "z": 3.5}
      }
    }
  }
}
```

| 字段 | 取值 | 说明 |
|---|---|---|
| policy.dedup | true/false | 完全重复行去重（最后执行，删除记日志） |
| format.type | none / trim_ws / number / date_iso / enum_map | 格式标准化；number 归一数值写法，date_iso 归一 YYYY-MM-DD（prefer: MDY/DMY），enum_map 需 mapping |
| missing.strategy | keep / drop_rows / fill_mean / fill_median / fill_mode / fill_forward / fill_constant | 缺失处理；fill_mean/fill_median 仅数值列，fill_constant 需 constant |
| outliers.strategy | keep / clip_iqr / clip_zscore / flag_only | 异常值处理，仅数值列；iqr_k 默认 1.5，z 默认 3.5 |

执行顺序固定：**format → missing → outliers → dedup**。异常值边界在 format+missing 之后的可解析数值上计算。

## 3. 默认策略矩阵（模型建议策略时遵循）

| 画像情形 | 建议策略 |
|---|---|
| 数值列缺失率 < 5% | fill_median（稳健，不受异常值影响） |
| 数值列缺失率 5%~30% | fill_median + 报告 warning 说明填充比例 |
| 数值列缺失率 > 30% | keep + 明确提示「该列缺失严重，分析结论需保留缺口」；用户坚持时才 fill |
| 时序数据的日期列缺失 | fill_forward（仅限时间有序场景），并在日志可见 |
| 关键分析列（指标/时间/维度）缺失 | drop_rows（删除必记录）优先于填充 |
| 枚举列取值混乱（大小写/全半角/别名） | enum_map 映射归一，mapping 须向用户展示 |
| 数值含 ¥/千分位/百分号/全角 | format.number |
| 日期格式混杂 | format.date_iso，prefer 取画像多数决结论 |
| 明显录入错误的极端值（如 99999） | flag_only 标记；用户确认口径后可 clip_iqr |
| 疑似重复导出 | dedup: true |

## 4. 校验失败处理

脚本 exit=2 时，按 stderr 的字段级错误清单修复策略 JSON（列名拼写、策略与列类型不匹配、缺少 constant/mapping 等），最多重试 2 次；仍失败则放弃脚本清洗，在报告中声明降级，仅基于画像做定性分析，不得手工改数。
