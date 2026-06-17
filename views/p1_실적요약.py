import datetime
import pandas as pd
from data.loader import load_sheet
from data.config import (
    Sheets,
    AT_국내_사업장,
    CORP_ORDER, 재무_CORP_ORDER, 재무_사업장_표시명,
    현금_CORP_ORDER, 현금_사업장_표시명, 현금_구분_순서,
    재무_소계행,
    SONIK_구분_순서, SONIK_표시명, SONIK_단위, SONIK_소수점, SONIK_PCT_대상,
    품목_구분_순서, 품목_단위, 품목_소수점, 품목_PCT_대상, 품목_PCT_소수점, 품목_PCT_품목, 품목_품목_순서,
)
from views.common import (
    parse as _parse, fmt as _fmt, pct as _pct,
    prev_month as _prev, drop_empty as _drop_empty, sort_by_order as _sort_corps,
    TH as _TH, TD_LBL as _TD_LBL, TD_NUM as _TD_NUM, TD_RED as _TD_RED,
    html_table as _html_table, memo_html as _memo_html, layout64 as _layout64,
)

_기호 = ['①', '②', '③', '④', '⑤', '⑥']


def _월헤더(year, month):
    return f"'{str(year)[2:]}년 {month}월"


def _당월헤더(year, month, n):
    return f"'{str(year)[2:]}.{month}월 {''.join(_기호[:n])}"


def _to_html_table(df):
    rows_html = ''
    for idx, row in df.iterrows():
        bg    = ';background:#f9f9fb' if idx % 2 == 1 else ''
        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if i == 0:
                cells += f'<td style="{_TD_LBL}{bg}">{s}</td>'
            elif s.startswith('-'):
                cells += f'<td style="{_TD_RED}{bg}">{s}</td>'
            else:
                cells += f'<td style="{_TD_NUM}{bg}">{s}</td>'
        rows_html += f'<tr>{cells}</tr>'

    headers = ''.join(f'<th style="{_TH}">{c}</th>' for c in df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)


def _section(title, table_df, memo='', unit='[단위: 만개, 백만원, %]'):
    return _layout64(title, _to_html_table(table_df), memo, unit)


def _재무_to_html_table(df, 소계행, 헤더행):
    depths    = df['_depth'].tolist() if '_depth' in df.columns else [1] * len(df)
    render_df = df.drop(columns=['_depth'], errors='ignore')

    td_hdr_num = 'background:#ede9f7;border-bottom:1px solid #d6ccee'
    td_sub_num = 'padding:5px 10px;text-align:right;background:#f0edf8;font-weight:600;border-bottom:1px solid #e2e8f0'
    td_sub_red = td_sub_num + ';color:#e53e3e'
    _pad    = {0: '8px',  1: '20px', 2: '36px'}
    _prefix = {0: '',     1: '&nbsp;&nbsp;&nbsp;', 2: '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'}

    rows_html = ''
    for (idx, row), depth in zip(render_df.iterrows(), depths):
        d      = int(depth) if str(depth).lstrip('-').isdigit() else 1
        label  = str(row.iloc[0])
        is_hdr = label in 헤더행
        is_sub = label in 소계행
        bg     = 'background:#f9f9fb' if (idx % 2 == 1 and not is_hdr and not is_sub) else ''
        pad    = _pad.get(d, '20px')
        prefix = _prefix.get(d, '&nbsp;&nbsp;&nbsp;')

        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if is_hdr:
                lbl_st = (f'padding:4px 8px;padding-left:{pad};text-align:left;'
                          f'background:#ede9f7;font-weight:700;color:#5a3e8a;'
                          f'border-bottom:1px solid #d6ccee')
                cells += (f'<td style="{lbl_st}">{prefix}{s}</td>' if i == 0
                          else f'<td style="{td_hdr_num}"></td>')
            elif i == 0:
                if is_sub:
                    lbl_st = (f'padding:5px 8px;padding-left:{pad};text-align:left;'
                              f'background:#f0edf8;font-weight:600;'
                              f'border-bottom:1px solid #e2e8f0')
                else:
                    lbl_st = (f'padding:5px 8px;padding-left:{pad};text-align:left;'
                              f'border-bottom:1px solid #e2e8f0;{bg}')
                cells += f'<td style="{lbl_st}">{prefix}{s}</td>'
            elif s.startswith('-'):
                cells += f'<td style="{td_sub_red if is_sub else _TD_RED+";"+bg}">{s}</td>'
            else:
                cells += f'<td style="{td_sub_num if is_sub else _TD_NUM+";"+bg}">{s}</td>'
        rows_html += f'<tr>{cells}</tr>'

    headers = ''.join(f'<th style="{_TH}">{c}</th>' for c in render_df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)


