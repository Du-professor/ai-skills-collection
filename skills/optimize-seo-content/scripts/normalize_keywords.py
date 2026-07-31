#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
normalize_keywords.py — 关键词去重、聚类、语言识别与枚举归一。

零依赖、零网络、纯标准库。读取完整 SEO JSON（含 keywords[]），
归一化后回写完整 JSON；若输入为纯数组则仅回写数组。

用法：
  python normalize_keywords.py --input seo.json --output seo.norm.json
  python normalize_keywords.py --input keywords.json   # 纯数组
"""
import sys
import re
import json
import argparse

CJK_RE = re.compile(r"[一-鿿]")
PUNCT_RE = re.compile(r"[\s\W_]+", flags=re.UNICODE)

CATS = {"primary", "secondary", "long_tail", "question"}
INTENTS = {"informational", "comparison", "commercial_investigation",
           "transactional", "navigational"}
FUNNELS = {"awareness", "consideration", "decision"}
RELEV = {"High", "Medium", "Low"}
EVID = {"measured", "trend_signal", "observable_phrase", "model_inference"}
PRIO = {"High", "Medium", "Low"}
PLACE = {"title", "h1", "body", "faq", "alt", "internal_link"}
PRIO_RANK = {"High": 3, "Medium": 2, "Low": 1}
CAT_ORDER = {"primary": 0, "secondary": 1, "long_tail": 2, "question": 3}


def detect_lang(token):
    if not token.strip():
        return "en-US"
    cjk = len(CJK_RE.findall(token))
    return "zh-CN" if (cjk / max(1, len(token.strip()))) >= 0.3 else "en-US"


def signature(token):
    """近义聚类签名：去标点、小写、CJK 去空格。"""
    t = token.strip().lower()
    if CJK_RE.search(t):
        t = re.sub(r"\s+", "", t)
    return PUNCT_RE.sub(" ", t).strip()


def normalize_one(kw, risks):
    if not isinstance(kw, dict):
        return None
    k = (kw.get("keyword") or "").strip()
    if not k:
        return None
    out = dict(kw)
    out["keyword"] = k
    lang = (out.get("language") or "auto").strip()
    if lang not in ("zh-CN", "en-US"):
        lang = detect_lang(k)
    out["language"] = lang

    cat = (out.get("category") or "secondary").lower()
    if cat not in CATS:
        risks.append({"type": "invalid_enum", "severity": "Low",
                      "detail": "keyword.category 非法已修正: %r" % out.get("category"),
                      "location": "keywords"})
        cat = "secondary"
    out["category"] = cat

    si = (out.get("search_intent") or "informational").lower()
    if si not in INTENTS:
        si = "informational"
        risks.append({"type": "invalid_enum", "severity": "Low",
                      "detail": "search_intent 非法已修正", "location": "keywords"})
    out["search_intent"] = si

    fn = (out.get("funnel_stage") or "consideration").lower()
    if fn not in FUNNELS:
        fn = "consideration"
    out["funnel_stage"] = fn

    rel = (out.get("relevance") or "Medium")
    if rel not in RELEV:
        rel = "Medium"
    out["relevance"] = rel

    ev = (out.get("evidence") or "model_inference").lower()
    if ev not in EVID:
        ev = "model_inference"
    out["evidence"] = ev

    pr = (out.get("priority") or "Medium")
    if pr not in PRIO:
        pr = "Medium"
    out["priority"] = pr

    pl = (out.get("recommended_placement") or "body").lower()
    if pl not in PLACE:
        pl = "body"
    out["recommended_placement"] = pl

    out["risk_note"] = out.get("risk_note") or ""
    out["recommendation_reason"] = out.get("recommendation_reason") or ""
    return out


def normalize_keywords(keywords, risks):
    seen = {}
    order = []
    for kw in keywords:
        n = normalize_one(kw, risks)
        if n is None:
            continue
        sig = signature(n["keyword"])
        lang = n["language"]
        key = (sig, lang)
        if key in seen:
            # 保留优先级更高者
            if PRIO_RANK[n["priority"]] > PRIO_RANK[seen[key]["priority"]]:
                seen[key] = n
            continue
        seen[key] = n
        order.append(key)
    result = [seen[k] for k in order]
    # 排序：category 顺序 -> priority 降序
    result.sort(key=lambda x: (CAT_ORDER.get(x["category"], 9),
                               -PRIO_RANK.get(x["priority"], 0)))
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="关键词归一化（零依赖）")
    ap.add_argument("--input", required=True, help="SEO JSON 或关键词数组")
    ap.add_argument("--output", help="输出路径（默认 stdout）")
    args = ap.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    risks = []
    if isinstance(data, list):
        normalized = normalize_keywords(data, risks)
        payload = normalized
    elif isinstance(data, dict):
        kws = data.get("keywords", [])
        normalized = normalize_keywords(kws, risks)
        data["keywords"] = normalized
        if risks:
            data.setdefault("risks", [])
            data["risks"].extend(risks)
        payload = data
    else:
        raise SystemExit("输入应为 JSON 对象或数组")

    out = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(out)
    else:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
