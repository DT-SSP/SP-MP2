import datetime
import pandas as pd
import plotly.graph_objects as go
from data.loader import load_sheet
from data.config import Sheets
from views.common import (
    parse as _parse, fmt as _fmt,
    drop_empty as _drop_empty,
    prev_month as _prev_month,
    recent_months as _recent_months,
    build_col_hdrs as _build_col_hdrs,
    TH as _TH, TD_NUM as _TD_NUM, TD_RED as _TD_RED,
    C_NAVY, C_ORANGE, C_CHART_SEC, C_CHART_GRID,
    TD_SUB_LBL as _TD_SUB_LBL, TD_SUB_NUM as _TD_SUB_NUM, TD_SUB_RED as _TD_SUB_RED,
    ROW_SEC,
    ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED,
    ROW_CAL_LBL, ROW_CAL_NUM, ROW_CAL_RED,
    ROW_ITEM,
    html_table as _html_table,
)

_TD_ANNO = 'padding:4px 10px;text-align:right;border-bottom:1px solid #f0edf8;color:#718096;font-size:0.88em'

_I1 = '&nbsp;&nbsp;&nbsp;'

# ── 멕시코 탭용 annotation 컬럼 역할 ────────────────────────────────────────
_ANNO_PCT_COLS = {0, 1, 2, 6, 7, 8}   # 마진율 x.x%
_ANNO_PP_COLS  = {3, 4, 9}             # p.p. 차이 x.xp
_PCT_COLS      = {5, 10}               # 달성률 x.x%

# ── 중국 탭용 annotation 컬럼 역할 (7컬럼) ────────────────────────────────────
# 컬럼: 0=전년도, 1=전월실, 2=당월실, 3=전월대비, 4=당월계, 5=계획대비, 6=달성누적
_ANNO2_PCT_COLS = {0, 1, 2, 4, 6}   # 마진율 x.x%
_ANNO2_PP_COLS  = {3, 5}             # p.p. 차이 x.xp


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────

def _get_연도_목록():
    df = load_sheet(Sheets.멕시코손익_DB)
    return sorted(pd.to_numeric(df['연도'], errors='coerce').dropna().astype(int).unique().tolist())


def _get_memo(sheet_info, year, month):
    try:
        df = load_sheet(sheet_info)
        df['연도'] = df['연도'].astype(str).str.strip()
        df['월']   = df['월'].astype(str).str.strip()
        row = df[(df['연도'] == str(year)) & (df['월'] == str(month))]
        return str(row.iloc[0]['메모']) if not row.empty else ''
    except Exception:
        return ''


def _sec_title(title, unit=''):
    return (
        '<div style="display:flex;justify-content:space-between;'
        'align-items:baseline;margin:0 0 4px 0">'
        f'<h3 style="margin:0;font-size:1.1em;font-weight:600">{title}</h3>'
        f'<span style="font-size:0.8em;color:gray">{unit}</span>'
        '</div>'
    )


def _memo_block(memo):
    if not memo:
        return ''
    return f'<p style="margin:0;font-size:0.9em;line-height:1.6;white-space:pre-wrap">{memo}</p>'


def _fmt_v(v, fmt_type, col_idx):
    """셀 값 포맷: 음수는 - 부호"""
    if v is None:
        return ''
    if col_idx in _PCT_COLS:
        return f'-{abs(v):.1f}%' if v < 0 else f'{v:.1f}%'
    if fmt_type == 'd1':
        return f'-{abs(v):,.1f}' if v < 0 else f'{v:,.1f}'
    return _fmt(v)   # 정수: common.fmt (쉼표 포함, 음수 - 부호)


def _fmt_anno(v, col_idx):
    """annotation 행 포맷: 마진율 또는 p.p."""
    if v is None:
        return ''
    if col_idx in _ANNO_PCT_COLS:
        return f'-{abs(v):.1f}%' if v < 0 else f'{v:.1f}%'
    if col_idx in _ANNO_PP_COLS:
        return f'-{abs(v):.1f}p' if v < 0 else f'{v:.1f}p'
    return ''


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 1: 멕시코_SGAM ─────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _build_멕시코손익(year, month):
    df = load_sheet(Sheets.멕시코손익_DB)
    df = _drop_empty(df, '연도', '월')
    for col in ['구분1', '구분2', '구분3']:
        df[col] = df[col].fillna('').astype(str).str.strip()
    df['_v'] = df['값'].apply(_parse)

    def _lookup(g1, g2, yr, mo, g3=None):
        m = (df['구분1'] == g1) & (df['구분2'] == g2) & (df['연도'] == yr) & (df['월'] == mo)
        if g3 is not None:
            m &= (df['구분3'] == g3)
        return float(df.loc[m, '_v'].sum())

    prev_yr, prev_mo = _prev_month(year, month)
    판매량_g3s = (
        df[(df['구분2'] == '판매량') & (df['구분3'] != '')]['구분3']
        .drop_duplicates().tolist()
    )

    def _calc(val_fn, div):
        prev_실    = val_fn('실적', prev_yr, prev_mo) / div
        cur_계     = val_fn('계획', year, month) / div
        cur_실     = val_fn('실적', year, month) / div
        전월비     = cur_실 - prev_실
        계획비     = cur_실 - cur_계
        달성률     = cur_실 / cur_계 * 100 if cur_계 != 0 else None
        전년실     = sum(val_fn('실적', year - 1, m) for m in range(1, 13)) / div
        누적계     = sum(val_fn('계획', year, m) for m in range(1, month + 1)) / div
        누적실     = sum(val_fn('실적', year, m) for m in range(1, month + 1)) / div
        금년계획비 = 누적실 - 누적계
        누적달성률 = 누적실 / 누적계 * 100 if 누적계 != 0 else None
        return [prev_실, cur_계, cur_실, 전월비, 계획비, 달성률,
                전년실, 누적계, 누적실, 금년계획비, 누적달성률]

    def fn_매출(pt, yr, mo):    return _lookup(pt, '매출', yr, mo)
    def fn_영업이익(pt, yr, mo): return _lookup(pt, '영업이익', yr, mo)
    def fn_판매량(pt, yr, mo):  return sum(_lookup(pt, '판매량', yr, mo, g3=g) for g in 판매량_g3s)

    vals_매출 = _calc(fn_매출, 1_000_000)
    vals_영   = _calc(fn_영업이익, 1_000_000)
    vals_판매 = _calc(fn_판매량, 10_000)

    # 영업이익 마진율 annotation
    anno = [None] * 11
    for i in _ANNO_PCT_COLS:
        m, e = vals_매출[i], vals_영[i]
        if m is not None and m != 0 and e is not None:
            anno[i] = e / m * 100
    anno[3] = (anno[2] - anno[0]) if None not in (anno[2], anno[0]) else None
    anno[4] = (anno[2] - anno[1]) if None not in (anno[2], anno[1]) else None
    anno[9] = (anno[8] - anno[7]) if None not in (anno[8], anno[7]) else None

    rows = [
        ('top',  '매출액',   vals_매출, None),
        ('top',  '영업이익', vals_영,   None),
        ('anno', '%',         anno,      None),
        ('top',  '판매량',   vals_판매, 'd1'),
    ]
    for g3 in 판매량_g3s:
        def _fn(pt, yr, mo, _g=g3): return _lookup(pt, '판매량', yr, mo, g3=_g)
        rows.append(('child', g3, _calc(_fn, 10_000), 'd1'))

    py2, cy2 = str(prev_yr)[2:], str(year)[2:]
    col_headers = [
        f"'{py2}.{prev_mo}월 실적",
        f"'{cy2}.{month}월 계획",
        f"'{cy2}.{month}월 실적",
        '전월비', '계획비', '달성률',
        f"'{str(year - 1)[2:]}년 실적",
        f"'{cy2}년 누적계획",
        f"'{cy2}년 누적실적",
        '계획비', '달성률',
    ]
    return rows, col_headers


def _멕시코손익_to_html(rows, col_headers):
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    body = ''
    for row_type, label, vals, fmt in rows:
        if row_type == 'top':
            lbl_s, prefix = ROW_HDR_LBL, ''
        elif row_type == 'anno':
            lbl_s, prefix = ROW_ITEM, ''
        else:  # child
            lbl_s, prefix = ROW_ITEM, _I1

        cells = f'<td style="{lbl_s}">{prefix}{label}</td>'
        for i, v in enumerate(vals):
            if row_type == 'anno':
                cells += f'<td style="{_TD_ANNO}">{_fmt_anno(v, i)}</td>'
            else:
                is_neg = v is not None and v < 0
                num_s  = (ROW_HDR_RED if is_neg else ROW_HDR_NUM) if row_type == 'top' \
                         else (_TD_RED if is_neg else _TD_NUM)
                cells += f'<td style="{num_s}">{_fmt_v(v, fmt, i)}</td>'
        body += f'<tr>{cells}</tr>'

    return _html_table(th_html, body)


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 1 - 섹션 2: 채권채무 현황 ──────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _build_채권채무(year, month):
    df = load_sheet(Sheets.멕시코원주채권채무_DB)
    df = _drop_empty(df, '연도', '월')
    for col in ['구분1', '구분2', '구분3']:
        df[col] = df[col].fillna('').astype(str).str.strip()
    df['_v'] = df['값'].apply(_parse)
    df_mo = df[(df['연도'] == year) & (df['월'] == month)].copy()

    def _get(g1, g2, g3):
        m = (df_mo['구분1'] == g1) & (df_mo['구분2'] == g2) & (df_mo['구분3'] == g3)
        return float(df_mo.loc[m, '_v'].sum())

    def _sub(g1, g2):
        m = (df_mo['구분1'] == g1) & (df_mo['구분2'] == g2)
        return float(df_mo.loc[m, '_v'].sum())

    rows = []
    rows.append(('total', '합계', [
        _sub('USD', '채권'), _sub('USD', '채무'),
        _sub('KRW', '채권'), _sub('KRW', '채무'),
    ]))

    g2_list = df_mo['구분2'].drop_duplicates().tolist()
    for g2 in g2_list:
        col_usd, col_krw = (0, 2) if g2 == '채권' else (1, 3)

        parent_vals = [None] * 4
        parent_vals[col_usd] = _sub('USD', g2)
        parent_vals[col_krw] = _sub('KRW', g2)
        rows.append(('parent', g2, parent_vals))

        for g3 in df_mo[df_mo['구분2'] == g2]['구분3'].drop_duplicates().tolist():
            if not g3:
                continue
            child_vals = [None] * 4
            child_vals[col_usd] = _get('USD', g2, g3)
            child_vals[col_krw] = _get('KRW', g2, g3)
            rows.append(('child', g3, child_vals))

    return rows


def _채권채무_to_html(rows):
    col_hdrs = ['USD 채권', 'USD 채무', 'KRW 채권', 'KRW 채무']
    th = (f'<th style="{_TH}">구분</th>'
          + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_hdrs))

    body = ''
    for row_type, label, vals in rows:
        if row_type == 'total':
            lbl_s = ROW_HDR_LBL
        elif row_type == 'parent':
            lbl_s = _TD_SUB_LBL
        else:
            lbl_s = ROW_ITEM

        prefix = _I1 if row_type == 'child' else ''
        cells = f'<td style="{lbl_s}">{prefix}{label}</td>'

        for v in vals:
            if v is None:
                cells += f'<td style="{_TD_NUM}"></td>'
            else:
                if row_type == 'total':
                    num_s = ROW_HDR_RED if v < 0 else ROW_HDR_NUM
                elif row_type == 'parent':
                    num_s = _TD_SUB_RED if v < 0 else _TD_SUB_NUM
                else:
                    num_s = _TD_RED if v < 0 else _TD_NUM
                cells += f'<td style="{num_s}">{_fmt(v) if v else ""}</td>'
        body += f'<tr>{cells}</tr>'

    return _html_table(f'<tr>{th}</tr>', body)


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 2: 중국_기차배건 ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _fmt_v2(v, fmt_type):
    if v is None:
        return ''
    if fmt_type == 'd1':
        return f'-{abs(v):,.1f}' if v < 0 else f'{v:,.1f}'
    return _fmt(v)