def _재무_section(title, per_corp_dfs, 소계행, 헤더행, corp_labels, memo='', unit='[단위: 백만원]'):
    safe = [c.replace(' ', '_') for c in corp_labels]

    hide_sel = ', '.join(f'#fp_{s}' for s in safe)
    css = f'{hide_sel}{{display:none}}'
    for s in safe:
        css += (f'#ft_{s}:checked~#fp_{s}{{display:block!important}}'
                f'#ft_{s}:checked~.ftbar>#fl_{s}'
                f'{{background:#6b46c1!important;color:white!important;border-color:#6b46c1!important}}')

    inputs = ''.join(
        f'<input type="radio" id="ft_{s}" name="ftab" {"checked" if i == 0 else ""} '
        f'style="position:absolute;opacity:0;pointer-events:none">'
        for i, s in enumerate(safe)
    )

    tab_bar = '<div class="ftbar" style="display:flex;margin-bottom:6px;border-bottom:2px solid #6b46c1">'
    tab_bar += ''.join(
        f'<label id="fl_{s}" for="ft_{s}" style="padding:5px 16px;cursor:pointer;'
        f'border:1px solid #d0c8e8;border-bottom:none;margin-right:2px;'
        f'font-size:0.9em;font-weight:500;border-radius:4px 4px 0 0;'
        f'background:white;color:#555">{corp}</label>'
        for corp, s in zip(corp_labels, safe)
    )
    tab_bar += '</div>'

    panels = ''.join(
        f'<div id="fp_{s}">{_재무_to_html_table(per_corp_dfs[corp], 소계행, 헤더행)}</div>'
        for corp, s in zip(corp_labels, safe)
    )

    tab_html = f'<style>{css}</style>' + inputs + tab_bar + panels
    return _layout64(title, tab_html, memo, unit)


def _build_현금전환주기_table(year, month):
    df = load_sheet(Sheets.현금전환주기_DB)
    df['값']  = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    yr_전기, mo_전기 = year - 1, 12
    yr_전월, mo_전월 = _prev(year, month, 1)

    db_corps    = _sort_corps(df['사업장'].unique().tolist(), 현금_CORP_ORDER)
    corp_labels = [현금_사업장_표시명.get(c, c) for c in db_corps]

    sub_labels = [
        f"'{str(year - 1)[2:]}년",
        f"'{str(yr_전월)[2:]}.{mo_전월}월",
        f"{month}월",
        '전월비',
    ]

    val_map = df.set_index(['연도', '월', '사업장', '구분1'])['값'].to_dict()

    def 값(yr, mo, corp, 항목):
        return val_map.get((yr, mo, corp, 항목), 0.0)

    rows = []
    for db_corp, corp_disp in zip(db_corps, corp_labels):
        for i, 항목 in enumerate(현금_구분_순서):
            전기_v = 값(yr_전기, mo_전기, db_corp, 항목)
            전월_v = 값(yr_전월, mo_전월, db_corp, 항목)
            당월_v = 값(year,    month,   db_corp, 항목)
            rows.append({
                '사업장':       corp_disp,
                '_first':       i == 0,
                '구분':         항목,
                sub_labels[0]:  _fmt(전기_v),
                sub_labels[1]:  _fmt(전월_v),
                sub_labels[2]:  _fmt(당월_v),
                sub_labels[3]:  _fmt(당월_v - 전월_v),
            })

    return rows, sub_labels


