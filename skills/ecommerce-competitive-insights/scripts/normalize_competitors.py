#!/usr/bin/env python3
"""Normalize product and optional review exports into a stable evidence package."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from common import (
    csv_safe,
    emit_json,
    ensure_distinct_paths,
    fail_runtime,
    fail_validation,
    mask_sensitive,
    normalize_currency,
    normalize_date,
    parse_bool,
    parse_integer,
    parse_number,
    read_records,
    safe_output_path,
    sanitize_public_url,
    setup_stdio,
    sha256_file,
    sha256_text,
    stable_json_dump,
    text_value,
    today_iso,
)


PRODUCT_FIELDS = [
    "product_id",
    "brand",
    "product_name",
    "price",
    "currency",
    "platform",
    "url",
    "rating",
    "review_count",
    "collected_at",
    "list_price",
    "category",
    "model",
    "specs",
    "is_own_brand",
    "source_file",
    "source_sha256",
    "source_row",
]


def make_review_id(product_id: str, review_text: str, source_row: int) -> str:
    payload = "{}\n{}\n{}".format(product_id, source_row, review_text)
    return "r-" + sha256_text(payload)[:16]


def safe_review_id(
    candidate: str, product_id: str, review_text: str, source_row: int
) -> tuple[str, bool]:
    if candidate and mask_sensitive(candidate) == candidate:
        return candidate, False
    return make_review_id(product_id, review_text, source_row), bool(candidate)


def normalize_products(
    source_path: Path, rows: List[Dict[str, Any]]
) -> tuple[List[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    normalized: List[Dict[str, Any]] = []
    snapshots: Dict[tuple[str, str], str] = {}
    exact_seen = set()
    source_hash = sha256_file(source_path)

    for index, row in enumerate(rows):
        source_row = int(row.get("__source_row", index + 2))
        path = "$[{}]".format(index)
        product_id = text_value(row.get("product_id"))
        brand = text_value(row.get("brand"))
        product_name = text_value(row.get("product_name"))
        currency_raw = text_value(row.get("currency"))
        currency = normalize_currency(currency_raw)
        price_text = text_value(row.get("price"))
        price = parse_number(price_text)
        url_raw = text_value(row.get("url"))
        url = sanitize_public_url(url_raw)

        for field, value in (
            ("product_id", product_id),
            ("brand", brand),
            ("product_name", product_name),
            ("currency", currency_raw),
        ):
            if not value:
                errors.append("{}.{}: 必填字段为空".format(path, field))
        if currency_raw and currency is None:
            errors.append(
                "{}.currency: 必须是三字母货币代码或受支持货币符号".format(path)
            )
        if price_text and (price is None or price < 0):
            errors.append("{}.price: 必须是非负数或留空表示未知".format(path))
        if url_raw and url is None:
            errors.append(
                "{}.url: 仅允许不含凭据、个人信息和内网地址的公网HTTP/HTTPS地址".format(
                    path
                )
            )
        elif url_raw and url != url_raw:
            warnings.append(
                "product_id={} 的URL已移除查询参数、片段或规范化主机名".format(
                    product_id or "未知"
                )
            )

        rating_text = text_value(row.get("rating"))
        rating = parse_number(rating_text)
        if rating_text and (rating is None or rating < 0 or rating > 5):
            errors.append("{}.rating: 必须在0到5之间".format(path))

        review_count_text = text_value(row.get("review_count"))
        review_count = parse_integer(review_count_text)
        if review_count_text and (review_count is None or review_count < 0):
            errors.append("{}.review_count: 必须是非负整数".format(path))

        list_price_text = text_value(row.get("list_price"))
        list_price = parse_number(list_price_text)
        if list_price_text and (list_price is None or list_price < 0):
            errors.append("{}.list_price: 必须是非负数".format(path))

        collected_raw = text_value(row.get("collected_at"))
        collected_at = normalize_date(collected_raw)
        if collected_raw and collected_at is None:
            errors.append("{}.collected_at: 日期格式无法识别".format(path))
        elif not collected_raw:
            warnings.append(
                "product_id={} 缺少collected_at，仅能作为价格快照，不能生成趋势".format(
                    product_id or "未知"
                )
            )

        if errors and any(item.startswith(path + ".") for item in errors):
            continue

        key = (product_id, collected_at or "")
        price_marker = "" if price is None else "{:.6f}".format(price)
        if key in snapshots and snapshots[key] != price_marker:
            errors.append(
                "{}: 同一product_id和collected_at存在冲突价格".format(path)
            )
            continue
        snapshots[key] = price_marker
        exact_key = (product_id, collected_at or "", price_marker)
        if exact_key in exact_seen:
            warnings.append(
                "忽略完全重复的商品快照: product_id={}, collected_at={}".format(
                    product_id, collected_at or "未知"
                )
            )
            continue
        exact_seen.add(exact_key)

        if price is None:
            warnings.append("product_id={} 的价格未知".format(product_id))
        elif price > 1_000_000_000:
            warnings.append("product_id={} 的价格异常偏高，请核对单位".format(product_id))

        normalized.append(
            {
                "product_id": product_id,
                "brand": mask_sensitive(brand),
                "product_name": mask_sensitive(product_name),
                "price": "" if price is None else "{:.2f}".format(price),
                "currency": currency,
                "platform": mask_sensitive(row.get("platform", "")),
                "url": url or "",
                "rating": "" if rating is None else "{:.2f}".format(rating),
                "review_count": "" if review_count is None else str(review_count),
                "collected_at": collected_at or "",
                "list_price": "" if list_price is None else "{:.2f}".format(list_price),
                "category": mask_sensitive(row.get("category", "")),
                "model": mask_sensitive(row.get("model", "")),
                "specs": mask_sensitive(row.get("specs", "")),
                "is_own_brand": "true" if parse_bool(row.get("is_own_brand")) else "false",
                "source_file": source_path.name,
                "source_sha256": source_hash,
                "source_row": str(source_row),
            }
        )

    if errors:
        fail_validation(errors)
    distinct = sorted({row["product_id"] for row in normalized})
    if not 2 <= len(distinct) <= 20:
        fail_validation(
            [
                "$.product_id: 需包含2到20个不同商品，当前为{}".format(
                    len(distinct)
                )
            ]
        )
    currencies = sorted({row["currency"] for row in normalized if row["currency"]})
    if len(currencies) > 1:
        warnings.append(
            "检测到混合货币{}；MVP不换汇，将按货币分别分析".format(
                "、".join(currencies)
            )
        )
    return normalized, sorted(set(warnings))


def review_evidence(
    source_path: Path,
    rows: List[Dict[str, Any]],
    product_ids: set[str],
) -> tuple[List[Dict[str, Any]], List[str]]:
    errors = []
    warnings = []
    evidence = []
    seen_ids = set()
    injection_markers = (
        "忽略之前",
        "ignore previous",
        "system prompt",
        "执行以下",
        "developer message",
    )
    for index, row in enumerate(rows):
        source_row = int(row.get("__source_row", index + 2))
        path = "$.reviews[{}]".format(index)
        product_id = text_value(row.get("product_id"))
        raw_text = text_value(row.get("review_text"))
        if not product_id:
            errors.append("{}.product_id: 必填字段为空".format(path))
        elif product_id not in product_ids:
            errors.append(
                "{}.product_id: 未在商品表中找到{}".format(path, product_id)
            )
        if not raw_text:
            errors.append("{}.review_text: 必填字段为空".format(path))
        if not product_id or product_id not in product_ids or not raw_text:
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
        masked = mask_sensitive(raw_text)
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
        if any(marker in raw_text.lower() for marker in injection_markers):
            warnings.append(
                "评论{}含疑似指令文本，已按不可信数据处理".format(review_id)
            )
        evidence.append(
            {
                "review_id": review_id,
                "product_id": product_id,
                "review_hash": sha256_text(masked),
                "source_file": source_path.name,
                "source_row": source_row,
                "source_url": source_url or "",
            }
        )
    if errors:
        fail_validation(errors)
    return evidence, sorted(set(warnings))


def write_products(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PRODUCT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_safe(row.get(key, "")) for key in PRODUCT_FIELDS})


def main() -> None:
    setup_stdio()
    parser = argparse.ArgumentParser()
    parser.add_argument("products")
    parser.add_argument("--reviews")
    parser.add_argument("--out", required=True)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()

    products_path, product_rows = read_records(args.products)
    reviews_path = None
    review_rows: List[Dict[str, Any]] = []
    if args.reviews:
        reviews_path, review_rows = read_records(args.reviews)
    out_path = safe_output_path(args.out, {".csv"})
    evidence_path = safe_output_path(args.evidence, {".json"})
    inputs = [products_path] + ([reviews_path] if reviews_path else [])
    ensure_distinct_paths(inputs, [out_path, evidence_path])

    normalized, warnings = normalize_products(products_path, product_rows)
    product_ids = {row["product_id"] for row in normalized}
    review_items = []
    if reviews_path:
        review_items, review_warnings = review_evidence(
            reviews_path, review_rows, product_ids
        )
        warnings.extend(review_warnings)

    write_products(out_path, normalized)
    by_product = defaultdict(int)
    for item in review_items:
        by_product[item["product_id"]] += 1
    evidence = {
        "schema_version": "1.0",
        "generated_on": today_iso(),
        "product_source": products_path.name,
        "review_source": reviews_path.name if reviews_path else None,
        "input_files": [
            {
                "file": products_path.name,
                "role": "products",
                "sha256": sha256_file(products_path),
            }
        ]
        + (
            [
                {
                    "file": reviews_path.name,
                    "role": "reviews",
                    "sha256": sha256_file(reviews_path),
                }
            ]
            if reviews_path
            else []
        ),
        "products": [
            {
                "product_id": row["product_id"],
                "brand": row["brand"],
                "product_name": row["product_name"],
                "facts": {
                    key: row[key]
                    for key in (
                        "price",
                        "currency",
                        "rating",
                        "review_count",
                        "collected_at",
                    )
                },
                "source": {
                    "file": row["source_file"],
                    "row": int(row["source_row"]),
                    "url": row["url"] or None,
                },
            }
            for row in normalized
        ],
        "reviews": review_items,
        "review_counts": dict(sorted(by_product.items())),
        "warnings": sorted(set(warnings)),
    }
    stable_json_dump(evidence_path, evidence)
    emit_json(
        {
            "output": str(out_path),
            "evidence": str(evidence_path),
            "product_snapshots": len(normalized),
            "distinct_products": len(product_ids),
            "reviews_indexed": len(review_items),
            "warnings": sorted(set(warnings)),
        }
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - last-resort contract
        fail_runtime(str(exc))
