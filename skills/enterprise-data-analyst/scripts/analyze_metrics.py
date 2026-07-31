"""analyze_metrics.py — 指标计算 / 异常检测 / 归因分析 / 轻量预测脚本。

用法：
    python analyze_metrics.py <数据文件> --spec 分析规格.json [--sheet 工作表名] [--max-rows N]

分析规格 JSON 骨架（白名单键；模型只填列名/枚举/整数参数，禁止任何结果字段）：
    {
      "time_column": "order_date", "time_grain": "month",
      "metrics": [{"column": "amount", "agg": "sum", "alias": "销售额"}],
      "dimensions": ["channel"],
      "baseline": {"type": "previous_period"},          // none|previous_period|same_period_last_year|fixed(需 constant)
      "anomaly": {"methods": ["iqr", "mad_z"], "iqr_k": 1.5, "mad_z": 3.5,
                  "thresholds": {"销售额": [0, 100000]}},
      "attribution": {"target_metric": "销售额", "dimension": "channel", "top_n": 5},
      "forecast": {"metric": "销售额", "method": "moving_average", "window": 3, "horizon": 3}
    }

输出（exit 0）：series / comparisons / dimension_totals / anomalies /
attribution / forecast / warnings。

退出契约：exit 0 成功；exit 2 规格校验失败（stderr 字段级报错，修复重试 ≤2 次）；
exit 1 运行错误。确定性：无随机数、无时间戳，同输入字节级一致。
"""

from __future__ import annotations

import argparse
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import datacommon as dc

# 模型输入 JSON 禁止携带的结果字段（统计值只能由脚本计算）
FORBIDDEN_ANALYSIS_KEYS = {
    "value", "mean", "delta", "pct", "yhat", "contribution", "share",
    "lower", "upper", "std", "p_value", "z_score", "statistic", "total",
}

AGG_FUNCS = {"sum", "mean", "count", "count_distinct"}
GRAINS = {"day", "week", "month"}
BASELINE_TYPES = {"none", "previous_period", "same_period_last_year", "fixed"}
ANOMALY_METHODS = {"iqr", "mad_z", "threshold"}
FORECAST_METHODS = {"moving_average", "linear", "exp_smoothing"}

SPEC_KEYS = {"time_column", "time_grain", "metrics", "dimensions",
             "baseline", "anomaly", "attribution", "forecast"}

# 预测方法局限性说明（脚本内置常量文案，报告须原样引用）
FORECAST_LIMITATIONS = {
    "moving_average": [
        "移动平均仅反映最近 window 期平均水平, 无法刻画趋势与季节性",
        "多期外推会把预测值回代入窗口, 误差逐期累积",
    ],
    "linear": [
        "最小二乘线性假设趋势恒定持续, 现实中趋势可能转折或饱和",
        "对异常点敏感, 序列剧烈波动时外推风险高",
    ],
    "exp_smoothing": [
        "简单指数平滑为水平外推(无趋势/季节项), 仅适合平稳序列",
        "alpha 固定, 无法自适应结构变化",
    ],
}
GENERIC_LIMITATIONS = [
    "预测区间为历史残差的经验估计(约80%水平), 覆盖率无严格统计保证",
    "轻量统计预测仅供参考, 不构成经营决策的唯一依据",
]


# ---------------------------------------------------------------------------
# 规格校验
# ---------------------------------------------------------------------------

