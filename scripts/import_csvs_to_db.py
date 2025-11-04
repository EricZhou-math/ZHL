import csv
import re
import sqlite3
from pathlib import Path
from datetime import datetime
from io import StringIO
import unicodedata

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / 'db' / 'zhl.sqlite3'
CSV_DIR = BASE / 'origin_ocr_csv_files'

DATE_FORMATS = [
    # 仅日期
    '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y%m%d',
    # 含时间
    '%Y-%m-%d %H:%M', '%Y/%m/%d %H:%M', '%Y.%m.%d %H:%M',
    # 美式月/日/年（两位或四位年），可能带时间
    '%m/%d/%y', '%m/%d/%Y', '%m/%d/%y %H:%M', '%m/%d/%Y %H:%M'
]

def normalize_date(s: str) -> str:
    s = (s or '').strip()
    # 先尝试常见格式
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
    # 兼容类似 "10/24/25 8:45" 的写法：提取日期部分并规范为 YYYY-MM-DD
    m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', s)
    if m:
        mm, dd, yy = m.groups()
        year = int(yy)
        if year < 100:
            year = 2000 + year
        try:
            dt = datetime(year, int(mm), int(dd))
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
    # 回退：原样返回（后续逻辑会丢弃空日期）
    return s

def parse_float(value: str):
    if value is None:
        return None
    text = str(value).strip()
    try:
        return float(text)
    except Exception:
        # try to extract first number
        m = re.search(r'[-+]?\d*\.\d+|[-+]?\d+', text)
        if m:
            try:
                return float(m.group(0))
            except Exception:
                return None
        return None

def parse_ref_range(s: str):
    if not s:
        return None, None
    text = str(s)
    nums = re.findall(r'[-+]?\d*\.\d+|[-+]?\d+', text)
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    elif len(nums) == 1:
        # 仅一个数，视为上限或下限，另一端为空
        v = float(nums[0])
        return None, v
    return None, None

# 常见检验项目别名到标准名称映射（可逐步扩展）
INDICATOR_SYNONYMS = {
    # 白细胞
    'wbc': '白细胞计数', '白细胞': '白细胞计数', '白细胞数': '白细胞计数', '白细胞计数': '白细胞计数',
    # 中性粒细胞
    'neut#': '中性粒细胞计数', 'neut%': '中性粒细胞百分数', '中性粒细胞计数': '中性粒细胞计数',
    '中性粒细胞百分比': '中性粒细胞百分数', '中性粒细胞%': '中性粒细胞百分数', '中性细胞计数': '中性粒细胞计数',
    '中性细胞百分数': '中性粒细胞百分数',
    # 补充：同义名称归并（ANC、绝对值）
    '中性粒细胞绝对值': '中性粒细胞计数', 'anc': '中性粒细胞计数',
    # 淋巴细胞
    'lymph#': '淋巴细胞计数', 'lymph%': '淋巴细胞百分数', 'lym#': '淋巴细胞计数', 'lym%': '淋巴细胞百分数',
    '淋巴细胞数': '淋巴细胞计数', '淋巴细胞比率': '淋巴细胞百分数', '淋巴细胞%': '淋巴细胞百分数',
    # 嗜酸性粒细胞
    'eo#': '嗜酸性粒细胞计数', 'eo%': '嗜酸性粒细胞百分数', '嗜酸细胞计数': '嗜酸性粒细胞计数',
    '嗜酸细胞百分比': '嗜酸性粒细胞百分数', '嗜酸粒细胞计数': '嗜酸性粒细胞计数', '嗜酸粒细胞百分比': '嗜酸性粒细胞百分数',
    # 嗜碱性粒细胞
    'baso#': '嗜碱性粒细胞计数', 'baso%': '嗜碱性粒细胞百分数', '嗜碱细胞计数': '嗜碱性粒细胞计数',
    '嗜碱细胞百分比': '嗜碱性粒细胞百分数', '嗜碱粒细胞计数': '嗜碱性粒细胞计数', '嗜碱粒细胞百分比': '嗜碱性粒细胞百分数',
    # 单核细胞
    'mono#': '单核细胞计数', 'mono%': '单核细胞百分数', '单核细胞数': '单核细胞计数', '单核细胞比率': '单核细胞百分数',
    # 红细胞
    'rbc': '红细胞计数', '红细胞数': '红细胞计数', '红细胞计数': '红细胞计数',
    # 血红蛋白/红细胞压积
    'hgb': '血红蛋白', 'hb': '血红蛋白', '血红蛋白': '血红蛋白', '血红蛋白浓度': '血红蛋白',
    'hct': '红细胞压积', '红细胞比容': '红细胞压积', '红细胞压积': '红细胞压积',
    # 红细胞指数
    'mcv': '平均红细胞体积', '平均红细胞体积': '平均红细胞体积',
    'mch': '平均红细胞血红蛋白含量', '平均红细胞血红蛋白含量': '平均红细胞血红蛋白含量', '平均红细胞血红蛋白量': '平均红细胞血红蛋白含量',
    'mchc': '平均红细胞血红蛋白浓度', '平均红细胞血红蛋白浓度': '平均红细胞血红蛋白浓度',
    # 血小板
    'plt': '血小板计数', '血小板数': '血小板计数', '血小板计数': '血小板计数',
    'mpv': '平均血小板体积', '平均血小板体积': '平均血小板体积',
    'pdw': '血小板分布宽度', '血小板分布宽度': '血小板分布宽度', '血小板体积分布宽度': '血小板分布宽度',
    'p-lcr': '大血小板比率', '大血小板比率': '大血小板比率',
    'pct': '血小板比容', '血小板比容': '血小板比容',
    # 有核红细胞
    'nrbc#': '有核红细胞计数', 'nrbc%': '有核红细胞百分数', '有核红细胞计数': '有核红细胞计数',
    # RDW（红细胞体积分布宽度）
    '红细胞分布宽度CV': '红细胞分布宽度变异系数', '红细胞分布宽度SD': '红细胞分布宽度标准差',
    'rdw-cv': '红细胞分布宽度变异系数', 'rdw-sd': '红细胞分布宽度标准差', 'rdw sd': '红细胞分布宽度标准差',
}

