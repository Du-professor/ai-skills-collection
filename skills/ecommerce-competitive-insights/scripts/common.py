#!/usr/bin/env python3
"""Shared, dependency-free helpers for ecommerce-competitive-insights."""

from __future__ import annotations

import csv
import hashlib
import ipaddress
import io
import json
import re
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree as ET


MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_ROWS = 200_000
MAX_XLSX_ENTRIES = 1_000
MAX_XLSX_EXPANDED_BYTES = 100 * 1024 * 1024


def setup_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def fail_validation(errors: Sequence[str]) -> None:
    for error in errors:
        print(error, file=sys.stderr)
    raise SystemExit(2)


def fail_runtime(message: str) -> None:
    print("运行错误: " + message, file=sys.stderr)
    raise SystemExit(1)


def emit_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def stable_json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_key(value: Any) -> str:
    return str(value or "").strip().lstrip("\ufeff").lower()


def canonical_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {canonical_key(key): value for key, value in record.items()}


def allowed_roots() -> Tuple[Path, ...]:
    cwd = Path.cwd().resolve()
    roots = {Path(tempfile.gettempdir()).resolve()}
    if cwd != Path(cwd.anchor):
        roots.add(cwd)
    return tuple(sorted(roots, key=lambda item: str(item).casefold()))


def is_within_allowed_roots(path: Path) -> bool:
    for root in allowed_roots():
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def require_allowed_path(path: Path, role: str) -> None:
    if not is_within_allowed_roots(path):
        fail_validation(
            [
                "$: {}路径必须位于当前工作目录或系统临时目录内: {}".format(
                    role, path
                )
            ]
        )


def safe_input_path(
    raw: str, allowed_suffixes: Optional[Iterable[str]] = None
) -> Path:
    candidate = Path(raw).expanduser()
    if candidate.is_symlink():
        fail_validation(["$: 不接受符号链接输入: {}".format(candidate)])
    try:
        path = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError):
        fail_runtime("输入文件不存在或不可访问: {}".format(candidate))
    require_allowed_path(path, "输入")
    if not path.exists() or not path.is_file():
        fail_runtime("输入文件不存在或不是普通文件: {}".format(path))
    if allowed_suffixes is not None:
        suffixes = {item.lower() for item in allowed_suffixes}
        if path.suffix.lower() not in suffixes:
            fail_validation(
                [
                    "$: 输入扩展名必须为 {}，实际为 {}".format(
                        "/".join(sorted(suffixes)), path.suffix or "无"
                    )
                ]
            )
    if path.stat().st_size > MAX_FILE_BYTES:
        fail_validation(["$: 文件超过100MB限制: {}".format(path.name)])
    return path


