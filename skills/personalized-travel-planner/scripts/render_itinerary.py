#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_itinerary.py — 将校验后的行程 JSON 渲染为自包含 HTML（内联 CSS，可离线打开）。

同时向 stdout 输出 HTML；若 HTML 渲染异常，降级输出 Markdown 到 stdout，保证用户始终拿到内容。
合规：无外链资源（无 <script src>、无外链字体/图片/CSS）；仅一个指向 amap.com 的 <a> 锚点（点击才联网）；
强制注入免责声明与隐私说明（见 DISCLAIMER / PRIVACY）。

退出码：0 成功 / 1 意外（仍会尽力输出 Markdown）。
"""
import argparse
import html
import json
import sys

DISCLAIMER = ("免责声明：本行程单由 AI 自动生成，仅供参考，不构成专业旅行/票务/安全建议。"
              "实时交通、天气、票价与开放信息请以高德地图及官方渠道为准；出行前请自行核实证件、票务、"
              "天气与当地规定，并对自身安全负责。")
PRIVACY = ("隐私说明：您的长期偏好仅保存在本机本地文件，不会上传至任何服务器；本行程单不嵌入任何个人身份信息（PII）。"
           "如需删除偏好，直接删除本地偏好文件即可。")

TYPE_META = {
    "transport": ("交通", "#2563eb"),
    "accommodation": ("住宿", "#7c3aed"),
    "attraction": ("景点", "#059669"),
    "meal": ("餐饮", "#ea580c"),
    "free": ("自由", "#64748b"),
}


def esc(s):
    return html.escape("" if s is None else str(s))


def md_escape(s):
    # Markdown 回退统一转义：去换行 + 转义行内标记字符，确保 <...>/[]()/| 不被解析为标记
    s = "" if s is None else str(s).replace("\r", "").replace("\n", " ")
    s = s.replace("\\", "\\\\")  # 先转义已有反斜杠
    for ch in ("`", "*", "_", "[", "]", "(", ")", "<", ">", "|", "~", "^", "#"):
        s = s.replace(ch, "\\" + ch)
    return s


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_html(plan):
    meta = plan.get("meta", {})
    dsn = plan.get("data_source_note", "estimate")
    realtime = dsn == "realtime"
    status_bar = ("✅ 已接入高德地图实时数据（天气/路况）" if realtime
                  else "⚠️ 数据基于知识库估算，非实时，请以高德地图为准。建议在高德地图查看：https://www.amap.com/")
    status_cls = "ok" if realtime else "warn"

    days_html = []
    for day in plan.get("days", []):
        segs = []
        for s in day.get("segments", []):
            t = s.get("type", "free")
            label, color = TYPE_META.get(t, TYPE_META["free"])
            extra = ""
            if t == "transport":
                extra = "%s：%s → %s" % (esc(s.get("transport_mode", "")), esc(s.get("from", "")), esc(s.get("to", "")))
            elif t == "accommodation":
                extra = "%s @ %s" % (esc(s.get("accommodation_type", "")), esc(s.get("location", "")))
            elif t == "attraction":
                extra = "%s @ %s" % (esc(s.get("category", "")), esc(s.get("location", "")))
            elif t == "meal":
                extra = "%s" % esc(s.get("meal_type", ""))
            cost = s.get("cost")
            cost_s = "¥%s" % cost if isinstance(cost, (int, float)) else ""
            note = "<div class='notes'>%s</div>" % esc(s.get("notes", "")) if s.get("notes") else ""
            segs.append(
                "<div class='seg'>"
                "<div class='time'>%s–%s</div>"
                "<div class='badge' style='background:%s'>%s</div>"
                "<div class='body'><div class='title'>%s</div>"
                "<div class='sub'>%s%s</div>%s</div></div>" % (
                    esc(s.get("start_time", "")), esc(s.get("end_time", "")), color, esc(label),
                    esc(s.get("title", "")), extra, (" · " + cost_s if cost_s else ""), note))
        days_html.append("<section class='day'><h3>第%s天 · %s · %s</h3>%s</section>" % (
            esc(day.get("day", "")), esc(day.get("date", "")), esc(day.get("city", "")), "".join(segs)))

    wnotes = []
    for n in plan.get("weather_traffic_notes", []):
        src = n.get("source", "estimate")
        badge = "<span class='src realtime'>实时</span>" if src == "realtime" else "<span class='src estimate'>估算</span>"
        wnotes.append("<li>%s <b>%s</b>：%s<br><span class='hint'>%s</span></li>" % (
            badge, esc(n.get("scope", "")), esc(n.get("text", "")), esc(n.get("amap_hint", ""))))

    bb = plan.get("budget_breakdown", {})
    total_budget = meta.get("total_budget")
    over = isinstance(bb.get("total"), (int, float)) and isinstance(total_budget, (int, float)) and float(bb["total"]) > float(total_budget)
    rows = "".join("<tr><td>%s</td><td class='num'>¥%s</td></tr>" % (esc(k), esc(bb.get(k, ""))) for k in
                   ("transport", "accommodation", "ticket", "meal", "contingency"))
    total_row = "<tr class='total %s'><td>合计</td><td class='num'>¥%s / 预算 ¥%s</td></tr>" % (
        "over" if over else "", esc(bb.get("total", "")), esc(total_budget))

    chips = "".join("<span class='chip'>%s</span>" % esc(p) for p in plan.get("preferences_applied", []))
    meta_line = "%s → %s | %s 至 %s | %s天 | 档位 %s | 同行 %s" % (
        esc(meta.get("origin", "")), esc(meta.get("destination", "")), esc(meta.get("start_date", "")),
        esc(meta.get("end_date", "")), esc(meta.get("days", "")), esc(meta.get("budget_tier", "")),
        esc(meta.get("companion_type", "")))
    title = esc(meta.get("title", "行程单"))

    return """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;max-width:860px;margin:0 auto;padding:20px;color:#1f2937;background:#f8fafc}}
