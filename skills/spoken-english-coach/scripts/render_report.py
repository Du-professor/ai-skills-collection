#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_report.py — 渲染自包含 HTML 会话报告（纯标准库，离线）

读取 指标 JSON（analyze_turns.py）+ 进度 JSON（progress_store.py），可选 transcript（含纠错示例），
渲染一份自包含 HTML 报告（内联 CSS，无任何外部网络请求）。同时向 stdout 输出 Markdown 回退版，
保证即便 HTML 写出失败，Skill 仍能拿到报告内容。

输入 : --analysis <path> (必需)
       --progress <path> (可选；缺省为空档案)
       --transcript <path> (可选；用于错误示例)
       --out <path> (可选；HTML 写出路径)
输出 : stdout 为 Markdown 报告；HTML 写入 --out（若提供）

退出码: 0 成功 | 1 意外错误
"""
import sys
import os
import json
import argparse
import html

BAND_DESC = {
    "A": "流利准确，偶有瑕疵",
    "B": "能顺畅沟通，局部需打磨",
    "C": "可理解，但错误影响表达",
    "D": "基础薄弱，多处影响理解",
    "E": "起步阶段，需大量支持",
}
CATEGORY_LABEL = {
    "grammar-tense": "时态", "grammar-article": "冠词", "grammar-preposition": "介词",
    "grammar-sva": "主谓一致", "grammar-plural": "单复数", "grammar-word-order": "语序",
    "vocab-choice": "用词不准", "collocation": "搭配", "chinglish": "中式英语",
    "spelling": "拼写", "register-tone": "语域/语气", "fluency-filler": "填充词过多",
    "fluency-repetition": "重复单调", "pron-hint": "发音文本近似提示", "other": "其他",
}
DISCLAIMER = ("免责声明：本报告为口语练习反馈，非专业语言测评，不用于任何正式考试判定；"
              "发音相关项仅为文本近似提示（音近词混淆提示），不代表真实发音评测。")


def load_json(path, default=None):
    if not path or not os.path.isfile(path):
        return default if default is not None else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def esc(s):
    return html.escape(str(s), quote=True)


def esc_md(s):
    """Markdown 转义：去换行、转义 \\ ` * _ [ ] |，防止用户内容破坏 Markdown 表格/列表。"""
    s = str(s).replace("\r", "").replace("\n", " ")
    for ch in ("\\", "`", "*", "_", "[", "]", "|"):
        s = s.replace(ch, "\\" + ch)
    return s


def top3_improve(analysis, progress):
    """生成 Top3 改进项：优先常错类别（跨会话）+ 当次高频。"""
    items = []
    ep = (progress or {}).get("error_profile", {})
    # 跨会话常错（按累计次数）
    for cat, rec in sorted(ep.items(), key=lambda kv: kv[1].get("count", 0), reverse=True)[:2]:
        items.append("巩固「%s」：历史累计 %d 次，建议针对性练习。" %
                     (CATEGORY_LABEL.get(cat, cat), rec.get("count", 0)))
    # 当次高频
    ec = analysis.get("error_counts", {})
    if ec:
        top_cat = max(ec.items(), key=lambda kv: kv[1])[0]
        items.append("本场重点：「%s」出现 %d 次，先集中攻克。" %
                     (CATEGORY_LABEL.get(top_cat, top_cat), ec[top_cat]))
    while len(items) < 3:
        items.append("保持当前练习节奏，逐步提升句式变化与词汇多样性。")
    return items[:3]


def section_summary(analysis, progress):
    a = analysis
    return ("本次练习 %d 个用户轮次，确定性评分 **%s（%s 分）**——%s。\n"
            "词汇多样性 TTR=%.2f，平均句长 %.1f 词，等级适配度 %.2f。"
            % (a.get("user_turns", 0), a.get("band", "-"), a.get("band_score", 0),
               BAND_DESC.get(a.get("band"), ""), a.get("ttr", 0), a.get("avg_sentence_len", 0),
               a.get("level_fit_ratio", 0)))


