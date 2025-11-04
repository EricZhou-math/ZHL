from flask import Flask, jsonify
try:
    from flask_cors import CORS
    _HAS_CORS = True
except Exception:
    _HAS_CORS = False
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / 'db' / 'zhl.sqlite3'

app = Flask(__name__)
if _HAS_CORS:
    CORS(app)
else:
    @app.after_request
    def add_cors_headers(resp):
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp

def get_conn():
    return sqlite3.connect(DB_PATH)

@app.route('/api/data')
def api_data():
    conn = get_conn()
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # meta
        cur.execute('SELECT key, value FROM meta')
        meta_rows = cur.fetchall()
        meta = {row['key']: row['value'] for row in meta_rows}

        # dates
        cur.execute('SELECT date FROM dates ORDER BY date')
        dates = [row['date'] for row in cur.fetchall()]

        # indicators
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
                # 回退推断：当数据库缺失标记时，基于参考范围派生
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
        return jsonify(payload)
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)