#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_report.py — 将 SEO JSON 渲染为多格式报告。

零依赖、零网络、纯标准库。支持：
  markdown（默认） / json / html（自包含、零外链、确定性、注入免责声明+隐私）
  / docx（zipfile 生成最小 OOXML） / csv（关键词批量表）

用法：
  python render_report.py --input seo.valid.json --format markdown --output report.md
  python render_report.py --input seo.valid.json --format html    --output report.html
  python render_report.py --input seo.valid.json --format docx    --output report.docx
  python render_report.py --input seo.valid.json --format csv     --output keywords.csv
"""
import sys
import os
import re
import json
import argparse
import csv
import io

DISCLAIMER = ("免责声明：本报告由 SEO 内容优化工具自动生成，所有关键词与标题建议均基于用户提供的页面内容，"
              "未使用任何搜索量实测数据，不构成搜索排名或流量保证。请以实际业务与人工复核为准。")
PRIVACY = ("数据隐私：本工具不保存登录凭证、Cookie 或个人身份信息；处理过程不上传原文至外部服务。")


def md_esc(s):
    """Markdown 注入防护：对所有不可信（模型/用户可控）字段统一转义。

    处理 < > ! ( ) [ ] ` | 反斜杠 换行，并中和 javascript: 链接（大小写/空白均可）。
    设计要点（顺序不可调换）：
      1) 先实体化 & < >，中和 <script>/<img> 等原始 HTML 标签；
      2) 再 defang javascript: 协议（避免下游 Markdown 渲染器激活链接），
         此步在 & 转义之后进行，避免 &#58; 被二次编码；
      3) 中和 Markdown 标记符号（链接/图片 [ ] ( )、强调 * _、标题 #、代码 `、表格 |、图片 !、转义符 \\）；
      4) 字段内换行压成空格，避免破坏列表/段落结构。
    """
    s = str(s if s is not None else "")
    # 1) HTML 实体转义，中和原始标签
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # 2) defang javascript: 链接（置于 & 转义之后，避免 &#58; 被二次编码）
    s = re.sub(r"(?i)javascript\s*:", "javascript&#58;", s)
    # 3) 中和 Markdown 标记符号
    for ch in ("\\", "`", "*", "_", "[", "]", "(", ")", "|", "!", "#"):
        s = s.replace(ch, "\\" + ch)
    # 4) 换行压成空格
    s = s.replace("\r", " ").replace("\n", " ")
    return s


def cell(s):
    # Markdown 表格单元格注入防护：复用 md_esc（已覆盖 | \ ` * _ [ ] ( ) ! 等），并去掉首尾空白
    return md_esc(s).strip()


def csv_cell(s):
    # CSV 公式注入防护：以 = + - @ 开头的单元格在表格软件中会被当作公式执行
    s = str(s if s is not None else "")
    if s and s[0] in "=+-@":
        s = "'" + s
    return s


def html_escape(s):
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def xml_escape(s):
    return (str(s if s is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


# ---------------- Markdown ----------------
def render_markdown(data):
    L = []
    L.append("# SEO 内容优化报告\n")
    # 1
    L.append("## 1. 执行摘要")
    L.append("- 状态：`%s`" % md_esc(data.get("status", "n/a")))
    L.append("- 语言：%s" % md_esc(data.get("language", "n/a")))
    L.append("- 页面类型：%s" % md_esc(data.get("page_type", "n/a")))
    L.append("- 推荐 SEO 标题：%s" % md_esc((data.get("recommended_title", {}) or {}).get("title", "—")))
    L.append("- 推荐元描述：%s" % md_esc((data.get("recommended_meta", {}) or {}).get("meta_description", "—")))
    v = data.get("validation", {}) or {}
    L.append("- 质量评分：%s" % md_esc(v.get("score", "n/a")))
    L.append("")
    # 2
    inp = data.get("input_summary", {}) or {}
    L.append("## 2. 输入与页面类型")
    L.append("- 来源类型：%s" % md_esc(inp.get("source_type", "n/a")))
    L.append("- 正文长度：%s 字符" % md_esc(inp.get("char_count", "n/a")))
    if inp.get("assumptions"):
        L.append("- 假设：%s" % md_esc("；".join(inp["assumptions"])))
    if inp.get("evidence_insufficient"):
        L.append("- 证据不足：是（关键词数量已受限）")
    L.append("")
    # 3
    si = data.get("search_intent", {}) or {}
    L.append("## 3. 搜索意图分析")
    L.append("- 主要意图：%s" % md_esc(si.get("primary_intent", "n/a")))
    L.append("- 次要意图：%s" % md_esc(si.get("secondary_intent") or "无"))
    L.append("- 决策阶段：%s" % md_esc(si.get("decision_stage", "n/a")))
    L.append("- 意图匹配度：%s" % md_esc(si.get("match_level", "n/a")))
    if si.get("content_gaps"):
        L.append("- 内容缺口：" + md_esc("；".join(si["content_gaps"])))
    if si.get("suggested_modules"):
        L.append("- 建议模块：" + md_esc("；".join(si["suggested_modules"])))
    L.append("")
    # 4
    L.append("## 4. SEO 关键词推荐")
    L.append("| 关键词 | 语言 | 类型 | 意图 | 阶段 | 相关性 | 证据 | 优先级 | 投放 | 理由 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for k in data.get("keywords", []):
        L.append("| " + " | ".join(cell(x) for x in [
            k.get("keyword"), k.get("language"), k.get("category"), k.get("search_intent"),
            k.get("funnel_stage"), k.get("relevance"), k.get("evidence"), k.get("priority"),
            k.get("recommended_placement"), k.get("recommendation_reason")]) + " |")
    L.append("")
    # 5
    L.append("## 5. 现有标题诊断")
    diag = data.get("title_diagnosis")
    if diag:
        if isinstance(diag, dict):
            for kk, vv in diag.items():
                L.append("- %s：%s" % (md_esc(kk), md_esc(vv)))
        else:
            L.append("- %s" % md_esc(diag))
    else:
        L.append("- 未提供现有标题，跳过诊断（如需审计请提供当前标题）。")
    L.append("")
    # 6
    L.append("## 6. 优化标题候选")
    L.append("| # | 标题 | 字符数 | 主关键词 | 意图 | 差异化 | 风险 | 评分 | 理由 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for i, c in enumerate(data.get("title_candidates", []), 1):
        L.append("| %d | %s |" % (i, cell(c.get("title"))) + " | ".join(cell(x) for x in [
            c.get("character_count"), c.get("primary_keyword"), c.get("search_intent"),
            c.get("differentiation"), c.get("claim_risk"), c.get("quality_score"),
            c.get("recommendation_reason")]) + " |")
    L.append("")
    # 7
    rt = data.get("recommended_title", {}) or {}
    L.append("## 7. 推荐 SEO 标题")
    L.append("- **%s**" % md_esc(rt.get("title") or "—"))
    L.append("- 选择理由：%s" % md_esc(rt.get("selection_reason") or "—"))
    L.append("- 评分：%s" % md_esc(rt.get("quality_score", "n/a")))
    L.append("")
    # 8
    L.append("## 8. 元描述候选")
    L.append("| # | 元描述 | 字符数 | 覆盖意图 | 含关键词 | 价值主张 | CTA | 风险 | 评分 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for i, c in enumerate(data.get("meta_candidates", []), 1):
        L.append("| %d | %s |" % (i, cell(c.get("meta_description"))) + " | ".join(cell(x) for x in [
            c.get("character_count"), c.get("covered_intent"), c.get("included_keyword"),
            c.get("value_proposition"), c.get("cta_type"), c.get("claim_risk"),
            c.get("quality_score")]) + " |")
    L.append("")
    # 9
    rm = data.get("recommended_meta", {}) or {}
    L.append("## 9. 推荐元描述")
    L.append("- **%s**" % md_esc(rm.get("meta_description") or "—"))
    L.append("- 选择理由：%s" % md_esc(rm.get("selection_reason") or "—"))
    L.append("- 评分：%s" % md_esc(rm.get("quality_score", "n/a")))
    L.append("")
    # 10
    L.append("## 10. 内容缺口建议")
    for g in data.get("content_gaps", []) or []:
        if isinstance(g, dict):
            L.append("- %s：%s" % (md_esc(g.get("module", "缺口")), md_esc(g.get("reason", ""))))
        else:
            L.append("- %s" % md_esc(g))
    if not data.get("content_gaps"):
        L.append("- 无明显内容缺口。")
    L.append("")
    # 11
    L.append("## 11. 关键词投放指引")
    by_place = {}
    for k in data.get("keywords", []):
        by_place.setdefault(k.get("recommended_placement", "body"), []).append(k.get("keyword"))
    for place, kws in by_place.items():
        L.append("- **%s**：%s" % (md_esc(place), md_esc("、".join(kws))))
    L.append("")
    # 12
    L.append("## 12. 重复与蚕食检查")
    bc = data.get("batch_check")
    if bc:
        L.append("- 汇总：%s" % md_esc(json.dumps(bc.get("summary", {}), ensure_ascii=False)))
        for p in bc.get("pages", []):
            L.append("- %s：%s" % (md_esc(p.get("id")), md_esc(p.get("status"))))
    else:
        L.append("- 单页面分析，无批量重复/蚕食检查。")
    L.append("")
    # 13
    L.append("## 13. 合规与声明风险")
    for r in data.get("risks", []) or []:
        L.append("- [%s/%s] %s（%s）" % (md_esc(r.get("severity")), md_esc(r.get("type")),
                                        md_esc(r.get("detail")), md_esc(r.get("location"))))
    if not data.get("risks"):
        L.append("- 无高风险合规项。")
    L.append("")
    # 14
    L.append("## 14. 验证结果")
    L.append("- 通过：%s" % md_esc(v.get("passed", "n/a")))
    L.append("- 评分：%s" % md_esc(v.get("score", "n/a")))
    if v.get("issues"):
        L.append("- 提示：%s" % md_esc("；".join(v["issues"])))
    L.append("")
    # 15
    L.append("## 15. 局限与待核查")
    L.append("- 未使用搜索量实测工具，所有推荐不含搜索量数值或\"高搜索量\"断言。")
    L.append("- 无网络时仅基于用户提供内容分析（Content-only Mode）。")
    L.append("- 含 Medium/High 风险项须经人工复核后再发布。")
    L.append("- " + DISCLAIMER)
    L.append("- " + PRIVACY)
    return "\n".join(L) + "\n"


# ---------------- HTML ----------------
def render_html(data):
    def sec(n, title):
        return '<section><h2>%d. %s</h2>' % (n, html_escape(title))

    parts = ['<!DOCTYPE html>', '<html lang="zh-CN"><head><meta charset="utf-8">',
             '<title>SEO 内容优化报告</title>',
             '<style>body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
             'max-width:960px;margin:24px auto;padding:0 16px;color:#1a1a1a;line-height:1.6}'
             'h1{font-size:24px;border-bottom:2px solid #2b6cb0;padding-bottom:8px}'
             'h2{font-size:18px;color:#2b6cb0;margin-top:28px}'
             'table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}'
             'th,td{border:1px solid #d0d7de;padding:6px 8px;text-align:left;vertical-align:top}'
             'th{background:#f0f6ff}tr:nth-child(even){background:#fafbfc}'
             '.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;'
             'background:#ebf8ff;color:#1a4971}.disclaimer{margin-top:32px;padding:12px;'
             'background:#fff8e1;border-left:4px solid #f0a020;font-size:13px}</style></head><body>']
    parts.append('<h1>SEO 内容优化报告</h1>')
    parts.append(sec(1, "执行摘要"))
    rt = data.get("recommended_title", {}) or {}
    rm = data.get("recommended_meta", {}) or {}
    v = data.get("validation", {}) or {}
    parts.append('<p>状态：<span class="badge">%s</span> ｜ 语言：%s ｜ 页面类型：%s ｜ 质量评分：%s</p>'
                 % (html_escape(data.get("status", "n/a")), html_escape(data.get("language", "")),
                    html_escape(data.get("page_type", "")), html_escape(v.get("score", "n/a"))))
    parts.append('<p><b>推荐标题：</b>%s</p>' % html_escape(rt.get("title", "—")))
    parts.append('<p><b>推荐元描述：</b>%s</p>' % html_escape(rm.get("meta_description", "—")))
    parts.append('</section>')

    parts.append(sec(3, "搜索意图分析"))
    si = data.get("search_intent", {}) or {}
    parts.append('<p>主要意图：%s ｜ 次要意图：%s ｜ 决策阶段：%s ｜ 匹配度：%s</p>' % (
        html_escape(si.get("primary_intent", "")), html_escape(str(si.get("secondary_intent") or "无")),
        html_escape(si.get("decision_stage", "")), html_escape(si.get("match_level", ""))))
    if si.get("content_gaps"):
        parts.append('<p>内容缺口：%s</p>' % html_escape("；".join(si["content_gaps"])))
    parts.append('</section>')

    parts.append(sec(4, "SEO 关键词推荐"))
    parts.append('<table><thead><tr><th>关键词</th><th>语言</th><th>类型</th><th>意图</th>'
                 '<th>阶段</th><th>相关性</th><th>证据</th><th>优先级</th><th>投放</th><th>理由</th></tr></thead><tbody>')
    for k in data.get("keywords", []):
        parts.append('<tr>' + ''.join('<td>%s</td>' % html_escape(k.get(f)) for f in
                     ["keyword", "language", "category", "search_intent", "funnel_stage",
                      "relevance", "evidence", "priority", "recommended_placement", "recommendation_reason"]) + '</tr>')
    parts.append('</tbody></table></section>')

    parts.append(sec(6, "优化标题候选"))
    parts.append('<table><thead><tr><th>#</th><th>标题</th><th>字符数</th><th>主关键词</th>'
                 '<th>意图</th><th>差异化</th><th>风险</th><th>评分</th><th>理由</th></tr></thead><tbody>')
    for i, c in enumerate(data.get("title_candidates", []), 1):
        parts.append('<tr><td>%d</td>' % i + ''.join('<td>%s</td>' % html_escape(c.get(f)) for f in
                     ["title", "character_count", "primary_keyword", "search_intent",
                      "differentiation", "claim_risk", "quality_score", "recommendation_reason"]) + '</tr>')
    parts.append('</tbody></table></section>')

    parts.append(sec(8, "元描述候选"))
    parts.append('<table><thead><tr><th>#</th><th>元描述</th><th>字符数</th><th>覆盖意图</th>'
                 '<th>含关键词</th><th>价值主张</th><th>CTA</th><th>风险</th><th>评分</th></tr></thead><tbody>')
    for i, c in enumerate(data.get("meta_candidates", []), 1):
        parts.append('<tr><td>%d</td>' % i + ''.join('<td>%s</td>' % html_escape(c.get(f)) for f in
                     ["meta_description", "character_count", "covered_intent", "included_keyword",
                      "value_proposition", "cta_type", "claim_risk", "quality_score"]) + '</tr>')
    parts.append('</tbody></table></section>')

    parts.append(sec(13, "合规与声明风险"))
    risks = data.get("risks", []) or []
    if risks:
        parts.append('<ul>' + ''.join('<li><b>%s/%s</b> %s（%s）</li>' % (
            html_escape(r.get("severity")), html_escape(r.get("type")),
            html_escape(r.get("detail")), html_escape(r.get("location"))) for r in risks) + '</ul>')
    else:
        parts.append('<p>无高风险合规项。</p>')
    parts.append('</section>')

    parts.append('<div class="disclaimer"><p>%s</p><p>%s</p></div>' % (
        html_escape(DISCLAIMER), html_escape(PRIVACY)))
    parts.append('</body></html>')
    return "\n".join(parts)


# ---------------- DOCX ----------------
def _docx_para(text, bold=False):
    rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return ('<w:p><w:pPr><w:spacing w:after="120"/></w:pPr>'
            '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p>' % (rpr, xml_escape(text)))


def _docx_table(rows):
    cells = "".join(
        '<w:tr>' + "".join(
            '<w:tc><w:tcPr><w:tcBorders>'
            '<w:top w:val="single" w:sz="4"/><w:left w:val="single" w:sz="4"/>'
            '<w:bottom w:val="single" w:sz="4"/><w:right w:val="single" w:sz="4"/>'
            '</w:tcBorders></w:tcPr><w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc>'
            % xml_escape(c) for c in row) + '</w:tr>'
        for row in rows)
    return ('<w:tbl><w:tblPr><w:tblBorders>'
            '<w:top w:val="single" w:sz="4"/><w:left w:val="single" w:sz="4"/>'
            '<w:bottom w:val="single" w:sz="4"/><w:right w:val="single" w:sz="4"/>'
            '<w:insideH w:val="single" w:sz="4"/><w:insideV w:val="single" w:sz="4"/>'
            '</w:tblBorders></w:tblPr>%s</w:tbl>' % cells)


def render_docx(data):
    body = []
    body.append(_docx_para("SEO 内容优化报告", bold=True))
    rt = data.get("recommended_title", {}) or {}
    rm = data.get("recommended_meta", {}) or {}
    v = data.get("validation", {}) or {}
    body.append(_docx_para("状态：%s ｜ 语言：%s ｜ 页面类型：%s ｜ 质量评分：%s" % (
        data.get("status", ""), data.get("language", ""), data.get("page_type", ""), v.get("score", ""))))
    body.append(_docx_para("推荐 SEO 标题：" + str(rt.get("title", "")), bold=True))
    body.append(_docx_para("推荐元描述：" + str(rm.get("meta_description", "")), bold=True))
    body.append(_docx_para("SEO 关键词推荐", bold=True))
    rows = [["关键词", "语言", "类型", "意图", "相关性", "证据", "优先级", "投放", "理由"]]
    for k in data.get("keywords", []):
        rows.append([str(k.get(f, "")) for f in ["keyword", "language", "category", "search_intent",
                   "relevance", "evidence", "priority", "recommended_placement", "recommendation_reason"]])
    body.append(_docx_table(rows))
    body.append(_docx_para("优化标题候选", bold=True))
    rows = [["#", "标题", "字符数", "主关键词", "差异化", "风险", "评分"]]
    for i, c in enumerate(data.get("title_candidates", []), 1):
        rows.append([str(i), str(c.get("title", "")), str(c.get("character_count", "")),
                     str(c.get("primary_keyword", "")), str(c.get("differentiation", "")),
                     str(c.get("claim_risk", "")), str(c.get("quality_score", ""))])
    body.append(_docx_table(rows))
    body.append(_docx_para("元描述候选", bold=True))
    rows = [["#", "元描述", "字符数", "含关键词", "价值主张", "CTA", "风险", "评分"]]
    for i, c in enumerate(data.get("meta_candidates", []), 1):
        rows.append([str(i), str(c.get("meta_description", "")), str(c.get("character_count", "")),
                     str(c.get("included_keyword", "")), str(c.get("value_proposition", "")),
                     str(c.get("cta_type", "")), str(c.get("claim_risk", "")), str(c.get("quality_score", ""))])
    body.append(_docx_table(rows))
    body.append(_docx_para("合规与声明风险", bold=True))
    for r in data.get("risks", []) or []:
        body.append(_docx_para("[%s/%s] %s" % (r.get("severity"), r.get("type"), r.get("detail"))))
    body.append(_docx_para(DISCLAIMER))
    body.append(_docx_para(PRIVACY))

    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body>' + "".join(body) +
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
                '</w:body></w:document>')
    content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     '<Default Extension="xml" ContentType="application/xml"/>'
                     '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                     '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
    return buf.getvalue()


# ---------------- CSV ----------------
def render_csv(data):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["keyword", "language", "category", "search_intent", "funnel_stage",
                "relevance", "evidence", "priority", "recommended_placement", "risk_note", "recommendation_reason"])
    for k in data.get("keywords", []):
        w.writerow([csv_cell(k.get(f, "")) for f in ["keyword", "language", "category", "search_intent",
                   "funnel_stage", "relevance", "evidence", "priority", "recommended_placement",
                   "risk_note", "recommendation_reason"]])
    return buf.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser(description="SEO 报告多格式渲染（零依赖）")
    ap.add_argument("--input", required=True)
    ap.add_argument("--format", required=True, choices=["markdown", "json", "html", "docx", "csv"])
    ap.add_argument("--output", help="输出路径（默认 stdout）")
    args = ap.parse_args(argv)

    with open(args.input, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    fmt = args.format
    if fmt == "json":
        content = json.dumps(data, ensure_ascii=False, indent=2)
        binary = False
    elif fmt == "markdown":
        content = render_markdown(data)
        binary = False
    elif fmt == "html":
        content = render_html(data)
        binary = False
    elif fmt == "csv":
        content = render_csv(data)
        binary = False
    elif fmt == "docx":
        content = render_docx(data)
        binary = True
    else:
        raise SystemExit("未知格式")

    if args.output:
        if binary:
            with open(args.output, "wb") as fh:
                fh.write(content)
        elif fmt == "csv":
            with open(args.output, "w", encoding="utf-8-sig") as fh:
                fh.write(content)
        else:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(content)
    else:
        if binary:
            sys.stdout.buffer.write(content)
        else:
            sys.stdout.write(content + "\n")


if __name__ == "__main__":
    main()