def validate_spec(spec: object, header: list) -> list:
    errors = []
    errors.extend(dc.find_forbidden_keys(spec, FORBIDDEN_ANALYSIS_KEYS))
    if not isinstance(spec, dict):
        return errors + ["$: 分析规格必须是对象"]
    errors.extend(dc.check_whitelist(spec, SPEC_KEYS, "$"))

    metrics = spec.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        errors.append("$.metrics: 必须是非空数组")
        metrics = []
    aliases = []
    for i, m in enumerate(metrics):
        base = f"$.metrics[{i}]"
        if not isinstance(m, dict):
            errors.append(f"{base}: 必须是对象")
            continue
        errors.extend(dc.check_whitelist(m, {"column", "agg", "alias"}, base))
        if m.get("column") not in header:
            errors.append(f"{base}.column: 列 '{m.get('column')}' 在数据中不存在")
        if m.get("agg") not in AGG_FUNCS:
            errors.append(f"{base}.agg: 非法取值 '{m.get('agg')}' (允许: {sorted(AGG_FUNCS)})")
        alias = m.get("alias")
        if not alias or not str(alias).strip():
            errors.append(f"{base}.alias: 必须是非空字符串")
        elif alias in aliases:
            errors.append(f"{base}.alias: 别名 '{alias}' 重复")
        aliases.append(alias)

    time_col = spec.get("time_column")
    if time_col is not None and time_col not in header:
        errors.append(f"$.time_column: 列 '{time_col}' 在数据中不存在")
    grain = spec.get("time_grain", "month")
    if grain not in GRAINS:
        errors.append(f"$.time_grain: 非法取值 '{grain}' (允许: {sorted(GRAINS)})")

    dimensions = spec.get("dimensions", [])
    if not isinstance(dimensions, list):
        errors.append("$.dimensions: 必须是数组")
        dimensions = []
    for d in dimensions:
        if d not in header:
            errors.append(f"$.dimensions: 列 '{d}' 在数据中不存在")

    baseline = spec.get("baseline", {"type": "none"})
    if not isinstance(baseline, dict):
        errors.append("$.baseline: 必须是对象")
    else:
        errors.extend(dc.check_whitelist(baseline, {"type", "constant"}, "$.baseline"))
        btype = baseline.get("type", "none")
        if btype not in BASELINE_TYPES:
            errors.append(f"$.baseline.type: 非法取值 '{btype}' (允许: {sorted(BASELINE_TYPES)})")
        if btype == "fixed" and dc.parse_number(baseline.get("constant")) is None:
            errors.append("$.baseline.constant: fixed 基线必须提供数值 constant")

    anomaly = spec.get("anomaly", {})
    if anomaly:
        if not isinstance(anomaly, dict):
            errors.append("$.anomaly: 必须是对象")
        else:
            errors.extend(dc.check_whitelist(anomaly, {"methods", "iqr_k", "mad_z", "thresholds"}, "$.anomaly"))
            methods = anomaly.get("methods", ["iqr"])
            if not isinstance(methods, list) or not methods:
                errors.append("$.anomaly.methods: 必须是非空数组")
            else:
                for method in methods:
                    if method not in ANOMALY_METHODS:
                        errors.append(f"$.anomaly.methods: 非法取值 '{method}' (允许: {sorted(ANOMALY_METHODS)})")
            for key in ("iqr_k", "mad_z"):
                if key in anomaly and dc.parse_number(anomaly[key]) is None:
                    errors.append(f"$.anomaly.{key}: 必须是数值")
            thresholds = anomaly.get("thresholds", {})
            if not isinstance(thresholds, dict):
                errors.append("$.anomaly.thresholds: 必须是对象(别名 -> [下限, 上限])")
            else:
                for alias, pair in thresholds.items():
                    if alias not in aliases:
                        errors.append(f"$.anomaly.thresholds.{alias}: 不是已声明的指标别名")
                    if (not isinstance(pair, list) or len(pair) != 2
                            or dc.parse_number(pair[0]) is None or dc.parse_number(pair[1]) is None):
                        errors.append(f"$.anomaly.thresholds.{alias}: 必须是 [数值下限, 数值上限]")

    attribution = spec.get("attribution")
    if attribution is not None:
        if not isinstance(attribution, dict):
            errors.append("$.attribution: 必须是对象")
        else:
            errors.extend(dc.check_whitelist(attribution, {"target_metric", "dimension", "top_n"}, "$.attribution"))
            if attribution.get("target_metric") not in aliases:
                errors.append("$.attribution.target_metric: 必须是已声明的指标别名")
            if attribution.get("dimension") not in header:
                errors.append(f"$.attribution.dimension: 列 '{attribution.get('dimension')}' 在数据中不存在")
            top_n = attribution.get("top_n", 5)
            if not isinstance(top_n, int) or not (1 <= top_n <= 20):
                errors.append("$.attribution.top_n: 必须是 1..20 的整数")

    forecast = spec.get("forecast")
    if forecast is not None:
        if not isinstance(forecast, dict):
            errors.append("$.forecast: 必须是对象")
        else:
            errors.extend(dc.check_whitelist(forecast, {"metric", "method", "window", "horizon", "alpha"}, "$.forecast"))
            if forecast.get("metric") not in aliases:
                errors.append("$.forecast.metric: 必须是已声明的指标别名")
            if forecast.get("method") not in FORECAST_METHODS:
                errors.append(f"$.forecast.method: 非法取值 '{forecast.get('method')}' (允许: {sorted(FORECAST_METHODS)})")
            window = forecast.get("window", 3)
            if not isinstance(window, int) or not (2 <= window <= 24):
                errors.append("$.forecast.window: 必须是 2..24 的整数")
            horizon = forecast.get("horizon", 3)
            if not isinstance(horizon, int) or not (1 <= horizon <= 24):
                errors.append("$.forecast.horizon: 必须是 1..24 的整数")
            alpha = forecast.get("alpha", 0.5)
            if dc.parse_number(alpha) is None or not (0 < float(dc.parse_number(alpha)) < 1):
                errors.append("$.forecast.alpha: 必须是 (0,1) 区间数值")
    return errors


