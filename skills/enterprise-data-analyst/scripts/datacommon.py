"""datacommon.py — enterprise-data-analyst 共享数据底座模块。

纯 Python 标准库实现，无第三方依赖、无网络调用。提供：
- 统一退出契约：fail_validation -> exit 2（stderr 字段级报错），
  fail_runtime -> exit 1（stderr 前缀「运行错误: 」），emit_json -> stdout 确定性 JSON。
- 数据读取：CSV/TSV（编码回退链 + 分隔符探测）、JSON/JSONL（深度限制 + 扁平化）、
  xlsx 只读解析（zipfile + ElementTree，公式格取缓存值，日期样式序列值还原）。
- 数据理解：列类型推断、数值解析（千分位/货币/百分号/括号负数/全半角）、
  日期解析（多格式 + 歧义多数决）、敏感列正则检测与脱敏。
- 通用工具：分位数、nice_ticks 刻度、CSV 公式注入防护、确定性数值格式化。

确定性承诺：无随机数、无时间戳；同一输入多次运行输出字节级一致。
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
import statistics
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

# ---------------------------------------------------------------------------
# 全局上限常量（超限截断并显式标记，不静默丢失）
# ---------------------------------------------------------------------------
MAX_FILE_BYTES = 100 * 1024 * 1024   # 输入文件大小上限 100MB
MAX_ROWS = 200_000                   # 数据行读取上限
MAX_JSON_DEPTH = 32                  # JSON 嵌套深度上限
MAX_CHANGE_LOG = 10_000              # 清洗变更日志条数上限
SAMPLE_SIZE = 2_000                  # 类型推断抽样上限（取前 N 个非空值，确定性）
TYPE_SUCCESS_RATE = 0.9              # 类型判定解析成功率阈值
ENUM_MAX_UNIQUE = 20                 # 枚举列唯一值个数上限
ENUM_MAX_RATIO = 0.05                # 枚举列唯一值占比上限
SENSITIVE_HIT_RATE = 0.3             # 敏感列判定命中率阈值

# 全角 -> 半角映射（数字、符号、字母、空格）
_FW2HW = {ord(c): ord(c) - 0xFEE0 for c in (chr(0xFF01 + i) for i in range(94))}
_FW2HW[0x3000] = 0x20

# ---------------------------------------------------------------------------
# 退出契约
# ---------------------------------------------------------------------------

def setup_stdio() -> None:
    """win32 下强制 stdout/stderr 使用 UTF-8，防止中文输出崩溃。"""
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def fail_validation(errors: list) -> None:
    """输入校验失败：stderr 逐行字段级报错，exit 2。调用方据此修复重试。"""
    setup_stdio()
    for err in errors:
        sys.stderr.write(str(err) + "\n")
    sys.exit(2)


def fail_runtime(message: str) -> None:
    """运行错误：stderr 前缀「运行错误: 」，exit 1。"""
    setup_stdio()
    sys.stderr.write("运行错误: " + str(message) + "\n")
    sys.exit(1)


def emit_json(result: dict) -> None:
    """成功输出：stdout 确定性 JSON（键排序、保留中文、2 空格缩进），exit 0。"""
    setup_stdio()
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    sys.stdout.write("\n")
    sys.exit(0)


def load_json_file(path_str: str, role: str = "输入") -> object:
    """读取并解析 JSON 文件；失败走运行错误。供各脚本读取策略/规格 JSON。"""
    p = Path(path_str)
    if not p.is_file():
        fail_runtime(f"{role} JSON 文件不存在: {path_str}")
    try:
        text = p.read_bytes().decode("utf-8-sig")
    except OSError as exc:
        fail_runtime(f"{role} JSON 文件不可读: {exc}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        fail_runtime(f"{role} JSON 解析失败: {exc}")


def find_forbidden_keys(obj: object, forbidden: set, path: str = "$") -> list:
    """递归检查模型输入 JSON 中是否私带结果字段（小写精确匹配）。

    统计值只能由脚本计算，模型在规格/策略 JSON 中填入这些键即拒绝。
    """
    errors = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str) and key.lower() in forbidden:
                errors.append(f"{path}.{key}: 禁止出现结果字段 '{key}' (统计值只能由脚本计算)")
            errors.extend(find_forbidden_keys(value, forbidden, f"{path}.{key}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            errors.extend(find_forbidden_keys(item, forbidden, f"{path}[{i}]"))
    return errors


def check_whitelist(obj: dict, allowed: set, path: str) -> list:
    """白名单键校验：规格 JSON 中任何白名单外的键都拒绝（防模型夹带）。"""
    errors = []
    for key in obj:
        if key not in allowed:
            errors.append(f"{path}.{key}: 未知字段 '{key}' (仅允许: {sorted(allowed)})")
    return errors


# ---------------------------------------------------------------------------
# 路径与读取
# ---------------------------------------------------------------------------

def resolve_input_path(raw: str) -> Path:
    """解析用户显式给出的输入文件路径。只读、不递归扫描目录。"""
    if not raw or not str(raw).strip():
        fail_runtime("输入文件路径为空")
    p = Path(raw)
    if not p.exists():
        fail_runtime(f"输入文件不存在: {raw}")
    if not p.is_file():
        fail_runtime(f"输入路径不是文件(不支持目录递归扫描): {raw}")
    try:
        size = p.stat().st_size
    except OSError as exc:
        fail_runtime(f"无法读取文件信息: {exc}")
    if size > MAX_FILE_BYTES:
        fail_runtime(f"文件超过 {MAX_FILE_BYTES // (1024 * 1024)}MB 上限({size} 字节),请拆分后重试")
    return p


def detect_encoding(path: Path) -> tuple:
    """编码识别回退链：utf-8-sig -> utf-8 -> gb18030 -> gb18030+replace。

    返回 (encoding, raw_bytes, warnings)。末档容错解码保证不崩溃。
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        fail_runtime(f"文件不可读: {exc}")
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig", raw, []
    try:
        raw.decode("utf-8")
        return "utf-8", raw, []
    except UnicodeDecodeError:
        pass
    try:
        raw.decode("gb18030")
        return "gb18030", raw, ["文件编码为 gb18030 (GBK 系), 已自动识别"]
    except UnicodeDecodeError:
        return "gb18030", raw, ["无法可靠识别文件编码, 已按 gb18030 容错解码(非法字符被替换)"]