STAR_RE = re.compile(r'[★☆＊*※✱﹡]')

def canonical_indicator_name(name: str) -> str:
    if not name:
        return ''
    s = unicodedata.normalize('NFKC', name).strip()
    # 去除星标/特殊标记
    s = STAR_RE.sub('', s)
    # 去除常见“新版/标星”等无关括注
    s = re.sub(r'（[^）]*?(?:新版|星标|标星)[^）]*）', '', s)
    s = re.sub(r'\([^)]*?(?:新版|星标|标星)[^)]*\)', '', s)
    s = s.strip()
    # 如果包含代码，如 NEUT# / NEUT% / LYM% 等，统一识别
    token = s.upper().replace(' ', '')
    for code in ['NEUT#', 'NEUT%', 'LYMPH#', 'LYMPH%', 'LYM#', 'LYM%', 'EO#', 'EO%', 'BASO#', 'BASO%', 'MONO#', 'MONO%', 'NRBC#', 'NRBC%', 'WBC', 'RBC', 'HGB', 'HCT', 'MCH', 'MCHC', 'MCV', 'PLT', 'MPV', 'PDW', 'P-LCR', 'PCT', 'ANC', 'RDW-CV', 'RDW-SD']:
        if code in token:
            key = code.lower()
            return INDICATOR_SYNONYMS.get(key, s)
    # 直接别名映射（中文/英文）
    key = s.lower()
    return INDICATOR_SYNONYMS.get(key, s)

def ensure_schema(conn: sqlite3.Connection):
    # 复用已存在的表结构（由 migrate_to_db.py 创建）
    cur = conn.cursor()
    cur.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="indicators"')
    if cur.fetchone() is None:
        raise RuntimeError('Database schema not found. Please run migrate_to_db.py first.')

def upsert_date(conn, date_str: str) -> int:
    cur = conn.cursor()
    cur.execute('INSERT OR IGNORE INTO dates(date) VALUES(?)', (date_str,))
    cur.execute('SELECT id FROM dates WHERE date=?', (date_str,))
    row = cur.fetchone()
    return row[0]

def upsert_indicator(conn, name: str, unit: str, ref_lower, ref_upper) -> int:
    cur = conn.cursor()
    cur.execute('INSERT OR IGNORE INTO indicators(name, unit, ref_lower, ref_upper) VALUES(?,?,?,?)',
                (name, unit, ref_lower, ref_upper))
    # 谨慎更新：仅在原值为空时覆盖单位或参考范围，避免冲突
    cur.execute('SELECT unit, ref_lower, ref_upper FROM indicators WHERE name=?', (name,))
    row = cur.fetchone()
    if row:
        old_unit, old_lower, old_upper = row
        if (not old_unit) and unit:
            cur.execute('UPDATE indicators SET unit=? WHERE name=?', (unit, name))
        # 若参考值缺失且新值提供，才更新
        if (old_lower is None and old_upper is None) and (ref_lower is not None or ref_upper is not None):
            cur.execute('UPDATE indicators SET ref_lower=?, ref_upper=? WHERE name=?', (ref_lower, ref_upper, name))
    cur.execute('SELECT id FROM indicators WHERE name=?', (name,))
    return cur.fetchone()[0]