def _fmt_anno2(v, col_idx):
    if v is None:
        return ''
    if col_idx in _ANNO2_PCT_COLS:
        return f'-{abs(v):.1f}%' if v < 0 else f'{v:.1f}%'
    if col_idx in _ANNO2_PP_COLS:
        return f'-{abs(v):.1f}p' if v < 0 else f'{v:.1f}p'
    return ''


def _build_중국손익(year, month):
    df = load_sheet(Sheets.중국손익_DB)
    df = _drop_empty(df, '연도', '월')
    for col in ['구분1', '구분2', '구분3']:
        df[col] = df[col].fillna('').astype(str).str.strip()
    df['_v'] = df['값'].apply(_parse)

    prev_yr, prev_mo = _prev_month(year, month)

    def _q(g1, g2, g3, yr, mo):
        m = ((df['구분1'] == g1) & (df['구분2'] == g2) & (df['구분3'] == g3)
             & (df['연도'] == yr) & (df['월'] == mo))
        return float(df.loc[m, '_v'].sum())

    def _q_list(g1, g2s, g3, yr, mo):
        m = ((df['구분1'] == g1) & (df['구분2'].isin(g2s)) & (df['구분3'] == g3)
             & (df['연도'] == yr) & (df['월'] == mo))
        return float(df.loc[m, '_v'].sum())

    def _yr_q(g1, g2, g3, yr):
        m = ((df['구분1'] == g1) & (df['구분2'] == g2) & (df['구분3'] == g3)
             & (df['연도'] == yr))
        return float(df.loc[m, '_v'].sum())

    def _yr_q_list(g1, g2s, g3, yr):
        m = ((df['구분1'] == g1) & (df['구분2'].isin(g2s)) & (df['구분3'] == g3)
             & (df['연도'] == yr))
        return float(df.loc[m, '_v'].sum())

    def _ytd_q(g1, g2, g3, yr, mo):
        m = ((df['구분1'] == g1) & (df['구분2'] == g2) & (df['구분3'] == g3)
             & (df['연도'] == yr) & (df['월'] <= mo))
        return float(df.loc[m, '_v'].sum())

    def _ytd_q_list(g1, g2s, g3, yr, mo):
        m = ((df['구분1'] == g1) & (df['구분2'].isin(g2s)) & (df['구분3'] == g3)
             & (df['연도'] == yr) & (df['월'] <= mo))
        return float(df.loc[m, '_v'].sum())

    def _row(g1, g2):
        """단일 g2에 대한 7개 값 [전년도, 전월실, 당월실, 전월대비, 당월계, 계획대비, 달성누적]"""
        전년도 = _yr_q(g1, g2, '실적', year - 1)
        전월실 = _q(g1, g2, '실적', prev_yr, prev_mo)
        당월실 = _q(g1, g2, '실적', year, month)
        당월계 = _q(g1, g2, '계획', year, month)
        누적   = _ytd_q(g1, g2, '실적', year, month)
        return [전년도, 전월실, 당월실, 당월실 - 전월실, 당월계, 당월실 - 당월계, 누적]

    def _row_multi(g1, g2s):
        """여러 g2 합계에 대한 7개 값"""
        전년도 = _yr_q_list(g1, g2s, '실적', year - 1)
        전월실 = _q_list(g1, g2s, '실적', prev_yr, prev_mo)
        당월실 = _q_list(g1, g2s, '실적', year, month)
        당월계 = _q_list(g1, g2s, '계획', year, month)
        누적   = _ytd_q_list(g1, g2s, '실적', year, month)
        return [전년도, 전월실, 당월실, 당월실 - 전월실, 당월계, 당월실 - 당월계, 누적]

    매출_g2s  = ['열후', '열전', '연마']
    판관비_g2s = ['인건비', '관리비', '판매비']

    v_매출     = _row_multi('매출액', 매출_g2s)
    v_원가     = _row('매출원가', '매출원가')
    v_판관비   = _row_multi('판관비', 판관비_g2s)
    v_매출이익 = [a - b for a, b in zip(v_매출, v_원가)]
    v_영업이익 = [a - b for a, b in zip(v_매출이익, v_판관비)]

    def _anno(v_이익, v_매출_ref):
        result = [None] * 7
        for i in _ANNO2_PCT_COLS:
            m, e = v_매출_ref[i], v_이익[i]
            if m and e is not None:
                result[i] = e / m * 100
        result[3] = (result[2] - result[1]) if None not in (result[2], result[1]) else None
        result[5] = (result[2] - result[4]) if None not in (result[2], result[4]) else None
        return result

    anno_매출이익 = _anno(v_매출이익, v_매출)
    anno_영업이익 = _anno(v_영업이익, v_매출)

    rows = [
        ('hdr',   '매출액',   v_매출,                    None),
        ('child', '열후',     _row('매출액', '열후'),     None),
        ('child', '열전',     _row('매출액', '열전'),     None),
        ('child', '연마',     _row('매출액', '연마'),     None),
        ('hdr',   '판매량',   _row_multi('판매량', 매출_g2s), 'd1'),
        ('child', '열후',     _row('판매량', '열후'),     'd1'),
        ('child', '열전',     _row('판매량', '열전'),     'd1'),
        ('child', '연마',     _row('판매량', '연마'),     'd1'),
        ('hdr',   '매출원가', v_원가,                    None),
        ('calc',   '매출이익', v_매출이익,                None),
        ('anno',  '%',        anno_매출이익,              None),
        ('hdr',   '판관비',   v_판관비,                  None),
        ('child', '인건비',   _row('판관비', '인건비'),   None),
        ('child', '관리비',   _row('판관비', '관리비'),   None),
        ('child', '판매비',   _row('판관비', '판매비'),   None),
        ('calc',  '영업이익', v_영업이익,                None),
        ('anno',  '%',        anno_영업이익,              None),
    ]

    prev_yr2 = str(prev_yr)[2:]
    py2      = str(year - 1)[2:]
    col_headers = [
        f"'{py2}년",
        f"'{prev_yr2}.{prev_mo}월",
        f"{month}월",
        "전월대비",
        f"{month}월계획",
        "계획대비",
        "달성누적",
    ]
    return rows, col_headers


def _중국손익_to_html(rows, col_headers):
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    body = ''
    for row_type, label, vals, fmt in rows:
        if row_type == 'hdr':
            lbl_s, prefix = ROW_HDR_LBL, ''
        elif row_type == 'calc':
            lbl_s, prefix = ROW_CAL_LBL, ''
        elif row_type == 'anno':
            lbl_s, prefix = ROW_ITEM, ''
        else:  # child
            lbl_s, prefix = ROW_ITEM, _I1

        cells = f'<td style="{lbl_s}">{prefix}{label}</td>'
        for i, v in enumerate(vals):
            if row_type == 'anno':
                cells += f'<td style="{_TD_ANNO}">{_fmt_anno2(v, i)}</td>'
            else:
                is_neg = v is not None and v < 0
                if row_type == 'calc':
                    num_s = ROW_CAL_RED if is_neg else ROW_CAL_NUM
                elif row_type == 'hdr':
                    num_s = ROW_HDR_RED if is_neg else ROW_HDR_NUM
                else:
                    num_s = _TD_RED if is_neg else _TD_NUM
                cells += f'<td style="{num_s}">{_fmt_v2(v, fmt)}</td>'
        body += f'<tr>{cells}</tr>'

    return _html_table(th_html, body)


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 2-2: 중국 재무상태표 ────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _build_중국재무상태표(year, month):
    df = load_sheet(Sheets.중국재무상태표_DB)
    df = _drop_empty(df, '연도', '월')
    for col in ['구분1', '구분2']:
        df[col] = df[col].fillna('').astype(str).str.strip()
    df['_v'] = df['값'].apply(_parse)

    prev_yr, prev_mo = _prev_month(year, month)

    # DB에 존재하는 연도 중 현재 조회 연도 이전인 것들만 연말 컬럼으로 사용
    db_years = sorted(df['연도'].unique().tolist())
    year_end_years = [y for y in db_years if y < year]

    def _q(g1, g2, yr, mo):
        m = ((df['구분1'] == g1) & (df['구분2'] == g2)
             & (df['연도'] == yr) & (df['월'] == mo))
        return float(df.loc[m, '_v'].sum())

    def _q_total(g1, yr, mo):
        m = (df['구분1'] == g1) & (df['연도'] == yr) & (df['월'] == mo)
        return float(df.loc[m, '_v'].sum())

    # 당월 기준으로 구분2 목록 확보
    cur = df[(df['연도'] == year) & (df['월'] == month)]
    g2s = {g1: cur[cur['구분1'] == g1]['구분2'].tolist()
           for g1 in ['자산', '부채', '자본']}

    def _vals(get_fn):
        """연말 컬럼들 + 전월 + 당월 + 전월대비"""
        vals = [get_fn(y, 12) for y in year_end_years]
        vc = get_fn(year, month)
        vp = get_fn(prev_yr, prev_mo)
        vals.extend([vp, vc, vc - vp])
        return vals

    rows = []
    totals = {}

    for g1 in ['자산', '부채', '자본']:
        tv = _vals(lambda yr, mo, _g=g1: _q_total(_g, yr, mo))
        totals[g1] = tv
        rows.append(('sub', f'{g1}총계', tv))
        for g2 in g2s.get(g1, []):
            rows.append(('child', g2, _vals(lambda yr, mo, _g=g1, _g2=g2: _q(_g, _g2, yr, mo))))

    # 부채및자본총계 = 부채총계 + 자본총계
    rows.append(('sub', '부채및자본총계', [b + c for b, c in zip(totals['부채'], totals['자본'])]))

    # 안정성 비율
    def _부채비율(yr, mo):
        자본 = _q_total('자본', yr, mo)
        return _q_total('부채', yr, mo) / 자본 * 100 if 자본 != 0 else None

    def _차입금의존도(yr, mo):
        자산 = _q_total('자산', yr, mo)
        return _q('부채', '차입금', yr, mo) / 자산 * 100 if 자산 != 0 else None

    def _ratio_vals(fn):
        vals = [fn(y, 12) for y in year_end_years]
        vc = fn(year, month)
        vp = fn(prev_yr, prev_mo)
        diff = (vc - vp) if (vc is not None and vp is not None) else None
        vals.extend([vp, vc, diff])
        return vals

    n_cols = len(year_end_years) + 3  # 연말 컬럼들 + 전월 + 당월 + 전월비
    rows.append(('sec', '안정성', [None] * n_cols))
    rows.append(('ratio', '부채비율', _ratio_vals(_부채비율)))
    rows.append(('ratio', '차입금의존도', _ratio_vals(_차입금의존도)))

    prev_yr2 = str(prev_yr)[2:]
    col_headers = [f"'{str(y)[2:]}년" for y in year_end_years]
    col_headers.append(f"'{prev_yr2}.{prev_mo}월")
    col_headers.append(f"'{str(year)[2:]}.{month}월")
    col_headers.append("전월비")
    return rows, col_headers