# ---------------------------------------------------------------------------
# 时间分桶
# ---------------------------------------------------------------------------

def bucket_label(d: date, grain: str) -> str:
    if grain == "day":
        return d.isoformat()
    if grain == "week":
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    return f"{d.year:04d}-{d.month:02d}"


def bucket_start(label: str, grain: str) -> date:
    if grain == "day":
        return date.fromisoformat(label)
    if grain == "week":
        year, week = label.split("-W")
        return date.fromisocalendar(int(year), int(week), 1)
    year, month = label.split("-")
    return date(int(year), int(month), 1)


def next_bucket(label: str, grain: str) -> str:
    start = bucket_start(label, grain)
    if grain == "day":
        return (start + timedelta(days=1)).isoformat()
    if grain == "week":
        nxt = start + timedelta(days=7)
        iso = nxt.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    year, month = start.year, start.month + 1
    if month > 12:
        year, month = year + 1, 1
    return f"{year:04d}-{month:02d}"


def bucket_range(min_label: str, max_label: str, grain: str) -> list:
    labels = [min_label]
    while labels[-1] != max_label and len(labels) < 4000:
        labels.append(next_bucket(labels[-1], grain))
    return labels


# ---------------------------------------------------------------------------
# 聚合与对比
# ---------------------------------------------------------------------------

def aggregate(rows: list, column: str, agg: str) -> float | None:
    """对一组行按聚合方式计算指标值。无可解析数据时 sum/mean 返回 None。"""
    if agg == "count":
        n = sum(1 for r in rows if not dc.is_missing(r.get(column, "")))
        return float(n)
    if agg == "count_distinct":
        return float(len({r.get(column, "") for r in rows if not dc.is_missing(r.get(column, ""))}))
    nums = [dc.parse_number(r.get(column, "")) for r in rows]
    nums = [v for v in nums if v is not None]
    if not nums:
        return None
    if agg == "sum":
        return dc.round6(sum(nums))
    return dc.round6(sum(nums) / len(nums))


