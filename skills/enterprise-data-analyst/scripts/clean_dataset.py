"""clean_dataset.py — 数据清洗与预处理脚本（缺失值填充/异常值处理/格式标准化）。

用法：
    python clean_dataset.py <数据文件> --policy 策略.json --out 清洗后.csv --log 日志.json
        [--sheet 工作表名] [--max-rows N]

策略 JSON 骨架（白名单键，其余键一律 exit 2）：
    {
      "policy": {
        "dedup": true,
        "columns": {
          "amount": {
            "format":   {"type": "number"},                       // none|trim_ws|number|date_iso|enum_map
            "missing":  {"strategy": "fill_median"},              // keep|drop_rows|fill_mean|fill_median|fill_mode|fill_forward|fill_constant
            "outliers": {"strategy": "clip_iqr", "iqr_k": 1.5}    // keep|clip_iqr|clip_zscore|flag_only
          },
          "order_date": {"format": {"type": "date_iso", "prefer": "DMY"}},
          "status":     {"format": {"type": "enum_map", "mapping": {"已完成": "done"}}}
        }
      }
    }

执行顺序固定：format -> missing -> outliers -> dedup。
不丢失关键信息：逐格变更日志（行号/列/原值/新值/规则）+ 删除行记录 + 前后行数对照，
日志超 1 万条截断并置 truncated=true。源文件只读，绝不覆写。

退出契约：exit 0 成功；exit 2 策略校验失败（stderr 字段级报错，修复后重试）；exit 1 运行错误。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import datacommon as dc

# 模型输入 JSON 禁止携带的结果字段（统计值只能由脚本计算）
FORBIDDEN_CLEAN_KEYS = {
    "rows_before", "rows_after", "cells_changed", "affected",
    "count", "total", "statistics",
}

MISSING_STRATEGIES = {"keep", "drop_rows", "fill_mean", "fill_median",
                      "fill_mode", "fill_forward", "fill_constant"}
OUTLIER_STRATEGIES = {"keep", "clip_iqr", "clip_zscore", "flag_only"}
FORMAT_TYPES = {"none", "trim_ws", "number", "date_iso", "enum_map"}


def validate_policy(policy: object, header: list, rows: list) -> list:
    """策略 JSON 校验。返回字段级错误清单（空列表 = 通过）。"""
    errors = []
    errors.extend(dc.find_forbidden_keys(policy, FORBIDDEN_CLEAN_KEYS))
    if not isinstance(policy, dict):
        return errors + ["$.policy: 必须是对象"]
    errors.extend(dc.check_whitelist(policy, {"columns", "dedup"}, "$.policy"))
    dedup = policy.get("dedup", False)
    if not isinstance(dedup, bool):
        errors.append("$.policy.dedup: 必须是布尔值")
    columns = policy.get("columns", {})
    if not isinstance(columns, dict):
        return errors + ["$.policy.columns: 必须是对象(列名 -> 规则)"]
    for col, rule in columns.items():
        base = f"$.policy.columns.{col}"
        if col not in header:
            errors.append(f"{base}: 列 '{col}' 在数据中不存在")
            continue
        if not isinstance(rule, dict):
            errors.append(f"{base}: 必须是对象")
            continue
        errors.extend(dc.check_whitelist(rule, {"format", "missing", "outliers"}, base))
        col_values = [r.get(col, "") for r in rows]
        ctype, _ = dc.infer_column_type(col_values)
        numeric_col = ctype in ("integer", "float")

        fmt = rule.get("format")
        if fmt is not None:
            if not isinstance(fmt, dict):
                errors.append(f"{base}.format: 必须是对象")
            else:
                errors.extend(dc.check_whitelist(fmt, {"type", "mapping", "prefer"}, f"{base}.format"))
                ftype = fmt.get("type")
                if ftype not in FORMAT_TYPES:
                    errors.append(f"{base}.format.type: 非法取值 '{ftype}' (允许: {sorted(FORMAT_TYPES)})")
                if ftype == "enum_map" and not isinstance(fmt.get("mapping"), dict):
                    errors.append(f"{base}.format.mapping: enum_map 必须提供 mapping 对象")
                if ftype == "number" and not numeric_col and ctype != "date":
                    # 文本列强制数值化大概率是策略错误，阻断并提示
                    errors.append(f"{base}.format.type: 列 '{col}' 推断类型为 {ctype}, 不适用 number 标准化")
                prefer = fmt.get("prefer")
                if prefer is not None and str(prefer).upper() not in ("MDY", "DMY"):
                    errors.append(f"{base}.format.prefer: 非法取值 '{prefer}' (允许: MDY/DMY)")

        mis = rule.get("missing")
        if mis is not None:
            if not isinstance(mis, dict):
                errors.append(f"{base}.missing: 必须是对象")
            else:
                errors.extend(dc.check_whitelist(mis, {"strategy", "constant"}, f"{base}.missing"))
                strat = mis.get("strategy")
                if strat not in MISSING_STRATEGIES:
                    errors.append(f"{base}.missing.strategy: 非法取值 '{strat}' (允许: {sorted(MISSING_STRATEGIES)})")
                if strat == "fill_constant" and "constant" not in mis:
                    errors.append(f"{base}.missing.constant: fill_constant 必须提供 constant")
                if strat in ("fill_mean", "fill_median") and not numeric_col:
                    errors.append(f"{base}.missing.strategy: 列 '{col}' 推断类型为 {ctype}, 不适用 {strat}")

        out = rule.get("outliers")
        if out is not None:
            if not isinstance(out, dict):
                errors.append(f"{base}.outliers: 必须是对象")
            else:
                errors.extend(dc.check_whitelist(out, {"strategy", "iqr_k", "z"}, f"{base}.outliers"))
                strat = out.get("strategy")
                if strat not in OUTLIER_STRATEGIES:
                    errors.append(f"{base}.outliers.strategy: 非法取值 '{strat}' (允许: {sorted(OUTLIER_STRATEGIES)})")
                if strat in ("clip_iqr", "clip_zscore", "flag_only") and not numeric_col:
                    errors.append(f"{base}.outliers.strategy: 列 '{col}' 推断类型为 {ctype}, 不适用异常值处理")
                for key in ("iqr_k", "z"):
                    if key in out and dc.parse_number(out[key]) is None:
                        errors.append(f"{base}.outliers.{key}: 必须是数值")
    return errors


class ChangeLog:
    """逐格变更日志。超 MAX_CHANGE_LOG 截断并显式标记，不静默丢失。"""

    def __init__(self) -> None:
        self.changes = []
        self.rows_dropped = []
        self.warnings = []
        self.truncated = False
        self.total_changes = 0

    def record(self, row_no: int, col: str, old, new, rule: str) -> None:
        self.total_changes += 1
        if len(self.changes) < dc.MAX_CHANGE_LOG:
            self.changes.append({"row": row_no, "col": col,
                                 "old": old, "new": new, "rule": rule})
        else:
            self.truncated = True

    def drop(self, row_no: int, reason: str) -> None:
        if len(self.rows_dropped) < dc.MAX_CHANGE_LOG:
            self.rows_dropped.append({"row": row_no, "reason": reason})
        else:
            self.truncated = True


def _numeric_values(rows: list, col: str) -> list:
    """收集某列当前可解析的数值（用于统计边界）。"""
    values = []
    for _, row in rows:
        v = dc.parse_number(row.get(col, ""))
        if v is not None:
            values.append(v)
    return values


def apply_clean(header: list, rows_in: list, policy: dict, log: ChangeLog) -> tuple:
    """按策略执行清洗。rows_in 为 [(原始行号, row_dict)]；返回 (header, rows, columns_added)。"""
    rows = [(i, dict(r)) for i, r in rows_in]
    columns = policy.get("columns", {})
    columns_added = []

    # ---- 第 1 步：format 格式标准化 ----
    for col, rule in columns.items():
        fmt = rule.get("format") or {}
        ftype = fmt.get("type", "none")
        if ftype == "none":
            continue
        prefer = str(fmt.get("prefer", "MDY")).upper()
        mapping = fmt.get("mapping") or {}
        for row_no, row in rows:
            old = row.get(col, "")
            if ftype == "trim_ws":
                new = str(old).strip()
                if new != old:
                    row[col] = new
                    log.record(row_no, col, old, new, "format.trim_ws")
            elif ftype == "number":
                if dc.is_missing(old):
                    continue
                v = dc.parse_number(old)
                if v is None:
                    log.warnings.append(f"第 {row_no} 行列 '{col}' 值 '{old}' 无法解析为数值, 保持原值")
                    continue
                new = dc.fmt_number(v)
                if new != str(old):
                    row[col] = new
                    log.record(row_no, col, old, new, "format.number")
            elif ftype == "date_iso":
                if dc.is_missing(old):
                    continue
                iso = dc.parse_date(old, prefer=prefer)
                if iso is None:
                    log.warnings.append(f"第 {row_no} 行列 '{col}' 值 '{old}' 无法解析为日期, 保持原值")
                    continue
                if iso != str(old):
                    row[col] = iso
                    log.record(row_no, col, old, iso, "format.date_iso")
            elif ftype == "enum_map":
                key = str(old)
                if key in mapping:
                    new = str(mapping[key])
                    row[col] = new
                    log.record(row_no, col, old, new, "format.enum_map")

    # ---- 第 2 步：missing 缺失值处理 ----
    for col, rule in columns.items():
        mis = rule.get("missing") or {}
        strat = mis.get("strategy", "keep")
        if strat == "keep":
            continue
        if strat == "drop_rows":
            kept = []
            for row_no, row in rows:
                if dc.is_missing(row.get(col, "")):
                    log.drop(row_no, f"missing:{col}")
                else:
                    kept.append((row_no, row))
            rows = kept
            continue
        fill_value = None
        if strat in ("fill_mean", "fill_median"):
            values = sorted(_numeric_values(rows, col))
            if not values:
                log.warnings.append(f"列 '{col}' 无可解析数值, {strat} 跳过")
                continue
            if strat == "fill_mean":
                fill_value = dc.fmt_number(sum(values) / len(values))
            else:
                fill_value = dc.fmt_number(dc.quantile(values, 0.5))
        elif strat == "fill_mode":
            counts = {}
            for _, row in rows:
                v = row.get(col, "")
                if not dc.is_missing(v):
                    counts[v] = counts.get(v, 0) + 1
            if not counts:
                log.warnings.append(f"列 '{col}' 全部为空, fill_mode 跳过")
                continue
            fill_value = max(counts, key=lambda k: counts[k])
        elif strat == "fill_constant":
            fill_value = str(mis.get("constant"))
        if strat == "fill_forward":
            last = None
            for row_no, row in rows:
                v = row.get(col, "")
                if dc.is_missing(v):
                    if last is not None:
                        row[col] = last
                        log.record(row_no, col, "", last, "missing.fill_forward")
                else:
                    last = v
        else:
            for row_no, row in rows:
                if dc.is_missing(row.get(col, "")):
                    row[col] = fill_value
                    log.record(row_no, col, "", fill_value, f"missing.{strat}")

    # ---- 第 3 步：outliers 异常值处理 ----
    for col, rule in columns.items():
        out = rule.get("outliers") or {}
        strat = out.get("strategy", "keep")
        if strat == "keep":
            continue
        values = sorted(_numeric_values(rows, col))
        if len(values) < 4:
            log.warnings.append(f"列 '{col}' 可解析数值少于 4 个, 异常值处理跳过")
            continue
        if strat in ("clip_iqr", "flag_only"):
            k = float(dc.parse_number(out.get("iqr_k", 1.5)))
            q1 = dc.quantile(values, 0.25)
            q3 = dc.quantile(values, 0.75)
            iqr = q3 - q1
            lower, upper = q1 - k * iqr, q3 + k * iqr
        else:  # clip_zscore
            z = float(dc.parse_number(out.get("z", 3.5)))
            mean = sum(values) / len(values)
            var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
            std = var ** 0.5
            if std == 0:
                log.warnings.append(f"列 '{col}' 标准差为 0(常量列), 不判定异常值")
                continue
            lower, upper = mean - z * std, mean + z * std
        if strat in ("clip_iqr", "flag_only") and (q3 - q1) == 0:
            log.warnings.append(f"列 '{col}' IQR 为 0(近常量列), 不判定异常值")
            continue
        if strat == "flag_only":
            flag_col = f"__flag_{col}"
            if flag_col not in columns_added:
                columns_added.append(flag_col)
            flagged = 0
            for row_no, row in rows:
                v = dc.parse_number(row.get(col, ""))
                flag = ""
                if v is not None:
                    if v > upper:
                        flag = "outlier_high"
                    elif v < lower:
                        flag = "outlier_low"
                if flag:
                    flagged += 1
                row[flag_col] = flag
            log.warnings.append(f"列 '{col}' flag_only: 标记 {flagged} 个异常值于新列 '{flag_col}', 原值未改动")
        else:
            for row_no, row in rows:
                old = row.get(col, "")
                v = dc.parse_number(old)
                if v is None:
                    continue
                if v > upper:
                    new = dc.fmt_number(upper)
                    row[col] = new
                    log.record(row_no, col, old, new,
                               f"outliers.{strat}(upper={dc.fmt_number(upper)})")
                elif v < lower:
                    new = dc.fmt_number(lower)
                    row[col] = new
                    log.record(row_no, col, old, new,
                               f"outliers.{strat}(lower={dc.fmt_number(lower)})")

    # ---- 第 4 步：dedup 完全重复行去重 ----
    if policy.get("dedup", False):
        all_cols = header + columns_added
        seen = set()
        kept = []
        for row_no, row in rows:
            key = tuple(row.get(c, "") for c in all_cols)
            if key in seen:
                log.drop(row_no, "duplicate")
            else:
                seen.add(key)
                kept.append((row_no, row))
        rows = kept

    return header, rows, columns_added


def write_csv(path: Path, header: list, rows: list, columns_added: list) -> None:
    """写出清洗后 CSV：utf-8-sig + 公式注入防护。"""
    all_cols = header + columns_added
    try:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(all_cols)
            for _, row in rows:
                writer.writerow([dc.csv_safe_cell(str(row.get(c, ""))) for c in all_cols])
    except OSError as exc:
        dc.fail_runtime(f"无法写出 CSV: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="企业数据清洗（缺失/异常/标准化）")
    parser.add_argument("file", help="数据文件路径 (csv/tsv/json/jsonl/xlsx)")
    parser.add_argument("--policy", required=True, help="清洗策略 JSON 路径")
    parser.add_argument("--out", required=True, help="清洗后 CSV 输出路径")
    parser.add_argument("--log", required=True, help="清洗日志 JSON 输出路径")
    parser.add_argument("--sheet", default=None, help="xlsx 工作表名(默认首个)")
    parser.add_argument("--max-rows", type=int, default=dc.MAX_ROWS, help="读取行数上限")
    args = parser.parse_args()
    dc.setup_stdio()

    # 输出路径不得覆写源文件或互相覆盖
    src = Path(args.file).resolve()
    out = Path(args.out).resolve()
    log_path = Path(args.log).resolve()
    path_errors = []
    if out == src:
        path_errors.append("$.--out: 输出路径不得与源文件相同(源文件只读保护)")
    if log_path == src:
        path_errors.append("$.--log: 日志路径不得与源文件相同")
    if out == log_path:
        path_errors.append("$.--log: 日志路径不得与 --out 相同")
    if path_errors:
        dc.fail_validation(path_errors)

    header, raw_rows, meta = dc.read_dataset(args.file, sheet=args.sheet, max_rows=args.max_rows)
    if not raw_rows:
        dc.fail_validation(["$.file: 数据行为 0, 无法清洗"])
    policy_obj = dc.load_json_file(args.policy, role="清洗策略")
    if not isinstance(policy_obj, dict) or "policy" not in policy_obj:
        dc.fail_validation(["$.policy: 策略 JSON 顶层必须包含 'policy' 对象"])
    rows_in = list(enumerate(raw_rows, start=1))
    errors = validate_policy(policy_obj["policy"], header, raw_rows)
    if errors:
        dc.fail_validation(errors)

    log = ChangeLog()
    log.warnings.extend(meta.get("warnings", []))
    header, rows, columns_added = apply_clean(header, rows_in, policy_obj["policy"], log)
    write_csv(out, header, rows, columns_added)

    log_doc = {
        "source": str(args.file),
        "output": str(args.out),
        "rows_before": len(raw_rows),
        "rows_after": len(rows),
        "changes": log.changes,
        "rows_dropped": log.rows_dropped,
        "columns_added": columns_added,
        "counts": {
            "cells_changed": log.total_changes,
            "rows_dropped": len(log.rows_dropped),
        },
        "truncated": log.truncated,
        "warnings": log.warnings,
    }
    try:
        log_path.write_text(json.dumps(log_doc, ensure_ascii=False, sort_keys=True, indent=2),
                            encoding="utf-8")
    except OSError as exc:
        dc.fail_runtime(f"无法写出清洗日志: {exc}")

    dc.emit_json({
        "output": str(args.out),
        "log": str(args.log),
        "rows_before": len(raw_rows),
        "rows_after": len(rows),
        "columns_added": columns_added,
        "cells_changed": log.total_changes,
        "rows_dropped": len(log.rows_dropped),
        "warnings": log.warnings,
    })


if __name__ == "__main__":
    main()