def _중국재무상태표_to_html(rows, col_headers):
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    body = ''
    for row_type, label, vals in rows:
        if row_type == 'sub':
            lbl_s, prefix = ROW_HDR_LBL, ''
        elif row_type == 'sec':
            lbl_s, prefix = ROW_CAL_LBL, ''
        else:  # 'child', 'ratio'
            lbl_s, prefix = ROW_ITEM, _I1

        cells = f'<td style="{lbl_s}">{prefix}{label}</td>'

        for v in vals:
            if row_type == 'sec':
                cells += f'<td style="{ROW_CAL_NUM}"></td>'
            elif row_type == 'ratio':
                if v is None:
                    cells += f'<td style="{_TD_NUM}"></td>'
                else:
                    is_neg = v < 0
                    num_s = _TD_RED if is_neg else _TD_NUM
                    cells += f'<td style="{num_s}">{"-" if is_neg else ""}{abs(v):.1f}%</td>'
            else:  # 'sub', 'child'
                is_neg = v is not None and v < 0
                num_s = (ROW_HDR_RED if is_neg else ROW_HDR_NUM) if row_type == 'sub' \
                        else (_TD_RED if is_neg else _TD_NUM)
                cells += f'<td style="{num_s}">{_fmt(v) if v is not None else ""}</td>'

        body += f'<tr>{cells}</tr>'

    return _html_table(th_html, body)


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 2-3: 중국 판매구성 - 제품별 판매 현황 ──────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _build_중국판매구성_제품별(year, month):
    df = load_sheet(Sheets.중국판매구성_제품별_DB)
    df = _drop_empty(df, '연도', '월')
    for col in ['구분1', '구분2', '구분3']:
        df[col] = df[col].fillna('').astype(str).str.strip()
    df['_v'] = df['값'].apply(_parse)

    prev_yr, prev_mo = _prev_month(year, month)

    def _q(g1, g2, g3, yr, mo):
        m = ((df['구분1'] == g1) & (df['구분2'] == g2) & (df['구분3'] == g3)
             & (df['연도'] == yr) & (df['월'] == mo))
        return float(df.loc[m, '_v'].sum())

    def _ytd(g1, g2, g3, yr, mo):
        m = ((df['구분1'] == g1) & (df['구분2'] == g2) & (df['구분3'] == g3)
             & (df['연도'] == yr) & (df['월'] <= mo))
        return float(df.loc[m, '_v'].sum())

    def _단가(g, q):
        """금액(백만원) / 판매량(만개) × 100 = 원/개"""
        return g * 100 / q if q else 0.0

    products = ['열후', '열전', '연마']

    def _8vals_금액(g2):
        계  = _q('매출액', g2, '계획', year, month)
        전  = _q('매출액', g2, '실적', prev_yr, prev_mo)
        당  = _q('매출액', g2, '실적', year, month)
        누계 = _ytd('매출액', g2, '계획', year, month)
        누실 = _ytd('매출액', g2, '실적', year, month)
        return [계, 전, 당, 당 - 전, 당 - 계, 누계, 누실, 누실 - 누계]

    def _8vals_판매량(g2):
        계  = _q('판매량', g2, '계획', year, month)
        전  = _q('판매량', g2, '실적', prev_yr, prev_mo)
        당  = _q('판매량', g2, '실적', year, month)
        누계 = _ytd('판매량', g2, '계획', year, month)
        누실 = _ytd('판매량', g2, '실적', year, month)
        return [계, 전, 당, 당 - 전, 당 - 계, 누계, 누실, 누실 - 누계]

    def _8vals_단가(g2):
        gk = _q('매출액', g2, '계획', year, month)
        gp = _q('매출액', g2, '실적', prev_yr, prev_mo)
        gc = _q('매출액', g2, '실적', year, month)
        gnk = _ytd('매출액', g2, '계획', year, month)
        gnc = _ytd('매출액', g2, '실적', year, month)
        qk  = _q('판매량', g2, '계획', year, month)
        qp  = _q('판매량', g2, '실적', prev_yr, prev_mo)
        qc  = _q('판매량', g2, '실적', year, month)
        qnk = _ytd('판매량', g2, '계획', year, month)
        qnc = _ytd('판매량', g2, '실적', year, month)
        dk, dp_, dc = _단가(gk, qk), _단가(gp, qp), _단가(gc, qc)
        dnk, dnc    = _단가(gnk, qnk), _단가(gnc, qnc)
        return [dk, dp_, dc, dc - dp_, dc - dk, dnk, dnc, dnc - dnk]

    rows = []
    for prod in products:
        rows.append(('sec', prod))
        rows.append(('item', '금액', _8vals_금액(prod), None))
        rows.append(('item', '단가', _8vals_단가(prod), None))
        rows.append(('item', '수량', _8vals_판매량(prod), 'd1'))

    # 합계
    rows.append(('sec', '합계'))

    def _tot(g1, g3, yr, mo):
        return sum(_q(g1, p, g3, yr, mo) for p in products)

    def _ytd_tot(g1, g3, yr, mo):
        return sum(_ytd(g1, p, g3, yr, mo) for p in products)

    gk  = _tot('매출액', '계획', year, month)
    gp  = _tot('매출액', '실적', prev_yr, prev_mo)
    gc  = _tot('매출액', '실적', year, month)
    gnk = _ytd_tot('매출액', '계획', year, month)
    gnc = _ytd_tot('매출액', '실적', year, month)
    qk  = _tot('판매량', '계획', year, month)
    qp  = _tot('판매량', '실적', prev_yr, prev_mo)
    qc  = _tot('판매량', '실적', year, month)
    qnk = _ytd_tot('판매량', '계획', year, month)
    qnc = _ytd_tot('판매량', '실적', year, month)

    tot_g  = [gk, gp, gc, gc - gp, gc - gk, gnk, gnc, gnc - gnk]
    tot_q  = [qk, qp, qc, qc - qp, qc - qk, qnk, qnc, qnc - qnk]
    dk, dp_, dc = _단가(gk, qk), _단가(gp, qp), _단가(gc, qc)
    dnk, dnc    = _단가(gnk, qnk), _단가(gnc, qnc)
    tot_d  = [dk, dp_, dc, dc - dp_, dc - dk, dnk, dnc, dnc - dnk]

    rows.append(('total', '금액', tot_g, None))
    rows.append(('total', '단가', tot_d, None))
    rows.append(('total', '수량', tot_q, 'd1'))

    cy2      = str(year)[2:]
    prev_yr2 = str(prev_yr)[2:]
    col_headers = [
        f"'{cy2}.{month}월계획",
        f"'{prev_yr2}.{prev_mo}월실적",
        f"{month}월실적",
        "전월비",
        "계획비",
        f"'{cy2}년 누적계획",
        "누적실적",
        "누적계획비",
    ]
    return rows, col_headers


def _중국판매구성_제품별_to_html(rows, col_headers):
    n_cols = len(col_headers) + 1
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    body = ''
    for row in rows:
        kind = row[0]
        if kind == 'sec':
            body += f'<tr><td colspan="{n_cols}" style="{ROW_SEC}">{row[1]}</td></tr>'
        else:
            _, label, vals, fmt = row
            is_tot = (kind == 'total')
            lbl_s  = ROW_HDR_LBL if is_tot else ROW_ITEM
            cells  = f'<td style="{lbl_s}">{label}</td>'
            for v in vals:
                is_neg = v < 0
                num_s = (ROW_HDR_RED if is_neg else ROW_HDR_NUM) if is_tot \
                        else (_TD_RED if is_neg else _TD_NUM)
                fv = _fmt(v, decimal=1) if fmt == 'd1' else _fmt(v)
                cells += f'<td style="{num_s}">{fv}</td>'
            body += f'<tr>{cells}</tr>'
    return _html_table(th_html, body)


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 2-4: 중국 판매구성 - 거래처별 판매 현황 ──────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

_CUST_ORDER = ['CW', '만도', '남양', '모비스', '기타']


def _build_중국판매구성_거래처별(year, month):
    df = load_sheet(Sheets.중국판매구성_거래처별_DB)
    df = _drop_empty(df, '연도', '월')
    df['구분1'] = df['구분1'].fillna('').astype(str).str.strip()
    df['_v'] = df['값'].apply(_parse)

    prev_yr, prev_mo = _prev_month(year, month)

    db_years = sorted(df['연도'].unique().tolist())
    past_years = [y for y in db_years if y < year]

    def _q(g1, yr, mo):
        m = (df['구분1'] == g1) & (df['연도'] == yr) & (df['월'] == mo)
        return float(df.loc[m, '_v'].sum())

    def _annual_avg(g1, yr):
        sub = df[(df['구분1'] == g1) & (df['연도'] == yr)]
        n = sub['월'].nunique()
        return float(sub['_v'].sum()) / n if n else 0.0

    def _ytd_avg(g1, yr, mo):
        sub = df[(df['구분1'] == g1) & (df['연도'] == yr) & (df['월'] <= mo)]
        return float(sub['_v'].sum()) / mo if mo else 0.0

    customers = [g for g in df['구분1'].unique() if g]
    ordered = [c for c in _CUST_ORDER if c in set(customers)]
    ordered += [c for c in customers if c not in set(_CUST_ORDER)]
    customers = ordered

    def _tot_annual_avg(yr):
        return sum(_annual_avg(c, yr) for c in customers)

    def _tot_ytd_avg(yr, mo):
        return sum(_ytd_avg(c, yr, mo) for c in customers)

    def _tot_q(yr, mo):
        return sum(_q(c, yr, mo) for c in customers)

    def _qty_vals(cust):
        vals = [_annual_avg(cust, y) for y in past_years]
        vals.append(_ytd_avg(cust, year, month))
        vals.extend(_q(cust, year, m) for m in range(1, month + 1))
        vals.append(_q(cust, year, month) - _q(cust, prev_yr, prev_mo))
        return vals

    def _pct_vals(cust):
        vals = []
        for y in past_years:
            tot = _tot_annual_avg(y)
            vals.append(_annual_avg(cust, y) / tot * 100 if tot else 0.0)
        tot_ytd = _tot_ytd_avg(year, month)
        vals.append(_ytd_avg(cust, year, month) / tot_ytd * 100 if tot_ytd else 0.0)
        for m in range(1, month + 1):
            tot = _tot_q(year, m)
            vals.append(_q(cust, year, m) / tot * 100 if tot else 0.0)
        # 전월比 for 비중: p.p. 차이
        cur_tot = _tot_q(year, month)
        prv_tot = _tot_q(prev_yr, prev_mo)
        cur_pct = _q(cust, year, month) / cur_tot * 100 if cur_tot else 0.0
        prv_pct = _q(cust, prev_yr, prev_mo) / prv_tot * 100 if prv_tot else 0.0
        vals.append(cur_pct - prv_pct)
        return vals

    def _tot_qty_vals():
        vals = [_tot_annual_avg(y) for y in past_years]
        vals.append(_tot_ytd_avg(year, month))
        vals.extend(_tot_q(year, m) for m in range(1, month + 1))
        vals.append(_tot_q(year, month) - _tot_q(prev_yr, prev_mo))
        return vals

    rows = []
    for cust in customers:
        rows.append(('parent', cust))
        rows.append(('qty', '판매량', _qty_vals(cust), 'd1'))
        rows.append(('pct', '비중',   _pct_vals(cust), None))

    rows.append(('total', '합계', _tot_qty_vals(), 'd1'))

    cy2 = str(year)[2:]
    col_headers = [f"'{str(y)[2:]}년 평균" for y in past_years]
    col_headers.append(f"'{cy2}년 평균")
    for m in range(1, month + 1):
        col_headers.append(f"'{cy2}.{m}월" if m == 1 else f"{m}월")
    col_headers.append("전월比")
    return rows, col_headers


