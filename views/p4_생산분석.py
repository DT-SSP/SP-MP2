import datetime
import pandas as pd
from data.loader import load_sheet
from data.config import Sheets
from views.common import (
    parse as _parse, fmt as _fmt,
    drop_empty as _drop_empty,
    prev_month as _prev,
    recent_months as _recent_months, build_col_hdrs as _build_col_hdrs,
    TH as _TH, TD_NUM as _TD_NUM, TD_LBL as _TD_LBL, TD_RED as _TD_RED,
    ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED, ROW_ITEM,
    html_table as _html_table, layout64 as _layout64,
)


def _get_연도_목록():
    df = load_sheet(Sheets.사내불량발생현황_DB)
    if '연도' not in df.columns:
        today = datetime.date.today()
        return list(range(today.year - 2, today.year + 1))
    return sorted(pd.to_numeric(df['연도'], errors='coerce').dropna().astype(int).unique().tolist())


def _get_memo(sheet_info, year, month):
    df = load_sheet(sheet_info)
    df['연도'] = df['연도'].astype(str).str.strip()
    df['월']   = df['월'].astype(str).str.strip()
    row = df[(df['연도'] == str(year)) & (df['월'] == str(month))]
    return str(row.iloc[0]['메모']) if not row.empty else ''


# ── 0) 월평균 생산실적 ────────────────────────────────────────────────────

def _build_생산실적(year, month):
    df = load_sheet(Sheets.월평균생산실적_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    vm = df.set_index(['구분1', '연도', '월'])['값'].to_dict()

    def raw(g1, yr, mo):
        return vm.get((g1, yr, mo), 0.0)

    def yr_avg(g1, yr):
        vals = [raw(g1, yr, m) for m in range(1, 13) if (g1, yr, m) in vm]
        return sum(vals) / len(vals) if vals else 0.0

    연도_in_db = sorted(df['연도'].unique().tolist())
    recent = _recent_months(year, month)
    col_hdrs = _build_col_hdrs(연도_in_db, recent, annual_suffix='년 평균')

    prev_yr, prev_mo = _prev(year, month)
    items = ['열전', '열후', '피니언']

    rows = []
    합계_main = [0.0] * (len(연도_in_db) + len(recent))
    합계_당월 = 0.0
    합계_전월 = 0.0

    for g1 in items:
        main = [yr_avg(g1, yr) for yr in 연도_in_db] + \
               [raw(g1, yr_c, mo_c) for yr_c, mo_c in recent]
        당월 = raw(g1, year, month)
        전월 = raw(g1, prev_yr, prev_mo)
        mom = 당월 - 전월
        pct = mom / 전월 * 100 if 전월 else 0.0
        rows.append(('item', g1, main, mom, pct))
        합계_main = [a + b for a, b in zip(합계_main, main)]
        합계_당월 += 당월
        합계_전월 += 전월

    mom_합 = 합계_당월 - 합계_전월
    pct_합 = mom_합 / 합계_전월 * 100 if 합계_전월 else 0.0
    rows.append(('total', '합계', 합계_main, mom_합, pct_합))

    return rows, col_hdrs


def _생산실적_to_html(rows, col_hdrs):
    all_hdrs = ['구분'] + col_hdrs + ['전월대비', '%']
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in all_hdrs)
    body = ''
    for kind, label, vals, mom, pct in rows:
        lbl_s = ROW_HDR_LBL if kind == 'total' else ROW_ITEM
        num_s = ROW_HDR_NUM if kind == 'total' else _TD_NUM
        red_s = ROW_HDR_RED if kind == 'total' else _TD_RED
        cells = f'<td style="{lbl_s}">{label}</td>'
        cells += ''.join(f'<td style="{num_s}">{_fmt(v)}</td>' for v in vals)
        cells += f'<td style="{red_s if mom < 0 else num_s}">{_fmt(mom, decimal=1)}</td>'
        cells += f'<td style="{red_s if pct < 0 else num_s}">{_fmt(abs(pct), decimal=1)}%</td>'
        body += f'<tr>{cells}</tr>'
    return _html_table(f'<tr>{th}</tr>', body)


# ── 1) 사내 불량 발생 현황 ────────────────────────────────────────────────

