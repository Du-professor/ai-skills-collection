#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
score_seo_candidates.py — 对标题与元描述候选做确定性评分并选择推荐项。

零依赖、零网络、纯标准库。读取完整 SEO JSON，依据
references/title-and-meta-standard.md 的权重矩阵计算 quality_score，
选择 recommended_title / recommended_meta，回写完整 JSON。

注意：**模型禁出分数**；本脚本是唯一计算 quality_score 的地方。

用法：
  python score_seo_candidates.py --input seo.json --output seo.scored.json
"""
import sys
import re
import json
import argparse

CJK_RE = re.compile(r"[一-鿿]")
PRIO_RANK = {"Low": 0, "Medium": 1, "High": 2}

CTA_VALID = {"none", "learn_more", "shop_now", "contact", "download", "subscribe"}

FORBIDDEN = [
    (re.compile(r"保证排名|排名第一|排名保证", re.I), "rank_guarantee"),
    (re.compile(r"guaranteed\s+(#?1|rank|top|first)|rank\s+first|#1\s+(on|in)|top\s+of\s+(google|search)", re.I), "rank_guarantee"),
    (re.compile(r"提升\s*\d|流量翻倍|销量翻倍", re.I), "effect_guarantee"),
    (re.compile(r"boost\s+(your\s+)?(traffic|sales|ranking)|double\s+(your\s+)?(traffic|sales)|increase\s+(traffic|sales)\s+by", re.I), "effect_guarantee"),
    (re.compile(r"月搜索量|搜索量\s*\d|日均搜索", re.I), "fabricated_volume"),
    (re.compile(r"search\s+volume|monthly\s+searches|\d+\s*k\s+(searches|monthly)", re.I), "fabricated_volume"),
]


def scan_forbidden(text):
    hits = []
    for pat, kind in FORBIDDEN:
        if pat.search(text or ""):
            if kind not in hits:
                hits.append(kind)
    return hits


def detect_lang(text):
    if not text.strip():
        return "en-US"
    cjk = len(CJK_RE.findall(text))
    return "zh-CN" if (cjk / max(1, len(text.strip()))) >= 0.3 else "en-US"


def in_band(count, lang, kind):
    if kind == "title":
        lo, hi = (20, 30) if lang == "zh-CN" else (50, 60)
    else:
        lo, hi = (50, 80) if lang == "zh-CN" else (140, 160)
    return lo <= count <= hi


def band_center(lang, kind):
    if kind == "title":
        return 25 if lang == "zh-CN" else 55
    return 65 if lang == "zh-CN" else 150


def count_occurrences(haystack, needle):
    if not needle:
        return 0
    return haystack.lower().count(needle.lower())


def score_title(c, risks):
    title = c.get("title", "") or ""
    c["character_count"] = len(title)
    forb = scan_forbidden(title)
    diff = c.get("differentiation") if c.get("differentiation") in ("Low", "Medium", "High") else "Medium"
    claim = c.get("claim_risk") if c.get("claim_risk") in ("Low", "Medium", "High") else "Low"

    if forb:
        c["claim_risk"] = "High"
        c["quality_score"] = 0
        risks.append({"type": "unsupported_claim", "severity": "High",
                      "detail": "标题命中禁止表述: %s" % ",".join(forb), "location": "title_candidates"})
        return 0

    pk = c.get("primary_keyword", "") or ""
    pres = 20 if (pk and pk.lower() in title.lower()) else 5
    diff_score = {"High": 10, "Medium": 6, "Low": 2}[diff]
    sub_relevance = pres + diff_score  # 30

    sub_intent = 20 if (c.get("search_intent") or "").strip() else 5  # 20

    words = [w for w in re.split(r"\s+", title) if w]
    caps = sum(1 for w in words if len(w) > 1 and w.isupper())
    caps_ratio = (caps / len(words)) if words else 0
    punct = len(re.findall(r"[!?！？，。]", title))
    sub_clarity = 15
    if caps_ratio > 0.5:
        sub_clarity -= 8
    if punct > 3:
        sub_clarity -= 7
    sub_clarity = max(0, sub_clarity)  # 15

    occ = count_occurrences(title, pk)
    sub_natural = {0: 5, 1: 15, 2: 10}.get(occ, 3)  # 15 (occ>2 堆砌)

    sub_diff = {"High": 10, "Medium": 6, "Low": 2}[diff]  # 10

    sub_safety = {"Low": 10, "Medium": 5, "High": 0}[claim]  # 10

    raw = sub_relevance + sub_intent + sub_clarity + sub_natural + sub_diff + sub_safety
    if claim == "High":
        raw -= 15
    score = max(0, min(100, round(raw)))
    c["quality_score"] = score
    c["claim_risk"] = claim
    return score


def score_meta(c, risks):
    meta = c.get("meta_description", "") or ""
    c["character_count"] = len(meta)
    forb = scan_forbidden(meta)
    claim = c.get("claim_risk") if c.get("claim_risk") in ("Low", "Medium", "High") else "Low"
    lang = detect_lang(meta)

    if forb:
        c["claim_risk"] = "High"
        c["quality_score"] = 0
        risks.append({"type": "unsupported_claim", "severity": "High",
                      "detail": "元描述命中禁止表述: %s" % ",".join(forb), "location": "meta_candidates"})
        return 0

    # 内容准确性 30
    if meta.rstrip().endswith("-") or (meta and not re.search(r"[。.!?！？]$", meta.rstrip())):
        sub_acc = 10  # 截断/不完整句
    elif in_band(len(meta), lang, "meta"):
        sub_acc = 30
    else:
        sub_acc = 15
    # 关键词覆盖 20
    ik = c.get("included_keyword", "") or ""
    sub_kw = 20 if (ik and ik.lower() in meta.lower()) else 5
    # 价值主张 15
    sub_val = 15 if (c.get("value_proposition") or "").strip() else 3
    # CTA 合理 10
    cta = c.get("cta_type", "none")
    if cta not in CTA_VALID:
        cta = "none"
        sub_cta = 3
    else:
        sub_cta = 10
    c["cta_type"] = cta
    # 清晰度 15
    words = [w for w in re.split(r"\s+", meta) if w]
    caps = sum(1 for w in words if len(w) > 1 and w.isupper())
    caps_ratio = (caps / len(words)) if words else 0
    punct = len(re.findall(r"[!?！？，。]", meta))
    sub_clar = 15
    if caps_ratio > 0.5:
        sub_clar -= 8
    if punct > 3:
        sub_clar -= 7
    sub_clar = max(0, sub_clar)
    # 安全 10
    sub_safe = {"Low": 10, "Medium": 5, "High": 0}[claim]

    raw = sub_acc + sub_kw + sub_val + sub_cta + sub_clar + sub_safe
    if claim == "High":
        raw -= 15
    score = max(0, min(100, round(raw)))
    c["quality_score"] = score
    c["claim_risk"] = claim
    return score


def select_best(cands, kind, risks):
    if not cands:
        return {}
    best = max(cands, key=lambda c: (c.get("quality_score", 0),
                                     PRIO_RANK.get(c.get("claim_risk", "Low"), 0)))
    score = best.get("quality_score", 0)
    reason = "选取 quality_score 最高（%d）的候选" % score
    if score < 50:
        reason += "；候选质量偏低，建议人工润色"
    if kind == "title":
        return {"title": best.get("title", ""), "selection_reason": reason,
                "quality_score": score}
    return {"meta_description": best.get("meta_description", ""), "selection_reason": reason,
            "quality_score": score}


def main(argv=None):
    ap = argparse.ArgumentParser(description="标题/元描述确定性评分（零依赖）")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", help="输出路径（默认 stdout）")
    args = ap.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    risks = data.get("risks", [])
    titles = data.get("title_candidates", [])
    metas = data.get("meta_candidates", [])
    for c in titles:
        score_title(c, risks)
    for c in metas:
        score_meta(c, risks)

    data["title_candidates"] = titles
    data["meta_candidates"] = metas
    data["recommended_title"] = select_best(titles, "title", risks)
    data["recommended_meta"] = select_best(metas, "meta", risks)
    data["risks"] = risks

    # 候选质量偏低则降级为 review
    best_t = max([c.get("quality_score", 0) for c in titles], default=0)
    best_m = max([c.get("quality_score", 0) for c in metas], default=0)
    if data.get("status") == "pass" and (best_t < 50 or best_m < 50):
        data["status"] = "review"

    out = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(out)
    else:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
