import datetime
import pandas as pd
import plotly.graph_objects as go
from data.loader import load_sheet
from data.config import Sheets
from data.config import (
    Sheets,
    CORP_ORDER, 재무_CORP_ORDER, 재무_사업장_표시명,
    현금_CORP_ORDER, 현금_사업장_표시명, 현금_구분_순서,
    재무_소계행,
    SONIK_구분_순서, SONIK_표시명, SONIK_단위, SONIK_소수점, SONIK_PCT_대상,
    품목_구분_순서, 품목_단위, 품목_소수점, 품목_PCT_대상, 품목_PCT_소수점, 품목_PCT_품목, 품목_품목_순서,
    회전일_CORP_ORDER, 회전일_구분_순서, 회전일_사업장_표시명, 선재_국내_사업장, 현금_소계행, overseas_SONIK_표시명, overseas_SONIK_구분_순서,
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
    return f"'{str(year)[2:]}년 {month}월"


def _당월헤더(year, month, n):
    return f"'{str(year)[2:]}.{month}월 {''.join(_기호[:n])}"


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
    safe = [c.replace(' ', '_') for c in corp_labels]
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
    safe = [c.replace(' ', '_') for c in corp_labels]
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
        f"{month}월",
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
                sub_labels[0]:  _fmt(전기_v),
                sub_labels[1]:  _fmt(전월_v),
                sub_labels[2]:  _fmt(당월_v),
                sub_labels[3]:  _fmt(당월_v - 전월_v),
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

def _get_손익차이_memo(year, month, corp) -> str:
    # 손익차이 메모 시트 로드
    df = load_sheet(Sheets.해외손익차이_메모)
    
    if df.empty:
        return ''
        
    df.columns = df.columns.str.strip()
    
    if '년도' in df.columns and '연도' not in df.columns:
        df.rename(columns={'년도': '연도'}, inplace=True)

    if '연도' not in df.columns or '월' not in df.columns:
        return ''
        
    df['연도'] = df['연도'].astype(str).str.strip()
    df['월']   = df['월'].astype(str).str.strip()
    
    row = df[(df['연도'] == str(year)) & (df['월'] == str(month))]
    
    if row.empty:
        return ''
        
    # 사업장에 따라 메모1(중국) 또는 메모2(태국) 컬럼 매핑
    if corp == '중국' and '메모1' in df.columns:
        memo_val = row.iloc[0]['메모1']
    elif corp == '태국' and '메모2' in df.columns:
        memo_val = row.iloc[0]['메모2']
    else:
        return ''
        
    # NaN이나 None 처리
    if pd.isna(memo_val):
        return ''
        
    return str(memo_val)

# ── 데이터 로드 ───────────────────────────────────────────────
def _load_손익():
    df = load_sheet(Sheets.해외손익요약_DB)
    df['값']  = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    df['연도'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    df['월'] = pd.to_numeric(df['월'], errors='coerce').fillna(0).astype(int)
    
    df['사업장'] = df['사업장'].astype(str).str.strip()
    df['구분1'] = df['구분1'].astype(str).str.strip()
    df['계획/실적'] = df['계획/실적'].astype(str).str.strip()
    # ----------------------------------------------------

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
    
    if df.empty:
        return ''
        
    # 컬럼명 공백 제거
    df.columns = df.columns.str.strip()
    
    # '년도' 컬럼이 존재하면 '연도'로 이름 변경
    if '년도' in df.columns and '연도' not in df.columns:
        df.rename(columns={'년도': '연도'}, inplace=True)

    # 필수 컬럼이 여전히 없으면 빈 문자열 반환
    if '연도' not in df.columns or '월' not in df.columns:
        return ''
        
    df['연도'] = df['연도'].astype(str).str.strip()
    df['월']   = df['월'].astype(str).str.strip()
    row = df[(df['연도'] == str(year)) & (df['월'] == str(month))]
    return str(row.iloc[0]['메모']) if not row.empty else ''


def _build_중국_table(get, year, month, 사업장='중국'):
    yr2, mo2 = _prev(year, month, 1)
    전월_col  = _월헤더(yr2, mo2)

    columns = ['구분', 전월_col,
               '당월_계획', '당월_실적', '당월_계획대비', '당월_전월대비',
               '누적_계획', '누적_실적', '누적_계획대비']

    rows, 매출액 = [], {}

    # 수정됨: 중국도 overseas_SONIK_구분_순서 사용
    for g in overseas_SONIK_구분_순서:
        div      = 1  # 수정됨: 시트 데이터가 이미 백만원/톤 단위이므로 1,000,000으로 나누지 않음
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
            '구분':          overseas_SONIK_표시명[g],
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

def _build_태국_table(get, year, month, 사업장='태국'):
    yr2, mo2 = _prev(year, month, 1)
    전월_col  = _월헤더(yr2, mo2)

    columns = ['구분', 전월_col,
               '당월_계획', '당월_실적', '당월_계획대비', '당월_전월대비',
               '누적_계획', '누적_실적', '누적_계획대비']

    rows, 매출액 = [], {}

    for g in overseas_SONIK_구분_순서:
        div      = 1  # 수정됨: 시트 데이터가 이미 백만원/톤 단위이므로 1,000,000으로 나누지 않음
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
            '구분':          overseas_SONIK_표시명[g],
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

def _build_해외현금흐름표_base(year, month, corp):
    df = load_sheet(Sheets.해외현금흐름_DB)
    
    # 1. 값 컬럼 정리
    val_col = '값'
    df[val_col] = df[val_col].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    # 2. 지정된 사업장(중국 or 태국) 데이터만 필터링
    df = df[df['사업장'] == corp].copy()

    # 3. 구분 컬럼 정제 (이미지에 맞춰 구분1~3만 사용)
    for c in ['구분1', '구분2', '구분3']:
        df[c] = df[c].fillna('').astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

    # 4. 데이터 롤업(Roll-up) 해시맵 생성
    val_map = {}
    for _, row in df.iterrows():
        y, m = int(row['연도']), int(row['월'])
        g1, g2, g3 = row['구분1'], row['구분2'], row['구분3']
        v = row[val_col]
        if v == 0: continue
        
        def add(k_g1, k_g2, k_g3):
            key = (y, m, k_g1, k_g2, k_g3)
            val_map[key] = val_map.get(key, 0.0) + v
        
        add(g1, g2, g3)
        if g3: add(g1, g2, '')
        if g2 or g3: add(g1, '', '')

    def get_val(yr, mo, g1, g2, g3):
        return val_map.get((yr, mo, g1, g2, g3), 0.0)

    # 5. 조회 로직: 구분4(당월/누적)가 없으므로 해당 월까지 1~M월을 합산
    def get_accumulated(yr, target_mo, g1, g2, g3):
        return sum(get_val(yr, m, g1, g2, g3) for m in range(1, target_mo + 1))

    # 6. 표 뼈대 생성 (해당 연도에 존재하는 모든 구분 항목 추출)
    target = df[df['연도'] == year].copy()
    tree = {}
    for _, row in target.iterrows():
        g1, g2, g3 = row['구분1'], row['구분2'], row['구분3']
        if not g1: continue
        if g1 not in tree: tree[g1] = {}
        if g2:
            if g2 not in tree[g1]: tree[g1][g2] = []
            if g3 and g3 not in tree[g1][g2]: tree[g1][g2].append(g3)

    # 7. 행 조립 및 계산
    rows = []
    소계행 = set(tree.keys()) | 현금_소계행
    
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
        final_rows.append({
            '구분':        r['label'],
            '_depth':      r['depth'],
            sub_labels[0]: _fmt(get_accumulated(yr_y2, 12, g1, g2, g3)),
            sub_labels[1]: _fmt(get_accumulated(yr_y1, 12, g1, g2, g3)),
            sub_labels[2]: _fmt(get_accumulated(year, month - 1, g1, g2, g3)),
            sub_labels[3]: _fmt(get_val(year, month, g1, g2, g3)),
            sub_labels[4]: _fmt(get_accumulated(year, month, g1, g2, g3)),
        })

    if not final_rows:  # 빈 데이터프레임 방지
        return _현금흐름표_연결_to_html_table(pd.DataFrame(columns=['구분', '_depth'] + sub_labels), 소계행, set())

    return _현금흐름표_연결_to_html_table(pd.DataFrame(final_rows), 소계행, set())


def _build_현금흐름표_중국_table(year, month):
    return _build_해외현금흐름표_base(year, month, '중국')


def _build_현금흐름표_태국_table(year, month):
    return _build_해외현금흐름표_base(year, month, '태국')

def _build_해외재무상태표_base(year, month, corp):
    df = load_sheet(Sheets.해외재무상태표_DB)
    df['값'] = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    # 지정된 사업장만 필터링
    df = df[df['사업장'] == corp]

    # 과거 3개년말 및 전월 계산
    yr_y3, yr_y2, yr_y1 = year - 3, year - 2, year - 1
    yr_전월, mo_전월 = _prev(year, month, 1)

    sub_labels = [
        f"'{str(yr_y3)[2:]}년말",
        f"'{str(yr_y2)[2:]}년말",
        f"'{str(yr_y1)[2:]}년말",
        f"'{str(yr_전월)[2:]} 전월",
        "당월",
        "전월비"
    ]

    # 첨부된 이미지 구조에 따른 소계행 및 항목 순서 (소계가 하단으로 이동)
    해외_재무_소계행 = ['자산총계', '부채총계', '자본총계', '부채 및 자본 총계']
    행_순서_final = [
        ('자산총계', '현금및현금성자산'), 
        ('자산총계', '매출채권'), 
        ('자산총계', '재고자산'), 
        ('자산총계', '유형자산'), 
        ('자산총계', '기타자산'),
        ('자산총계', '자산총계'),  # 소계
        
        ('부채총계', '매입채무'), 
        ('부채총계', '차입금'), 
        ('부채총계', '기타부채'),
        ('부채총계', '부채총계'),  # 소계
        
        ('자본총계', '자본금'), 
        ('자본총계', '기타(외화환산 포함)'),
        ('자본총계', '자본총계'),  # 소계
        
        ('총계', '부채 및 자본 총계') # 최종 합계
    ]

    # 조회용 Map 생성
    val_map = df.set_index(['연도', '월', '구분1', '구분2'])['값'].to_dict()

    # 특정 연월/구분의 값을 조회하는 내부 함수 (총계 자동 계산)
    def get_val(yr, mo, g1, g2):
        # 1. 부채 및 자본 총계: 부채총계 합산값 + 자본총계 합산값
        if g1 == '총계' and g2 == '부채 및 자본 총계':
            부채_sum = sum(val_map.get((yr, mo, '부채총계', d), 0.0) for g, d in 행_순서_final if g == '부채총계' and d != '부채총계')
            자본_sum = sum(val_map.get((yr, mo, '자본총계', d), 0.0) for g, d in 행_순서_final if g == '자본총계' and d != '자본총계')
            return 부채_sum + 자본_sum
            
        # 2. 일반 소계(자산총계, 부채총계, 자본총계): 해당 그룹의 하위 항목 합산
        elif g1 == g2:
            return sum(val_map.get((yr, mo, g1, d), 0.0) for g, d in 행_순서_final if g == g1 and d != g1)
            
        # 3. 그 외 상세 항목: 딕셔너리에서 직접 조회
        else:
            return val_map.get((yr, mo, g1, g2), 0.0)

    columns = ['구분', '_depth'] + sub_labels
    헤더행 = set()
    rows = []

    for g1, g2 in 행_순서_final:
        label = g2
        depth = 0 if label in 해외_재무_소계행 else 1
        
        v_y3   = get_val(yr_y3, 12, g1, g2)
        v_y2   = get_val(yr_y2, 12, g1, g2)
        v_y1   = get_val(yr_y1, 12, g1, g2)
        v_prev = get_val(yr_전월, mo_전월, g1, g2)
        v_curr = get_val(year, month, g1, g2)
        v_diff = v_curr - v_prev

        rows.append({
            '구분':        label,
            '_depth':      depth,
            sub_labels[0]: _fmt(v_y3),
            sub_labels[1]: _fmt(v_y2),
            sub_labels[2]: _fmt(v_y1),
            sub_labels[3]: _fmt(v_prev),
            sub_labels[4]: _fmt(v_curr),
            sub_labels[5]: _fmt(v_diff),
        })

    render_df = pd.DataFrame(
        {col: [r.get(col, '') for r in rows] for col in columns}
    )

    return _재무_to_html_table(render_df, 해외_재무_소계행, 헤더행)


def _build_재무상태표_중국_table(year, month):
    return _build_해외재무상태표_base(year, month, '중국')


def _build_재무상태표_태국_table(year, month):
    return _build_해외재무상태표_base(year, month, '태국')

def _build_해외판매구성_table(year, month):
    # 판매구성 DB 로드
    df = load_sheet(Sheets.해외등급별판매_DB) 
    
    # 컬럼명 공백 제거 (KeyError 방지)
    df.columns = df.columns.str.strip()
    
    # 시트가 비어있거나 필수 컬럼이 없으면 빈 데이터프레임 반환
    if df.empty or '연도' not in df.columns:
        return pd.DataFrame()
        
    df['값'] = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    # 연도, 월, 사업장, 구분1, 구분2 기준으로 값 합산
    val_map = df.groupby(['연도', '월', '사업장', '구분1', '구분2'])['값'].sum().to_dict()

    def get_v(yr, mo, corp, g1, g2):
        if yr == year - 1:
            # 전년도는 1~12월 전체 합산
            return sum(val for (k_y, k_m, k_c, k_g1, k_g2), val in val_map.items() 
                       if k_y == yr and k_c == corp and k_g1 == g1 and k_g2 == g2)
        return val_map.get((yr, mo, corp, g1, g2), 0.0)

    yr_m1, mo_m1 = _prev(year, month, 1)
    yr_m2, mo_m2 = _prev(yr_m1, mo_m1, 1)

    cols_periods = [
        (year - 1, None),
        (yr_m2, mo_m2),
        (yr_m1, mo_m1),
        (year, month)
    ]

    c1 = f"'{str(year - 1)[2:]}년"
    c2 = f"'{str(yr_m2)[2:]}년 {mo_m2}월"
    c3 = f"'{str(yr_m1)[2:]}년 {mo_m1}월"
    c4 = f"'{str(year)[2:]}년 {month}월"
    c5 = f"'{str(year)[2:]}년 {month}월 전월대비 증감"
    c6 = f"'{str(year)[2:]}년 {month}월 전월대비 증감률 %"
    
    columns = ['구분', c1, c2, c3, c4, c5, c6]
    all_rows = []

    def calc_metrics(corp, sub_items):
        rows = []
        
        def get_series(g1, g2):
            return [get_v(y, m, corp, g1, g2) for y, m in cols_periods]
        
        def get_b_series():
            res = []
            for y, m in cols_periods:
                if y == year - 1:
                    v = sum(val for (k_y, k_m, k_c, k_g1, k_g2), val in val_map.items() if k_y == y and k_c == corp and k_g1 == 'B급')
                else:
                    v = sum(val for (k_y, k_m, k_c, k_g1, k_g2), val in val_map.items() if k_y == y and k_m == m and k_c == corp and k_g1 == 'B급')
                res.append(v)
            return res

        posco = get_series('정품', 'POSCO')
        seah = get_series('정품', '세아특수강')
        local = get_series('정품', '로컬') if '로컬' in sub_items else [0,0,0,0]
        gita = get_series('정품', '기타') if '기타' in sub_items else [0,0,0,0]
        
        b_grade = get_b_series()
        
        # 합계 로직
        jungpum = [posco[i] + seah[i] + local[i] + gita[i] for i in range(4)]
        total = [jungpum[i] + b_grade[i] for i in range(4)]
        
        # 비율 로직 (POSCO 비중, B급 비중)
        posco_pct = [posco[i]/jungpum[i] if jungpum[i] else 0.0 for i in range(4)]
        b_pct = [b_grade[i]/total[i] if total[i] else 0.0 for i in range(4)]
        
        def fmt_pct_val(v):
            return f"{v*100:.1f}%"
            
        def fmt_row(label, series, is_pct_row=False):
            v_m1 = series[2]
            v_m = series[3]
            
            diff = v_m - v_m1
            diff_pct = (v_m / v_m1 - 1) if v_m1 != 0 else 0.0
            
            if is_pct_row:
                return {
                    '구분': label,
                    c1: fmt_pct_val(series[0]),
                    c2: fmt_pct_val(series[1]),
                    c3: fmt_pct_val(series[2]),
                    c4: fmt_pct_val(series[3]),
                    c5: fmt_pct_val(diff),
                    c6: fmt_pct_val(diff_pct)
                }
            else:
                return {
                    '구분': label,
                    c1: _fmt(series[0]),
                    c2: _fmt(series[1]),
                    c3: _fmt(series[2]),
                    c4: _fmt(series[3]),
                    c5: _fmt(diff),
                    c6: fmt_pct_val(diff_pct)
                }

        rows.append(fmt_row('POSCO', posco))
        rows.append(fmt_row('세아특수강', seah))
        if '로컬' in sub_items: rows.append(fmt_row('로컬', local))
        if '기타' in sub_items: rows.append(fmt_row('기타', gita))
        
        rows.append(fmt_row('POSCO %', posco_pct, True))
        rows.append(fmt_row('정품', jungpum))
        rows.append(fmt_row('B급', b_grade))
        rows.append(fmt_row('%', b_pct, True))
        rows.append(fmt_row(corp, total)) # 법인 합계 (중국/태국)
        
        return rows

    all_rows.extend(calc_metrics('중국', ['POSCO', '세아특수강', '로컬']))
    all_rows.extend(calc_metrics('태국', ['POSCO', '세아특수강', '기타']))
    
    return pd.DataFrame(all_rows)

def _등급별판매현황_to_html_table(df):
    rows_html = ''
    for idx, row in df.iterrows():
        label = str(row.iloc[0])
        is_total = label in ['중국', '태국']
        
        # '중국', '태국' 행은 약간의 배경색과 Bold 처리
        bg = f'background:#f8f9fa;' if is_total else ''
        fw = 'font-weight:700;' if is_total else ''
        
        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            align = 'center' if i == 0 else 'right'
            color = f';color:{_C_RED}' if s.startswith('-') else ''
            cells += f'<td style="padding:6px 12px;text-align:{align};border-bottom:1px solid #e2e8f0;{bg}{fw}{color}">{s}</td>'
        
        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'
    
    headers = ''.join(f'<th style="{_TH};text-align:center">{c}</th>' for c in df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)

def _build_세부판매현황_base_table(year, month, sheet_info, g1_name, g3_items, pct_target=None):
    """
    구분1(g1_name)과 구분3 항목리스트(g3_items)를 동적으로 받아 판매현황 표를 생성합니다.
    pct_target이 지정되면 해당 항목의 비중(%)을 추가로 계산합니다.
    """
    df = load_sheet(sheet_info) 
    
    if df.empty:
        return pd.DataFrame()
        
    df.columns = df.columns.str.strip()
    if '년도' in df.columns and '연도' not in df.columns:
        df.rename(columns={'년도': '연도'}, inplace=True)
        
    if '연도' not in df.columns or '월' not in df.columns:
        return pd.DataFrame()
        
    df['값'] = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    # 인자로 받은 구분1 항목만 필터링
    df = df[df['구분1'] == g1_name]

    # 구분2: 사업장(중국, 태국), 구분3: 상세항목
    val_map = df.groupby(['연도', '월', '구분2', '구분3'])['값'].sum().to_dict()

    def get_v(yr, mo, corp, item):
        if yr == year - 1:
            return sum(val for (k_y, k_m, k_c, k_item), val in val_map.items() 
                       if k_y == yr and k_c == corp and k_item == item)
        return val_map.get((yr, mo, corp, item), 0.0)

    yr_m1, mo_m1 = _prev(year, month, 1)
    yr_m2, mo_m2 = _prev(yr_m1, mo_m1, 1)

    cols_periods = [
        (year - 1, None),
        (yr_m2, mo_m2),
        (yr_m1, mo_m1),
        (year, month)
    ]

    c1 = f"'{str(year - 1)[2:]}년"
    c2 = f"'{str(yr_m2)[2:]}년 {mo_m2}월"
    c3 = f"'{str(yr_m1)[2:]}년 {mo_m1}월"
    c4 = f"'{str(year)[2:]}년 {month}월"
    c5 = f"'{str(year)[2:]}년 {month}월 전월대비 증감"
    c6 = f"'{str(year)[2:]}년 {month}월 전월대비 증감률 %"
    
    columns = ['구분', '_depth', c1, c2, c3, c4, c5, c6]
    all_rows = []

    def calc_metrics(corp):
        rows = []
        
        # 각 구분3 항목별 데이터 추출
        series_dict = {item: [get_v(y, m, corp, item) for y, m in cols_periods] for item in g3_items}
        
        # 합계 계산
        total = [sum(series_dict[item][i] for item in g3_items) for i in range(4)]
        
        # 비중(%) 계산
        if pct_target and pct_target in series_dict:
            pct_series = [series_dict[pct_target][i]/total[i] if total[i] else 0.0 for i in range(4)]
        else:
            pct_series = [0, 0, 0, 0]
        
        def fmt_pct_val(v):
            return f"{v*100:.1f}%"
            
        def fmt_row(label, series, is_pct_row=False, depth=1):
            v_m1 = series[2]
            v_m = series[3]
            
            diff = v_m - v_m1
            diff_pct = (v_m / v_m1 - 1) if v_m1 != 0 else 0.0
            
            if is_pct_row:
                return {
                    '구분': label,
                    '_depth': depth,
                    c1: fmt_pct_val(series[0]),
                    c2: fmt_pct_val(series[1]),
                    c3: fmt_pct_val(series[2]),
                    c4: fmt_pct_val(series[3]),
                    c5: fmt_pct_val(diff),  
                    c6: fmt_pct_val(diff_pct)
                }
            else:
                return {
                    '구분': label,
                    '_depth': depth,
                    c1: _fmt(series[0]),
                    c2: _fmt(series[1]),
                    c3: _fmt(series[2]),
                    c4: _fmt(series[3]),
                    c5: _fmt(diff),
                    c6: fmt_pct_val(diff_pct)
                }

        # 개별 항목 추가 (depth=1)
        for item in g3_items:
            rows.append(fmt_row(item, series_dict[item], depth=1))
            
        # 퍼센트 기호 추가 (depth=1)
        if pct_target:
            rows.append(fmt_row('%', pct_series, is_pct_row=True, depth=1))
            
        # 법인 합계 추가 (depth=0)
        rows.append(fmt_row(corp, total, depth=0)) 
        
        return rows

    all_rows.extend(calc_metrics('중국'))
    all_rows.extend(calc_metrics('태국'))
    
    return pd.DataFrame(all_rows)

def _세부판매현황_to_html_table(df):
    depths = df['_depth'].tolist() if '_depth' in df.columns else [1] * len(df)
    render_df = df.drop(columns=['_depth'], errors='ignore')

    rows_html = ''
    for (_, row), depth in zip(render_df.iterrows(), depths):
        is_total = depth == 0
        
        # 합계 행은 배경색과 굵은 글씨 적용
        bg = 'background:#f8f9fa;' if is_total else ''
        fw = 'font-weight:700;' if is_total else ''
        
        # 항목 행(depth=1)에 들여쓰기 적용
        indent = '&nbsp;&nbsp;&nbsp;&nbsp;' if depth == 1 else ''
        align_first = 'left' if depth == 1 else 'center'
        
        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if i == 0:
                cells += f'<td style="padding:6px 12px;text-align:{align_first};border-bottom:1px solid #e2e8f0;{bg}{fw}">{indent}{s}</td>'
            else:
                color = f';color:{_C_RED}' if s.startswith('-') else ''
                cells += f'<td style="padding:6px 12px;text-align:right;border-bottom:1px solid #e2e8f0;{bg}{fw}{color}">{s}</td>'
        
        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'
    
    headers = ''.join(f'<th style="{_TH};text-align:center">{c}</th>' for c in render_df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)

def _build_해외손익차이_table(year, month, corp):
    # 손익차이 DB 로드 (Sheets 상수는 환경에 맞게 수정 필요)
    df = load_sheet(Sheets.해외손익차이_DB)
    
    # 데이터가 없을 경우 기본 구조 반환
    if df.empty or '연도' not in df.columns:
        return pd.DataFrame(columns=['구분', '_depth', '영업', '제조', '구매', '기타', '합계'])
        
    df.columns = df.columns.str.strip()
    df['값'] = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    # 해당 연월 및 사업장 필터링
    df = df[(df['연도'] == year) & (df['월'] == month) & (df['사업장'] == corp)]
    
    # 구분2의 NaN 또는 빈 값을 안전하게 빈 문자열로 정제
    df['구분2'] = df['구분2'].fillna('').astype(str).str.strip()
    df['구분1'] = df['구분1'].astype(str).str.strip()
    df['구분3'] = df['구분3'].astype(str).str.strip()
    
    g3_cols = ['영업', '제조', '구매', '기타']
    
    def get_val(g1, g2, g3):
        mask = (df['구분1'] == g1) & (df['구분2'] == g2) & (df['구분3'] == g3)
        return df[mask]['값'].sum()

    # 각 항목별 데이터 추출[cite: 1]
    sales_vals = [get_val('매출이익', '판매', g3) for g3 in g3_cols]
    cost_vals = [get_val('매출이익', '원가', g3) for g3 in g3_cols]
    gross_profit_vals = [s + c for s, c in zip(sales_vals, cost_vals)] # 판매와 원가를 더해 매출이익 계산
    
    sgna_vals = [get_val('판매비와관리비', '', g3) for g3 in g3_cols]
    op_diff_vals = [get_val('영업이익차이', '', g3) for g3 in g3_cols]

    def format_row(label, depth, vals):
        total = sum(vals)
        return {
            '구분': label,
            '_depth': depth,
            '영업': _fmt(vals[0]),
            '제조': _fmt(vals[1]),
            '구매': _fmt(vals[2]),
            '기타': _fmt(vals[3]),
            '합계': _fmt(total)
        }

    rows = []
    
    # 계층구조를 반영하여 행 추가 (_depth 부여)
    rows.append(format_row('매출이익', 0, gross_profit_vals))
    rows.append(format_row('판매', 1, sales_vals))
    rows.append(format_row('원가', 1, cost_vals))
    rows.append(format_row('판매비와관리비', 0, sgna_vals))
    rows.append(format_row('영업이익차이', 0, op_diff_vals))
    
    return pd.DataFrame(rows)

def _해외손익차이_to_html_table(df):
    if df.empty:
        return ""
        
    depths = df['_depth'].tolist() if '_depth' in df.columns else [0] * len(df)
    render_df = df.drop(columns=['_depth'], errors='ignore')
    
    rows_html = ''
    for (_, row), depth in zip(render_df.iterrows(), depths):
        label = str(row.iloc[0])
        
        # 주요 합계 항목(매출이익, 영업이익차이)은 배경색 및 굵게 처리
        is_highlight = label in ['매출이익', '영업이익차이']
        bg = 'background:#f8f9fa;' if is_highlight else ''
        fw = 'font-weight:700;' if is_highlight else ''
        
        # depth에 따른 들여쓰기 설정 (하위 항목인 판매, 원가 등에 적용)
        indent = '&nbsp;&nbsp;&nbsp;&nbsp;' if depth == 1 else ''
        
        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if i == 0: # 구분 컬럼
                # 상/하위 항목 관계없이 모두 왼쪽 정렬로 통일하고 들여쓰기 적용
                cells += f'<td style="padding:6px 12px;text-align:left;border-bottom:1px solid #e2e8f0;{bg}{fw}">{indent}{s}</td>'
            else: # 값 컬럼
                # 음수인 경우 빨간색 텍스트 렌더링 적용
                color = f';color:{_C_RED}' if s.startswith('-') else ''
                cells += f'<td style="padding:6px 12px;text-align:right;border-bottom:1px solid #e2e8f0;{bg}{fw}{color}">{s}</td>'
        
        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'
    
    headers = ''.join(f'<th style="{_TH};text-align:center">{c}</th>' for c in render_df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)

_중국재고_ITEM_ORDER = ['제품', '재공', '원재료']


# 기존 _중국재고_ITEM_ORDER 대신 공통으로 사용할 순서 지정
_해외재고_ITEM_ORDER = ['제품', '재공', '원재료']

# 스타일 상수 (views.common에 없을 경우를 대비한 기본 스타일 선언)
ROW_SEC = "padding:6px 12px;background:#f8f9fa;font-weight:700;text-align:left;border-bottom:1px solid #e2e8f0;color:#1e293b;"
ROW_ITEM = "padding:6px 12px;text-align:left;border-bottom:1px solid #e2e8f0;"
ROW_HDR_LBL = "padding:6px 12px;background:#e2e8f0;font-weight:700;text-align:left;border-bottom:1px solid #cbd5e1;"
ROW_HDR_NUM = "padding:6px 12px;background:#e2e8f0;font-weight:700;text-align:right;border-bottom:1px solid #cbd5e1;"
ROW_HDR_RED = ROW_HDR_NUM + "color:#ef4444;"
_I1 = "&nbsp;&nbsp;&nbsp;&nbsp;"

def _build_해외재고자산_table(year, month, corp):
    df = load_sheet(Sheets.해외재고자산_DB) 
    
    if df.empty or '연도' not in df.columns:
        return [], {'past_years': [], 'recent_curr': []}
        
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['_v'] = df['값'].apply(_parse)
    
    # 1. 사업장 필터링
    df = df[df['사업장'] == corp]

    df['구분1'] = df['구분1'].astype(str).str.strip()
    df['구분2'] = df['구분2'].astype(str).str.strip()

    # 2. 구분1, 구분2를 기준으로 딕셔너리 매핑
    vm = df.set_index(['구분1', '구분2', '연도', '월'])['_v'].to_dict()

    연도_in_db = sorted(df['연도'].unique().tolist())
    
    # 최근 3개월 계산 헬퍼 함수 (_prev 활용)
    def get_recent(y, m, n=3):
        res = []
        for i in range(n-1, -1, -1):
            ry, rm = _prev(y, m, i)
            res.append((ry, rm))
        return res
        
    recent_curr = get_recent(year, month, 3)
    prev_year_end = max((yr for yr in 연도_in_db if yr < year), default=None)
    past_years = ([prev_year_end] 
                  if prev_year_end is not None and (prev_year_end, 12) not in recent_curr 
                  else [])
    prev_yr, prev_mo = _prev(year, month, 1)

    items_in_db = list(dict.fromkeys(df['구분1'].tolist()))
    items = [it for it in _해외재고_ITEM_ORDER if it in set(items_in_db)]
    items += [it for it in items_in_db if it not in set(_해외재고_ITEM_ORDER)]

    all_keys = df[['구분1', '구분2']].drop_duplicates().apply(tuple, axis=1).tolist()

    def raw(g1, g2, yr, mo):
        return vm.get((g1, g2, yr, mo), 0.0)

    def pct_chg(curr, prev):
        return (curr - prev) / abs(prev) * 100 if prev else 0.0

    def make_vals(g1, g2):
        v  = [raw(g1, g2, yr, 12) for yr in past_years]
        v += [raw(g1, g2, yr_c, mo_c) for yr_c, mo_c in recent_curr]
        c = raw(g1, g2, year, month)
        p = raw(g1, g2, prev_yr, prev_mo)
        v += [c - p, pct_chg(c, p)]
        return v

    rows = []
    for g1 in items:
        rows.append(('parent', g1))
        # 해당 구분1에 속한 구분2 항목들 나열
        for d in list(dict.fromkeys(df[df['구분1'] == g1]['구분2'].tolist())):
            rows.append(('child', d, make_vals(g1, d), 0)) # 기본 소수점 0자리 처리

    def _sum_vals():
        def s(yr, mo): return sum(raw(g1, d, yr, mo) for g1, d in all_keys)
        v  = [s(yr, 12) for yr in past_years]
        v += [s(yr_c, mo_c) for yr_c, mo_c in recent_curr]
        c, p = s(year, month), s(prev_yr, prev_mo)
        v += [c - p, pct_chg(c, p)]
        return v

    rows.append(('total_hdr', '재고자산 계'))
    rows.append(('total_child', '합계', _sum_vals(), 0))

    col_spec = {'past_years': past_years, 'recent_curr': recent_curr}
    return rows, col_spec

def _해외재고자산_to_html(rows, col_spec):
    if not rows:
        return ""
        
    past_years = col_spec['past_years']
    recent_curr = col_spec['recent_curr']
    n_cols = 1 + len(past_years) + len(recent_curr) + 2

    th = f'<th style="{_TH};text-align:center;">구분</th>'
    for yr in past_years:
        th += f'<th style="{_TH}">{str(yr)[2:]}년말</th>'
        
    last_yr = None
    for yr_c, mo_c in recent_curr:
        lbl = f"'{str(yr_c)[2:]}.{mo_c}월말" if yr_c != last_yr else f"{mo_c}월말"
        th += f'<th style="{_TH}">{lbl}</th>'
        last_yr = yr_c
        
    th += (f'<th style="{_TH}">전월대비<br>증감</th>'
           f'<th style="{_TH}">전월대비<br>증감률</th>')
    thead = f'<tr>{th}</tr>'

    def val_cells(vals, decimal=0, num_s=_TD_NUM, red_s=_TD_RED):
        cells = ''
        n = len(vals)
        for i, v in enumerate(vals):
            s = red_s if v < 0 else num_s
            if i == n - 1: # 증감률 열 처리
                txt = f'-{abs(round(v, 1))}%' if v < 0 else f'{round(v, 1)}%'
            else:
                txt = _fmt(v, decimal=decimal)
                s = num_s if i < n - 2 else s
            cells += f'<td style="{s}">{txt}</td>'
        return cells

    body = ''
    for row in rows:
        kind = row[0]
        if kind == 'parent':
            cells = f'<td style="{ROW_SEC}" colspan="{n_cols}">{row[1]}</td>'
        elif kind == 'child':
            _, label, vals, dec = row
            cells = f'<td style="{ROW_ITEM}">{_I1}{label}</td>' + val_cells(vals, dec)
        elif kind == 'total_hdr':
            cells = f'<td style="{ROW_HDR_LBL}" colspan="{n_cols}">{row[1]}</td>'
        else:  # 'total_child'
            _, label, vals, dec = row
            cells = (f'<td style="{ROW_HDR_LBL}">{_I1}{label}</td>'
                     + val_cells(vals, dec, ROW_HDR_NUM, ROW_HDR_RED))
        body += f'<tr>{cells}</tr>'

    return _html_table(thead, body)

_해외부적합장기재고_ITEM_ORDER = ['부적합재고', '장기재고']

def _build_해외부적합장기재고_flow_table(year, month, corp):
    # 전월, 전전월, 전년말 연월 계산[cite: 2]
    prev_yr, prev_mo = _prev(year, month, 1)
    prev2_yr, prev2_mo = _prev(year, month, 2)
    py_yr, py_mo = year - 1, 12
    
    # 동적 컬럼명 생성 (숫자로 표시)[cite: 2]
    c_py = f"'{str(py_yr)[2:]}년말"
    c_p2 = f"'{str(prev2_yr)[2:]}.{prev2_mo}월말"
    c_p1 = f"'{str(prev_yr)[2:]}.{prev_mo}월말"
    c_in = "당월 발생"
    c_out = "당월 소진"
    c_c = f"'{str(year)[2:]}.{month}월말"
    c_diff = "전월비 증감률"  # 컬럼명 변경

    columns = ['구분', '_depth', c_py, c_p2, c_p1, c_in, c_out, c_c, c_diff]

    df = load_sheet(Sheets.해외부적합장기재고_DB) 
    
    if df.empty or '연도' not in df.columns:
        return pd.DataFrame(columns=columns)
        
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['_v'] = df['값'].apply(_parse)
    
    # 해당 사업장 필터링[cite: 2]
    df = df[df['사업장'] == corp]

    for c in ['구분1', '구분2', '구분3']:
        df[c] = df[c].astype(str).str.strip()

    # 값 롤업 매핑 생성 (품목별, 발생/소진/실적별 합산)[cite: 2]
    vm = df.groupby(['구분1', '구분2', '구분3', '연도', '월'])['_v'].sum().to_dict()

    def get_v(g1, g2, g3, y, m):
        return vm.get((g1, g2, g3, y, m), 0.0)

    # 증감률 계산 헬퍼 함수
    def calc_pct_str(curr, prev):
        if prev == 0:
            return "0.0%"
        val = (curr - prev) / abs(prev) * 100
        return f"{val:.1f}%"

    items_in_db = list(dict.fromkeys(df['구분1'].tolist()))
    g1_list = [it for it in _해외부적합장기재고_ITEM_ORDER if it in items_in_db]
    g1_list += [it for it in items_in_db if it not in _해외부적합장기재고_ITEM_ORDER]

    rows = []
    grand_totals = {c_py: 0, c_p2: 0, c_p1: 0, c_in: 0, c_out: 0, c_c: 0}

    for g1 in g1_list:
        # 해당 구분1에 속한 품목(구분2) 리스트 추출[cite: 2]
        g2_list = list(dict.fromkeys(df[df['구분1'] == g1]['구분2'].tolist()))
        
        g1_totals = {c_py: 0, c_p2: 0, c_p1: 0, c_in: 0, c_out: 0, c_c: 0}
        g2_rows = []
        
        # 세부 품목별 데이터 계산[cite: 2]
        for g2 in g2_list:
            v_py  = get_v(g1, g2, '실적', py_yr, py_mo)
            v_p2  = get_v(g1, g2, '실적', prev2_yr, prev2_mo)
            v_p1  = get_v(g1, g2, '실적', prev_yr, prev_mo)
            v_in  = get_v(g1, g2, '발생', year, month)
            v_out = get_v(g1, g2, '소진', year, month)
            v_c   = get_v(g1, g2, '실적', year, month)
            
            g1_totals[c_py]  += v_py
            g1_totals[c_p2]  += v_p2
            g1_totals[c_p1]  += v_p1
            g1_totals[c_in]  += v_in
            g1_totals[c_out] += v_out
            g1_totals[c_c]   += v_c
            
            g2_rows.append({
                '구분': g2,
                '_depth': 1,
                c_py: _fmt(v_py),
                c_p2: _fmt(v_p2),
                c_p1: _fmt(v_p1),
                c_in: _fmt(v_in),
                c_out: _fmt(v_out),
                c_c: _fmt(v_c),
                c_diff: calc_pct_str(v_c, v_p1) # 증감률 포맷팅 적용
            })
            
        # 그룹(구분1) 합계 행 추가 (부적합재고 합계, 장기재고 합계)[cite: 2]
        rows.append({
            '구분': f'{g1} 합계',
            '_depth': 0,
            c_py: _fmt(g1_totals[c_py]),
            c_p2: _fmt(g1_totals[c_p2]),
            c_p1: _fmt(g1_totals[c_p1]),
            c_in: _fmt(g1_totals[c_in]),
            c_out: _fmt(g1_totals[c_out]),
            c_c: _fmt(g1_totals[c_c]),
            c_diff: calc_pct_str(g1_totals[c_c], g1_totals[c_p1]) # 증감률 포맷팅 적용
        })
        
        # 세부 품목 행을 그룹 합계 아래에 추가[cite: 2]
        rows.extend(g2_rows)
        
        for k in grand_totals:
            grand_totals[k] += g1_totals[k]

    # 최종 총계 행 추가[cite: 2]
    if rows:
        rows.append({
            '구분': '총계',
            '_depth': 0,
            c_py: _fmt(grand_totals[c_py]),
            c_p2: _fmt(grand_totals[c_p2]),
            c_p1: _fmt(grand_totals[c_p1]),
            c_in: _fmt(grand_totals[c_in]),
            c_out: _fmt(grand_totals[c_out]),
            c_c: _fmt(grand_totals[c_c]),
            c_diff: calc_pct_str(grand_totals[c_c], grand_totals[c_p1]) # 증감률 포맷팅 적용
        })

    # 최종 결과 데이터프레임 순서를 명확하게 지정하여 반환[cite: 2]
    return pd.DataFrame(rows, columns=columns)

def _해외부적합장기재고_flow_to_html_table(df):
    if df.empty:
        return ""
        
    depths = df['_depth'].tolist() if '_depth' in df.columns else [0] * len(df)
    render_df = df.drop(columns=['_depth'], errors='ignore')
    
    rows_html = ''
    for (_, row), depth in zip(render_df.iterrows(), depths):
        label = str(row.iloc[0])
        
        is_total = (depth == 0)
        bg = 'background:#f8f9fa;' if is_total else ''
        fw = 'font-weight:700;' if is_total else ''
        indent = '&nbsp;&nbsp;&nbsp;&nbsp;' if depth == 1 else ''
        
        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if i == 0:
                cells += f'<td style="padding:6px 12px;text-align:left;border-bottom:1px solid #e2e8f0;{bg}{fw}">{indent}{s}</td>'
            else:
                color = f';color:{_C_RED}' if s.startswith('-') else ''
                cells += f'<td style="padding:6px 12px;text-align:right;border-bottom:1px solid #e2e8f0;{bg}{fw}{color}">{s}</td>'
        
        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'
    
    headers = ''.join(f'<th style="{_TH};text-align:center">{c}</th>' for c in render_df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)

_해외연령별_ITEM_ORDER = ['제품', '재공', '원재료']
_해외연령별_AGE_ORDER = ['3개월 이하', '3개월 초과', '6개월 초과', '1년 초과']
_해외연령별_UNIT_ORDER = ['중량', '금액']

def _build_해외연령별재고_table(year, month, corp):
    # 전월, 전전월, 전년말 연월 계산[cite: 4]
    prev_yr, prev_mo = _prev(year, month, 1)
    prev2_yr, prev2_mo = _prev(year, month, 2)
    py_yr, py_mo = year - 1, 12
    
    # 동적 컬럼명 생성 (모든 시간 흐름 컬럼 유지)[cite: 4]
    c_py = f"'{str(py_yr)[2:]}년말"
    c_p2 = f"'{str(prev2_yr)[2:]}년 {prev2_mo}월"
    c_p1 = f"'{str(prev_yr)[2:]}년 {prev_mo}월"
    c_c = f"'{str(year)[2:]}년 {month}월"
    c_diff = "전월비 증감률"

    columns = ['구분', '_depth', c_py, c_p2, c_p1, c_c, c_diff]

    df = load_sheet(Sheets.해외연령별재고_DB)
    if df.empty or '연도' not in df.columns:
        return pd.DataFrame(columns=columns)
        
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['_v'] = df['값'].apply(_parse)
    
    df = df[df['사업장'] == corp]
    for c in ['구분1', '구분2', '구분3']:
        df[c] = df[c].astype(str).str.strip()
        
    vm = df.groupby(['구분1', '구분2', '구분3', '연도', '월'])['_v'].sum().to_dict()

    def get_v(g1, g2, g3, y, m):
        return vm.get((g1, g2, g3, y, m), 0.0)

    def calc_pct_str(curr, prev):
        if prev == 0:
            return "0.0%"
        val = (curr - prev) / abs(prev) * 100
        return f"{val:.1f}%"

    items_in_db = list(dict.fromkeys(df['구분1'].tolist()))
    g1_list = [it for it in _해외연령별_ITEM_ORDER if it in items_in_db]
    g1_list += [it for it in items_in_db if it not in _해외연령별_ITEM_ORDER]

    rows = []
    grand_totals = {
        '중량': {c_py: 0, c_p2: 0, c_p1: 0, c_c: 0},
        '금액': {c_py: 0, c_p2: 0, c_p1: 0, c_c: 0}
    }

    for g1 in g1_list:
        # 1. 대분류 (원재료, 제품 등) - Depth 0, 값은 표시하지 않고 헤더 역할[cite: 4]
        rows.append({
            '구분': g1,
            '_depth': 0,
            c_py: '', c_p2: '', c_p1: '', c_c: '', c_diff: ''
        })
        
        units_in_db = set(df[df['구분1'] == g1]['구분3'].tolist())
        g3_list = [u for u in _해외연령별_UNIT_ORDER if u in units_in_db]
        g3_list += [u for u in units_in_db if u not in _해외연령별_UNIT_ORDER]

        for g3 in g3_list:
            g3_totals = {c_py: 0, c_p2: 0, c_p1: 0, c_c: 0}
            
            ages_in_db = set(df[(df['구분1'] == g1) & (df['구분3'] == g3)]['구분2'].tolist())
            g2_list = [a for a in _해외연령별_AGE_ORDER if a in ages_in_db]
            g2_list += [a for a in ages_in_db if a not in _해외연령별_AGE_ORDER]
            
            g2_rows = []
            # 3. 하위 연령 항목 (3개월 이하 등) - Depth 2[cite: 4]
            for g2 in g2_list:
                v_py = get_v(g1, g2, g3, py_yr, py_mo)
                v_p2 = get_v(g1, g2, g3, prev2_yr, prev2_mo)
                v_p1 = get_v(g1, g2, g3, prev_yr, prev_mo)
                v_c = get_v(g1, g2, g3, year, month)
                
                g3_totals[c_py] += v_py
                g3_totals[c_p2] += v_p2
                g3_totals[c_p1] += v_p1
                g3_totals[c_c] += v_c
                
                dec = 1 if '중량' in g3 else 0
                g2_rows.append({
                    '구분': g2,
                    '_depth': 2,
                    c_py: _fmt(v_py, decimal=dec),
                    c_p2: _fmt(v_p2, decimal=dec),
                    c_p1: _fmt(v_p1, decimal=dec),
                    c_c: _fmt(v_c, decimal=dec),
                    c_diff: calc_pct_str(v_c, v_p1)
                })
                
            dec = 1 if '중량' in g3 else 0
            
            # 2. 단위별 소계 (중량, 금액) - Depth 1[cite: 4]
            rows.append({
                '구분': g3,
                '_depth': 1,
                c_py: _fmt(g3_totals[c_py], decimal=dec),
                c_p2: _fmt(g3_totals[c_p2], decimal=dec),
                c_p1: _fmt(g3_totals[c_p1], decimal=dec),
                c_c: _fmt(g3_totals[c_c], decimal=dec),
                c_diff: calc_pct_str(g3_totals[c_c], g3_totals[c_p1])
            })
            
            # 세부 연령 항목들을 단위 소계 아래에 일괄 추가[cite: 4]
            rows.extend(g2_rows)
            
            if g3 in grand_totals:
                for k in grand_totals[g3]:
                    grand_totals[g3][k] += g3_totals[k]

    # 최종 합계 (중량/금액 구분)[cite: 4]
    if rows:
        rows.append({
            '구분': '총계',
            '_depth': 0,
            c_py: '', c_p2: '', c_p1: '', c_c: '', c_diff: ''
        })
        for g3 in _해외연령별_UNIT_ORDER:
            if g3 in grand_totals:
                dec = 1 if '중량' in g3 else 0
                rows.append({
                    '구분': f'합계 ({g3})',
                    '_depth': 1,
                    c_py: _fmt(grand_totals[g3][c_py], decimal=dec),
                    c_p2: _fmt(grand_totals[g3][c_p2], decimal=dec),
                    c_p1: _fmt(grand_totals[g3][c_p1], decimal=dec),
                    c_c: _fmt(grand_totals[g3][c_c], decimal=dec),
                    c_diff: calc_pct_str(grand_totals[g3][c_c], grand_totals[g3][c_p1])
                })

    return pd.DataFrame(rows, columns=columns)

def _해외연령별재고_to_html_table(df):
    if df.empty:
        return ""
        
    depths = df['_depth'].tolist() if '_depth' in df.columns else [0] * len(df)
    render_df = df.drop(columns=['_depth'], errors='ignore')
    
    rows_html = ''
    for (_, row), depth in zip(render_df.iterrows(), depths):
        label = str(row.iloc[0])
        
        # Depth 0: 상위 항목 (원재료, 총계 등) - 배경색 + 굵게[cite: 4]
        # Depth 1: 중위 항목 (중량, 금액) - 중간 굵기, 들여쓰기 1단계[cite: 4]
        # Depth 2: 하위 항목 (각 기간) - 기본 폰트, 들여쓰기 2단계[cite: 4]
        bg = 'background:#f8f9fa;' if depth == 0 else ''
        fw = 'font-weight:700;' if depth == 0 else ('font-weight:600;' if depth == 1 else '')
        
        if depth == 1:
            indent = '&nbsp;&nbsp;&nbsp;&nbsp;'
        elif depth == 2:
            indent = '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        else:
            indent = ''
            
        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if i == 0:
                cells += f'<td style="padding:6px 12px;text-align:left;border-bottom:1px solid #e2e8f0;{bg}{fw}">{indent}{s}</td>'
            else:
                color = f';color:{_C_RED}' if s.startswith('-') else ''
                cells += f'<td style="padding:6px 12px;text-align:right;border-bottom:1px solid #e2e8f0;{bg}{fw}{color}">{s}</td>'
        
        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'
    
    headers = ''.join(f'<th style="{_TH};text-align:center">{c}</th>' for c in render_df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)

_해외채권_ITEM_ORDER = ['정상채권', '부실채권']
_해외채권_AGE_ORDER = ['3개월 이하', '3개월 초과', '6개월 초과']

def _build_해외채권현황_table(year, month, corp):
    # 과거 연도 및 전월 계산[cite: 3]
    y4, y3, y2, y1 = year - 4, year - 3, year - 2, year - 1
    prev_yr, prev_mo = _prev(year, month, 1)
    
    # 동적 컬럼명 생성 (과거 4개년말, 전월, 당월)[cite: 3]
    c_y4 = f"'{str(y4)[2:]}년말"
    c_y3 = f"'{str(y3)[2:]}년말"
    c_y2 = f"'{str(y2)[2:]}년말"
    c_y1 = f"'{str(y1)[2:]}년말"
    c_p1 = f"'{str(prev_yr)[2:]}년 {prev_mo}월"
    c_c  = f"'{str(year)[2:]}년 {month}월"

    columns = ['구분', '_depth', c_y4, c_y3, c_y2, c_y1, c_p1, c_c]

    df = load_sheet(Sheets.해외채권_DB)
    
    if df.empty or '연도' not in df.columns:
        return pd.DataFrame(columns=columns)
        
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['_v'] = df['값'].apply(_parse)
    
    # 해당 사업장 필터링[cite: 3]
    df = df[df['사업장'] == corp]
    
    # 구분1, 구분2 컬럼 정제[cite: 3]
    df['구분1'] = df['구분1'].fillna('').astype(str).str.strip()
    df['구분2'] = df['구분2'].fillna('').astype(str).str.strip()
    
    # (구분1, 구분2, 연도, 월) 기준 해시맵 생성[cite: 3]
    vm = df.groupby(['구분1', '구분2', '연도', '월'])['_v'].sum().to_dict()

    # DB 값 조회 헬퍼 함수[cite: 3]
    def get_raw(g1, g2, y, m):
        return vm.get((g1, g2, y, m), 0.0)

    # 시점별 계산 로직 정의[cite: 3]
    def val_jongsang_total(y, m):
        # 구분1이 '정상채권'이고 구분2가 비어있는 값
        return get_raw('정상채권', '', y, m)

    def val_age_3m_under(y, m):
        return get_raw('정상채권', '3개월 이하', y, m)

    def val_age_3m_over(y, m):
        return get_raw('정상채권', '3개월 초과', y, m)

    def val_age_6m_over(y, m):
        return get_raw('정상채권', '6개월 초과', y, m)

    def val_bad_debt(y, m):
        return get_raw('정상채권', '회수불능', y, m)

    def val_gijun_chogwa(y, m):
        # 기준초과채권 = 3개월이하 + 3개월초과 + 6개월초과 + 회수불능 합계[cite: 3]
        return (val_age_3m_under(y, m) + 
                val_age_3m_over(y, m) + 
                val_age_6m_over(y, m) + 
                val_bad_debt(y, m))

    def val_maechul_chaekwon(y, m):
        # 매출채권 계 = 정상채권 + 기준초과채권[cite: 3]
        return val_jongsang_total(y, m) + val_gijun_chogwa(y, m)

    def val_chogwa_rate(y, m):
        # 초과채권 비율(%) = (기준초과채권 / 매출채권 계) * 100
        v = get_raw('초과채권 비율(%)', '', y, m)
        if v == 0:
            mc = val_maechul_chaekwon(y, m)
            return (val_gijun_chogwa(y, m) / mc * 100) if mc != 0 else 0.0
        return v

    def val_chogwa_loss(y, m):
        # 💡 초과채권 이자손실 계산식: (기준초과채권 * 연 이자율 5%) / 12개월
        # DB에 등록된 값이 없거나 0인 경우, 연 5% 기준 월간 기회비용 손실액을 자동 계산함
        v = get_raw('초과채권 이자손실', '', y, m)
        if v == 0:
            chogwa_val = val_gijun_chogwa(y, m)
            return (chogwa_val * 0.05) / 12
        return v

    def val_maechul_giil(y, m):
        return get_raw('매출채권기일', '', y, m)

    def val_jongsang_giil(y, m):
        return get_raw('정상채권기일', '', y, m)

    def val_giil_diff(y, m):
        # 차이 = 매출채권기일 - 정상채권기일[cite: 3]
        return val_maechul_giil(y, m) - val_jongsang_giil(y, m)

    # 행 구성을 위한 설정 리스트: (표시명, depth, 수치계산함수)[cite: 3]
    row_configs = [
        ('매출액(세금포함)', 0, lambda y, m: get_raw('매출액(세금포함)', '', y, m)),
        ('정상채권', 0, val_jongsang_total),
        ('3개월 이하', 1, val_age_3m_under),
        ('3개월 초과', 1, val_age_3m_over),
        ('6개월 초과', 1, val_age_6m_over),
        ('회수불능', 1, val_bad_debt),
        ('기준초과채권', 0, val_gijun_chogwa),
        ('매출채권 계', 0, val_maechul_chaekwon),
        ('초과채권 비율(%)', 0, val_chogwa_rate),
        ('초과채권 이자손실', 0, val_chogwa_loss),
        ('매출채권기일', 0, val_maechul_giil),
        ('정상채권기일', 0, val_jongsang_giil),
        ('차이', 0, val_giil_diff)
    ]

    # 각 항목별 시점별 6개 수치 리스트 세팅[cite: 3]
    periods = [(y4, 12), (y3, 12), (y2, 12), (y1, 12), (prev_yr, prev_mo), (year, month)]

    rows = []
    for label, depth, calc_fn in row_configs:
        vals = [calc_fn(y, m) for y, m in periods]
        dec = 1 if '(%)' in label else 0
        
        rows.append({
            '구분': label,
            '_depth': depth,
            c_y4: _fmt(vals[0], decimal=dec),
            c_y3: _fmt(vals[1], decimal=dec),
            c_y2: _fmt(vals[2], decimal=dec),
            c_y1: _fmt(vals[3], decimal=dec),
            c_p1: _fmt(vals[4], decimal=dec),
            c_c:  _fmt(vals[5], decimal=dec)
        })

    return pd.DataFrame(rows, columns=columns)


def _해외채권현황_to_html_table(df):
    if df.empty:
        return ""
        
    depths = df['_depth'].tolist() if '_depth' in df.columns else [0] * len(df)
    render_df = df.drop(columns=['_depth'], errors='ignore')
    
    rows_html = ''
    for (_, row), depth in zip(render_df.iterrows(), depths):
        label = str(row.iloc[0])
        
        # 이미지 형태처럼 깔끔한 Flat 스타일 유지
        # 하위 연령 항목(3개월 이하 등)에만 1단계 들여쓰기 적용
        indent = '&nbsp;&nbsp;&nbsp;&nbsp;' if depth == 1 else ''
            
        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if i == 0:
                cells += f'<td style="padding:6px 12px;text-align:left;border-bottom:1px solid #e2e8f0;">{indent}{s}</td>'
            else:
                color = f';color:{_C_RED}' if s.startswith('-') else ''
                cells += f'<td style="padding:6px 12px;text-align:right;border-bottom:1px solid #e2e8f0;{color}">{s}</td>'
        
        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'
    
    headers = ''.join(f'<th style="{_TH};text-align:center">{c}</th>' for c in render_df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)

# ── 1) 인원현황 (중국, 태국) 테이블 생성 함수 ───────────────────────────────────────

def _build_해외인원현황_table(year, month):
    df = load_sheet(Sheets.해외인원_DB)
    # 기본 컬럼 정의
    prev_yr, prev_mo = _prev(year, month, 1)
    py_yr = year - 1
    
    c_py = f"'{str(py_yr)[2:]}년말"
    c_p1 = f"'{str(prev_yr)[2:]}년 {prev_mo}월"
    c_c  = f"'{str(year)[2:]}년 {month}월"
    
    columns = ['구분', '_depth', c_py, c_p1, c_c, '전월비', '%']
    
    if df.empty or '연도' not in df.columns:
        return pd.DataFrame(columns=columns)
        
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['_v'] = df['값'].apply(_parse)
    
    for c in ['구분1', '구분2', '구분3']:
        if c in df.columns:
            df[c] = df[c].fillna('').astype(str).str.strip()
            
    # (사업장, 구분2, 구분3, 연도, 월) -> 값
    vm = df.groupby(['사업장', '구분2', '구분3', '연도', '월'])['_v'].sum().to_dict()

    def get_v(corp, g2, g3, y, m):
        return vm.get((corp, g2, g3, y, m), 0.0)

    rows = []
    
    for corp in ['중국', '태국']:
        # 1. 수치 수집 헬퍼
        def get_series(g2, g3):
            v_py = get_v(corp, g2, g3, py_yr, 12)
            v_p1 = get_v(corp, g2, g3, prev_yr, prev_mo)
            v_c  = get_v(corp, g2, g3, year, month)
            return [v_py, v_p1, v_c]

        samu = get_series('자사', '사무직')
        gineung = get_series('자사', '기능직')
        
        # 자사 합계 = 사무직 + 기능직
        jasa = [s + g for s, g in zip(samu, gineung)]
        
        # 외주기능직 (구분2가 '외주기능직')
        oeju_py = get_v(corp, '외주기능직', '', py_yr, 12) + get_v(corp, '외주기능직', '외주기능직', py_yr, 12)
        oeju_p1 = get_v(corp, '외주기능직', '', prev_yr, prev_mo) + get_v(corp, '외주기능직', '외주기능직', prev_yr, prev_mo)
        oeju_c  = get_v(corp, '외주기능직', '', year, month) + get_v(corp, '외주기능직', '외주기능직', year, month)
        oeju = [oeju_py, oeju_p1, oeju_c]
        
        # 법인 합계 = 자사 + 외주기능직
        total = [j + o for j, o in zip(jasa, oeju)]

        def make_row_dict(label, depth, series):
            v_py, v_p1, v_c = series
            diff = v_c - v_p1
            pct = (diff / abs(v_p1) * 100) if v_p1 != 0 else 0.0
            return {
                '구분': label,
                '_depth': depth,
                c_py: _fmt(v_py, decimal=0),
                c_p1: _fmt(v_p1, decimal=0),
                c_c:  _fmt(v_c,  decimal=0),
                '전월비': _fmt(diff, decimal=0),
                '%': _fmt(pct, is_pct=True, decimal=1)
            }

        rows.append(make_row_dict('사무직', 1, samu))
        rows.append(make_row_dict('기능직', 1, gineung))
        rows.append(make_row_dict('자사', 0, jasa))
        rows.append(make_row_dict('외주기능직', 0, oeju))
        rows.append(make_row_dict(corp, 2, total))  # 법인 최종 합계 (중국, 태국)

    return pd.DataFrame(rows, columns=columns)


def _해외인원현황_to_html_table(df):
    if df.empty:
        return ""
        
    depths = df['_depth'].tolist() if '_depth' in df.columns else [0] * len(df)
    render_df = df.drop(columns=['_depth'], errors='ignore')
    
    rows_html = ''
    for (_, row), depth in zip(render_df.iterrows(), depths):
        label = str(row.iloc[0])
        
        # Depth 2: 법인 합계 행(중국, 태국) - 배경색 + Bold
        # Depth 0: 자사, 외주기능직
        # Depth 1: 하위 항목(사무직, 기능직) - 들여쓰기 적용
        is_corp_total = (depth == 2)
        bg = 'background:#f8f9fa;' if is_corp_total else ''
        fw = 'font-weight:700;' if is_corp_total else ('font-weight:600;' if depth == 0 else '')
        
        indent = '&nbsp;&nbsp;&nbsp;&nbsp;' if depth == 1 else ''
        align_first = 'left' if depth == 1 else ('center' if is_corp_total else 'left')
            
        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if i == 0:
                cells += f'<td style="padding:6px 12px;text-align:{align_first};border-bottom:1px solid #e2e8f0;{bg}{fw}">{indent}{s}</td>'
            else:
                color = f';color:{_C_RED}' if s.startswith('-') else ''
                cells += f'<td style="padding:6px 12px;text-align:right;border-bottom:1px solid #e2e8f0;{bg}{fw}{color}">{s}</td>'
        
        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'
    
    headers = ''.join(f'<th style="{_TH};text-align:center">{c}</th>' for c in render_df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)


# ── 2) 인당 월평균 생산량 테이블 생성 함수 ─────────────────────────────────────
def _build_인당월평균생산량_table(year, month):
    df = load_sheet(Sheets.해외인원_DB) 
    
    py_yr = year - 1
    c_py_avg = f"'{str(py_yr)[2:]}년 월평균"
    c_prev   = f"'{str(year)[2:]}년 {month-1}월" if month > 1 else f"'{str(year-1)[2:]}년 12월"
    c_curr   = f"'{str(year)[2:]}년 {month}월"
    c_cy_avg = f"'{str(year)[2:]}년 월평균"
    
    columns = ['구분', '_depth', c_py_avg, c_prev, c_curr, c_cy_avg]
    
    if df.empty or '연도' not in df.columns:
        return pd.DataFrame(columns=columns)
        
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['_v'] = df['값'].apply(_parse)
    
    for c in ['구분1', '구분2', '구분3']:
        if c in df.columns:
            df[c] = df[c].fillna('').astype(str).str.strip()

    # 인원현황 데이터 해시맵: (사업장, 구분2, 구분3, 연도, 월) -> 값
    df_emp = df[df['구분1'] == '인원현황'].copy()
    vm_emp = df_emp.groupby(['사업장', '구분2', '구분3', '연도', '월'])['_v'].sum().to_dict()

    # 생산량 데이터 해시맵: (사업장, 연도, 월) -> 값
    df_prod = df[df['구분1'].isin(['인당 월평균 생산량', '인당월평균생산량', '생산량']) & (df['구분2'] == '생산량')].copy()
    vm_prod = df_prod.groupby(['사업장', '연도', '월'])['_v'].sum().to_dict()

    # 1. 월별 직접인원 계산 헬퍼 함수: 직접인원 = 기능직 + 외주기능직
    def get_direct_emp(corp, y, m):
        # 기능직 (자사 - 기능직)
        gineung = vm_emp.get((corp, '자사', '기능직', y, m), 0.0)
        # 외주기능직 (외주기능직)
        oeju = vm_emp.get((corp, '외주기능직', '', y, m), 0.0) + vm_emp.get((corp, '외주기능직', '외주기능직', y, m), 0.0)
        return gineung + oeju

    # 2. 월별 생산량 조회 헬퍼 함수
    def get_production(corp, y, m):
        return vm_prod.get((corp, y, m), 0.0)

    # 3. 연간 월평균 계산 헬퍼 함수
    def get_yr_avg(fn, corp, y, max_m=12):
        vals = [fn(corp, y, m) for m in range(1, max_m + 1)]
        valid_vals = [v for v in vals if v != 0]
        return sum(valid_vals) / len(valid_vals) if valid_vals else 0.0

    rows = []
    prev_yr, prev_mo = _prev(year, month, 1)

    for corp in ['중국', '태국']:
        # [생산량] 전년 월평균, 전월, 당월, 금년 월평균
        prod_py = get_yr_avg(get_production, corp, py_yr, 12)
        prod_p1 = get_production(corp, prev_yr, prev_mo)
        prod_c  = get_production(corp, year, month)
        prod_cy = get_yr_avg(get_production, corp, year, month)
        
        # [직접인원] 기능직 + 외주기능직으로 자동 계산
        emp_py = get_yr_avg(get_direct_emp, corp, py_yr, 12)
        emp_p1 = get_direct_emp(corp, prev_yr, prev_mo)
        emp_c  = get_direct_emp(corp, year, month)
        emp_cy = get_yr_avg(get_direct_emp, corp, year, month)
        
        # [인당 생산량] = 생산량 / 직접인원
        per_py = prod_py / emp_py if emp_py else 0.0
        per_p1 = prod_p1 / emp_p1 if emp_p1 else 0.0
        per_c  = prod_c  / emp_c  if emp_c  else 0.0
        per_cy = prod_cy / emp_cy if emp_cy else 0.0

        rows.append({
            '구분': '생산량',
            '_depth': 0,
            c_py_avg: _fmt(prod_py, decimal=0),
            c_prev:   _fmt(prod_p1, decimal=0),
            c_curr:   _fmt(prod_c,  decimal=0),
            c_cy_avg: _fmt(prod_cy, decimal=0)
        })
        rows.append({
            '구분': '직접인원',
            '_depth': 0,
            c_py_avg: _fmt(emp_py, decimal=0),
            c_prev:   _fmt(emp_p1, decimal=0),
            c_curr:   _fmt(emp_c,  decimal=0),
            c_cy_avg: _fmt(emp_cy, decimal=0)
        })
        rows.append({
            '구분': f'{corp} (인당)',
            '_depth': 2,
            c_py_avg: _fmt(per_py, decimal=0),
            c_prev:   _fmt(per_p1, decimal=0),
            c_curr:   _fmt(per_c,  decimal=0),
            c_cy_avg: _fmt(per_cy, decimal=0)
        })

    return pd.DataFrame(rows, columns=columns)


def _인당월평균생산량_to_html_table(df):
    if df.empty:
        return ""
        
    depths = df['_depth'].tolist() if '_depth' in df.columns else [0] * len(df)
    render_df = df.drop(columns=['_depth'], errors='ignore')
    
    rows_html = ''
    for (_, row), depth in zip(render_df.iterrows(), depths):
        label = str(row.iloc[0])
        
        # 인당 결과 행(Depth 2)은 배경색 + Bold 강조
        is_total = (depth == 2)
        bg = 'background:#f8f9fa;' if is_total else ''
        fw = 'font-weight:700;' if is_total else ''
        
        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if i == 0:
                cells += f'<td style="padding:6px 12px;text-align:left;border-bottom:1px solid #e2e8f0;{bg}{fw}">{s}</td>'
            else:
                color = f';color:{_C_RED}' if s.startswith('-') else ''
                cells += f'<td style="padding:6px 12px;text-align:right;border-bottom:1px solid #e2e8f0;{bg}{fw}{color}">{s}</td>'
        
        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'
    
    headers = ''.join(f'<th style="{_TH};text-align:center">{c}</th>' for c in render_df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)

# ── render_page ───────────────────────────────────────────────────────────

def render_page(app, year_state, month_state):

    def _render_title():
        app.markdown(
            f'<h1 style="color:#404448">{int(year_state.value)}년 {int(month_state.value)}월 해외법인실적</h1>',
            unsafe_allow_html=True,
        )
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["손익요약", "현금흐름표", "재무상태표", "판매구성", "전월대비 손익차이", "재고자산 현황", "채권현황", "인원현황"])

    with tabs[0]:
        def _render_해외손익():
            year, month = int(year_state.value), int(month_state.value)
            get, _ = _load_손익()
            memo1 = _get_memo(Sheets.해외손익요약_중국_메모, year, month)
            app.markdown(_section("1) 손익 (중국)", _build_중국_table(get, year, month), memo1),
                         unsafe_allow_html=True)
            memo2 = _get_memo(Sheets.해외손익요약_태국_메모, year, month)
            app.markdown(_section("2) 손익 (태국)", _build_태국_table(get, year, month), memo2),
                         unsafe_allow_html=True)
            
        app.If(lambda: True, _render_해외손익)

    with tabs[1]:
        def _render_해외현금흐름():
            year, month = int(year_state.value), int(month_state.value)
            
            # 중국 현금흐름표 렌더링
            memo_cn = _get_memo(Sheets.해외현금흐름_중국_메모, year, month)
            app.markdown(_layout64("1) 현금흐름표 (중국)", _build_현금흐름표_중국_table(year, month), memo_cn, '[단위: 백만원]'),
                         unsafe_allow_html=True)
            
            # 태국 현금흐름표 렌더링
            memo_th = _get_memo(Sheets.해외현금흐름_태국_메모, year, month)
            app.markdown(_layout64("2) 현금흐름표 (태국)", _build_현금흐름표_태국_table(year, month), memo_th, '[단위: 백만원]'),
                         unsafe_allow_html=True)
            
        app.If(lambda: True, _render_해외현금흐름)

    with tabs[2]:
        def _render_해외재무상태표():
            year, month = int(year_state.value), int(month_state.value)
            
            # 1. 중국 재무상태표 렌더링
            memo_cn = _get_memo(Sheets.해외재무상태표_중국_메모, year, month)
            app.markdown(_layout64("1) 재무상태표 (중국)", _build_재무상태표_중국_table(year, month), memo_cn, '[단위: 백만원]'),
                         unsafe_allow_html=True)
            
            # 2. 태국 재무상태표 렌더링
            memo_th = _get_memo(Sheets.해외재무상태표_태국_메모, year, month)
            app.markdown(_layout64("2) 재무상태표 (태국)", _build_재무상태표_태국_table(year, month), memo_th, '[단위: 백만원]'),
                         unsafe_allow_html=True)
            
        app.If(lambda: True, _render_해외재무상태표)

    with tabs[3]:
        def _render_해외판매구성():
            year, month = int(year_state.value), int(month_state.value)
            
            # 1) 등급별 판매현황
            df1 = _build_해외판매구성_table(year, month)
            html_table1 = _등급별판매현황_to_html_table(df1)
            memo1 = _get_memo(Sheets.해외등급별판매_메모, year, month)
            app.markdown(_layout64("1) 등급별 판매현황", html_table1, memo1, '[단위: 톤]'), unsafe_allow_html=True)
            
            # 2) CHQ 열처리 제품 판매현황
            df_1 = _build_세부판매현황_base_table(year, month, Sheets.해외판매현황_DB, 'CHQ 열처리 제품 판매현황', ['비열처리', '열처리'], '열처리')
            html_1 = _세부판매현황_to_html_table(df_1)
            memo_1 = _get_memo(Sheets.해외판매현황_CHQ_메모, year, month) 
            app.markdown(_layout64("2) CHQ 열처리 제품 판매현황", html_1, memo_1, '[단위: 톤]'), unsafe_allow_html=True)
            
            # 3) 비가공품 판매현황
            df_2 = _build_세부판매현황_base_table(year, month, Sheets.해외판매현황_DB, '비가공품 판매현황', ['가공', '비가공'], '비가공')
            html_2 = _세부판매현황_to_html_table(df_2)
            memo_2 = _get_memo(Sheets.해외판매현황_비가공품_메모, year, month) 
            app.markdown(_layout64("3) 비가공품 판매현황", html_2, memo_2, '[단위: 톤]'), unsafe_allow_html=True)

            # 4) 제품/임가공 판매현황 
            df_3 = _build_세부판매현황_base_table(year, month, Sheets.해외판매현황_DB, '제품/임가공 판매현황', ['제품', '임가공'], '임가공')
            html_3 = _세부판매현황_to_html_table(df_3)
            memo_3 = _get_memo(Sheets.해외판매현황_제품임가공_메모, year, month) 
            app.markdown(_layout64("4) 제품/임가공 판매현황", html_3, memo_3, '[단위: 톤]'), unsafe_allow_html=True)

        app.If(lambda: True, _render_해외판매구성)

    with tabs[4]:
        def _render_전월대비손익차이():
            year, month = int(year_state.value), int(month_state.value)
            
            # 1) 전월대비 손익차이 (중국)
            df_cn = _build_해외손익차이_table(year, month, '중국')
            html_cn = _해외손익차이_to_html_table(df_cn)
            # 중국은 메모1 컬럼에서 가져옴
            memo_cn = _get_손익차이_memo(year, month, '중국') 
            app.markdown(_layout64("1) 전월대비 손익차이 (중국)", html_cn, memo_cn, '[단위: 백만원]'), unsafe_allow_html=True)
            
            # 2) 전월대비 손익차이 (태국)
            df_th = _build_해외손익차이_table(year, month, '태국')
            html_th = _해외손익차이_to_html_table(df_th)
            # 태국은 메모2 컬럼에서 가져옴
            memo_th = _get_손익차이_memo(year, month, '태국') 
            app.markdown(_layout64("2) 전월대비 손익차이 (태국)", html_th, memo_th, '[단위: 백만원]'), unsafe_allow_html=True)

        app.If(lambda: True, _render_전월대비손익차이)

    with tabs[5]:
        def _render_재고자산():
            year, month = int(year_state.value), int(month_state.value)
            
            # 1) 재고자산 현황 (중국)
            rows_cn, spec_cn = _build_해외재고자산_table(year, month, '중국')
            html_cn = _해외재고자산_to_html(rows_cn, spec_cn)
            memo_cn = _get_memo(Sheets.해외재고자산_중국_메모, year, month) 
            app.markdown(_layout64("1) 재고자산 (중국)", html_cn, memo_cn, '[단위: 톤, 백만원]'), unsafe_allow_html=True)

            # 2) 재고자산 현황 (태국)
            rows_th, spec_th = _build_해외재고자산_table(year, month, '태국')
            html_th = _해외재고자산_to_html(rows_th, spec_th)
            memo_th = _get_memo(Sheets.해외재고자산_태국_메모, year, month) 
            app.markdown(_layout64("2) 재고자산 (태국)", html_th, memo_th, '[단위: 톤, 백만원]'), unsafe_allow_html=True)

            # 3) 부적합 및 장기재고 증감 현황 (중국) - 새로 작성된 함수 적용
            df_cn_bad = _build_해외부적합장기재고_flow_table(year, month, '중국')
            html_cn_bad = _해외부적합장기재고_flow_to_html_table(df_cn_bad) 
            memo_cn2 = _get_memo(Sheets.해외부적합장기재고_중국_메모, year, month) 
            app.markdown(_layout64("3) 부적합 및 장기재고 현황 (중국)", html_cn_bad, memo_cn2, '[단위: 톤, 백만원]'), unsafe_allow_html=True)

            # 4) 부적합 및 장기재고 증감 현황 (태국) - 새로 작성된 함수 적용
            df_th_bad = _build_해외부적합장기재고_flow_table(year, month, '태국')
            html_th_bad = _해외부적합장기재고_flow_to_html_table(df_th_bad)
            memo_th2 = _get_memo(Sheets.해외부적합장기재고_태국_메모, year, month) 
            app.markdown(_layout64("4) 부적합 및 장기재고 현황 (태국)", html_th_bad, memo_th2, '[단위: 톤, 백만원]'), unsafe_allow_html=True)

            # 5) 연령별 재고 현황 (중국) - 수정된 부분 (단일 변수로 데이터프레임 받기)
            df_cn_age = _build_해외연령별재고_table(year, month, '중국')
            html_cn_age = _해외연령별재고_to_html_table(df_cn_age) 
            memo_cn3 = _get_memo(Sheets.해외연령별재고_중국_메모, year, month)
            app.markdown(_layout64("5) 연령별 재고 현황 (중국)", html_cn_age, memo_cn3, '[단위: 톤, 백만원]'), unsafe_allow_html=True)

            # 6) 연령별 재고 현황 (태국) - 수정된 부분 (단일 변수로 데이터프레임 받기)
            df_th_age = _build_해외연령별재고_table(year, month, '태국')
            html_th_age = _해외연령별재고_to_html_table(df_th_age)
            memo_th3 = _get_memo(Sheets.해외연령별재고_태국_메모, year, month) 
            app.markdown(_layout64("6) 연령별 재고 현황 (태국)", html_th_age, memo_th3, '[단위: 톤, 백만원]'), unsafe_allow_html=True)

        app.If(lambda: True, _render_재고자산)

    with tabs[6]:
        def _render_채권현황():
            year, month = int(year_state.value), int(month_state.value)
            
            # 1) 채권 현황 (중국)
            df_cn_ar = _build_해외채권현황_table(year, month, '중국')
            html_cn_ar = _해외채권현황_to_html_table(df_cn_ar) 
            # 필요 시 관련 메모 시트 매핑
            memo_cn_ar = _get_memo(Sheets.해외채권_중국_메모, year, month) 
            app.markdown(_layout64("1) 채권 현황 (중국)", html_cn_ar, memo_cn_ar, '[단위: 백만원]'), unsafe_allow_html=True)

            # 2) 채권 현황 (태국)
            df_th_ar = _build_해외채권현황_table(year, month, '태국')
            html_th_ar = _해외채권현황_to_html_table(df_th_ar)
            # 필요 시 관련 메모 시트 매핑
            memo_th_ar = _get_memo(Sheets.해외채권_태국_메모, year, month)
            app.markdown(_layout64("2) 채권 현황 (태국)", html_th_ar, memo_th_ar, '[단위: 백만원]'), unsafe_allow_html=True)

        app.If(lambda: True, _render_채권현황)

    with tabs[7]:
        def _render_인원현황():
            year, month = int(year_state.value), int(month_state.value)
            
            # 1) 인원현황 (중국, 태국)
            df_emp = _build_해외인원현황_table(year, month)
            html_emp = _해외인원현황_to_html_table(df_emp)
            memo_emp = _get_memo(Sheets.해외인원_메모, year, month)
            app.markdown(_layout64("1) 인원현황 (중국, 태국)", html_emp, memo_emp, '[단위: 명]'), unsafe_allow_html=True)

            # 2) 인당 월평균 생산량
            df_prod = _build_인당월평균생산량_table(year, month)
            html_prod = _인당월평균생산량_to_html_table(df_prod)
            memo_prod = _get_memo(Sheets.해외인원_생산량_메모, year, month)
            app.markdown(_layout64("2) 인당 월평균 생산량", html_prod, memo_prod, '[단위: 명, 톤]'), unsafe_allow_html=True)

        app.If(lambda: True, _render_인원현황)