def _중국판매구성_거래처별_to_html(rows, col_headers):
    n_cols = len(col_headers) + 1
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    body = ''
    for row in rows:
        kind = row[0]
        if kind == 'parent':
            body += f'<tr><td colspan="{n_cols}" style="{ROW_SEC}">{row[1]}</td></tr>'
        elif kind == 'total':
            _, label, vals, fmt = row
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            for v in vals:
                is_neg = v < 0
                num_s = ROW_HDR_RED if is_neg else ROW_HDR_NUM
                fv = _fmt(v, decimal=1) if fmt == 'd1' else _fmt(v)
                cells += f'<td style="{num_s}">{fv}</td>'
            body += f'<tr>{cells}</tr>'
        else:  # 'qty' or 'pct'
            _, label, vals, fmt = row
            last_idx = len(vals) - 1
            cells = f'<td style="{ROW_ITEM}">{_I1}{label}</td>'
            for i, v in enumerate(vals):
                is_neg = v < 0
                num_s = _TD_RED if is_neg else _TD_NUM
                if kind == 'pct':
                    if i == last_idx:
                        fv = f'-{abs(v):.1f}p' if is_neg else f'{v:.1f}p'
                    else:
                        fv = f'-{abs(v):.1f}%' if is_neg else f'{v:.1f}%'
                else:
                    fv = _fmt(v, decimal=1) if fmt == 'd1' else _fmt(v)
                cells += f'<td style="{num_s}">{fv}</td>'
            body += f'<tr>{cells}</tr>'
    return _html_table(th_html, body)


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 2-5: 중국 판매구성 - 열후 제품 판매 비중 ────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _build_중국판매구성_열후비중(year, month):
    df = load_sheet(Sheets.중국판매구성_열후별_DB)
    df = _drop_empty(df, '연도', '월')
    for col in ['구분1', '구분2']:
        df[col] = df[col].fillna('').astype(str).str.strip()
    df['_v'] = df['값'].apply(_parse)

    df_q = df[df['구분1'] == '판매량']
    vm = df_q.set_index(['구분2', '연도', '월'])['_v'].to_dict()

    prev_yr, prev_mo = _prev_month(year, month)

    def raw(품목, yr, mo):
        return vm.get((품목, yr, mo), 0.0)

    def yr_avg(품목, yr):
        vals = [v for m in range(1, 13) if (v := raw(품목, yr, m)) > 0]
        return sum(vals) / len(vals) if vals else 0.0

    연도_in_db = sorted(df_q['연도'].unique().tolist())
    recent = _recent_months(year, month)

    products = ['연마', '열전', '열후']

    data = {}
    for prod in products:
        vals = [yr_avg(prod, yr) for yr in 연도_in_db]
        vals += [raw(prod, yr_c, mo_c) for yr_c, mo_c in recent]
        data[prod] = vals

    n = len(연도_in_db) + len(recent)
    계_vals  = [sum(data[p][i] for p in products) for i in range(n)]
    비중_vals = [data['열후'][i] / 계_vals[i] * 100 if 계_vals[i] else 0.0 for i in range(n)]

    # 전월比: 판매량은 당월-전월, 비중은 p.p.
    def _전월비(prod):
        return raw(prod, year, month) - raw(prod, prev_yr, prev_mo)

    전월비_계  = sum(_전월비(p) for p in products)
    cur_계     = sum(raw(p, year, month) for p in products)
    prv_계     = sum(raw(p, prev_yr, prev_mo) for p in products)
    cur_비중   = raw('열후', year, month) / cur_계 * 100 if cur_계 else 0.0
    prv_비중   = raw('열후', prev_yr, prev_mo) / prv_계 * 100 if prv_계 else 0.0

    for prod in products:
        data[prod] = data[prod] + [_전월비(prod)]
    계_vals  = 계_vals  + [전월비_계]
    비중_vals = 비중_vals + [cur_비중 - prv_비중]

    col_hdrs = _build_col_hdrs(연도_in_db, recent, annual_suffix='년 평균')
    col_hdrs.append('전월比')

    rows = [
        ('sub',   '연마',     data['연마']),
        ('sub',   '열전',     data['열전']),
        ('sub',   '열후',     data['열후']),
        ('total', '계',       계_vals),
        ('pct',   '열후비중', 비중_vals),
    ]

    chart_x    = col_hdrs[:-1]
    chart_data = {p: data[p][:-1] for p in products}
    chart_계   = 계_vals[:-1]
    chart_비중 = 비중_vals[:-1]
    return rows, col_hdrs, chart_x, chart_data, chart_계, chart_비중


def _중국판매구성_열후비중_to_html(rows, col_hdrs):
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in ['구분'] + col_hdrs)
    body = ''
    sub_idx = 0
    for kind, label, vals in rows:
        if kind == 'sub':
            bg = ';background:#f9f9fb' if sub_idx % 2 else ''
            sub_idx += 1
            cells = f'<td style="{ROW_ITEM + bg}">{label}</td>'
            for v in vals:
                is_neg = v < 0
                cells += f'<td style="{(_TD_RED if is_neg else _TD_NUM) + bg}">{_fmt(v, decimal=1)}</td>'
        elif kind == 'total':
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            for v in vals:
                is_neg = v < 0
                cells += f'<td style="{ROW_HDR_RED if is_neg else ROW_HDR_NUM}">{_fmt(v, decimal=1)}</td>'
        elif kind == 'pct':
            cells = f'<td style="{ROW_ITEM}">{label}</td>'
            for v in vals:
                is_neg = v < 0
                fv = f'-{abs(v):.1f}%' if is_neg else f'{v:.1f}%'
                cells += f'<td style="{_TD_RED if is_neg else _TD_NUM}">{fv}</td>'
        body += f'<tr>{cells}</tr>'
    return _html_table(f'<tr>{th}</tr>', body)


