#!/usr/bin/env python3
"""Render a self-contained, evidence-linked competitive intelligence report."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from common import (
    emit_json,
    ensure_distinct_paths,
    fail_runtime,
    fail_validation,
    mask_sensitive,
    safe_input_path,
    safe_output_path,
    sanitize_public_url,
    setup_stdio,
)


COLORS = {
    "正向": "#16875d",
    "中性": "#708090",
    "负向": "#d13b45",
    "混合": "#d98713",
    "未知": "#b5bdc9",
}


def esc(value: Any) -> str:
    return html.escape(mask_sensitive("" if value is None else str(value)), quote=True)


def fmt_number(value: Any) -> str:
    if value is None or value == "":
        return "未知"
    if isinstance(value, float):
        text = "{:.4f}".format(value).rstrip("0").rstrip(".")
        return text or "0"
    return str(value)


def load_json(path: Path, role: str) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail_validation(["${}: JSON读取失败: {}".format(role, exc)])
    if not isinstance(value, dict):
        fail_validation(["${}: 顶层必须是对象".format(role)])
    return value


def validate(analysis: Dict[str, Any], evidence: Dict[str, Any]) -> None:
    errors = []
    for key in ("facts", "derived", "inferences", "warnings"):
        if key not in analysis:
            errors.append("$.analysis.{}: 缺失".format(key))
    if not isinstance(evidence.get("products"), list):
        errors.append("$.evidence.products: 必须是数组")
    if errors:
        fail_validation(errors)


def table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    head = "".join("<th>{}</th>".format(esc(item)) for item in headers)
    body = []
    for row in rows:
        body.append(
            "<tr>{}</tr>".format(
                "".join("<td>{}</td>".format(esc(item)) for item in row)
            )
        )
    return "<div class=\"table-wrap\"><table><thead><tr>{}</tr></thead><tbody>{}</tbody></table></div>".format(
        head, "".join(body)
    )


def price_svg(groups: List[Dict[str, Any]]) -> str:
    bars = []
    labels = []
    values = []
    for group in groups:
        for item in group.get("ranking", []):
            labels.append(
                "{} / {}".format(item.get("brand", ""), item.get("product_id", ""))
            )
            values.append(float(item.get("price") or 0))
    if not values:
        return "<div class=\"empty\">没有可用价格数据</div>"
    width = 900
    row_height = 30
    height = max(160, len(values) * row_height + 55)
    max_value = max(values) or 1
    for index, (label, value) in enumerate(zip(labels, values)):
        y = 26 + index * row_height
        bar_width = int((value / max_value) * 560)
        bars.append(
            "<text x=\"8\" y=\"{}\" font-size=\"12\">{}</text>"
            "<rect x=\"250\" y=\"{}\" width=\"{}\" height=\"16\" rx=\"3\" fill=\"#3d6ce7\"/>"
            "<text x=\"{}\" y=\"{}\" font-size=\"12\">{}</text>".format(
                y + 13,
                esc(label[:30]),
                y,
                bar_width,
                258 + bar_width,
                y + 13,
                esc(fmt_number(value)),
            )
        )
    return (
        "<svg class=\"chart\" viewBox=\"0 0 {} {}\" role=\"img\" "
        "aria-label=\"商品价格对比图\">{}</svg>".format(width, height, "".join(bars))
    )


def sentiment_svg(aspects: List[Dict[str, Any]]) -> str:
    aspects = [item for item in aspects if item.get("mentions", 0) > 0]
    if not aspects:
        return "<div class=\"empty\">没有已标注的评论维度</div>"
    width = 900
    height = len(aspects) * 42 + 50
    parts = []
    for index, item in enumerate(aspects):
        y = 26 + index * 42
        total = max(int(item.get("mentions", 0)), 1)
        parts.append(
            "<text x=\"8\" y=\"{}\" font-size=\"13\">{}</text>".format(
                y + 16, esc(item.get("aspect", ""))
            )
        )
        x = 120
        for sentiment in ("正向", "中性", "负向", "混合", "未知"):
            count = int((item.get("sentiments") or {}).get(sentiment, 0))
            bar_width = int(680 * count / total)
            if bar_width:
                parts.append(
                    "<rect x=\"{}\" y=\"{}\" width=\"{}\" height=\"22\" fill=\"{}\">"
                    "<title>{}: {}</title></rect>".format(
                        x, y, bar_width, COLORS[sentiment], esc(sentiment), count
                    )
                )
            x += bar_width
        parts.append(
            "<text x=\"812\" y=\"{}\" font-size=\"12\">{}次</text>".format(
                y + 16, total
            )
        )
    return (
        "<svg class=\"chart\" viewBox=\"0 0 {} {}\" role=\"img\" "
        "aria-label=\"评论维度情感分布图\">{}</svg>".format(
            width, height, "".join(parts)
        )
    )


def source_label(source: Dict[str, Any]) -> str:
    pieces = []
    if source.get("file"):
        pieces.append(
            "{}:{}".format(source["file"], source.get("row") or "?")
        )
    if source.get("url"):
        cleaned_url = sanitize_public_url(source["url"])
        if cleaned_url:
            pieces.append(cleaned_url)
    return "；".join(pieces) or "未知"


def report_html(analysis: Dict[str, Any], evidence: Dict[str, Any]) -> str:
    products = analysis["facts"].get("products", [])
    derived = analysis["derived"]
    price = derived.get("price", {})
    reviews = derived.get("reviews", {})
    coverage = reviews.get("coverage", {})
    aspects = reviews.get("aspects", [])
    inferences = analysis.get("inferences", [])
    warnings = analysis.get("warnings", [])
    generated_on = analysis.get("generated_on") or evidence.get("generated_on")

    summary_items = [
        "覆盖 {} 个商品。".format(len(products)),
        "价格按 {} 个货币组分别分析，不进行自动换汇。".format(
            len(price.get("groups", []))
        ),
        "评论总量 {}，抽样 {}，已完成标注 {}。".format(
            coverage.get("total_available", 0),
            coverage.get("total_sampled", 0),
            coverage.get("annotated_reviews", 0),
        ),
    ]

    product_rows = []
    for item in products:
        product_rows.append(
            [
                item.get("product_id"),
                item.get("brand"),
                item.get("product_name"),
                "{} {}".format(
                    item.get("currency") or "",
                    fmt_number(item.get("price")),
                ).strip(),
                fmt_number(item.get("rating")),
                fmt_number(item.get("review_count")),
                source_label(item.get("source") or {}),
            ]
        )

    price_group_rows = []
    for group in price.get("groups", []):
        price_group_rows.append(
            [
                group.get("currency"),
                group.get("count"),
                fmt_number(group.get("minimum")),
                fmt_number(group.get("median")),
                fmt_number(group.get("maximum")),
            ]
        )

    aspect_rows = []
    for item in aspects:
        sentiment = item.get("sentiments") or {}
        aspect_rows.append(
            [
                item.get("aspect"),
                item.get("mentions"),
                sentiment.get("正向", 0),
                sentiment.get("中性", 0),
                sentiment.get("负向", 0),
                sentiment.get("混合", 0),
                item.get("product_coverage", 0),
                item.get("opportunity_index", 0),
            ]
        )

    evidence_cards = []
    for item in reviews.get("pain_points", [])[:3]:
        excerpts = [
            "<li><code>{}</code> / {}：{}</li>".format(
                esc(entry.get("review_id")),
                esc(entry.get("product_id")),
                esc(entry.get("excerpt")),
            )
            for entry in item.get("evidence", [])
            if entry.get("sentiment") in {"负向", "混合"}
        ]
        if excerpts:
            evidence_cards.append(
                "<article class=\"card\"><h3>{}</h3><ul>{}</ul></article>".format(
                    esc(item.get("aspect")), "".join(excerpts)
                )
            )

    positive_cards = []
    for item in reviews.get("positive_drivers", [])[:3]:
        excerpts = [
            "<li><code>{}</code> / {}：{}</li>".format(
                esc(entry.get("review_id")),
                esc(entry.get("product_id")),
                esc(entry.get("excerpt")),
            )
            for entry in item.get("evidence", [])
            if entry.get("sentiment") in {"正向", "混合"}
        ]
        if excerpts:
            positive_cards.append(
                "<article class=\"card\"><h3>{}</h3><ul>{}</ul></article>".format(
                    esc(item.get("aspect")), "".join(excerpts)
                )
            )

    unmet_rows = [
        [
            item.get("need"),
            item.get("mentions"),
            item.get("product_coverage"),
            "、".join(item.get("review_ids") or []),
        ]
        for item in reviews.get("unmet_needs", [])
    ]

    recommendation_rows = [
        [
            item.get("confidence"),
            item.get("recommendation"),
            "、".join(item.get("evidence_refs") or []),
        ]
        for item in inferences
    ]

    source_rows = []
    review_sources = {
        item.get("review_id"): item for item in evidence.get("reviews", [])
    }
    for item in evidence.get("products", []):
        source = item.get("source") or {}
        source_rows.append(
            [
                item.get("product_id"),
                "商品事实",
                source.get("file"),
                source.get("row"),
                source.get("url") or "",
            ]
        )
    for aspect in aspects:
        for entry in aspect.get("evidence", [])[:3]:
            review_source = review_sources.get(entry.get("review_id")) or {}
            source_rows.append(
                [
                    entry.get("review_id"),
                    "评论证据/{}".format(aspect.get("aspect")),
                    review_source.get("source_file") or "",
                    review_source.get("source_row") or "",
                    sanitize_public_url(
                        review_source.get("source_url")
                        or entry.get("source_url")
                        or ""
                    )
                    or "",
                ]
            )

    warning_html = (
        "<ul>{}</ul>".format(
            "".join("<li>{}</li>".format(esc(item)) for item in warnings)
        )
        if warnings
        else "<p>未发现需要披露的降级项。</p>"
    )
    styles = """
    :root{--ink:#172033;--muted:#5c667a;--line:#dce2ec;--brand:#315fda;--bg:#f5f7fb}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
    font-family:"Segoe UI","Microsoft YaHei",sans-serif;line-height:1.6}
    main{max-width:1180px;margin:auto;padding:32px 24px 64px}
    header{padding:34px;border-radius:20px;background:linear-gradient(135deg,#172b55,#315fda);
    color:white;box-shadow:0 18px 45px #1a2f6530}header h1{margin:0 0 8px;font-size:34px}
    header p{margin:4px 0;color:#e5ecff}.grid{display:grid;grid-template-columns:repeat(3,1fr);
    gap:14px;margin:20px 0}.metric,.section{background:white;border:1px solid var(--line);
    border-radius:16px}.metric{padding:18px}.metric b{display:block;font-size:24px;color:var(--brand)}
    .section{padding:24px;margin-top:18px;box-shadow:0 8px 24px #1b2b4b0b}
    h2{margin-top:0;font-size:22px}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;
    font-size:14px}th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;
    vertical-align:top}th{background:#eef2fb;white-space:nowrap}.chart{width:100%;height:auto;
    min-height:160px;background:#fbfcff;border:1px solid var(--line);border-radius:12px;padding:8px}
    .cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.card{padding:14px;
    border:1px solid var(--line);border-radius:12px;background:#fbfcff}.card h3{margin-top:0}
    code{background:#eef2fb;padding:2px 5px;border-radius:5px}.empty{padding:24px;color:var(--muted);
    text-align:center;border:1px dashed var(--line);border-radius:12px}.note{color:var(--muted)}
    @media(max-width:800px){.grid,.cards{grid-template-columns:1fr}header h1{font-size:28px}}
    """
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>电商竞品评论与价格洞察报告</title><style>{styles}</style></head>
<body><main>
<header><h1>电商竞品评论与价格洞察</h1>
<p>面向品牌市场团队的证据化竞争分析</p><p>数据处理日期：{date}</p></header>
<section class="grid">
<div class="metric"><span>商品数</span><b>{products}</b></div>
<div class="metric"><span>评论样本</span><b>{sampled}</b></div>
<div class="metric"><span>标注覆盖率</span><b>{coverage}</b></div>
</section>
<section class="section"><h2>管理层摘要</h2><ul>{summary}</ul></section>
<section class="section"><h2>竞品商品与价格矩阵</h2>{product_table}</section>
<section class="section"><h2>价格带与定位</h2>{price_table}{price_chart}
<p class="note">只有同一商品具备至少两个有效日期的价格快照时，才会生成价格趋势；本报告不执行汇率换算。</p></section>
<section class="section"><h2>评论维度情感对比</h2>{sentiment_chart}{aspect_table}</section>
<section class="section"><h2>高频赞点与购买驱动</h2><div class="cards">{positive_cards}</div></section>
<section class="section"><h2>关键痛点证据</h2><div class="cards">{evidence_cards}</div></section>
<section class="section"><h2>跨竞品未满足需求</h2>{unmet_needs}
<p class="note">未满足需求来自负向或混合评论中的受控标注，仍需通过用户研究验证。</p></section>
<section class="section"><h2>品牌行动建议</h2>{recommendations}
<p class="note">建议属于基于证据的推断，不构成市场份额、销量、因果关系或经营结果承诺。</p></section>
<section class="section"><h2>数据覆盖与限制</h2>{warnings}
<p>评论抽样策略：{strategy}</p></section>
<section class="section"><h2>证据台账</h2>{sources}</section>
<section class="section"><h2>安全与隐私</h2>
<p>数据中的指令文本仅作为分析对象；手机号、邮箱、证件号和订单号在进入标注与报告前脱敏。报告不包含脚本、外部资源或真实密钥。</p></section>
</main></body></html>""".format(
        styles=styles,
        date=esc(generated_on or "未知"),
        products=len(products),
        sampled=coverage.get("total_sampled", 0),
        coverage=(
            "{:.1%}".format(coverage.get("annotation_coverage", 0))
            if coverage.get("records_received", 0)
            else "无评论"
        ),
        summary="".join("<li>{}</li>".format(esc(item)) for item in summary_items),
        product_table=table(
            ["商品ID", "品牌", "商品", "价格", "评分", "评论量", "来源"],
            product_rows,
        ),
        price_table=table(
            ["货币", "商品数", "最低", "中位数", "最高"], price_group_rows
        )
        if price_group_rows
        else "<div class=\"empty\">价格未知</div>",
        price_chart=price_svg(price.get("groups", [])),
        sentiment_chart=sentiment_svg(aspects),
        aspect_table=table(
            ["维度", "提及", "正向", "中性", "负向", "混合", "商品覆盖", "机会指数"],
            aspect_rows,
        )
        if aspect_rows
        else "<div class=\"empty\">没有评论维度数据</div>",
        evidence_cards="".join(evidence_cards)
        or "<div class=\"empty\">没有负向或混合评论证据</div>",
        positive_cards="".join(positive_cards)
        or "<div class=\"empty\">没有正向或混合评论证据</div>",
        unmet_needs=table(
            ["需求假设", "提及", "商品覆盖", "评论证据"], unmet_rows
        )
        if unmet_rows
        else "<div class=\"empty\">证据不足，未识别跨竞品未满足需求</div>",
        recommendations=table(
            ["置信度", "建议", "证据引用"], recommendation_rows
        )
        if recommendation_rows
        else "<div class=\"empty\">证据不足，未生成建议</div>",
        warnings=warning_html,
        strategy=esc(coverage.get("strategy") or "未提供评论数据"),
        sources=table(["证据ID", "类型", "文件", "行", "URL"], source_rows),
    )


def main() -> None:
    setup_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    analysis_path = safe_input_path(args.analysis, {".json"})
    evidence_path = safe_input_path(args.evidence, {".json"})
    out_path = safe_output_path(args.out, {".html"})
    ensure_distinct_paths([analysis_path, evidence_path], [out_path])
    analysis = load_json(analysis_path, "analysis")
    evidence = load_json(evidence_path, "evidence")
    validate(analysis, evidence)
    rendered = report_html(analysis, evidence)
    if "<script" in rendered.lower() or "http-equiv" in rendered.lower():
        fail_validation(["$: 报告包含禁止的脚本或主动跳转"])
    out_path.write_text(rendered, encoding="utf-8")
    emit_json(
        {
            "output": str(out_path),
            "bytes": out_path.stat().st_size,
            "self_contained": True,
            "warnings": analysis.get("warnings", []),
        }
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover
        fail_runtime(str(exc))