def _현금_to_html_table(rows, sub_labels):
    headers = (f'<th style="{_TH}">사업장</th>'
               f'<th style="{_TH}">구분</th>'
               + ''.join(f'<th style="{_TH}">{h}</th>' for h in sub_labels))

    rows_html = ''
    group_idx = -1
    for row in rows:
        is_first = row['_first']
        if is_first:
            group_idx += 1

        grp_bg = '#f9f9fb' if group_idx % 2 == 1 else '#ffffff'
        sep    = 'border-top:2px solid #9f7aea;' if (is_first and group_idx > 0) else ''
        b_bot  = 'border-bottom:1px solid #e2e8f0'

        corp_val = row['사업장'] if is_first else ''
        corp_fw  = 'font-weight:700;' if is_first else ''
        cells    = (f'<td style="padding:6px 12px;text-align:center;{corp_fw}'
                    f'background:{grp_bg};{sep}{b_bot}">{corp_val}</td>')

        cells += (f'<td style="padding:5px 10px;text-align:left;'
                  f'background:{grp_bg};{sep}{b_bot}">{row["구분"]}</td>')

        for h in sub_labels:
            s      = str(row[h])
            color  = ';color:#e53e3e' if s.startswith('-') else ''
            cells += (f'<td style="padding:5px 10px;text-align:right;'
                      f'background:{grp_bg};{sep}{b_bot}{color}">{s}</td>')

        rows_html += f'<tr>{cells}</tr>'

    return _html_table(f'<tr>{headers}</tr>', rows_html)


def _build_매출채권현황_table(year, month):
    df = load_sheet(Sheets.매출채권현황_DB)
    df['실적'] = df['실적'].apply(_parse)
    df = _drop_empty(df, '연도', '월')
    df['구분2'] = df['구분2'].fillna('').astype(str).str.strip()

    yr_전전기, mo_전전기 = year - 2, 12
    yr_전기,   mo_전기   = year - 1, 12
    yr_전월,   mo_전월   = _prev(year, month, 1)

    sub_labels = [
        f"'{str(year-2)[2:]}.12월",
        f"'{str(year-1)[2:]}.12월",
        f"'{str(yr_전월)[2:]}.{mo_전월}월",
        f"{month}월",
        f"'{str(year-1)[2:]}년대비",
        '전월대비',
    ]

    val_map = df.set_index(['연도', '월', '구분1', '구분2'])['실적'].to_dict()

    def 값(yr, mo, g1, g2=''):
        return val_map.get((yr, mo, g1, g2), 0.0)

    target = df[(df['연도'] == year) & (df['월'] == month)]
    if target.empty:
        최신 = df[['연도', '월']].drop_duplicates().sort_values(['연도', '월']).iloc[-1]
        target = df[(df['연도'] == 최신['연도']) & (df['월'] == 최신['월'])]
    행_순서 = list(dict.fromkeys(zip(target['구분1'], target['구분2'])))

    rows   = []
    소계행 = set()
    헤더행 = set()

    for g1, g2 in 행_순서:
        if g2 == '':
            if g1 == '합계':
                label, depth = '합계', 0
                소계행.add(label)
            else:
                label = g1.replace(' 계', '')
                depth = 1
                소계행.add(label)
        else:
            label, depth = g2, 2

        전전기_v = 값(yr_전전기, mo_전전기, g1, g2)
        전기_v   = 값(yr_전기,   mo_전기,   g1, g2)
        전월_v   = 값(yr_전월,   mo_전월,   g1, g2)
        당월_v   = 값(year,      month,     g1, g2)

        rows.append({
            '구분':         label,
            '_depth':       depth,
            sub_labels[0]:  _fmt(전전기_v),
            sub_labels[1]:  _fmt(전기_v),
            sub_labels[2]:  _fmt(전월_v),
            sub_labels[3]:  _fmt(당월_v),
            sub_labels[4]:  _fmt(당월_v - 전기_v),
            sub_labels[5]:  _fmt(당월_v - 전월_v),
        })

    columns   = ['구분', '_depth'] + sub_labels
    result_df = pd.DataFrame({col: [r.get(col, '') for r in rows] for col in columns})
    return result_df, 소계행, 헤더행


