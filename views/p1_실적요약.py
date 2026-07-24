import datetime
import pandas as pd
from data.loader import load_sheet
from data.config import (
    Sheets,
    CORP_ORDER, 재무_CORP_ORDER, 재무_사업장_표시명,
    현금_CORP_ORDER, 현금_사업장_표시명, 현금_구분_순서,
    재무_소계행,
    SONIK_구분_순서, SONIK_표시명, SONIK_단위, SONIK_소수점, SONIK_PCT_대상,
    품목_구분_순서, 품목_단위, 품목_소수점, 품목_PCT_대상, 품목_PCT_소수점, 품목_PCT_품목, 품목_품목_순서,
    회전일_CORP_ORDER, 회전일_구분_순서, 회전일_사업장_표시명, 선재_국내_사업장, 현금_소계행
)
from views.common import (
    parse as _parse, fmt as _fmt, pct as _pct,
    prev_month as _prev, drop_empty as _drop_empty, sort_by_order as _sort_corps,
    C_NAVY as _C_NAVY, C_RED as _C_RED, C_LT_GRAY as _C_LT_GRAY,
    TH as _TH, TD_LBL as _TD_LBL, TD_NUM as _TD_NUM, TD_RED as _TD_RED,
    TD_SUB_LBL as _TD_SUB_LBL, TD_SUB_NUM as _TD_SUB_NUM, TD_SUB_RED as _TD_SUB_RED,
    html_table as _html_table, memo_html as _memo_html, layout64 as _layout64, layout100 as _layout100,
)

_기호 = ['①', '②', '③', '④', '⑤', '⑥']


def _월헤더(year, month):
    return f"'{str(year)[2:]}.{month}월"


def _당월헤더(year, month, n):
    return f"'{str(year)[2:]}.{month}월 {'+'.join(_기호[:n])}"


def _fmt_pct_diff(v):
    v = round(v, 1)
    if v > 0:
        return f"↑{v:.1f}%p"
    if v < 0:
        return f"↓{abs(v):.1f}%p"
    return f"{v:.1f}%p"


def _fmt_pct_val(v):
    v = round(v, 1)
    return f"-{abs(v):.1f}%" if v < 0 else f"{v:.1f}%"


def _to_html_table(df):
    rows_html = ''
    for idx, row in df.iterrows():
        bg    = f';background:{_C_LT_GRAY}' if idx % 2 == 1 else ''
        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if i == 0:
                cells += f'<td style="{_TD_LBL}{bg}">{s}</td>'
            elif s.startswith('-'):
                cells += f'<td style="{_TD_RED}{bg}">{s}</td>'
            else:
                cells += f'<td style="{_TD_NUM}{bg}">{s}</td>'
        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'

    headers = ''.join(f'<th style="{_TH}">{c}</th>' for c in df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)


def _section(title, table_df, memo='', unit='[단위: 톤, 백만원, %]'):
    return _layout64(title, _to_html_table(table_df), memo, unit)


def _재무_to_html_table(df, 소계행, 헤더행):
    depths    = df['_depth'].tolist() if '_depth' in df.columns else [1] * len(df)
    render_df = df.drop(columns=['_depth'], errors='ignore')

    _td_hdr_num = f'background:{_C_LT_GRAY};border-bottom:1px solid #DEE2E6'
    _pad    = {0: '8px',  1: '20px', 2: '36px'}
    _prefix = {0: '',     1: '&nbsp;&nbsp;&nbsp;', 2: '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'}

    rows_html = ''
    for (_, row), depth in zip(render_df.iterrows(), depths):
        d      = int(depth) if str(depth).lstrip('-').isdigit() else 1
        label  = str(row.iloc[0])
        is_hdr = label in 헤더행
        is_sub = label in 소계행
        bg     = ''
        pad    = _pad.get(d, '20px')
        prefix = _prefix.get(d, '&nbsp;&nbsp;&nbsp;')

        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if is_hdr:
                lbl_st = (f'padding:4px 8px;padding-left:{pad};text-align:left;'
                          f'background:{_C_LT_GRAY};font-weight:700;color:{_C_NAVY};'
                          f'border-bottom:1px solid #DEE2E6')
                cells += (f'<td style="{lbl_st}">{prefix}{s}</td>' if i == 0
                          else f'<td style="{_td_hdr_num}"></td>')
            elif i == 0:
                if is_sub:
                    lbl_st = (f'padding:5px 8px;padding-left:{pad};text-align:left;'
                              f'background:{_C_LT_GRAY};font-weight:600;'
                              f'border-bottom:1px solid #e2e8f0')
                else:
                    lbl_st = (f'padding:5px 8px;padding-left:{pad};text-align:left;'
                              f'border-bottom:1px solid #e2e8f0;{bg}')
                cells += f'<td style="{lbl_st}">{prefix}{s}</td>'
            elif s.startswith('-'):
                cells += f'<td style="{_TD_SUB_RED if is_sub else _TD_RED+";"+bg}">{s}</td>'
            else:
                cells += f'<td style="{_TD_SUB_NUM if is_sub else _TD_NUM+";"+bg}">{s}</td>'
        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'

    headers = ''.join(f'<th style="{_TH}">{c}</th>' for c in render_df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)


def _재무_section(title, per_corp_dfs, 소계행, 헤더행, corp_labels, memo='', unit='[단위: 백만원]'):
    safe = [c.replace(' ', '_').replace('(', '').replace(')', '') for c in corp_labels]
    prefix = "bs"  # 재무상태표 고유 접두사 (Balance Sheet)

    hide_sel = ', '.join(f'#fp_{prefix}_{s}' for s in safe)
    css = f'{hide_sel}{{display:none}}'
    for s in safe:
        css += (f'#ft_{prefix}_{s}:checked~#fp_{prefix}_{s}{{display:block!important}}'
                f'#ft_{prefix}_{s}:checked~.ftbar>#fl_{prefix}_{s}'
                f'{{background:{_C_NAVY}!important;color:white!important;border-color:{_C_NAVY}!important}}')

    inputs = ''.join(
        f'<input type="radio" id="ft_{prefix}_{s}" name="ftab_{prefix}" {"checked" if i == 0 else ""} '
        f'style="position:absolute;opacity:0;pointer-events:none">'
        for i, s in enumerate(safe)
    )

    tab_bar = f'<div class="ftbar" style="display:flex;margin-bottom:6px;border-bottom:2px solid {_C_NAVY}">'
    tab_bar += ''.join(
        f'<label id="fl_{prefix}_{s}" for="ft_{prefix}_{s}" style="padding:5px 16px;cursor:pointer;'
        f'border:1px solid #DEE2E6;border-bottom:none;margin-right:2px;'
        f'font-size:0.9em;font-weight:500;border-radius:4px 4px 0 0;'
        f'background:white;color:#555">{corp}</label>'
        for corp, s in zip(corp_labels, safe)
    )
    tab_bar += '</div>'

    panels = ''.join(
        f'<div id="fp_{prefix}_{s}">{_재무_to_html_table(per_corp_dfs[corp], 소계행, 헤더행)}</div>'
        for corp, s in zip(corp_labels, safe)
    )

    tab_html = f'<style>{css}</style>' + inputs + tab_bar + panels
    return _layout64(title, tab_html, memo, unit)

def _현금흐름표_연결_to_html_table(df, 소계행, 헤더행):
    depths    = df['_depth'].tolist() if '_depth' in df.columns else [1] * len(df)
    render_df = df.drop(columns=['_depth'], errors='ignore')

    _td_hdr_num = f'background:{_C_LT_GRAY};border-bottom:1px solid #DEE2E6'
    _pad    = {0: '8px',  1: '20px', 2: '36px'}
    _prefix = {0: '',     1: '&nbsp;&nbsp;&nbsp;', 2: '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'}

    rows_html = ''
    for (_, row), depth in zip(render_df.iterrows(), depths):
        d      = int(depth) if str(depth).lstrip('-').isdigit() else 1
        label  = str(row.iloc[0])
        is_hdr = label in 헤더행
        is_sub = label in 소계행
        bg     = ''
        pad    = _pad.get(d, '20px')
        prefix = _prefix.get(d, '&nbsp;&nbsp;&nbsp;')

        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if is_hdr:
                lbl_st = (f'padding:4px 8px;padding-left:{pad};text-align:left;'
                          f'background:{_C_LT_GRAY};font-weight:700;color:{_C_NAVY};'
                          f'border-bottom:1px solid #DEE2E6')
                cells += (f'<td style="{lbl_st}">{prefix}{s}</td>' if i == 0
                          else f'<td style="{_td_hdr_num}"></td>')
            elif i == 0:
                if is_sub:
                    lbl_st = (f'padding:5px 8px;padding-left:{pad};text-align:left;'
                              f'background:{_C_LT_GRAY};font-weight:600;'
                              f'border-bottom:1px solid #e2e8f0')
                else:
                    lbl_st = (f'padding:5px 8px;padding-left:{pad};text-align:left;'
                              f'border-bottom:1px solid #e2e8f0;{bg}')
                cells += f'<td style="{lbl_st}">{prefix}{s}</td>'
            elif s.startswith('-'):
                cells += f'<td style="{_TD_SUB_RED if is_sub else _TD_RED+";"+bg}">{s}</td>'
            else:
                cells += f'<td style="{_TD_SUB_NUM if is_sub else _TD_NUM+";"+bg}">{s}</td>'
        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'

    headers = ''.join(f'<th style="{_TH}">{c}</th>' for c in render_df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)