def _decode(raw: bytes, encoding: str) -> str:
    """按识别出的编码解码；末档 gb18030 容错。"""
    if encoding == "gb18030":
        try:
            return raw.decode("gb18030")
        except UnicodeDecodeError:
            return raw.decode("gb18030", errors="replace")
    return raw.decode(encoding)


def sniff_delimiter(sample: str) -> str:
    """分隔符探测：csv.Sniffer 失败时按首行候选字符计数，最终回退逗号。"""
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        pass
    first_line = sample.splitlines()[0] if sample.splitlines() else ""
    counts = {c: first_line.count(c) for c in (",", "\t", ";", "|")}
    best = max(counts, key=lambda c: counts[c])
    return best if counts[best] > 0 else ","


def _dedupe_header(header: list, warnings: list) -> list:
    """重复/空表头处理：重命名为 name_2、column_<位置>，记 warning，不丢列。"""
    seen = {}
    result = []
    for i, name in enumerate(header):
        name = (name or "").strip()
        if not name:
            name = f"column_{i + 1}"
            warnings.append(f"第 {i + 1} 列表头为空, 已命名为 '{name}'")
        if name in seen:
            seen[name] += 1
            new_name = f"{name}_{seen[name]}"
            warnings.append(f"表头 '{name}' 重复, 第 {i + 1} 列已重命名为 '{new_name}'")
            name = new_name
        else:
            seen[name] = 1
        result.append(name)
    return result


