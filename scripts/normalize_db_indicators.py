import sqlite3
import re
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / 'db' / 'zhl.sqlite3'

STAR_RE = re.compile(r'[★☆＊*※✱﹡]')

# 与导入脚本保持一致的别名映射
INDICATOR_SYNONYMS = {
    'wbc': '白细胞计数', '白细胞': '白细胞计数', '白细胞数': '白细胞计数', '白细胞计数': '白细胞计数',
    'neut#': '中性粒细胞计数', 'neut%': '中性粒细胞百分数', '中性粒细胞计数': '中性粒细胞计数',
    '中性粒细胞百分比': '中性粒细胞百分数', '中性粒细胞%': '中性粒细胞百分数', '中性细胞计数': '中性粒细胞计数',
    '中性细胞百分数': '中性粒细胞百分数',
    # 补充：同义名称归并
    '中性粒细胞绝对值': '中性粒细胞计数', 'anc': '中性粒细胞计数',
    '淋巴细胞绝对值': '淋巴细胞计数',
    '单核细胞绝对值': '单核细胞计数',
    '嗜酸性粒细胞绝对值': '嗜酸性粒细胞计数',
    '嗜碱性粒细胞绝对值': '嗜碱性粒细胞计数',
    '有核红细胞绝对值': '有核红细胞计数',
    'lymph#': '淋巴细胞计数', 'lymph%': '淋巴细胞百分数', 'lym#': '淋巴细胞计数', 'lym%': '淋巴细胞百分数',
    '淋巴细胞数': '淋巴细胞计数', '淋巴细胞比率': '淋巴细胞百分数', '淋巴细胞%': '淋巴细胞百分数',
    'eo#': '嗜酸性粒细胞计数', 'eo%': '嗜酸性粒细胞百分数', '嗜酸细胞计数': '嗜酸性粒细胞计数',
    '嗜酸细胞百分比': '嗜酸性粒细胞百分数', '嗜酸粒细胞计数': '嗜酸性粒细胞计数', '嗜酸粒细胞百分比': '嗜酸性粒细胞百分数',
    'baso#': '嗜碱性粒细胞计数', 'baso%': '嗜碱性粒细胞百分数', '嗜碱细胞计数': '嗜碱性粒细胞计数',
    '嗜碱细胞百分比': '嗜碱性粒细胞百分数', '嗜碱粒细胞计数': '嗜碱性粒细胞计数', '嗜碱粒细胞百分比': '嗜碱性粒细胞百分数',
    'mono#': '单核细胞计数', 'mono%': '单核细胞百分数', '单核细胞数': '单核细胞计数', '单核细胞比率': '单核细胞百分数',
    'rbc': '红细胞', '红细胞数': '红细胞', '红细胞计数': '红细胞', '红细胞': '红细胞',
    'hgb': '血红蛋白', 'hb': '血红蛋白', '血红蛋白': '血红蛋白', '血红蛋白浓度': '血红蛋白',
    'hct': '红细胞压积', '红细胞比容': '红细胞压积', '红细胞压积': '红细胞压积',
    'mcv': '平均红细胞体积', '平均红细胞体积': '平均红细胞体积',
    'mch': '平均红细胞血红蛋白含量', '平均红细胞血红蛋白含量': '平均红细胞血红蛋白含量', '平均红细胞血红蛋白量': '平均红细胞血红蛋白含量',
    'mchc': '平均红细胞血红蛋白浓度', '平均红细胞血红蛋白浓度': '平均红细胞血红蛋白浓度',
    'plt': '血小板计数', '血小板数': '血小板计数', '血小板计数': '血小板计数',
    'mpv': '平均血小板体积', '平均血小板体积': '平均血小板体积',
    'pdw': '血小板分布宽度', '血小板分布宽度': '血小板分布宽度', '血小板体积分布宽度': '血小板分布宽度',
    'p-lcr': '大血小板比率', '大血小板比率': '大血小板比率',
    'pct': '血小板比容', '血小板比容': '血小板比容',
    'nrbc#': '有核红细胞计数', 'nrbc%': '有核红细胞百分数', '有核红细胞计数': '有核红细胞计数',
    # RDW 同义项
    '红细胞分布宽度CV': '红细胞分布宽度变异系数', '红细胞分布宽度SD': '红细胞分布宽度标准差',
    'rdw-cv': '红细胞分布宽度变异系数', 'rdw-sd': '红细胞分布宽度标准差', 'rdw sd': '红细胞分布宽度标准差',
}

