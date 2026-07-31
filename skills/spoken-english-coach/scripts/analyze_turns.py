#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_turns.py — 确定性口语练习指标计算（纯标准库，离线）

读取模型产出的「带标签转写」JSON，输出指标 JSON。
模型只负责打标签（category 来自 feedback-rubric.md 枚举），本脚本只做计数与算分，
保证评分确定、可复现、无模型漂移。

输入 : --transcript <path> 或 stdin，JSON 结构见 references/output-contract.md §1
输出 : stdout 为指标 JSON（结构见 §2）

退出码:
  0  成功
  2  输入校验失败（stderr 给字段级错误，供模型修复重试 ≤2 次）
  1  意外错误
"""
import sys
import os
import re
import json
import argparse
from datetime import date

# ---- 错误类别枚举（与 feedback-rubric.md §1 完全一致，唯一来源） ----
VALID_CATEGORIES = {
    "grammar-tense", "grammar-article", "grammar-preposition", "grammar-sva",
    "grammar-plural", "grammar-word-order", "vocab-choice", "collocation",
    "chinglish", "spelling", "register-tone", "fluency-filler",
    "fluency-repetition", "pron-hint", "other",
}
VALID_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}

# 高级衔接词信号（用于等级适配度的确定性近似指标）
ADVANCED_MARKERS = {
    "however", "therefore", "although", "though", "nevertheless", "furthermore",
    "whereas", "despite", "in addition", "as a result", "on the other hand",
    "consequently", "moreover", "nonetheless", "admittedly", "meanwhile",
    "subsequently", "hence", "thus", "otherwise",
}
# 各等级基础适配基线（确定性近似）
LEVEL_BASE = {"A1": 0.30, "A2": 0.40, "B1": 0.50, "B2": 0.60, "C1": 0.70, "C2": 0.80}


def fail(msg, code=2):
    sys.stderr.write("VALIDATION ERROR: " + msg + "\n")
    sys.exit(code)


def load_transcript(path):
    if path:
        if not os.path.isfile(path):
            fail("transcript file not found: %s" % path)
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    else:
        raw = sys.stdin.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        fail("invalid JSON: %s" % e)


def tokenize(text):
    """转小写、去标点（保留词内撇号），按空白切分。"""
    if not text:
        return []
    text = text.lower()
    text = re.sub(r"[^a-z0-9'\s]", " ", text)
    return [t for t in text.split() if t]


def split_sentences(text):
    if not text:
        return []
    return [s for s in re.split(r"[.!?]+", text) if s.strip()]


def validate(doc):
    if not isinstance(doc, dict):
        fail("top-level JSON must be an object")
    sess = doc.get("session")
    if not isinstance(sess, dict):
        fail("missing field: session (object)")
    if "level" not in sess:
        fail("missing field: session.level")
    if sess["level"] not in VALID_LEVELS:
        fail("invalid session.level: %r (expected one of %s)" % (sess["level"], sorted(VALID_LEVELS)))
    turns = doc.get("turns")
    if not isinstance(turns, list):
        fail("missing/invalid field: turns (list)")
    for i, t in enumerate(turns):
        if not isinstance(t, dict):
            fail("turns[%d] must be object" % i)
        if t.get("role") != "user":
            continue  # 只校验用户轮；陪练轮忽略
        for j, e in enumerate(t.get("errors", [])):
            if not isinstance(e, dict):
                fail("turns[%d].errors[%d] must be object" % (i, j))
            cat = e.get("category")
            if cat not in VALID_CATEGORIES:
                fail("turns[%d].errors[%d] unknown category: %r (expected one of %s)"
                     % (i, j, cat, sorted(VALID_CATEGORIES)))


def compute(doc):
    sess = doc["session"]
    level = sess["level"]
    turns = doc.get("turns", [])

    user_texts = []
    error_counts = {}
    total_errors = 0
    user_turns = 0
    for t in turns:
        if t.get("role") != "user":
            continue
        user_turns += 1
        user_texts.append(t.get("text", ""))
        for e in t.get("errors", []):
            cat = e.get("category")
            error_counts[cat] = error_counts.get(cat, 0) + 1
            total_errors += 1

    # 自由表达并入语料（用于流利度/多样性）
    fs = doc.get("free_speech") or {}
    fs_text = fs.get("text", "")
    if fs_text:
        user_texts.append(fs_text)

    all_text = " ".join(user_texts)
    tokens = tokenize(all_text)
    total_tokens = len(tokens)
    unique_tokens = len(set(tokens))
    ttr = round(unique_tokens / total_tokens, 4) if total_tokens else 0.0

    sentences = split_sentences(all_text)
    if sentences:
        wlens = [len(tokenize(s)) for s in sentences]
        avg_sentence_len = round(sum(wlens) / len(wlens), 2)
    else:
        avg_sentence_len = 0.0

    # 等级适配度近似：基线 + 高级衔接词数量加权，封顶 1.0
    base = LEVEL_BASE.get(level, 0.50)
    adv_hits = sum(1 for m in ADVANCED_MARKERS if m in all_text)
    level_fit_ratio = round(min(1.0, base + 0.05 * adv_hits), 4)

    # 确定性评分
    user_turns_eff = max(1, user_turns)
    error_rate = total_errors / user_turns_eff  # 每用户轮错误数
    score = 100.0
    score -= min(60.0, error_rate * 30.0)        # 错误越多扣越多，封顶 60
    if ttr < 0.40:
        score -= 10.0
    elif ttr >= 0.60:
        score += 5.0
    score += (level_fit_ratio - 0.5) * 20.0      # -10..+10
    score = max(0.0, min(100.0, round(score, 1)))

    if score >= 90:
        band = "A"
    elif score >= 75:
        band = "B"
    elif score >= 60:
        band = "C"
    elif score >= 40:
        band = "D"
    else:
        band = "E"

    if error_rate >= 1.0:
        difficulty_adjustment = "down"
    elif error_rate <= 0.2:
        difficulty_adjustment = "up"
    else:
        difficulty_adjustment = "steady"

    return {
        "turns": len(turns),
        "user_turns": user_turns,
        "error_counts": error_counts,
        "total_errors": total_errors,
        "ttr": ttr,
        "unique_tokens": unique_tokens,
        "total_tokens": total_tokens,
        "avg_sentence_len": avg_sentence_len,
        "level_fit_ratio": level_fit_ratio,
        "band": band,
        "band_score": score,
        "difficulty_adjustment": difficulty_adjustment,
        "computed_at": date.today().isoformat(),
    }


def main():
    ap = argparse.ArgumentParser(description="Deterministic spoken-English practice metrics.")
    ap.add_argument("--transcript", help="path to tagged transcript JSON (else stdin)")
    args = ap.parse_args()
    doc = load_transcript(args.transcript)
    validate(doc)
    result = compute(doc)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # 意外错误
        sys.stderr.write("UNEXPECTED ERROR: %s\n" % e)
        sys.exit(1)
