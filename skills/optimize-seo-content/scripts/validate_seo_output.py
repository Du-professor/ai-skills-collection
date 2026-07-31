#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_seo_output.py — SEO 结果验证门禁（Schema / 字符数 / 禁用模式 / 截断 / 乱码 / 解析）。

零依赖、零网络、纯标准库。读取完整 SEO JSON，校验必需字段、候选数量、关键词必填字段，
扫描排名保证/虚构搜索量/截断/乱码，回写 validation 块并设 status。

退出码：
  0  通过（status=pass 且无致命项）
  2  字段级错误（打印到 stderr，供模型重试 ≤2 次）
  1  致命（空输入 / JSON 非法）

用法：
  python validate_seo_output.py --input seo.scored.json --output seo.valid.json
"""
import sys
import re
import json
import argparse
from datetime import datetime, timezone

REQUIRED_TOP = ["status", "language", "page_type", "keywords",
                "title_candidates", "meta_candidates",
                "recommended_title", "recommended_meta"]
KW_REQUIRED = ["keyword", "search_intent", "priority", "recommendation_reason"]

FORBIDDEN = [
    (re.compile(r"保证排名|排名第一|排名保证", re.I), "rank_guarantee"),
    (re.compile(r"guaranteed\s+(#?1|rank|top|first)|rank\s+first|#1\s+(on|in)|top\s+of\s+(google|search)", re.I), "rank_guarantee"),
    (re.compile(r"提升\s*\d|流量翻倍|销量翻倍", re.I), "effect_guarantee"),
    (re.compile(r"boost\s+(your\s+)?(traffic|sales|ranking)|double\s+(your\s+)?(traffic|sales)|increase\s+(traffic|sales)\s+by", re.I), "effect_guarantee"),
    (re.compile(r"月搜索量|搜索量\s*\d|日均搜索", re.I), "fabricated_volume"),
    (re.compile(r"search\s+volume|monthly\s+searches|\d+\s*k\s+(searches|monthly)", re.I), "fabricated_volume"),
]
MOJIBAKE = "�"
NUMERIC_CLAIM = re.compile(r"\d+%|认证|授权|certified|authorized|官方指定", re.I)


def err(msg):
    sys.stderr.write("VALIDATION ERROR: " + msg + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="SEO 输出验证门禁（零依赖）")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", help="输出路径（默认 stdout）")
    args = ap.parse_args(argv)

    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        err("输入文件不存在")
        return 1
    except json.JSONDecodeError as e:
        err("JSON 非法: %s" % e)
        return 1

    if not isinstance(data, dict) or not data:
        err("空输入或非对象")
        return 1

    issues = []
    fatal_errors = []  # exit 2 字段级

    # 必需顶层字段
    for f in REQUIRED_TOP:
        if f not in data:
            fatal_errors.append("缺少顶层字段: %s" % f)

    titles = data.get("title_candidates", []) or []
    metas = data.get("meta_candidates", []) or []
    kws = data.get("keywords", []) or []

    if len(titles) < 3:
        fatal_errors.append("title_candidates 数量 %d < 3" % len(titles))
    if len(metas) < 2:
        fatal_errors.append("meta_candidates 数量 %d < 2" % len(metas))

    for i, kw in enumerate(kws):
        if not isinstance(kw, dict):
            fatal_errors.append("keywords[%d] 非对象" % i)
            continue
        for rf in KW_REQUIRED:
            if not (kw.get(rf) or "").strip():
                fatal_errors.append("keywords[%d] 缺少必填字段: %s" % (i, rf))

    # 字符数复算
    for c in titles:
        if isinstance(c, dict) and "title" in c:
            c["character_count"] = len(c.get("title", ""))
    for c in metas:
        if isinstance(c, dict) and "meta_description" in c:
            c["character_count"] = len(c.get("meta_description", ""))

    # 禁用模式扫描
    scan_texts = []
    for c in titles:
        if isinstance(c, dict):
            scan_texts.append(c.get("title", ""))
    for c in metas:
        if isinstance(c, dict):
            scan_texts.append(c.get("meta_description", ""))
    rt = data.get("recommended_title", {}) or {}
    rm = data.get("recommended_meta", {}) or {}
    scan_texts.append(rt.get("title", ""))
    scan_texts.append(rm.get("meta_description", ""))

    found_forbidden = []
    for t in scan_texts:
        for pat, kind in FORBIDDEN:
            if pat.search(t or ""):
                found_forbidden.append(kind)
    if found_forbidden:
        fatal_errors.append("命中禁止表述(排名保证/效果保证/虚构搜索量): %s" % ",".join(sorted(set(found_forbidden))))
        data.setdefault("risks", []).append(
            {"type": "unsupported_claim", "severity": "High",
             "detail": "检测到禁止表述: %s" % ",".join(sorted(set(found_forbidden))),
             "location": "candidates/recommended"})

    # 数值类未核实声明（中等风险，人工复核）
    for t in scan_texts:
        if NUMERIC_CLAIM.search(t or ""):
            data.setdefault("risks", []).append(
                {"type": "unverified_numeric_claim", "severity": "Medium",
                 "detail": "含可能需核实的数值/认证表述，请确认正文支撑", "location": "candidates"})
            break

    # 乱码检测
    blob = json.dumps(data, ensure_ascii=False)
    if MOJIBAKE in blob:
        data.setdefault("risks", []).append(
            {"type": "mojibake", "severity": "Medium",
             "detail": "检测到替换字符(U+FFFD)，可能存在编码乱码", "location": "output"})
        issues.append("mojibake_detected")

    # 截断检测（元描述未以句末标点结尾或以 - 结尾）
    for c in metas:
        m = (c.get("meta_description", "") if isinstance(c, dict) else "")
        if m.rstrip().endswith("-") or (m and not re.search(r"[。.!?！？]$", m.rstrip())):
            issues.append("meta_truncated_or_incomplete")

    # 评分（evaluation-rubric §2）
    structure_ok = len(fatal_errors) == 0
    base = 40 if structure_ok else 0
    cand_scores = [c.get("quality_score", 0) for c in titles + metas if isinstance(c, dict)]
    avg = (sum(cand_scores) / len(cand_scores)) if cand_scores else 0
    score_map = min(40, round(avg * 0.4))
    risks = data.get("risks", [])
    has_high = any(r.get("severity") == "High" for r in risks)
    has_med = any(r.get("severity") == "Medium" for r in risks)
    clean_bonus = 20 if not (has_high or has_med) else (10 if has_med else 0)
    total = base + score_map + clean_bonus
    total = max(0, min(100, total))

    if has_high or found_forbidden:
        data["status"] = "fail"
    elif total >= 80 and structure_ok:
        data["status"] = "pass"
    else:
        data["status"] = "review"

    data["validation"] = {
        "passed": structure_ok and not found_forbidden,
        "score": total,
        "issues": issues,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if fatal_errors:
        for e in fatal_errors:
            err(e)
        # 写回以便模型重试修正
        if args.output:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(data, ensure_ascii=False, indent=2))
        return 2

    out = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(out)
    else:
        sys.stdout.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
