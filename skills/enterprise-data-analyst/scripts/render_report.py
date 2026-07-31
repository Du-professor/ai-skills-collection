"""render_report.py — 多维可视化与自包含 HTML 分析报告渲染脚本。

用法：
    python render_report.py --spec 报告规格.json --out 报告.html

报告规格 JSON 骨架（白名单键；图表/表格数据只能经 source 引用脚本输出
JSON/数据文件路径，由本脚本自行提取，规格内禁止内联任何数值）：
    {
      "title": "月度销售经营分析报告",
      "sections": [
        {"kind": "profile_summary", "source": "profile.json"},
        {"kind": "quality_log", "source": "clean-log.json", "max_rows": 50},
        {"kind": "chart", "chart_type": "line", "title": "销售额月度趋势",
         "source": "analysis.json", "metric": "销售额"},
        {"kind": "chart", "chart_type": "pie", "title": "渠道占比",
         "source": "analysis.json", "dimension": "channel", "metric": "销售额"},
        {"kind": "chart", "chart_type": "histogram", "title": "金额分布",
         "source": "cleaned.csv", "column": "amount"},
        {"kind": "anomaly_list", "source": "analysis.json"},
        {"kind": "attribution_table", "source": "analysis.json"},
        {"kind": "forecast_table", "source": "analysis.json"},
        {"kind": "text", "heading": "结论", "body": "……"},
        {"kind": "actions", "items": ["……"]},
        {"kind": "disclaimer"}, {"kind": "privacy"}
      ]
    }

图表六型：line / bar / grouped_bar / pie / scatter / histogram。
HTML 单文件自包含：内联 SVG 与样式，无 <script>、无外部资源、全部文本转义。
免责声明与数据隐私说明两节由脚本强制注入（规格未声明也追加）。

退出契约：exit 0 成功；exit 2 规格校验失败（字段级报错）；exit 1 运行错误。
确定性：无时间戳、无随机数，同输入字节级一致。
"""

from __future__ import annotations

import argparse
import html
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import datacommon as dc

# 规格内禁止内联的结果字段（数值只能来自 source 引用的脚本输出）
FORBIDDEN_REPORT_KEYS = {
    "value", "yhat", "mean", "delta", "pct", "total",
    "contribution", "share", "score",
}

CHART_TYPES = {"line", "bar", "grouped_bar", "pie", "scatter", "histogram"}
SECTION_KINDS = {
    "profile_summary", "quality_log", "chart", "anomaly_list",
    "attribution_table", "forecast_table", "text", "actions",
    "disclaimer", "privacy",
}

PALETTE = ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed",
           "#0891b2", "#db2777", "#65a30d", "#ea580c", "#4f46e5"]
FINANCE_UP = "#dc2626"    # 红涨（中国市场惯例，仅 finance_palette=true 时启用）
FINANCE_DOWN = "#16a34a"  # 绿跌
TEXT_COLOR = "#1f2937"
GRID_COLOR = "#e5e7eb"
AXIS_COLOR = "#9ca3af"
FONT_STACK = "'Microsoft YaHei','PingFang SC','Noto Sans CJK SC',sans-serif"

DISCLAIMER_TEXT = (
    "本报告由 AI 协同确定性脚本生成，全部统计数值均由脚本按固定算法计算，仅供参考，"
    "不构成任何经营、投资或决策承诺；分析结论依赖输入数据的完整性与真实性，"
    "预测结果存在不确定性，请结合业务实际审慎采信。"
)
PRIVACY_TEXT = (
    "数据文件仅由用户显式提供并在本地处理：不联网、不上传、不存储；"
    "敏感列（手机号/证件号/邮箱/银行卡号）在画像与本报告中均已脱敏展示，"
    "原值仅保留于用户本地的清洗日志文件，未写入本报告。"
)


def esc(text) -> str:
    """HTML/SVG 文本统一转义（防数据内注入标记）。"""
    return html.escape(str(text), quote=True)


# ---------------------------------------------------------------------------
# 规格校验
# ---------------------------------------------------------------------------

CHART_REQUIRED = {
    "line": ("metric",), "bar": ("metric",), "grouped_bar": ("metrics",),
    "pie": ("dimension", "metric"), "scatter": ("x", "y"), "histogram": ("column",),
}
SECTION_ALLOWED = {
    "profile_summary": {"kind", "source"},
    "quality_log": {"kind", "source", "max_rows", "sensitive_columns"},
    "chart": {"kind", "chart_type", "title", "source", "metric", "metrics",
              "dimension", "column", "x", "y", "finance_palette"},
    "anomaly_list": {"kind", "source"},
    "attribution_table": {"kind", "source"},
    "forecast_table": {"kind", "source"},
    "text": {"kind", "heading", "body"},
    "actions": {"kind", "items"},
    "disclaimer": {"kind"},
    "privacy": {"kind"},
}


