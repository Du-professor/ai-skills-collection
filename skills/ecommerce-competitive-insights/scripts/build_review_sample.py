#!/usr/bin/env python3
"""Build a deterministic, privacy-masked review sample for controlled labeling."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Deque, Dict, List

from common import (
    emit_json,
    ensure_distinct_paths,
    fail_runtime,
    fail_validation,
    mask_sensitive,
    normalize_date,
    parse_integer,
    parse_number,
    read_records,
    safe_input_path,
    safe_output_path,
    sanitize_public_url,
    setup_stdio,
    sha256_text,
    stable_json_dump,
    text_value,
    today_iso,
)
from normalize_competitors import safe_review_id


def read_products(path: Path) -> Dict[str, Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"product_id", "brand", "product_name"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            fail_validation(
                ["$: normalized.csv缺少字段: {}".format(
                    "、".join(sorted(required - set(reader.fieldnames or [])))
                )]
            )
        products = {}
        for row in reader:
            product_id = text_value(row.get("product_id"))
            if product_id and product_id not in products:
                products[product_id] = row
    if not products:
        fail_validation(["$: normalized.csv没有商品"])
    return products


def rating_bucket(rating: Any) -> str:
    value = parse_number(rating)
    if value is None:
        return "unknown"
    if value <= 2:
        return "negative"
    if value < 4:
        return "neutral"
    return "positive"


def prepare_reviews(
    source_path: Path,
    rows: List[Dict[str, Any]],
    products: Dict[str, Dict[str, str]],
) -> tuple[List[Dict[str, Any]], List[str]]:
    errors = []
    warnings = []
    prepared = []
    seen_ids = set()
    for index, row in enumerate(rows):
        source_row = int(row.get("__source_row", index + 2))
        path = "$[{}]".format(index)
        product_id = text_value(row.get("product_id"))
        raw_text = text_value(row.get("review_text"))
        if not product_id:
            errors.append("{}.product_id: 必填字段为空".format(path))
        elif product_id not in products:
            errors.append(
                "{}.product_id: 未在normalized.csv中找到{}".format(path, product_id)
            )
        if not raw_text:
            errors.append("{}.review_text: 必填字段为空".format(path))
        if not product_id or product_id not in products or not raw_text:
            continue
        review_id, replaced_sensitive_id = safe_review_id(
            text_value(row.get("review_id")), product_id, raw_text, source_row
        )
        if replaced_sensitive_id:
            warnings.append(
                "评论行{}的review_id可能包含个人信息，已替换为稳定匿名ID".format(
                    source_row
                )
            )
        if review_id in seen_ids:
            errors.append("{}.review_id: 重复ID {}".format(path, review_id))
            continue
        seen_ids.add(review_id)
        rating_raw = text_value(row.get("rating"))
        rating = parse_number(rating_raw)
        if rating_raw and (rating is None or rating < 0 or rating > 5):
            errors.append("{}.rating: 必须在0到5之间".format(path))
            continue
        date_raw = text_value(row.get("review_date"))
        review_date = normalize_date(date_raw)
        if date_raw and review_date is None:
            warnings.append(
                "review_id={} 日期无法识别，抽样时按未知日期处理".format(review_id)
            )
        masked_text = mask_sensitive(raw_text)
        source_url_raw = text_value(row.get("source_url"))
        source_url = sanitize_public_url(source_url_raw)
        if source_url_raw and source_url is None:
            errors.append(
                "{}.source_url: 仅允许不含凭据、个人信息和内网地址的公网HTTP/HTTPS地址".format(
                    path
                )
            )
            continue
        if source_url_raw and source_url != source_url_raw:
            warnings.append(
                "评论{}的source_url已移除查询参数、片段或规范化主机名".format(
                    review_id
                )
            )
        prepared.append(
            {
                "record_type": "review",
                "review_id": review_id,
                "product_id": product_id,
                "brand": products[product_id].get("brand", ""),
                "product_name": products[product_id].get("product_name", ""),
                "review_text": masked_text,
                "review_hash": sha256_text(masked_text),
                "rating": rating,
                "rating_bucket": rating_bucket(rating),
                "review_date": review_date,
                "source_url": source_url or "",
                "source_file": source_path.name,
                "source_row": source_row,
                "helpful_count": parse_integer(row.get("helpful_count")),
                "variant": mask_sensitive(row.get("variant", "")),
                "annotations": [],
            }
        )
    if errors:
        fail_validation(errors)
    return prepared, sorted(set(warnings))


def sample_reviews(
    reviews: List[Dict[str, Any]], max_total: int, max_per_product: int
) -> List[Dict[str, Any]]:
    by_product: Dict[str, Dict[str, Deque[Dict[str, Any]]]] = defaultdict(
        lambda: {
            "negative": deque(),
            "neutral": deque(),
            "positive": deque(),
            "unknown": deque(),
        }
    )
    for item in sorted(
        reviews,
        key=lambda row: (
            row["product_id"],
            row["review_date"] or "",
            row["review_id"],
        ),
        reverse=True,
    ):
        by_product[item["product_id"]][item["rating_bucket"]].append(item)

    per_product: Dict[str, Deque[Dict[str, Any]]] = {}
    bucket_order = ("negative", "positive", "neutral", "unknown")
    for product_id in sorted(by_product):
        selected: List[Dict[str, Any]] = []
        buckets = by_product[product_id]
        while len(selected) < max_per_product and any(buckets[name] for name in bucket_order):
            for name in bucket_order:
                if buckets[name] and len(selected) < max_per_product:
                    selected.append(buckets[name].popleft())
        per_product[product_id] = deque(selected)

    result = []
    product_ids = sorted(per_product)
    while len(result) < max_total and any(per_product[key] for key in product_ids):
        for product_id in product_ids:
            if per_product[product_id] and len(result) < max_total:
                result.append(per_product[product_id].popleft())
    return result


def main() -> None:
    setup_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("normalized")
    parser.add_argument("--reviews", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-total", type=int, default=800)
    parser.add_argument("--max-per-product", type=int, default=80)
    args = parser.parse_args()

    if not 1 <= args.max_total <= 5000:
        fail_validation(["$.max_total: 必须在1到5000之间"])
    if not 1 <= args.max_per_product <= 500:
        fail_validation(["$.max_per_product: 必须在1到500之间"])

    normalized_path = safe_input_path(args.normalized, {".csv"})
    reviews_path, review_rows = read_records(args.reviews)
    out_path = safe_output_path(args.out, {".json"})
    ensure_distinct_paths([normalized_path, reviews_path], [out_path])

    products = read_products(normalized_path)
    reviews, warnings = prepare_reviews(reviews_path, review_rows, products)
    sampled = sample_reviews(reviews, args.max_total, args.max_per_product)

    available = defaultdict(int)
    selected = defaultdict(int)
    for row in reviews:
        available[row["product_id"]] += 1
    for row in sampled:
        selected[row["product_id"]] += 1
    metadata = {
        "record_type": "meta",
        "schema_version": "1.0",
        "generated_on": today_iso(),
        "strategy": "按商品轮询；商品内按负向、正向、中性、未知评分桶分层并优先较新评论",
        "total_available": len(reviews),
        "total_sampled": len(sampled),
        "max_total": args.max_total,
        "max_per_product": args.max_per_product,
        "per_product": {
            product_id: {
                "available": available[product_id],
                "sampled": selected[product_id],
            }
            for product_id in sorted(products)
        },
        "warnings": warnings,
    }
    stable_json_dump(
        out_path,
        {
            "schema_version": "1.0",
            "meta": metadata,
            "reviews": sampled,
        },
    )

    emit_json(
        {
            "output": str(out_path),
            "total_available": len(reviews),
            "total_sampled": len(sampled),
            "coverage": (
                round(len(sampled) / len(reviews), 6) if reviews else 0
            ),
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