def _build_중국열후비중_chart(x_labels, data, 계_vals, 비중_vals):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='연마', x=x_labels, y=data['연마'],
        marker_color=C_CHART_SEC, marker_line_width=0,
        text=[_fmt(v, decimal=1) for v in data['연마']],
        textposition='inside', textfont=dict(color='white', size=11),
    ))
    fig.add_trace(go.Bar(
        name='열전', x=x_labels, y=data['열전'],
        marker_color=C_ORANGE, marker_line_width=0,
        text=[_fmt(v, decimal=1) for v in data['열전']],
        textposition='inside', textfont=dict(color='white', size=11),
    ))
    fig.add_trace(go.Bar(
        name='열후', x=x_labels, y=data['열후'],
        marker_color=C_NAVY, marker_line_width=0,
        text=[_fmt(v, decimal=1) for v in data['열후']],
        textposition='inside', textfont=dict(color='white', size=13),
    ))
    fig.add_trace(go.Scatter(
        name='열후비중',
        x=x_labels, y=비중_vals,
        mode='lines+markers+text',
        line=dict(color=C_NAVY, width=2),
        marker=dict(color='white', size=7, line=dict(color=C_NAVY, width=2)),
        text=[f"{round(v)}%" for v in 비중_vals],
        textposition='top center',
        textfont=dict(size=12, color=C_NAVY),
        yaxis='y2',
    ))

    max_계   = max(계_vals)   if 계_vals   else 20
    비중_pos = [v for v in 비중_vals if v > 0]
    min_비중 = min(비중_pos) if 비중_pos else 0
    max_비중 = max(비중_pos) if 비중_pos else 100

    dr        = max(max_비중 - min_비중, 5)
    y2_total  = dr / 0.40
    ymin2     = min_비중 - 0.50 * y2_total
    ymax2     = ymin2 + y2_total

    step      = max(2, int(dr / 4))
    t_min     = (int(min_비중) // step) * step
    t_max     = (int(max_비중) // step + 2) * step
    tick_vals = [v for v in range(t_min, t_max + 1, step) if v >= 0]

    fig.update_layout(
        barmode='stack',
        height=380,
        margin=dict(l=10, r=45, t=15, b=60),
        legend=dict(orientation='h', y=-0.28, x=0.5, xanchor='center',
                    font=dict(size=12), bgcolor='rgba(0,0,0,0)'),
        xaxis=dict(tickfont=dict(size=11, color=C_NAVY),
                   showgrid=False, linecolor='#e2e8f0', linewidth=1, showline=True),
        yaxis=dict(showgrid=True, gridcolor=C_CHART_GRID, gridwidth=1,
                   range=[0, max_계 * 2.5],
                   tickfont=dict(size=11, color=C_NAVY),
                   showline=False, zeroline=False),
        yaxis2=dict(overlaying='y', side='right',
                    range=[ymin2, ymax2],
                    tickvals=tick_vals,
                    ticktext=[f"{v}%" for v in tick_vals],
                    showgrid=False,
                    tickfont=dict(size=11, color=C_NAVY),
                    showline=False, zeroline=False),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 2-7: 중국 원재료 입고 (실적, 단가) ──────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

_MAT_ORDER = ['POSMA45R', 'S45C', 'SWCH45FCR', '기타']


def _build_중국원재료입고(year, month):
    df = load_sheet(Sheets.중국원재료입고_DB)
    df = _drop_empty(df, '연도', '월')
    for col in ['구분1', '구분2']:
        df[col] = df[col].fillna('').astype(str).str.strip()
    df['_v'] = df['값'].apply(_parse)

    prev_yr, prev_mo = _prev_month(year, month)

    db_years = sorted(df['연도'].unique().tolist())
    past_years = [y for y in db_years if y < year]
    recent = _recent_months(year, month, n=4)

    def _q(g1, g2, yr, mo):
        m = (df['구분1'] == g1) & (df['구분2'] == g2) & (df['연도'] == yr) & (df['월'] == mo)
        return float(df.loc[m, '_v'].sum())

    def _yr_sum(g1, g2, yr):
        m = (df['구분1'] == g1) & (df['구분2'] == g2) & (df['연도'] == yr)
        return float(df.loc[m, '_v'].sum())

    def _yr_n(g1, yr):
        m = (df['구분1'] == g1) & (df['구분2'] == '중량') & (df['연도'] == yr) & (df['_v'] > 0)
        return max(int(df.loc[m, '월'].nunique()), 1)

    def _ytd_sum(g1, g2, yr, mo):
        m = (df['구분1'] == g1) & (df['구분2'] == g2) & (df['연도'] == yr) & (df['월'] <= mo)
        return float(df.loc[m, '_v'].sum())

    def _ytd_n(g1, yr, mo):
        m = (df['구분1'] == g1) & (df['구분2'] == '중량') & (df['연도'] == yr) & (df['월'] <= mo) & (df['_v'] > 0)
        return max(int(df.loc[m, '월'].nunique()), 1)

    materials = [m for m in _MAT_ORDER if m in set(df['구분1'].unique())]
    materials += [m for m in df['구분1'].unique() if m and m not in set(_MAT_ORDER)]

    def _tot_w(yr, mo):
        return sum(_q(mat, '중량', yr, mo) for mat in materials)

    def _w_vals(mat):
        vals = [_yr_sum(mat, '중량', y) / _yr_n(mat, y) for y in past_years]
        vals.append(_ytd_sum(mat, '중량', year, month) / _ytd_n(mat, year, month))
        vals.extend(_q(mat, '중량', yr_c, mo_c) for yr_c, mo_c in recent)
        vals.append(_q(mat, '중량', year, month) - _q(mat, '중량', prev_yr, prev_mo))
        return vals

    def _g_vals(mat):
        vals = [_yr_sum(mat, '금액', y) / _yr_n(mat, y) for y in past_years]
        vals.append(_ytd_sum(mat, '금액', year, month) / _ytd_n(mat, year, month))
        vals.extend(_q(mat, '금액', yr_c, mo_c) for yr_c, mo_c in recent)
        vals.append(_q(mat, '금액', year, month) - _q(mat, '금액', prev_yr, prev_mo))
        return vals

    def _d_vals(mat):
        vals = []
        for y in past_years:
            w, g = _yr_sum(mat, '중량', y), _yr_sum(mat, '금액', y)
            vals.append(g / w if w else 0.0)
        w = _ytd_sum(mat, '중량', year, month)
        g = _ytd_sum(mat, '금액', year, month)
        vals.append(g / w if w else 0.0)
        for yr_c, mo_c in recent:
            w, g = _q(mat, '중량', yr_c, mo_c), _q(mat, '금액', yr_c, mo_c)
            vals.append(g / w if w else 0.0)
        # 전월대비: 단가 차이
        w_c, g_c = _q(mat, '중량', year, month), _q(mat, '금액', year, month)
        w_p, g_p = _q(mat, '중량', prev_yr, prev_mo), _q(mat, '금액', prev_yr, prev_mo)
        vals.append((g_c / w_c if w_c else 0.0) - (g_p / w_p if w_p else 0.0))
        return vals

    def _비중_vals(mat):
        vals = []
        for y in past_years:
            n = _yr_n(mat, y)
            w_mat = _yr_sum(mat, '중량', y) / n
            w_tot = sum(_yr_sum(m, '중량', y) / _yr_n(m, y) for m in materials)
            vals.append(w_mat / w_tot * 100 if w_tot else 0.0)
        n = _ytd_n(mat, year, month)
        w_mat = _ytd_sum(mat, '중량', year, month) / n
        w_tot = sum(_ytd_sum(m, '중량', year, month) / _ytd_n(m, year, month) for m in materials)
        vals.append(w_mat / w_tot * 100 if w_tot else 0.0)
        for yr_c, mo_c in recent:
            w_mat = _q(mat, '중량', yr_c, mo_c)
            w_tot = _tot_w(yr_c, mo_c)
            vals.append(w_mat / w_tot * 100 if w_tot else 0.0)
        # 전월대비 for 비중: p.p.
        w_c_mat = _q(mat, '중량', year, month)
        w_p_mat = _q(mat, '중량', prev_yr, prev_mo)
        w_c_tot = _tot_w(year, month)
        w_p_tot = _tot_w(prev_yr, prev_mo)
        c_pct = w_c_mat / w_c_tot * 100 if w_c_tot else 0.0
        p_pct = w_p_mat / w_p_tot * 100 if w_p_tot else 0.0
        vals.append(c_pct - p_pct)
        return vals

    rows = []
    for mat in materials:
        rows.append(('parent', mat))
        rows.append(('pct',  '입고비중', _비중_vals(mat)))
        rows.append(('item', '중량',    _w_vals(mat), 'd1'))
        rows.append(('item', '금액',    _g_vals(mat), None))
        rows.append(('item', '단가',    _d_vals(mat), None))

    # 합계 (계)
    n_reg = len(past_years) + 1 + len(recent)  # 전월대비 제외 컬럼 수

    def _tot_w_col(i):
        if i < len(past_years):
            y = past_years[i]
            return sum(_yr_sum(m, '중량', y) / _yr_n(m, y) for m in materials)
        elif i == len(past_years):
            return sum(_ytd_sum(m, '중량', year, month) / _ytd_n(m, year, month) for m in materials)
        else:
            yr_c, mo_c = recent[i - len(past_years) - 1]
            return _tot_w(yr_c, mo_c)

    def _tot_g_col(i):
        if i < len(past_years):
            y = past_years[i]
            return sum(_yr_sum(m, '금액', y) / _yr_n(m, y) for m in materials)
        elif i == len(past_years):
            return sum(_ytd_sum(m, '금액', year, month) / _ytd_n(m, year, month) for m in materials)
        else:
            yr_c, mo_c = recent[i - len(past_years) - 1]
            return sum(_q(m, '금액', yr_c, mo_c) for m in materials)

    tot_w_v = [_tot_w_col(i) for i in range(n_reg)]
    tot_g_v = [_tot_g_col(i) for i in range(n_reg)]
    tot_d_v = [tot_g_v[i] / tot_w_v[i] if tot_w_v[i] else 0.0 for i in range(n_reg)]

    w_c_tot = _tot_w(year, month)
    w_p_tot = _tot_w(prev_yr, prev_mo)
    g_c_tot = sum(_q(m, '금액', year, month) for m in materials)
    g_p_tot = sum(_q(m, '금액', prev_yr, prev_mo) for m in materials)
    tot_w_v.append(w_c_tot - w_p_tot)
    tot_g_v.append(g_c_tot - g_p_tot)
    tot_d_v.append((g_c_tot / w_c_tot if w_c_tot else 0.0) - (g_p_tot / w_p_tot if w_p_tot else 0.0))

    rows.append(('sec_total', '계'))
    rows.append(('tot_item', '중량', tot_w_v, 'd1'))
    rows.append(('tot_item', '금액', tot_g_v, None))
    rows.append(('tot_item', '단가', tot_d_v, None))

    cy2 = str(year)[2:]
    col_headers = [f"'{str(y)[2:]}년 평균" for y in past_years]
    col_headers.append(f"'{cy2}년 평균")
    last_yr = None
    for yr_c, mo_c in recent:
        col_headers.append(f"'{str(yr_c)[2:]}.{mo_c}월" if yr_c != last_yr else f"{mo_c}월")
        last_yr = yr_c
    col_headers.append("전월대비")
    return rows, col_headers


def _중국원재료입고_to_html(rows, col_headers):
    n_cols = len(col_headers) + 1
    last_idx = len(col_headers) - 1
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    body = ''
    for row in rows:
        kind = row[0]
        if kind == 'parent':
            body += f'<tr><td colspan="{n_cols}" style="{ROW_SEC}">{row[1]}</td></tr>'
        elif kind == 'sec_total':
            body += f'<tr><td colspan="{n_cols}" style="{ROW_HDR_LBL}">{row[1]}</td></tr>'
        elif kind == 'pct':
            _, label, vals = row
            cells = f'<td style="{ROW_ITEM}">{_I1}{label}</td>'
            for i, v in enumerate(vals):
                is_neg = v < 0
                num_s = _TD_RED if is_neg else _TD_NUM
                fv = (f'-{abs(v):.1f}p' if is_neg else f'{v:.1f}p') if i == last_idx \
                     else (f'-{round(abs(v))}%' if is_neg else f'{round(v)}%')
                cells += f'<td style="{num_s}">{fv}</td>'
            body += f'<tr>{cells}</tr>'
        elif kind == 'item':
            _, label, vals, fmt = row
            cells = f'<td style="{ROW_ITEM}">{_I1}{label}</td>'
            for v in vals:
                is_neg = v < 0
                num_s = _TD_RED if is_neg else _TD_NUM
                cells += f'<td style="{num_s}">{_fmt(v, decimal=1) if fmt == "d1" else _fmt(v)}</td>'
            body += f'<tr>{cells}</tr>'
        elif kind == 'tot_item':
            _, label, vals, fmt = row
            cells = f'<td style="{ROW_HDR_LBL}">{_I1}{label}</td>'
            for v in vals:
                is_neg = v < 0
                num_s = ROW_HDR_RED if is_neg else ROW_HDR_NUM
                cells += f'<td style="{num_s}">{_fmt(v, decimal=1) if fmt == "d1" else _fmt(v)}</td>'
            body += f'<tr>{cells}</tr>'
    return _html_table(th_html, body)


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 2-8: 중국 제조 가공비 ────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

_제조가공비_ITEM_ORDER = [
    '부재료비', '급여', '전력비', '감가상각비', '수선비', '소모품비',
    '복리후생비', '지급임차료', '지급수수료', '외주용역비', '외주가공비', '기타',
]


def _build_중국제조가공비(year, month):
    df = load_sheet(Sheets.중국제조가공비_DB)
    df = _drop_empty(df, '연도', '월')
    df['구분1'] = df['구분1'].fillna('').astype(str).str.strip()
    df['_v'] = df['값'].apply(_parse)

    prev_yr, prev_mo = _prev_month(year, month)
    db_years = sorted(df['연도'].unique().tolist())
    past_years = [y for y in db_years if y < year]

    def _q(g1, yr, mo):
        m = (df['구분1'] == g1) & (df['연도'] == yr) & (df['월'] == mo)
        return float(df.loc[m, '_v'].sum())

    def _yr_sum(g1, yr):
        m = (df['구분1'] == g1) & (df['연도'] == yr)
        return float(df.loc[m, '_v'].sum())

    def _yr_n(yr):
        m = (df['구분1'] == '제품생산량') & (df['연도'] == yr) & (df['_v'] > 0)
        return max(int(df.loc[m, '월'].nunique()), 1)

    def _ytd_sum(g1, yr, mo):
        m = (df['구분1'] == g1) & (df['연도'] == yr) & (df['월'] <= mo)
        return float(df.loc[m, '_v'].sum())

    def _ytd_n(yr, mo):
        m = (df['구분1'] == '제품생산량') & (df['연도'] == yr) & (df['월'] <= mo) & (df['_v'] > 0)
        return max(int(df.loc[m, '월'].nunique()), 1)

    all_items_in_db = set(df[df['구분1'] != '제품생산량']['구분1'].unique())
    items = [it for it in _제조가공비_ITEM_ORDER if it in all_items_in_db]
    items += [it for it in all_items_in_db if it and it not in set(_제조가공비_ITEM_ORDER)]

    def _단가(g, p):
        return g / (p * 10) if p else 0.0

    def _g_cols(item):
        vals = [_yr_sum(item, y) / _yr_n(y) for y in past_years]
        vals.append(_ytd_sum(item, year, month) / _ytd_n(year, month))
        g_p = _q(item, prev_yr, prev_mo)
        g_c = _q(item, year, month)
        vals.extend([g_p, g_c, g_c - g_p])
        return vals

    def _d_cols(item):
        vals = [_단가(_yr_sum(item, y), _yr_sum('제품생산량', y)) for y in past_years]
        vals.append(_단가(_ytd_sum(item, year, month), _ytd_sum('제품생산량', year, month)))
        d_p = _단가(_q(item, prev_yr, prev_mo), _q('제품생산량', prev_yr, prev_mo))
        d_c = _단가(_q(item, year, month), _q('제품생산량', year, month))
        vals.extend([d_p, d_c, d_c - d_p])
        return vals

    def _prod_cols():
        vals = [_yr_sum('제품생산량', y) / _yr_n(y) for y in past_years]
        vals.append(_ytd_sum('제품생산량', year, month) / _ytd_n(year, month))
        p_p = _q('제품생산량', prev_yr, prev_mo)
        p_c = _q('제품생산량', year, month)
        vals.extend([p_p, p_c, p_c - p_p])
        return vals

    def _tot_g_cols():
        vals = [sum(_yr_sum(it, y) for it in items) / _yr_n(y) for y in past_years]
        vals.append(sum(_ytd_sum(it, year, month) for it in items) / _ytd_n(year, month))
        tg_p = sum(_q(it, prev_yr, prev_mo) for it in items)
        tg_c = sum(_q(it, year, month) for it in items)
        vals.extend([tg_p, tg_c, tg_c - tg_p])
        return vals

    def _tot_d_cols():
        vals = [_단가(sum(_yr_sum(it, y) for it in items), _yr_sum('제품생산량', y)) for y in past_years]
        vals.append(_단가(sum(_ytd_sum(it, year, month) for it in items), _ytd_sum('제품생산량', year, month)))
        d_p = _단가(sum(_q(it, prev_yr, prev_mo) for it in items), _q('제품생산량', prev_yr, prev_mo))
        d_c = _단가(sum(_q(it, year, month) for it in items), _q('제품생산량', year, month))
        vals.extend([d_p, d_c, d_c - d_p])
        return vals

    rows = []
    for item in items:
        rows.append(('item', item, _g_cols(item), _d_cols(item)))
    rows.append(('total', '합계', _tot_g_cols(), _tot_d_cols()))
    rows.append(('prod', '제품생산량', _prod_cols()))

    cy2, prev_yr2 = str(year)[2:], str(prev_yr)[2:]
    col_headers = []
    for y in past_years:
        yy = str(y)[2:]
        col_headers += [f"'{yy}년 금액", f"'{yy}년 단가"]
    col_headers += [f"'{cy2}년 금액", f"'{cy2}년 단가"]
    col_headers += [f"'{prev_yr2}.{prev_mo}월 금액", f"'{prev_yr2}.{prev_mo}월 단가"]
    mo_lbl = f"{month}월" if year == prev_yr else f"'{cy2}.{month}월"
    col_headers += [f"{mo_lbl} 금액", f"{mo_lbl} 단가"]
    col_headers += ["전월비 금액", "전월비 단가"]
    return rows, col_headers


def _중국제조가공비_to_html(rows, col_headers):
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )

    body = ''
    for row in rows:
        kind = row[0]
        if kind == 'item':
            _, label, g_vals, d_vals = row
            cells = f'<td style="{ROW_ITEM}">{label}</td>'
            for g, d in zip(g_vals, d_vals):
                cells += f'<td style="{_TD_RED if g < 0 else _TD_NUM}">{_fmt(g)}</td>'
                cells += f'<td style="{_TD_RED if d < 0 else _TD_NUM}">{_fmt(d, decimal=1)}</td>'
        elif kind == 'total':
            _, label, g_vals, d_vals = row
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            for g, d in zip(g_vals, d_vals):
                cells += f'<td style="{ROW_HDR_RED if g < 0 else ROW_HDR_NUM}">{_fmt(g)}</td>'
                cells += f'<td style="{ROW_HDR_RED if d < 0 else ROW_HDR_NUM}">{_fmt(d, decimal=1)}</td>'
        elif kind == 'prod':
            _, label, vals = row
            cells = f'<td style="{ROW_ITEM}">{label}</td>'
            for v in vals:
                cells += f'<td style="{_TD_RED if v < 0 else _TD_NUM}">{_fmt(v, decimal=1)}</td>'
                cells += f'<td style="{_TD_NUM}"></td>'
        body += f'<tr>{cells}</tr>'

    return _html_table(th_html, body)


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 2-9: 중국 판매비와 관리비 ─────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

_판관비_ITEM_ORDER = ['급여', '복리후생비', '지급임차료', '세금과공과', '지급수수료', '운반비', '기타']


def _build_중국판관비(year, month):
    df = load_sheet(Sheets.중국판관비_DB)
    df = _drop_empty(df, '연도', '월')
    df['구분1'] = df['구분1'].fillna('').astype(str).str.strip()
    df['_v'] = df['값'].apply(_parse)

    db_years = sorted(df['연도'].unique())
    past_years = [y for y in db_years if y < year]
    prev_yr, prev_mo = _prev_month(year, month)
    recent = _recent_months(year, month, n=4)

    items_in_db = set(df[~df['구분1'].isin(['판매량', '매출액'])]['구분1'].unique())
    items = [it for it in _판관비_ITEM_ORDER if it in items_in_db]
    items += [it for it in items_in_db if it not in set(_판관비_ITEM_ORDER)]

    def _q(g1, yr, mo):
        return float(df[(df['구분1'] == g1) & (df['연도'] == yr) & (df['월'] == mo)]['_v'].sum())

    def _yr_n(yr):
        return max(1, int(df[(df['연도'] == yr) & (~df['구분1'].isin(['판매량', '매출액']))]['월'].nunique()))

    def _ytd_n(yr, mo):
        return max(1, int(df[(df['연도'] == yr) & (df['월'] <= mo)
                             & (~df['구분1'].isin(['판매량', '매출액']))]['월'].nunique()))

    def _yr_avg(g1, yr):
        return sum(_q(g1, yr, m) for m in range(1, 13)) / _yr_n(yr)

    def _ytd_avg(g1, yr, mo):
        return sum(_q(g1, yr, m) for m in range(1, mo + 1)) / _ytd_n(yr, mo)

    def _tot_sum(yr, mo):
        return sum(_q(it, yr, mo) for it in items)

    def _tot_yr_avg(yr):
        return sum(_yr_avg(it, yr) for it in items)

    def _tot_ytd_avg(yr, mo):
        return sum(_ytd_avg(it, yr, mo) for it in items)

    def _period_vals(fn_yr, fn_ytd, fn_q):
        vals = [fn_yr(y) for y in past_years]
        vals.append(fn_ytd(year, month))
        for yr_r, mo_r in recent:
            vals.append(fn_q(yr_r, mo_r))
        vals.append(fn_q(year, month) - fn_q(prev_yr, prev_mo))
        return vals

    def _단가(합계, 판매량):
        return 합계 / 판매량 * 100 if 판매량 else 0.0

    def _단가_cols():
        tot, pv = [], []
        for y in past_years:
            tot.append(_tot_yr_avg(y)); pv.append(_yr_avg('판매량', y))
        tot.append(_tot_ytd_avg(year, month)); pv.append(_ytd_avg('판매량', year, month))
        for yr_r, mo_r in recent:
            tot.append(_tot_sum(yr_r, mo_r)); pv.append(_q('판매량', yr_r, mo_r))
        vals = [_단가(t, p) for t, p in zip(tot, pv)]
        vals.append(_단가(_tot_sum(year, month), _q('판매량', year, month))
                    - _단가(_tot_sum(prev_yr, prev_mo), _q('판매량', prev_yr, prev_mo)))
        return vals

    def _비중_cols():
        tot, mae = [], []
        for y in past_years:
            tot.append(_tot_yr_avg(y)); mae.append(_yr_avg('매출액', y))
        tot.append(_tot_ytd_avg(year, month)); mae.append(_ytd_avg('매출액', year, month))
        for yr_r, mo_r in recent:
            tot.append(_tot_sum(yr_r, mo_r)); mae.append(_q('매출액', yr_r, mo_r))
        vals = [t / m * 100 if m else 0.0 for t, m in zip(tot, mae)]
        cur = _tot_sum(year, month) / _q('매출액', year, month) * 100 if _q('매출액', year, month) else 0.0
        prv = _tot_sum(prev_yr, prev_mo) / _q('매출액', prev_yr, prev_mo) * 100 if _q('매출액', prev_yr, prev_mo) else 0.0
        vals.append(cur - prv)
        return vals

    rows = []
    for it in items:
        rows.append(('item', it, _period_vals(
            lambda y, _i=it: _yr_avg(_i, y),
            lambda yr, mo, _i=it: _ytd_avg(_i, yr, mo),
            lambda yr, mo, _i=it: _q(_i, yr, mo),
        )))
    rows.append(('total', '합계', _period_vals(_tot_yr_avg, _tot_ytd_avg, _tot_sum)))
    rows.append(('item', '판매량', _period_vals(
        lambda y: _yr_avg('판매량', y),
        lambda yr, mo: _ytd_avg('판매량', yr, mo),
        lambda yr, mo: _q('판매량', yr, mo),
    )))
    rows.append(('item', '단가(원/개)', _단가_cols()))
    rows.append(('total', '매출액', _period_vals(
        lambda y: _yr_avg('매출액', y),
        lambda yr, mo: _ytd_avg('매출액', yr, mo),
        lambda yr, mo: _q('매출액', yr, mo),
    )))
    rows.append(('pct', '비중', _비중_cols()))

    col_headers = _build_col_hdrs(past_years + [year], recent, annual_suffix='년 월평균')
    col_headers.append('전월比')
    return rows, col_headers


def _중국판관비_to_html(rows, col_headers):
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    last_col = len(col_headers) - 1
    body = ''
    for kind, label, vals in rows:
        lbl_s = ROW_HDR_LBL if kind == 'total' else ROW_ITEM
        cells = f'<td style="{lbl_s}">{label}</td>'
        for i, v in enumerate(vals):
            is_last = (i == last_col)
            if kind == 'pct':
                txt = f'-{abs(v):.1f}%' if v < 0 else f'{v:.1f}%'
                s = _TD_RED if v < 0 else _TD_NUM
            elif kind == 'total':
                txt = _fmt(v, decimal=1) if is_last else _fmt(v)
                s = ROW_HDR_RED if v < 0 else ROW_HDR_NUM
            else:
                txt = _fmt(v, decimal=1) if is_last else _fmt(v)
                s = _TD_RED if v < 0 else _TD_NUM
            cells += f'<td style="{s}">{txt}</td>'
        body += f'<tr>{cells}</tr>'
    return _html_table(th_html, body)


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 2-10: 중국 재고자산 현황 ─────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

_중국재고_ITEM_ORDER = ['제품', '반제품', '재공', '원재료', '부재료', '기타']


def _build_중국재고자산(year, month):
    df = load_sheet(Sheets.중국재고자산_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['_v'] = df['값'].apply(_parse)
    df['구분1'] = df['구분1'].astype(str).str.strip()
    df['단위']  = df['단위'].astype(str).str.strip()

    vm = df.set_index(['구분1', '단위', '연도', '월'])['_v'].to_dict()

    연도_in_db    = sorted(df['연도'].unique().tolist())
    recent_curr   = _recent_months(year, month, n=3)
    prev_year_end = max((yr for yr in 연도_in_db if yr < year), default=None)
    past_years    = ([prev_year_end]
                     if prev_year_end is not None and (prev_year_end, 12) not in recent_curr
                     else [])
    prev_yr, prev_mo = _prev_month(year, month)

    items_in_db = list(dict.fromkeys(df['구분1'].tolist()))
    items = [it for it in _중국재고_ITEM_ORDER if it in set(items_in_db)]
    items += [it for it in items_in_db if it not in set(_중국재고_ITEM_ORDER)]

    all_keys = df[['구분1', '단위']].drop_duplicates().apply(tuple, axis=1).tolist()

    def raw(g1, 단위, yr, mo):
        return vm.get((g1, 단위, yr, mo), 0.0)

    def pct_chg(curr, prev):
        return (curr - prev) / abs(prev) * 100 if prev else 0.0

    def make_vals(g1, 단위):
        v  = [raw(g1, 단위, yr, 12) for yr in past_years]
        v += [raw(g1, 단위, yr_c, mo_c) for yr_c, mo_c in recent_curr]
        c = raw(g1, 단위, year, month)
        p = raw(g1, 단위, prev_yr, prev_mo)
        v += [c - p, pct_chg(c, p)]
        return v

    def decimal_for(단위):
        return 1 if ('수량' in 단위 or '중량' in 단위) else 0

    rows = []
    for g1 in items:
        rows.append(('parent', g1))
        for d in list(dict.fromkeys(df[df['구분1'] == g1]['단위'].tolist())):
            rows.append(('child', d, make_vals(g1, d), decimal_for(d)))

    def _sum_vals(kw):
        def s(yr, mo): return sum(raw(g1, d, yr, mo) for g1, d in all_keys if kw in d)
        v  = [s(yr, 12) for yr in past_years]
        v += [s(yr_c, mo_c) for yr_c, mo_c in recent_curr]
        c, p = s(year, month), s(prev_yr, prev_mo)
        v += [c - p, pct_chg(c, p)]
        return v

    rows.append(('total_hdr', '재고자산 계'))
    rows.append(('total_child', '금액 계', _sum_vals('금액'), 0))
    단위_vals = df['단위'].unique().tolist()
    if any('수량' in d for d in 단위_vals):
        rows.append(('total_child', '수량 계', _sum_vals('수량'), 1))
    if any('중량' in d for d in 단위_vals):
        rows.append(('total_child', '중량 계', _sum_vals('중량'), 1))

    col_spec = {'past_years': past_years, 'recent_curr': recent_curr}
    return rows, col_spec


def _중국재고자산_to_html(rows, col_spec):
    past_years  = col_spec['past_years']
    recent_curr = col_spec['recent_curr']
    n_cols = 1 + len(past_years) + len(recent_curr) + 2

    th = f'<th style="{_TH}">구분</th>'
    for yr in past_years:
        th += f'<th style="{_TH}">\'{str(yr)[2:]}년말</th>'
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
            if i == n - 1:
                txt = f'-{abs(round(v))}%' if v < 0 else f'{round(v)}%'
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


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 2-11: 중국 생산실적 공정별 처리량 ─────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

_공정별_ITEM_ORDER = ['절단', '건드릴', '선삭', 'D-CUTTING', 'SLOT', '단차연마', '연마', '열후EPS', '황삭연마']


def _build_중국생산실적_공정별(year, month):
    df = load_sheet(Sheets.중국생산실적_공정별_DB)
    df = _drop_empty(df, '연도', '월')
    df['구분1'] = df['구분1'].astype(str).str.strip()
    df['구분2'] = df['구분2'].astype(str).str.strip()
    df['_v'] = df['값'].apply(_parse)

    db_years  = sorted(df['연도'].unique())
    past_years = [y for y in db_years if y < year]
    prev_yr, prev_mo = _prev_month(year, month)

    items_in_db = list(dict.fromkeys(df['구분1'].tolist()))
    items = [it for it in _공정별_ITEM_ORDER if it in set(items_in_db)]
    items += [it for it in items_in_db if it not in set(_공정별_ITEM_ORDER)]

    def _q(g1, g2, yr, mo):
        return float(df[(df['구분1'] == g1) & (df['구분2'] == g2) & (df['연도'] == yr) & (df['월'] == mo)]['_v'].sum())

    def _yr_n(yr):
        return max(1, int(df[(df['연도'] == yr) & (df['구분2'] == '처리량')]['월'].nunique()))

    def _ytd_n(yr, mo):
        return max(1, int(df[(df['연도'] == yr) & (df['월'] <= mo) & (df['구분2'] == '처리량')]['월'].nunique()))

    def _yr_q_avg(g1, yr):
        return sum(_q(g1, '처리량', yr, m) for m in range(1, 13)) / _yr_n(yr)

    def _ytd_q_avg(g1, yr, mo):
        return sum(_q(g1, '처리량', yr, m) for m in range(1, mo + 1)) / _ytd_n(yr, mo)

    def _yr_d_avg(g1, yr):
        q_tot = sum(_q(g1, '처리량', yr, m) for m in range(1, 13))
        qd_tot = sum(_q(g1, '처리량', yr, m) * _q(g1, '단가', yr, m) for m in range(1, 13))
        return qd_tot / q_tot if q_tot else 0.0

    def _ytd_d_avg(g1, yr, mo):
        q_tot = sum(_q(g1, '처리량', yr, m) for m in range(1, mo + 1))
        qd_tot = sum(_q(g1, '처리량', yr, m) * _q(g1, '단가', yr, m) for m in range(1, mo + 1))
        return qd_tot / q_tot if q_tot else 0.0

    def _item_q_cols(g1):
        vals = [_yr_q_avg(g1, y) for y in past_years]
        vals.append(_ytd_q_avg(g1, year, month))
        vals.append(_q(g1, '처리량', prev_yr, prev_mo))
        vals.append(_q(g1, '처리량', year, month))
        vals.append(_q(g1, '처리량', year, month) - _q(g1, '처리량', prev_yr, prev_mo))
        return vals

    def _item_d_cols(g1):
        vals = [_yr_d_avg(g1, y) for y in past_years]
        vals.append(_ytd_d_avg(g1, year, month))
        vals.append(_q(g1, '단가', prev_yr, prev_mo))
        vals.append(_q(g1, '단가', year, month))
        vals.append(_q(g1, '단가', year, month) - _q(g1, '단가', prev_yr, prev_mo))
        return vals

    def _tot_q_cols():
        def sums(yr, mo): return sum(_q(it, '처리량', yr, mo) for it in items)
        vals = [sum(_q(it, '처리량', y, m) for it in items for m in range(1, 13)) / _yr_n(y)
                for y in past_years]
        vals.append(sum(_q(it, '처리량', year, m) for it in items for m in range(1, month + 1))
                    / _ytd_n(year, month))
        vals.append(sums(prev_yr, prev_mo))
        vals.append(sums(year, month))
        vals.append(sums(year, month) - sums(prev_yr, prev_mo))
        return vals

    rows = []
    for it in items:
        rows.append(('item', it, _item_q_cols(it), _item_d_cols(it)))
    rows.append(('total', '합계', _tot_q_cols()))

    cy2, prev_yr2 = str(year)[2:], str(prev_yr)[2:]
    col_headers = []
    for y in past_years:
        yy = str(y)[2:]
        col_headers += [f"'{yy}년 처리량", f"'{yy}년 단가"]
    col_headers += [f"'{cy2}년 처리량", f"'{cy2}년 단가"]
    col_headers += [f"'{prev_yr2}.{prev_mo}월 처리량", f"'{prev_yr2}.{prev_mo}월 단가"]
    mo_lbl = f"{month}월" if year == prev_yr else f"'{cy2}.{month}월"
    col_headers += [f"{mo_lbl} 처리량", f"{mo_lbl} 단가"]
    col_headers += ["전월비 처리량", "전월비 단가"]
    return rows, col_headers


def _중국생산실적_공정별_to_html(rows, col_headers):
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    body = ''
    for row in rows:
        kind = row[0]
        if kind == 'item':
            _, label, q_vals, d_vals = row
            cells = f'<td style="{ROW_ITEM}">{label}</td>'
            n = len(q_vals)
            for i, (q, d) in enumerate(zip(q_vals, d_vals)):
                is_last = (i == n - 1)
                q_s = _TD_RED if q < 0 else _TD_NUM
                d_s = _TD_RED if d < 0 else _TD_NUM
                cells += f'<td style="{q_s}">{_fmt(q, decimal=1)}</td>'
                if not is_last and round(d) == 0:
                    cells += f'<td style="{_TD_NUM}">-</td>'
                else:
                    cells += f'<td style="{d_s}">{_fmt(d)}</td>'
        else:  # 'total'
            _, label, q_vals = row
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            for q in q_vals:
                q_s = ROW_HDR_RED if q < 0 else ROW_HDR_NUM
                cells += f'<td style="{q_s}">{_fmt(q, decimal=1)}</td>'
                cells += f'<td style="{ROW_HDR_NUM}"></td>'
        body += f'<tr>{cells}</tr>'
    return _html_table(th_html, body)


# ── 12) 중국 생산실적 - 황삭연마 ─────────────────────────────────────────────

def _build_중국생산실적_황삭연마(year, month):
    df = load_sheet(Sheets.중국생산실적_황삭연마_DB)
    df = _drop_empty(df, '연도', '월')
    df['구분1'] = df['구분1'].astype(str).str.strip()
    df['_v'] = df['값'].apply(_parse)

    db_years = sorted(df['연도'].unique())
    past_years = [y for y in db_years if y < year]
    recent = _recent_months(year, month, n=5)

    def _q(g1, yr, mo):
        return float(df[(df['구분1'] == g1) & (df['연도'] == yr) & (df['월'] == mo)]['_v'].sum())

    def _yr_avg(g1, yr):
        mos = sorted(df[(df['구분1'] == g1) & (df['연도'] == yr)]['월'].unique())
        return sum(_q(g1, yr, m) for m in mos) / len(mos) if mos else 0.0

    def _ytd_avg(g1, yr, mo):
        mos = sorted(df[(df['구분1'] == g1) & (df['연도'] == yr) & (df['월'] <= mo)]['월'].unique())
        return sum(_q(g1, yr, m) for m in mos) / len(mos) if mos else 0.0

    def _period_vals(g1):
        vals = [_yr_avg(g1, y) for y in past_years]
        vals.append(_ytd_avg(g1, year, month))
        for yr_r, mo_r in recent:
            vals.append(_q(g1, yr_r, mo_r))
        return vals

    capa_vals = _period_vals('CAPA')
    prod_vals = _period_vals('생산실적')
    pct_vals = [p / c * 100 if c else 0.0 for c, p in zip(capa_vals, prod_vals)]

    rows = [
        ('item', 'CAPA', capa_vals),
        ('item', '생산실적', prod_vals),
        ('pct', '가동율', pct_vals),
    ]
    col_headers = _build_col_hdrs(past_years + [year], recent, annual_suffix='년 평균')
    return rows, col_headers


def _중국생산실적_황삭연마_to_html(rows, col_headers):
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    body = ''
    for kind, label, vals in rows:
        cells = f'<td style="{ROW_ITEM}">{label}</td>'
        for v in vals:
            txt = f'{round(v)}%' if kind == 'pct' else _fmt(v, decimal=1)
            s = _TD_RED if v < 0 else _TD_NUM
            cells += f'<td style="{s}">{txt}</td>'
        body += f'<tr>{cells}</tr>'
    return _html_table(th_html, body)


# ── 13) 중국 인원 현황 ────────────────────────────────────────────────────────

def _build_중국인원현황(year, month):
    df = load_sheet(Sheets.중국인력현황_DB)
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    df['구분2'] = df['구분2'].fillna('').astype(str).str.strip()

    vm = {}
    for _, row in df.iterrows():
        key = (str(row['구분1']).strip(), str(row['구분2']).strip(), int(row['연도']), int(row['월']))
        vm[key] = float(row['값'])

    years = sorted(df['연도'].unique().tolist())
    자사계_subs = ['사무직', '기능직']

    def get(g1, g2, yr, mo):
        return vm.get((g1, g2, yr, mo), 0.0)

    def 자사계_val(yr, mo):
        return sum(get('자사', s, yr, mo) for s in 자사계_subs)

    def 외주계_val(yr, mo):
        return get('외주', '', yr, mo)

    def 전체_val(yr, mo):
        return 자사계_val(yr, mo) + 외주계_val(yr, mo)

    def yr_avg(val_fn, yr):
        mos = range(1, 13) if yr < year else range(1, month)
        vals = [val_fn(yr, mo) for mo in mos]
        cnt = sum(1 for v in vals if v != 0.0)
        return sum(vals) / cnt if cnt else 0.0

    recent = _recent_months(year, month, 5)
    col_keys = [(yr, 'avg') for yr in years] + list(recent)

    def get_cell(val_fn, key):
        if key[1] == 'avg':
            return yr_avg(val_fn, key[0])
        return val_fn(key[0], key[1])

    col_headers = [f"'{str(yr)[2:]}년 연평균" for yr in years]
    last_yr = None
    for yr, mo in recent:
        if yr != last_yr:
            col_headers.append(f"'{str(yr)[2:]}.{mo}월")
            last_yr = yr
        else:
            col_headers.append(f"{mo}월")

    rows = []
    for sub in 자사계_subs:
        def val_fn(yr, mo, s=sub):
            return get('자사', s, yr, mo)
        rows.append(('child', sub, [get_cell(val_fn, ck) for ck in col_keys]))

    rows.append(('subtotal', '자사계', [get_cell(자사계_val, ck) for ck in col_keys]))
    rows.append(('standalone', '외주계', [get_cell(외주계_val, ck) for ck in col_keys]))
    rows.append(('total', '전체', [get_cell(전체_val, ck) for ck in col_keys]))

    return rows, col_headers


def _중국인원현황_to_html(rows, col_headers):
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    body_html = ''
    child_idx = 0

    for row_type, label, vals in rows:
        if row_type == 'child':
            bg = ';background:#f9f9fb' if child_idx % 2 == 1 else ''
            child_idx += 1
            cells = f'<td style="{ROW_ITEM + bg}">{_I1}{label}</td>'
            for v in vals:
                cells += f'<td style="{(_TD_RED if v < 0 else _TD_NUM) + bg}">{_fmt(v)}</td>'
        elif row_type in ('subtotal', 'standalone'):
            child_idx = 0
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_HDR_NUM}">{_fmt(v)}</td>'
        elif row_type == 'total':
            cells = f'<td style="{ROW_CAL_LBL}">{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_CAL_NUM}">{_fmt(v)}</td>'
        body_html += f'<tr>{cells}</tr>'

    return _html_table(th_html, body_html)


# ── render_page ───────────────────────────────────────────────────────────

def render_page(app, year_state, month_state):

    def _render_title():
        app.markdown(
            f'<h1 style="color:#404448">{int(year_state.value)}년 {int(month_state.value)}월 해외법인실적</h1>',
            unsafe_allow_html=True,
        )
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["멕시코_SGAM", "중국_기차배건"])

    with tabs[0]:
        def _render_멕시코():
            year, month = int(year_state.value), int(month_state.value)

            # 1) 손익요약
            rows_손익, col_headers = _build_멕시코손익(year, month)
            memo_손익 = _get_memo(Sheets.멕시코손익_메모, year, month)
            col_l, col_r = app.columns([6, 4])
            with col_l:
                app.markdown(
                    _sec_title('1) 손익요약', '[단위: 만개, 백만원]')
                    + _멕시코손익_to_html(rows_손익, col_headers),
                    unsafe_allow_html=True,
                )
            with col_r:
                if memo_손익:
                    app.markdown(_memo_block(memo_손익), unsafe_allow_html=True)

            # 2) 채권채무 현황
            rows_채권채무 = _build_채권채무(year, month)
            memo_채권채무 = _get_memo(Sheets.멕시코원주채권채무_메모, year, month)
            col_l2, col_r2 = app.columns([6, 4])
            with col_l2:
                app.markdown(
                    _sec_title('2) SGAM-원주 간 채권∙채무 현황', '[단위: USD, 백만원]')
                    + _채권채무_to_html(rows_채권채무),
                    unsafe_allow_html=True,
                )
            with col_r2:
                if memo_채권채무:
                    app.markdown(_memo_block(memo_채권채무), unsafe_allow_html=True)
        app.If(lambda: True, _render_멕시코)

    with tabs[1]:
        def _render_중국():
            year, month = int(year_state.value), int(month_state.value)

            # 1) 손익요약
            rows_손익, col_headers_손익 = _build_중국손익(year, month)
            memo_손익 = _get_memo(Sheets.중국손익_메모, year, month)
            col_l, col_r = app.columns([6, 4])
            with col_l:
                app.markdown(
                    _sec_title('1) 손익요약', '[단위: 만개, 백만원]')
                    + _중국손익_to_html(rows_손익, col_headers_손익),
                    unsafe_allow_html=True,
                )
            with col_r:
                if memo_손익:
                    app.markdown(_memo_block(memo_손익), unsafe_allow_html=True)

            # 2) 재무상태표
            rows_재무, col_headers_재무 = _build_중국재무상태표(year, month)
            memo_재무 = _get_memo(Sheets.중국재무상태표_메모, year, month)
            col_l2, col_r2 = app.columns([6, 4])
            with col_l2:
                app.markdown(
                    _sec_title('2) 재무상태표', '[단위: 백만원, %]')
                    + _중국재무상태표_to_html(rows_재무, col_headers_재무),
                    unsafe_allow_html=True,
                )
            with col_r2:
                if memo_재무:
                    app.markdown(_memo_block(memo_재무), unsafe_allow_html=True)

            # 3) 판매구성 - 제품별 판매 현황
            rows_판매, col_headers_판매 = _build_중국판매구성_제품별(year, month)
            memo_판매 = _get_memo(Sheets.중국판매구성_제품벌_메모, year, month)
            col_l3, col_r3 = app.columns([6, 4])
            with col_l3:
                app.markdown(
                    _sec_title('3) 판매구성 - 제품별 판매 현황', '[단위: 만개, 백만원, 원/개]')
                    + _중국판매구성_제품별_to_html(rows_판매, col_headers_판매),
                    unsafe_allow_html=True,
                )
            with col_r3:
                if memo_판매:
                    app.markdown(_memo_block(memo_판매), unsafe_allow_html=True)

            # 4) 판매구성 - 거래처별 판매 현황
            rows_거래처, col_headers_거래처 = _build_중국판매구성_거래처별(year, month)
            memo_거래처 = _get_memo(Sheets.중국판매구성_거래처벌_메모, year, month)
            col_l4, col_r4 = app.columns([6, 4])
            with col_l4:
                app.markdown(
                    _sec_title('4) 판매구성 - 거래처별 판매 현황', '[단위: 만개, %]')
                    + _중국판매구성_거래처별_to_html(rows_거래처, col_headers_거래처),
                    unsafe_allow_html=True,
                )
            with col_r4:
                if memo_거래처:
                    app.markdown(_memo_block(memo_거래처), unsafe_allow_html=True)

            # 5) 판매구성 - 열후 제품 판매 비중
            rows_열후, col_hdrs_열후, chart_x, chart_data, chart_계, chart_비중 = \
                _build_중국판매구성_열후비중(year, month)
            memo_열후 = _get_memo(Sheets.중국판매구성_열후벌_메모, year, month)
            col_l5, col_r5 = app.columns([6, 4])
            with col_l5:
                app.markdown(
                    _sec_title('5) 판매구성 - 열후 제품 판매 비중', '[단위: 만개, %]')
                    + _중국판매구성_열후비중_to_html(rows_열후, col_hdrs_열후),
                    unsafe_allow_html=True,
                )
                app.plotly_chart(
                    _build_중국열후비중_chart(chart_x, chart_data, chart_계, chart_비중),
                    use_container_width=True,
                )
            with col_r5:
                if memo_열후:
                    app.markdown(_memo_block(memo_열후), unsafe_allow_html=True)

            # 7) 원재료 입고 (실적, 단가)  ← 6)은 DB 미구현
            rows_재료, col_headers_재료 = _build_중국원재료입고(year, month)
            memo_재료 = _get_memo(Sheets.중국원재료입고_메모, year, month)
            col_l7, col_r7 = app.columns([6, 4])
            with col_l7:
                app.markdown(
                    _sec_title('7) 원재료 입고 (실적, 단가)', '[단위: 톤, 백만원]')
                    + _중국원재료입고_to_html(rows_재료, col_headers_재료),
                    unsafe_allow_html=True,
                )
            with col_r7:
                if memo_재료:
                    app.markdown(_memo_block(memo_재료), unsafe_allow_html=True)

            # 8) 제조 가공비
            rows_가공비, col_headers_가공비 = _build_중국제조가공비(year, month)
            memo_가공비 = _get_memo(Sheets.중국제조가공비_메모, year, month)
            col_l8, col_r8 = app.columns([6, 4])
            with col_l8:
                app.markdown(
                    _sec_title('8) 제조 가공비', '[단위: 백만원]')
                    + _중국제조가공비_to_html(rows_가공비, col_headers_가공비),
                    unsafe_allow_html=True,
                )
            with col_r8:
                if memo_가공비:
                    app.markdown(_memo_block(memo_가공비), unsafe_allow_html=True)

            # 9) 판매비와 관리비
            rows_판관비, col_headers_판관비 = _build_중국판관비(year, month)
            memo_판관비 = _get_memo(Sheets.중국판관비_메모, year, month)
            col_l9, col_r9 = app.columns([6, 4])
            with col_l9:
                app.markdown(
                    _sec_title('9) 판매비와 관리비', '[단위: 만개, 백만원]')
                    + _중국판관비_to_html(rows_판관비, col_headers_판관비),
                    unsafe_allow_html=True,
                )
            with col_r9:
                if memo_판관비:
                    app.markdown(_memo_block(memo_판관비), unsafe_allow_html=True)

            # 10) 재고자산 현황
            rows_재고, col_spec_재고 = _build_중국재고자산(year, month)
            memo_재고 = _get_memo(Sheets.중국재고자산_메모, year, month)
            col_l10, col_r10 = app.columns([6, 4])
            with col_l10:
                app.markdown(
                    _sec_title('10) 재고자산 현황', '[단위: 만개, 톤, 백만원]')
                    + _중국재고자산_to_html(rows_재고, col_spec_재고),
                    unsafe_allow_html=True,
                )
            with col_r10:
                if memo_재고:
                    app.markdown(_memo_block(memo_재고), unsafe_allow_html=True)

            # 11) 생산실적 공정별 처리량
            rows_공정별, col_headers_공정별 = _build_중국생산실적_공정별(year, month)
            memo_공정별 = _get_memo(Sheets.중국생산실적_공정별_메모, year, month)
            col_l11, col_r11 = app.columns([6, 4])
            with col_l11:
                app.markdown(
                    _sec_title('11) 생산실적 - 공정별 처리량', '[단위: 만개, 원/개]')
                    + _중국생산실적_공정별_to_html(rows_공정별, col_headers_공정별),
                    unsafe_allow_html=True,
                )
            with col_r11:
                if memo_공정별:
                    app.markdown(_memo_block(memo_공정별), unsafe_allow_html=True)

            # 12) 생산실적 - 황삭연마
            rows_황삭연마, col_headers_황삭연마 = _build_중국생산실적_황삭연마(year, month)
            memo_황삭연마 = _get_memo(Sheets.중국생산실적_황삭연마_메모, year, month)
            col_l12, col_r12 = app.columns([6, 4])
            with col_l12:
                app.markdown(
                    _sec_title('12) 생산실적 - 황삭연마', '[단위: 만개, %]')
                    + _중국생산실적_황삭연마_to_html(rows_황삭연마, col_headers_황삭연마),
                    unsafe_allow_html=True,
                )
            with col_r12:
                if memo_황삭연마:
                    app.markdown(_memo_block(memo_황삭연마), unsafe_allow_html=True)

            # 13) 인원 현황
            rows_인원, col_headers_인원 = _build_중국인원현황(year, month)
            memo_인원 = _get_memo(Sheets.중국인력현황_메모, year, month)
            col_l13, col_r13 = app.columns([6, 4])
            with col_l13:
                app.markdown(
                    _sec_title('13) 인원 현황', '[단위: 명]')
                    + _중국인원현황_to_html(rows_인원, col_headers_인원),
                    unsafe_allow_html=True,
                )
            with col_r13:
                if memo_인원:
                    app.markdown(_memo_block(memo_인원), unsafe_allow_html=True)
        app.If(lambda: True, _render_중국)