def validate_report_spec(spec: object) -> list:
    errors = []
    errors.extend(dc.find_forbidden_keys(spec, FORBIDDEN_REPORT_KEYS))
    if not isinstance(spec, dict):
        return errors + ["$: 报告规格必须是对象"]
    errors.extend(dc.check_whitelist(spec, {"title", "sections"}, "$"))
    if not spec.get("title") or not str(spec.get("title")).strip():
        errors.append("$.title: 必须是非空字符串")
    sections = spec.get("sections")
    if not isinstance(sections, list) or not sections:
        return errors + ["$.sections: 必须是非空数组"]
    for i, sec in enumerate(sections):
        base = f"$.sections[{i}]"
        if not isinstance(sec, dict):
            errors.append(f"{base}: 必须是对象")
            continue
        kind = sec.get("kind")
        if kind not in SECTION_KINDS:
            errors.append(f"{base}.kind: 非法取值 '{kind}' (允许: {sorted(SECTION_KINDS)})")
            continue
        errors.extend(dc.check_whitelist(sec, SECTION_ALLOWED[kind], base))
        if kind == "chart":
            ctype = sec.get("chart_type")
            if ctype not in CHART_TYPES:
                errors.append(f"{base}.chart_type: 非法取值 '{ctype}' (允许: {sorted(CHART_TYPES)})")
            else:
                for req in CHART_REQUIRED[ctype]:
                    if not sec.get(req):
                        errors.append(f"{base}.{req}: chart_type={ctype} 必须提供该字段")
            if not sec.get("source"):
                errors.append(f"{base}.source: chart 必须提供数据引用路径")
        if kind in ("profile_summary", "quality_log", "anomaly_list",
                    "attribution_table", "forecast_table") and not sec.get("source"):
            errors.append(f"{base}.source: {kind} 必须提供数据引用路径")
        if kind == "text" and not sec.get("body"):
            errors.append(f"{base}.body: text 章节必须提供正文")
        if kind == "actions":
            items = sec.get("items")
            if not isinstance(items, list) or not items:
                errors.append(f"{base}.items: actions 必须提供非空字符串数组")
            elif not all(isinstance(x, str) and x.strip() for x in items):
                errors.append(f"{base}.items: 必须全部是非空字符串")
    return errors


# ---------------------------------------------------------------------------
# SVG 图表（纯字符串拼装；viewBox 0 0 800 420）
# ---------------------------------------------------------------------------
_SVG_W, _SVG_H = 800, 420
_ML, _MR, _MT, _MB = 64, 24, 46, 58


def _svg_open(title: str) -> list:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_W} {_SVG_H}" role="img">',
        f'<rect width="{_SVG_W}" height="{_SVG_H}" fill="#ffffff"/>',
        f'<text x="{_ML}" y="26" font-size="15" font-weight="600" '
        f'fill="{TEXT_COLOR}" font-family="{FONT_STACK}">{esc(title)}</text>',
    ]


def _svg_empty(title: str) -> str:
    parts = _svg_open(title)
    parts.append(f'<text x="{_SVG_W // 2}" y="{_SVG_H // 2}" font-size="14" fill="{AXIS_COLOR}" '
                 f'text-anchor="middle" font-family="{FONT_STACK}">无数据</text>')
    parts.append("</svg>")
    return "".join(parts)