.status{{padding:12px 16px;border-radius:10px;font-weight:600;margin-bottom:16px}}
.status.ok{{background:#dcfce7;color:#166534}}
.status.warn{{background:#fef9c3;color:#854d0e}}
h1{{font-size:22px;margin:0 0 4px}}
.meta{{color:#64748b;font-size:13px;margin-bottom:16px}}
.day{{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:14px 16px;margin-bottom:14px}}
.day h3{{margin:0 0 10px;font-size:16px}}
.seg{{display:flex;gap:10px;padding:8px 0;border-top:1px dashed #eef2f7}}
.seg:first-child{{border-top:none}}
.time{{width:92px;color:#475569;font-size:13px;flex-shrink:0}}
.badge{{color:#fff;font-size:12px;padding:2px 8px;border-radius:999px;height:fit-content;flex-shrink:0}}
.body{{flex:1}}
.title{{font-weight:600}}
.sub{{color:#64748b;font-size:13px}}
.notes{{color:#94a3b8;font-size:12px;margin-top:2px}}
.mapcard{{background:#eef2ff;border:1px solid #c7d2fe;border-radius:12px;padding:16px;margin-bottom:14px;text-align:center;color:#4338ca}}
.mapcard a{{color:#4338ca;font-weight:600}}
.wnotes{{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:12px 16px;margin-bottom:14px}}
.wnotes ul{{margin:0;padding-left:18px}}
.src{{font-size:11px;padding:1px 6px;border-radius:6px}}
.src.realtime{{background:#dcfce7;color:#166534}}
.src.estimate{{background:#fef9c3;color:#854d0e}}
.hint{{color:#94a3b8;font-size:12px}}
.budget{{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:12px 16px;margin-bottom:14px}}
.budget table{{width:100%%;border-collapse:collapse}}
.budget td{{padding:6px 4px;border-bottom:1px solid #f1f5f9}}
.budget td.num{{text-align:right}}
.budget tr.total td{{font-weight:700;border-top:2px solid #e5e7eb}}
.budget tr.over td{{color:#dc2626}}
.chips{{margin-bottom:14px}}
.chip{{display:inline-block;background:#e0f2fe;color:#0369a1;font-size:12px;padding:3px 10px;border-radius:999px;margin:2px}}
.legal{{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:12px;padding:12px 16px;font-size:12px;color:#475569;margin-top:8px}}
.legal p{{margin:6px 0}}
</style></head><body>
<h1>%s</h1>
<div class="meta">%s</div>
<div class="status %s">%s</div>
<div class="mapcard">📍 地图占位（离线示意图）<br><a href="https://www.amap.com/" target="_blank" rel="noopener">建议在高德地图查看路线与周边</a></div>
%s
<div class="wnotes"><h3>天气与路况提醒</h3><ul>%s</ul></div>
<div class="budget"><h3>预算摘要</h3><table>%s%s</table></div>
<div class="chips"><b>已应用偏好：</b><br>%s</div>
<div class="legal"><p>%s</p><p>%s</p></div>
</body></html>""" % (title, title, meta_line, status_cls, status_bar, "".join(days_html),
               "".join(wnotes) if wnotes else "<li>暂无提醒</li>", rows, total_row,
               chips if chips else "无", DISCLAIMER, PRIVACY)


def render_md(plan):
    # 全部动态字段经 md_escape 转义，避免用户内容中的 <...>/[]()/| 被解析为 Markdown 标记
    meta = plan.get("meta", {})
    dsn = plan.get("data_source_note", "estimate")
    lines = []
    lines.append("# %s" % md_escape(meta.get("title", "行程单")))
    lines.append("%s -> %s | %s 至 %s | %s天 | 档位 %s | 同行 %s" % (
        md_escape(meta.get("origin", "")), md_escape(meta.get("destination", "")), md_escape(meta.get("start_date", "")),
        md_escape(meta.get("end_date", "")), md_escape(meta.get("days", "")), md_escape(meta.get("budget_tier", "")), md_escape(meta.get("companion_type", ""))))
    lines.append("已接入高德地图实时数据" if dsn == "realtime" else "数据基于知识库估算，非实时，请以高德地图为准")
    for day in plan.get("days", []):
        lines.append("\n## 第%s天 · %s · %s" % (md_escape(day.get("day", "")), md_escape(day.get("date", "")), md_escape(day.get("city", ""))))
        for s in day.get("segments", []):
            cost = s.get("cost")
            cost_s = " ¥%s" % cost if isinstance(cost, (int, float)) else ""
            lines.append("- %s–%s 【%s】%s%s" % (md_escape(s.get("start_time", "")), md_escape(s.get("end_time", "")), md_escape(s.get("type", "")), md_escape(s.get("title", "")), cost_s))
    lines.append("\n## 天气与路况提醒")
    for n in plan.get("weather_traffic_notes", []):
        lines.append("- [%s] %s：%s" % (md_escape(n.get("source", "")), md_escape(n.get("scope", "")), md_escape(n.get("text", ""))))
    bb = plan.get("budget_breakdown", {})
    lines.append("\n## 预算摘要")
    for k in ("transport", "accommodation", "ticket", "meal", "contingency", "total"):
        lines.append("- %s: %s" % (k, md_escape(bb.get(k, ""))))
    lines.append("\n" + md_escape(DISCLAIMER))
    lines.append(md_escape(PRIVACY))
    return "\n".join(lines)


def _setup_streams():
    # 防止 Windows GBK 控制台下打印含非 ASCII（如 ✅/⚠️/→）时抛 UnicodeEncodeError
    for s in (sys.stdout, sys.stderr):
        try:
            if hasattr(s, "reconfigure"):
                s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _emit(text, stream=None):
    # 安全输出：即便底层编码不支持也能降级，绝不因编码抛异常
    stream = stream or sys.stdout
    try:
        stream.write(text + "\n")
        return
    except UnicodeEncodeError:
        pass
    try:
        stream.buffer.write((text + "\n").encode("utf-8", "replace"))
    except Exception:
        pass


def main():
    _setup_streams()
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--preferences", help="可选，展示用（当前以 plan.preferences_applied 为主）")
    ap.add_argument("--out", help="输出 HTML 路径（可选，不指定则打印 HTML 到 stdout）")
    args = ap.parse_args()

    try:
        plan = load(args.plan)
    except Exception as e:
        _emit("render failed to read plan: %s" % e, sys.stderr)
        sys.exit(1)

    md = render_md(plan)
    try:
        doc = render_html(plan)
    except Exception as e:
        _emit("render html failed (%s); falling back to markdown" % e, sys.stderr)
        _emit(md)
        sys.exit(0)

    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(doc)
            _emit("rendered: %s" % args.out)  # 仅输出 ASCII 状态，避免特殊字符触发编码错误
        except Exception as e:
            _emit("write html failed (%s); outputting markdown to stdout" % e, sys.stderr)
            _emit(md)  # 经 _setup_streams 安全降级，异常分支不会二次崩溃
        sys.exit(0)
    _emit(doc)
    sys.exit(0)


if __name__ == "__main__":
    main()