def read_csv_rows(path: Path, max_rows: int = MAX_ROWS) -> tuple:
    """读取 CSV/TSV。返回 (header, rows[list[dict]], meta)。超行数截断并标记。"""
    encoding, raw, warnings = detect_encoding(path)
    text = _decode(raw, encoding)
    delimiter = sniff_delimiter(text[:8192])
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        raw_header = next(reader)
    except StopIteration:
        return [], [], {"encoding": encoding, "delimiter": delimiter,
                        "truncated": False, "warnings": warnings}
    header = _dedupe_header(raw_header, warnings)
    rows = []
    truncated = False
    for record in reader:
        if len(rows) >= max_rows:
            truncated = True
            break
        if len(record) < len(header):
            record = record + [""] * (len(header) - len(record))
        elif len(record) > len(header):
            record = record[: len(header)]
        rows.append(dict(zip(header, (cell if cell is not None else "" for cell in record))))
    if truncated:
        warnings.append(f"数据超过 {max_rows} 行上限, 已截断(truncated=true), 仅分析前 {max_rows} 行")
    meta = {"encoding": encoding, "delimiter": delimiter,
            "truncated": truncated, "warnings": warnings}
    return header, rows, meta


def json_depth(obj: object, current: int = 1) -> int:
    """计算 JSON 结构嵌套深度。"""
    if isinstance(obj, dict):
        return max((json_depth(v, current + 1) for v in obj.values()), default=current)
    if isinstance(obj, list):
        return max((json_depth(v, current + 1) for v in obj), default=current)
    return current


def flatten_record(record: dict, depth: int = 2, prefix: str = "") -> dict:
    """嵌套 dict 按 depth 层扁平化为点号键；更深层与列表序列化为紧凑 JSON 字符串。"""
    flat = {}
    for key, value in record.items():
        full = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict) and depth > 1:
            flat.update(flatten_record(value, depth - 1, full))
        elif isinstance(value, (dict, list)):
            flat[full] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            flat[full] = "" if value is None else str(value)
    return flat


def read_json_rows(path: Path, max_rows: int = MAX_ROWS) -> tuple:
    """读取 JSON(对象数组) 或 JSONL(每行一个对象)。深度>32 或格式非法走运行错误。"""
    encoding, raw, warnings = detect_encoding(path)
    text = _decode(raw, encoding)
    records = None
    bad_lines = 0
    stripped = text.strip()
    if not stripped:
        return [], [], {"encoding": encoding, "truncated": False, "warnings": warnings}
    try:
        parsed = json.loads(stripped)
        if not isinstance(parsed, list):
            fail_runtime("JSON 顶层必须是对象数组(或改用 JSONL 每行一个对象)")
        records = parsed
    except json.JSONDecodeError:
        # 回退 JSONL：逐行解析，坏行跳过并计数
        records = []
        for line in stripped.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                bad_lines += 1
        if bad_lines:
            warnings.append(f"JSONL 有 {bad_lines} 行无法解析, 已跳过")
        if not records:
            fail_runtime("JSON/JSONL 解析失败: 无有效数据行")
    if json_depth(records) > MAX_JSON_DEPTH + 2:
        fail_runtime(f"JSON 嵌套深度超过 {MAX_JSON_DEPTH} 层, 请扁平化后重试")
    truncated = False
    if len(records) > max_rows:
        records = records[:max_rows]
        truncated = True
        warnings.append(f"数据超过 {max_rows} 行上限, 已截断(truncated=true)")
    flat_rows = []
    header = []
    seen = set()
    for rec in records:
        if not isinstance(rec, dict):
            rec = {"value": rec}
        flat = flatten_record(rec)
        for key in flat:
            if key not in seen:
                seen.add(key)
                header.append(key)
        flat_rows.append(flat)
    header = _dedupe_header(header, warnings)
    rows = [{h: row.get(h, "") for h in header} for row in flat_rows]
    meta = {"encoding": encoding, "truncated": truncated, "warnings": warnings}
    return header, rows, meta


# ---------------------------------------------------------------------------
# xlsx 只读解析（zipfile + ElementTree；公式格取缓存值；日期样式还原）
# ---------------------------------------------------------------------------
_XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_XLSX_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_XLSX_PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
# Excel 内置日期类数字格式 id 区间
_DATE_NUMFMT_IDS = set(range(14, 23)) | {45, 46, 47}
_DATE_FMT_CODE = re.compile(r"[ymdhHsS]", re.IGNORECASE)


