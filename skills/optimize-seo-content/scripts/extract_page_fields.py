#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_page_fields.py — 从 HTML / Markdown / TXT / DOCX 提取 SEO 页面字段。

零依赖、零网络、纯标准库。输出 JSON：
  title, meta_description, meta_keywords, h1[], h2[], body,
  canonical, language, robots, json_ld[], source_type, char_count

用法：
  python extract_page_fields.py --input page.html
  python extract_page_fields.py --text "正文..." --source-type text
  python extract_page_fields.py --html "<html>..." --output fields.json
"""
import sys
import os
import re
import json
import argparse
from html.parser import HTMLParser

CJK_RE = re.compile(r"[一-鿿]")
WS_RE = re.compile(r"\s+")


def detect_language(text):
    """按 CJK 占比判定语言；默认 auto。"""
    stripped = text.strip()
    if not stripped:
        return "auto"
    cjk = len(CJK_RE.findall(stripped))
    return "zh-CN" if (cjk / max(1, len(stripped))) >= 0.3 else "en-US"


def clean_body(text):
    return WS_RE.sub(" ", text).strip()


class _PageExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self.meta = {}
        self.canonical = ""
        self.lang = ""
        self.robots = ""
        self.json_ld = []
        self.h1 = []
        self.h2 = []
        self._text = []
        self._skip_depth = 0
        self._heading = None
        self._in_ld = False
        self._ld_buf = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag in ("script", "style"):
            self._skip_depth += 1
            return
        if tag == "html":
            self.lang = d.get("lang", "") or ""
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            name = (d.get("name") or d.get("property") or "").lower()
            content = d.get("content", "") or ""
            if name == "description":
                self.meta["description"] = content
            elif name == "keywords":
                self.meta["keywords"] = content
            elif name == "robots":
                self.robots = content
        if tag == "link" and (d.get("rel") or "").lower() == "canonical":
            self.canonical = d.get("href", "") or ""
        if tag == "script" and (d.get("type") or "").lower() == "application/ld+json":
            self._in_ld = True
            self._ld_buf = []

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._in_ld:
            self._in_ld = False
            raw = "".join(self._ld_buf).strip()
            try:
                self.json_ld.append(json.loads(raw))
            except Exception:
                pass
        if tag in ("h1", "h2") and self._heading and self._heading["level"] == tag:
            tx = "".join(self._heading["text"]).strip()
            if tx:
                (self.h1 if tag == "h1" else self.h2).append(tx)
            self._heading = None

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        if self._in_title:
            self.title += data
            return
        if self._in_ld:
            self._ld_buf.append(data)
            return
        if self._heading is not None:
            self._heading["text"].append(data)
            return
        self._text.append(data)


def parse_html(text):
    p = _PageExtractor()
    try:
        p.feed(text)
        p.close()
    except Exception:
        pass
    body = clean_body(" ".join(p._text))
    lang = p.lang.strip() if p.lang.strip() else detect_language(body)
    return {
        "title": p.title.strip(),
        "meta_description": p.meta.get("description", "").strip(),
        "meta_keywords": p.meta.get("keywords", "").strip(),
        "h1": p.h1,
        "h2": p.h2,
        "body": body,
        "canonical": p.canonical.strip(),
        "language": lang,
        "robots": p.robots.strip(),
        "json_ld": p.json_ld,
    }


def parse_markdown(text):
    h1, h2, body_parts = [], [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("## "):
            h2.append(s[3:].strip())
        elif s.startswith("# "):
            h1.append(s[2:].strip())
        else:
            body_parts.append(line)
    body = "\n".join(body_parts).strip()
    return {
        "title": "",
        "meta_description": "",
        "meta_keywords": "",
        "h1": h1,
        "h2": h2,
        "body": body,
        "canonical": "",
        "language": detect_language(body),
        "robots": "",
        "json_ld": [],
    }


def parse_txt(text):
    return {
        "title": "",
        "meta_description": "",
        "meta_keywords": "",
        "h1": [],
        "h2": [],
        "body": text.strip(),
        "canonical": "",
        "language": detect_language(text),
        "robots": "",
        "json_ld": [],
    }


def parse_docx(path):
    import zipfile
    from xml.etree import ElementTree as ET

    W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml")
    except Exception as e:
        raise SystemExit("DOCX 读取失败: %s" % e)
    root = ET.fromstring(xml)
    paras = []
    for p in root.iter(W + "p"):
        texts = [t.text or "" for t in p.iter(W + "t")]
        paras.append("".join(texts))
    non_empty = [p for p in paras if p.strip()]
    h1 = [non_empty[0]] if non_empty else []
    body = "\n".join(paras).strip()
    return {
        "title": "",
        "meta_description": "",
        "meta_keywords": "",
        "h1": h1,
        "h2": [],
        "body": body,
        "canonical": "",
        "language": detect_language(body),
        "robots": "",
        "json_ld": [],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="提取 SEO 页面字段（零依赖）")
    ap.add_argument("--input", help="输入文件（.html/.md/.txt/.docx）")
    ap.add_argument("--text", help="直接传入纯文本")
    ap.add_argument("--html", help="直接传入 HTML 源码")
    ap.add_argument("--source-type", help="显式指定类型 text/markdown/html/docx")
    ap.add_argument("--output", help="输出 JSON 路径（默认 stdout）")
    args = ap.parse_args(argv)

    source_type = args.source_type
    text = None
    if args.input:
        if not os.path.isfile(args.input):
            raise SystemExit("文件不存在: %s" % args.input)
        ext = os.path.splitext(args.input)[1].lower()
        if source_type is None:
            source_type = {".html": "html", ".htm": "html", ".md": "markdown",
                           ".txt": "text", ".docx": "docx"}.get(ext, "text")
        with open(args.input, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    elif args.html is not None:
        source_type = source_type or "html"
        text = args.html
    elif args.text is not None:
        source_type = source_type or "text"
        text = args.text
    else:
        raise SystemExit("需提供 --input / --text / --html 之一")

    if source_type == "html":
        fields = parse_html(text)
    elif source_type == "markdown":
        fields = parse_markdown(text)
    elif source_type == "docx":
        fields = parse_docx(args.input)
    else:
        fields = parse_txt(text)

    fields["source_type"] = source_type
    fields["char_count"] = len(fields.get("body", ""))
    out = json.dumps(fields, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(out)
    else:
        sys.stdout.write(out + "\n")


if __name__ == "__main__":
    main()