def _axes(parts: list, y_ticks: list, ymin: float, ymax: float,
          x_labels: list, x_step: int = 1) -> tuple:
    """绘制坐标轴/网格/刻度。返回 (plot_w, plot_h, y_of) 供数据映射。"""
    plot_w = _SVG_W - _ML - _MR
    plot_h = _SVG_H - _MT - _MB
    span = (ymax - ymin) or 1.0

    def y_of(v: float) -> float:
        return _MT + plot_h - (v - ymin) / span * plot_h

    for t in y_ticks:
        y = y_of(t)
        parts.append(f'<line x1="{_ML}" y1="{y:.2f}" x2="{_ML + plot_w}" y2="{y:.2f}" '
                     f'stroke="{GRID_COLOR}" stroke-width="1"/>')
        parts.append(f'<text x="{_ML - 8}" y="{y + 4:.2f}" font-size="11" fill="{AXIS_COLOR}" '
                     f'text-anchor="end" font-family="{FONT_STACK}">{esc(dc.fmt_tick(t))}</text>')
    parts.append(f'<line x1="{_ML}" y1="{_MT}" x2="{_ML}" y2="{_MT + plot_h}" stroke="{AXIS_COLOR}"/>')
    parts.append(f'<line x1="{_ML}" y1="{_MT + plot_h}" x2="{_ML + plot_w}" y2="{_MT + plot_h}" stroke="{AXIS_COLOR}"/>')
    n = len(x_labels)
    for i, label in enumerate(x_labels):
        if i % x_step != 0 and i != n - 1:
            continue
        x = _ML + (i + 0.5) / max(1, n) * plot_w
        parts.append(f'<text x="{x:.2f}" y="{_MT + plot_h + 18}" font-size="11" fill="{AXIS_COLOR}" '
                     f'text-anchor="middle" font-family="{FONT_STACK}">{esc(label)}</text>')
    return plot_w, plot_h, y_of


def svg_line(title: str, categories: list, values: list,
             finance: bool = False) -> str:
    """折线图。value=None 的缺口断开不连线；finance=True 时按涨跌红绿着色。"""
    if not categories:
        return _svg_empty(title)
    nums = [v for v in values if v is not None]
    if not nums:
        return _svg_empty(title)
    ticks = dc.nice_ticks(min(nums), max(nums), 5)
    ymin, ymax = ticks[0], ticks[-1]
    parts = _svg_open(title)
    step = max(1, math.ceil(len(categories) / 10))
    plot_w, plot_h, y_of = _axes(parts, ticks, ymin, ymax, categories, step)
    n = len(categories)

    def x_of(i: int) -> float:
        return _ML + (i + 0.5) / n * plot_w

    segment = []
    for i, v in enumerate(values):
        if v is None:
            if len(segment) >= 2:
                _draw_polyline(parts, segment, y_of, finance, values)
            segment = []
            continue
        segment.append(i)
    if len(segment) >= 2:
        _draw_polyline(parts, segment, y_of, finance, values)
    for i, v in enumerate(values):
        if v is None:
            continue
        color = PALETTE[0]
        if finance and i > 0:
            prev = next((values[j] for j in range(i - 1, -1, -1) if values[j] is not None), None)
            if prev is not None:
                color = FINANCE_UP if v >= prev else FINANCE_DOWN
        parts.append(f'<circle cx="{x_of(i):.2f}" cy="{y_of(v):.2f}" r="3.5" fill="{color}"/>')
    parts.append("</svg>")
    return "".join(parts)


def _draw_polyline(parts: list, idxs: list, y_of, finance: bool, values: list) -> None:
    n_plot = len(values)
    plot_w = _SVG_W - _ML - _MR

    def x_of(i: int) -> float:
        return _ML + (i + 0.5) / n_plot * plot_w

    if not finance:
        pts = " ".join(f"{x_of(i):.2f},{y_of(values[i]):.2f}" for i in idxs)
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{PALETTE[0]}" stroke-width="2"/>')
        return
    for a, b in zip(idxs, idxs[1:]):
        color = FINANCE_UP if values[b] >= values[a] else FINANCE_DOWN
        parts.append(f'<line x1="{x_of(a):.2f}" y1="{y_of(values[a]):.2f}" '
                     f'x2="{x_of(b):.2f}" y2="{y_of(values[b]):.2f}" stroke="{color}" stroke-width="2"/>')