def build_comparisons(series: list, baseline: dict, grain: str) -> list:
    """同环比计算。除零/缺基线 -> pct=null + note，不崩溃。"""
    btype = baseline.get("type", "none")
    if btype == "none":
        return []
    value_map = {p["bucket"]: p["value"] for p in series}
    result = []
    for i, point in enumerate(series):
        bucket, value = point["bucket"], point["value"]
        base_value = None
        if btype == "previous_period" and i > 0:
            base_value = series[i - 1]["value"]
        elif btype == "same_period_last_year":
            start = bucket_start(bucket, grain)
            if grain == "month":
                prev = f"{start.year - 1:04d}-{start.month:02d}"
            elif grain == "week":
                prev_start = date.fromisocalendar(start.isocalendar()[0] - 1, start.isocalendar()[1], 1)
                iso = prev_start.isocalendar()
                prev = f"{iso[0]}-W{iso[1]:02d}"
            else:
                try:
                    prev = start.replace(year=start.year - 1).isoformat()
                except ValueError:  # 2月29日
                    prev = (start - timedelta(days=365)).isoformat()
            base_value = value_map.get(prev)
        elif btype == "fixed":
            base_value = float(dc.parse_number(baseline.get("constant")))
        entry = {"bucket": bucket, "value": value, "baseline": base_value,
                 "delta": None, "pct": None}
        if value is not None and base_value is not None:
            entry["delta"] = dc.round6(value - base_value)
            if base_value != 0:
                entry["pct"] = dc.round6((value - base_value) / base_value)
            else:
                entry["note"] = "基线为 0, 百分比不可计算"
        elif i > 0 or btype != "previous_period":
            entry["note"] = "基线期无数据, 对比不可计算"
        result.append(entry)
    return result


# ---------------------------------------------------------------------------
# 异常检测
# ---------------------------------------------------------------------------

def detect_anomalies(series: list, alias: str, anomaly_cfg: dict, warnings: list) -> list:
    methods = anomaly_cfg.get("methods", ["iqr"])
    thresholds = anomaly_cfg.get("thresholds", {})
    points = [(p["bucket"], p["value"]) for p in series if p["value"] is not None]
    values = [v for _, v in points]
    findings = []
    if len(values) < 4:
        if methods:
            warnings.append(f"指标 '{alias}' 有效数据点少于 4 个, 异常检测跳过")
        return findings

    if "iqr" in methods:
        k = float(dc.parse_number(anomaly_cfg.get("iqr_k", 1.5)))
        sv = sorted(values)
        q1, q3 = dc.quantile(sv, 0.25), dc.quantile(sv, 0.75)
        iqr = q3 - q1
        if iqr == 0:
            warnings.append(f"指标 '{alias}' IQR 为 0(近常量序列), IQR 法不报警")
        else:
            lower, upper = q1 - k * iqr, q3 + k * iqr
            for bucket, v in points:
                if v < lower or v > upper:
                    overshoot = (lower - v) if v < lower else (v - upper)
                    rel = overshoot / iqr
                    severity = "high" if rel >= 1 else ("medium" if rel >= 0.5 else "low")
                    findings.append({"metric": alias, "bucket": bucket, "value": v,
                                     "method": "iqr", "lower": dc.round6(lower),
                                     "upper": dc.round6(upper), "severity": severity})

    if "mad_z" in methods:
        z_limit = float(dc.parse_number(anomaly_cfg.get("mad_z", 3.5)))
        med = statistics.median(values)
        mad = statistics.median([abs(v - med) for v in values])
        if mad == 0:
            warnings.append(f"指标 '{alias}' MAD 为 0(近常量序列), MAD-z 法不报警")
        else:
            for bucket, v in points:
                z = 0.6745 * (v - med) / mad
                if abs(z) > z_limit:
                    az = abs(z)
                    severity = "high" if az >= 2 * z_limit else ("medium" if az >= 1.5 * z_limit else "low")
                    findings.append({"metric": alias, "bucket": bucket, "value": v,
                                     "method": "mad_z",
                                     "lower": dc.round6(med - z_limit * mad / 0.6745),
                                     "upper": dc.round6(med + z_limit * mad / 0.6745),
                                     "severity": severity})

    if "threshold" in methods and alias in thresholds:
        lo = float(dc.parse_number(thresholds[alias][0]))
        hi = float(dc.parse_number(thresholds[alias][1]))
        for bucket, v in points:
            if v < lo or v > hi:
                findings.append({"metric": alias, "bucket": bucket, "value": v,
                                 "method": "threshold", "lower": dc.round6(lo),
                                 "upper": dc.round6(hi), "severity": "medium"})

    findings.sort(key=lambda f: (f["metric"], f["bucket"], f["method"]))
    return findings


