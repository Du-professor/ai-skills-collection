# 输出契约（四脚本 IO schema / FORBIDDEN 表 / 报告模板 / 降级标注）

本文件是模型与脚本之间的唯一契约。模型阅读本文件后**只按 schema 组装输入、只按模板撰写叙述**，任何数值不得出自模型。

## 1. 四脚本调用契约（统一）

- exit 0：成功，stdout 为结果 JSON（`ensure_ascii=False, sort_keys=True, indent=2`）。
- exit 2：输入校验失败，stderr 逐行字段级错误（如 `$.policy.columns.amount.missing.strategy: 非法取值 'xxx'`）；模型按报错修复输入 JSON，**最多重试 2 次**。
- exit 1：运行错误，stderr 前缀「运行错误: 」（文件不可读/格式不支持/JSON 解析失败）；按 [鲁棒性场景处置表](robustness-cases.md) 处理，不重试。
- 重试仍失败或脚本不可用：进入降级模式（第 6 节），不得手工补算。

## 2. 四脚本 IO 摘要

### 2.1 profile_dataset.py（数据画像）

```
python scripts/profile_dataset.py <数据文件> [--sheet 名] [--max-rows N]
```

输出：`source / shape{rows,columns,truncated} / duplicate_rows / columns[]{name,type,confidence,missing_count,missing_rate,unique_count,examples,stats|date_range|top_values} / suspected_keys / suspected_time_columns / sensitive_columns / warnings`。0 数据行 → exit 2。

### 2.2 clean_dataset.py（清洗）

```
python scripts/clean_dataset.py <数据文件> --policy 策略.json --out 清洗后.csv --log 日志.json
```

策略 schema 与执行顺序（format→missing→outliers→dedup）见 [清洗策略](cleaning-policy.md)。stdout：`output / log / rows_before / rows_after / columns_added / cells_changed / rows_dropped / warnings`。日志 JSON：`changes[]{row,col,old,new,rule}`（≤1 万条，超限 truncated=true）+ `rows_dropped[]{row,reason}` + `counts` + `warnings`。`--out` 不得等于源文件/日志路径。

### 2.3 analyze_metrics.py（分析）

```
python scripts/analyze_metrics.py <清洗后文件> --spec 分析规格.json
```

规格白名单键：`time_column / time_grain(day|week|month) / metrics[]{column,agg,alias} / dimensions[] / baseline{type,constant} / anomaly{methods,iqr_k,mad_z,thresholds} / attribution{target_metric,dimension,top_n} / forecast{metric,method,window,horizon,alpha}`。输出：`series / comparisons / dimension_totals / anomalies / attribution / forecast / warnings`（口径见 [分析规则](anomaly-attribution-rubric.md)）。

### 2.4 render_report.py（报告）

```
python scripts/render_report.py --spec 报告规格.json --out 报告.html
```

规格白名单键：`title / sections[]`；章节 kind ∈ `profile_summary|quality_log|chart|anomaly_list|attribution_table|forecast_table|text|actions|disclaimer|privacy`；chart_type ∈ `line|bar|grouped_bar|pie|scatter|histogram`。图表/表格数据**只能经 source 引用脚本输出 JSON 或数据文件路径**；`--out` 必须为 .html 且不得与任何 source 相同。

## 3. FORBIDDEN 键三张表（模型输入 JSON 递归校验，命中即 exit 2）

| 脚本 | 禁止出现的键（小写精确匹配） |
|---|---|
| clean | rows_before, rows_after, cells_changed, affected, count, total, statistics |
| analyze | value, mean, delta, pct, yhat, contribution, share, lower, upper, std, p_value, z_score, statistic, total |
| render | value, yhat, mean, delta, pct, total, contribution, share, score |

各脚本同时执行白名单键校验：任何 schema 外的键一律 exit 2（防模型夹带）。

## 4. 报告模板（text/actions 章节撰写规范 + 两节原文）

建议章节顺序见 [可视化规范](visualization-guide.md) 第 4 节。模型负责撰写的部分：

- **text（结论）**：3~6 段。每段一个要点：整体走势（引用 series/comparisons 数值）→ 异常点（引用 anomalies：指标/周期/数值/方法/级别）→ 归因（引用 attribution，按 [分析规则](anomaly-attribution-rubric.md) 第 3 节标注「假设+证据强度」）→ 预测（引用 forecast.points 与 limitations 原文）→ 数据质量保留说明（缺失填充比例、截断、降级点）。
- **actions（行动建议）**：3~7 条。异常核查（指向具体周期与维度取值）→ 归因验证（需补充的业务信息/数据）→ 预测参考下的备货/预算提示 → 数据治理建议（缺失口径、重复导出、敏感列管理）。
- 所有数字逐字引用脚本输出 JSON，不得改写、四舍五入或重新计算。

**免责声明（脚本强制注入原文）**：
> 本报告由 AI 协同确定性脚本生成，全部统计数值均由脚本按固定算法计算，仅供参考，不构成任何经营、投资或决策承诺；分析结论依赖输入数据的完整性与真实性，预测结果存在不确定性，请结合业务实际审慎采信。

**数据隐私说明（脚本强制注入原文）**：
> 数据文件仅由用户显式提供并在本地处理：不联网、不上传、不存储；敏感列（手机号/证件号/邮箱/银行卡号）在画像与本报告中均已脱敏展示，原值仅保留于用户本地的清洗日志文件，未写入本报告。

## 5. 敏感信息处理

- 画像 examples/top_values 已脱敏；模型在对话中复述时保持脱敏形态，**不得复述敏感原值**。
- 敏感原值只存在于用户本地清洗日志的 old 字段；日志文件路径可在对话中告知，但内容不粘贴进对话。

## 6. 降级标注规范

发生以下任一情况，报告 text 章节必须单句声明：脚本 exit=2 重试 2 次仍失败（说明放弃哪一步）/ 脚本 exit=1（按处置表给出用户可操作指引）/ 行数截断 / 时间列部分行无法解析被剔除 / 预测或异常检测因数据不足被跳过 / 日期歧义采用默认口径。降级不阻断流程，但结论强度相应下调并在措辞中体现。