def _col_letter_to_index(ref: str) -> int:
    """单元格引用 'BC12' -> 列下标 54（从 0 计）。"""
    letters = re.match(r"[A-Za-z]+", ref)
    if not letters:
        return 0
    idx = 0
    for ch in letters.group(0).upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _xlsx_date_styles(zf: zipfile.ZipFile) -> set:
    """解析 styles.xml，返回「日期类样式」的 cellXfs 下标集合（轻量近似）。"""
    try:
        styles_xml = zf.read("xl/styles.xml")
    except KeyError:
        return set()
    try:
        root = ET.fromstring(styles_xml)
    except ET.ParseError:
        return set()
    custom = {}
    for numfmt in root.iter(_XLSX_NS + "numFmt"):
        fid = numfmt.get("numFmtId")
        code = numfmt.get("formatCode", "")
        if fid and code:
            custom[int(fid)] = bool(_DATE_FMT_CODE.search(code))
    date_styles = set()
    cellxfs = root.find(_XLSX_NS + "cellXfs")
    if cellxfs is None:
        return set()
    for i, xf in enumerate(cellxfs.findall(_XLSX_NS + "xf")):
        fid = int(xf.get("numFmtId", "0"))
        if fid in _DATE_NUMFMT_IDS or custom.get(fid, False):
            date_styles.add(i)
    return date_styles


def _serial_to_iso(value_text: str) -> str:
    """Excel 日期序列值 -> ISO 日期字符串（1900 日期系统，基准 1899-12-30）。"""
    try:
        serial = float(value_text)
    except (TypeError, ValueError):
        return value_text
    if not (1 <= serial <= 2958465):  # 1900-01-01 .. 9999-12-31
        return value_text
    day = date(1899, 12, 30) + timedelta(days=int(serial))
    frac = serial - int(serial)
    if frac > 0:
        seconds = int(round(frac * 86400))
        return day.isoformat() + f" {seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
    return day.isoformat()