def _build_품목손익_table(year, month):
    df = load_sheet(Sheets.품목손익_DB)
    df['값']  = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    db_품목   = df['구분2'].unique().tolist()
    품목_cols = [p for p in 품목_품목_순서 if p in db_품목]
    for p in db_품목:
        if p not in 품목_cols:
            품목_cols.append(p)

    val_map = df.set_index(['연도', '월', '구분1', '구분2'])['값'].to_dict()

    def 값(g1, g2):
        return val_map.get((year, month, g1, g2), 0.0)

    def total(g1):
        return sum(값(g1, p) for p in 품목_cols)

    rows     = []
    매출액_v = {}

    for g in 품목_구분_순서:
        div    = 품목_단위[g]
        dec    = 품목_소수점.get(g, 0)
        tot_v  = total(g)
        품목_v = {p: 값(g, p) for p in 품목_cols}

        if g == '매출액':
            매출액_v = {'합계': tot_v, **품목_v}

        row = {'구분': g, '합계': _fmt(tot_v / div, decimal=dec)}
        row.update({p: _fmt(품목_v[p] / div, decimal=dec) for p in 품목_cols})
        rows.append(row)

        if g in 품목_PCT_대상 and 매출액_v.get('합계'):
            pct = {'구분': '%',
                   '합계': _fmt(_pct(tot_v, 매출액_v['합계']),
                                is_pct=True, decimal=품목_PCT_소수점)}
            for p in 품목_cols:
                if p in 품목_PCT_품목 and 매출액_v.get(p, 0):
                    pct[p] = _fmt(_pct(품목_v[p], 매출액_v[p]),
                                  is_pct=True, decimal=품목_PCT_소수점)
                else:
                    pct[p] = '-'
            rows.append(pct)

    columns = ['구분', '합계'] + 품목_cols
    return pd.DataFrame({col: [r.get(col, '') for r in rows] for col in columns})


def _build_원재료단가변동_table(year, month):
    df = load_sheet(Sheets.원재료단가변동_DB)
    df = _drop_empty(df, '연도', '월')
    df['당월 입고량(톤)'] = df['당월 입고량(톤)'].apply(_parse)
    df['전월 단가']       = df['전월 단가'].apply(_parse)
    df['당월 단가']       = df['당월 단가'].apply(_parse)

    target = df[(df['연도'] == year) & (df['월'] == month)]

    yr_전월, mo_전월 = _prev(year, month, 1)
    전월_col = f"'{str(yr_전월)[2:]}.{mo_전월}월"
    당월_col = f"{month}월"
    columns  = ['구분1', '구분2', '구분3', '입고량(톤)', 전월_col, 당월_col, '단가차이', '금액(백만원)']

    rows    = []
    금액_합 = 0.0

    for _, row in target.iterrows():
        입고량  = row['당월 입고량(톤)']
        전월단가 = row['전월 단가']
        당월단가 = row['당월 단가']
        차이    = 당월단가 - 전월단가
        금액    = 차이 * 입고량 / 1000
        금액_합 += 금액

        rows.append({
            '구분1':      str(row['구분1']),
            '구분2':      str(row['구분2']),
            '구분3':      str(row['구분3']),
            '입고량(톤)': _fmt(입고량, decimal=1),
            전월_col:     _fmt(전월단가),
            당월_col:     _fmt(당월단가),
            '단가차이':   _fmt(차이),
            '금액(백만원)': _fmt(금액, decimal=1),
        })

    rows.append({
        '구분1': '계', '구분2': '', '구분3': '',
        '입고량(톤)': '', 전월_col: '', 당월_col: '', '단가차이': '',
        '금액(백만원)': _fmt(금액_합, decimal=1),
    })

    return pd.DataFrame({col: [r.get(col, '') for r in rows] for col in columns})


