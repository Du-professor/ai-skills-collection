#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
progress_store.py — 跨会话个性化记忆（纯标准库，离线）

读取单次练习的「指标 JSON」（来自 analyze_turns.py），与本地进度档案合并，
更新常错点 / 薄弱话题 / 趋势，并写出合并后的进度档案 JSON。
不可写时优雅降级：返回空档案（total_sessions:0）+ stderr warning，exit 0，不中断 Skill。

输入 : --merge <analysis.json path> 或 stdin（指标 JSON，结构见 output-contract.md §2）
       --progress <existing progress path>（可选，覆盖默认路径）
       --out <path>（可选，写出合并后档案；默认仍写默认路径）
输出 : stdout 为合并后的进度 JSON（结构见 output-contract.md §3）

退出码: 0 成功（含降级成功） | 1 意外错误
"""
import sys
import os
import json
import argparse
from datetime import date


def progress_path(override=None):
    if override:
        return override
    # 优先可写的应用数据目录；均不可用时退回临时目录
    candidates = []
    if os.name == "nt":
        app = os.environ.get("APPDATA")
        if app:
            candidates.append(os.path.join(app, "spoken-english-coach"))
    candidates.append(os.path.join(os.path.expanduser("~"), ".local", "share", "spoken-english-coach"))
    candidates.append(os.path.join(os.path.expanduser("~"), ".spoken-english-coach"))
    candidates.append(os.path.join(sys.prefix, "var", "spoken-english-coach"))
    for c in candidates:
        try:
            os.makedirs(c, exist_ok=True)
            # 探测可写
            probe = os.path.join(c, ".write_test")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
            return os.path.join(c, "progress.json")
        except OSError:
            continue
    # 实在不行：临时目录（会话级，重启可能丢失）
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "spoken-english-coach")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "progress.json")


def safe_override_path(p):
    """校验覆盖路径：拒绝 '..' 穿越；绝对路径必须落在用户主目录/APPDATA/临时目录内。
    非法时返回 None，调用方将降级使用默认进度路径。"""
    if not p:
        return None
    norm = os.path.normpath(p)
    if ".." in norm.replace("\\", "/").split("/"):
        sys.stderr.write("WARNING: 拒绝路径穿越的覆盖路径 (%s)，改用默认进度路径\n" % p)
        return None
    if os.path.isabs(norm):
        roots = []
        app = os.environ.get("APPDATA")
        if app:
            roots.append(os.path.abspath(app))
        roots.append(os.path.abspath(os.path.expanduser("~")))
        try:
            import tempfile
            roots.append(os.path.abspath(tempfile.gettempdir()))
        except Exception:
            pass
        absp = os.path.abspath(norm)
        if not any(absp == r or absp.startswith(r + os.sep) for r in roots):
            sys.stderr.write("WARNING: 绝对路径超出安全根目录 (%s)，改用默认进度路径\n" % p)
            return None
        return absp
    return norm


def empty_profile():
    return {
        "version": 1,
        "updated_at": date.today().isoformat(),
        "total_sessions": 0,
        "error_profile": {},
        "weak_topics": {},
        "strong_topics": [],
        "ttr_history": [],
        "band_history": [],
        "recommended_focus": {"category": None, "topic": None},
    }


def load_existing(path):
    if not os.path.isfile(path):
        return empty_profile()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return empty_profile()
        # 补全缺失键，保证向前兼容
        base = empty_profile()
        base.update(data)
        for k, v in empty_profile().items():
            base.setdefault(k, v)
        return base
    except (json.JSONDecodeError, OSError):
        return empty_profile()


def recommended_focus(prof):
    ep = prof.get("error_profile", {})
    wt = prof.get("weak_topics", {})
    top_cat = max(ep.items(), key=lambda kv: kv[1].get("count", 0))[0] if ep else None
    top_topic = max(wt.items(), key=lambda kv: kv[1])[0] if wt else None
    return {"category": top_cat, "topic": top_topic}


def merge(analysis, profile):
    today = date.today().isoformat()
    profile["updated_at"] = today
    profile["total_sessions"] = profile.get("total_sessions", 0) + 1

    # 错误档案累计
    ep = profile.setdefault("error_profile", {})
    for cat, cnt in (analysis.get("error_counts") or {}).items():
        rec = ep.setdefault(cat, {"count": 0, "last_seen": today})
        rec["count"] = rec.get("count", 0) + cnt
        rec["last_seen"] = today

    # 话题强弱
    topic = (analysis.get("session") or {}).get("topic") if "session" in analysis else None
    topic = topic or (analysis.get("topic"))
    band = analysis.get("band")
    if topic:
        wt = profile.setdefault("weak_topics", {})
        # 表现 weak（C/D/E）计为薄弱
        if analysis.get("band_score", 100) < 75:
            wt[topic] = wt.get(topic, 0) + 1
        if band in ("A", "B"):
            st = profile.setdefault("strong_topics", [])
            if topic not in st:
                st.append(topic)

    # 趋势
    if "ttr" in analysis:
        profile.setdefault("ttr_history", []).append(analysis["ttr"])
    if band:
        profile.setdefault("band_history", []).append(band)

    profile["recommended_focus"] = recommended_focus(profile)
    return profile


def main():
    ap = argparse.ArgumentParser(description="Merge session metrics into progress profile.")
    ap.add_argument("--merge", help="path to analysis JSON (else stdin)")
    ap.add_argument("--progress", help="existing progress JSON path (override default)")
    ap.add_argument("--out", help="write merged profile to this path")
    args = ap.parse_args()

    raw = None
    if args.merge:
        if not os.path.isfile(args.merge):
            sys.stderr.write("WARNING: merge file not found: %s; using empty profile\n" % args.merge)
            analysis = empty_profile_mergeable()
        else:
            with open(args.merge, "r", encoding="utf-8") as f:
                raw = f.read()
    else:
        raw = sys.stdin.read()
    if raw is not None:
        try:
            analysis = json.loads(raw)
        except json.JSONDecodeError as e:
            sys.stderr.write("WARNING: invalid analysis JSON (%s); using empty profile\n" % e)
            analysis = {}
    else:
        analysis = {}

    path = progress_path(safe_override_path(args.progress))
    profile = load_existing(path)
    try:
        profile = merge(analysis, profile)
    except Exception as e:
        sys.stderr.write("WARNING: merge failed (%s); returning existing profile\n" % e)

    out = safe_override_path(args.out) or path
    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
    except OSError as e:
        # 降级：不写文件，但仍在 stdout 返回档案，Skill 继续
        sys.stderr.write("WARNING: cannot write progress file (%s); degraded to in-memory only\n" % e)

    sys.stdout.write(json.dumps(profile, ensure_ascii=False, indent=2) + "\n")


def empty_profile_mergeable():
    return {"error_counts": {}, "band": None, "band_score": 100, "ttr": 0.0, "session": {}}


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write("UNEXPECTED ERROR: %s\n" % e)
        sys.exit(1)