def import_csvs():
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema(conn)
        cur = conn.cursor()
        files = sorted([p for p in CSV_DIR.glob('*.csv')])
        if not files:
            print(f'No CSV files found in {CSV_DIR}')
            return
        total_rows = 0
        for fpath in files:
            print(f'Importing {fpath.name}...')
            # 兼容不同编码和分隔符
            encodings = ['utf-8-sig', 'utf-8', 'gbk', 'gb18030']
            reader_obj = None
            delim = ','
            for enc in encodings:
                try:
                    with open(fpath, 'r', encoding=enc) as f:
                        sample = f.read(4096)
                        try:
                            dialect = csv.Sniffer().sniff(sample)
                            delim = dialect.delimiter
                        except Exception:
                            delim = ','
                    # 重新打开并创建 DictReader
                    f = open(fpath, 'r', encoding=enc)
                    reader_obj = csv.DictReader(f, delimiter=delim)
                    # 检查是否有字段名
                    if reader_obj.fieldnames and len(reader_obj.fieldnames) > 0:
                        # 保存文件句柄以便迭代
                        file_handle = f
                        break
                    else:
                        f.close()
                except Exception:
                    continue

            if reader_obj is None:
                print(f'  Skipped {fpath.name}: cannot read CSV with supported encodings')
                continue

            # 映射字段名（兼容不同表头写法）
            def find_key(keys, candidates):
                for k in keys:
                    ks = (k or '').strip()
                    for c in candidates:
                        if c in ks:
                            return k
                return None

            keys = reader_obj.fieldnames
            date_key = find_key(keys, ['报告日期', '日期', '采集时间', '采集日期', '检验时间', '检验日期', '时间'])
            name_key = find_key(keys, ['检测指标', '项目', '项目名称', '检验项目'])
            value_key = find_key(keys, ['结果', '数值'])
            status_key = find_key(keys, ['状态'])
            ref_key = find_key(keys, ['参考值', '参考范围', '参考区间'])
            unit_key = find_key(keys, ['单位'])

            # 聚合：同日同项目去重与优选
            rows_map = {}
            def select_better(old, new):
                if old is None:
                    return new
                # 优先保留数值有效的记录
                old_num = isinstance(old.get('value'), (int, float))
                new_num = isinstance(new.get('value'), (int, float))
                if new_num and not old_num:
                    return new
                if old_num and not new_num:
                    return old
                # 都是数值：优先保留带上下箭头标记的（信息量更高），否则取最新
                old_flag = old.get('flag')
                new_flag = new.get('flag')
                def score(flag):
                    return 1 if flag in ('↑', '↓') else 0
                if score(new_flag) > score(old_flag):
                    return new
                return new  # 默认后来的覆盖

            for row in reader_obj:
                date_raw = (row.get(date_key) if date_key else '').strip()
                date_str = normalize_date(date_raw)
                raw_name = (row.get(name_key) if name_key else '').strip()
                ind_name = canonical_indicator_name(raw_name)
                value = parse_float(row.get(value_key) if value_key else None)
                status = (row.get(status_key) if status_key else '').strip()
                flag = status
                unit = (row.get(unit_key) if unit_key else '').strip()
                ref_lower, ref_upper = parse_ref_range(row.get(ref_key) if ref_key else None)

                if not ind_name or not date_str:
                    continue

                key = (ind_name, date_str)
                rec = {
                    'value': value,
                    'status': status,
                    'flag': flag,
                    'unit': unit,
                    'ref_lower': ref_lower,
                    'ref_upper': ref_upper,
                }
                rows_map[key] = select_better(rows_map.get(key), rec)

            # 写入数据库
            for (ind_name, date_str), rec in rows_map.items():
                date_id = upsert_date(conn, date_str)
                ind_id = upsert_indicator(conn, ind_name, rec['unit'], rec['ref_lower'], rec['ref_upper'])
                cur.execute('''
                    INSERT OR REPLACE INTO measurements(indicator_id, date_id, value, status, flag, phase)
                    VALUES(?,?,?,?,?,?)
                ''', (ind_id, date_id, rec['value'], rec['status'], rec['flag'], None))
                total_rows += 1

        conn.commit()
        print(f'Imported {total_rows} rows from {len(files)} files.')
    finally:
        conn.close()

if __name__ == '__main__':
    import_csvs()