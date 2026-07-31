#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_batch_duplicates.py — 批量页面差异性检查。

零依赖、零网络、纯标准库。输入一组页面记录（数组），检测：
  - 保护字段完全重复（title / meta / h1）
  - 模板归一化重复（仅替换型号/品牌/数字）
  - 关键词蚕食（集合重叠 > 0.6）
  - 开篇相似度（> 0.8）
  - 薄内容（仅替换品牌/型号/数字）

输出判定：Duplicate / Cannibalization Risk / Review / Pass。

支持的输入：
  - 简化页面对象数组：{id,title,meta_description,h1,keywords,opening}
  - 完整 SEO JSON 数组：自动提取 recommended_title/recommended_meta

用法：
  python check_batch_duplicates.py --input pages.json --output batch.json
"""
import sys
import re
import json
import argparse
from difflib import SequenceMatcher

CANON = re.compile(r"\s+")
TOKEN = re.compile(r"[0-9A-Za-z]+")


def norm_text(s):
    return CANON.sub(" ", (s or "").lower()).strip()


def norm_template(s):
    s = (s or "").lower()
    s = TOKEN.sub("X", s)
    s = re.sub(r"[\s\W_]+", " ", s).strip()
    return s


def kw_set(page):
    out = set()
    for k in page.get("keywords", []) or []:
        if isinstance(k, dict):
            out.add((k.get("keyword", "") or "").lower().strip())
        else:
            out.add(str(k).lower().strip())
    out.discard("")
    return out


def extract_page(p):
    if "recommended_title" in p or "title_candidates" in p:
        rt = p.get("recommended_title", {}) or {}
        rm = p.get("recommended_meta", {}) or {}
        return {
            "id": p.get("id", "page"),
            "title": rt.get("title", "") or p.get("title", ""),
            "meta_description": rm.get("meta_description", "") or p.get("meta_description", ""),
            "h1": (p.get("h1") or [""])[0] if isinstance(p.get("h1"), list) else (p.get("h1") or ""),
            "keywords": p.get("keywords", []) or [],
            "opening": p.get("opening", "") or "",
        }
    return {
        "id": p.get("id", "page"),
        "title": p.get("title", "") or "",
        "meta_description": p.get("meta_description", "") or "",
        "h1": p.get("h1", "") or "",
        "keywords": p.get("keywords", []) or [],
        "opening": p.get("opening", "") or "",
    }


def jaccard(a, b):
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def main(argv=None):
    ap = argparse.ArgumentParser(description="批量页面差异检查（零依赖）")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", help="输出路径（默认 stdout）")
    args = ap.parse_args(argv)

    try:
        with open(args.input, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise SystemExit("读取失败: %s" % e)
    if not isinstance(raw, list):
        raise SystemExit("输入应为页面数组")

    pages = [extract_page(p) for p in raw]
    n = len(pages)
    pairs = []
    page_flags = {p["id"]: set() for p in pages}

    if n >= 2:
        for i in range(n):
            for j in range(i + 1, n):
                a, b = pages[i], pages[j]
                issues = []
                # 完全重复
                if norm_text(a["title"]) and norm_text(a["title"]) == norm_text(b["title"]):
                    issues.append("title_duplicate")
                    page_flags[a["id"]].add("Duplicate")
                    page_flags[b["id"]].add("Duplicate")
                if norm_text(a["meta_description"]) and norm_text(a["meta_description"]) == norm_text(b["meta_description"]):
                    issues.append("meta_duplicate")
                    page_flags[a["id"]].add("Duplicate")
                    page_flags[b["id"]].add("Duplicate")
                if norm_text(a["h1"]) and norm_text(a["h1"]) == norm_text(b["h1"]):
                    issues.append("h1_duplicate")
                    page_flags[a["id"]].add("Duplicate")
                    page_flags[b["id"]].add("Duplicate")
                # 模板归一化重复 / 薄内容
                if norm_template(a["title"]) == norm_template(b["title"]) and a["title"] != b["title"]:
                    issues.append("title_template_swap")
                    page_flags[a["id"]].add("Review")
                    page_flags[b["id"]].add("Review")
                # 关键词蚕食
                ov = jaccard(kw_set(a), kw_set(b))
                if ov > 0.6:
                    issues.append("keyword_cannibalization(%.2f)" % ov)
                    page_flags[a["id"]].add("Cannibalization Risk")
                    page_flags[b["id"]].add("Cannibalization Risk")
                # 开篇相似
                if a["opening"] and b["opening"]:
                    sim = SequenceMatcher(None, norm_text(a["opening"]), norm_text(b["opening"])).ratio()
                    if sim > 0.8:
                        issues.append("opening_similarity(%.2f)" % sim)
                        page_flags[a["id"]].add("Review")
                        page_flags[b["id"]].add("Review")
                if issues:
                    pairs.append({"a": a["id"], "b": b["id"], "issues": issues})

    summary = {"Duplicate": 0, "Cannibalization Risk": 0, "Review": 0, "Pass": 0}
    result_pages = []
    for p in pages:
        flags = page_flags[p["id"]]
        if "Duplicate" in flags:
            status = "Duplicate"
        elif "Cannibalization Risk" in flags:
            status = "Cannibalization Risk"
        elif "Review" in flags:
            status = "Review"
        else:
            status = "Pass"
        summary[status] += 1
        result_pages.append({"id": p["id"], "status": status, "flags": sorted(flags)})

    report = {"pages": result_pages, "pairs": pairs, "summary": summary}
    out = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(out)
    else:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
