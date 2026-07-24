import datetime
import base64
import plotly.graph_objects as go
import pandas as pd
from data.loader import load_sheet
from data.config import Sheets
from views.common import (
    parse as _parse, fmt as _fmt,
    drop_empty as _drop_empty,
    prev_month as _prev,
    recent_months as _recent_months,
    TH as _TH, TD_NUM as _TD_NUM, TD_RED as _TD_RED,
    C_NAVY, C_ORANGE, C_RED, C_CHART_SEC, C_CHART_GRID,
    ROW_GRP, ROW_ITEM, ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED,
    html_table as _html_table, layout64 as _layout64,
)

# ── 공통 상수 ─────────────────────────────────────────────────────────────

_N_RECENT = 3
_SUM_KW   = ('금액', '중량')



# ══════════════════════════════════════════════════════════════════════════
# ── 탭 1: 재고자산 현황 ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _get_연도_목록():
    df = load_sheet(Sheets.재고현황_DB)
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


def _fmt_pct(v):
    v = round(v)
    return f'-{abs(v)}%' if v < 0 else f'{v}%'

def _fig_to_iframe(fig):
    """Plotly figure → base64 iframe HTML (간격 없는 인라인 렌더링)."""
    h = fig.layout.height or 260
    html = fig.to_html(include_plotlyjs='cdn', full_html=True,
                       config={'displayModeBar': False, 'responsive': True})
    # iframe 내부 body 스크롤 제거
    html = html.replace('</head>',
                        '<style>html,body{margin:0;padding:0;overflow:hidden}</style></head>', 1)
    
    import base64
    b64 = base64.b64encode(html.encode()).decode()
    return (f'<iframe src="data:text/html;base64,{b64}" '
            f'height="{h}" width="100%" scrolling="no" '
            f'style="border:none;display:block;margin:0;padding:0"></iframe>')

