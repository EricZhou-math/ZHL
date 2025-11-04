import json
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA_JSON = BASE / 'dashboard' / 'data.json'
DB_PATH = BASE / 'db' / 'zhl.sqlite3'

SCHEMA = {
    'tables': [
        # 指标表
        '''CREATE TABLE IF NOT EXISTS indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            unit TEXT,
            ref_lower REAL,
            ref_upper REAL
        )''',
        # 日期表（便于规范化和复用）
        '''CREATE TABLE IF NOT EXISTS dates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL
        )''',
        # 度量数据表
        '''CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator_id INTEGER NOT NULL,
            date_id INTEGER NOT NULL,
            value REAL,
            status TEXT,
            flag TEXT,
            phase TEXT,
            FOREIGN KEY (indicator_id) REFERENCES indicators(id),
            FOREIGN KEY (date_id) REFERENCES dates(id),
            UNIQUE(indicator_id, date_id)
        )''',
        # 元数据：起始日期与周期长度
        '''CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )'''
    ]
}

def ensure_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    for ddl in SCHEMA['tables']:
        cur.execute(ddl)
    conn.commit()

def upsert_date(conn, date_str: str) -> int:
    cur = conn.cursor()
    cur.execute('INSERT OR IGNORE INTO dates(date) VALUES(?)', (date_str,))
    cur.execute('SELECT id FROM dates WHERE date=?', (date_str,))
    return cur.fetchone()[0]

def upsert_indicator(conn, name: str, unit: str, ref: dict) -> int:
    ref_lower = ref.get('lower') if isinstance(ref, dict) else None
    ref_upper = ref.get('upper') if isinstance(ref, dict) else None
    cur = conn.cursor()
    cur.execute(
        'INSERT OR IGNORE INTO indicators(name, unit, ref_lower, ref_upper) VALUES(?,?,?,?)',
        (name, unit, ref_lower, ref_upper)
    )
    # 若已存在，更新单位与参考范围
    cur.execute('UPDATE indicators SET unit=?, ref_lower=?, ref_upper=? WHERE name=?',
                (unit, ref_lower, ref_upper, name))
    cur.execute('SELECT id FROM indicators WHERE name=?', (name,))
    return cur.fetchone()[0]

def migrate():
    if not DATA_JSON.exists():
        raise FileNotFoundError(f'data.json not found: {DATA_JSON}')
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(DATA_JSON, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema(conn)
        cur = conn.cursor()

        # meta
        start_date = payload.get('start_date')
        cycle_length_days = payload.get('cycle_length_days')
        cur.execute('INSERT OR REPLACE INTO meta(key, value) VALUES(?,?)', ('start_date', start_date or ''))
        cur.execute('INSERT OR REPLACE INTO meta(key, value) VALUES(?,?)', ('cycle_length_days', str(cycle_length_days or '')))

        # dates
        dates = payload.get('dates', [])
        for d in dates:
            upsert_date(conn, d)

        # indicators and measurements
        indicators = payload.get('indicators', {})
        for name, info in indicators.items():
            unit = info.get('unit') or ''
            ref = info.get('ref') or {}
            ind_id = upsert_indicator(conn, name, unit, ref)

            series = info.get('series', [])
            for pt in series:
                date = pt.get('date')
                date_id = upsert_date(conn, date)
                value = pt.get('value')
                status = pt.get('status')
                flag = pt.get('flag')
                phase = pt.get('phase')
                cur.execute(
                    'INSERT OR REPLACE INTO measurements(indicator_id, date_id, value, status, flag, phase) VALUES(?,?,?,?,?,?)',
                    (ind_id, date_id, value, status, flag, phase)
                )

        conn.commit()
        print(f'Migrated to {DB_PATH}')
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()