# ---------------------------------------------------------------------------
# 归因分析（差额分解：Σ 维度贡献 = 总差额）
# ---------------------------------------------------------------------------

def build_attribution(rows: list, spec: dict, series: list, metric_def: dict,
                      grain: str, warnings: list) -> dict | None:
    attr = spec.get("attribution")
    if not attr:
        return None
    target = attr["target_metric"]
    dimension = attr["dimension"]
    top_n = attr.get("top_n", 5)
    non_null = [p for p in series if p["value"] is not None]
    if len(non_null) < 2:
        warnings.append(f"指标 '{target}' 有效周期少于 2 个, 归因分析跳过")
        return None
    cur_bucket = non_null[-1]["bucket"]
    base_bucket = non_null[-2]["bucket"]
    column = metric_def[target]["column"]
    cur_rows = [r for r in rows if r.get("__bucket__") == cur_bucket]
    base_rows = [r for r in rows if r.get("__bucket__") == base_bucket]

    def per_dimension(group_rows):
        totals = {}
        for r in group_rows:
            key = str(r.get(dimension, "")).strip() or "(空)"
            v = dc.parse_number(r.get(column, ""))
            if v is not None:
                totals[key] = totals.get(key, 0.0) + v
        return totals

    cur_map = per_dimension(cur_rows)
    base_map = per_dimension(base_rows)
    all_keys = sorted(set(cur_map) | set(base_map))
    contributors = []
    delta_total = 0.0
    for key in all_keys:
        cur = cur_map.get(key, 0.0)
        base = base_map.get(key, 0.0)
        contribution = cur - base
        delta_total += contribution
        contributors.append({"value": key, "current": dc.round6(cur),
                             "baseline": dc.round6(base),
                             "contribution": dc.round6(contribution)})
    contributors.sort(key=lambda c: (-abs(c["contribution"]), c["value"]))
    top = contributors[:top_n]
    rest = contributors[top_n:]
    others_contribution = sum(c["contribution"] for c in rest)

    def share(x):
        if delta_total == 0:
            return None
        return dc.round6(x / delta_total)

    for c in top:
        c["share"] = share(c["contribution"])
    result = {
        "metric": target,
        "dimension": dimension,
        "current_bucket": cur_bucket,
        "baseline_bucket": base_bucket,
        "delta_total": dc.round6(delta_total),
        "contributors": top,
        "others": {"contribution": dc.round6(others_contribution),
                   "share": share(others_contribution),
                   "merged_count": len(rest)},
        "method_note": "差额分解法(按求和口径): Σ 各维度贡献 = 总差额",
    }
    if delta_total == 0:
        result["note"] = "总差额为 0, 贡献占比不可计算"
    return result


# ---------------------------------------------------------------------------
# 轻量预测
# ---------------------------------------------------------------------------

