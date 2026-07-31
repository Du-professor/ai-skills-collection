#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_report.py — 将校验通过的政策解读 JSON 渲染为报告。

输出：
  - 默认自包含 HTML（内联 CSS、零外链、确定性、无时间戳）
  - --format markdown 输出 Markdown 回退
强制注入 references/disclaimer-template.md 中的免责声明与数据隐私说明。

用法：
  python render_report.py --mode summary --input data.json --output report.html
  cat data.json | python render_report.py --mode extract --format markdown
"""
import sys
import json
import argparse
import html as _html

MODE_LABELS = {
    "summary": "政策摘要",
    "extract": "要点提取",
    "compare": "对比分析",
    "qa": "政策问答",
}

DISCLAIMER_HTML = """
<div class="disclaimer">
  <h2>免责声明</h2>
  <p>本解读由人工智能（模型）基于用户<strong>提供的政策原文</strong>自动生成，仅供辅助参考，<strong>不构成任何官方解读、法律意见或行政指导</strong>。政策的理解与适用，请以发布机关正式发布的原文及权威解释为准。人工智能可能存在遗漏、偏差或错误，关键决策前请务必人工复核原文。</p>
  <h2>数据隐私说明</h2>
  <p>本工具仅在用户<strong>本地环境</strong>处理所粘贴或上传的政策文本，不会将其上传至任何外部服务器，也不会用于模型训练之外的用途。请勿在本工具中粘贴涉密、未公开或受保护的特殊敏感文件；如确需处理，请在符合保密规定的可信环境中进行。</p>