def _원재료_to_html_table(df):
    sub_lbl = _TD_LBL + ';background:#f0edf8;font-weight:600'
    sub_num = _TD_NUM + ';background:#f0edf8;font-weight:600'
    sub_red = sub_num + ';color:#e53e3e'

    headers   = ''.join(f'<th style="{_TH}">{c}</th>' for c in df.columns)
    rows_html = ''
    for idx, row in df.iterrows():
        bg     = ';background:#f9f9fb' if idx % 2 == 1 else ''
        is_sub = str(row.iloc[0]) == '계'
        cells  = ''
        for i, val in enumerate(row):
            s   = str(val)
            neg = s.startswith('-')
            if is_sub:
                style = (sub_red if neg else sub_num) if i >= 3 else sub_lbl
            elif i < 3:
                style = _TD_LBL + bg
            else:
                style = (_TD_RED if neg else _TD_NUM) + bg
            cells += f'<td style="{style}">{s}</td>'
        rows_html += f'<tr>{cells}</tr>'

    return _html_table(f'<tr>{headers}</tr>', rows_html)


# ── 데이터 로드 ───────────────────────────────────────────────

def _load_손익():
    df = load_sheet(Sheets.손익_DB)
    df['값']  = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    사업장_list = _sort_corps(df['사업장'].unique().tolist(), CORP_ORDER)

    def get(계실, yr, mo, 장=None, 구분=None):
        m = (df['계획/실적'] == 계실) & (df['연도'] == yr) & (df['월'] == mo)
        if 장:   m &= df['사업장'] == 장
        if 구분: m &= df['구분1']  == 구분
        return df[m]['값'].sum()

    return get, 사업장_list


def _get_연도_목록():
    df = load_sheet(Sheets.손익_DB)
    return sorted(pd.to_numeric(df['연도'], errors='coerce').dropna().astype(int).unique().tolist())


def _get_memo(sheet_info, year, month) -> str:
    df = load_sheet(sheet_info)
    df['연도'] = df['연도'].astype(str).str.strip()
    df['월']   = df['월'].astype(str).str.strip()
    row = df[(df['연도'] == str(year)) & (df['월'] == str(month))]
    return str(row.iloc[0]['메모']) if not row.empty else ''


# ── 테이블 빌더 ───────────────────────────────────────────────

