#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seo_store.py — 跨会话 SEO 优化记忆（品牌 / 常优化页面类型 / 薄弱点）。

零依赖、零网络、纯标准库。仅存本机元信息，不存正文。
含路径穿越防护；不可写时静默降级（exit 0 + 空档案），不中断主流程。

用法：
  python seo_store.py --action record --brand "Acme" --page-type product --weak-area "meta_length"
  python seo_store.py --action query
  python seo_store.py --action record --store-path /custom/path.json ...
"""
import sys
import os
import json
import argparse

DEFAULT_STORE = os.path.join(
    os.path.expanduser("~"), ".workbuddy", "optimize-seo-content-memory.json"
)


def safe_path(p):
    """路径穿越防护：仅允许本机用户目录下绝对路径或相对文件名。"""
    p = os.path.abspath(os.path.expanduser(p))
    home = os.path.abspath(os.path.expanduser("~"))
    allowed = [home.replace("\\", "/"),
               os.path.join(home, ".workbuddy").replace("\\", "/")]
    if not any(p.replace("\\", "/").startswith(a) for a in allowed):
        return None
    if ".." in p.replace("\\", "/").split("/"):
        return None
    return p


def load(store):
    try:
        if os.path.isfile(store):
            with open(store, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:
        pass
    return {"brands": [], "page_types": [], "weak_areas": [], "history": []}


def save(store, data):
    try:
        os.makedirs(os.path.dirname(store), exist_ok=True)
        with open(store, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def record(store, brand, page_type, weak_area):
    data = load(store)
    if brand and brand not in data["brands"]:
        data["brands"].append(brand)
    if page_type and page_type not in data["page_types"]:
        data["page_types"].append(page_type)
    if weak_area and weak_area not in data["weak_areas"]:
        data["weak_areas"].append(weak_area)
    data["history"].append({"brand": brand, "page_type": page_type, "weak_area": weak_area})
    if not save(store, data):
        sys.stderr.write("记忆写入失败，已降级跳过（不中断）\n")
        return
    sys.stdout.write(json.dumps({"ok": True, "stored": bool(brand or page_type or weak_area)},
                                ensure_ascii=False) + "\n")


def query(store):
    data = load(store)
    focus = []
    if data["weak_areas"]:
        focus.append("建议重点关注历史薄弱点: " + "、".join(data["weak_areas"][-3:]))
    if data["page_types"]:
        focus.append("常见优化页面类型: " + "、".join(data["page_types"]))
    if data["brands"]:
        focus.append("已知品牌: " + "、".join(data["brands"]))
    if not focus:
        focus.append("暂无历史记忆，按通用 SEO 规范处理")
    sys.stdout.write(json.dumps({"recommended_focus": focus}, ensure_ascii=False) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="跨会话 SEO 记忆（零依赖）")
    ap.add_argument("--action", required=True, choices=["record", "query"])
    ap.add_argument("--brand")
    ap.add_argument("--page-type")
    ap.add_argument("--weak-area")
    ap.add_argument("--store-path", default=DEFAULT_STORE)
    args = ap.parse_args(argv)

    sp = safe_path(args.store_path)
    if sp is None:
        sys.stderr.write("路径不合规，已降级（不写入）\n")
        if args.action == "query":
            sys.stdout.write(json.dumps({"recommended_focus": ["路径不合规，按通用规范处理"]}, ensure_ascii=False) + "\n")
        return
    if args.action == "record":
        record(sp, args.brand, args.page_type, args.weak_area)
    else:
        query(sp)


if __name__ == "__main__":
    main()
