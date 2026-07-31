#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
read_docx.py — 零依赖提取 .docx 正文文本（zipfile + xml.etree）。

用于政策原文为 Word 文档时，在标准库内提取纯文本，避免引入第三方依赖。
不解析图片/复杂表格布局，仅提取段落与表格单元格文本。

用法：
  python read_docx.py --input policy.docx
  python read_docx.py --input policy.docx --output policy.txt

退出码：
  0  成功（文本写到 stdout 或 --output）
  1  失败（非 docx / 损坏 / 加密 / 读取出错）
"""
import sys
import zipfile
import xml.etree.ElementTree as ET
import argparse

# OOXML 文档的 XML 命名空间标识符（ECMA-376 / ISO 29500 标准）。
# 仅用于 xml.etree 标签匹配，不是网络地址，不会发起任何请求。
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_text(path):
    if not zipfile.is_zipfile(path):
        raise ValueError("不是有效的 .docx（ZIP）文件")
    with zipfile.ZipFile(path) as z:
        # 防止 Zip 路径穿越（Zip Slip）
        for name in z.namelist():
            if name.startswith("/") or ".." in name.split("/"):
                raise ValueError(f"文档含可疑路径：{name}")
        if "word/document.xml" not in z.namelist():
            raise ValueError("文档缺少 word/document.xml，可能已损坏或非标准")
        with z.open("word/document.xml") as f:
            tree = ET.parse(f)
    root = tree.getroot()
    body = root.find(f"{W_NS}body")
    if body is None:
        raise ValueError("文档 body 缺失")
    lines = []
    for el in body.iter():
        tag = el.tag
        if tag == f"{W_NS}p":
            texts = [t.text for t in el.iter(f"{W_NS}t") if t.text]
            lines.append("".join(texts))
        elif tag == f"{W_NS}br":
            lines.append("")
        elif tag == f"{W_NS}tab":
            lines.append("\t")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()
    try:
        text = extract_text(args.input)
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"FATAL: 无法读取 docx: {e}\n")
        sys.exit(1)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"已提取文本：{args.output}")
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"FATAL: 无法写入: {e}\n")
            sys.exit(1)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