def _build_포함_table(get, 사업장_list, year, month):
    yr1, mo1 = _prev(year, month, 2)
    yr2, mo2 = _prev(year, month, 1)

    전전월_col = _월헤더(yr1, mo1)
    전월_col   = _월헤더(yr2, mo2)
    당월_col   = _당월헤더(year, month, len(사업장_list))
    장_cols    = [f"{장} {_기호[i]}" for i, 장 in enumerate(사업장_list)]
    columns    = ['구분', 전전월_col, 전월_col, '계획', 당월_col] + 장_cols + ['전월대비', '계획대비']

    rows, 매출 = [], {}

    for g in SONIK_구분_순서:
        div      = SONIK_단위[g]
        dec      = SONIK_소수점.get(g, 0)
        전전월_v = get('실적', yr1, mo1, 구분=g)
        전월_v   = get('실적', yr2, mo2, 구분=g)
        계획_v   = get('계획', year, month, 구분=g)
        장별     = {장: get('실적', year, month, 장=장, 구분=g) for 장 in 사업장_list}
        당월_v   = sum(장별.values())

        if g == '매출':
            매출 = {'전전월': 전전월_v, '전월': 전월_v, '계획': 계획_v, '당월': 당월_v, **장별}

        rows.append({
            '구분':     SONIK_표시명[g],
            전전월_col: _fmt(전전월_v / div, decimal=dec),
            전월_col:   _fmt(전월_v   / div, decimal=dec),
            '계획':     _fmt(계획_v   / div, decimal=dec),
            당월_col:   _fmt(당월_v   / div, decimal=dec),
            '전월대비': _fmt((당월_v - 전월_v) / div, decimal=dec),
            '계획대비': _fmt((당월_v - 계획_v) / div, decimal=dec),
            **{장_cols[i]: _fmt(장별[장] / div, decimal=dec) for i, 장 in enumerate(사업장_list)},
        })

        if g in SONIK_PCT_대상 and 매출.get('당월'):
            전전월_p = _pct(전전월_v, 매출['전전월'])
            전월_p   = _pct(전월_v,   매출['전월'])
            계획_p   = _pct(계획_v,   매출['계획'])
            당월_p   = _pct(당월_v,   매출['당월'])
            rows.append({
                '구분':     '%',
                전전월_col: _fmt(전전월_p,        is_pct=True),
                전월_col:   _fmt(전월_p,          is_pct=True),
                '계획':     _fmt(계획_p,          is_pct=True),
                당월_col:   _fmt(당월_p,          is_pct=True),
                '전월대비': _fmt(당월_p - 전월_p,  is_pct=True),
                '계획대비': _fmt(당월_p - 계획_p,  is_pct=True),
                **{장_cols[i]: _fmt(_pct(장별[장], 매출.get(장, 0)), is_pct=True)
                   for i, 장 in enumerate(사업장_list)},
            })

    return pd.DataFrame({col: [r.get(col, '') for r in rows] for col in columns})


def _build_국내_table(get, year, month, 사업장=AT_국내_사업장):
    yr2, mo2 = _prev(year, month, 1)
    전월_col  = _월헤더(yr2, mo2)

    columns = ['구분', 전월_col,
               '당월_계획', '당월_실적', '당월_계획대비', '당월_전월대비',
               '누적_계획', '누적_실적', '누적_계획대비']

    rows, 매출 = [], {}

    for g in SONIK_구분_순서:
        div      = SONIK_단위[g]
        dec      = SONIK_소수점.get(g, 0)
        전월_v   = get('실적', yr2, mo2, 장=사업장, 구분=g)
        당월계획  = get('계획', year, month, 장=사업장, 구분=g)
        당월실적  = get('실적', year, month, 장=사업장, 구분=g)
        누적계획  = sum(get('계획', year, m, 장=사업장, 구분=g) for m in range(1, month + 1))
        누적실적  = sum(get('실적', year, m, 장=사업장, 구분=g) for m in range(1, month + 1))

        if g == '매출':
            매출 = {'전월': 전월_v, '당월계획': 당월계획, '당월실적': 당월실적,
                    '누적계획': 누적계획, '누적실적': 누적실적}

        rows.append({
            '구분':          SONIK_표시명[g],
            전월_col:        _fmt(전월_v             / div, decimal=dec),
            '당월_계획':     _fmt(당월계획            / div, decimal=dec),
            '당월_실적':     _fmt(당월실적            / div, decimal=dec),
            '당월_계획대비': _fmt((당월실적 - 당월계획) / div, decimal=dec),
            '당월_전월대비': _fmt((당월실적 - 전월_v)   / div, decimal=dec),
            '누적_계획':     _fmt(누적계획            / div, decimal=dec),
            '누적_실적':     _fmt(누적실적            / div, decimal=dec),
            '누적_계획대비': _fmt((누적실적 - 누적계획) / div, decimal=dec),
        })

        if g in SONIK_PCT_대상 and 매출.get('당월실적'):
            전월_p     = _pct(전월_v,    매출['전월'])
            당월계획_p  = _pct(당월계획, 매출['당월계획'])
            당월실적_p  = _pct(당월실적, 매출['당월실적'])
            누적계획_p  = _pct(누적계획, 매출['누적계획'])
            누적실적_p  = _pct(누적실적, 매출['누적실적'])
            rows.append({
                '구분':          '%',
                전월_col:        _fmt(전월_p,                   is_pct=True),
                '당월_계획':     _fmt(당월계획_p,               is_pct=True),
                '당월_실적':     _fmt(당월실적_p,               is_pct=True),
                '당월_계획대비': _fmt(당월실적_p - 당월계획_p,  is_pct=True),
                '당월_전월대비': _fmt(당월실적_p - 전월_p,      is_pct=True),
                '누적_계획':     _fmt(누적계획_p,               is_pct=True),
                '누적_실적':     _fmt(누적실적_p,               is_pct=True),
                '누적_계획대비': _fmt(누적실적_p - 누적계획_p,  is_pct=True),
            })

    return pd.DataFrame({col: [r.get(col, '') for r in rows] for col in columns})