def _현금흐름표_연결_section(title, per_corp_dfs, 소계행, 헤더행, corp_labels, memo='', unit='[단위: 백만원]'):
    # CSS id 선택자에 쓰이므로 공백/괄호 등 특수문자는 제거해야 함 (안 그러면 선택자가 깨져서 탭 전환이 무력화됨)
    safe = [c.replace(' ', '_').replace('(', '').replace(')', '') for c in corp_labels]
    prefix = "cf"  # 현금흐름표 고유 접두사 (Cash Flow)

    hide_sel = ', '.join(f'#fp_{prefix}_{s}' for s in safe)
    css = f'{hide_sel}{{display:none}}'
    for s in safe:
        css += (f'#ft_{prefix}_{s}:checked~#fp_{prefix}_{s}{{display:block!important}}'
                f'#ft_{prefix}_{s}:checked~.ftbar>#fl_{prefix}_{s}'
                f'{{background:{_C_NAVY}!important;color:white!important;border-color:{_C_NAVY}!important}}')

    inputs = ''.join(
        f'<input type="radio" id="ft_{prefix}_{s}" name="ftab_{prefix}" {"checked" if i == 0 else ""} '
        f'style="position:absolute;opacity:0;pointer-events:none">'
        for i, s in enumerate(safe)
    )

    tab_bar = f'<div class="ftbar" style="display:flex;margin-bottom:6px;border-bottom:2px solid {_C_NAVY}">'
    tab_bar += ''.join(
        f'<label id="fl_{prefix}_{s}" for="ft_{prefix}_{s}" style="padding:5px 16px;cursor:pointer;'
        f'border:1px solid #DEE2E6;border-bottom:none;margin-right:2px;'
        f'font-size:0.9em;font-weight:500;border-radius:4px 4px 0 0;'
        f'background:white;color:#555">{corp}</label>'
        for corp, s in zip(corp_labels, safe)
    )
    tab_bar += '</div>'

    panels = ''.join(
        f'<div id="fp_{prefix}_{s}">{_현금흐름표_연결_to_html_table(per_corp_dfs[corp], 소계행, 헤더행)}</div>'
        for corp, s in zip(corp_labels, safe)
    )

    tab_html = f'<style>{css}</style>' + inputs + tab_bar + panels
    return _layout64(title, tab_html, memo, unit)



def _build_회전일_table(year, month):
    df = load_sheet(Sheets.회전일_DB)
    df['값']  = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    # 천진 사업장 제외
    df = df[df['사업장'] != '천진']

    yr_전기, mo_전기 = year - 1, 12
    yr_전월, mo_전월 = _prev(year, month, 1)

    db_corps    = _sort_corps(df['사업장'].unique().tolist(), 회전일_CORP_ORDER)
    corp_labels = [회전일_사업장_표시명.get(c, c) for c in db_corps]

    sub_labels = [
        f"'{str(year - 1)[2:]}년",
        f"'{str(yr_전월)[2:]}.{mo_전월}월",
        f"'{str(year)[2:]}.{month}월",
        '전월비',
    ]

    val_map = df.set_index(['연도', '월', '사업장', '구분1'])['값'].to_dict()

    def 값(yr, mo, corp, 항목):
        return val_map.get((yr, mo, corp, 항목), 0.0)

    rows = []
    for db_corp, corp_disp in zip(db_corps, corp_labels):
        for i, 항목 in enumerate(회전일_구분_순서):
            전기_v = 값(yr_전기, mo_전기, db_corp, 항목)
            전월_v = 값(yr_전월, mo_전월, db_corp, 항목)
            당월_v = 값(year,    month,   db_corp, 항목)
            rows.append({
                '사업장':       corp_disp,
                '_first':       i == 0,
                '구분':         항목,
                sub_labels[0]:  _fmt(전기_v,           decimal=1),
                sub_labels[1]:  _fmt(전월_v,           decimal=1),
                sub_labels[2]:  _fmt(당월_v,           decimal=1),
                sub_labels[3]:  _fmt(당월_v - 전월_v,  decimal=1),
            })

    return rows, sub_labels


def _회전일_to_html_table(rows, sub_labels):
    headers = (f'<th style="{_TH}">사업장</th>'
               f'<th style="{_TH}">구분</th>'
               + ''.join(f'<th style="{_TH}">{h}</th>' for h in sub_labels))

    rows_html = ''
    group_idx = -1
    for row in rows:
        is_first = row['_first']
        if is_first:
            group_idx += 1

        grp_bg = _C_LT_GRAY if group_idx % 2 == 1 else '#ffffff'
        sep    = f'border-top:2px solid {_C_NAVY};' if (is_first and group_idx > 0) else ''
        b_bot  = 'border-bottom:1px solid #e2e8f0'

        corp_val = row['사업장'] if is_first else ''
        corp_fw  = 'font-weight:700;' if is_first else ''
        cells    = (f'<td style="padding:6px 12px;text-align:center;{corp_fw}'
                    f'background:{grp_bg};{sep}{b_bot}">{corp_val}</td>')

        cells += (f'<td style="padding:5px 10px;text-align:left;'
                  f'background:{grp_bg};{sep}{b_bot}">{row["구분"]}</td>')

        for h in sub_labels:
            s      = str(row[h])
            color  = f';color:{_C_RED}' if s.startswith('-') else ''
            cells += (f'<td style="padding:5px 10px;text-align:right;'
                      f'background:{grp_bg};{sep}{b_bot}{color}">{s}</td>')

        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'

    return _html_table(f'<tr>{headers}</tr>', rows_html)


# ── 데이터 로드 ───────────────────────────────────────────────

def _load_손익():
    df = load_sheet(Sheets.손익_DB)
    df['값']  = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    # 천진 사업장 제외
    df = df[df['사업장'] != '천진']

    사업장_list = _sort_corps(df['사업장'].unique().tolist(), CORP_ORDER)

    def get(계실, yr, mo, 장=None, 구분=None):
        m = (df['계획/실적'] == 계실) & (df['연도'] == yr) & (df['월'] == mo)
        if 장:   m &= df['사업장'] == 장
        if 구분: m &= df['구분1']  == 구분
        return df[m]['값'].sum()

    return get, 사업장_list


def _get_연도_목록():
    df1 = load_sheet(Sheets.손익_DB)
    df2 = load_sheet(Sheets.현금흐름표_별도_DB)
    df3 = load_sheet(Sheets.재무상태표_DB)
    
    y1 = pd.to_numeric(df1['연도'], errors='coerce').dropna().astype(int).unique().tolist()
    y2 = pd.to_numeric(df2['연도'], errors='coerce').dropna().astype(int).unique().tolist()
    y3 = pd.to_numeric(df3['연도'], errors='coerce').dropna().astype(int).unique().tolist()
    
    return sorted(list(set(y1 + y2 + y3)))

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
    _장_표시명 = {'본사': '선재_국내', '남통': '선재_남통', '타이': '선재_타이'}
    장_cols    = [f"{_장_표시명.get(장, 장)} {_기호[i]}" for i, 장 in enumerate(사업장_list)]
    columns    = ['구분', 전전월_col, 전월_col, '계획', 당월_col] + 장_cols + ['전월대비', '계획대비']

    rows, 매출액 = [], {}

    for g in SONIK_구분_순서:
        div      = SONIK_단위[g]
        dec      = SONIK_소수점.get(g, 0)
        전전월_v = get('실적', yr1, mo1, 구분=g)
        전월_v   = get('실적', yr2, mo2, 구분=g)
        계획_v   = get('계획', year, month, 구분=g)
        장별     = {장: get('실적', year, month, 장=장, 구분=g) for 장 in 사업장_list}
        당월_v   = sum(장별.values())

        if g == '매출액':
            매출액 = {'전전월': 전전월_v, '전월': 전월_v, '계획': 계획_v, '당월': 당월_v, **장별}

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

        if g in SONIK_PCT_대상 and 매출액.get('당월'):
            전전월_p = _pct(전전월_v, 매출액['전전월'])
            전월_p   = _pct(전월_v,   매출액['전월'])
            계획_p   = _pct(계획_v,   매출액['계획'])
            당월_p   = _pct(당월_v,   매출액['당월'])
            rows.append({
                '구분':     '%',
                전전월_col: _fmt_pct_val(전전월_p),
                전월_col:   _fmt_pct_val(전월_p),
                '계획':     _fmt_pct_val(계획_p),
                당월_col:   _fmt_pct_val(당월_p),
                '전월대비': _fmt_pct_diff(당월_p - 전월_p),
                '계획대비': _fmt_pct_diff(당월_p - 계획_p),
                **{장_cols[i]: _fmt_pct_val(_pct(장별[장], 매출액.get(장, 0)))
                   for i, 장 in enumerate(사업장_list)},
            })

    return pd.DataFrame({col: [r.get(col, '') for r in rows] for col in columns})


