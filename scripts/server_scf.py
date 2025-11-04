import json
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / 'db' / 'zhl.sqlite3'

def _query_payload():
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
            ref_lower = ind['ref_lower']
            ref_upper = ind['ref_upper']

            cur.execute('''
                SELECT d.date as date, m.value as value, m.status as status, m.flag as flag, m.phase as phase
                FROM measurements m JOIN dates d ON m.date_id = d.id
                WHERE m.indicator_id = ?
                ORDER BY d.date
            ''', (ind_id,))
            series = []
            for row in cur.fetchall():
                v = row['value']
                status = row['status']
                flag = row['flag']
                # 缺失标记时按参考范围派生，确保前端着色一致
                if (flag is None or str(flag).strip() == '') and v is not None and (ref_lower is not None or ref_upper is not None):
                    if ref_lower is not None and v < ref_lower:
                        flag = '↓'
                        status = status or '低'
                    elif ref_upper is not None and v > ref_upper:
                        flag = '↑'
                        status = status or '高'
                    else:
                        flag = '-'
                        status = status or '正常'
                series.append({
                    'date': row['date'],
                    'value': v,
                    'status': status,
                    'flag': flag,
                    'phase': row['phase']
                })

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

def _resp_json(data, status=200):
    body = json.dumps(data, ensure_ascii=False)
    return {
        'isBase64Encoded': False,
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        },
        'body': body
    }

def _resp_text(text, status=200):
    return {
        'isBase64Encoded': False,
        'statusCode': status,
        'headers': {
            'Content-Type': 'text/plain; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        },
        'body': text
    }

def main_handler(event, context):
    # Tencent SCF + API Gateway event shape
    method = (event.get('httpMethod') or 'GET').upper()
    path = event.get('path') or '/'
    if method == 'OPTIONS':
        return _resp_text('ok', 204)
    if path.endswith('/api/data'):
        try:
            payload = _query_payload()
            return _resp_json(payload)
        except Exception as e:
            return _resp_json({'error': str(e)}, 500)
    # default
    return _resp_text('ok')