import json
import sqlite3
from pathlib import Path
from datetime import datetime
import re

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / 'db' / 'zhl.sqlite3'
OUT_JSON_DASH = BASE / 'dashboard' / 'data.json'
OUT_JSON_DOCS = BASE / 'docs' / 'data.json'

# 指标同义词归并：将“绝对值/绝对数”归整到“计数”
NAME_SYNONYMS = {
    '中性粒细胞绝对值': '中性粒细胞计数',
    '淋巴细胞绝对值': '淋巴细胞计数',
    '单核细胞绝对值': '单核细胞计数',
    '嗜酸性粒细胞绝对值': '嗜酸性粒细胞计数',
    '嗜碱性粒细胞绝对值': '嗜碱性粒细胞计数',
    '有核红细胞绝对值': '有核红细胞计数',
    # RBC 归并到“红细胞”
    'rbc': '红细胞',
    '红细胞数': '红细胞',
    '红细胞计数': '红细胞',
}

def canonical_name(name: str) -> str:
    name = (name or '').strip()
    return NAME_SYNONYMS.get(name, name)

def normalize_date_str(s: str) -> str:
    s = (s or '').strip()
    if not s:
        return s
    # 支持 ISO 与非零填充格式：YYYY-M-D [HH:MM[:SS]]
    m = re.match(r'^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:\s+(\d{1,2})(?::(\d{1,2})(?::(\d{1,2}))?)?)?$', s)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        try:
            dt = datetime(int(y), int(mo), int(d))
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
    # 备用：尝试常见格式
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y%m%d', '%m/%d/%y', '%m/%d/%Y'):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            continue
    return s

def date_key(s: str):
    s2 = normalize_date_str(s)
    try:
        return datetime.strptime(s2, '%Y-%m-%d')
    except Exception:
        return datetime.max

def export_payload() -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute('SELECT key, value FROM meta')
        meta = {row['key']: row['value'] for row in cur.fetchall()}

        cur.execute('SELECT date FROM dates')
        dates_raw = [row['date'] for row in cur.fetchall()]
        dates = sorted({normalize_date_str(d) for d in dates_raw}, key=lambda x: date_key(x))

        cur.execute('SELECT id, name, unit, ref_lower, ref_upper FROM indicators ORDER BY name')
        inds = cur.fetchall()
        indicators = {}
        for ind in inds:
            ind_id = ind['id']
            name = ind['name']
            canon = canonical_name(name)
            unit = ind['unit'] or ''
            ref = {}
            if ind['ref_lower'] is not None or ind['ref_upper'] is not None:
                lower = ind['ref_lower']
                upper = ind['ref_upper']
                if isinstance(upper, (int, float)) and upper < 0:
                    upper = abs(upper)
                if isinstance(lower, (int, float)) and isinstance(upper, (int, float)) and lower > upper:
                    lower, upper = upper, lower
                ref = {
                    'lower': lower,
                    'upper': upper
                }

            cur.execute('''
                SELECT d.date as date, m.value as value, m.status as status, m.flag as flag, m.phase as phase
                FROM measurements m JOIN dates d ON m.date_id = d.id
                WHERE m.indicator_id = ?
            ''', (ind_id,))
            rows = cur.fetchall()
            # 统一日期并排序
            rows = sorted(rows, key=lambda r: date_key(r['date']))

            def derive_flag_status(val, r):
                # 根据参考范围自动推断异常标记；当原标记缺失或为空时应用
                if val is None or not isinstance(val, (int, float)):
                    return None, None
                lower = r.get('lower') if isinstance(r, dict) else None
                upper = r.get('upper') if isinstance(r, dict) else None
                if lower is not None and val < lower:
                    return '↓', '↓'
                if upper is not None and val > upper:
                    return '↑', '↑'
                # 在有范围且正常时，返回 '-' 以便前端着色为正常
                if lower is not None or upper is not None:
                    return '-', '-'
                return None, None

            series = []
            for row in rows:
                s = {
                    'date': normalize_date_str(row['date']),
                    'value': row['value'],
                    'status': row['status'],
                    'flag': row['flag'],
                    'phase': row['phase']
                }
                # 如果 flag/status 为空或缺失，则根据参考范围与数值推断
                if (not s['flag']) or (s['flag'] == ''):
                    auto_flag, auto_status = derive_flag_status(s['value'], ref)
                    if auto_flag:
                        s['flag'] = auto_flag
                    if auto_status:
                        s['status'] = auto_status
                series.append(s)
            # 初始去重：同一天保留信息量更高的点
            by_date_initial = {}
            for pt in series:
                ex = by_date_initial.get(pt['date'])
                if not ex:
                    by_date_initial[pt['date']] = pt
                else:
                    e_num = isinstance(ex.get('value'), (int, float))
                    s_num = isinstance(pt.get('value'), (int, float))
                    choose_src = False
                    if s_num and not e_num:
                        choose_src = True
                    elif s_num and e_num:
                        e_score = 1 if (ex.get('flag') in {'↑', '↓'}) else 0
                        s_score = 1 if (pt.get('flag') in {'↑', '↓'}) else 0
                        if s_score >= e_score:
                            choose_src = True
                    if choose_src:
                        by_date_initial[pt['date']] = pt
            series = [by_date_initial[d] for d in sorted(by_date_initial.keys(), key=date_key)]
            # 合并到 canonical 指标名（避免同义词重复导致数据分散）
            if canon not in indicators:
                indicators[canon] = {
                    'unit': unit,
                    'ref': ref,
                    'series': series
                }
            else:
                # 单位：优先已有，否则用当前
                if not indicators[canon].get('unit') and unit:
                    indicators[canon]['unit'] = unit
                # 参考范围：选择更完整（同时具备上下限）的那一个
                existing_ref = indicators[canon].get('ref') or {}
                def is_ref_complete(r):
                    return isinstance(r, dict) and (r.get('lower') is not None) and (r.get('upper') is not None)
                if not is_ref_complete(existing_ref) and is_ref_complete(ref):
                    indicators[canon]['ref'] = ref
                # series 合并：按日期取并集，优先保留数值型与带有异常标志的点
                by_date = {pt['date']: pt for pt in indicators[canon].get('series', [])}
                for pt in series:
                    ex = by_date.get(pt['date'])
                    if not ex:
                        by_date[pt['date']] = pt
                    else:
                        e_num = isinstance(ex.get('value'), (int, float))
                        s_num = isinstance(pt.get('value'), (int, float))
                        choose_src = False
                        if s_num and not e_num:
                            choose_src = True
                        elif s_num and e_num:
                            e_score = 1 if (ex.get('flag') in {'↑', '↓'}) else 0
                            s_score = 1 if (pt.get('flag') in {'↑', '↓'}) else 0
                            if s_score >= e_score:
                                choose_src = True
                        if choose_src:
                            by_date[pt['date']] = pt
                indicators[canon]['series'] = [by_date[d] for d in sorted(by_date.keys(), key=date_key)]

        payload = {
            'start_date': meta.get('start_date'),
            'cycle_length_days': int(meta.get('cycle_length_days')) if meta.get('cycle_length_days') else None,
            'dates': dates,
            'indicators': indicators
        }
        return payload
    finally:
        conn.close()

def export_to_json():
    payload = export_payload()
    # 写入 dashboard/data.json
    OUT_JSON_DASH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON_DASH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'Exported to {OUT_JSON_DASH}')
    # 同步写入 docs/data.json 以便静态预览无需后端
    OUT_JSON_DOCS.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON_DOCS, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'Exported to {OUT_JSON_DOCS}')

if __name__ == '__main__':
    export_to_json()