def _build_국내_table(get, year, month, 사업장=선재_국내_사업장):
    yr2, mo2 = _prev(year, month, 1)
    전월_col  = _월헤더(yr2, mo2)

    columns = ['구분', 전월_col,
               '당월_계획', '당월_실적', '당월_계획대비', '당월_전월대비',
               '누적_계획', '누적_실적', '누적_계획대비']

    rows, 매출액 = [], {}

    for g in SONIK_구분_순서:
        div      = SONIK_단위[g]
        dec      = SONIK_소수점.get(g, 0)
        전월_v   = get('실적', yr2, mo2, 장=사업장, 구분=g)
        당월계획  = get('계획', year, month, 장=사업장, 구분=g)
        당월실적  = get('실적', year, month, 장=사업장, 구분=g)
        누적계획  = sum(get('계획', year, m, 장=사업장, 구분=g) for m in range(1, month + 1))
        누적실적  = sum(get('실적', year, m, 장=사업장, 구분=g) for m in range(1, month + 1))

        if g == '매출액':
            매출액 = {'전월': 전월_v, '당월계획': 당월계획, '당월실적': 당월실적,
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

        if g in SONIK_PCT_대상 and 매출액.get('당월실적'):
            전월_p     = _pct(전월_v,    매출액['전월'])
            당월계획_p  = _pct(당월계획, 매출액['당월계획'])
            당월실적_p  = _pct(당월실적, 매출액['당월실적'])
            누적계획_p  = _pct(누적계획, 매출액['누적계획'])
            누적실적_p  = _pct(누적실적, 매출액['누적실적'])
            rows.append({
                '구분':          '%',
                전월_col:        _fmt_pct_val(전월_p),
                '당월_계획':     _fmt_pct_val(당월계획_p),
                '당월_실적':     _fmt_pct_val(당월실적_p),
                '당월_계획대비': _fmt_pct_diff(당월실적_p - 당월계획_p),
                '당월_전월대비': _fmt_pct_diff(당월실적_p - 전월_p),
                '누적_계획':     _fmt_pct_val(누적계획_p),
                '누적_실적':     _fmt_pct_val(누적실적_p),
                '누적_계획대비': _fmt_pct_diff(누적실적_p - 누적계획_p),
            })

    return pd.DataFrame({col: [r.get(col, '') for r in rows] for col in columns})


def _build_현금흐름표_연결_table(year, month):
    df = load_sheet(Sheets.현금흐름표_연결_DB)
    df['값']  = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')
    df['구분2'] = df['구분2'].fillna('').astype(str).str.strip()
    df['구분3'] = df['구분3'].fillna('').astype(str).str.strip()
    df['구분4'] = df['구분4'].fillna('').astype(str).str.strip()

    # 전체, 천진 사업장 제외
    df = df[df['사업장'] != '전체']
    df = df[df['사업장'] != '천진']

    db_corps    = _sort_corps(df['사업장'].unique().tolist(), 현금_CORP_ORDER)
    corp_labels = [현금_사업장_표시명.get(c, c) for c in db_corps]

    sub_labels = [
        f"'{str(year - 1)[2:]}년",
        '전월누적',
        f"'{str(year)[2:]}.{month}월",
        f"'{str(year)[2:]}년누적",
    ]

    # 특정 사업장이 아닌, 해당 월의 전체 데이터 기준으로 표의 뼈대(행 순서) 생성
    target = df[(df['연도'] == year) & (df['월'] == month)]
    행_순서 = list(dict.fromkeys(zip(target['구분1'], target['구분2'], target['구분3'])))

    # 구분4(당월/누적) 기준으로 값을 조회, 24년 이전은 DB에 저장된 '누적' 값을 그대로 사용
    val_map = df.groupby(['연도', '월', '구분4', '구분1', '구분2', '구분3', '사업장'])['값'].sum().to_dict()

    def get_val(yr, mo, g4, g1, g2, g3, 장):
        return val_map.get((yr, mo, g4, g1, g2, g3, 장), 0.0)

    def get_accumulated(yr, target_mo, g1, g2, g3, 장):
        if yr < 2025:
            return get_val(yr, 12, '누적', g1, g2, g3, 장)
        return sum(get_val(yr, m, '당월', g1, g2, g3, 장) for m in range(1, target_mo + 1))

    # 기초현금/기말현금은 흐름의 누적이 아니라 특정 시점의 현황값이므로 월별 합산 대신
    # 해당 시점의 값을 그대로 가져온다.
    잔액_항목 = {'기초현금', '기말현금'}
    yr_전월, mo_전월 = _prev(year, month, 1)

    def get_잔액(label, period, g1, g2, g3, 장):
        if period == '전년':
            return get_val(year - 1, 12, '누적', g1, g2, g3, 장)
        if period == '당월':
            return get_val(year, month, '당월', g1, g2, g3, 장)
        if label == '기초현금':
            # 전월누적/당월누적 모두 해당 연도 1월의 기초현금
            return get_val(year, 1, '당월', g1, g2, g3, 장)
        # 기말현금: 전월누적은 전월의 기말현금, 당월누적은 당월의 기말현금
        if period == '전월누적':
            return get_val(yr_전월, mo_전월, '당월', g1, g2, g3, 장)
        return get_val(year, month, '당월', g1, g2, g3, 장)

    columns = ['구분', '_depth'] + sub_labels
    소계행  = 현금_소계행
    헤더행  = set()

    # 선재(연결) 탭을 선재_국내 앞에 추가 — 사업장 전체 합산
    tab_groups = [('선재(연결)', db_corps)] + [(corp_disp, [db_corp]) for db_corp, corp_disp in zip(db_corps, corp_labels)]

    per_corp_dfs = {}
    for tab_label, target_corps in tab_groups:
        rows = []
        for g1, g2, g3 in 행_순서:
            # 구분이 비어있으면 상위 구분을 라벨로 사용
            if not g2 and not g3:
                label = g1
                depth = 0
            elif not g3:
                label = g2
                depth = 1
            else:
                label = g3
                depth = 2

            if label in 소계행:
                depth = 0

            if label in 잔액_항목:
                전년누적_v = sum(get_잔액(label, '전년',   g1, g2, g3, c) for c in target_corps)
                전월누적_v = sum(get_잔액(label, '전월누적', g1, g2, g3, c) for c in target_corps)
                당월_v     = sum(get_잔액(label, '당월',   g1, g2, g3, c) for c in target_corps)
                당월누적_v = sum(get_잔액(label, '당월누적', g1, g2, g3, c) for c in target_corps)
            else:
                전년누적_v = sum(get_accumulated(year - 1, 12,          g1, g2, g3, c) for c in target_corps)
                전월누적_v = sum(get_accumulated(year,     month - 1,   g1, g2, g3, c) for c in target_corps)
                당월_v     = sum(get_val(year, month, '당월',           g1, g2, g3, c) for c in target_corps)
                당월누적_v = sum(get_accumulated(year,     month,       g1, g2, g3, c) for c in target_corps)

            rows.append({
                '구분':        label,
                '_depth':      depth,
                sub_labels[0]: _fmt(전년누적_v),
                sub_labels[1]: _fmt(전월누적_v),
                sub_labels[2]: _fmt(당월_v),
                sub_labels[3]: _fmt(당월누적_v),
            })

        per_corp_dfs[tab_label] = pd.DataFrame(
            {col: [r.get(col, '') for r in rows] for col in columns}
        )

    corp_labels = ['선재(연결)'] + corp_labels

    return per_corp_dfs, 소계행, 헤더행, corp_labels

def _build_재무상태표_table(year, month):
    df = load_sheet(Sheets.재무상태표_DB)
    df['값']  = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    # 천진 사업장 제외
    df = df[df['사업장'] != '천진']

    yr_전기, mo_전기 = year - 1, 12
    yr_전월, mo_전월 = _prev(year, month, 1)

    db_corps    = _sort_corps(df['사업장'].unique().tolist(), 재무_CORP_ORDER)
    corp_labels = [재무_사업장_표시명.get(c, c) for c in db_corps]

    sub_labels = [
        f"'{str(year - 1)[2:]}년",
        f"'{str(yr_전월)[2:]}.{mo_전월}월",
        f"'{str(year)[2:]}.{month}월",
        '전월비',
    ]

    anchor  = df[(df['연도'] == year) & (df['월'] == month) & (df['사업장'] == db_corps[0])]
    행_순서 = list(dict.fromkeys(zip(anchor['구분1'], anchor['구분2'])))

    # 반복 필터 대신 O(1) 조회 dict
    val_map = df.set_index(['연도', '월', '구분1', '구분2', '사업장'])['값'].to_dict()

    def 값(yr, mo, g1, g2, 장):
        return val_map.get((yr, mo, g1, g2, 장), 0.0)

    # 자본총계의 '기타'는 DB 원본 값 대신 자본총계 - 자본금 - 이익잉여금으로 계산
    def 자본총계_기타(yr, mo, 장):
        총계     = 값(yr, mo, '자본총계', '자본총계', 장)
        자본금   = 값(yr, mo, '자본총계', '자본금',   장)
        이익잉여금 = 값(yr, mo, '자본총계', '이익잉여금', 장)
        return 총계 - 자본금 - 이익잉여금

    columns = ['구분', '_depth'] + sub_labels
    소계행  = 재무_소계행
    헤더행  = set()
    빈행    = {col: '' for col in columns}

    _SUM = '__SUM__'
    행_순서_aug, seen = [], set()
    for g1, g2 in 행_순서:
        key = (g1, g2)
        행_순서_aug.append((g1, g2))

    # 각 g1 그룹에서 소계행(총계)이 맨 앞으로 오도록 재정렬 (p8 스타일)
    g1_order = list(dict.fromkeys(t[0] for t in 행_순서_aug))
    g1_groups: dict = {g: [] for g in g1_order}
    for triple in 행_순서_aug:
        g1_groups[triple[0]].append(triple)

    행_순서_final: list = []
    for g1 in g1_order:
        group  = g1_groups[g1]
        totals = [t for t in group if (t[1] in 소계행 or t[0] == t[1])]
        others = [t for t in group if t not in totals]
        행_순서_final.extend(totals + others)

    # 선재(연결) 탭을 선재_국내 앞에 추가 — 사업장 전체 합산
    tab_groups = [('선재(연결)', db_corps)] + [(corp_disp, [db_corp]) for db_corp, corp_disp in zip(db_corps, corp_labels)]

    per_corp_dfs = {}
    for tab_label, target_corps in tab_groups:
        rows = []
        for g1, g2 in 행_순서_final:
            label = g2

            if label in 소계행 or g1 == g2:
                depth = 0
            else:
                depth = 1

            if g1 == '자본총계' and g2 == '기타':
                전기_v = sum(자본총계_기타(yr_전기, mo_전기, c) for c in target_corps)
                전월_v = sum(자본총계_기타(yr_전월, mo_전월, c) for c in target_corps)
                당월_v = sum(자본총계_기타(year,    month,   c) for c in target_corps)
            else:
                전기_v = sum(값(yr_전기, mo_전기, g1, g2, c) for c in target_corps)
                전월_v = sum(값(yr_전월, mo_전월, g1, g2, c) for c in target_corps)
                당월_v = sum(값(year,    month,   g1, g2, c) for c in target_corps)

            rows.append({
                '구분':        label,
                '_depth':      depth,
                sub_labels[0]: _fmt(전기_v),
                sub_labels[1]: _fmt(전월_v),
                sub_labels[2]: _fmt(당월_v),
                sub_labels[3]: _fmt(당월_v - 전월_v),
            })
        per_corp_dfs[tab_label] = pd.DataFrame(
            {col: [r.get(col, '') for r in rows] for col in columns}
        )

    corp_labels = ['선재(연결)'] + corp_labels

    return per_corp_dfs, 소계행, 헤더행, corp_labels

def _build_품목손익_별도_table(year, month):
    df = load_sheet(Sheets.품목손익_DB)
    df['값'] = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    target = df[(df['연도'] == year) & (df['월'] == month)]
    val_map = target.set_index(['구분1', '구분2'])['값'].to_dict()

    def get_val(g1, g2):
        return val_map.get((g1, g2), 0.0)

    품목_cols = ['CHQ', 'CD', 'STS', 'BTB', 'PB']
    구분_목록 = ['매출액', '판매량', '영업이익', '경상이익']
    단위 = {'매출액': 1e6, '판매량': 1, '영업이익': 1e6, '경상이익': 1e6}
    
    rows = []
    매출액_dict = {}

    for g1 in 구분_목록:
        div = 단위.get(g1, 1)
        row = {'구분': g1}
        
        합_raw = get_val(g1, '합계')
        row['합계'] = _fmt(합_raw / div, decimal=0)

        raw_vals = {}
        for p in 품목_cols:
            v = get_val(g1, p)
            raw_vals[p] = v
            if g1 == '판매량' and v == 0:
                row[p] = ''
            else:
                row[p] = _fmt(v / div, decimal=0)

        # 상품 등 = 합계 - (CHQ+CD+STS+BTB+PB)
        상품등_raw = 합_raw - sum(raw_vals.values())
        raw_vals['상품 등'] = 상품등_raw
        row['상품 등'] = _fmt(상품등_raw / div, decimal=0)

        if g1 == '매출액':
            매출액_dict = {'합계': 합_raw}
            매출액_dict.update(raw_vals)

        rows.append(row)

        if g1 in ['영업이익', '경상이익']:
            pct_row = {'구분': '%'}

            매출_합 = 매출액_dict.get('합계', 0)
            pct_row['합계'] = _fmt(_pct(합_raw, 매출_합), is_pct=True, decimal=1) if 매출_합 else '-'

            for p in 품목_cols + ['상품 등']:
                매출_p = 매출액_dict.get(p, 0)
                이익_p = raw_vals.get(p, 0)
                if 매출_p and 이익_p != 0.0:
                    pct_row[p] = _fmt(_pct(이익_p, 매출_p), is_pct=True, decimal=1)
                else:
                    pct_row[p] = ''
            rows.append(pct_row)

    columns = ['구분', '합계'] + 품목_cols + ['상품 등']
    return pd.DataFrame({col: [r.get(col, '') for r in rows] for col in columns})

def _build_수정원가기준손익_별도_table(year, month):
    df = load_sheet(Sheets.수정원가기준손익_DB)
    df['값'] = df['값'].astype(str).str.replace('%', '', regex=False).apply(_parse)
    df = _drop_empty(df, '연도', '월')

    target = df[(df['연도'] == year) & (df['월'] == month)]
    val_map = target.set_index(['구분1', '구분2'])['값'].to_dict()

    def get_val(g1, g2):
        return val_map.get((g1, g2), 0.0)

    def get_pct(g1, g2):
        return val_map.get((f'%({g1})', g2), None)

    품목_cols = ['계', 'CHQ', 'CD', 'STS', 'BTB', 'PB', '내수', '수출']
    구분_목록 = ['매출액', '판매량', 'X등급및재고평가', '영업이익', '한계이익']
    구분_표시명 = {'X등급및재고평가': 'X등급 및 재고평가'}

    rows = []

    for g1 in 구분_목록:
        row = {'구분': 구분_표시명.get(g1, g1)}

        for p in 품목_cols:
            v = get_val(g1, p)
            if g1 == '판매량' and v == 0:
                row[p] = ''
            else:
                row[p] = _fmt(v, decimal=0)

        rows.append(row)

        # 영업이익, 한계이익 다음 행에 직접 계산한 이익률 표시
        if g1 in ['영업이익', '한계이익']:
            pct_row = {'구분': '%'}

            for p in 품목_cols:
                # 이익(영업이익 or 한계이익) 금액과 매출액 금액을 각각 가져옴
                profit = get_val(g1, p)
                sales = get_val('매출액', p)
                
                # 매출액이 0이 아닐 때만 비율을 계산 (0으로 나누는 에러 방지)
                if sales and sales != 0:
                    v = profit / sales  # 퍼센트 표기 방식에 따라 * 100이 필요할 수 있습니다.
                else:
                    v = None
                    
                pct_row[p] = _fmt_pct_val(v) if v is not None else ''
            
            rows.append(pct_row)

    columns = ['구분'] + 품목_cols
    return pd.DataFrame({col: [r.get(col, '') for r in rows] for col in columns})

def _build_원재료입고기초단가차이_table(year, month):
    df = load_sheet(Sheets.원재료입고기초단가차이_DB)
    df['값'] = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    target = df[(df['연도'] == year) & (df['월'] == month)]
    val_map = target.set_index(['구분1', '구분2'])['값'].to_dict()

    def get_val(g1, g2):
        return val_map.get((g1, g2), 0.0)

    # 데이터에 존재하는 메이커 목록 추출 (합계는 맨 마지막으로 배치)
    makers = [m for m in target['구분1'].unique() if m != '합계']
    if '합계' in target['구분1'].values:
        makers.append('합계')

    columns = ['메이커', '입고중량', '금액', '단가']
    rows = []

    for m in makers:
        w = get_val(m, '중량') / 1000.0      # 톤 단위
        a = get_val(m, '금액') / 1000000.0   # 백만원 단위
        p = get_val(m, '단가')               # 그대로

        rows.append({
            '메이커': m,
            '입고중량': _fmt(w, decimal=0),
            '금액': _fmt(a, decimal=0),
            '단가': _fmt(p, decimal=0),
        })

    return pd.DataFrame({col: [r.get(col, '') for r in rows] for col in columns})


def _build_원재료입고단가차이_거래처기준_table(year, month):
    df = load_sheet(Sheets.원재료입고단가차이_거래처기준_DB)
    df['값'] = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    target = df[(df['연도'] == year) & (df['월'] == month)]
    val_map = target.set_index(['구분1', '구분2'])['값'].to_dict()

    def get_val(g1, g2):
        return val_map.get((g1, g2), 0.0)

    # 데이터에 존재하는 메이커 목록 추출 (합계는 맨 마지막으로 배치)
    makers = [m for m in target['구분1'].unique() if m != '합계']
    if '합계' in target['구분1'].values:
        makers.append('합계')

    columns = ['메이커', '금액', '단가']
    rows = []
    
    for m in makers:
        a = get_val(m, '금액') / 1000000.0   # 백만원 단위
        p = get_val(m, '단가')               # 그대로
        
        rows.append({
            '메이커': m,
            '금액': _fmt(a, decimal=0),
            '단가': _fmt(p, decimal=0),
        })

    return pd.DataFrame({col: [r.get(col, '') for r in rows] for col in columns})


def _원재료_to_html_table(df):
    rows_html = ''
    for idx, row in df.iterrows():
        is_sub = str(row.iloc[0]) == '합계'
        bg = '' if is_sub else (f';background:{_C_LT_GRAY}' if idx % 2 == 1 else '')
        
        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if i == 0:
                style = _TD_SUB_LBL if is_sub else _TD_LBL + bg
            elif s.startswith('-'):
                style = _TD_SUB_RED if is_sub else _TD_RED + bg
            else:
                style = _TD_SUB_NUM if is_sub else _TD_NUM + bg
            cells += f'<td style="{style}">{s}</td>'
        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'

    headers = ''.join(f'<th style="{_TH}">{c}</th>' for c in df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)


def _원재료_section(title, table_df, memo='', unit='[단위: 톤, 백만원]'):
    return _layout64(title, _원재료_to_html_table(table_df), memo, unit)

def _build_제품수불표_table(year, month):
    df = load_sheet(Sheets.제품수불표_DB)
    df['값'] = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    target = df[(df['연도'] == year) & (df['월'] == month)]
    val_map = target.set_index(['구분1', '구분2'])['값'].to_dict()

    def get_val(g1, g2):
        return val_map.get((g1, g2), 0.0)

    columns = ['구분', '단가', '금액']
    rows = []

    for g1 in ['입고-기초', '매출원가-기초']:
        p = get_val(g1, '단가')
        a = get_val(g1, '금액') / 1000000.0 

        rows.append({
            '구분': g1,
            '단가': _fmt(p, decimal=0),
            '금액': _fmt(a, decimal=0)
        })

    return pd.DataFrame({col: [r.get(col, '') for r in rows] for col in columns})

def _build_현금흐름표_별도_table(year, month):
    df = load_sheet(Sheets.현금흐름표_별도_DB)
    
    # 1. 값 컬럼 정리
    val_col = '실적' if '실적' in df.columns else '값'
    df[val_col] = df[val_col].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    # 2. 구분 컬럼 정제
    for c in ['구분1', '구분2', '구분3', '구분4']:
        df[c] = df[c].fillna('').astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

    # 3. 데이터 롤업(Roll-up) 해시맵 생성
    val_map = {}
    for _, row in df.iterrows():
        y, m, g4 = int(row['연도']), int(row['월']), row['구분4']
        g1, g2, g3 = row['구분1'], row['구분2'], row['구분3']
        v = row[val_col]
        if v == 0: continue
        
        def add(k_g1, k_g2, k_g3):
            key = (y, m, g4, k_g1, k_g2, k_g3)
            val_map[key] = val_map.get(key, 0.0) + v
        
        add(g1, g2, g3)
        if g3: add(g1, g2, '')
        if g2 or g3: add(g1, '', '')

    def get_val(yr, mo, g4, g1, g2, g3):
        return val_map.get((yr, mo, g4, g1, g2, g3), 0.0)

    # 4. 조회 로직: 과거/현재 구분
    def get_accumulated(yr, target_mo, g1, g2, g3):
        # 1) 23, 24년 등 과거는 DB에 저장된 '누적' 값을 우선 사용
        if yr < 2025:
            return get_val(yr, 12, '누적', g1, g2, g3)

        return sum(get_val(yr, m, '당월', g1, g2, g3) for m in range(1, target_mo + 1))

    # 기초현금/기말현금은 흐름의 누적이 아니라 특정 시점의 현황값이므로 월별 합산 대신
    # 해당 시점의 값을 그대로 가져온다.
    잔액_항목 = {'기초현금', '기말현금'}
    yr_전월, mo_전월 = _prev(year, month, 1)

    def get_잔액(label, period, g1, g2, g3):
        if period in ('전전년', '전년'):
            yr = year - 2 if period == '전전년' else year - 1
            return get_val(yr, 12, '누적', g1, g2, g3)
        if period == '당월':
            return get_val(year, month, '당월', g1, g2, g3)
        if label == '기초현금':
            # 전월누적/당월누적 모두 해당 연도 1월의 기초현금
            return get_val(year, 1, '당월', g1, g2, g3)
        # 기말현금: 전월누적은 전월의 기말현금, 당월누적은 당월의 기말현금
        if period == '전월누적':
            return get_val(yr_전월, mo_전월, '당월', g1, g2, g3)
        return get_val(year, month, '당월', g1, g2, g3)

    # 5. 표 뼈대 생성 (당월 데이터 기준)
    target = df[(df['연도'] == year) & (df['월'] == month)].copy()
    tree = {}
    for _, row in target.iterrows():
        g1, g2, g3 = row['구분1'], row['구분2'], row['구분3']
        if not g1: continue
        if g1 not in tree: tree[g1] = {}
        if g2:
            if g2 not in tree[g1]: tree[g1][g2] = []
            if g3 and g3 not in tree[g1][g2]: tree[g1][g2].append(g3)

    # 6. 행 조립 및 계산
    rows = []
    소계행 = set(tree.keys())
    
    for g1, g2_dict in tree.items():
        rows.append({'label': g1, 'depth': 0, 'keys': (g1, '', '')})
        for g2, g3_list in g2_dict.items():
            rows.append({'label': g2, 'depth': 1, 'keys': (g1, g2, '')})
            for g3 in g3_list:
                rows.append({'label': g3, 'depth': 2, 'keys': (g1, g2, g3)})

    final_rows = []
    yr_y2, yr_y1 = year - 2, year - 1
    sub_labels = [f"'{str(yr_y2)[2:]}년", f"'{str(yr_y1)[2:]}년", '전월누적', '당월', f"'{str(year)[2:]}년누적"]
    
    for r in rows:
        g1, g2, g3 = r['keys']
        label = r['label']
        if label in 잔액_항목:
            v0 = get_잔액(label, '전전년',   g1, g2, g3)
            v1 = get_잔액(label, '전년',     g1, g2, g3)
            v2 = get_잔액(label, '전월누적', g1, g2, g3)
            v3 = get_잔액(label, '당월',     g1, g2, g3)
            v4 = get_잔액(label, '당월누적', g1, g2, g3)
        else:
            v0 = get_accumulated(yr_y2, 12, g1, g2, g3)
            v1 = get_accumulated(yr_y1, 12, g1, g2, g3)
            v2 = get_accumulated(year, month - 1, g1, g2, g3)
            v3 = get_val(year, month, '당월', g1, g2, g3)
            v4 = get_accumulated(year, month, g1, g2, g3)

        final_rows.append({
            '구분':        label,
            '_depth':      r['depth'],
            sub_labels[0]: _fmt(v0),
            sub_labels[1]: _fmt(v1),
            sub_labels[2]: _fmt(v2),
            sub_labels[3]: _fmt(v3),
            sub_labels[4]: _fmt(v4),
        })

    return _현금흐름표_연결_to_html_table(pd.DataFrame(final_rows), 소계행, set())

def _build_재무상태표_별도_table(year, month):
    df = load_sheet(Sheets.재무상태표_DB)
    df['값']  = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    df = df[df['사업장'] == '특수강']

    yr_전기, mo_전기 = year - 1, 12
    yr_전월, mo_전월 = _prev(year, month, 1)

    sub_labels = [
        f"'{str(year - 1)[2:]}년",
        f"'{str(yr_전월)[2:]}.{mo_전월}월",
        f"'{str(year)[2:]}.{month}월",
        '전월비',
    ]

    anchor = df[(df['연도'] == year) & (df['월'] == month)]
    
    if anchor.empty:
        행_순서 = list(dict.fromkeys(zip(df['구분1'], df['구분2'])))
    else:
        행_순서 = list(dict.fromkeys(zip(anchor['구분1'], anchor['구분2'])))

    val_map = df.set_index(['연도', '월', '구분1', '구분2'])['값'].to_dict()

    def 값(yr, mo, g1, g2):
        return val_map.get((yr, mo, g1, g2), 0.0)

    columns = ['구분', '_depth'] + sub_labels
    소계행  = 재무_소계행
    헤더행  = set()

    행_순서_aug = [(g1, g2) for g1, g2 in 행_순서]
    g1_order = list(dict.fromkeys(t[0] for t in 행_순서_aug))
    g1_groups: dict = {g: [] for g in g1_order}
    for triple in 행_순서_aug:
        g1_groups[triple[0]].append(triple)

    행_순서_final: list = []
    for g1 in g1_order:
        group  = g1_groups[g1]
        totals = [t for t in group if (t[1] in 소계행 or t[0] == t[1])]
        others = [t for t in group if t not in totals]
        행_순서_final.extend(totals + others)

    rows = []
    for g1, g2 in 행_순서_final:
        label = g2
        depth = 0 if (label in 소계행 or g1 == g2) else 1

        전기_v = 값(yr_전기, mo_전기, g1, g2)
        전월_v = 값(yr_전월, mo_전월, g1, g2)
        당월_v = 값(year,    month,   g1, g2)

        rows.append({
            '구분':        label,
            '_depth':      depth,
            sub_labels[0]: _fmt(전기_v),
            sub_labels[1]: _fmt(전월_v),
            sub_labels[2]: _fmt(당월_v),
            sub_labels[3]: _fmt(당월_v - 전월_v),
        })

    df_res = pd.DataFrame({col: [r.get(col, '') for r in rows] for col in columns})
    return _재무_to_html_table(df_res, 소계행, 헤더행)

def _build_회전일_별도_table(year, month):
    df = load_sheet(Sheets.회전일_DB)
    val_col = '실적' if '실적' in df.columns else '값'
    df[val_col] = df[val_col].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    if '사업장' in df.columns:
        df = df[df['사업장'] == '특수강']

    yr_전기, mo_전기 = year - 1, 12
    yr_전월, mo_전월 = _prev(year, month, 1)

    sub_labels = [
        f"'{str(yr_전기)[2:]}년말",
        f"'{str(yr_전월)[2:]}.{mo_전월}월",
        f"'{str(year)[2:]}.{month}월",
        '전월대비'
    ]

    item_col = '구분2' if '구분2' in df.columns else '구분1'
    df[item_col] = df[item_col].fillna('').astype(str).str.strip()
    
    val_map = df.set_index(['연도', '월', item_col])[val_col].to_dict()

    def 값(yr, mo, 항목):
        for k, v in val_map.items():
            if k[0] == yr and k[1] == mo and 항목 in k[2]:
                return float(v)
        return None

    rows_info = [
        ("매출채권 ⓐ", "매출채권"),
        ("재고자산 ⓑ", "재고자산"),
        ("매입채무 ⓒ", "매입채무"),
        ("현금전환주기<br>(ⓐ+ⓑ-ⓒ)", "현금전환주기"),
    ]
    rows = []
    
    def fmt_num(v):
        if v is None: return ""
        return f"{v:.1f}"

    for label, key in rows_info:
        v_end = 값(yr_전기, mo_전기, key)
        v_pre = 값(yr_전월, mo_전월, key)
        v_cur = 값(year, month, key)
        v_dif = v_cur - v_pre if (v_cur is not None and v_pre is not None) else None
        
        rows.append({
            '구분': label,
            sub_labels[0]: fmt_num(v_end),
            sub_labels[1]: fmt_num(v_pre),
            sub_labels[2]: fmt_num(v_cur),
            sub_labels[3]: fmt_num(v_dif)
        })
    
    return pd.DataFrame(rows)

def _build_안정성_별도_table(year, month):
    df = load_sheet(Sheets.안정성_DB)
    val_col = '값' if '값' in df.columns else '실적'
    
    df[val_col] = df[val_col].astype(str).str.replace('%', '', regex=False).apply(_parse)
    df = _drop_empty(df, '연도', '월')

    if '사업장' in df.columns:
        if '본사' in df['사업장'].values:
            df = df[df['사업장'] == '본사']
        elif '특수강' in df['사업장'].values:
            df = df[df['사업장'] == '특수강']

    yr_전기, mo_전기 = year - 1, 12
    yr_전월, mo_전월 = _prev(year, month, 1)

    sub_labels = [
        f"'{str(yr_전기)[2:]}년말",
        f"'{str(yr_전월)[2:]}.{mo_전월}월",
        f"'{str(year)[2:]}.{month}월",
        '전월대비'
    ]

    item_col = '구분2' if '구분2' in df.columns and df['구분2'].str.strip().astype(bool).any() else '구분1'
    df[item_col] = df[item_col].fillna('').astype(str).str.strip()
    
    val_map = df.groupby(['연도', '월', item_col])[val_col].sum().to_dict()

    def 값(yr, mo, 항목):
        for k, v in val_map.items():
            if k[0] == yr and k[1] == mo and 항목 in k[2]:
                # 엑셀 서식 보정: 소수점으로 들어온 실제 값에 100을 곱함
                return float(v) * 100
        return None

    rows_info = ["부채비율", "차입금의존도"]
    rows = []
    
    def fmt_pct(v):
        if v is None: return ""
        return f"{v:.1f}%"
        
    def fmt_p(v):
        if v is None: return ""
        if v > 0: return f"+{v:.1f}%p"
        return f"{v:.1f}%p"

    for label in rows_info:
        v_end = 값(yr_전기, mo_전기, label)
        v_pre = 값(yr_전월, mo_전월, label)
        v_cur = 값(year, month, label)
        v_dif = v_cur - v_pre if (v_cur is not None and v_pre is not None) else None
        
        rows.append({
            '구분': label,
            sub_labels[0]: fmt_pct(v_end),
            sub_labels[1]: fmt_pct(v_pre),
            sub_labels[2]: fmt_pct(v_cur),
            sub_labels[3]: fmt_p(v_dif)
        })
    
    return pd.DataFrame(rows)


def _build_수익성_별도_table(year, month):
    df = load_sheet(Sheets.수익성_DB)
    val_col = '값' if '값' in df.columns else '실적'
    
    df[val_col] = df[val_col].astype(str).str.replace('%', '', regex=False).apply(_parse)
    df = _drop_empty(df, '연도', '월')

    if '사업장' in df.columns:
        if '본사' in df['사업장'].values:
            df = df[df['사업장'] == '본사']
        elif '특수강' in df['사업장'].values:
            df = df[df['사업장'] == '특수강']

    yr_전기, mo_전기 = year - 1, 12
    yr_전월, mo_전월 = _prev(year, month, 1)

    sub_labels = [
        f"'{str(yr_전기)[2:]}년말",
        f"'{str(yr_전월)[2:]}.{mo_전월}월",
        f"'{str(year)[2:]}.{month}월",
        '전월대비'
    ]

    item_col = '구분2' if '구분2' in df.columns and df['구분2'].str.strip().astype(bool).any() else '구분1'
    df[item_col] = df[item_col].fillna('').astype(str).str.strip()
    
    val_map = df.groupby(['연도', '월', item_col])[val_col].sum().to_dict()

    def 값(yr, mo, 항목):
        for k, v in val_map.items():
            if k[0] == yr and k[1] == mo and 항목 in k[2]:
                # 엑셀 서식 보정: 소수점으로 들어온 실제 값에 100을 곱함
                return float(v) * 100
        return None

    rows_info = ["ROA", "ROE"]
    rows = []
    
    def fmt_pct(v):
        if v is None: return ""
        return f"{v:.1f}%"

    def fmt_p(v):
        if v is None: return ""
        if v > 0: return f"+{v:.1f}%p"
        return f"{v:.1f}%p"

    for label in rows_info:
        v_end = 값(yr_전기, mo_전기, label)
        v_pre = 값(yr_전월, mo_전월, label)
        v_cur = 값(year, month, label)
        v_dif = v_cur - v_pre if (v_cur is not None and v_pre is not None) else None

        rows.append({
            '구분': label,
            sub_labels[0]: fmt_pct(v_end),
            sub_labels[1]: fmt_pct(v_pre),
            sub_labels[2]: fmt_pct(v_cur),
            sub_labels[3]: fmt_p(v_dif)
        })

    return pd.DataFrame(rows)


def _build_수익성_연결_table(year, month):
    df = load_sheet(Sheets.수익성_DB)
    val_col = '값' if '값' in df.columns else '실적'

    df[val_col] = df[val_col].astype(str).str.replace('%', '', regex=False).apply(_parse)
    df = _drop_empty(df, '연도', '월')

    # 천진 사업장 제외
    df = df[df['사업장'] != '천진']

    yr_전기, mo_전기 = year - 1, 12
    yr_전월, mo_전월 = _prev(year, month, 1)

    수익성_CORP_ORDER    = ['계', '본사', '남통', '태국']
    수익성_사업장_표시명  = {'계': '선재_전체', '본사': '선재_국내', '남통': '선재_남통', '태국': '선재_태국'}

    db_corps    = _sort_corps(df['사업장'].unique().tolist(), 수익성_CORP_ORDER)
    corp_labels = [수익성_사업장_표시명.get(c, c) for c in db_corps]

    sub_labels = [
        f"'{str(yr_전기)[2:]}년말",
        f"'{str(yr_전월)[2:]}.{mo_전월}월",
        f"'{str(year)[2:]}.{month}월",
        '전월대비',
    ]

    item_col = '구분2' if '구분2' in df.columns and df['구분2'].str.strip().astype(bool).any() else '구분1'
    df[item_col] = df[item_col].fillna('').astype(str).str.strip()

    val_map = df.groupby(['연도', '월', '사업장', item_col])[val_col].sum().to_dict()

    def 값(yr, mo, corp, 항목):
        for k, v in val_map.items():
            if k[0] == yr and k[1] == mo and k[2] == corp and 항목 in k[3]:
                # 엑셀 서식 보정: 소수점으로 들어온 실제 값에 100을 곱함
                return float(v) * 100
        return None

    def fmt_pct(v):
        if v is None: return ""
        return f"{v:.1f}%"

    def fmt_p(v):
        if v is None: return ""
        if v > 0: return f"+{v:.1f}%p"
        return f"{v:.1f}%p"

    rows_info = ["ROA", "ROE"]
    rows = []
    for db_corp, corp_disp in zip(db_corps, corp_labels):
        for i, label in enumerate(rows_info):
            v_end = 값(yr_전기, mo_전기, db_corp, label)
            v_pre = 값(yr_전월, mo_전월, db_corp, label)
            v_cur = 값(year,    month,   db_corp, label)
            v_dif = v_cur - v_pre if (v_cur is not None and v_pre is not None) else None

            rows.append({
                '사업장':       corp_disp,
                '_first':       i == 0,
                '구분':         label,
                sub_labels[0]:  fmt_pct(v_end),
                sub_labels[1]:  fmt_pct(v_pre),
                sub_labels[2]:  fmt_pct(v_cur),
                sub_labels[3]:  fmt_p(v_dif),
            })

    return rows, sub_labels


def _build_판매계획및실적_html(year, month):
    raw = load_sheet(Sheets.판매계획및실적_DB)
    
    # 1. 원본 데이터 값 정제
    val_col = '값' if '값' in raw.columns else '실적'
    raw[val_col] = raw[val_col].astype(str).str.replace(',', '', regex=False)
    raw[val_col] = pd.to_numeric(raw[val_col], errors='coerce').fillna(0)
    raw['연도'] = pd.to_numeric(raw['연도'], errors='coerce').fillna(0).astype(int)
    raw['월'] = pd.to_numeric(raw['월'], errors='coerce').fillna(0).astype(int)
    
    # 2. 빠른 데이터 조회를 위한 해시맵
    data_map = {}
    for _, row in raw.iterrows():
        if row[val_col] == 0: continue
        k = (str(row.get('계획/실적', '')).strip(), 
             str(row.get('구분4', '')).strip(),
             str(row.get('구분1', '')).strip(), 
             str(row.get('구분2', '')).strip(), 
             str(row.get('구분3', '')).strip(), 
             row['연도'],
             row['월'])
        data_map[k] = data_map.get(k, 0) + row[val_col]
        
    def get_val(mode, metric, keys, target_year, m_range):
        total = 0.0
        for g1, g2, g3 in keys:
            for m in m_range:
                total += data_map.get((mode, metric, g1, g2, g3, target_year, m), 0.0)
        return total

    # 3. 그룹별 키 매핑
    k_선재 = [('국내', '내수', '선재영업팀')]
    k_봉강 = [('국내', '내수', '봉강영업팀')]
    k_부산 = [('국내', '내수', '부산영업소')]
    k_대구 = [('국내', '내수', '대구영업소')]
    k_내수 = k_선재 + k_봉강 + k_부산 + k_대구
    
    k_수출 = [('국내', '수출', '글로벌영업팀')]
    k_국내선재 = k_내수 + k_수출
    k_국내AT = [('국내', '국내(AT)', 'AT_국내')]
    k_국내계 = k_국내선재 + k_국내AT
    
    k_남통 = [('중국', '포스세아', '남통')]
    k_천진 = [('중국', '포스세아', '천진')]
    k_포스세아 = k_남통 + k_천진
    k_기차배건 = [('중국', '기차배건', 'AT_기차배건')]
    k_중국계 = k_포스세아 + k_기차배건
    
    k_태국계 = [('태국', '태국', '태국')]
    k_멕시코계 = [('멕시코', 'SGAM', 'AT_멕시코')]

    k_Total = k_국내계 + k_중국계 + k_태국계 + k_멕시코계
    k_선재계 = k_국내선재 + k_포스세아 + k_태국계
    k_AT계 = k_국내AT + k_기차배건 + k_멕시코계

    # 4. 표에 출력될 행 정의 (이미지 기반 예외처리 추가)
    # vol_keys: 판매량 집계 시 별도로 참조할 키 (단위가 섞이는 걸 방지)
    rows_info = [
        {'label': '선재영업팀', 'keys': k_선재, 'lv': 2, 'is_AT': False},
        {'label': '봉강영업팀', 'keys': k_봉강, 'lv': 2, 'is_AT': False},
        {'label': '부산영업소', 'keys': k_부산, 'lv': 2, 'is_AT': False},
        {'label': '대구영업소', 'keys': k_대구, 'lv': 2, 'is_AT': False},
        {'label': '내수', 'keys': k_내수, 'lv': 1, 'bold': True, 'is_AT': False},
        {'label': '수출 (글로벌영업팀)', 'keys': k_수출, 'lv': 1, 'bold': True, 'is_AT': False},
        {'label': '선재_국내', 'keys': k_국내선재, 'lv': 0, 'bold': True, 'is_AT': False},
        {'label': 'AT_국내', 'keys': k_국내AT, 'lv': 0, 'bold': True, 'is_AT': True},
        # 🟢 국내 계: 판매량은 '국내선재'만 가져오고, 단가는 숨김
        {'label': '국내 계', 'keys': k_국내계, 'vol_keys': k_국내선재, 'lv': 0, 'bold': True, 'bg': '#E9ECEF', 'skip_price': True},

        {'label': '선재_남통', 'keys': k_포스세아, 'lv': 1, 'bold': True, 'is_AT': False},
        {'label': 'AT_중국', 'keys': k_기차배건, 'lv': 1, 'bold': True, 'is_AT': True},
        # 🟢 중국 계: 판매량은 '포스세아(선재)'만 가져오고, 단가는 숨김
        {'label': '중국 계', 'keys': k_중국계, 'vol_keys': k_포스세아, 'lv': 0, 'bold': True, 'bg': '#E9ECEF', 'skip_price': True},

        {'label': '선재_태국', 'keys': k_태국계, 'lv': 0, 'bold': True, 'bg': '#E9ECEF', 'is_AT': False},
        {'label': 'AT_멕시코', 'keys': k_멕시코계, 'lv': 0, 'bold': True, 'bg': '#E9ECEF', 'is_AT': True},
        # 🟢 Total: 판매량, 단가 모두 숨김
        {'label': 'Total', 'keys': k_Total, 'lv': 0, 'bold': True, 'bg': '#53565A', 'color': 'white', 'skip_vol': True, 'skip_price': True},
        
        {'label': '선재 계', 'keys': k_선재계, 'lv': 0, 'bold': True, 'is_AT': False},
        {'label': 'A T 계', 'keys': k_AT계, 'lv': 0, 'bold': True, 'is_AT': True},
    ]

    # 각 지표 계산 로직 (vol_keys 우선 참조)
    def calc_metrics(mode, keys, m_range, is_AT, vol_keys=None):
        v_target_keys = vol_keys if vol_keys else keys
        
        v_raw = get_val(mode, '판매량', v_target_keys, int(year), m_range)
        r_raw = get_val(mode, '매출액', keys, int(year), m_range)
        
        v = (v_raw / 1000.0) if is_AT else v_raw
        r = r_raw / 100_000.0
        p = (r_raw / v) if v != 0 else 0
        
        return v, p, r

    # 셀 렌더링 (단가와 판매량 스킵을 분리)
    def td(val, is_pct=False, bg='', color='', skip=False):
        if skip or val is None:
            return f"<td style='background:{bg}; border:1px solid #DEE2E6;'></td>"
        
        c = color
        if val < 0: c = '#DC2626'
            
        v_abs = abs(val)
        s = f"{v_abs:,.0f}%" if is_pct else f"{v_abs:,.0f}"
        if val < 0: s = f"-{s}"
            
        style = "padding:6px 10px; text-align:right; border:1px solid #DEE2E6; white-space:nowrap;"
        if bg: style += f" background:{bg};"
        if c: style += f" color:{c};"
        
        return f"<td style='{style}'>{s}</td>"

    # 5. 본문 생성
    body_html = ""
    for r in rows_info:
        keys = r['keys']
        vol_keys = r.get('vol_keys')
        skip_vol = r.get('skip_vol', False)
        skip_price = r.get('skip_price', False)
        is_AT = r.get('is_AT', False)
        
        bg = r.get('bg', '#ffffff')
        txt_col = r.get('color', '#333333')
        fw = '700' if r.get('bold') else '400'
        lv = r.get('lv', 0)
        
        # 데이터 계산
        py_v, py_p, py_r = calc_metrics('계획', keys, range(1, 13), is_AT, vol_keys)
        pc_v, pc_p, pc_r = calc_metrics('계획', keys, range(1, month + 1), is_AT, vol_keys)
        ac_v, ac_p, ac_r = calc_metrics('실적', keys, range(1, month + 1), is_AT, vol_keys)
        
        var_v = ac_v - pc_v
        var_p = ac_p - pc_p
        var_r = ac_r - pc_r
        
        ach_v = (ac_v / pc_v * 100) if pc_v else 0
        ach_r = (ac_r / pc_r * 100) if pc_r else 0
        
        td_label_style = f"padding:6px 10px; text-align:left; border:1px solid #DEE2E6; font-weight:{fw}; background:{bg}; color:{txt_col};"
        label_html = f"<td style='{td_label_style}'><span style='padding-left:{lv*16}px'>{r['label']}</span></td>"
        
        body_html += "<tr>" + label_html
        
        # skip_vol, skip_price를 각각 필요한 열에 독립적으로 적용
        body_html += td(py_v, bg=bg, color=txt_col, skip=skip_vol)
        body_html += td(py_p, bg=bg, color=txt_col, skip=skip_price)
        body_html += td(py_r, bg=bg, color=txt_col)
        
        body_html += td(pc_v, bg=bg, color=txt_col, skip=skip_vol)
        body_html += td(pc_p, bg=bg, color=txt_col, skip=skip_price)
        body_html += td(pc_r, bg=bg, color=txt_col)
        
        body_html += td(ac_v, bg=bg, color=txt_col, skip=skip_vol)
        body_html += td(ac_p, bg=bg, color=txt_col, skip=skip_price)
        body_html += td(ac_r, bg=bg, color=txt_col)
        
        body_html += td(var_v, bg=bg, color=txt_col, skip=skip_vol)
        body_html += td(var_p, bg=bg, color=txt_col, skip=skip_price)
        body_html += td(var_r, bg=bg, color=txt_col)
        
        body_html += td(ach_v, is_pct=True, bg=bg, color=txt_col, skip=skip_vol)
        body_html += td(ach_r, is_pct=True, bg=bg, color=txt_col)
        
        body_html += "</tr>"

    # 6. 헤더 생성
    th_st = f"padding:8px 10px; text-align:center !important; border:1px solid #DEE2E6; background:{_C_NAVY}; color:white; font-weight:700; white-space:nowrap;"
    header_html = f"""
    <tr>
        <th rowspan="2" style="{th_st}">구분</th>
        <th colspan="3" style="{th_st}">사업 계획 (연간)</th>
        <th colspan="3" style="{th_st}">사업 계획 (누적)</th>
        <th colspan="3" style="{th_st}">실적 (누적)</th>
        <th colspan="3" style="{th_st}">실적 - 계획</th>
        <th colspan="2" style="{th_st}">달성률(%)</th>
    </tr>
    <tr>
        <th style="{th_st}">판매량</th><th style="{th_st}">단가</th><th style="{th_st}">매출액</th>
        <th style="{th_st}">판매량</th><th style="{th_st}">단가</th><th style="{th_st}">매출액</th>
        <th style="{th_st}">판매량</th><th style="{th_st}">단가</th><th style="{th_st}">매출액</th>
        <th style="{th_st}">판매량</th><th style="{th_st}">단가</th><th style="{th_st}">매출액</th>
        <th style="{th_st}">판매량</th><th style="{th_st}">매출액</th>
    </tr>
    """

    return f"""
    <div style='overflow-x:auto; width:100%;'>
        <table style='border-collapse:collapse; width:100%; font-size:14px; min-width:1100px;'>
            <thead>{header_html}</thead>
            <tbody>{body_html}</tbody>
        </table>
    </div>
    """


def _build_이익계획실적_table(year, month):
    df = load_sheet(Sheets.이익계획및실적_DB)
    df['값'] = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    for c in ['구분1', '구분2', '구분3', '구분4', '계획/실적']:
        df[c] = df[c].fillna('').astype(str).str.strip()

    val_map = df.groupby(['계획/실적', '구분4', '구분1', '구분2', '구분3', '연도', '월'])['값'].sum().to_dict()

    def get_val(mode, g1, g2, metric, yr, mo):
        return val_map.get((mode, '당월', g1, g2, metric, yr, mo), 0.0)

    def sum_range(mode, keys, metric, yr, m_range):
        total = 0.0
        for g1, g2 in keys:
            for m in m_range:
                total += get_val(mode, g1, g2, metric, yr, m)
        return total

    # 사업장 키
    k_국내선재 = [('국내', '선재')]
    k_국내AT   = [('국내', 'AT')]
    k_국내계   = k_국내선재 + k_국내AT

    k_포스세아남통 = [('해외', '포스세아남통')]
    k_기차배건    = [('해외', '기차배건')]
    k_태국       = [('해외', '태국')]
    k_멕시코     = [('해외', '멕시코')]
    k_중국계     = k_포스세아남통 + k_기차배건
    k_해외계     = k_중국계 + k_태국 + k_멕시코

    k_Total  = k_국내계 + k_해외계
    k_선재계 = k_국내선재 + k_포스세아남통 + k_태국
    k_AT계   = k_국내AT + k_기차배건 + k_멕시코

    columns = ['사업계획(연간)', '사업계획(누적)', '실적(누적)', '실적-계획', '달성률(%)']
    div = 100_000  # 천원 → 억원

    def calc(keys, metric):
        연간계획 = sum_range('계획', keys, metric, year, range(1, 13))       / div
        누적계획 = sum_range('계획', keys, metric, year, range(1, month + 1)) / div
        누적실적 = sum_range('실적', keys, metric, year, range(1, month + 1)) / div
        차이    = 누적실적 - 누적계획
        달성률  = (누적실적 / 누적계획 * 100) if 누적계획 else 0
        return 연간계획, 누적계획, 누적실적, 차이, 달성률

    def build_rows(groups):
        rows = []
        for label, keys, bold, dark in groups:
            for i, metric in enumerate(['영업이익', '경상이익']):
                연간계획, 누적계획, 누적실적, 차이, 달성률 = calc(keys, metric)
                rows.append({
                    '사업장': label,
                    '_first': i == 0,
                    '_bold':  bold,
                    '_dark':  dark,
                    '구분':   metric,
                    columns[0]: _fmt(연간계획, decimal=1),
                    columns[1]: _fmt(누적계획, decimal=1),
                    columns[2]: _fmt(누적실적, decimal=1),
                    columns[3]: _fmt(차이,    decimal=1),
                    columns[4]: f'{_fmt(달성률, decimal=0)}%',
                })

                m_연간계획, m_누적계획, m_누적실적, *_ = calc(keys, '매출액')
                pr_연간   = (연간계획 / m_연간계획 * 100) if m_연간계획 else 0
                pr_누적계획 = (누적계획 / m_누적계획 * 100) if m_누적계획 else 0
                pr_누적실적 = (누적실적 / m_누적실적 * 100) if m_누적실적 else 0
                rows.append({
                    '사업장': label,
                    '_first': False,
                    '_bold':  bold,
                    '_dark':  dark,
                    '구분':   '(%)',
                    columns[0]: _fmt(pr_연간,   decimal=1),
                    columns[1]: _fmt(pr_누적계획, decimal=1),
                    columns[2]: _fmt(pr_누적실적, decimal=1),
                    columns[3]: _fmt(pr_누적실적 - pr_누적계획, decimal=1),
                    columns[4]: '',
                })
        return rows

    총계_groups = [
        ('국내(선재)', k_국내선재, False, False),
        ('국내(AT)',   k_국내AT,   False, False),
        ('국내 계',    k_국내계,   True,  False),
        ('해외 계',    k_해외계,   True,  False),
        ('총 계',      k_Total,    True,  True),
        ('선재 계',    k_선재계,   True,  False),
        ('AT 계',      k_AT계,     True,  False),
    ]
    해외상세_groups = [
        ('포스세아 남통', k_포스세아남통, False, False),
        ('기차배건',      k_기차배건,    False, False),
        ('중국 계',       k_중국계,      True,  False),
        ('태국 계',       k_태국,        True,  False),
        ('멕시코 계',     k_멕시코,      True,  False),
    ]

    return {
        '총계':       (build_rows(총계_groups), columns),
        '해외법인상세': (build_rows(해외상세_groups), columns),
    }


def _이익계획실적_to_html_table(rows, columns) -> str:
    headers = (f'<th style="{_TH}">사업장</th><th style="{_TH}">구분</th>'
               + ''.join(f'<th style="{_TH}">{c}</th>' for c in columns))

    # 각 행이 그룹(사업장)의 몇 번째 줄인지, 그리고 마지막 줄인지 미리 계산 (구분선 처리용)
    group_ids = []
    gid = -1
    for row in rows:
        if row['_first']:
            gid += 1
        group_ids.append(gid)

    rows_html = ''
    for i, row in enumerate(rows):
        is_first  = row['_first']
        is_last   = (i == len(rows) - 1) or (group_ids[i + 1] != group_ids[i])
        is_bold   = row.get('_bold', False)
        is_dark   = row.get('_dark', False)

        if is_dark:
            grp_bg, txt_col = _C_NAVY, 'white'
        else:
            grp_bg, txt_col = ('#E9ECEF' if is_bold else '#ffffff'), '#333333'
        fw = 'font-weight:700;' if is_bold else ''

        line_col      = 'white' if (is_bold and not is_dark) else '#e2e8f0'
        border_top    = f'border-top:3px solid {_C_NAVY};'   if (is_first and group_ids[i] > 0) else ''
        border_bottom = f'border-bottom:2px solid {_C_NAVY};' if is_last else f'border-bottom:1px solid {line_col};'
        border_left   = f'border-left:4px solid {_C_NAVY};'  if is_first else 'border-left:4px solid transparent;'

        corp_val = row['사업장'] if is_first else ''
        corp_fw  = 'font-weight:700;' if is_first or is_bold else ''
        cells    = (f'<td style="padding:6px 12px;text-align:center;{corp_fw}color:{txt_col};'
                    f'background:{grp_bg};{border_left}{border_top}{border_bottom}">{corp_val}</td>')

        cells += (f'<td style="padding:5px 10px;text-align:left;{fw}color:{txt_col};'
                  f'background:{grp_bg};{border_top}{border_bottom}">{row["구분"]}</td>')

        for h in columns:
            s     = str(row[h])
            color = f';color:{_C_RED}' if s.startswith('-') else f';color:{txt_col}'
            cells += (f'<td style="padding:5px 10px;text-align:right;{fw}'
                      f'background:{grp_bg};{border_top}{border_bottom}{color}">{s}</td>')

        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'

    return _html_table(f'<tr>{headers}</tr>', rows_html)


def _이익계획실적_section(title, tabs_data, memo='', unit='[단위: 억원]'):
    prefix = "pl"  # 이익계획및실적 고유 접두사 (Profit/Loss plan)
    tab_names = list(tabs_data.keys())
    safe = [n.replace(' ', '_').replace('(', '').replace(')', '') for n in tab_names]

    hide_sel = ', '.join(f'#fp_{prefix}_{s}' for s in safe)
    css = f'{hide_sel}{{display:none}}'
    for s in safe:
        css += (f'#ft_{prefix}_{s}:checked~#fp_{prefix}_{s}{{display:block!important}}'
                f'#ft_{prefix}_{s}:checked~.ftbar>#fl_{prefix}_{s}'
                f'{{background:{_C_NAVY}!important;color:white!important;border-color:{_C_NAVY}!important}}')

    inputs = ''.join(
        f'<input type="radio" id="ft_{prefix}_{s}" name="ftab_{prefix}" {"checked" if i == 0 else ""} '
        f'style="position:absolute;opacity:0;pointer-events:none">'
        for i, s in enumerate(safe)
    )

    tab_bar = f'<div class="ftbar" style="display:flex;margin-bottom:6px;border-bottom:2px solid {_C_NAVY}">'
    tab_bar += ''.join(
        f'<label id="fl_{prefix}_{s}" for="ft_{prefix}_{s}" style="padding:5px 16px;cursor:pointer;'
        f'border:1px solid #DEE2E6;border-bottom:none;margin-right:2px;'
        f'font-size:0.9em;font-weight:500;border-radius:4px 4px 0 0;'
        f'background:white;color:#555">{name}</label>'
        for name, s in zip(tab_names, safe)
    )
    tab_bar += '</div>'

    panels = ''.join(
        f'<div id="fp_{prefix}_{s}">{_이익계획실적_to_html_table(*tabs_data[name])}</div>'
        for name, s in zip(tab_names, safe)
    )

    tab_html = f'<style>{css}</style>' + inputs + tab_bar + panels
    return _layout64(title, tab_html, memo, unit)


# ── 페이지 렌더 ───────────────────────────────────────────────

def render_page(app, year_state, month_state):
    
    def _render_title():
        app.markdown(
            f'<h1 style="color:#404448">{int(year_state.value)}년 {int(month_state.value)}월 실적요약</h1>',
            unsafe_allow_html=True,
        )
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["주요경영지표(해외법인 포함)", "주요경영지표(선재_국내)", "연간사업계획"])
    
    with tabs[0]:
        def _render_포함():
            year, month = int(year_state.value), int(month_state.value)
            get, 사업장_list = _load_손익()

            memo1 = _get_memo(Sheets.손익_메모, year, month)
            app.markdown(_section("1) 손익 (연결)", _build_포함_table(get, 사업장_list, year, month), memo1),
                         unsafe_allow_html=True)

            df_현금, 소계행_현금, 헤더행_현금, 사업장_현금 = _build_현금흐름표_연결_table(year, month)
            memo2 = _get_memo(Sheets.현금흐름표_연결_메모, year, month)
            app.markdown(_현금흐름표_연결_section("2) 현금흐름표 (연결)", df_현금, 소계행_현금, 헤더행_현금, 사업장_현금, memo2),
                         unsafe_allow_html=True)

            per_corp_dfs, 소계행, 헤더행, corp_labels = _build_재무상태표_table(year, month)
            memo3 = _get_memo(Sheets.재무상태표_메모, year, month)
            app.markdown(_재무_section("3) 재무상태표 (연결)", per_corp_dfs, 소계행, 헤더행, corp_labels, memo3),
                         unsafe_allow_html=True)
            
            rows_회전, sub_회전 = _build_회전일_table(year, month)
            memo4 = _get_memo(Sheets.회전일_메모, year, month)
            app.markdown(_layout64("4) 회전일",
                                   _회전일_to_html_table(rows_회전, sub_회전),
                                   memo4, '[단위: 일]'),
                         unsafe_allow_html=True)

            rows_수익성, sub_수익성 = _build_수익성_연결_table(year, month)
            memo5 = _get_memo(Sheets.수익성_메모_연결, year, month)
            app.markdown(_layout64("5) 수익성",
                                   _회전일_to_html_table(rows_수익성, sub_수익성),
                                   memo5, '[단위: %]'),
                         unsafe_allow_html=True)

        app.If(lambda: True, _render_포함)

    with tabs[1]:
        def _render_국내():
            year, month = int(year_state.value), int(month_state.value)
            get, _ = _load_손익()
            memo1 = _get_memo(Sheets.손익_국내_메모, year, month)
            app.markdown(_section("1) 손익 (별도)", _build_국내_table(get, year, month), memo1),
                         unsafe_allow_html=True)
            
            
            memo2 = ""
            app.markdown(_section("2) 품목손익 (별도, 재경기준 : 원재료 희석, 재고 영향 반영)", _build_품목손익_별도_table(year, month), memo2),
                         unsafe_allow_html=True)

            memo3 = _get_memo(Sheets.수정원가기준손익_메모, year, month)
            app.markdown(_section("3) 수정원가기준손익 (별도)", _build_수정원가기준손익_별도_table(year, month), memo3),
                         unsafe_allow_html=True)
            
            app.markdown(_원재료_section("4) 원재료 입고-기초 단가 차이", _build_원재료입고기초단가차이_table(year, month), "", '[단위: 톤, 백만원]'),
                         unsafe_allow_html=True)
            app.markdown('<div style="font-size:0.85em;color:gray;margin:2px 0 12px 0">※ 산출기준 : 대구분/내외자/강종류/강종/메이커</div>',
                         unsafe_allow_html=True)

            app.markdown(_원재료_section("5) 원재료 입고-기초 단가 차이 거래처 기준", _build_원재료입고단가차이_거래처기준_table(year, month), "", '[단위: 톤, 백만원]'),
                         unsafe_allow_html=True)
            app.markdown('<div style="font-size:0.85em;color:gray;margin:2px 0 12px 0">※ 산출기준 : 메이커/산업재/강종</div>',
                         unsafe_allow_html=True)

            app.markdown(_section("6) 제품수불표 (별도)", _build_제품수불표_table(year, month), "", '[단위: 원, 백만원]'),
                         unsafe_allow_html=True)
            app.markdown('<div style="font-size:0.85em;color:gray;margin:2px 0 12px 0">※ 산출기준 : 품목/내수/열처리/대표공정/강종종류/수불강종/표준강종</div>',
                         unsafe_allow_html=True)

            memo7 = _get_memo(Sheets.현금흐름표_별도_메모, year, month)
            app.markdown(_layout64("7) 현금흐름표 (별도)", _build_현금흐름표_별도_table(year, month), memo7, '[단위: 백만원]'),
                         unsafe_allow_html=True)

            memo8 = _get_memo(Sheets.재무상태표_국내_메모, year, month)
            app.markdown(_layout64("8) 재무상태표 (별도)", _build_재무상태표_별도_table(year, month), memo8, '[단위: 백만원]'),
                         unsafe_allow_html=True)
            
            memo9 = _get_memo(Sheets.안정성_메모, year, month)
            app.markdown(_section("9) 안정성 (별도)", _build_안정성_별도_table(year, month), memo9, '[단위: %]'),
                         unsafe_allow_html=True)
            
            memo10 = _get_memo(Sheets.회전일_국내_메모, year, month)
            app.markdown(_section("10) 회전일 (별도)", _build_회전일_별도_table(year, month), memo10, '[단위: 일]'),
                         unsafe_allow_html=True)
            
            memo11 = _get_memo(Sheets.수익성_메모, year, month)
            app.markdown(_section("11) 수익성 (별도)", _build_수익성_별도_table(year, month), memo11, '[단위: %]'),
                         unsafe_allow_html=True)
            
        app.If(lambda: True, _render_국내)
        
    with tabs[2]:
        def _render_연간():
            year, month = int(year_state.value), int(month_state.value)
            html_table = _build_판매계획및실적_html(year, month)
            memo = _get_memo(Sheets.판매계획및실적_메모, year, month)
            
            app.markdown(_layout100("1) 판매계획 및 실적", html_table, memo, '[단위: 톤, 천개, 억원]'),
                         unsafe_allow_html=True)

            tabs_data = _build_이익계획실적_table(year, month)
            memo2 = _get_memo(Sheets.이익계획및실적_메모, year, month)
            app.markdown(_이익계획실적_section("2) 이익계획 및 실적", tabs_data, memo2, '[단위: 억원]'),
                         unsafe_allow_html=True)

        app.If(lambda: True, _render_연간)