def canonical_indicator_name(name: str) -> str:
    if not name:
        return ''
    s = unicodedata.normalize('NFKC', name).strip()
    s = STAR_RE.sub('', s)
    s = re.sub(r'（[^）]*?(?:新版|星标|标星)[^）]*）', '', s)
    s = re.sub(r'\([^)]*?(?:新版|星标|标星)[^)]*\)', '', s)
    s = s.strip()
    token = s.upper().replace(' ', '')
    for code in ['NEUT#', 'NEUT%', 'LYMPH#', 'LYMPH%', 'LYM#', 'LYM%', 'EO#', 'EO%', 'BASO#', 'BASO%', 'MONO#', 'MONO%', 'NRBC#', 'NRBC%', 'WBC', 'RBC', 'HGB', 'HCT', 'MCH', 'MCHC', 'MCV', 'PLT', 'MPV', 'PDW', 'P-LCR', 'PCT', 'ANC', 'RDW-CV', 'RDW-SD']:
        if code in token:
            key = code.lower()
            return INDICATOR_SYNONYMS.get(key, s)
    key = s.lower()
    return INDICATOR_SYNONYMS.get(key, s)

def score_record(flag):
    return 1 if flag in ('↑', '↓') else 0

def normalize_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute('SELECT id, name, unit, ref_lower, ref_upper FROM indicators')
        inds = cur.fetchall()
        moved_count = 0
        deleted_inds = 0

        for ind in inds:
            ind_id = ind['id']
            name = ind['name']
            canon = canonical_indicator_name(name)
            if canon == name:
                continue

            # 找到或创建目标标准指标
            cur.execute('SELECT id, unit, ref_lower, ref_upper FROM indicators WHERE name=?', (canon,))
            target = cur.fetchone()
            if target:
                tgt_id = target['id']
                tgt_unit, tgt_lower, tgt_upper = target['unit'], target['ref_lower'], target['ref_upper']
                # 填补缺失的单位与参考范围
                updates = []
                if (not tgt_unit) and ind['unit']:
                    updates.append(('unit', ind['unit']))
                if (tgt_lower is None and tgt_upper is None) and (ind['ref_lower'] is not None or ind['ref_upper'] is not None):
                    updates.append(('ref', (ind['ref_lower'], ind['ref_upper'])))
                if updates:
                    if any(u[0] == 'unit' for u in updates):
                        cur.execute('UPDATE indicators SET unit=? WHERE id=?', (ind['unit'], tgt_id))
                    if any(u[0] == 'ref' for u in updates):
                        cur.execute('UPDATE indicators SET ref_lower=?, ref_upper=? WHERE id=?', (ind['ref_lower'], ind['ref_upper'], tgt_id))
            else:
                cur.execute('INSERT INTO indicators(name, unit, ref_lower, ref_upper) VALUES(?,?,?,?)',
                            (canon, ind['unit'], ind['ref_lower'], ind['ref_upper']))
                tgt_id = cur.lastrowid

            # 迁移测量数据：同日冲突时进行优选
            cur.execute('''
                SELECT m.id as mid, d.date as date, m.value as value, m.status as status, m.flag as flag, m.phase as phase
                FROM measurements m JOIN dates d ON m.date_id = d.id
                WHERE m.indicator_id = ?
            ''', (ind_id,))
            src_rows = cur.fetchall()
            for r in src_rows:
                # 目标是否已有同日记录
                cur.execute('''
                    SELECT m.id as mid, d.date as date, m.value as value, m.status as status, m.flag as flag, m.phase as phase
                    FROM measurements m JOIN dates d ON m.date_id = d.id
                    WHERE m.indicator_id = ? AND d.date = ?
                ''', (tgt_id, r['date']))
                tgt_row = cur.fetchone()
                # 获取该日期 id
                cur.execute('SELECT id FROM dates WHERE date=?', (r['date'],))
                date_id = cur.fetchone()['id']
                if not tgt_row:
                    # 直接插入到目标
                    cur.execute('''
                        INSERT OR REPLACE INTO measurements(indicator_id, date_id, value, status, flag, phase)
                        VALUES(?,?,?,?,?,?)
                    ''', (tgt_id, date_id, r['value'], r['status'], r['flag'], r['phase']))
                else:
                    # 优选覆盖策略
                    tgt_is_num = isinstance(tgt_row['value'], (int, float))
                    src_is_num = isinstance(r['value'], (int, float))
                    choose_src = False
                    if src_is_num and not tgt_is_num:
                        choose_src = True
                    elif src_is_num and tgt_is_num:
                        if score_record(r['flag']) > score_record(tgt_row['flag']):
                            choose_src = True
                        else:
                            choose_src = True  # 默认用来源记录更新（认为来源更近）
                    elif not src_is_num and not tgt_is_num:
                        # 都非数值，优先带箭头
                        if score_record(r['flag']) > score_record(tgt_row['flag']):
                            choose_src = True
                    if choose_src:
                        cur.execute('''
                            UPDATE measurements SET value=?, status=?, flag=?, phase=?
                            WHERE id=?
                        ''', (r['value'], r['status'], r['flag'], r['phase'], tgt_row['mid']))
                # 删除源记录
                cur.execute('DELETE FROM measurements WHERE id=?', (r['mid'],))
                moved_count += 1

            # 删除源指标
            cur.execute('DELETE FROM indicators WHERE id=?', (ind_id,))
            deleted_inds += 1

        conn.commit()
        print(f'Moved {moved_count} measurements; deleted {deleted_inds} starred/aliased indicators.')
    finally:
        conn.close()

if __name__ == '__main__':
    normalize_db()