def _build_재무상태표_table(year, month):
    df = load_sheet(Sheets.재무상태표_DB)
    df['값']  = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')
    df['구분3'] = df['구분3'].fillna('').astype(str).str.strip()

    yr_전기, mo_전기 = year - 1, 12
    yr_전월, mo_전월 = _prev(year, month, 1)

    db_corps    = _sort_corps(df['사업장'].unique().tolist(), 재무_CORP_ORDER)
    corp_labels = [재무_사업장_표시명.get(c, c) for c in db_corps]

    sub_labels = [
        f"'{str(year - 1)[2:]}년",
        f"'{str(yr_전월)[2:]}.{mo_전월}월",
        f"{month}월",
        '전월비',
    ]

    anchor  = df[(df['연도'] == year) & (df['월'] == month) & (df['사업장'] == db_corps[0])]
    행_순서 = list(dict.fromkeys(zip(anchor['구분1'], anchor['구분2'], anchor['구분3'])))

    # 반복 필터 대신 O(1) 조회 dict
    val_map = df.set_index(['연도', '월', '구분1', '구분2', '구분3', '사업장'])['값'].to_dict()

    def 값(yr, mo, g1, g2, g3, 장):
        return val_map.get((yr, mo, g1, g2, g3, 장), 0.0)

    columns = ['구분', '_depth'] + sub_labels
    소계행  = 재무_소계행
    헤더행  = set()
    빈행    = {col: '' for col in columns}

    # g3 서브행만 있고 부모 행(empty g3)이 없는 (g1,g2) → 합산 행 자동 삽입
    has_empty_g3 = {(g1, g2) for g1, g2, g3 in 행_순서 if not g3}
    sub_g3_map   = {}
    for g1, g2, g3 in 행_순서:
        if g3:
            sub_g3_map.setdefault((g1, g2), []).append(g3)

    _SUM = '__SUM__'
    행_순서_aug, seen = [], set()
    for g1, g2, g3 in 행_순서:
        key = (g1, g2)
        if g3 and key not in has_empty_g3 and key not in seen:
            행_순서_aug.append((g1, g2, _SUM))
            seen.add(key)
        행_순서_aug.append((g1, g2, g3))

    per_corp_dfs = {}
    for db_corp, corp_disp in zip(db_corps, corp_labels):
        rows    = []
        prev_g1 = None
        for g1, g2, g3 in 행_순서_aug:
            if g1 != prev_g1 and g1 != g2:
                rows.append({**빈행, '구분': g1, '_depth': 0})
                헤더행.add(g1)
            prev_g1 = g1

            if g3 == _SUM:
                label   = g2
                depth   = 1
                g3_list = sub_g3_map[(g1, g2)]
                전기_v  = sum(값(yr_전기, mo_전기, g1, g2, gv, db_corp) for gv in g3_list)
                전월_v  = sum(값(yr_전월, mo_전월, g1, g2, gv, db_corp) for gv in g3_list)
                당월_v  = sum(값(year,    month,   g1, g2, gv, db_corp) for gv in g3_list)
            else:
                label   = g3 if g3 else g2
                depth   = 2 if g3 else (0 if g1 == g2 else 1)
                전기_v  = 값(yr_전기, mo_전기, g1, g2, g3, db_corp)
                전월_v  = 값(yr_전월, mo_전월, g1, g2, g3, db_corp)
                당월_v  = 값(year,    month,   g1, g2, g3, db_corp)

            rows.append({
                '구분':        label,
                '_depth':      depth,
                sub_labels[0]: _fmt(전기_v),
                sub_labels[1]: _fmt(전월_v),
                sub_labels[2]: _fmt(당월_v),
                sub_labels[3]: _fmt(당월_v - 전월_v),
            })
        per_corp_dfs[corp_disp] = pd.DataFrame(
            {col: [r.get(col, '') for r in rows] for col in columns}
        )

    return per_corp_dfs, 소계행, 헤더행, corp_labels