def svg_bar(title: str, categories: list, values: list,
            groups: list = None) -> str:
    """柱状图（groups 为 None）或分组柱状图（groups=[{name, values}]）。空值跳过。"""
    if not categories:
        return _svg_empty(title)
    series_list = groups if groups else [{"name": "", "values": values}]
    nums = [v for g in series_list for v in g["values"] if v is not None]
    if not nums:
        return _svg_empty(title)
    ticks = dc.nice_ticks(min(0, min(nums)), max(nums), 5)
    ymin, ymax = ticks[0], ticks[-1]
    parts = _svg_open(title)
    step = max(1, math.ceil(len(categories) / 12))
    plot_w, plot_h, y_of = _axes(parts, ticks, ymin, ymax, categories, step)
    n = len(categories)
    g_count = len(series_list)
    slot = plot_w / n
    bar_w = slot * 0.7 / g_count
    zero_y = y_of(max(0, ymin))
    for gi, g in enumerate(series_list):
        color = PALETTE[gi % len(PALETTE)]
        for i, v in enumerate(g["values"]):
            if v is None:
                continue
            x = _ML + i * slot + slot * 0.15 + gi * bar_w
            y_top = y_of(max(v, 0))
            height = abs(y_of(v) - zero_y)
            parts.append(f'<rect x="{x:.2f}" y="{y_top:.2f}" width="{bar_w:.2f}" '
                         f'height="{height:.2f}" fill="{color}"/>')
    if groups:
        lx = _ML + 8
        for gi, g in enumerate(series_list):
            color = PALETTE[gi % len(PALETTE)]
            parts.append(f'<rect x="{lx}" y="14" width="10" height="10" fill="{color}"/>')
            parts.append(f'<text x="{lx + 14}" y="23" font-size="11" fill="{TEXT_COLOR}" '
                         f'font-family="{FONT_STACK}">{esc(g["name"])}</text>')
            lx += 14 + 11 * (len(str(g["name"])) + 2) + 16
    parts.append("</svg>")
    return "".join(parts)


def svg_pie(title: str, labels: list, values: list) -> str:
    """饼图。占比 ≤7 类直接展示，更多由调用方合并；右侧图例带百分比。"""
    total = sum(values)
    if not values or total <= 0:
        return _svg_empty(title)
    parts = _svg_open(title)
    cx, cy, r = 250, 220, 130
    angle = -90.0
    for i, (label, v) in enumerate(zip(labels, values)):
        frac = v / total
        sweep = frac * 360.0
        color = PALETTE[i % len(PALETTE)]
        if frac >= 0.999999:
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')
        else:
            a1 = math.radians(angle)
            a2 = math.radians(angle + sweep)
            x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
            x2, y2 = cx + r * math.cos(a2), cy + r * math.sin(a2)
            large = 1 if sweep > 180 else 0
            parts.append(
                f'<path d="M{cx},{cy} L{x1:.2f},{y1:.2f} '
                f'A{r},{r} 0 {large} 1 {x2:.2f},{y2:.2f} Z" fill="{color}"/>')
        angle += sweep
    ly = 90
    for i, (label, v) in enumerate(zip(labels, values)):
        color = PALETTE[i % len(PALETTE)]
        pct = v / total * 100
        parts.append(f'<rect x="470" y="{ly - 10}" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="486" y="{ly}" font-size="12" fill="{TEXT_COLOR}" '
                     f'font-family="{FONT_STACK}">{esc(label)} ({pct:.1f}%)</text>')
        ly += 24
    parts.append("</svg>")
    return "".join(parts)


def svg_scatter(title: str, xs: list, ys: list, x_name: str, y_name: str) -> str:
    if not xs:
        return _svg_empty(title)
    parts = _svg_open(title)
    y_ticks = dc.nice_ticks(min(ys), max(ys), 5)
    x_ticks = dc.nice_ticks(min(xs), max(xs), 6)
    plot_w = _SVG_W - _ML - _MR
    plot_h = _SVG_H - _MT - _MB
    ymin, ymax = y_ticks[0], y_ticks[-1]
    xmin, xmax = x_ticks[0], x_ticks[-1]
    xspan = (xmax - xmin) or 1.0
    for t in x_ticks:
        x = _ML + (t - xmin) / xspan * plot_w
        parts.append(f'<line x1="{x:.2f}" y1="{_MT}" x2="{x:.2f}" y2="{_MT + plot_h}" stroke="{GRID_COLOR}"/>')
        parts.append(f'<text x="{x:.2f}" y="{_MT + plot_h + 18}" font-size="11" fill="{AXIS_COLOR}" '
                     f'text-anchor="middle" font-family="{FONT_STACK}">{esc(dc.fmt_tick(t))}</text>')
    _, _, y_of = _axes(parts, y_ticks, ymin, ymax, [], 1)
    parts.append(f'<text x="{_ML + plot_w // 2}" y="{_SVG_H - 8}" font-size="12" fill="{TEXT_COLOR}" '
                 f'text-anchor="middle" font-family="{FONT_STACK}">{esc(x_name)}</text>')
    parts.append(f'<text x="14" y="{_MT + plot_h // 2}" font-size="12" fill="{TEXT_COLOR}" '
                 f'text-anchor="middle" font-family="{FONT_STACK}" '
                 f'transform="rotate(-90 14 {_MT + plot_h // 2})">{esc(y_name)}</text>')
    for xv, yv in zip(xs, ys):
        x = _ML + (xv - xmin) / xspan * plot_w
        parts.append(f'<circle cx="{x:.2f}" cy="{y_of(yv):.2f}" r="3.5" '
                     f'fill="{PALETTE[0]}" fill-opacity="0.65"/>')
    parts.append("</svg>")
    return "".join(parts)