def _build_재고현황(year, month):
    df = load_sheet(Sheets.재고현황_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값']   = df['값'].apply(_parse)
    df['구분1'] = df['구분1'].astype(str).str.strip()
    df['구분2'] = df['구분2'].astype(str).str.strip()

    # ⭕ 1. .round()를 제거하거나 .round(1)로 변경하여 소수점 1자리 유지
    df.loc[df['구분2'].str.contains('금액'), '값'] = (df['값'] / 1_000_000.0).round(1)
    df.loc[df['구분2'].str.contains('중량'), '값'] = (df['값'] / 1_000.0).round(1)

    vm = df.set_index(['구분1', '구분2', '연도', '월'])['값'].to_dict()

    연도_in_db  = sorted(df['연도'].unique().tolist())
    recent_curr = _recent_months(year, month, n=_N_RECENT)
    prev_year_end = max((yr for yr in 연도_in_db if yr < year), default=None)
    past_years    = ([prev_year_end]
                     if prev_year_end is not None and (prev_year_end, 12) not in recent_curr
                     else [])
    prev_yr, prev_mo = _prev(year, month)

    groups_order = list(dict.fromkeys(df['구분1'].tolist()))
    all_keys = df[['구분1', '구분2']].drop_duplicates().apply(tuple, axis=1).tolist()

    def raw(g1, g2, yr, mo):
        return vm.get((g1, g2, yr, mo), 0.0)

    def pct_chg(curr, prev):
        return (curr - prev) / abs(prev) * 100 if prev else 0.0

    # ⭕ 2. 금액, 중량 상관없이 무조건 소수점 1자리(1)를 사용하도록 수정
    def decimal_for(g2):
        return 1  # 무조건 소수점 첫째자리까지 표시

    def make_vals(g1, g2):
        v  = [raw(g1, g2, yr, 12) for yr in past_years]
        v += [raw(g1, g2, yr_c, mo_c) for yr_c, mo_c in recent_curr]
        curr_v = raw(g1, g2, year, month)
        prev_v = raw(g1, g2, prev_yr, prev_mo)
        v += [curr_v - prev_v, pct_chg(curr_v, prev_v)]
        return v

    group_rows = []
    for g1 in groups_order:
        metrics = list(dict.fromkeys(df[df['구분1'] == g1]['구분2'].tolist()))
        group_rows.append((g1, [(g2, make_vals(g1, g2), decimal_for(g2)) for g2 in metrics]))

    g2_vals    = df['구분2'].unique().tolist()
    active_kws = [kw for kw in _SUM_KW if any(kw in g2 for g2 in g2_vals)]

    def sum_kw(kw, yr, mo):
        return sum(raw(g1, g2, yr, mo) for g1, g2 in all_keys if kw in g2)

    def make_sum_vals(kw):
        v  = [sum_kw(kw, yr, 12) for yr in past_years]
        v += [sum_kw(kw, yr_c, mo_c) for yr_c, mo_c in recent_curr]
        curr_v = sum_kw(kw, year, month)
        prev_v = sum_kw(kw, prev_yr, prev_mo)
        v += [curr_v - prev_v, pct_chg(curr_v, prev_v)]
        return v

    sum_rows = [
        (kw if i == 0 else f'{kw} 계', make_sum_vals(kw), decimal_for(kw))
        for i, kw in enumerate(active_kws)
    ]

    col_spec = {'past_years': past_years, 'recent_curr': recent_curr, 'curr_year': year}
    return group_rows, sum_rows, col_spec

def _재고현황_to_html(group_rows, sum_rows, col_spec):
    past_years  = col_spec['past_years']
    recent_curr = col_spec['recent_curr']

    n_cols = len(past_years) + len(recent_curr) + 3  # 구분 + 연도/월 + 증감 + 증감률

    th = f'<th style="{_TH}">구분</th>'
    for yr in past_years:
        th += f'<th style="{_TH}">\'{str(yr)[2:]}년말</th>'
    last_yr = None
    for yr_c, mo_c in recent_curr:
        label = f"'{str(yr_c)[2:]}년 {mo_c}월말"
        th += f'<th style="{_TH}">{label}</th>'
        last_yr = yr_c
    th += f'<th style="{_TH}">전월대비<br>증감</th>'
    th += f'<th style="{_TH}">전월대비<br>증감률</th>'
    thead = f'<tr>{th}</tr>'

    def val_cells(vals, decimal, num_s=_TD_NUM, red_s=_TD_RED):
        cells = ''
        n = len(vals)
        for i, v in enumerate(vals):
            if i == n - 1:
                s = red_s if v < 0 else num_s
                cells += f'<td style="{s}">{_fmt_pct(v)}</td>'
            elif i == n - 2:
                s = red_s if v < 0 else num_s
                cells += f'<td style="{s}">{_fmt(v, decimal=decimal)}</td>'
            else:
                cells += f'<td style="{num_s}">{_fmt(v, decimal=decimal)}</td>'
        return cells

    body = ''
    for g1, metrics in group_rows:
        body += f'<tr><td colspan="{n_cols}" style="{ROW_GRP}">{g1}</td></tr>'
        for g2, vals, decimal in metrics:
            cells  = f'<td style="{ROW_ITEM}">{g2}</td>'
            cells += val_cells(vals, decimal)
            body  += f'<tr>{cells}</tr>'

    body += f'<tr><td colspan="{n_cols}" style="{ROW_HDR_LBL}">재고자산 계</td></tr>'
    for label, vals, decimal in sum_rows:
        cells  = f'<td style="{ROW_HDR_LBL}">{label}</td>'
        cells += val_cells(vals, decimal, num_s=ROW_HDR_NUM, red_s=ROW_HDR_RED)
        body  += f'<tr>{cells}</tr>'

    return _html_table(thead, body)


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 2: 연령별 재고현황 ──────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _sec_title(title, unit):
    return (
        '<div style="display:flex;justify-content:space-between;'
        'align-items:baseline;margin:0 0 4px 0">'
        f'<h3 style="margin:0;font-size:1.1em;font-weight:600">{title}</h3>'
        f'<span style="font-size:0.8em;color:gray">{unit}</span>'
        '</div>'
    )


def _memo_html(memo):
    if not memo:
        return ''
    return f'<p style="margin:0;font-size:0.9em;line-height:1.6;white-space:pre-wrap">{memo}</p>'


def _fmt_연령_pct(v, decimal=0):
    if decimal:
        v_r = round(v, decimal)
        return f'-{abs(v_r):.{decimal}f}%' if v_r < 0 else f'{v_r:.{decimal}f}%'
    v_r = round(v)
    return f'-{abs(v_r)}%' if v_r < 0 else f'{v_r}%'


def _load_연령별(year, month):
    df = load_sheet(Sheets.연령별재고현황_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    df['값'] = (df['값'] / 1_000).round()

    for c in ['구분1', '구분2']:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    # 과거 2년(2년 전말, 1년 전말)
    past_years = [year - 2, year - 1]
    
    # 최근 3개월(2개월 전, 1개월 전, 당월)
    recent_curr = _recent_months(year, month, n=_N_RECENT)
    prev_yr, prev_mo = _prev(year, month)

    col_spec = {
        'past_years':  past_years,
        'recent_curr': recent_curr,
        'curr': (year, month),
        'prev': (prev_yr, prev_mo),
    }
    return df, col_spec

def _col_labels(col_spec):
    # ⭕ 요청하신 컬럼명 포맷 ('23년말, '25년 5월 형식)
    labels = [f"'{str(yr)[2:]}년말" for yr in col_spec['past_years']]
    for yr_c, mo_c in col_spec['recent_curr']:
        labels.append(f"'{str(yr_c)[2:]}년 {mo_c}월")
    return labels


# ── 원재료 데이터 빌더 ─────────────────────────────────────────────────────

def _build_원재료_rows(df, col_spec):
    past_years  = col_spec['past_years']
    recent_curr = col_spec['recent_curr']
    curr_yr, curr_mo = col_spec['curr']
    prev_yr, prev_mo = col_spec['prev']

    df1 = df[df['구분1'] == '원재료'].copy()
    agg = df1.groupby(['구분2', '연도', '월'])['값'].sum().to_dict()

    def v(g2, yr, mo): return agg.get((g2, yr, mo), 0.0)
    def v_정상(yr, mo): return v('3개월 이하', yr, mo) + v('3개월 초과', yr, mo)
    def v_장기(yr, mo): return v('6개월 초과', yr, mo) + v('1년 초과', yr, mo)
    def v_총계(yr, mo): return v_정상(yr, mo) + v_장기(yr, mo)

    def cvs(fn, *keys):
        return ([fn(*keys, yr, 12) for yr in past_years]
                + [fn(*keys, yr_c, mo_c) for yr_c, mo_c in recent_curr])

    def mom(fn, *keys):
        return fn(*keys, curr_yr, curr_mo) - fn(*keys, prev_yr, prev_mo)

    def pct_col(장기_fn, total_fn):
        def p(yr, mo):
            t = total_fn(yr, mo)
            return 장기_fn(yr, mo) / t * 100 if t else 0.0
        p_vals = [p(yr, 12) for yr in past_years] + [p(yr_c, mo_c) for yr_c, mo_c in recent_curr]
        p_mom  = p(curr_yr, curr_mo) - p(prev_yr, prev_mo)
        return p_vals, p_mom

    def detail_row(g2):
        sub_rows = [('ton', cvs(v, g2), mom(v, g2), 0, False)]
        return {'label': g2, 'kind': 'detail', 'sub_rows': sub_rows}

    def subtotal_row(label, fn, with_pct=False):
        sub_rows = [('ton', cvs(fn), mom(fn), 0, False)]
        if with_pct:
            p_vals, p_mom = pct_col(fn, v_총계)
            sub_rows.append(('(%)', p_vals, p_mom, None, True))
        return {'label': label, 'kind': 'subtotal', 'sub_rows': sub_rows}

    rows = []
    rows.append(detail_row('3개월 이하'))
    rows.append(detail_row('3개월 초과'))
    rows.append(subtotal_row('정상재고', v_정상))
    
    rows.append(detail_row('6개월 초과'))
    rows.append(detail_row('1년 초과'))
    rows.append(subtotal_row('장기재고', v_장기, with_pct=True))

    rows.append({'label': '원재료 합계', 'kind': 'total', 'sub_rows': [('ton', cvs(v_총계), mom(v_총계), 0, False)]})
    return rows

def _원재료_to_html(rows, col_spec):
    col_lbls = _col_labels(col_spec)
    n_cols   = len(col_lbls) + 2  # 구분 + 날짜 컬럼들 + 전월대비

    th = f'<th style="{_TH}">원재료</th>'
    for lbl in col_lbls:
        th += f'<th style="{_TH}">{lbl}</th>'
    th += f'<th style="{_TH}">전월대비</th>'

    body = ''
    for row in rows:
        kind     = row['kind']
        sub_rows = row['sub_rows']
        num_s    = _TD_NUM if kind == 'detail' else ROW_HDR_NUM
        red_s    = _TD_RED if kind == 'detail' else ROW_HDR_RED
        hdr_s    = ROW_HDR_LBL if kind == 'total' else ROW_GRP

        body += f'<tr><td colspan="{n_cols}" style="{hdr_s}">{row["label"]}</td></tr>'

        for unit, vals, mom_v, dec, is_pct in sub_rows:
            cells = f'<td style="{ROW_ITEM}">{unit}</td>'
            if is_pct:
                for v in vals:
                    cells += f'<td style="{num_s}">{_fmt_연령_pct(v)}</td>'
                cells += f'<td style="{num_s}">{_fmt_연령_pct(mom_v, decimal=1)}</td>'
            else:
                for v in vals:
                    cells += f'<td style="{num_s}">{_fmt(v, decimal=dec)}</td>'
                m_s = red_s if mom_v < 0 else num_s
                cells += f'<td style="{m_s}">{_fmt(mom_v, decimal=dec)}</td>'
            body += f'<tr>{cells}</tr>'

    return _html_table(f'<tr>{th}</tr>', body)


# ── 재공품/제품 데이터 빌더 ────────────────────────────────────────────────

def _build_단품_rows(g1, df, col_spec):
    past_years  = col_spec['past_years']
    recent_curr = col_spec['recent_curr']
    curr_yr, curr_mo = col_spec['curr']
    prev_yr, prev_mo = col_spec['prev']

    df1  = df[df['구분1'] == g1].copy()
    agg = df1.groupby(['구분2', '연도', '월'])['값'].sum().to_dict()

    def v(g2, yr, mo): return agg.get((g2, yr, mo), 0.0)
    def v_정상(yr, mo): return v('3개월 이하', yr, mo) + v('3개월 초과', yr, mo)
    def v_장기(yr, mo): return v('6개월 초과', yr, mo) + v('1년 초과', yr, mo)
    
    # ⭕ 매입매출 데이터 추출 및 전체 합계 산식 변경
    def v_매입(yr, mo): return sum(v(g2, yr, mo) for g2 in df1['구분2'].unique() if '매입매출' in str(g2))
    def v_총계(yr, mo): return sum(v(g2, yr, mo) for g2 in df1['구분2'].unique())

    def cvs(fn, *keys):
        return ([fn(*keys, yr, 12) for yr in past_years]
                + [fn(*keys, yr_c, mo_c) for yr_c, mo_c in recent_curr])

    def mom(fn, *keys):
        return fn(*keys, curr_yr, curr_mo) - fn(*keys, prev_yr, prev_mo)

    def pct_v(yr, mo):
        t = v_총계(yr, mo)
        return v_장기(yr, mo) / t * 100 if t else 0.0

    pct_vals = [pct_v(yr, 12) for yr in past_years] + [pct_v(yr_c, mo_c) for yr_c, mo_c in recent_curr]
    pct_mom  = pct_v(curr_yr, curr_mo) - pct_v(prev_yr, prev_mo)

    dec = 1
    rows = []
    
    # 1. 정상재고 파트
    for g2 in ['3개월 이하', '3개월 초과']:
        rows.append({'label': g2, 'kind': 'detail', 'vals': cvs(v, g2), 'mom': mom(v, g2), 'dec': dec})
    rows.append({'label': '정상재고', 'kind': 'subtotal', 'vals': cvs(v_정상), 'mom': mom(v_정상), 'dec': dec})
    
    # ⭕ 2. 매입매출 행 추가 (정상재와 장기재고 사이)
    rows.append({'label': '매입매출', 'kind': 'detail', 'vals': cvs(v_매입), 'mom': mom(v_매입), 'dec': dec})
    
    # 3. 장기재고 파트
    for g2 in ['6개월 초과', '1년 초과']:
        rows.append({'label': g2, 'kind': 'detail', 'vals': cvs(v, g2), 'mom': mom(v, g2), 'dec': dec})
    rows.append({'label': '장기재고', 'kind': '장기소계', 'vals': cvs(v_장기), 'mom': mom(v_장기), 'dec': dec,
                 'pct_vals': pct_vals, 'pct_mom': pct_mom})
    
    # 4. 총계
    rows.append({'label': f'{g1} 계', 'kind': 'total', 'vals': cvs(v_총계), 'mom': mom(v_총계), 'dec': dec})
    return rows

def _단품_to_html(rows, col_spec, g1_label):
    th = f'<th style="{_TH}">{g1_label}</th>'
    for lbl in _col_labels(col_spec):
        th += f'<th style="{_TH}">{lbl}</th>'
    th += f'<th style="{_TH}">전월대비</th>'

    body = ''
    for row in rows:
        kind  = row['kind']
        vals  = row['vals']
        mom_v = row['mom']
        dec   = row['dec']

        if kind == 'detail':
            lbl_s, num_s, red_s = ROW_ITEM, _TD_NUM, _TD_RED
        else:
            lbl_s, num_s, red_s = ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED

        cells  = f'<td style="{lbl_s}">{row["label"]}</td>'
        for v in vals:
            cells += f'<td style="{num_s}">{_fmt(v, decimal=dec)}</td>'
        m_s = red_s if mom_v < 0 else num_s
        cells += f'<td style="{m_s}">{_fmt(mom_v, decimal=dec)}</td>'
        body  += f'<tr>{cells}</tr>'

        if kind == '장기소계':
            cells = f'<td style="{ROW_ITEM}">(%)</td>'
            for v in row['pct_vals']:
                cells += f'<td style="{ROW_HDR_NUM}">{_fmt_연령_pct(v)}</td>'
            cells += f'<td style="{ROW_HDR_NUM}">{_fmt_연령_pct(row["pct_mom"], decimal=1)}</td>'
            body  += f'<tr>{cells}</tr>'

    return _html_table(f'<tr>{th}</tr>', body)

# ── 종합 현황 데이터 빌더 ────────────────────────────────────────────────

def _build_종합_rows(df, col_spec):
    past_years  = col_spec['past_years']
    recent_curr = col_spec['recent_curr']
    curr_yr, curr_mo = col_spec['curr']
    prev_yr, prev_mo = col_spec['prev']

    valid_ages = ['3개월 이하', '3개월 초과', '6개월 초과', '1년 초과']
    df_valid = df[df['구분2'].isin(valid_ages)].copy()
    
    agg = df_valid.groupby(['구분1', '연도', '월'])['값'].sum().to_dict()
    agg_janggi = df_valid[df_valid['구분2'].isin(['6개월 초과', '1년 초과'])].groupby(['구분1', '연도', '월'])['값'].sum().to_dict()

    def v(g1, yr, mo): return agg.get((g1, yr, mo), 0.0)
    def j(g1, yr, mo): return agg_janggi.get((g1, yr, mo), 0.0)
    
    def v_총계(yr, mo): return v('원재료', yr, mo) + v('재공품', yr, mo) + v('제품', yr, mo)
    def j_총계(yr, mo): return j('원재료', yr, mo) + j('재공품', yr, mo) + j('제품', yr, mo)

    def cvs(fn, *keys):
        return ([fn(*keys, yr, 12) for yr in past_years]
                + [fn(*keys, yr_c, mo_c) for yr_c, mo_c in recent_curr])

    def mom(fn, *keys):
        return fn(*keys, curr_yr, curr_mo) - fn(*keys, prev_yr, prev_mo)

    def pct_v(yr, mo):
        t = v_총계(yr, mo)
        return j_총계(yr, mo) / t * 100 if t else 0.0

    pct_vals = [pct_v(yr, 12) for yr in past_years] + [pct_v(yr_c, mo_c) for yr_c, mo_c in recent_curr]
    pct_mom  = pct_v(curr_yr, curr_mo) - pct_v(prev_yr, prev_mo)

    dec = 1
    rows = []
    # 원재료, 재공품, 제품의 총계만 표시
    for g1 in ['원재료', '재공품', '제품']:
        rows.append({'label': g1, 'kind': 'detail', 'vals': cvs(v, g1), 'mom': mom(v, g1), 'dec': dec})
    
    # 장기재고 소계 (비율 포함)
    rows.append({'label': '장기재고', 'kind': '장기소계', 'vals': cvs(j_총계), 'mom': mom(j_총계), 'dec': dec,
                 'pct_vals': pct_vals, 'pct_mom': pct_mom})
    
    # 전체 총계
    rows.append({'label': '총 재고 계', 'kind': 'total', 'vals': cvs(v_총계), 'mom': mom(v_총계), 'dec': dec})
    return rows

def _종합_to_html(rows, col_spec):
    th = f'<th style="{_TH}">구분</th>'
    for lbl in _col_labels(col_spec):
        th += f'<th style="{_TH}">{lbl}</th>'
    th += f'<th style="{_TH}">전월대비</th>'

    body = ''
    for row in rows:
        kind  = row['kind']
        vals  = row['vals']
        mom_v = row['mom']
        dec   = row['dec']

        if kind == 'detail':
            lbl_s, num_s, red_s = ROW_ITEM, _TD_NUM, _TD_RED
        else:
            lbl_s, num_s, red_s = ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED

        cells  = f'<td style="{lbl_s}">{row["label"]}</td>'
        for v in vals:
            cells += f'<td style="{num_s}">{_fmt(v, decimal=dec)}</td>'
        m_s = red_s if mom_v < 0 else num_s
        cells += f'<td style="{m_s}">{_fmt(mom_v, decimal=dec)}</td>'
        body  += f'<tr>{cells}</tr>'

        if kind == '장기소계':
            cells = f'<td style="{ROW_ITEM}">(%)</td>'
            for v in row['pct_vals']:
                cells += f'<td style="{ROW_HDR_NUM}">{_fmt_연령_pct(v)}</td>'
            cells += f'<td style="{ROW_HDR_NUM}">{_fmt_연령_pct(row["pct_mom"], decimal=1)}</td>'
            body  += f'<tr>{cells}</tr>'

    return _html_table(f'<tr>{th}</tr>', body)

# ── 차트 함수 ──────────────────────────────────────────────────────────────

def _build_단품_chart_data(g1, df, col_spec):
    past_years  = col_spec['past_years']
    recent_curr = col_spec['recent_curr']
    cols = [(yr, 12) for yr in past_years] + list(recent_curr)

    df1 = df[df['구분1'] == g1]

    # 1. 정상재 (연령 데이터 4종 합산)
    valid_ages = ['3개월 이하', '3개월 초과', '6개월 초과', '1년 초과']
    agg_정상 = df1[df1['구분2'].isin(valid_ages)].groupby(['연도', '월'])['값'].sum().to_dict()
    
    # 2. 장기재고 (선 그래프용)
    agg_장기 = df1[df1['구분2'].isin(['6개월 초과', '1년 초과'])].groupby(['연도', '월'])['값'].sum().to_dict()
    
    # 3. 매입매출
    agg_매입 = df1[df1['구분2'].str.contains('매입매출', na=False)].groupby(['연도', '월'])['값'].sum().to_dict()
    
    # 4. 기타 (회색 바: 전체 - 정상재 - 매입매출)
    agg_all  = df1.groupby(['연도', '월'])['값'].sum().to_dict()

    정상_vals = [agg_정상.get(k, 0.0) for k in cols]
    장기_vals = [agg_장기.get(k, 0.0) for k in cols]
    매입_vals = [agg_매입.get(k, 0.0) for k in cols]
    
    기타_vals = []
    for k in cols:
        val = agg_all.get(k, 0.0) - agg_정상.get(k, 0.0) - agg_매입.get(k, 0.0)
        기타_vals.append(max(0, val))  # 음수 방지

    return 정상_vals, 매입_vals, 기타_vals, 장기_vals


def _build_종합_chart_data(df, col_spec):
    past_years  = col_spec['past_years']
    recent_curr = col_spec['recent_curr']
    cols = [(yr, 12) for yr in past_years] + list(recent_curr)
    
    valid_ages = ['3개월 이하', '3개월 초과', '6개월 초과', '1년 초과']
    df_valid = df[df['구분2'].isin(valid_ages)]

    def agg_vals(df_f):
        a = df_f.groupby(['연도', '월'])['값'].sum().to_dict()
        return [a.get((yr, mo), 0.0) for yr, mo in cols]

    df_원재료 = df_valid[df_valid['구분1'] == '원재료']
    df_재공품 = df_valid[df_valid['구분1'] == '재공품']
    df_제품   = df_valid[df_valid['구분1'] == '제품']

    원재료_v = agg_vals(df_원재료)
    재공품_v = agg_vals(df_재공품)
    제품_v   = agg_vals(df_제품)

    def agg_장기(df_f):
        a = df_f[df_f['구분2'].isin(['6개월 초과', '1년 초과'])].groupby(['연도', '월'])['값'].sum().to_dict()
        return [a.get((yr, mo), 0.0) for yr, mo in cols]

    장기_v  = [a + b + c for a, b, c in zip(agg_장기(df_원재료), agg_장기(df_재공품), agg_장기(df_제품))]
    total_v = [a + b + c for a, b, c in zip(원재료_v, 재공품_v, 제품_v)]
    pct_v   = [j / t * 100 if t else 0.0 for j, t in zip(장기_v, total_v)]

    return 제품_v, 재공품_v, 원재료_v, 장기_v, pct_v

def _chart_단품(x_labels, 정상_vals, 매입_vals, 기타_vals, 장기_vals, decimal=0, g1_label=''):
    fig = go.Figure()
    fmt_v = lambda v: _fmt(v, decimal=decimal)

    # 1. 정상재 (진한 회색 막대)
    fig.add_trace(go.Bar(
        name='정상재', x=x_labels, y=정상_vals,
        marker_color='#3b4a5a', marker_line_width=0,
        text=[fmt_v(v) if v > 0 else '' for v in 정상_vals], # 볼드 제거
        textposition='inside', insidetextanchor='end',
        textfont=dict(color='white', size=10), # 폰트 10으로 통일
    ))
    
    # 2. 매입매출 (빨간색 막대)
    fig.add_trace(go.Bar(
        name='매입매출', x=x_labels, y=매입_vals,
        marker_color='#e74c3c', marker_line_width=0,
        hoverinfo='y+name'
    ))
    
    # 3. [구분] 합계 (연한 회색 막대)
    fig.add_trace(go.Bar(
        name=f'{g1_label} 합계', x=x_labels, y=기타_vals,
        marker_color='#a6a6a6', marker_line_width=0,
        hoverinfo='y+name'
    ))
    
    # 4. 장기재고 (노란색 선 그래프) - 단일 축에 렌더링
    fig.add_trace(go.Scatter(
        name='장기재고', x=x_labels, y=장기_vals,
        mode='lines+markers+text',
        line=dict(color='#FFC000', width=2), # 굵기 2로 통일
        marker=dict(size=8, color='white', line=dict(color='#FFC000', width=2)), # 마커 스타일 통일
        text=[fmt_v(v) if v > 0 else '' for v in 장기_vals], # 볼드 제거
        textposition='top center',
        textfont=dict(size=10, color='#FFC000'), # 폰트 10으로 통일
    ))

    # 최대값 계산하여 여백 확보
    max_total = max([a + b + c for a, b, c in zip(정상_vals, 매입_vals, 기타_vals)], default=1)

    fig.update_layout(
        barmode='stack', height=280,
        margin=dict(l=40, r=20, t=30, b=40),
        showlegend=True,
        legend=dict(orientation='h', x=0.5, xanchor='center',
                    y=-0.15, yanchor='top',
                    font=dict(size=11), bgcolor='rgba(0,0,0,0)'),
        xaxis=dict(showgrid=False, tickfont=dict(size=11, color=C_NAVY)), # 색상 통일
        yaxis=dict(showgrid=True, gridcolor='#eee',
                   range=[0, max_total * 1.15], 
                   showticklabels=True, tickfont=dict(size=11, color='#555')),
        plot_bgcolor='white', paper_bgcolor='white', bargap=0.4,
        # 우측 상단 단위 라벨 추가
        annotations=[
            dict(
                text='(단위 : 톤)',
                xref='paper', yref='paper',
                x=1.0, y=1.05,
                showarrow=False,
                font=dict(size=11, color='gray'),
                xanchor='right', yanchor='bottom'
            )
        ]
    )
    return fig

def _chart_종합(x_labels, 제품_v, 재공품_v, 원재료_v, 장기_v, pct_v):
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='원재료(ea)', x=x_labels, y=원재료_v,
        marker_color=C_NAVY, marker_line_width=0,
        text=[_fmt(v, decimal=1) for v in 원재료_v],
        textposition='inside', textfont=dict(color='white', size=10),
    ))
    fig.add_trace(go.Bar(
        name='재공품', x=x_labels, y=재공품_v,
        marker_color=C_CHART_SEC, marker_line_width=0,
        text=[_fmt(v, decimal=1) for v in 재공품_v],
        textposition='inside', textfont=dict(color='white', size=10),
    ))
    fig.add_trace(go.Bar(
        name='제품', x=x_labels, y=제품_v,
        marker_color=C_ORANGE, marker_line_width=0,
        text=[_fmt(v, decimal=1) for v in 제품_v],
        textposition='inside', textfont=dict(color='white', size=10),
    ))
    
    fig.add_trace(go.Scatter(
        name='장기재고', x=x_labels, y=장기_v,
        yaxis='y2',
        mode='lines+markers+text',
        # 아래 line, marker, textfont의 color를 노란색 계열로 변경
        line=dict(color='#FFC000', width=2),
        marker=dict(size=8, color='white', line=dict(color='#FFC000', width=2)),
        text=[f"{_fmt(v, decimal=1)}({p:.0f}%)" for v, p in zip(장기_v, pct_v)],
        textposition='top center',
        textfont=dict(size=10, color='#FFC000'),
    ))

    max_total = max(a + b + c for a, b, c in zip(원재료_v, 재공품_v, 제품_v)) if 원재료_v else 1
    max_janggi = max(장기_v) if 장기_v and max(장기_v) > 0 else 1

    fig.update_layout(
        barmode='stack', height=280,
        margin=dict(l=10, r=10, t=5, b=20),
        showlegend=True,
        legend=dict(orientation='h', x=0.5, xanchor='center',
                    y=0.98, yanchor='top',
                    font=dict(size=11), bgcolor='rgba(255,255,255,0.8)',
                    borderwidth=0),
        xaxis=dict(showgrid=False, tickfont=dict(size=11, color=C_NAVY)),
        yaxis=dict(showgrid=True, gridcolor=C_CHART_GRID,
                   range=[0, max_total * 1.3], showticklabels=False),
        # ⭕ 보조축 레이아웃 추가
        yaxis2=dict(overlaying='y', side='right',
                    range=[0, max_janggi * 1.5], showticklabels=False, showgrid=False),
        plot_bgcolor='white', paper_bgcolor='white', bargap=0.3,
    )
    return fig