</div>
"""

DISCLAIMER_MD = """
> ## 免责声明
> 本解读由人工智能（模型）基于用户**提供的政策原文**自动生成，仅供辅助参考，**不构成任何官方解读、法律意见或行政指导**。政策的理解与适用，请以发布机关正式发布的原文及权威解释为准。人工智能可能存在遗漏、偏差或错误，关键决策前请务必人工复核原文。
>
> ## 数据隐私说明
> 本工具仅在用户**本地环境**处理所粘贴或上传的政策文本，不会将其上传至任何外部服务器，也不会用于模型训练之外的用途。请勿在本工具中粘贴涉密、未公开或受保护的特殊敏感文件；如确需处理，请在符合保密规定的可信环境中进行。
"""


def esc(s):
    s = _html.escape(str(s), quote=True)
    # 额外中和 Markdown 链接/图片语法（[text](url)），防止下游 Markdown 渲染器
    # 把 javascript:/data: 等危险协议激活；用 HTML 实体表示，视觉仍是 [ ] ( )。
    s = s.replace("[", "&#91;").replace("]", "&#93;").replace("(", "&#40;").replace(")", "&#41;")
    return s


def md_esc(s):
    """Markdown 回退报告专用的不可信字段转义。

    目标：消除原文字段注入 Markdown/HTML 渲染器的三类风险：
      1) 原生 HTML 标签（<script>、<img onerror> 等）→ 实体化
      2) Markdown 链接/图片语法 [text](url)（含 javascript:/data: 危险协议）→ 中和
      3) 裸露的 & 被误当作实体 → 优先实体化
    注：表格单元格另用 _md_cell 额外转义竖线，避免破坏表格结构。
    """
    s = str(s)
    # 1) HTML 实体转义（先处理 &，再处理 < >，避免二次转义已生成的实体）
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # 2) 中和 Markdown 链接/图片语法（[ ] ( )），尤其是危险协议 URL
    s = s.replace("[", "\\[").replace("]", "\\]").replace("(", "\\(").replace(")", "\\)")
    return s


def _md_cell(s):
    """表格单元格：在 md_esc 基础上额外转义竖线，避免破坏 GFM 表格。"""
    return md_esc(s).replace("|", "\\|")


def _h(body):
    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>政策解读报告</title>\n<style>\n"
        "body{font-family:-apple-system,'Segoe UI','Microsoft YaHei',sans-serif;"
        "max-width:880px;margin:24px auto;padding:0 16px;color:#1f2933;line-height:1.7;}\n"
        "h1{font-size:24px;border-bottom:3px solid #2b6cb0;padding-bottom:8px;}\n"
        "h2{font-size:19px;color:#2b6cb0;margin-top:28px;}\n"
        ".meta{color:#52606d;font-size:14px;margin-bottom:8px;}\n"
        ".section{border-left:4px solid #cbd5e0;padding:4px 14px;margin:14px 0;background:#f7fafc;}\n"
        "blockquote{background:#fffaf0;border-left:4px solid #dd6b20;margin:8px 0;padding:6px 12px;color:#7b341e;}\n"
        "table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px;}\n"
        "th,td{border:1px solid #cbd5e0;padding:8px 10px;text-align:left;vertical-align:top;}\n"
        "th{background:#ebf4ff;}\n"
        ".cat{margin:14px 0;}\n"
        ".cat h3{margin:6px 0;color:#2b6cb0;font-size:16px;}\n"
        ".point{margin:6px 0 6px 4px;}\n"
        ".disclaimer{margin-top:36px;border-top:2px dashed #a0aec0;padding-top:12px;color:#4a5568;font-size:13px;}\n"
        ".disclaimer h2{color:#718096;font-size:15px;}\n"
        ".not-mentioned{color:#a0aec0;font-style:italic;}\n"
        "</style>\n</head>\n<body>\n" + body + DISCLAIMER_HTML + "\n</body>\n</html>\n"
    )


def render_summary_html(d):
    title = esc(d.get("title", "未明确"))
    meta = []
    if d.get("issued_by"):
        meta.append("发布机关：" + esc(d["issued_by"]))
    if d.get("issued_date"):
        meta.append("发布日期：" + esc(d["issued_date"]))
    meta_html = '<p class="meta">' + " ｜ ".join(meta) + "</p>" if meta else ""
    body = f"<h1>政策摘要：{title}</h1>\n{meta_html}\n"
    for s in d.get("sections", []):
        body += f'<div class="section"><h2>{esc(s.get("heading",""))}</h2><p>{esc(s.get("content",""))}</p></div>\n'
    refs = d.get("source_refs") or []
    if refs:
        body += "<h2>关键原文引用</h2>\n"
        for r in refs:
            body += f"<blockquote>{esc(r)}</blockquote>\n"
    return _h(body)


def render_extract_html(d):
    title = esc(d.get("title", "未明确"))
    body = f"<h1>政策要点提取：{title}</h1>\n"
    for c in d.get("categories", []):
        body += f'<div class="cat"><h3>{esc(c.get("label",""))}（{esc(c.get("category",""))}）</h3>\n'
        for p in c.get("points", []):
            body += (
                f'<div class="point">• {esc(p.get("point",""))}'
                f'<blockquote>{esc(p.get("quote",""))}'
                f'<br><span class="meta">位置：{esc(p.get("location",""))}</span></blockquote></div>\n'
            )
        body += "</div>\n"
    tp = d.get("total_points")
    body += f'<p class="meta">共提取要点 {tp if isinstance(tp,int) else ""} 条。</p>\n'
    return _h(body)


def render_compare_html(d):
    body = "<h1>政策对比分析</h1>\n<table><tr><th>维度</th>"
    policies = d.get("policies", [])
    for p in policies:
        body += f"<th>{esc(p.get('title',''))}<br><span class='meta'>{esc(p.get('issued_by',''))} {esc(p.get('issued_date',''))}</span></th>"
    body += "</tr>\n"
    for dim in d.get("dimensions", []):
        body += f"<tr><th>{esc(dim.get('label',''))}</th>"
        rowmap = {r.get("policy_id"): r.get("value", "") for r in dim.get("rows", [])}
        for p in policies:
            body += f"<td>{esc(rowmap.get(p.get('id'),''))}</td>"
        body += "</tr>\n"
    body += "</table>\n"
    if d.get("diff_summary"):
        body += f"<h2>核心差异总结</h2><p>{esc(d['diff_summary'])}</p>\n"
    if d.get("recommendation"):
        body += f"<h2>适用建议</h2><p>{esc(d['recommendation'])}</p>\n"
    return _h(body)


def render_qa_html(d):
    body = "<h1>政策问答</h1>\n"
    for q in d.get("qa_pairs", []):
        ans = q.get("answer", "")
        not_m = (ans.strip() == "原文未提及")
        ans_cls = ' class="not-mentioned"' if not_m else ""
        body += f"<h2>问：{esc(q.get('question',''))}</h2>\n"
        body += f"<p{ans_cls}>答：{esc(ans)}</p>\n"
        if not not_m:
            for c in q.get("citations", []):
                body += f"<blockquote>{esc(c.get('quote',''))}<br><span class='meta'>位置：{esc(c.get('location',''))}</span></blockquote>\n"
    return _h(body)


RENDERERS_HTML = {
    "summary": render_summary_html,
    "extract": render_extract_html,
    "compare": render_compare_html,
    "qa": render_qa_html,
}


def render_markdown(d, mode):
    title = d.get("title") or (d.get("policies", [{}])[0].get("title", "政策") if mode == "compare" else "政策")
    out = [f"# 政策解读报告 · {MODE_LABELS.get(mode, mode)}", ""]
    if mode == "summary":
        if d.get("issued_by") or d.get("issued_date"):
            out.append(f"> 发布机关：{md_esc(d.get('issued_by',''))} ｜ 发布日期：{md_esc(d.get('issued_date',''))}")
            out.append("")
        for s in d.get("sections", []):
            out.append(f"## {md_esc(s.get('heading',''))}\n\n{md_esc(s.get('content',''))}")
        refs = d.get("source_refs") or []
        if refs:
            out.append("## 关键原文引用")
            for r in refs:
                out.append(f"> {md_esc(r)}")
    elif mode == "extract":
        out.append(f"**政策：{md_esc(title)}**")
        for c in d.get("categories", []):
            out.append(f"### {md_esc(c.get('label',''))}（{md_esc(c.get('category',''))}）")
            for p in c.get("points", []):
                out.append(f"- {md_esc(p.get('point',''))}")
                out.append(f"  > {md_esc(p.get('quote',''))}（位置：{md_esc(p.get('location',''))}）")
        out.append(f"共提取要点 {md_esc(d.get('total_points',''))} 条。")
    elif mode == "compare":
        headers = ["维度"] + [_md_cell(p.get("title", "")) for p in d.get("policies", [])]
        out.append("| " + " | ".join(headers) + " |")
        out.append("|" + "---|" * len(headers))
        for dim in d.get("dimensions", []):
            rowmap = {r.get("policy_id"): r.get("value", "") for r in dim.get("rows", [])}
            row = [_md_cell(dim.get("label", ""))] + [_md_cell(rowmap.get(p.get("id"), "")) for p in d.get("policies", [])]
            out.append("| " + " | ".join(row) + " |")
        if d.get("diff_summary"):
            out.append(f"## 核心差异总结\n\n{md_esc(d['diff_summary'])}")
        if d.get("recommendation"):
            out.append(f"## 适用建议\n\n{md_esc(d['recommendation'])}")
    elif mode == "qa":
        for q in d.get("qa_pairs", []):
            out.append(f"**问：** {md_esc(q.get('question',''))}")
            out.append(f"**答：** {md_esc(q.get('answer',''))}")
            if q.get("answer", "").strip() != "原文未提及":
                for c in q.get("citations", []):
                    out.append(f"> {md_esc(c.get('quote',''))}（位置：{md_esc(c.get('location',''))}）")
    out.append("")
    out.append(DISCLAIMER_MD)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=list(MODE_LABELS))
    ap.add_argument("--input", default=None)
    ap.add_argument("--format", choices=["html", "markdown"], default="html")
    ap.add_argument("--output", default=None, help="输出文件；缺省写 stdout")
    args = ap.parse_args()

    try:
        if args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                raw = f.read()
        else:
            raw = sys.stdin.read()
        data = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        print(f"FATAL: 无法读取/解析输入: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict) or data.get("mode") not in MODE_LABELS:
        # 允许通过 --mode 覆盖，但 data 至少要像样
        pass

    if args.format == "html":
        text = RENDERERS_HTML[args.mode](data)
    else:
        text = render_markdown(data, args.mode)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"已生成报告：{args.output}")
        except Exception as e:  # noqa: BLE001
            print(f"FATAL: 无法写入输出: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