def section_errors(analysis, transcript):
    ec = analysis.get("error_counts", {})
    if not ec:
        return "_本场未发现明显错误，保持得很好。_"
    lines = ["| 类别 | 次数 |", "|------|------|"]
    for cat, cnt in sorted(ec.items(), key=lambda kv: kv[1], reverse=True):
        lines.append("| %s | %d |" % (CATEGORY_LABEL.get(cat, cat), cnt))
    md = "\n".join(lines)
    # 示例（来自 transcript）
    if transcript:
        ex = []
        for t in transcript.get("turns", []):
            if t.get("role") != "user":
                continue
            for e in t.get("errors", []):
                ex.append("- 「%s」→ 建议：%s（%s）"
                          % (esc_md(e.get("user_phrase", "")), esc_md(e.get("better", "")), esc_md(e.get("why", ""))))
        if ex:
            md += "\n\n示例：\n" + "\n".join(ex[:6])
    return md


def section_next(progress):
    rf = (progress or {}).get("recommended_focus", {}) or {}
    cat = rf.get("category")
    topic = rf.get("topic")
    if not cat and not topic:
        return "暂无足够历史数据，下次可任选感兴趣话题继续练习。"
    parts = []
    if cat:
        parts.append("重点攻克「%s」" % CATEGORY_LABEL.get(cat, cat))
    if topic:
        parts.append("围绕「%s」场景多练" % topic)
    return "下次针对性练习建议：" + "；".join(parts) + "。"


def build_markdown(analysis, progress, transcript):
    lines = []
    lines.append("# 英语口语陪练 · 会话报告")
    lines.append("")
    lines.append(section_summary(analysis, progress))
    lines.append("\n## 错误分类\n")
    lines.append(section_errors(analysis, transcript))
    lines.append("\n## 强项\n")
    st = (progress or {}).get("strong_topics", []) or []
    if st:
        lines.append("你已在以下话题表现稳定：**%s**。" % "、".join(esc_md(t) for t in st))
    else:
        lines.append("继续积累，强项会随着练习逐渐显现。")
    lines.append("\n## Top 3 改进项\n")
    for i, it in enumerate(top3_improve(analysis, progress), 1):
        lines.append("%d. %s" % (i, it))
    lines.append("\n## 个性化下一步\n")
    lines.append(section_next(progress))
    lines.append("\n## 进度快照\n")
    lines.append("- 累计会话：%d 次" % (progress or {}).get("total_sessions", 0))
    bh = (progress or {}).get("band_history", []) or []
    if bh:
        lines.append("- 近期档位：" + " → ".join(bh[-5:]))
    lines.append("\n> " + DISCLAIMER)
    return "\n".join(lines)


def build_html(analysis, progress, transcript):
    md_summary = section_summary(analysis, progress)
    errors_md = section_errors(analysis, transcript)
    strong = (progress or {}).get("strong_topics", []) or []
    if strong:
        strong_html = "你已在以下话题表现稳定：<b>%s</b>。" % esc("、".join(strong))
    else:
        strong_html = "继续积累，强项会逐渐显现。"
    top3 = "\n".join("<li>%s</li>" % esc(x) for x in top3_improve(analysis, progress))
    next_md = section_next(progress)
    total_sessions = (progress or {}).get("total_sessions", 0)
    bh = (progress or {}).get("band_history", []) or []
    snap = "<li>累计会话：<b>%d</b> 次</li>" % total_sessions
    if bh:
        snap += "<li>近期档位：<b>%s</b></li>" % esc(" → ".join(bh[-5:]))

    # 错误表
    ec = analysis.get("error_counts", {})
    if ec:
        rows = "".join("<tr><td>%s</td><td>%d</td></tr>" %
                       (esc(CATEGORY_LABEL.get(c, c)), n)
                       for c, n in sorted(ec.items(), key=lambda kv: kv[1], reverse=True))
        err_table = '<table><tr><th>类别</th><th>次数</th></tr>%s</table>' % rows
        ex_html = ""
        if transcript:
            exs = []
            for t in transcript.get("turns", []):
                if t.get("role") != "user":
                    continue
                for e in t.get("errors", []):
                    exs.append("<li>「%s」 → 建议：<b>%s</b>（%s）</li>"
                               % (esc(e.get("user_phrase", "")), esc(e.get("better", "")), esc(e.get("why", ""))))
            if exs:
                ex_html = "<h3>示例</h3><ul>%s</ul>" % "\n".join(exs[:6])
        errors_block = err_table + ex_html
    else:
        errors_block = "<p>本场未发现明显错误，保持得很好。</p>"

    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>英语口语陪练 · 会话报告</title>