def svg_histogram(title: str, values: list, bins: int = 10) -> str:
    if not values:
        return _svg_empty(title)
    vmin, vmax = min(values), max(values)
    if vmin == vmax:
        vmin, vmax = vmin - 0.5, vmax + 0.5
    width = (vmax - vmin) / bins
    counts = [0] * bins
    for v in values:
        idx = min(bins - 1, int((v - vmin) / width))
        counts[idx] += 1
    labels = [f"{dc.fmt_tick(vmin + i * width)}" for i in range(bins)]
    parts = _svg_open(title)
    ticks = dc.nice_ticks(0, max(counts), 5)
    plot_w, plot_h, y_of = _axes(parts, ticks, ticks[0], ticks[-1], labels, 2)
    slot = plot_w / bins
    for i, c in enumerate(counts):
        x = _ML + i * slot + 1
        y = y_of(c)
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{slot - 2:.2f}" '
                     f'height="{y_of(0) - y:.2f}" fill="{PALETTE[0]}"/>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# 数据提取（source 引用 -> 图表/表格数据）
# ---------------------------------------------------------------------------

def load_source(path_str: str):
    """按扩展名加载 source：.json -> 解析 JSON；数据文件 -> 数据集。"""
    p = Path(path_str)
    if not p.is_file():
        dc.fail_runtime(f"source 引用的文件不存在: {path_str}")
    if p.suffix.lower() == ".json":
        return dc.load_json_file(path_str, role="source")
    header, rows, _ = dc.read_dataset(path_str)
    return {"__dataset__": True, "header": header, "rows": rows}


def render_chart(sec: dict) -> str:
    ctype = sec["chart_type"]
    title = sec.get("title", "")
    src = load_source(sec["source"])
    if ctype in ("line", "bar"):
        series = (src.get("series") or {}).get(sec["metric"])
        if series is None:
            dc.fail_validation([f"$.chart: 指标 '{sec['metric']}' 在 {sec['source']} 的 series 中不存在"])
        categories = [p["bucket"] for p in series]
        values = [p["value"] for p in series]
        if ctype == "line":
            return svg_line(title, categories, values, bool(sec.get("finance_palette")))
        return svg_bar(title, categories, values)
    if ctype == "grouped_bar":
        categories = None
        groups = []
        for alias in sec["metrics"]:
            series = (src.get("series") or {}).get(alias)
            if series is None:
                dc.fail_validation([f"$.chart: 指标 '{alias}' 在 {sec['source']} 的 series 中不存在"])
            if categories is None:
                categories = [p["bucket"] for p in series]
            groups.append({"name": alias, "values": [p["value"] for p in series]})
        return svg_bar(title, categories, None, groups=groups)
    if ctype == "pie":
        key = f"{sec['dimension']}@{sec['metric']}"
        items = (src.get("dimension_totals") or {}).get(key)
        if items is None:
            dc.fail_validation([f"$.chart: 维度汇总 '{key}' 在 {sec['source']} 中不存在"])
        items = items[:7]
        if len((src.get("dimension_totals") or {}).get(key, [])) > 7:
            rest = (src.get("dimension_totals") or {})[key][7:]
            items.append({"value": "其他", "total": sum(x["total"] for x in rest)})
        return svg_pie(title, [x["value"] for x in items], [x["total"] for x in items])
    if ctype == "histogram":
        if not src.get("__dataset__"):
            dc.fail_validation([f"$.chart: histogram 的 source 必须是数据文件(csv/json/xlsx): {sec['source']}"])
        col = sec["column"]
        if col not in src["header"]:
            dc.fail_validation([f"$.chart: 列 '{col}' 在 {sec['source']} 中不存在"])
        values = [dc.parse_number(r.get(col, "")) for r in src["rows"]]
        values = [v for v in values if v is not None]
        return svg_histogram(title, values)
    if ctype == "scatter":
        if not src.get("__dataset__"):
            dc.fail_validation([f"$.chart: scatter 的 source 必须是数据文件(csv/json/xlsx): {sec['source']}"])
        x_col, y_col = sec["x"], sec["y"]
        for c in (x_col, y_col):
            if c not in src["header"]:
                dc.fail_validation([f"$.chart: 列 '{c}' 在 {sec['source']} 中不存在"])
        pairs = [(dc.parse_number(r.get(x_col, "")), dc.parse_number(r.get(y_col, "")))
                 for r in src["rows"]]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        return svg_scatter(title, [a for a, _ in pairs], [b for _, b in pairs], x_col, y_col)
    dc.fail_validation([f"$.chart.chart_type: 未支持的类型 '{ctype}'"])


