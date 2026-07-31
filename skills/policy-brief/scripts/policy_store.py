#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
policy_store.py — 跨会话政策记忆（本机 JSON 档案）。

记录已解读政策的元信息（不含原文正文）与用户关注领域，支持连续对比与
自动针对关注方向。结构见 references/policy-schema.md。

用法：
  python policy_store.py --action record --title "..." --domain fiscal_tax \
      --date 2025-01-01 --policy-hash ab12 --modes summary,extract
  python policy_store.py --action query
  python policy_store.py --action record --store-path /path/profile.json ...

退出码：
  0  成功（含降级：返回 degraded 档案，不中断主流程）
  1  参数或致命错误（仅在不该发生的调用错误时）
"""
import sys
import os
import json
import argparse
import tempfile

DEFAULT_STORE = os.path.join(
    os.path.expanduser("~"), ".workbuddy", "policy-brief", "profile.json"
)

POLICY_DOMAINS = {
    "tech_innovation", "industry", "fiscal_tax", "talent_employment",
    "livelihood", "agriculture", "ecology", "opening_up", "other",
}

EMPTY_PROFILE = {
    "version": 1,
    "policies": [],
    "focus_counts": {},
    "recommended_focus": None,
}

DEGRADED_PROFILE = {
    "degraded": True,
    "policies": [],
    "focus_counts": {},
    "recommended_focus": None,
}


def safe_path(p):
    """路径穿越防护：仅允许落在用户主目录 / APPDATA / 临时目录下。"""
    try:
        ap = os.path.abspath(os.path.expanduser(p))
    except Exception:  # noqa: BLE001
        return None
    roots = [os.path.abspath(os.path.expanduser("~"))]
    apdata = os.environ.get("APPDATA")
    if apdata:
        roots.append(os.path.abspath(apdata))
    roots.append(os.path.abspath(tempfile.gettempdir()))
    if any(ap == r or ap.startswith(r + os.sep) for r in roots):
        return ap
    return None


def _recompute_focus(profile):
    counts = {}
    for p in profile.get("policies", []):
        d = p.get("domain", "other")
        counts[d] = counts.get(d, 0) + 1
    profile["focus_counts"] = counts
    if counts:
        # 取计数最高；并列时取字母序首个，保证确定性
        profile["recommended_focus"] = sorted(
            counts.items(), key=lambda kv: (-kv[1], kv[0])
        )[0][0]
    else:
        profile["recommended_focus"] = None


def load_profile(store_path):
    if not os.path.exists(store_path):
        return dict(EMPTY_PROFILE)
    try:
        with open(store_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return dict(EMPTY_PROFILE)
        data.setdefault("version", 1)
        data.setdefault("policies", [])
        data.setdefault("focus_counts", {})
        data.setdefault("recommended_focus", None)
        return data
    except Exception:  # noqa: BLE001
        return dict(EMPTY_PROFILE)


def record(args):
    store_path = safe_path(args.store_path or DEFAULT_STORE)
    if store_path is None:
        print(json.dumps(DEGRADED_PROFILE, ensure_ascii=False))
        return 0
    try:
        profile = load_profile(store_path)
        h = args.policy_hash or ""
        modes = [m for m in (args.modes or "").split(",") if m]
        domain = args.domain if args.domain in POLICY_DOMAINS else "other"
        existing = next((p for p in profile["policies"] if p.get("hash") == h and h), None)
        if existing:
            existing["title"] = args.title or existing.get("title", "")
            existing["domain"] = domain
            if args.date:
                existing["date"] = args.date
            existing["modes"] = sorted(set(existing.get("modes", []) + modes))
            existing["interpreted_at"] = _now()
        else:
            profile["policies"].append({
                "title": args.title or "未命名政策",
                "domain": domain,
                "date": args.date or "未明确",
                "hash": h,
                "interpreted_at": _now(),
                "modes": sorted(modes),
            })
        _recompute_focus(profile)
        os.makedirs(os.path.dirname(store_path), exist_ok=True)
        with open(store_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        print(json.dumps(profile, ensure_ascii=False))
        return 0
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"policy_store 降级：{e}\n")
        print(json.dumps(DEGRADED_PROFILE, ensure_ascii=False))
        return 0


def query(args):
    store_path = safe_path(args.store_path or DEFAULT_STORE)
    if store_path is None:
        print(json.dumps(DEGRADED_PROFILE, ensure_ascii=False))
        return 0
    try:
        profile = load_profile(store_path)
        print(json.dumps(profile, ensure_ascii=False))
        return 0
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"policy_store 降级：{e}\n")
        print(json.dumps(DEGRADED_PROFILE, ensure_ascii=False))
        return 0


def _now():
    # 仅用于记录，确定性非必需；使用本地时间字符串
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", required=True, choices=["record", "query"])
    ap.add_argument("--store-path", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--domain", default="other")
    ap.add_argument("--date", default=None)
    ap.add_argument("--policy-hash", default=None)
    ap.add_argument("--modes", default="")
    args = ap.parse_args()

    if args.action == "record":
        return record(args)
    return query(args)


if __name__ == "__main__":
    sys.exit(main())