<style>
  body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;max-width:820px;margin:24px auto;padding:0 18px;color:#1f2328;background:#fff;line-height:1.6}
  h1{font-size:22px;border-bottom:3px solid #2f6fed;padding-bottom:8px}
  h2{font-size:18px;margin-top:26px;color:#2f6fed}
  h3{font-size:15px;margin-bottom:6px}
  .band{display:inline-block;background:#2f6fed;color:#fff;border-radius:6px;padding:2px 10px;font-weight:600}
  table{border-collapse:collapse;width:100%%;margin:10px 0}
  th,td{border:1px solid #d0d7de;padding:6px 10px;text-align:left}
  th{background:#f3f5f8}
  ul,ol{margin:6px 0 6px 20px}
  .box{background:#f6f8fa;border:1px solid #d0d7de;border-radius:8px;padding:12px 16px;margin:10px 0}
  .disc{font-size:13px;color:#57606a;border-top:1px dashed #d0d7de;margin-top:24px;padding-top:10px}
  .muted{color:#57606a}
</style></head><body>
<h1>英语口语陪练 · 会话报告</h1>
<div class="box"><span class="band">%s · %s 分</span> &nbsp;<span class="muted">%s</span>
<p>%s</p></div>
<h2>错误分类</h2>
%s
<h2>强项</h2>
<p>%s</p>
<h2>Top 3 改进项</h2>
<ol>%s</ol>
<h2>个性化下一步</h2>
<p>%s</p>
<h2>进度快照</h2>
<ul>%s</ul>
<p class="disc">%s</p>
</body></html>""" % (
        esc(analysis.get("band", "-")), esc(analysis.get("band_score", 0)),
        esc(BAND_DESC.get(analysis.get("band"), "")), esc(md_summary),
        errors_block, strong_html, top3, esc(next_md), snap, esc(DISCLAIMER),
    )


def main():
    ap = argparse.ArgumentParser(description="Render spoken-English practice report.")
    ap.add_argument("--analysis", required=True, help="analysis JSON from analyze_turns.py")
    ap.add_argument("--progress", help="progress JSON from progress_store.py")
    ap.add_argument("--transcript", help="tagged transcript JSON (for error examples)")
    ap.add_argument("--out", help="output HTML path")
    args = ap.parse_args()

    analysis = load_json(args.analysis, {})
    progress = load_json(args.progress, None)
    if progress is None:
        progress = {"version": 1, "total_sessions": 0, "error_profile": {}, "weak_topics": {},
                    "strong_topics": [], "ttr_history": [], "band_history": [], "recommended_focus": {}}
    transcript = load_json(args.transcript, None)

    md = build_markdown(analysis, progress, transcript)
    sys.stdout.write(md + "\n")

    html_doc = build_html(analysis, progress, transcript)
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(html_doc)
            sys.stderr.write("REPORT_HTML: %s\n" % args.out)
        except OSError as e:
            sys.stderr.write("WARNING: cannot write HTML (%s); Markdown fallback above.\n" % e)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write("UNEXPECTED ERROR: %s\n" % e)
        sys.exit(1)
