#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import csv
import json
import os
import re
from collections import defaultdict, Counter
from datetime import datetime, date

SRC_PATH = "/Users/ericzhou/MyStudio/Trae_projects/ZHL/化疗周期血常规数据.csv"
OUT_DIR = "/Users/ericzhou/MyStudio/Trae_projects/ZHL/data_processed"
DASHBOARD_DATA_PATH = "/Users/ericzhou/MyStudio/Trae_projects/ZHL/dashboard/data.json"
CHEMO_START_DATE = date(2025, 8, 8)
CYCLE_LENGTH_DAYS = 21

os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DASHBOARD_DATA_PATH), exist_ok=True)

FIELDS = ["报告单号", "报告日期", "检测指标", "结果", "状态", "参考值", "单位"]

REF_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*~\s*([0-9]+(?:\.[0-9]+)?)\s*$")


def parse_date(s: str) -> str:
    # normalize to YYYY-MM-DD
    s = s.strip()
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.date().isoformat()
    except ValueError:
        # try YYYY.MM.DD
        try:
            dt = datetime.strptime(s, "%Y.%m.%d")
            return dt.date().isoformat()
        except ValueError:
            return s  # fallback


def parse_value(s: str):
    s = s.strip()
    if s == "" or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        # some cells might contain non-numeric; keep as string
        return s


def parse_ref_interval(ref_str: str):
    if not ref_str:
        return None
    ref_str = ref_str.strip()
    m = REF_RE.match(ref_str)
    if not m:
        return None
    lower = float(m.group(1))
    upper = float(m.group(2))
    return lower, upper


def chemo_phase_label(d: date) -> str:
    # returns like "第一次化疗d5" etc.
    delta_days = (d - CHEMO_START_DATE).days
    if delta_days < 0:
        # before first cycle, label as "首次化疗前"
        return "首次化疗前"
    cycle = delta_days // CYCLE_LENGTH_DAYS + 1
    day_in_cycle = (delta_days % CYCLE_LENGTH_DAYS) + 1
    return f"第{cycle}次化疗d{day_in_cycle}"


