import json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent
DOCS = BASE / 'docs' / 'data.json'
DASH = BASE / 'dashboard' / 'data.json'

def parse_date(s: str):
    return datetime.strptime(s, '%Y-%m-%d')

def run_checks(path: Path):
    data = json.loads(path.read_text(encoding='utf-8'))
    dates = data.get('dates') or []
    assert all(len(d) == 10 and d[4] == '-' and d[7] == '-' for d in dates), '日期未统一为YYYY-MM-DD'
    dates_sorted = sorted(dates, key=parse_date)
    assert dates == dates_sorted, 'dates顺序错误'
    inds = data.get('indicators') or {}
    # 至少对最新日期进行检查
    if dates:
        last = dates[-1]
        for name, obj in inds.items():
            series = obj.get('series') or []
            for pt in series:
                if pt.get('date') == last:
                    flag = (pt.get('flag') or '').strip()
                    if flag:
                        assert flag in {'-', '↑', '↓'}, f'flag不规范: {flag}'

def main():
    run_checks(DOCS)
    run_checks(DASH)
    print('Data integrity checks passed')

if __name__ == '__main__':
    main()