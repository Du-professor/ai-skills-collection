#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preference_store.py — 跨会话长期偏好 JSON 的读写。

隐私默认：默认不持久保存；仅当用户显式 --consent 时才写本机文件；--clear 可清除。
不可写时降级返回空档案不中断；含路径穿越防护（拒绝 '..' 与允许根外的绝对路径）。
唯一来源：references/preference-schema.md。

退出码：0（含降级）/ 1 意外。
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import date

EMPTY = {
    "version": 1, "updated_at": "", "budget_tier": "", "budget_currency": "CNY",
    "frequent_cities": [], "dietary_restrictions": [], "companion_types": [],
    "interest_tags": [], "preferred_transport": [], "avoid": [],
    "last_destinations": [], "recommended_next": {"destination": None, "reason": None},
}

# 兴趣 → 推荐城市（用于 recommended_next，基于计数，非评分）
INTEREST_CITY = {
    "美食": "成都", "自然": "桂林", "历史": "西安", "购物": "上海", "亲子": "广州",
    "摄影": "丽江", "夜生活": "重庆", "休闲": "杭州", "文化": "南京", "冒险": "昆明",
}


def candidate_paths():
    paths = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(os.path.join(appdata, "personalized-travel-planner"))
    home = os.path.expanduser("~")
    if home:
        paths.append(os.path.join(home, ".local", "share", "personalized-travel-planner"))
        paths.append(os.path.join(home, ".config", "personalized-travel-planner"))
    paths.append(os.path.join(tempfile.gettempdir(), "personalized-travel-planner"))
    return paths


def _safe_override(override):
    """路径穿越防护：拒绝 '..'；绝对路径须落在 用户主目录/APPDATA/临时目录 内。"""
    home = os.path.expanduser("~")
    appdata = os.environ.get("APPDATA")
    tmp = tempfile.gettempdir()
    allowed_roots = [p for p in (home, appdata, tmp) if p]
    norm_parts = override.replace("\\", "/").split("/")
    if ".." in norm_parts:
        sys.stderr.write("WARNING: path traversal '..' rejected, using default\n")
        return None
    if os.path.isabs(override):
        abs_override = os.path.abspath(override)
        if not any(abs_override.startswith(os.path.abspath(r)) for r in allowed_roots):
            sys.stderr.write("WARNING: absolute path outside allowed roots, using default\n")
            return None
    return override


def find_existing():
    # 读取：仅查找已有文件，绝不创建目录（避免无谓的持久化副作用）
    for p in candidate_paths():
        fp = os.path.join(p, "preferences.json")
        if os.path.exists(fp):
            return fp
    return None


def read_path(override=None):
    if override:
        ov = _safe_override(override)
        if ov:
            return ov
    existing = find_existing()
    if existing:
        return existing
    cands = candidate_paths()
    return os.path.join(cands[0], "preferences.json") if cands else None


def writable_path(override=None):
    # 仅真正落盘时调用：挑第一个可写目录并创建
    if override:
        ov = _safe_override(override)
        if ov:
            return ov
    for p in candidate_paths():
        try:
            os.makedirs(p, exist_ok=True)
            probe = os.path.join(p, ".writetest")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            return os.path.join(p, "preferences.json")
        except Exception:
            continue
    tmp = tempfile.gettempdir()
    os.makedirs(os.path.join(tmp, "personalized-travel-planner"), exist_ok=True)
    return os.path.join(tmp, "personalized-travel-planner", "preferences.json")


def load_profile(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None


def empty_profile():
    e = dict(EMPTY)
    e["recommended_next"] = {"destination": None, "reason": None}
    return e


def merge_profile(base, inc):
    p = dict(base) if isinstance(base, dict) else empty_profile()
    for k in ("budget_tier", "budget_currency", "companion_types"):
        if inc.get(k) not in (None, "", []):
            p[k] = inc[k]
    for k in ("frequent_cities", "dietary_restrictions", "interest_tags", "preferred_transport", "avoid"):
        if isinstance(inc.get(k), list):
            cur = list(p.get(k, []))
            for v in inc[k]:
                if v not in cur:
                    cur.append(v)
            p[k] = cur[-8:]
    if isinstance(inc.get("last_destinations"), list):
        cur = list(p.get("last_destinations", []))
        for v in inc["last_destinations"]:
            if v in cur:
                cur.remove(v)
            cur.insert(0, v)
        p["last_destinations"] = cur[:6]
    interests = p.get("interest_tags", [])
    visited = set(p.get("frequent_cities", [])) | set(p.get("last_destinations", []))
    rec = None
    reason = None
    for it in interests:
        c = INTEREST_CITY.get(it)
        if c and c not in visited:
            rec = c
            reason = "基于兴趣「%s」推荐" % it
            break
    p["recommended_next"] = {"destination": rec, "reason": reason}
    p["version"] = 1
    p["updated_at"] = date.today().isoformat()
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--read", action="store_true", help="输出当前偏好档案到 stdout（不写盘）")
    ap.add_argument("--merge", help="增量 JSON 路径，或 - 读 stdin；合并（需 --consent 才落盘）")
    ap.add_argument("--consent", action="store_true",
                    help="明确同意跨会话持久保存；缺省时 --merge 仅返回本次会话内合并结果，不写本机文件")
    ap.add_argument("--clear", action="store_true", help="删除本机偏好文件，清除所有跨会话记忆")
    ap.add_argument("--out", help="（保留兼容）覆盖输出路径（受限路径）")
    ap.add_argument("--preferences", help="覆盖默认偏好路径（受限路径，含路径穿越防护）")
    args = ap.parse_args()

    # 防止 Windows GBK 控制台打印含中文时 UnicodeEncodeError
    for _s in (sys.stdout, sys.stderr):
        try:
            if hasattr(_s, "reconfigure"):
                _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if args.clear:
        target = args.preferences or read_path()
        try:
            if target and os.path.exists(target):
                os.remove(target)
                sys.stderr.write("cleared preference file: %s\n" % target)
            else:
                sys.stderr.write("no preference file to clear\n")
        except Exception as e:
            sys.stderr.write("clear failed: %s\n" % e)
        sys.exit(0)

    if args.read:
        path = read_path(args.preferences)
        prof = load_profile(path) if (path and os.path.exists(path)) else None
        if prof is None:
            sys.stderr.write("WARNING: preference file missing/unreadable, returning empty profile\n")
            prof = empty_profile()
        print(json.dumps(prof, ensure_ascii=False, indent=2))
        sys.exit(0)

    if args.merge is not None:
        # 默认不持久保存：无 --consent 时仅在本次会话内合并并返回，不写盘
        path = writable_path(args.preferences) if args.consent else read_path(args.preferences)
        base = load_profile(path) if (path and os.path.exists(path)) else empty_profile()
        try:
            if args.merge == "-":
                inc = json.loads(sys.stdin.read())
            else:
                with open(args.merge, "r", encoding="utf-8") as f:
                    inc = json.load(f)
        except Exception as e:
            sys.stderr.write("ERROR reading merge input: %s\n" % e)
            sys.exit(1)
        merged = merge_profile(base, inc if isinstance(inc, dict) else {})
        if args.consent:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(merged, f, ensure_ascii=False, indent=2)
            except Exception as e:
                sys.stderr.write("WARNING: cannot write preference file (%s); returning in-memory profile only\n" % e)
        else:
            sys.stderr.write("NOTE: preferences NOT saved (opt-in required). Pass --consent to persist across sessions.\n")
        print(json.dumps(merged, ensure_ascii=False, indent=2))
        sys.exit(0)

    sys.stderr.write("ERROR: specify --read / --merge / --clear\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
