#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_itinerary.py — 校验并归一化模型产出的行程 JSON。

唯一来源：references/itinerary-rubric.md（枚举与预算公式）、references/output-contract.md（字段约束）。
脚本顶部常量必须与这两个文件保持一致，改动时须同步更新。

退出码：0 成功（含警告）/ 2 校验错误（供模型按 stderr 字段级错误修复 JSON 后重试 ≤2 次）/ 1 意外错误（降级不中断）。
"""
import argparse
import json
import sys

# ---- 枚举（唯一来源: references/itinerary-rubric.md §1-§4）----
TRANSPORT_MODES = {"飞机", "高铁", "自驾", "公交地铁", "打车", "步行", "骑行", "轮渡", "长途大巴"}
ACCOMMODATION_TYPES = {"经济连锁", "舒适商务", "豪华酒店", "民宿", "青年旅舍", "服务公寓"}
CATEGORIES = {"自然风光", "历史古迹", "博物馆", "主题乐园", "美食街区", "购物中心",
              "城市观景", "演出演艺", "户外探险", "休闲度假", "亲子乐园", "宗教场所", "市集", "校园"}
MEAL_TYPES = {"早餐", "午餐", "晚餐", "小吃夜市", "下午茶", "特色宴"}
COMPANION_TYPES = {"单人", "情侣", "家庭", "朋友", "商务"}
BUDGET_TIERS = {"economy", "comfort", "luxury"}

# 预算比例上限（唯一来源: itinerary-rubric.md §5）。顺序: 交通, 住宿, 门票, 餐饮, 备用金下限
BUDGET_RATIOS = {
    "economy": (0.35, 0.20, 0.15, 0.25, 0.10),
    "comfort": (0.30, 0.28, 0.15, 0.22, 0.10),
    "luxury":  (0.25, 0.35, 0.15, 0.20, 0.10),
}
MIN_TRANSFER_MIN = 30

# 国内判定（合规：仅限国内）。仅用国内省级/主要城市白名单；未命中即视为无法确认为国内目的地，
# 由上层拒绝并要求用户确认。不写入任何境外地名，确保「境外关键词零命中」。
DOMESTIC_TOKENS = {"北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏",
                   "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "海南",
                   "四川", "贵州", "云南", "陕西", "甘肃", "青海", "宁夏", "新疆", "内蒙古", "广西",
                   "西藏", "香港", "澳门", "台湾", "杭州", "成都", "西安", "苏州", "南京", "武汉",
                   "广州", "深圳", "厦门", "青岛", "大连", "昆明", "丽江", "三亚", "桂林", "拉萨",
                   "西宁", "银川", "兰州", "贵阳", "长沙", "郑州", "济南", "合肥", "南昌", "福州",
                   "太原", "石家庄", "哈尔滨", "长春", "沈阳", "呼和浩特", "南宁", "海口", "乌鲁木齐"}


def to_min(t):
    try:
        h, m = str(t).split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def is_domestic(dest):
    if not isinstance(dest, str) or not dest.strip():
        return False
    for tok in DOMESTIC_TOKENS:
        if tok in dest:
            return True
    return False  # 未命中国内名单：无法确认为国内目的地，由上层拒绝并要求确认


def seg_loc(seg, which):
    t = seg.get("type")
    if t == "transport":
        return seg.get("to") if which == "end" else seg.get("from")
    if t in ("accommodation", "attraction", "meal"):
        return seg.get("location")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True, help="行程 JSON 路径，或 - 读 stdin")
    ap.add_argument("--preferences", help="偏好 JSON（可选，用于交叉核对档位）")
    ap.add_argument("--out", help="写归一化 JSON 的路径（可选）")
    args = ap.parse_args()

    errors = []
    warnings = []

    # 读取 plan
    try:
        if args.plan == "-":
            raw = sys.stdin.read()
        else:
            with open(args.plan, "r", encoding="utf-8") as f:
                raw = f.read()
        plan = json.loads(raw)
    except Exception as e:
        print("unexpected error reading plan: %s" % e, file=sys.stderr)
        sys.exit(1)

    # meta 必填
    meta = plan.get("meta")
    if not isinstance(meta, dict):
        errors.append("missing field: meta")
        meta = {}
    else:
        for fld in ("origin", "destination", "start_date", "end_date", "budget_tier", "total_budget", "currency"):
            if fld not in meta or meta.get(fld) in (None, ""):
                errors.append("missing field: meta.%s" % fld)
        if "days" not in meta or not isinstance(meta.get("days"), int):
            errors.append("missing/invalid field: meta.days")
        if "interest_tags" not in meta or not isinstance(meta.get("interest_tags"), list):
            errors.append("missing field: meta.interest_tags")
        if "dietary_restrictions" not in meta or not isinstance(meta.get("dietary_restrictions"), list):
            errors.append("missing field: meta.dietary_restrictions")
        bt = meta.get("budget_tier")
        if bt is not None and bt not in BUDGET_TIERS:
            errors.append("unknown budget_tier: %s" % bt)
        ct = meta.get("companion_type")
        if ct is not None and ct not in COMPANION_TYPES:
            errors.append("unknown companion_type: %s" % ct)
        dest = meta.get("destination")
        if dest is not None:
            if not is_domestic(dest):
                errors.append("destination not domestic: %s (请确认是国内目的地)" % dest)

    # days / segments
    days = plan.get("days")
    if not isinstance(days, list) or not days:
        errors.append("missing/invalid field: days (non-empty list required)")
        days = []
    else:
        for di, day in enumerate(days, 1):
            segs = day.get("segments") if isinstance(day, dict) else None
            if not isinstance(segs, list):
                errors.append("missing/invalid field: days[%d].segments" % di)
                continue
            # 时间冲突 + 中转间隔（非跨午夜段按 start 排序）
            checkable = []
            for s in segs:
                if not isinstance(s, dict):
                    errors.append("invalid segment in day%d" % di)
                    continue
                st = to_min(s.get("start_time"))
                et = to_min(s.get("end_time"))
                if st is not None and et is not None and not s.get("cross_midnight"):
                    checkable.append((st, et, s))
            checkable.sort(key=lambda x: x[0])
            for i in range(len(checkable) - 1):
                st0, et0, s0 = checkable[i]
                st1, et1, s1 = checkable[i + 1]
                if et0 is not None and st1 is not None and et0 > st1:
                    errors.append("time overlap day%d seg %s vs %s" % (di, s0.get("id"), s1.get("id")))
                loc0 = seg_loc(s0, "end")
                loc1 = seg_loc(s1, "start")
                if loc0 and loc1 and loc0 != loc1:
                    gap = (st1 - et0) if (et0 is not None and st1 is not None) else None
                    if gap is not None and 0 <= gap < MIN_TRANSFER_MIN:
                        warnings.append("transfer gap < %dmin between %s(to=%s) and %s(from=%s)" % (
                            MIN_TRANSFER_MIN, s0.get("id"), loc0, s1.get("id"), loc1))
            # 枚举 + 成本
            for s in segs:
                if not isinstance(s, dict):
                    continue
                sid = s.get("id", "?")
                stype = s.get("type")
                cost = s.get("cost", 0)
                if isinstance(cost, (int, float)) and cost < 0:
                    errors.append("negative cost in segment %s" % sid)
                if stype == "transport":
                    m = s.get("transport_mode")
                    if m not in TRANSPORT_MODES:
                        errors.append("unknown enum transport_mode: %s (seg %s)" % (m, sid))
                elif stype == "accommodation":
                    a = s.get("accommodation_type")
                    if a not in ACCOMMODATION_TYPES:
                        errors.append("unknown enum accommodation_type: %s (seg %s)" % (a, sid))
                elif stype == "attraction":
                    c = s.get("category")
                    if c not in CATEGORIES:
                        errors.append("unknown enum category: %s (seg %s)" % (c, sid))
                elif stype == "meal":
                    mt = s.get("meal_type")
                    if mt not in MEAL_TYPES:
                        errors.append("unknown enum meal_type: %s (seg %s)" % (mt, sid))
                elif stype != "free":
                    errors.append("unknown segment type: %s (seg %s)" % (stype, sid))

    # 预算
    bb = plan.get("budget_breakdown")
    if not isinstance(bb, dict):
        errors.append("missing field: budget_breakdown")
    else:
        for k in ("transport", "accommodation", "ticket", "meal", "contingency", "total"):
            if k not in bb:
                errors.append("missing field: budget_breakdown.%s" % k)
        total_budget = meta.get("total_budget") if isinstance(meta, dict) else None
        parts = {k: bb.get(k, 0) for k in ("transport", "accommodation", "ticket", "meal", "contingency")}
        try:
            s_sum = sum(float(v) for v in parts.values())
        except Exception:
            s_sum = None
        if s_sum is not None and "total" in bb and abs(float(bb["total"]) - s_sum) > 0.01:
            errors.append("budget breakdown mismatch: parts sum %s != total %s" % (s_sum, bb["total"]))
        if total_budget is not None and isinstance(bb.get("total"), (int, float)):
            if float(bb["total"]) > float(total_budget) + 0.01:
                errors.append("budget exceeded: total %s > limit %s" % (bb["total"], total_budget))
            else:
                tier = meta.get("budget_tier")
                if tier in BUDGET_RATIOS and float(total_budget) > 0:
                    rt, ra, rk, rm, rc = BUDGET_RATIOS[tier]
                    limits = {"transport": rt, "accommodation": ra, "ticket": rk, "meal": rm}
                    for k, v in limits.items():
                        val = float(parts.get(k, 0))
                        if val > float(total_budget) * v + 0.01:
                            warnings.append("budget ratio warning: %s %.0f > %d%% of budget" % (k, val, int(v * 100)))
                    cont = float(parts.get("contingency", 0))
                    if cont < float(total_budget) * rc - 0.01:
                        warnings.append("contingency < %d%% of budget: %.0f" % (int(rc * 100), cont))

    # data_source_note 默认
    dsn = plan.get("data_source_note")
    if dsn not in ("realtime", "estimate"):
        plan["data_source_note"] = "estimate"
        warnings.append("data_source_note defaulted to 'estimate'")

    # 归一化：按 start_time 排序 segments
    for day in plan.get("days", []):
        if isinstance(day, dict) and isinstance(day.get("segments"), list):
            day["segments"].sort(key=lambda s: (to_min(s.get("start_time")) if isinstance(s, dict) else 0) or 0)

    # 输出：警告（stderr，不致命）；错误（stderr，exit 2）
    for w in warnings:
        print("WARNING: %s" % w, file=sys.stderr)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(2)

    out_json = json.dumps(plan, ensure_ascii=False, indent=2)
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(out_json)
        except Exception as e:
            print("unexpected error writing out: %s" % e, file=sys.stderr)
            sys.exit(1)
    else:
        print(out_json)
    sys.exit(0)


if __name__ == "__main__":
    main()
