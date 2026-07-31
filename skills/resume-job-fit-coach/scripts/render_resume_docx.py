#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""职配雷达 · 定制版简历 DOCX 渲染脚本。

仅用标准库 zipfile 从零生成最小 OOXML 文档, 不依赖 python-docx 等第三方库。
输入为结构化简历 JSON (schema 见 references/output-schema.md 第 3 节)。

用法:
    python render_resume_docx.py input.json -o output.docx

退出码:
    0  成功
    2  输入校验失败, stderr 逐行输出字段级错误清单
    1  运行错误 (文件不可读 / JSON 解析失败 / 写入失败)

说明: ZIP 条目使用固定时间戳与固定顺序, 同一输入生成的文件内容一致。
"""

import argparse
import json
import sys
import zipfile
from xml.sax.saxutils import escape

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

FONT_ASCII = "Calibri"
FONT_EAST_ASIA = "\u7b49\u7ebf"  # 等线

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults>
<w:rPrDefault><w:rPr>
<w:rFonts w:ascii="{ascii}" w:hAnsi="{ascii}" w:eastAsia="{ea}"/>
<w:sz w:val="22"/><w:szCs w:val="22"/>
</w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal">
<w:name w:val="Normal"/><w:qFormat/>
</w:style>
</w:styles>""".format(ascii=FONT_ASCII, ea=FONT_EAST_ASIA)


def run_xml(text, bold=False, size=None):
    """构造一个 run; size 为半磅值 (如 22 = 11pt)。"""
    props = [f'<w:rFonts w:ascii="{FONT_ASCII}" w:hAnsi="{FONT_ASCII}" w:eastAsia="{FONT_EAST_ASIA}"/>']
    if bold:
        props.append("<w:b/><w:bCs/>")
    if size is not None:
        props.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    rpr = "<w:rPr>" + "".join(props) + "</w:rPr>"
    return f'<w:r>{rpr}<w:t xml:space="preserve">{escape(str(text))}</w:t></w:r>'


def paragraph(runs, space_after=None):
    """构造段落; runs 为 run_xml 字符串列表或单个字符串。"""
    ppr = ""
    if space_after is not None:
        ppr = f'<w:pPr><w:spacing w:after="{space_after}"/></w:pPr>'
    if isinstance(runs, str):
        runs = [runs]
    return "<w:p>" + ppr + "".join(runs) + "</w:p>"


def heading(text):
    return paragraph(run_xml(text, bold=True, size=26), space_after=120)


def bullet(text):
    return paragraph(run_xml("\u2022 " + str(text)))


def validate(data, errors):
    if not isinstance(data, dict):
        errors.append("$: 顶层必须是 JSON 对象")
        return
    for key in ("candidate_name", "contact_placeholder", "target_title", "summary"):
        if not isinstance(data.get(key), str) or not data.get(key).strip():
            errors.append(f"$.{key}: 缺失或不是非空字符串")
    for key in ("skills", "projects", "education"):
        if not isinstance(data.get(key), list):
            errors.append(f"$.{key}: 缺失或不是数组")
    skills = data.get("skills") or []
    for i, s in enumerate(skills):
        if not isinstance(s, str) or not s.strip():
            errors.append(f"$.skills[{i}]: 必须是非空字符串")
    projects = data.get("projects") or []
    for i, p in enumerate(projects):
        path = f"$.projects[{i}]"
        if not isinstance(p, dict):
            errors.append(f"{path}: 必须是对象")
            continue
        if not isinstance(p.get("title"), str) or not p.get("title").strip():
            errors.append(f"{path}.title: 缺失或不是非空字符串")
        if "period" in p and not isinstance(p.get("period"), str):
            errors.append(f"{path}.period: 必须是字符串")
        if not isinstance(p.get("bullets"), list) or not all(isinstance(b, str) and b.strip() for b in p.get("bullets", [])):
            errors.append(f"{path}.bullets: 缺失或不是非空字符串数组")
    internships = data.get("internships", [])
    if not isinstance(internships, list):
        errors.append("$.internships: 必须是数组")
        internships = []
    for i, p in enumerate(internships):
        path = f"$.internships[{i}]"
        if not isinstance(p, dict):
            errors.append(f"{path}: 必须是对象")
            continue
        for key in ("org", "role"):
            if not isinstance(p.get(key), str) or not p.get(key).strip():
                errors.append(f"{path}.{key}: 缺失或不是非空字符串")
        if not isinstance(p.get("bullets"), list) or not all(isinstance(b, str) and b.strip() for b in p.get("bullets", [])):
            errors.append(f"{path}.bullets: 缺失或不是非空字符串数组")
    education = data.get("education") or []
    for i, e in enumerate(education):
        path = f"$.education[{i}]"
        if not isinstance(e, dict):
            errors.append(f"{path}: 必须是对象")
            continue
        for key in ("school", "major", "degree"):
            if not isinstance(e.get(key), str) or not e.get(key).strip():
                errors.append(f"{path}.{key}: 缺失或不是非空字符串")
        if "period" in e and not isinstance(e.get("period"), str):
            errors.append(f"{path}.period: 必须是字符串")