def safe_output_path(raw: str, allowed_suffixes: Iterable[str]) -> Path:
    candidate = Path(raw).expanduser()
    if candidate.exists() and candidate.is_symlink():
        fail_validation(["$: 不接受符号链接输出: {}".format(candidate)])
    parent = candidate.parent.resolve()
    require_allowed_path(parent, "输出")
    path = (parent / candidate.name).resolve()
    require_allowed_path(path, "输出")
    suffixes = {item.lower() for item in allowed_suffixes}
    if path.suffix.lower() not in suffixes:
        fail_validation(
            ["$: 输出扩展名必须为 {}，实际为 {}".format(
                "/".join(sorted(suffixes)), path.suffix or "无"
            )]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not path.is_file():
        fail_validation(["$: 输出路径必须是普通文件: {}".format(path)])
    return path


def ensure_distinct_paths(inputs: Sequence[Path], outputs: Sequence[Path]) -> None:
    input_set = {item.resolve() for item in inputs}
    seen = set()
    errors = []
    for path in outputs:
        resolved = path.resolve()
        if resolved in input_set:
            errors.append("$: 输出不得覆盖输入文件: {}".format(path))
        if resolved in seen:
            errors.append("$: 多个输出路径不得相同: {}".format(path))
        seen.add(resolved)
    if errors:
        fail_validation(errors)


def detect_encoding(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    fail_runtime("无法以UTF-8或GB18030解码: {}".format(path.name))
    return "utf-8"


def _read_delimited(path: Path, delimiter: Optional[str] = None) -> List[Dict[str, Any]]:
    encoding = detect_encoding(path)
    text = path.read_text(encoding=encoding)
    if "\x00" in text:
        fail_validation(["$: 文本文件包含NUL字节: {}".format(path.name)])
    if delimiter is None:
        sample = text[:8192]
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",\t;|").delimiter
        except csv.Error:
            delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        fail_validation(["$: 文件缺少表头: {}".format(path.name)])
    rows = []
    for index, row in enumerate(reader, start=2):
        if index - 1 > MAX_ROWS:
            fail_validation(["$: 数据行超过{}行限制".format(MAX_ROWS)])
        canonical = canonical_record(dict(row))
        canonical["__source_row"] = index
        rows.append(canonical)
    return rows


def _read_json(path: Path) -> List[Dict[str, Any]]:
    encoding = detect_encoding(path)
    text = path.read_text(encoding=encoding)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        fail_validation(["$: JSON解析失败: {}".format(exc.msg)])
    if isinstance(value, dict):
        selected = next(
            (
                value.get(key)
                for key in ("records", "data", "products", "reviews")
                if isinstance(value.get(key), list)
            ),
            None,
        )
        value = selected if selected is not None else [value]
    if not isinstance(value, list):
        fail_validation(["$: JSON顶层必须是对象数组或包含records数组"])
    rows = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            fail_validation(["$[{}]: 必须是对象".format(index - 1)])
        row = canonical_record(item)
        row["__source_row"] = index
        rows.append(row)
    return rows


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> List[str]:
    try:
        raw = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(raw)
    values = []
    for node in root.iter():
        if node.tag.endswith("}si"):
            pieces = [
                child.text or ""
                for child in node.iter()
                if child.tag.endswith("}t")
            ]
            values.append("".join(pieces))
    return values


def _cell_col_index(reference: str) -> int:
    letters = "".join(ch for ch in reference if ch.isalpha()).upper()
    result = 0
    for char in letters:
        result = result * 26 + (ord(char) - ord("A") + 1)
    return max(result - 1, 0)


def _read_xlsx(path: Path) -> List[Dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as zf:
            entries = zf.infolist()
            if len(entries) > MAX_XLSX_ENTRIES:
                fail_validation(
                    ["$: XLSX内部文件数超过{}限制".format(MAX_XLSX_ENTRIES)]
                )
            expanded_size = sum(item.file_size for item in entries)
            if expanded_size > MAX_XLSX_EXPANDED_BYTES:
                fail_validation(["$: XLSX解压后内容超过100MB限制"])
            shared = _xlsx_shared_strings(zf)
            workbook = ET.fromstring(zf.read("xl/workbook.xml"))
            rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            rel_map = {
                node.attrib.get("Id"): node.attrib.get("Target")
                for node in rels
                if node.attrib.get("Id") and node.attrib.get("Target")
            }
            sheet_node = next(
                (node for node in workbook.iter() if node.tag.endswith("}sheet")),
                None,
            )
            if sheet_node is None:
                fail_validation(["$: XLSX中没有工作表"])
            rel_id = next(
                (
                    value
                    for key, value in sheet_node.attrib.items()
                    if key.endswith("}id")
                ),
                None,
            )
            target = rel_map.get(rel_id, "worksheets/sheet1.xml")
            target = target.lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            root = ET.fromstring(zf.read(target))
            matrix: List[List[str]] = []
            for row_node in (
                node for node in root.iter() if node.tag.endswith("}row")
            ):
                row: List[str] = []
                for cell in (
                    node for node in row_node if node.tag.endswith("}c")
                ):
                    col = _cell_col_index(cell.attrib.get("r", "A1"))
                    while len(row) <= col:
                        row.append("")
                    cell_type = cell.attrib.get("t", "")
                    value_node = next(
                        (node for node in cell if node.tag.endswith("}v")), None
                    )
                    inline = [
                        node.text or ""
                        for node in cell.iter()
                        if node.tag.endswith("}t")
                    ]
                    raw_value = value_node.text if value_node is not None else "".join(inline)
                    if cell_type == "s" and raw_value:
                        try:
                            raw_value = shared[int(raw_value)]
                        except (ValueError, IndexError):
                            raw_value = ""
                    elif cell_type == "b":
                        raw_value = "true" if raw_value == "1" else "false"
                    row[col] = raw_value or ""
                matrix.append(row)
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        fail_runtime("XLSX解析失败: {}".format(exc))

    if not matrix:
        return []
    headers = []
    used = {}
    for index, item in enumerate(matrix[0]):
        key = canonical_key(item) or "column_{}".format(index + 1)
        used[key] = used.get(key, 0) + 1
        headers.append(key if used[key] == 1 else "{}_{}".format(key, used[key]))
    rows = []
    for source_row, values in enumerate(matrix[1:], start=2):
        if source_row - 1 > MAX_ROWS:
            fail_validation(["$: 数据行超过{}行限制".format(MAX_ROWS)])
        if not any(str(item).strip() for item in values):
            continue
        padded = values + [""] * max(0, len(headers) - len(values))
        row = {headers[i]: padded[i] for i in range(len(headers))}
        row["__source_row"] = source_row
        rows.append(row)
    return rows


def read_records(raw_path: str) -> Tuple[Path, List[Dict[str, Any]]]:
    path = safe_input_path(
        raw_path, {".csv", ".tsv", ".json", ".xlsx"}
    )
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return path, _read_delimited(path, ",")
    if suffix == ".tsv":
        return path, _read_delimited(path, "\t")
    if suffix == ".json":
        return path, _read_json(path)
    if suffix == ".xlsx":
        return path, _read_xlsx(path)
    fail_validation(
        ["$: 仅支持CSV、TSV、JSON、XLSX，实际为{}".format(suffix or "无")]
    )
    return path, []


def text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_number(value: Any) -> Optional[float]:
    text = text_value(value)
    if not text:
        return None
    cleaned = (
        text.replace(",", "")
        .replace("￥", "")
        .replace("¥", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .strip()
    )
    try:
        result = float(cleaned)
    except ValueError:
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def parse_integer(value: Any) -> Optional[int]:
    parsed = parse_number(value)
    if parsed is None or int(parsed) != parsed:
        return None
    return int(parsed)


def parse_bool(value: Any) -> bool:
    return canonical_key(value) in {"1", "true", "yes", "y", "是", "自有", "own"}


def normalize_currency(value: Any) -> Optional[str]:
    text = text_value(value).upper()
    mapping = {
        "¥": "CNY",
        "￥": "CNY",
        "RMB": "CNY",
        "人民币": "CNY",
        "$": "USD",
        "美元": "USD",
        "€": "EUR",
        "欧元": "EUR",
        "£": "GBP",
        "英镑": "GBP",
    }
    text = mapping.get(text, text)
    return text if re.fullmatch(r"[A-Z]{3}", text or "") else None


def normalize_date(value: Any) -> Optional[str]:
    text = text_value(value)
    if not text:
        return None
    normalized = text.replace("/", "-").replace(".", "-")
    candidates = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m",
    ]
    for fmt in candidates:
        try:
            parsed = datetime.strptime(normalized, fmt)
            return parsed.date().isoformat()
        except ValueError:
            continue
    return None


EMAIL_RE = re.compile(
    r"(?i)(?<![a-z0-9._%+-])[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}(?![a-z0-9-])"
)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
ID_RE = re.compile(r"(?<!\w)\d{14,17}[\dXx](?!\w)")
ORDER_RE = re.compile(
    r"(?i)(订单号|订单|order(?:\s*id)?)[：:#=\s-]*([A-Z0-9-]{8,})"
)


def mask_sensitive(value: Any) -> str:
    text = text_value(value)
    text = EMAIL_RE.sub("[已脱敏邮箱]", text)
    text = PHONE_RE.sub("[已脱敏手机号]", text)
    text = ID_RE.sub("[已脱敏证件号]", text)
    text = ORDER_RE.sub(lambda m: "{}：[已脱敏订单号]".format(m.group(1)), text)
    return text


def sanitize_public_url(value: Any) -> Optional[str]:
    text = text_value(value)
    if not text:
        return ""
    if any(ord(char) < 32 for char in text):
        return None
    if mask_sensitive(text) != text:
        return None
    try:
        parsed = urlsplit(text)
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if not parsed.hostname or parsed.username or parsed.password:
        return None
    hostname = parsed.hostname.rstrip(".").casefold()
    if hostname == "localhost" or hostname.endswith(
        (".localhost", ".local", ".internal", ".lan", ".home", ".home.arpa")
    ):
        return None
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is None and re.fullmatch(
        r"(?:0x[0-9a-f]+|\d+|[0-9.]+)", hostname, flags=re.IGNORECASE
    ):
        return None
    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        return None
    if port == 0:
        return None
    host_display = "[{}]".format(hostname) if ":" in hostname else hostname
    netloc = "{}:{}".format(host_display, port) if port is not None else host_display
    return urlunsplit(
        (parsed.scheme.lower(), netloc, parsed.path or "/", "", "")
    )


def csv_safe(value: Any) -> str:
    text = text_value(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def round_number(value: Optional[float], digits: int = 4) -> Optional[float]:
    if value is None:
        return None
    return round(value, digits)


def median(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def today_iso() -> str:
    from datetime import date

    return date.today().isoformat()