# ---------------------------------------------------------------------------
# HTML 章节渲染
# ---------------------------------------------------------------------------

def _table(headers: list, rows: list) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _fmt_cell(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return dc.fmt_number(v)
    return str(v)


def _mask_value_safe(val, kind: str):
    """对非空敏感值脱敏；空值/None 原样返回（交由 _fmt_cell 显示占位）。"""
    if val is None or val == "":
        return val
    return dc.mask_value(val, kind)


def render_profile_summary(sec: dict) -> str:
    src = load_source(sec["source"])
    shape = src.get("shape", {})
    lines = [
        f"数据规模：{shape.get('rows', '—')} 行 × {shape.get('columns', '—')} 列"
        + ("（已截断）" if shape.get("truncated") else ""),
        f"完全重复行：{src.get('duplicate_rows', 0)}；"
        f"疑似主键：{', '.join(src.get('suspected_keys', [])) or '无'}；"
        f"疑似时间列：{', '.join(src.get('suspected_time_columns', [])) or '无'}",
    ]
    rows = []
    for c in src.get("columns", []):
        summary = ""
        if c.get("stats"):
            s = c["stats"]
            summary = f"{_fmt_cell(s.get('min'))} ~ {_fmt_cell(s.get('max'))}, 均值 {_fmt_cell(s.get('mean'))}"
        elif c.get("date_range"):
            summary = f"{c['date_range'].get('min')} ~ {c['date_range'].get('max')}"
        rows.append([c.get("name"), c.get("type"), c.get("confidence"),
                     f"{c.get('missing_count')} ({round((c.get('missing_rate') or 0) * 100, 1)}%)",
                     c.get("unique_count"), summary])
    html_parts = [f"<h2>数据画像摘要</h2><p>{esc('；'.join(lines))}</p>",
                  _table(["列名", "类型", "置信度", "缺失", "唯一值", "范围/均值"], rows)]
    warnings = src.get("warnings", [])
    if warnings:
        html_parts.append("<ul class='warn'>" + "".join(f"<li>{esc(w)}</li>" for w in warnings) + "</ul>")
    return "<section>" + "".join(html_parts) + "</section>"


def render_quality_log(sec: dict) -> str:
    src = load_source(sec["source"])
    max_rows = int(dc.parse_number(sec.get("max_rows", 50)) or 50)
    # 显式敏感列（可由画像产出传入 sec.sensitive_columns）；与逐条自动检测并用，
    # 确保共享 HTML 报告中敏感列的原值被脱敏，仅展示脱敏摘要。
    sensitive_cols = set(sec.get("sensitive_columns") or [])
    counts = src.get("counts", {})
    head = (f"<h2>数据质量报告</h2><p>清洗前行数 {src.get('rows_before')} → 清洗后行数 {src.get('rows_after')}；"
            f"改动单元格 {counts.get('cells_changed', 0)} 个；删除行 {counts.get('rows_dropped', 0)} 行"
            + ("；日志已截断（仅展示前 1 万条）" if src.get("truncated") else "") + "</p>")
    changes = src.get("changes", [])[:max_rows]
    masked_any = False
    rows = []
    for c in changes:
        col = c.get("col")
        old, new = c.get("old"), c.get("new")
        # 敏感列：优先用画像显式集合，否则按列名+值自动判定
        if col in sensitive_cols:
            kind = dc.classify_sensitive(col, old) or dc.classify_sensitive(col, new) or "phone"
        else:
            kind = dc.classify_sensitive(col, old) or dc.classify_sensitive(col, new)
        if kind:
            masked_any = True
            old = _mask_value_safe(old, kind)
            new = _mask_value_safe(new, kind)
        rows.append([c.get("row"), col, old, new, c.get("rule")])
    parts = [head, _table(["行号", "列", "原值(已脱敏)", "新值(已脱敏)", "规则"], rows)]
    if masked_any:
        parts.append("<p class='note'>注：敏感列（手机/邮箱/证件号/银行卡号等）的变更原值已在报告中脱敏——"
                     "报告中不展示敏感列原始值，仅展示脱敏摘要；完整变更明细保留在本地清洗日志文件（用户私有）中。</p>")
    dropped = src.get("rows_dropped", [])
    if dropped:
        parts.append("<p>删除行：" + esc("；".join(f"第 {d.get('row')} 行({d.get('reason')})" for d in dropped[:20])) + "</p>")
    warnings = src.get("warnings", [])
    if warnings:
        parts.append("<ul class='warn'>" + "".join(f"<li>{esc(w)}</li>" for w in warnings) + "</ul>")
    return "<section>" + "".join(parts) + "</section>"


def render_anomaly_list(sec: dict) -> str:
    src = load_source(sec["source"])
    anomalies = src.get("anomalies", [])
    if not anomalies:
        return "<section><h2>异常检测结果</h2><p>未检出业务指标异常。</p></section>"
    rows = [[a.get("metric"), a.get("bucket"), _fmt_cell(a.get("value")), a.get("method"),
             f"[{_fmt_cell(a.get('lower'))}, {_fmt_cell(a.get('upper'))}]", a.get("severity")]
            for a in anomalies]
    return ("<section><h2>异常检测结果</h2>"
            + _table(["指标", "周期", "数值", "方法", "正常区间", "级别"], rows) + "</section>")


def render_attribution_table(sec: dict) -> str:
    src = load_source(sec["source"])
    attr = src.get("attribution")
    if not attr:
        return "<section><h2>归因分析</h2><p>本次分析未执行归因（无规格或周期不足）。</p></section>"
    rows = []
    for c in attr.get("contributors", []):
        share = c.get("share")
        rows.append([c.get("value"), _fmt_cell(c.get("baseline")), _fmt_cell(c.get("current")),
                     _fmt_cell(c.get("contribution")),
                     f"{round(share * 100, 1)}%" if share is not None else "—"])
    others = attr.get("others", {})
    if others.get("merged_count"):
        share = others.get("share")
        rows.append([f"其他({others.get('merged_count')} 项合并)", "—", "—",
                     _fmt_cell(others.get("contribution")),
                     f"{round(share * 100, 1)}%" if share is not None else "—"])
    note = (f"指标「{attr.get('metric')}」按维度「{attr.get('dimension')}」："
            f"{attr.get('baseline_bucket')} → {attr.get('current_bucket')}，"
            f"总差额 {_fmt_cell(attr.get('delta_total'))}。{attr.get('method_note', '')}"
            + (" " + attr.get("note", "") if attr.get("note") else ""))
    return ("<section><h2>归因分析（数量贡献，非因果结论）</h2><p>" + esc(note) + "</p>"
            + _table(["维度取值", "基期", "当期", "贡献", "占比"], rows) + "</section>")


def render_forecast_table(sec: dict) -> str:
    src = load_source(sec["source"])
    fc = src.get("forecast")
    if not fc:
        return "<section><h2>预测建议</h2><p>本次分析未执行预测。</p></section>"
    parts = [f"<h2>预测建议（{esc(fc.get('method'))}）</h2>"]
    if fc.get("note"):
        parts.append(f"<p class='warn'>{esc(fc['note'])}</p>")
    if fc.get("points"):
        rows = [[p.get("bucket"), _fmt_cell(p.get("yhat")),
                 _fmt_cell(p.get("lo")), _fmt_cell(p.get("hi"))] for p in fc["points"]]
        parts.append(_table(["周期", "预测值", "区间下限", "区间上限"], rows))
    if fc.get("limitations"):
        parts.append("<p>方法局限：</p><ul class='warn'>"
                     + "".join(f"<li>{esc(x)}</li>" for x in fc["limitations"]) + "</ul>")
    return "<section>" + "".join(parts) + "</section>"


def render_text(sec: dict) -> str:
    heading = sec.get("heading", "分析结论")
    paragraphs = [p for p in str(sec.get("body", "")).split("\n") if p.strip()]
    body = "".join(f"<p>{esc(p)}</p>" for p in paragraphs)
    return f"<section><h2>{esc(heading)}</h2>{body}</section>"


def render_actions(sec: dict) -> str:
    items = "".join(f"<li>{esc(x)}</li>" for x in sec.get("items", []))
    return f"<section><h2>行动建议</h2><ol>{items}</ol></section>"


# ---------------------------------------------------------------------------
# HTML 组装
# ---------------------------------------------------------------------------

def build_html(title: str, sections_html: list) -> str:
    style = (
        "body{margin:0;background:#f3f4f6;color:#1f2937;font-family:" + FONT_STACK + ";}"
        ".report{max-width:880px;margin:0 auto;padding:24px;}"
        "header{border-bottom:2px solid #2563eb;margin-bottom:16px;}"
        "h1{font-size:22px;margin:8px 0;}h2{font-size:16px;margin:18px 0 8px;color:#111827;}"
        ".meta{color:#6b7280;font-size:12px;}"
        "section{background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;"
        "padding:14px 18px;margin:14px 0;}"
        ".table-wrap{overflow-x:auto;}"
        "table{border-collapse:collapse;width:100%;font-size:13px;}"
        "th,td{border:1px solid #e5e7eb;padding:5px 8px;text-align:left;}"
        "th{background:#f9fafb;}tr:nth-child(even){background:#fcfcfd;}"
        ".warn{color:#b45309;font-size:12px;}"
        "svg{display:block;max-width:100%;height:auto;border:1px solid #eef0f2;border-radius:6px;}"
        "ol{padding-left:22px;}footer{color:#6b7280;font-size:12px;text-align:center;margin:18px 0;}"
    )
    return ("<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{esc(title)}</title>\n<style>{style}</style>\n</head>\n<body>\n"
            f"<main class=\"report\">\n<header><h1>{esc(title)}</h1>\n"
            "<p class=\"meta\">由 enterprise-data-analyst 生成 · 数据仅在本地处理 · "
            "全部统计数值由确定性脚本产出</p></header>\n"
            + "\n".join(sections_html)
            + "\n<footer>enterprise-data-analyst · 本地确定性分析报告</footer>\n"
            "</main>\n</body>\n</html>\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="自包含 HTML 分析报告渲染")
    parser.add_argument("--spec", required=True, help="报告规格 JSON 路径")
    parser.add_argument("--out", required=True, help="输出 HTML 路径")
    args = parser.parse_args()
    dc.setup_stdio()

    spec = dc.load_json_file(args.spec, role="报告规格")
    errors = validate_report_spec(spec)
    if errors:
        dc.fail_validation(errors)
    out_path = Path(args.out).resolve()
    if out_path.suffix.lower() not in (".html", ".htm"):
        dc.fail_validation(["$.--out: 输出路径必须是 .html 文件"])
    for sec in spec["sections"]:
        src = sec.get("source")
        if src and Path(src).resolve() == out_path:
            dc.fail_validation(["$.--out: 输出路径不得与任何 source 相同"])

    sections_html = []
    chart_count = 0
    for sec in spec["sections"]:
        kind = sec["kind"]
        if kind == "chart":
            sections_html.append("<section>" + render_chart(sec) + "</section>")
            chart_count += 1
        elif kind == "profile_summary":
            sections_html.append(render_profile_summary(sec))
        elif kind == "quality_log":
            sections_html.append(render_quality_log(sec))
        elif kind == "anomaly_list":
            sections_html.append(render_anomaly_list(sec))
        elif kind == "attribution_table":
            sections_html.append(render_attribution_table(sec))
        elif kind == "forecast_table":
            sections_html.append(render_forecast_table(sec))
        elif kind == "text":
            sections_html.append(render_text(sec))
        elif kind == "actions":
            sections_html.append(render_actions(sec))
        elif kind == "disclaimer":
            sections_html.append(f"<section><h2>免责声明</h2><p>{esc(DISCLAIMER_TEXT)}</p></section>")
        elif kind == "privacy":
            sections_html.append(f"<section><h2>数据隐私说明</h2><p>{esc(PRIVACY_TEXT)}</p></section>")

    # 强制注入：免责声明与数据隐私说明缺省时自动追加
    kinds = {s["kind"] for s in spec["sections"]}
    if "disclaimer" not in kinds:
        sections_html.append(f"<section><h2>免责声明</h2><p>{esc(DISCLAIMER_TEXT)}</p></section>")
    if "privacy" not in kinds:
        sections_html.append(f"<section><h2>数据隐私说明</h2><p>{esc(PRIVACY_TEXT)}</p></section>")

    html_doc = build_html(spec["title"], sections_html)
    try:
        out_path.write_text(html_doc, encoding="utf-8")
    except OSError as exc:
        dc.fail_runtime(f"无法写出 HTML 报告: {exc}")
    dc.emit_json({"output": str(args.out), "sections": len(sections_html),
                  "charts": chart_count})


if __name__ == "__main__":
    main()