def build_document(data):
    parts = []
    parts.append(paragraph(run_xml(data["candidate_name"], bold=True, size=36), space_after=40))
    parts.append(paragraph(run_xml(data["contact_placeholder"], size=20), space_after=40))
    parts.append(paragraph(run_xml("\u6c42\u804c\u610f\u5411\uff1a" + data["target_title"], size=22), space_after=160))

    parts.append(heading("\u4e2a\u4eba\u6458\u8981"))
    parts.append(paragraph(run_xml(data["summary"])))

    if data.get("skills"):
        parts.append(heading("\u4e13\u4e1a\u6280\u80fd"))
        parts.append(paragraph(run_xml("\u3001".join(data["skills"]))))

    if data.get("projects"):
        parts.append(heading("\u9879\u76ee\u7ecf\u5386"))
        for p in data["projects"]:
            title = p["title"] + ("\uff08" + p["period"] + "\uff09" if p.get("period") else "")
            parts.append(paragraph(run_xml(title, bold=True), space_after=40))
            for b in p["bullets"]:
                parts.append(bullet(b))

    if data.get("internships"):
        parts.append(heading("\u5b9e\u4e60\u7ecf\u5386"))
        for p in data["internships"]:
            title = p["org"] + " " + p["role"] + ("\uff08" + p["period"] + "\uff09" if p.get("period") else "")
            parts.append(paragraph(run_xml(title, bold=True), space_after=40))
            for b in p["bullets"]:
                parts.append(bullet(b))

    if data.get("education"):
        parts.append(heading("\u6559\u80b2\u80cc\u666f"))
        for e in data["education"]:
            line = e["school"] + " " + e["major"] + " " + e["degree"]
            if e.get("period"):
                line += "\uff08" + e["period"] + "\uff09"
            parts.append(paragraph(run_xml(line)))

    sect = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
            'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>')
    body = "".join(parts) + sect
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>" + body + "</w:body></w:document>")


def write_docx(document_xml, out_path):
    entries = [
        ("[Content_Types].xml", CONTENT_TYPES),
        ("_rels/.rels", ROOT_RELS),
        ("word/_rels/document.xml.rels", DOC_RELS),
        ("word/document.xml", document_xml),
        ("word/styles.xml", STYLES),
    ]
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zf.writestr(info, content.encode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="职配雷达 DOCX 简历渲染 (schema: references/output-schema.md)")
    parser.add_argument("input_json", help="结构化简历 JSON 文件路径")
    parser.add_argument("-o", "--output", required=True, help="输出 DOCX 文件路径")
    args = parser.parse_args()

    try:
        with open(args.input_json, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"运行错误: 无法读取或解析输入 JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    errors = []
    validate(data, errors)
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        sys.exit(2)

    document_xml = build_document(data)
    try:
        write_docx(document_xml, args.output)
    except OSError as exc:
        print(f"运行错误: 无法写入 DOCX: {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps({"output": args.output, "status": "ok"}, ensure_ascii=False, sort_keys=True))
    sys.exit(0)


if __name__ == "__main__":
    main()