# ── 페이지 렌더 ───────────────────────────────────────────────

def render_page(app):
    today     = datetime.date.today()
    연도_목록 = _get_연도_목록()

    with app.sidebar:
        app.divider()
        app.subheader("조회 기간")
        default_year_idx = 연도_목록.index(today.year) if today.year in 연도_목록 else len(연도_목록) - 1
        year_state  = app.selectbox("연도", 연도_목록, index=default_year_idx)
        month_state = app.selectbox("월", list(range(1, 13)), index=today.month - 1)

    def _render_title():
        app.title(f"{int(year_state.value)}년 {int(month_state.value)}월 실적요약")
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["주요경영지표(해외법인 포함)", "주요경영지표(AT_국내)"])

    with tabs[0]:
        def _render_포함():
            year, month = int(year_state.value), int(month_state.value)
            get, 사업장_list = _load_손익()

            memo1 = _get_memo(Sheets.손익_메모, year, month)
            app.markdown(_section("1) 손익", _build_포함_table(get, 사업장_list, year, month), memo1),
                         unsafe_allow_html=True)

            per_corp_dfs, 소계행, 헤더행, corp_labels = _build_재무상태표_table(year, month)
            memo2 = _get_memo(Sheets.재무상태표_메모, year, month)
            app.markdown(_재무_section("2) 재무상태표", per_corp_dfs, 소계행, 헤더행, corp_labels, memo2),
                         unsafe_allow_html=True)

            rows_현금, sub_현금 = _build_현금전환주기_table(year, month)
            memo3 = _get_memo(Sheets.현금전환주기_메모, year, month)
            app.markdown(_layout64("3) 현금전환주기",
                                   _현금_to_html_table(rows_현금, sub_현금),
                                   memo3, '[단위: 일]'),
                         unsafe_allow_html=True)

            df_채권, 소계행_채권, 헤더행_채권 = _build_매출채권현황_table(year, month)
            memo4 = _get_memo(Sheets.매출채권현황_메모, year, month)
            app.markdown(_layout64("4) 매출채권현황",
                                   _재무_to_html_table(df_채권, 소계행_채권, 헤더행_채권),
                                   memo4, '[단위: 백만원]'),
                         unsafe_allow_html=True)

            df_품목 = _build_품목손익_table(year, month)
            memo5 = _get_memo(Sheets.품목손익_메모, year, month)
            app.markdown(_section("5) 품목손익", df_품목, memo5),
                         unsafe_allow_html=True)

            df_원재료 = _build_원재료단가변동_table(year, month)
            memo6 = _get_memo(Sheets.원재료단가변동_메모, year, month)
            app.markdown(_layout64("6) 원재료 단가변동",
                                   _원재료_to_html_table(df_원재료),
                                   memo6, '[단위: 톤, 원/kg, 백만원]'),
                         unsafe_allow_html=True)
        app.If(lambda: True, _render_포함)

    with tabs[1]:
        def _render_국내():
            year, month = int(year_state.value), int(month_state.value)
            get, _ = _load_손익()
            memo = _get_memo(Sheets.손익_국내_메모, year, month)
            app.markdown(_section("1) 손익_전월비/계획비", _build_국내_table(get, year, month), memo),
                         unsafe_allow_html=True)
        app.If(lambda: True, _render_국내)