def build_forecast(series: list, spec: dict, grain: str, warnings: list) -> dict | None:
    fc = spec.get("forecast")
    if not fc:
        return None
    method = fc["method"]
    window = fc.get("window", 3)
    horizon = fc.get("horizon", 3)
    alpha = float(dc.parse_number(fc.get("alpha", 0.5)))
    points = [(p["bucket"], p["value"]) for p in series if p["value"] is not None]
    values = [v for _, v in points]
    min_needed = {"moving_average": window, "linear": 3, "exp_smoothing": 2}[method]
    limitations = FORECAST_LIMITATIONS[method] + GENERIC_LIMITATIONS
    result = {"metric": fc["metric"], "method": method,
              "params": {"window": window, "horizon": horizon,
                         **({"alpha": alpha} if method == "exp_smoothing" else {})},
              "points": [], "limitations": limitations}
    if len(values) < min_needed:
        result["note"] = f"有效数据点 {len(values)} 个, 少于方法要求的最少 {min_needed} 个, 预测降级为不输出"
        warnings.append(f"指标 '{fc['metric']}': {result['note']}")
        return result

    history = list(values)
    residuals = []
    if method == "moving_average":
        for t in range(window, len(history)):
            residuals.append(history[t] - sum(history[t - window:t]) / window)
    elif method == "linear":
        n = len(history)
        sx = n * (n - 1) / 2
        sxx = (n - 1) * n * (2 * n - 1) / 6
        sy = sum(history)
        sxy = sum(i * v for i, v in enumerate(history))
        denom = n * sxx - sx * sx
        slope = (n * sxy - sx * sy) / denom if denom else 0.0
        intercept = (sy - slope * sx) / n
        residuals = [v - (intercept + slope * i) for i, v in enumerate(history)]
    else:  # exp_smoothing
        level = history[0]
        for t in range(1, len(history)):
            residuals.append(history[t] - level)
            level = alpha * history[t] + (1 - alpha) * level

    std = statistics.stdev(residuals) if len(residuals) >= 2 else 0.0
    margin = 1.28 * std

    future_values = []
    work = list(history)
    if method == "moving_average":
        for _ in range(horizon):
            yhat = sum(work[-window:]) / window
            future_values.append(yhat)
            work.append(yhat)
    elif method == "linear":
        n = len(history)
        for h in range(horizon):
            future_values.append(intercept + slope * (n + h))
    else:
        for _ in range(horizon):
            future_values.append(level)

    last_bucket = points[-1][0]
    bucket = last_bucket
    for yhat in future_values:
        bucket = next_bucket(bucket, grain)
        result["points"].append({"bucket": bucket, "yhat": dc.round6(yhat),
                                 "lo": dc.round6(yhat - margin),
                                 "hi": dc.round6(yhat + margin)})
    return result


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run_analysis(path_str: str, spec: dict, sheet: str = None,
                 max_rows: int = dc.MAX_ROWS) -> dict:
    header, rows, meta = dc.read_dataset(path_str, sheet=sheet, max_rows=max_rows)
    if not rows:
        dc.fail_validation(["$.file: 数据行为 0, 无法分析"])
    errors = validate_spec(spec, header)
    if errors:
        dc.fail_validation(errors)

    warnings = list(meta.get("warnings", []))
    time_col = spec.get("time_column")
    grain = spec.get("time_grain", "month")
    metrics = spec["metrics"]
    metric_def = {m["alias"]: m for m in metrics}

    # 时间分桶：无法解析的时间行剔除并计数警告
    unparsed_time = 0
    if time_col:
        prefer, note = dc.detect_date_prefer([r.get(time_col, "") for r in rows])
        if "无法多数决" not in note:
            warnings.append(f"时间列 '{time_col}': {note}")
        for r in rows:
            parsed = dc.parse_date(r.get(time_col, ""), prefer=prefer)
            if parsed is None:
                if not dc.is_missing(r.get(time_col, "")):
                    unparsed_time += 1
                r["__bucket__"] = None
            else:
                r["__bucket__"] = bucket_label(date.fromisoformat(parsed), grain)
        if unparsed_time:
            warnings.append(f"时间列 '{time_col}' 有 {unparsed_time} 行无法解析, 已从时序分析中剔除")
    else:
        warnings.append("未提供时间列: 全量聚合为单周期, 对比/异常/预测不适用")
        for r in rows:
            r["__bucket__"] = "all"

    # 序列：全范围分桶，缺口 bucket value=None
    valid_buckets = [r["__bucket__"] for r in rows if r["__bucket__"]]
    if not valid_buckets:
        dc.fail_validation([f"$.time_column: 时间列 '{time_col}' 无可解析值, 无法构建时间序列"])
    labels = bucket_range(min(valid_buckets), max(valid_buckets), grain) if time_col else ["all"]
    if time_col:
        gap = len(labels) - len(set(valid_buckets))
        if gap > 0:
            warnings.append(f"时间序列存在 {gap} 个缺口周期(无数据), 已留空并在图中断开")
    rows_by_bucket = {}
    for r in rows:
        if r["__bucket__"]:
            rows_by_bucket.setdefault(r["__bucket__"], []).append(r)

    series = {}
    comparisons = {}
    for m in metrics:
        alias = m["alias"]
        series[alias] = [
            {"bucket": label,
             "value": aggregate(rows_by_bucket.get(label, []), m["column"], m["agg"])}
            for label in labels
        ]
        comparisons[alias] = build_comparisons(series[alias], spec.get("baseline", {"type": "none"}), grain)

    # 维度汇总（供图表与维度分析；高基数 top-49 + 其他）
    dimension_totals = {}
    for dim in spec.get("dimensions", []):
        for m in metrics:
            totals = {}
            for r in rows:
                key = str(r.get(dim, "")).strip() or "(空)"
                v = dc.parse_number(r.get(m["column"], ""))
                if v is not None:
                    totals[key] = totals.get(key, 0.0) + v
            items = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
            if len(items) > 50:
                head = items[:49]
                others = sum(v for _, v in items[49:])
                items = head + [("其他", others)]
                warnings.append(f"维度 '{dim}' 基数超过 50, 已合并为 top-49 + 其他")
            dimension_totals[f"{dim}@{m['alias']}"] = [
                {"value": k, "total": dc.round6(v)} for k, v in items
            ]

    anomalies = []
    anomaly_cfg = spec.get("anomaly", {})
    if anomaly_cfg and time_col:
        for m in metrics:
            anomalies.extend(detect_anomalies(series[m["alias"]], m["alias"], anomaly_cfg, warnings))
    elif anomaly_cfg and not time_col:
        warnings.append("无时间列, 异常检测不适用, 已跳过")

    attribution = build_attribution(rows, spec, series[spec["attribution"]["target_metric"]],
                                    metric_def, grain, warnings) if spec.get("attribution") and time_col else None
    if spec.get("attribution") and not time_col:
        warnings.append("无时间列, 归因分析不适用, 已跳过")

    forecast = None
    if spec.get("forecast") and time_col:
        forecast = build_forecast(series[spec["forecast"]["metric"]], spec, grain, warnings)
    elif spec.get("forecast") and not time_col:
        warnings.append("无时间列, 预测不适用, 已跳过")

    for r in rows:
        r.pop("__bucket__", None)

    return {
        "series": series,
        "comparisons": comparisons,
        "dimension_totals": dimension_totals,
        "anomalies": anomalies,
        "attribution": attribution,
        "forecast": forecast,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="企业指标分析(聚合/异常/归因/预测)")
    parser.add_argument("file", help="数据文件路径 (csv/tsv/json/jsonl/xlsx)")
    parser.add_argument("--spec", required=True, help="分析规格 JSON 路径")
    parser.add_argument("--sheet", default=None, help="xlsx 工作表名(默认首个)")
    parser.add_argument("--max-rows", type=int, default=dc.MAX_ROWS, help="读取行数上限")
    args = parser.parse_args()
    dc.setup_stdio()
    spec = dc.load_json_file(args.spec, role="分析规格")
    dc.emit_json(run_analysis(args.file, spec, sheet=args.sheet, max_rows=args.max_rows))


if __name__ == "__main__":
    main()