# ══════════════════════════════════════════════════════════════════════════
# ── 탭 3: 등급별 재고현황 ──────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _load_등급별(year, month):
    df = load_sheet(Sheets.등급별재고현황_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    df['값'] = (df['값'] / 1_000).round()

    for c in ['구분1', '구분2']:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    # ⭕ 두번째 탭과 동일하게 2년전말, 1년전말 고정
    past_years = [year - 2, year - 1]
    
    # ⭕ 최근 3개월(2개월 전, 1개월 전, 당월) 고정
    recent_curr = _recent_months(year, month, n=_N_RECENT)
    
    col_spec = {
        'past_years':  past_years,
        'recent_curr': recent_curr,
        'curr': (year, month),
    }
    return df, col_spec


def _build_등급별_rows(df, col_spec):
    past_years  = col_spec['past_years']
    recent_curr = col_spec['recent_curr']

    agg = df.groupby(['구분1', '구분2', '연도', '월'])['값'].sum().to_dict()

    def v(g1, g2, yr, mo): 
        return agg.get((g1, g2, yr, mo), 0.0)

    def cvs(g1, g2):
        return ([v(g1, g2, yr, 12) for yr in past_years]
                + [v(g1, g2, yr_c, mo_c) for yr_c, mo_c in recent_curr])

    # 제품 합계 계산용
    grades = ['B급', 'C급', 'D급', 'D2급', 'X급']
    def v_제품합계(yr, mo):
        return sum(v('제품', g, yr, mo) for g in grades)

    def cvs_제품합계():
        return ([v_제품합계(yr, 12) for yr in past_years]
                + [v_제품합계(yr_c, mo_c) for yr_c, mo_c in recent_curr])

    rows = []
    # 1. 제품 개별 등급
    for g2 in grades:
        rows.append({'label': f'제품 ({g2})', 'kind': 'detail', 'vals': cvs('제품', g2)})
    
    # 2. 제품 합계
    rows.append({'label': '제품 (합계)', 'kind': 'total', 'vals': cvs_제품합계()})
    
    # 3. 재공품
    rows.append({'label': '재공품 (재공품)', 'kind': 'detail', 'vals': cvs('재공품', '재공품')})

    return rows


def _등급별_to_html(rows, col_spec):
    col_lbls = _col_labels(col_spec)
    n_cols   = len(col_lbls) + 1  # 구분 + 날짜 컬럼들

    th = f'<th style="{_TH}">구분</th>'
    for lbl in col_lbls:
        th += f'<th style="{_TH}">{lbl}</th>'

    body = ''
    for row in rows:
        kind  = row['kind']
        vals  = row['vals']
        
        if kind == 'detail':
            lbl_s, num_s = ROW_ITEM, _TD_NUM
        else:
            lbl_s, num_s = ROW_HDR_LBL, ROW_HDR_NUM

        cells = f'<td style="{lbl_s}">{row["label"]}</td>'
        for val in vals:
            cells += f'<td style="{num_s}">{_fmt(val, decimal=0)}</td>'
        body += f'<tr>{cells}</tr>'

    return _html_table(f'<tr>{th}</tr>', body)


def _build_등급별_chart_data(df, col_spec):
    past_years  = col_spec['past_years']
    recent_curr = col_spec['recent_curr']
    cols = [(yr, 12) for yr in past_years] + list(recent_curr)

    agg = df.groupby(['구분1', '구분2', '연도', '월'])['값'].sum().to_dict()

    def get_vals(g1, g2):
        return [agg.get((g1, g2, yr, mo), 0.0) for yr, mo in cols]

    grades = ['B급', 'C급', 'D급', 'D2급', 'X급']
    grade_data = {g: get_vals('제품', g) for g in grades}
    rework_data = get_vals('재공품', '재공품')

    return grade_data, rework_data


def _chart_등급별(x_labels, grade_data, rework_data):
    fig = go.Figure()

    # 이미지 기준 색상 매칭 (B급: 어두운 네이비, C급: 주황/다홍, D급: 회색 계열 등)
    colors = {
        'B급': '#34495e',
        'C급': '#e74c3c',
        'D급': '#95a5a6',
        'D2급': '#bdc3c7',
        'X급': '#3498db',
        '재공품': '#2ecc71'
    }

    # 스택 바 차트 생성 (아래에서 위로 쌓이는 순서)
    order = ['B급', 'C급', 'D급', 'D2급', 'X급']
    for g in order:
        vals = grade_data[g]
        fig.add_trace(go.Bar(
            name=f'제품({g})', x=x_labels, y=vals,
            marker_color=colors.get(g, C_NAVY), marker_line_width=0,
            text=[_fmt(v, decimal=0) if v > 0 else '' for v in vals],
            textposition='inside', textfont=dict(color='white', size=10),
        ))

    # 재공품 스택 추가
    fig.add_trace(go.Bar(
        name='재공품(재공품)', x=x_labels, y=rework_data,
        marker_color=colors['재공품'], marker_line_width=0,
        text=[_fmt(v, decimal=0) if v > 0 else '' for v in rework_data],
        textposition='outside', textfont=dict(color='#333333', size=10),
    ))

    fig.update_layout(
        barmode='stack', height=320,
        margin=dict(l=10, r=10, t=20, b=20),
        showlegend=True,
        legend=dict(orientation='h', x=0.5, xanchor='center',
                    y=-0.2, yanchor='top',
                    font=dict(size=11), bgcolor='rgba(255,255,255,0.8)',
                    borderwidth=0),
        xaxis=dict(showgrid=False, tickfont=dict(size=11, color=C_NAVY)),
        yaxis=dict(showgrid=True, gridcolor=C_CHART_GRID, showticklabels=False),
        plot_bgcolor='white', paper_bgcolor='white', bargap=0.3,
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════
# ── render_page ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def render_page(app, year_state, month_state):

    def _render_title():
        app.markdown(
            f'<h1 style="color:#404448">{int(year_state.value)}년 {int(month_state.value)}월 재고자산분석</h1>',
            unsafe_allow_html=True,
        )
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["재고자산 현황", "연령별 재고현황", "등급별 재고현황"])

    # ── 탭 0: 재고자산 현황 ─────────────────────────────────────────────
    with tabs[0]:
        def _render_재고현황():
            year, month = int(year_state.value), int(month_state.value)
            group_rows, sum_rows, col_spec = _build_재고현황(year, month)
            memo = _get_memo(Sheets.재고현황_메모, year, month)
            app.markdown(
                _layout64('1) 재고자산 현황',
                          _재고현황_to_html(group_rows, sum_rows, col_spec),
                          memo,
                          unit='[단위: 톤, 백만원]'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_재고현황)

    # ── 탭 1: 연령별 재고현황 ────────────────────────────────────────────
    with tabs[1]:
        def _render_연령별():
            year, month = int(year_state.value), int(month_state.value)
            df, col_spec = _load_연령별(year, month)
            x_labels = _col_labels(col_spec)
            memo = _get_memo(Sheets.연령별재고현황_메모, year, month)

            # ⭕ 차트를 표 하단에 맞추기 위한 컨테이너 스타일 (높이 조절)
            chart_wrapper = '<div style="display:flex; flex-direction:column; justify-content:flex-end; height:100%; min-height:280px; padding-top:40px;">'
         
            # 1) 원재료 현황
            rows_원재료 = _build_단품_rows('원재료', df, col_spec)
            정상_1, 매입_1, 기타_1, 장기_1 = _build_단품_chart_data('원재료', df, col_spec)

            col_l, col_r = app.columns([6, 4])
            with col_l:
                app.markdown(
                    _sec_title('1) 원재료 현황', '[단위: 톤]') 
                    + _단품_to_html(rows_원재료, col_spec, '원재료'),
                    unsafe_allow_html=True)
            with col_r:
                app.markdown(
                    chart_wrapper 
                    + _fig_to_iframe(_chart_단품(x_labels, 정상_1, 매입_1, 기타_1, 장기_1, decimal=0, g1_label='원재료'))
                    + '</div>', 
                    unsafe_allow_html=True)

            # 2) 재공품 현황
            rows_재공품 = _build_단품_rows('재공품', df, col_spec)
            정상_2, 매입_2, 기타_2, 장기_2 = _build_단품_chart_data('재공품', df, col_spec)

            col_l2, col_r2 = app.columns([6, 4])
            with col_l2:
                app.markdown(
                    _sec_title('2) 재공품 현황', '[단위: 톤]') 
                    + _단품_to_html(rows_재공품, col_spec, '재공품'),
                    unsafe_allow_html=True)
            with col_r2:
                app.markdown(
                    chart_wrapper
                    + _fig_to_iframe(_chart_단품(x_labels, 정상_2, 매입_2, 기타_2, 장기_2, decimal=1, g1_label='재공품'))
                    + '</div>', 
                    unsafe_allow_html=True)

            # 3) 제품 현황
            rows_제품 = _build_단품_rows('제품', df, col_spec)
            정상_3, 매입_3, 기타_3, 장기_3 = _build_단품_chart_data('제품', df, col_spec)

            col_l3, col_r3 = app.columns([6, 4])
            with col_l3:
                app.markdown(
                    _sec_title('3) 제품 현황', '[단위: 톤]') 
                    + _단품_to_html(rows_제품, col_spec, '제품'),
                    unsafe_allow_html=True)
            with col_r3:
                app.markdown(
                    chart_wrapper
                    + _fig_to_iframe(_chart_단품(x_labels, 정상_3, 매입_3, 기타_3, 장기_3, decimal=1, g1_label='제품'))
                    + '</div>', 
                    unsafe_allow_html=True)
            # 4) 종합 현황 (왼쪽 6 영역에 표, 오른쪽 4 영역에 차트)
            rows_종합 = _build_종합_rows(df, col_spec)
            제품_v, 재공품_v, 원재료_v, 장기_v, pct_v = _build_종합_chart_data(df, col_spec)

            col_l4, col_r4 = app.columns([6, 4])
            with col_l4:
                app.markdown(
                    _sec_title('4) 총 재고 및 장기재고 현황', '[단위: 만개]')
                    + _종합_to_html(rows_종합, col_spec),
                    unsafe_allow_html=True)
            with col_r4:
                app.markdown(
                    chart_wrapper
                    + _fig_to_iframe(_chart_종합(x_labels, 제품_v, 재공품_v, 원재료_v, 장기_v, pct_v))
                    + '</div>',
                    unsafe_allow_html=True)
            # 5) 메모 출력
            if memo:
                app.markdown('<br><hr style="border-top:1px solid #ddd;">', unsafe_allow_html=True)
                app.markdown(_sec_title('', ''), unsafe_allow_html=True)
                app.markdown(_memo_html(memo), unsafe_allow_html=True)

        app.If(lambda: True, _render_연령별)

    # ── 탭 2: 등급별 재고현황 ─────────────────────────────────────────────
    with tabs[2]:
        def _render_등급별():
            year, month = int(year_state.value), int(month_state.value)
            df, col_spec = _load_등급별(year, month)
            x_labels = _col_labels(col_spec)
            rows_등급 = _build_등급별_rows(df, col_spec)
            grade_data, rework_data = _build_등급별_chart_data(df, col_spec)
            memo = _get_memo(Sheets.등급별재고현황_메모, year, month)

            chart_wrapper = '<div style="display:flex; flex-direction:column; justify-content:flex-end; height:100%; min-height:280px; padding-top:40px;">'

            col_l, col_r = app.columns([6, 4])
            
            # 1) 왼쪽 영역 (6): 표 렌더링
            with col_l:
                app.markdown(
                    _sec_title('1) 등급별 재고현황', '[단위: 톤]')
                    + _등급별_to_html(rows_등급, col_spec),
                    unsafe_allow_html=True,
                )
                
            # 2) 오른쪽 영역 (4): 차트 렌더링
            with col_r:
                app.markdown(
                    chart_wrapper
                    + _fig_to_iframe(_chart_등급별(x_labels, grade_data, rework_data))
                    + '</div>',
                    unsafe_allow_html=True,
                )

            # 3) 메모 출력 (가장 아래 배치)
            if memo:
                app.markdown('<br><hr style="border-top:1px solid #ddd;">', unsafe_allow_html=True)
                app.markdown(_sec_title('', ''), unsafe_allow_html=True)
                app.markdown(_memo_html(memo), unsafe_allow_html=True)

        app.If(lambda: True, _render_등급별)