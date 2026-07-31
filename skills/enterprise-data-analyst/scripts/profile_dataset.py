"""profile_dataset.py — 数据画像脚本（全流程第 1 步：数据获取与理解）。

用法：
    python profile_dataset.py <数据文件> [--sheet 工作表名] [--max-rows N]

输出（exit 0, stdout JSON）：
    source / shape / duplicate_rows / columns[] / suspected_keys /
    suspected_time_columns / sensitive_columns / warnings

退出契约：
    exit 0 成功；exit 2 输入校验失败（0 数据行等）；exit 1 运行错误。
    本脚本无模型输入 JSON，无需 FORBIDDEN 键校验。

确定性：同一输入多次运行 stdout 字节级一致。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import datacommon as dc

TOP_VALUES_LIMIT = 5   # top_values 最多保留的取值个数
EXAMPLES_LIMIT = 3     # 每列示例值个数（敏感列脱敏）


def build_profile(path_str: str, sheet: str = None, max_rows: int = dc.MAX_ROWS) -> dict:
    """读取数据集并生成画像。0 数据行 -> exit 2。"""
    header, rows, meta = dc.read_dataset(path_str, sheet=sheet, max_rows=max_rows)
    if not header:
        dc.fail_validation(["$.file: 文件为空或没有表头行, 请提供含表头的数据文件"])
    if not rows:
        dc.fail_validation(["$.file: 数据行为 0 (仅有表头), 无法画像, 请提供含数据行的文件"])

    warnings = list(meta.get("warnings", []))
    n_rows = len(rows)

    # 敏感列先行：示例值与 top_values 需要脱敏
    sensitive = dc.detect_sensitive_columns(header, rows)
    sensitive_map = {s["name"]: s["kind"] for s in sensitive}
    for s in sensitive:
        warnings.append(
            f"检测到敏感列 '{s['name']}' (类型: {s['kind']}, 命中率: {s['hit_rate']}), "
            "画像示例值已脱敏, 报告中将以聚合/脱敏形式展示")

    columns = []
    for col in header:
        raw_values = [r.get(col, "") for r in rows]
        non_missing = [v for v in raw_values if not dc.is_missing(v)]
        missing_count = n_rows - len(non_missing)
        ctype, confidence = dc.infer_column_type(non_missing)
        col_info = {
            "name": col,
            "type": ctype,
            "confidence": confidence,
            "missing_count": missing_count,
            "missing_rate": dc.round6(missing_count / n_rows),
            "unique_count": len(set(non_missing)),
        }
        # 示例值（脱敏）
        examples = []
        for v in non_missing:
            if v not in examples:
                examples.append(v)
            if len(examples) >= EXAMPLES_LIMIT:
                break
        if col in sensitive_map:
            examples = [dc.mask_value(v, sensitive_map[col]) for v in examples]
        col_info["examples"] = examples

        if ctype in ("integer", "float") and col not in sensitive_map:
            nums = [dc.parse_number(v) for v in non_missing]
            nums = [x for x in nums if x is not None]
            col_info["stats"] = dc.column_stats(nums)
            unparsed = len(non_missing) - len(nums)
            if unparsed:
                warnings.append(f"列 '{col}' 有 {unparsed} 个非空值无法解析为数值, 未计入统计")
        elif ctype in ("integer", "float") and col in sensitive_map:
            warnings.append(f"敏感列 '{col}' 不计算数值统计(防原值经统计量泄露)")
        elif ctype == "date":
            prefer, note = dc.detect_date_prefer(non_missing)
            if "无法多数决" not in note:
                warnings.append(f"列 '{col}': {note}")
            parsed = [dc.parse_date(v, prefer=prefer) for v in non_missing]
            parsed = [d for d in parsed if d]
            if parsed:
                col_info["date_range"] = {"min": min(parsed), "max": max(parsed)}
        if ctype in ("enum", "boolean") or (ctype == "text" and col_info["unique_count"] <= 20):
            counts = {}
            for v in non_missing:
                counts[v] = counts.get(v, 0) + 1
            top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_VALUES_LIMIT]
            if col in sensitive_map:
                top = [(dc.mask_value(v, sensitive_map[col]), c) for v, c in top]
            col_info["top_values"] = [{"value": v, "count": c} for v, c in top]
        if col_info["missing_rate"] == 1.0:
            warnings.append(f"列 '{col}' 全部为空(missing_rate=1.0), 建议检查导出口径")
        columns.append(col_info)

    # 完全重复行计数（所有列值一致）
    seen = set()
    dup = 0
    for r in rows:
        key = tuple(r.get(c, "") for c in header)
        if key in seen:
            dup += 1
        else:
            seen.add(key)

    suspected_keys = [
        c["name"] for c in columns
        if c["missing_count"] == 0 and c["unique_count"] == n_rows
        and c["type"] in ("integer", "text")
    ]
    suspected_time = [c["name"] for c in columns if c["type"] == "date"]
    if len(header) == 1:
        warnings.append("数据仅 1 列, 维度不足, 仅可做分布与统计画像")
    constant_cols = [c["name"] for c in columns
                     if c["unique_count"] == 1 and c["missing_count"] < n_rows]
    for name in constant_cols:
        warnings.append(f"列 '{name}' 为常量列(唯一值=1), 无方差, 异常检测将不报警")

    profile = {
        "source": {
            "path": str(path_str),
            "format": Path(path_str).suffix.lower().lstrip("."),
            "encoding": meta.get("encoding"),
            "delimiter": meta.get("delimiter"),
            "sheet": meta.get("sheet"),
        },
        "shape": {
            "rows": n_rows,
            "columns": len(header),
            "truncated": bool(meta.get("truncated")),
            "max_rows": max_rows,
        },
        "duplicate_rows": dup,
        "columns": columns,
        "suspected_keys": suspected_keys,
        "suspected_time_columns": suspected_time,
        "sensitive_columns": sensitive,
        "warnings": warnings,
    }
    return profile


def main() -> None:
    parser = argparse.ArgumentParser(description="企业数据画像（数据获取与理解）")
    parser.add_argument("file", help="数据文件路径 (csv/tsv/json/jsonl/xlsx)")
    parser.add_argument("--sheet", default=None, help="xlsx 工作表名(默认首个)")
    parser.add_argument("--max-rows", type=int, default=dc.MAX_ROWS, help="读取行数上限")
    args = parser.parse_args()
    if args.max_rows < 1:
        dc.fail_validation(["$.--max-rows: 必须为正整数"])
    dc.setup_stdio()
    dc.emit_json(build_profile(args.file, sheet=args.sheet, max_rows=args.max_rows))


if __name__ == "__main__":
    main()
