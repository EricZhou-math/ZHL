import json
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / 'db' / 'zhl.sqlite3'
OUT_JSON = BASE / 'dashboard' / 'data.json'

def export_payload() -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute('SELECT key, value FROM meta')
        meta = {row['key']: row['value'] for row in cur.fetchall()}

        cur.execute('SELECT date FROM dates ORDER BY date')
        dates = [row['date'] for row in cur.fetchall()]

        cur.execute('SELECT id, name, unit, ref_lower, ref_upper FROM indicators ORDER BY name')
        inds = cur.fetchall()
        indicators = {}
        for ind in inds:
            ind_id = ind['id']
            name = ind['name']
            unit = ind['unit'] or ''
            ref = {}
            if ind['ref_lower'] is not None or ind['ref_upper'] is not None:
                ref = {
                    'lower': ind['ref_lower'],
                    'upper': ind['ref_upper']
                }

            cur.execute('''
                SELECT d.date as date, m.value as value, m.status as status, m.flag as flag, m.phase as phase
                FROM measurements m JOIN dates d ON m.date_id = d.id
                WHERE m.indicator_id = ?
                ORDER BY d.date
            ''', (ind_id,))
            rows = cur.fetchall()

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
                    'date': row['date'],
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

            indicators[name] = {
                'unit': unit,
                'ref': ref,
                'series': series
            }

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
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'Exported to {OUT_JSON}')

if __name__ == '__main__':
    export_to_json()