def load_rows():
    rows = []
    with open(SRC_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        # Validate header
        if reader.fieldnames != FIELDS:
            # try to map by position if header differs slightly
            mapping = {FIELDS[i]: name for i, name in enumerate(reader.fieldnames or [])}
        for r in reader:
            # normalize fields
            rec = {key: r.get(key, "").strip() for key in FIELDS}
            rows.append(rec)
    return rows


def process():
    rows = load_rows()
    # Collect sets
    indicators = []
    indicator_set = set()
    dates = set()

    # Data map: (indicator, date) -> {value, status, unit, ref_str}
    data_map = {}

    # For ref and unit unification
    unit_counter_by_ind = defaultdict(Counter)
    ref_counter_by_ind = defaultdict(Counter)

    for r in rows:
        ind = r["检测指标"].strip()
        dt_str = parse_date(r["报告日期"])  # normalized
        val = parse_value(r["结果"])  # float or str
        status = r["状态"].strip()
        ref_str = r["参考值"].strip()
        unit = r["单位"].strip()

        if ind not in indicator_set:
            indicator_set.add(ind)
            indicators.append(ind)
        dates.add(dt_str)

        key = (ind, dt_str)
        data_map[key] = {
            "value": val,
            "status": status,
            "unit": unit,
            "ref_str": ref_str,
        }
        if unit:
            unit_counter_by_ind[ind][unit] += 1
        if ref_str and parse_ref_interval(ref_str):
            ref_counter_by_ind[ind][ref_str] += 1

    sorted_dates = sorted(list(dates))

    # Build unified ref per indicator
    unified_ref = {}
    unified_unit = {}
    for ind in indicators:
        # unit: most common
        if unit_counter_by_ind[ind]:
            unit_common = unit_counter_by_ind[ind].most_common(1)[0][0]
        else:
            unit_common = ""
        unified_unit[ind] = unit_common

        # ref: most common parseable interval
        ref_common = None
        if ref_counter_by_ind[ind]:
            ref_common = ref_counter_by_ind[ind].most_common(1)[0][0]
        ref_interval = parse_ref_interval(ref_common) if ref_common else None
        unified_ref[ind] = {
            "ref_str": ref_common,
            "lower": ref_interval[0] if ref_interval else None,
            "upper": ref_interval[1] if ref_interval else None,
        }

    # Write pivot CSV
    pivot_path = os.path.join(OUT_DIR, "化疗周期血常规数据_透视表.csv")
    with open(pivot_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        header = ["检测指标"] + sorted_dates
        writer.writerow(header)
        for ind in indicators:
            row = [ind]
            for dt_str in sorted_dates:
                entry = data_map.get((ind, dt_str))
                if not entry:
                    row.append("")
                else:
                    val = entry["value"]
                    # keep numeric as string for CSV
                    if isinstance(val, float):
                        row.append(f"{val}")
                    else:
                        row.append(f"{val}")
            writer.writerow(row)

    # Write abnormal-flag CSV
    abn_path = os.path.join(OUT_DIR, "化疗周期血常规数据_异常标记.csv")
    with open(abn_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        header = ["检测指标"] + sorted_dates
        writer.writerow(header)
        for ind in indicators:
            lower = unified_ref[ind]["lower"]
            upper = unified_ref[ind]["upper"]
            row = [ind]
            for dt_str in sorted_dates:
                entry = data_map.get((ind, dt_str))
                if not entry:
                    row.append("")
                    continue
                val = entry["value"]
                status = entry["status"]
                flag = "-"
                if isinstance(val, float) and lower is not None and upper is not None:
                    if val < lower:
                        flag = "↓"
                    elif val > upper:
                        flag = "↑"
                    else:
                        flag = "-"
                else:
                    # fallback to provided status
                    flag = status if status in {"-", "↑", "↓"} else "-"
                row.append(flag)
            writer.writerow(row)

    # Write unified reference ranges CSV
    ref_out_path = os.path.join(OUT_DIR, "参考区间标准化.csv")
    with open(ref_out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["检测指标", "参考下限", "参考上限", "单位", "参考值来源"])
        for ind in indicators:
            ur = unified_ref[ind]
            unit = unified_unit[ind]
            writer.writerow([
                ind,
                ur["lower"] if ur["lower"] is not None else "",
                ur["upper"] if ur["upper"] is not None else "",
                unit,
                ur["ref_str"] if ur["ref_str"] else "",
            ])

    # Build dashboard JSON
    dash = {
        "start_date": CHEMO_START_DATE.isoformat(),
        "cycle_length_days": CYCLE_LENGTH_DAYS,
        "dates": sorted_dates,
        "indicators": {},
    }

    # Prepare series per indicator
    for ind in indicators:
        unit = unified_unit[ind]
        ur = unified_ref[ind]
        series = []
        for dt_str in sorted_dates:
            entry = data_map.get((ind, dt_str))
            if not entry:
                continue
            val = entry["value"]
            status = entry["status"]
            # compute flag using unified ref when available
            lower = ur["lower"]
            upper = ur["upper"]
            flag = status if status in {"-", "↑", "↓"} else "-"
            if isinstance(val, float) and lower is not None and upper is not None:
                if val < lower:
                    flag = "↓"
                elif val > upper:
                    flag = "↑"
                else:
                    flag = "-"
            # phase
            try:
                d = datetime.strptime(dt_str, "%Y-%m-%d").date()
                phase = chemo_phase_label(d)
            except Exception:
                phase = ""
            series.append({
                "date": dt_str,
                "value": val,
                "status": status,
                "flag": flag,
                "phase": phase,
            })
        dash["indicators"][ind] = {
            "unit": unit,
            "ref": {
                "lower": ur["lower"],
                "upper": ur["upper"],
            },
            "series": series,
        }

    with open(DASHBOARD_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(dash, f, ensure_ascii=False, indent=2)

    print("Written:")
    print("-", pivot_path)
    print("-", abn_path)
    print("-", ref_out_path)
    print("-", DASHBOARD_DATA_PATH)


if __name__ == "__main__":
    process()