def read_xlsx_rows(path: Path, sheet: str = None, max_rows: int = MAX_ROWS) -> tuple:
    """只读解析 xlsx 首个（或指定）工作表。

    - 公式单元格取缓存值 <v>；无缓存 -> None + warning。
    - 日期样式序列值还原为 ISO 字符串。
    - xls/xlsm/加密文件 -> fail_runtime 提示另存。
    """
    warnings = []
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        fail_runtime("无法解析 xlsx(可能为 xls/xlsm/加密文件), 请另存为标准 xlsx 或 CSV 后重试")
    with zf:
        names = set(zf.namelist())
        if "xl/workbook.xml" not in names:
            fail_runtime("不是有效的 xlsx 文件(缺少 xl/workbook.xml)")
        try:
            wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
        except ET.ParseError:
            fail_runtime("xlsx workbook.xml 解析失败")
        rels = {}
        try:
            rel_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
            for rel in rel_root.iter(_XLSX_PKG_REL_NS + "Relationship"):
                rels[rel.get("Id")] = rel.get("Target")
        except KeyError:
            fail_runtime("xlsx 缺少 workbook 关系文件")
        # 收集工作表 (名称 -> 目标路径)
        sheets = []
        for sh in wb_root.iter(_XLSX_NS + "sheet"):
            rid = sh.get(_XLSX_REL_NS + "id")
            target = rels.get(rid, "")
            if target and not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            sheets.append((sh.get("name", "Sheet1"), target))
        if not sheets:
            fail_runtime("xlsx 中没有工作表")
        chosen = None
        if sheet:
            for name, target in sheets:
                if name == sheet:
                    chosen = (name, target)
                    break
            if chosen is None:
                fail_runtime(f"xlsx 中不存在工作表 '{sheet}' (现有: {[s[0] for s in sheets]})")
        else:
            chosen = sheets[0]
        sheet_name, sheet_path = chosen
        # 共享字符串
        shared = []
        if "xl/sharedStrings.xml" in names:
            try:
                ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                for si in ss_root.iter(_XLSX_NS + "si"):
                    shared.append("".join(t.text or "" for t in si.iter(_XLSX_NS + "t")))
            except ET.ParseError:
                warnings.append("sharedStrings.xml 解析失败, 共享字符串按空值处理")
        date_styles = _xlsx_date_styles(zf)
        try:
            sheet_root = ET.fromstring(zf.read(sheet_path))
        except (KeyError, ET.ParseError):
            fail_runtime(f"xlsx 工作表 '{sheet_name}' 解析失败")
        grid = []
        max_col = 0
        formula_no_cache = 0
        for row_el in sheet_root.iter(_XLSX_NS + "row"):
            cells = {}
            for c in row_el.iter(_XLSX_NS + "c"):
                ref = c.get("r", "A1")
                col = _col_letter_to_index(ref)
                ctype = c.get("t", "")
                style_idx = int(c.get("s", "0"))
                v_el = c.find(_XLSX_NS + "v")
                f_el = c.find(_XLSX_NS + "f")
                value = None
                if ctype == "s" and v_el is not None and v_el.text is not None:
                    try:
                        value = shared[int(v_el.text)]
                    except (ValueError, IndexError):
                        value = ""
                elif ctype == "inlineStr":
                    is_el = c.find(_XLSX_NS + "is")
                    value = "".join(t.text or "" for t in is_el.iter(_XLSX_NS + "t")) if is_el is not None else ""
                elif ctype == "b" and v_el is not None:
                    value = "TRUE" if v_el.text == "1" else "FALSE"
                elif ctype == "e":
                    value = ""  # 错误单元格按空处理
                elif v_el is not None and v_el.text is not None:
                    value = v_el.text
                    if style_idx in date_styles and re.fullmatch(r"\d+(\.\d+)?", value or ""):
                        value = _serial_to_iso(value)
                elif f_el is not None:
                    formula_no_cache += 1  # 公式无缓存值
                    value = ""
                cells[col] = value if value is not None else ""
                max_col = max(max_col, col + 1)
            if cells:
                grid.append(cells)
        if formula_no_cache:
            warnings.append(
                f"xlsx 有 {formula_no_cache} 个公式单元格无缓存值, 已按空值处理; "
                "建议在 Excel 中另存一次以写入缓存值")
        if not grid:
            return [], [], {"encoding": "xlsx", "sheet": sheet_name,
                            "truncated": False, "warnings": warnings}
        raw_header = [grid[0].get(i, "") for i in range(max_col)]
        header = _dedupe_header([str(h) for h in raw_header], warnings)
        rows = []
        truncated = False
        for cells in grid[1:]:
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append({header[i]: str(cells.get(i, "") or "") for i in range(max_col)})
        if truncated:
            warnings.append(f"数据超过 {max_rows} 行上限, 已截断(truncated=true)")
        meta = {"encoding": "xlsx", "sheet": sheet_name,
                "truncated": truncated, "warnings": warnings}
        return header, rows, meta


def read_dataset(path_str: str, sheet: str = None, max_rows: int = MAX_ROWS) -> tuple:
    """按扩展名分发读取 CSV/TSV/JSON/JSONL/xlsx。统一返回 (header, rows, meta)。"""
    p = resolve_input_path(path_str)
    suffix = p.suffix.lower()
    if suffix in (".csv", ".tsv", ".txt"):
        return read_csv_rows(p, max_rows)
    if suffix in (".json", ".jsonl", ".ndjson"):
        return read_json_rows(p, max_rows)
    if suffix == ".xlsx":
        return read_xlsx_rows(p, sheet=sheet, max_rows=max_rows)
    if suffix in (".xls", ".xlsm"):
        fail_runtime(f"不支持 {suffix} 格式, 请另存为 xlsx 或 CSV 后重试")
    fail_runtime(f"无法识别的文件格式 '{suffix}' (支持: csv/tsv/json/jsonl/xlsx)")


# ---------------------------------------------------------------------------
# 数值与日期解析
# ---------------------------------------------------------------------------
_INT_RE = re.compile(r"^[+-]?\d+$")
_FLOAT_RE = re.compile(r"^[+-]?\d+(\.\d+)?([eE][+-]?\d+)?$")
_CURRENCY_PREFIX = re.compile(r"^[¥￥$€£]\s*")