def _build_사내불량(year, month):
    df = load_sheet(Sheets.사내불량발생현황_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    vm = df.set_index(['구분1', '구분2', '연도', '월'])['값'].to_dict()

    def raw(g1, g2, yr, mo):
        return vm.get((g1, g2, yr, mo), 0.0)

    # sum / count of DB entries (includes 0-value months stored as "-")
    def yr_avg(g1, g2, yr):
        vals = [raw(g1, g2, yr, m) for m in range(1, 13) if (g1, g2, yr, m) in vm]
        return sum(vals) / len(vals) if vals else 0.0

    연도_in_db = sorted(df['연도'].unique().tolist())
    recent = _recent_months(year, month)
    col_hdrs = _build_col_hdrs(연도_in_db, recent, annual_suffix='년 평균')

    def item_vals(g1, g2):
        return [yr_avg(g1, g2, yr) for yr in 연도_in_db] + \
               [raw(g1, g2, yr_c, mo_c) for yr_c, mo_c in recent]

    def ppm_vals(g1):
        return [yr_avg(g1, '불량률(PPM)', yr) for yr in 연도_in_db] + \
               [raw(g1, '불량률(PPM)', yr_c, mo_c) for yr_c, mo_c in recent]

    열전   = item_vals('랙바', '열전')
    열후   = item_vals('랙바', '열후')
    소계_r = [a + b for a, b in zip(열전, 열후)]

    선삭   = item_vals('피니언', '선삭')
    열처리 = item_vals('피니언', '열처리')
    소계_p = [a + b for a, b in zip(선삭, 열처리)]

    합계   = [a + b for a, b in zip(소계_r, 소계_p)]

    rows = [
        ('item',  '열전',         열전),
        ('item',  '열후',         열후),
        ('total', '랙바 소계',    소계_r),
        ('ppm',   '불량률(PPM)', ppm_vals('랙바')),
        ('item',  '선삭',         선삭),
        ('item',  '열처리',       열처리),
        ('total', '피니언 소계',  소계_p),
        ('ppm',   '불량률(PPM)', ppm_vals('피니언')),
        ('total', '합계',         합계),
        ('ppm',   '불량률(PPM)', ppm_vals('합계')),
    ]
    return rows, col_hdrs


# ── 2) 사외 불량 발생 현황 ────────────────────────────────────────────────

def _build_사외불량(year, month):
    df = load_sheet(Sheets.사외불량발생현황_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    vm = df.set_index(['구분1', '연도', '월'])['값'].to_dict()

    def raw(g1, yr, mo):
        return vm.get((g1, yr, mo), 0.0)

    def yr_avg(g1, yr):
        vals = [raw(g1, yr, m) for m in range(1, 13) if (g1, yr, m) in vm]
        return sum(vals) / len(vals) if vals else 0.0

    연도_in_db = sorted(df['연도'].unique().tolist())
    recent = _recent_months(year, month)
    col_hdrs = _build_col_hdrs(연도_in_db, recent, annual_suffix='.평균')

    rows = [
        ('item', '사외불량수량',
         [yr_avg('사외불량수량', yr) for yr in 연도_in_db] +
         [raw('사외불량수량', yr_c, mo_c) for yr_c, mo_c in recent]),
        ('ppm',  '불량률(PPM)',
         [yr_avg('불량률(PPM)', yr) for yr in 연도_in_db] +
         [raw('불량률(PPM)', yr_c, mo_c) for yr_c, mo_c in recent]),
    ]
    return rows, col_hdrs


# ── HTML ─────────────────────────────────────────────────────────────────

def _불량_to_html(rows, col_hdrs):
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in ['구분'] + col_hdrs)
    body = ''
    for kind, label, vals in rows:
        if kind == 'item':
            cells = f'<td style="{ROW_ITEM}">{label}</td>'
            cells += ''.join(f'<td style="{_TD_NUM}">{_fmt(v)}</td>' for v in vals)
        elif kind == 'total':
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            cells += ''.join(f'<td style="{ROW_HDR_NUM}">{_fmt(v)}</td>' for v in vals)
        elif kind == 'ppm':
            cells = f'<td style="{_TD_LBL}">{label}</td>'
            cells += ''.join(f'<td style="{_TD_NUM}">{_fmt(v)}</td>' for v in vals)
        body += f'<tr>{cells}</tr>'
    return _html_table(f'<tr>{th}</tr>', body)


# ── render_page ───────────────────────────────────────────────────────────

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
        app.title(f"{int(year_state.value)}년 {int(month_state.value)}월 생산분석")
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["생산실적", "불량 발생내역"])

    with tabs[0]:
        def _render_생산실적():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_hdrs = _build_생산실적(year, month)
            memo = _get_memo(Sheets.월평균생산실적_메모, year, month)
            app.markdown(
                _layout64('1) 월평균 생산실적',
                          _생산실적_to_html(rows, col_hdrs),
                          memo,
                          unit='[단위: 만개]'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_생산실적)

    with tabs[1]:
        def _render_불량():
            year, month = int(year_state.value), int(month_state.value)
            rows1, col_hdrs1 = _build_사내불량(year, month)
            memo1 = _get_memo(Sheets.사내불량발생현황_메모, year, month)
            rows2, col_hdrs2 = _build_사외불량(year, month)
            memo2 = _get_memo(Sheets.사외불량발생현황_메모, year, month)

            app.markdown(
                _layout64('1) 사내 불량 발생 현황',
                          _불량_to_html(rows1, col_hdrs1),
                          memo1,
                          unit='[단위: 개]'),
                unsafe_allow_html=True,
            )
            app.markdown(
                _layout64('2) 사외 불량 발생 현황',
                          _불량_to_html(rows2, col_hdrs2),
                          memo2,
                          unit='[단위: 개]'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_불량)
