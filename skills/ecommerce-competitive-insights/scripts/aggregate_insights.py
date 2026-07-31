#!/usr/bin/env python3
"""Validate controlled review labels and deterministically aggregate insights."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from common import (
    emit_json,
    ensure_distinct_paths,
    fail_runtime,
    fail_validation,
    mask_sensitive,
    median,
    parse_bool,
    parse_integer,
    parse_number,
    round_number,
    safe_input_path,
    safe_output_path,
    sanitize_public_url,
    setup_stdio,
    sha256_text,
    stable_json_dump,
    text_value,
    today_iso,
)


ASPECTS = ("性能", "质量耐用", "易用性", "设计", "性价比", "物流", "售后")
SENTIMENTS = ("正向", "中性", "负向", "混合", "未知")
SEVERITIES = ("低", "中", "高", "未知")
SEVERITY_WEIGHT = {"低": 1, "中": 2, "高": 3, "未知": 0}


def read_normalized(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    required = {"product_id", "brand", "product_name", "price", "currency"}
    fields = set(reader.fieldnames or [])
    if not required.issubset(fields):
        fail_validation(
            ["$: normalized.csv缺少字段: {}".format(
                "、".join(sorted(required - fields))
            )]
        )
    if not rows:
        fail_validation(["$: normalized.csv没有商品记录"])
    return rows


def read_labels(path: Optional[Path]) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if path is None:
        return {
            "record_type": "meta",
            "total_available": 0,
            "total_sampled": 0,
            "per_product": {},
            "warnings": ["未提供评论标签，仅生成价格与商品定位分析"],
        }, []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail_validation(["$: 标签JSON读取失败: {}".format(exc)])
    errors = []
    if not isinstance(value, dict):
        fail_validation(["$: 标签JSON顶层必须是对象"])
    meta = value.get("meta")
    reviews = value.get("reviews")
    if not isinstance(meta, dict):
        errors.append("$.meta: 必须是对象")
    if not isinstance(reviews, list):
        errors.append("$.reviews: 必须是数组")
        reviews = []
    for index, item in enumerate(reviews):
        if not isinstance(item, dict):
            errors.append("$.reviews[{}]: 必须是对象".format(index))
            continue
        item["__line"] = index + 1
        if item.get("record_type") not in (None, "review"):
            errors.append(
                "$.reviews[{}].record_type: 必须是review或省略".format(index)
            )
    if errors:
        fail_validation(errors)
    return meta or {}, reviews


def validate_labels(
    rows: List[Dict[str, Any]], product_ids: set[str]
) -> List[Dict[str, Any]]:
    errors = []
    validated = []
    seen_reviews = set()
    for row in rows:
        line = row.get("__line", "?")
        path = "$[line={}]".format(line)
        review_id = text_value(row.get("review_id"))
        product_id = text_value(row.get("product_id"))
        review_text = text_value(row.get("review_text"))
        review_hash = text_value(row.get("review_hash"))
        if review_id and mask_sensitive(review_id) != review_id:
            errors.append(
                "{}.review_id: 可能包含个人信息，请重新生成匿名评论样本".format(
                    path
                )
            )
        if not review_id:
            errors.append("{}.review_id: 必填".format(path))
        elif review_id in seen_reviews:
            errors.append("{}.review_id: 重复ID {}".format(path, review_id))
        seen_reviews.add(review_id)
        if product_id not in product_ids:
            errors.append("{}.product_id: 未知商品{}".format(path, product_id))
        if not review_text:
            errors.append("{}.review_text: 必填".format(path))
        elif review_hash != sha256_text(review_text):
            errors.append("{}.review_hash: 与review_text不匹配".format(path))
        annotations = row.get("annotations")
        if not isinstance(annotations, list):
            errors.append("{}.annotations: 必须是数组".format(path))
            continue
        seen_aspects = set()
        clean_annotations = []
        for index, annotation in enumerate(annotations):
            item_path = "{}.annotations[{}]".format(path, index)
            if not isinstance(annotation, dict):
                errors.append("{}: 必须是对象".format(item_path))
                continue
            extra = set(annotation) - {
                "aspect",
                "sentiment",
                "evidence",
                "severity",
                "unmet_need",
            }
            if extra:
                errors.append(
                    "{}: 不允许字段{}".format(item_path, "、".join(sorted(extra)))
                )
            aspect = text_value(annotation.get("aspect"))
            sentiment = text_value(annotation.get("sentiment"))
            evidence = text_value(annotation.get("evidence"))
            severity = text_value(annotation.get("severity")) or "未知"
            unmet_need = mask_sensitive(annotation.get("unmet_need"))
            if aspect not in ASPECTS:
                errors.append(
                    "{}.aspect: 必须是{}".format(item_path, "、".join(ASPECTS))
                )
            elif aspect in seen_aspects:
                errors.append("{}.aspect: 同一评论维度重复".format(item_path))
            seen_aspects.add(aspect)
            if sentiment not in SENTIMENTS:
                errors.append(
                    "{}.sentiment: 必须是{}".format(
                        item_path, "、".join(SENTIMENTS)
                    )
                )
            if severity not in SEVERITIES:
                errors.append(
                    "{}.severity: 必须是{}".format(
                        item_path, "、".join(SEVERITIES)
                    )
                )
            if not evidence:
                errors.append("{}.evidence: 必填".format(item_path))
            elif len(evidence) > 120:
                errors.append("{}.evidence: 不得超过120字符".format(item_path))
            elif evidence not in review_text:
                errors.append("{}.evidence: 必须是review_text原文子串".format(item_path))
            if len(unmet_need) > 100:
                errors.append("{}.unmet_need: 不得超过100字符".format(item_path))
            if unmet_need and sentiment not in {"负向", "混合"}:
                errors.append(
                    "{}.unmet_need: 仅负向或混合情感可填写".format(item_path)
                )
            clean_annotations.append(
                {
                    "aspect": aspect,
                    "sentiment": sentiment,
                    "evidence": evidence,
                    "severity": severity,
                    "unmet_need": unmet_need,
                }
            )
        clean = dict(row)
        clean.pop("__line", None)
        source_url_raw = text_value(clean.get("source_url"))
        source_url = sanitize_public_url(source_url_raw)
        if source_url_raw and source_url is None:
            errors.append(
                "{}.source_url: 仅允许不含凭据、个人信息和内网地址的公网HTTP/HTTPS地址".format(
                    path
                )
            )
        clean["source_url"] = source_url or ""
        clean["annotations"] = clean_annotations
        validated.append(clean)
    if errors:
        fail_validation(errors)
    return validated


def latest_products(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["product_id"]].append(row)
    latest = []
    for product_id in sorted(grouped):
        choices = sorted(
            grouped[product_id],
            key=lambda row: (
                row.get("collected_at", ""),
                parse_integer(row.get("source_row")) or 0,
            ),
        )
        latest.append(choices[-1])
    return latest


def price_analysis(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    latest = latest_products(rows)
    by_currency: Dict[str, List[Tuple[float, Dict[str, str]]]] = defaultdict(list)
    for row in latest:
        price = parse_number(row.get("price"))
        currency = text_value(row.get("currency"))
        if price is not None and currency:
            by_currency[currency].append((price, row))
    groups = []
    for currency in sorted(by_currency):
        values = [item[0] for item in by_currency[currency]]
        brand_values: Dict[str, List[float]] = defaultdict(list)
        for value, row in by_currency[currency]:
            brand_values[row["brand"]].append(value)
        groups.append(
            {
                "currency": currency,
                "count": len(values),
                "minimum": round_number(min(values)),
                "maximum": round_number(max(values)),
                "median": round_number(median(values)),
                "brand_medians": [
                    {
                        "brand": brand,
                        "median": round_number(median(brand_values[brand])),
                        "count": len(brand_values[brand]),
                    }
                    for brand in sorted(brand_values)
                ],
                "ranking": [
                    {
                        "product_id": row["product_id"],
                        "brand": row["brand"],
                        "product_name": row["product_name"],
                        "price": round_number(value),
                    }
                    for value, row in sorted(
                        by_currency[currency],
                        key=lambda item: (item[0], item[1]["product_id"]),
                    )
                ],
            }
        )

    timelines: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        price = parse_number(row.get("price"))
        date = text_value(row.get("collected_at"))
        if price is not None and date:
            timelines[row["product_id"]].append(
                {
                    "date": date,
                    "price": round_number(price),
                    "currency": row["currency"],
                }
            )
    trends = []
    for product_id in sorted(timelines):
        points = sorted(
            timelines[product_id], key=lambda item: (item["date"], item["price"])
        )
        dates = {item["date"] for item in points}
        currencies = {item["currency"] for item in points}
        if len(dates) >= 2 and len(currencies) == 1:
            trends.append({"product_id": product_id, "points": points})
    return {"groups": groups, "trends": trends}


def review_analysis(
    rows: List[Dict[str, Any]], meta: Dict[str, Any]
) -> Dict[str, Any]:
    product_aspects: Dict[str, Dict[str, Counter]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    overall: Dict[str, Counter] = defaultdict(Counter)
    severity: Counter = Counter()
    evidence: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    unmet: Dict[str, Dict[str, Any]] = {}
    annotated_reviews = 0

    for row in rows:
        if row["annotations"]:
            annotated_reviews += 1
        for annotation in row["annotations"]:
            aspect = annotation["aspect"]
            sentiment = annotation["sentiment"]
            product_aspects[row["product_id"]][aspect][sentiment] += 1
            overall[aspect][sentiment] += 1
            severity[aspect] += SEVERITY_WEIGHT[annotation["severity"]]
            if len(evidence[aspect]) < 5:
                evidence[aspect].append(
                    {
                        "review_id": row["review_id"],
                        "product_id": row["product_id"],
                        "sentiment": sentiment,
                        "excerpt": annotation["evidence"],
                        "source_url": text_value(row.get("source_url")),
                    }
                )
            need = annotation["unmet_need"]
            if need:
                key = need.casefold()
                if key not in unmet:
                    unmet[key] = {
                        "need": need,
                        "mentions": 0,
                        "products": set(),
                        "review_ids": [],
                    }
                unmet[key]["mentions"] += 1
                unmet[key]["products"].add(row["product_id"])
                unmet[key]["review_ids"].append(row["review_id"])

    aspect_rows = []
    for aspect in ASPECTS:
        counts = overall[aspect]
        mentions = sum(counts.values())
        products = {
            product_id
            for product_id, aspect_map in product_aspects.items()
            if sum(aspect_map[aspect].values()) > 0
        }
        aspect_rows.append(
            {
                "aspect": aspect,
                "mentions": mentions,
                "sentiments": {name: counts[name] for name in SENTIMENTS},
                "product_coverage": len(products),
                "severity_weight": severity[aspect],
                "opportunity_index": (
                    counts["负向"] * 2
                    + counts["混合"]
                    + severity[aspect]
                    + len(products)
                ),
                "evidence": evidence[aspect],
            }
        )
    positive_drivers = sorted(
        aspect_rows,
        key=lambda item: (
            -item["sentiments"]["正向"],
            -item["mentions"],
            item["aspect"],
        ),
    )
    pain_points = sorted(
        aspect_rows,
        key=lambda item: (-item["opportunity_index"], item["aspect"]),
    )
    unmet_rows = [
        {
            "need": item["need"],
            "mentions": item["mentions"],
            "product_coverage": len(item["products"]),
            "review_ids": sorted(set(item["review_ids"])),
        }
        for item in unmet.values()
    ]
    unmet_rows.sort(
        key=lambda item: (-item["mentions"], -item["product_coverage"], item["need"])
    )
    total_available = parse_integer(meta.get("total_available")) or 0
    total_sampled = parse_integer(meta.get("total_sampled")) or len(rows)
    return {
        "coverage": {
            "total_available": total_available,
            "total_sampled": total_sampled,
            "records_received": len(rows),
            "annotated_reviews": annotated_reviews,
            "sampling_coverage": (
                round(total_sampled / total_available, 6)
                if total_available
                else 0
            ),
            "annotation_coverage": (
                round(annotated_reviews / len(rows), 6) if rows else 0
            ),
            "per_product": meta.get("per_product", {}),
            "strategy": meta.get("strategy"),
        },
        "by_product": [
            {
                "product_id": product_id,
                "aspects": [
                    {
                        "aspect": aspect,
                        "mentions": sum(counter.values()),
                        "sentiments": {
                            name: counter[name] for name in SENTIMENTS
                        },
                    }
                    for aspect, counter in sorted(aspect_map.items())
                ],
            }
            for product_id, aspect_map in sorted(product_aspects.items())
        ],
        "aspects": aspect_rows,
        "positive_drivers": [
            item for item in positive_drivers if item["sentiments"]["正向"] > 0
        ][:5],
        "pain_points": [
            item
            for item in pain_points
            if item["sentiments"]["负向"] + item["sentiments"]["混合"] > 0
        ][:5],
        "unmet_needs": unmet_rows[:10],
    }


def product_matrix(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    return [
        {
            "product_id": row["product_id"],
            "brand": row["brand"],
            "product_name": row["product_name"],
            "price": parse_number(row.get("price")),
            "currency": row.get("currency") or None,
            "rating": parse_number(row.get("rating")),
            "review_count": parse_integer(row.get("review_count")),
            "platform": row.get("platform") or None,
            "collected_at": row.get("collected_at") or None,
            "is_own_brand": parse_bool(row.get("is_own_brand")),
            "source": {
                "file": row.get("source_file"),
                "row": parse_integer(row.get("source_row")),
                "url": row.get("url") or None,
            },
        }
        for row in latest_products(rows)
    ]


def build_inferences(
    price: Dict[str, Any], reviews: Dict[str, Any]
) -> List[Dict[str, Any]]:
    results = []
    if reviews["positive_drivers"]:
        item = reviews["positive_drivers"][0]
        results.append(
            {
                "type": "inference",
                "confidence": "中",
                "recommendation": "传播内容可优先强化“{}”优势，并以评论证据支撑。".format(
                    item["aspect"]
                ),
                "evidence_refs": [
                    entry["review_id"] for entry in item["evidence"][:3]
                ],
            }
        )
    if reviews["pain_points"]:
        item = reviews["pain_points"][0]
        results.append(
            {
                "type": "inference",
                "confidence": "中",
                "recommendation": "优先验证并改善“{}”相关负向体验。".format(
                    item["aspect"]
                ),
                "evidence_refs": [
                    entry["review_id"]
                    for entry in item["evidence"]
                    if entry["sentiment"] in {"负向", "混合"}
                ][:3],
            }
        )
    if reviews["unmet_needs"]:
        item = reviews["unmet_needs"][0]
        results.append(
            {
                "type": "inference",
                "confidence": "中",
                "recommendation": "将“{}”列为产品或服务机会假设，并通过用户访谈进一步验证。".format(
                    item["need"]
                ),
                "evidence_refs": item["review_ids"][:3],
            }
        )
    if price["groups"]:
        results.append(
            {
                "type": "inference",
                "confidence": "高",
                "recommendation": "定价讨论必须按货币分别参考报告中的价格带；未执行自动换汇。",
                "evidence_refs": [
                    "price-group:{}".format(group["currency"])
                    for group in price["groups"]
                ],
            }
        )
    return results


def main() -> None:
    setup_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("normalized")
    parser.add_argument("--labels")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    normalized_path = safe_input_path(args.normalized, {".csv"})
    labels_path = (
        safe_input_path(args.labels, {".json"}) if args.labels else None
    )
    out_path = safe_output_path(args.out, {".json"})
    ensure_distinct_paths(
        [normalized_path] + ([labels_path] if labels_path else []), [out_path]
    )

    rows = read_normalized(normalized_path)
    product_ids = {row["product_id"] for row in rows}
    if not 2 <= len(product_ids) <= 20:
        fail_validation(["$: 商品数量必须为2到20"])
    meta, label_rows = read_labels(labels_path)
    validated = validate_labels(label_rows, product_ids)
    price = price_analysis(rows)
    reviews = review_analysis(validated, meta)
    warnings = sorted(
        set(
            list(meta.get("warnings") or [])
            + (
                ["未发现可用价格，价格分析已降级"]
                if not price["groups"]
                else []
            )
            + (
                ["存在多个货币，未换汇并按货币分组"]
                if len(price["groups"]) > 1
                else []
            )
            + (
                ["没有评论标签，评论洞察已降级"]
                if not validated
                else []
            )
        )
    )
    analysis = {
        "schema_version": "1.0",
        "generated_on": today_iso(),
        "layers": {
            "fact": "直接来自上传文件或公共页面",
            "derived": "由确定性脚本计算",
            "inference": "基于证据的建议，需业务验证",
            "unknown": "证据不足，不补写结论",
        },
        "facts": {"products": product_matrix(rows)},
        "derived": {"price": price, "reviews": reviews},
        "inferences": build_inferences(price, reviews),
        "warnings": warnings,
    }
    stable_json_dump(out_path, analysis)
    emit_json(
        {
            "output": str(out_path),
            "distinct_products": len(product_ids),
            "price_currencies": len(price["groups"]),
            "label_records": len(validated),
            "annotated_reviews": reviews["coverage"]["annotated_reviews"],
            "warnings": warnings,
        }
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover
        fail_runtime(str(exc))