def parse_number(text) -> float | None:
    """宽松数值解析：千分位、货币符号、百分号(除以100)、括号负数、全半角、科学计数。

    无法解析返回 None；空串返回 None。
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    s = s.translate(_FW2HW)
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1].strip()
    percent = s.endswith("%")
    if percent:
        s = s[:-1].strip()
    s = _CURRENCY_PREFIX.sub("", s)
    s = re.sub(r"\s*(元|块)$", "", s)
    s = s.replace(",", "").replace(" ", "")
    if not _FLOAT_RE.fullmatch(s):
        return None
    try:
        value = float(s)
    except ValueError:
        return None
    if negative:
        value = -value
    if percent:
        value = value / 100.0
    return value


_DATE_YMD = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?$")
_DATE_CN = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日?$")
_DATE_COMPACT = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_DATE_AMBIGUOUS = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$")


def _valid_date(y: int, m: int, d: int) -> str | None:
    """校验并格式化 ISO 日期；非法日期返回 None。"""
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def parse_date(text, prefer: str = "MDY") -> str | None:
    """多格式日期解析，返回 ISO 'YYYY-MM-DD' 或 None。

    prefer 用于 xx/xx/yyyy 歧义格式：'MDY'(月/日/年) 或 'DMY'(日/月/年)，
    列级多数决结果由调用方传入；单边 >12 时自动判型无需 prefer。
    """
    if text is None:
        return None
    s = str(text).strip().translate(_FW2HW)
    if not s:
        return None
    m = _DATE_YMD.match(s)
    if m:
        return _valid_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _DATE_CN.match(s)
    if m:
        return _valid_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _DATE_COMPACT.match(s)
    if m:
        return _valid_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = _DATE_AMBIGUOUS.match(s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12 and b <= 12:
            return _valid_date(y, b, a)          # 必为 日/月/年
        if b > 12 and a <= 12:
            return _valid_date(y, a, b)          # 必为 月/日/年
        if prefer.upper() == "DMY":
            return _valid_date(y, b, a)
        return _valid_date(y, a, b)              # 默认 月/日/年
    return None


def detect_date_prefer(values: list) -> tuple:
    """列级歧义格式多数决。返回 (prefer, note)；无法判定时 prefer='MDY'。"""
    mdy = dmy = 0
    for v in values:
        s = str(v).strip().translate(_FW2HW)
        m = _DATE_AMBIGUOUS.match(s)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12 and b <= 12:
            dmy += 1
        elif b > 12 and a <= 12:
            mdy += 1
    if mdy == 0 and dmy == 0:
        return "MDY", "歧义日期格式无法多数决, 默认按月/日/年(MDY)解析"
    if dmy > mdy:
        return "DMY", f"歧义日期格式按多数决采用 日/月/年(DMY) (证据 {dmy}:{mdy})"
    return "MDY", f"歧义日期格式按多数决采用 月/日/年(MDY) (证据 {mdy}:{dmy})"


# ---------------------------------------------------------------------------
# 列类型推断
# ---------------------------------------------------------------------------
_BOOL_VALUES = {"true", "false", "yes", "no", "y", "n", "是", "否", "对", "错"}


def is_missing(value) -> bool:
    """缺失判定：None 或纯空白字符串。"""
    return value is None or str(value).strip() == ""


def infer_column_type(values: list) -> tuple:
    """列类型推断。values 为非空原始字符串列表。

    返回 (type, confidence)：integer/float/date/boolean/enum/text。
    判定顺序：integer -> float -> date -> boolean -> enum -> text；
    前四类要求解析成功率 >= 0.9（抽样前 SAMPLE_SIZE 个，确定性）。
    空值在函数内部过滤，调用方无需预处理。
    """
    sample = [v for v in values if not is_missing(v)][:SAMPLE_SIZE]
    n = len(sample)
    if n == 0:
        return "text", 0.0
    int_hits = sum(1 for v in sample if _INT_RE.fullmatch(str(v).strip()))
    if int_hits / n >= TYPE_SUCCESS_RATE:
        return "integer", round(int_hits / n, 4)
    num_hits = sum(1 for v in sample if parse_number(v) is not None)
    if num_hits / n >= TYPE_SUCCESS_RATE:
        return "float", round(num_hits / n, 4)
    date_hits = sum(1 for v in sample if parse_date(v) is not None)
    if date_hits / n >= TYPE_SUCCESS_RATE:
        return "date", round(date_hits / n, 4)
    if all(str(v).strip().lower() in _BOOL_VALUES for v in sample):
        return "boolean", 1.0
    unique_count = len(set(sample))
    # 枚举阈值：唯一值个数 <= min(20, max(3, n*5%))；下限 3 保证小数据集可判定
    if unique_count <= min(ENUM_MAX_UNIQUE, max(3, int(n * ENUM_MAX_RATIO))):
        return "enum", 0.8
    return "text", 1.0


# ---------------------------------------------------------------------------
# 敏感列检测与脱敏
# ---------------------------------------------------------------------------
_PHONE_RE = re.compile(r"1[3-9]\d{9}")
_IDCARD_RE = re.compile(r"\d{17}[\dXx]")
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_BANKCARD_RE = re.compile(r"\d{16,19}")

SENSITIVE_KINDS = ("phone", "idcard", "email", "bankcard")


def detect_sensitive_columns(header: list, rows: list) -> list:
    """按正则命中率 >= 0.3 判定敏感列。返回 [{name, kind, hit_rate}]（按列序）。"""
    findings = []
    for col in header:
        values = [str(r.get(col, "")).strip() for r in rows]
        values = [v for v in values if v]
        if not values:
            continue
        rates = {}
        phone = sum(1 for v in values if _PHONE_RE.fullmatch(v))
        rates["phone"] = phone / len(values)
        idcard = sum(1 for v in values if _IDCARD_RE.fullmatch(v))
        rates["idcard"] = idcard / len(values)
        email = sum(1 for v in values if _EMAIL_RE.fullmatch(v))
        rates["email"] = email / len(values)
        bank = sum(1 for v in values
                   if _BANKCARD_RE.fullmatch(v) and not _PHONE_RE.fullmatch(v)
                   and not _IDCARD_RE.fullmatch(v))
        rates["bankcard"] = bank / len(values)
        best_kind = max(rates, key=lambda k: rates[k])
        if rates[best_kind] >= SENSITIVE_HIT_RATE:
            findings.append({"name": col, "kind": best_kind,
                             "hit_rate": round(rates[best_kind], 4)})
    return findings


def mask_value(value: str, kind: str) -> str:
    """敏感值脱敏展示。原值不出现在报告与对话正文。"""
    v = str(value)
    if kind == "phone" and len(v) >= 7:
        return v[:3] + "****" + v[-4:]
    if kind == "idcard":
        return (v[:4] + "*" * max(4, len(v) - 8) + v[-4:]) if len(v) > 8 else "****"
    if kind == "email" and "@" in v:
        local, domain = v.split("@", 1)
        return (local[:1] if local else "") + "***@" + domain
    if kind == "bankcard" and len(v) >= 4:
        return "****" + v[-4:]
    return "***"


def detect_value_kind(value) -> str | None:
    """对单个值精确判定敏感类型；非敏感返回 None。供报告渲染前脱敏判定。"""
    v = "" if value is None else str(value).strip()
    if not v:
        return None
    if _PHONE_RE.fullmatch(v):
        return "phone"
    if _IDCARD_RE.fullmatch(v):
        return "idcard"
    if _EMAIL_RE.fullmatch(v):
        return "email"
    if _BANKCARD_RE.fullmatch(v) and not _PHONE_RE.fullmatch(v) and not _IDCARD_RE.fullmatch(v):
        return "bankcard"
    return None


# 仅覆盖四类 PII 的典型列名（不含裸 'id'，避免误伤 order_id/user_id 等非敏感列）
_SENSITIVE_NAME_RE = re.compile(
    r"(手机|电话|手机号|联系电话|phone|mobile|tel|"
    r"邮箱|电子邮件|email|e-?mail|"
    r"身份证|身份证号码|证件|证件号|护照|passport|id_?card|"
    r"银行卡|银行卡号|卡号|bank_?card|card_?no)",
    re.I,
)


def classify_sensitive(column: str, value) -> str | None:
    """综合列名与值判定 (列,值) 是否应在报告中脱敏。

    值模式精确匹配优先（手机/邮箱/证件/银行卡）；列名模式作兜底
    （命中但值非标准格式时回退通用掩码）。返回 'phone'/'idcard'/
    'email'/'bankcard' 或 None。渲染质量日志前对命中列/值脱敏，
    确保共享 HTML 报告不泄露 PII 原值。
    """
    v = "" if value is None else str(value).strip()
    if v:
        kind = detect_value_kind(v)
        if kind:
            return kind
    if _SENSITIVE_NAME_RE.search(str(column)):
        low = str(column).lower()
        if re.search(r"手机|电话|phone|mobile|tel|号码", low):
            return "phone"
        if re.search(r"邮箱|邮件|email|mail", low):
            return "email"
        if re.search(r"身份证|证件|身份|护照|passport", low):
            return "idcard"
        if re.search(r"银行|卡号|bank|card", low):
            return "bankcard"
        return "phone"
    return None


# ---------------------------------------------------------------------------
# 统计与格式化工具
# ---------------------------------------------------------------------------

def quantile(sorted_values: list, q: float) -> float | None:
    """线性插值分位数。输入必须已升序排序；空列表返回 None。"""
    n = len(sorted_values)
    if n == 0:
        return None
    pos = (n - 1) * q
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * frac


def column_stats(values: list) -> dict:
    """数值列统计量。输入为 float 列表（调用方负责解析过滤）。"""
    if not values:
        return {}
    sv = sorted(values)
    n = len(sv)
    mean = statistics.fmean(sv)
    std = statistics.stdev(sv) if n >= 2 else 0.0
    return {
        "min": round6(sv[0]),
        "max": round6(sv[-1]),
        "mean": round6(mean),
        "median": round6(quantile(sv, 0.5)),
        "std": round6(std),
        "q1": round6(quantile(sv, 0.25)),
        "q3": round6(quantile(sv, 0.75)),
    }


def round6(x) -> float | None:
    """输出统一保留 6 位小数；消除 -0.0；None 透传。"""
    if x is None:
        return None
    v = round(float(x), 6)
    return 0.0 if v == 0 else v


def fmt_number(v: float) -> str:
    """确定性数值字符串（用于写回 CSV）：整数去小数点，最多 6 位小数。"""
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


def nice_ticks(vmin: float, vmax: float, count: int = 5) -> list:
    """1-2-2.5-5-10 漂亮刻度算法，返回刻度值列表（含边界取整外扩）。"""
    if vmin == vmax:
        vmin -= 1.0
        vmax += 1.0
    if vmin > vmax:
        vmin, vmax = vmax, vmin
    span = vmax - vmin
    raw_step = span / max(1, count)
    mag = 10 ** math.floor(math.log10(raw_step))
    step = None
    for m in (1, 2, 2.5, 5, 10):
        if raw_step <= m * mag:
            step = m * mag
            break
    if step is None:
        step = 10 * mag
    lo = math.floor(vmin / step) * step
    hi = math.ceil(vmax / step) * step
    ticks = []
    t = lo
    while t <= hi + step * 1e-9:
        ticks.append(round6(t))
        t += step
    return ticks


def fmt_tick(v: float) -> str:
    """坐标轴刻度标签：千分位 + 去尾零。"""
    if abs(v) >= 1000:
        return f"{v:,.0f}" if v == int(v) else f"{v:,.2f}".rstrip("0").rstrip(".")
    return fmt_number(v)


def csv_safe_cell(text: str) -> str:
    """CSV 公式注入防护：= + - @ 开头的文本单元格加单引号前缀。"""
    if isinstance(text, str) and text[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text
