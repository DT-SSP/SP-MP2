import base64
import datetime
import pandas as pd
import plotly.graph_objects as go
from data.loader import load_sheet
from data.config import (
    Sheets,
    노무비_G1_순서, 노무비_계_G1, 노무비_인당평균_G1,
    근태_인원수_G1,
)
from views.common import (
    parse as _parse, fmt as _fmt,
    drop_empty as _drop_empty,
    recent_months as _recent_months,
    TH as _TH, TD_NUM as _TD_NUM, TD_RED as _TD_RED,
    ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED,
    ROW_CAL_LBL, ROW_CAL_NUM, ROW_CAL_RED,
    ROW_GRP, ROW_ITEM,
    html_table as _html_table,
)

# ── 로컬 스타일 상수 ───────────────────────────────────────────────────────
_TD_ANNO  = 'padding:4px 10px;text-align:right;border-bottom:1px solid #e2e8f0;color:#718096;font-size:0.88em'
_ROW_ANNO = 'padding:4px 10px 4px 10px;text-align:left;border-bottom:1px solid #e2e8f0;color:#718096;font-size:0.88em'


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────

def _get_연도_목록():
    df = load_sheet(Sheets.인원현황_DB)
    return sorted(pd.to_numeric(df['연도'], errors='coerce').dropna().astype(int).unique().tolist())


def _get_memo(sheet_info, year, month):
    df = load_sheet(sheet_info)
    df['연도'] = df['연도'].astype(str).str.strip()
    df['월']   = df['월'].astype(str).str.strip()
    row = df[(df['연도'] == str(year)) & (df['월'] == str(month))]
    return str(row.iloc[0]['메모']) if not row.empty else ''


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


def _fig_to_iframe(fig):
    h = fig.layout.height or 260
    html = fig.to_html(include_plotlyjs='cdn', full_html=True,
                       config={'displayModeBar': False, 'responsive': True})
    html = html.replace('</head>',
                        '<style>html,body{margin:0;padding:0;overflow:hidden}</style></head>', 1)
    b64 = base64.b64encode(html.encode()).decode()
    return (f'<iframe src="data:text/html;base64,{b64}" '
            f'height="{h}" width="100%" scrolling="no" '
            f'style="border:none;display:block;margin:0;padding:0"></iframe>')


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 1: 인원현황 ─────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _build_인원변동내역(year, month):
    df = load_sheet(Sheets.인원_DB)
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    df['구분2'] = df['구분2'].fillna('').astype(str).str.strip()

    vm = {}
    for _, row in df.iterrows():
        key = (str(row['구분1']).strip(), str(row['구분2']).strip(), int(row['연도']), int(row['월']))
        vm[key] = float(row['값'])

    years = sorted(df['연도'].unique().tolist())
    자사계_subs = ['사무기술직', '기능직']

    def get(g1, g2, yr, mo):
        return vm.get((g1, g2, yr, mo), 0.0)

    def 자사계_val(yr, mo):
        return sum(get('자사계', s, yr, mo) for s in 자사계_subs)

    def 외주계_val(yr, mo):
        return get('외주계', '', yr, mo)

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
            return get('자사계', s, yr, mo)
        rows.append(('child', sub, [get_cell(val_fn, ck) for ck in col_keys]))

    rows.append(('subtotal', '자사계', [get_cell(자사계_val, ck) for ck in col_keys]))
    rows.append(('standalone', '외주계', [get_cell(외주계_val, ck) for ck in col_keys]))
    rows.append(('total', '전체', [get_cell(전체_val, ck) for ck in col_keys]))

    return rows, col_headers


def _인원변동내역_to_html(rows, col_headers):
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
            cells = f'<td style="{ROW_ITEM + bg}">&nbsp;&nbsp;&nbsp;{label}</td>'
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


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 2: 노무비 현황 ─────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _build_노무비현황(year, month):
    df = load_sheet(Sheets.사무직기능직노무비현황_DB)
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    for col in ['구분1', '구분2', '구분3']:
        df[col] = df[col].fillna('').astype(str).str.strip()

    vm = {}
    for _, row in df.iterrows():
        key = (row['구분1'], row['구분2'], row['구분3'], int(row['연도']), int(row['월']))
        vm[key] = float(row['값'])

    years = sorted(df['연도'].unique().tolist())
    actual_g1s = set(df['구분1'].unique())

    def get(g1, g2, g3, yr, mo):
        return vm.get((g1, g2, g3, yr, mo), 0.0)

    def yr_avg(val_fn, yr):
        mos = range(1, 13) if yr < year else range(1, month)
        vals = [val_fn(yr, mo) for mo in mos]
        cnt = sum(1 for v in vals if v != 0.0)
        return sum(vals) / cnt if cnt else 0.0

    def g2_for(g1):
        return list(dict.fromkeys(
            df[(df['구분1'] == g1) & (df['구분2'] != '')]['구분2'].tolist()
        ))

    def g3_for(g1, g2):
        return list(dict.fromkeys(
            df[(df['구분1'] == g1) & (df['구분2'] == g2) & (df['구분3'] != '')]['구분3'].tolist()
        ))

    def val_g2_sum(g1, g2, yr, mo):
        g3s = g3_for(g1, g2)
        if not g3s:
            return get(g1, g2, '', yr, mo)
        return sum(get(g1, g2, g3, yr, mo) for g3 in g3s if '근무시간' not in g3)

    def val_g1_sum(g1, yr, mo):
        g2s = g2_for(g1)
        if not g2s:
            return get(g1, '', '', yr, mo)
        return sum(val_g2_sum(g1, g2, yr, mo) for g2 in g2s)

    def 인원_g2(g2, yr, mo):
        return get('인원수', g2, '', yr, mo)

    def 인원_total(yr, mo):
        return sum(get('인원수', g2, '', yr, mo) for g2 in g2_for('인원수'))

    def 노무비계_val(yr, mo):
        return sum(val_g1_sum(g1, yr, mo) for g1 in 노무비_계_G1 if g1 in actual_g1s)

    recent = _recent_months(year, month, 5)
    col_keys = [(yr, 'avg') for yr in years] + list(recent)

    def get_cell(val_fn, key):
        if key[1] == 'avg':
            return yr_avg(val_fn, key[0])
        return val_fn(key[0], key[1])

    col_headers = [f"'{str(yr)[2:]}.평균" for yr in years]
    last_yr = None
    for yr, mo in recent:
        if yr != last_yr:
            col_headers.append(f"'{str(yr)[2:]}.{mo}월")
            last_yr = yr
        else:
            col_headers.append(f"{mo}월")

    # rows: (type, label, vals, fmt)
    # type: 'sec'|'sec_alone'|'calc'|'child1'|'child2'|'anno0'|'anno1'|'anno2'
    # fmt:  None(int) | 'd1'(소수1자리+괄호) | 'ip'(정수+괄호)
    rows = []

    for g1 in 노무비_G1_순서:
        if g1 == '$노무비계':
            rows.append(('calc', '노무비 계',
                         [get_cell(노무비계_val, ck) for ck in col_keys], None))
            continue
        if g1 not in actual_g1s:
            continue

        g2s = g2_for(g1)

        if g2s:
            def _g1fn(yr, mo, _g1=g1): return val_g1_sum(_g1, yr, mo)
            rows.append(('sec', g1, [get_cell(_g1fn, ck) for ck in col_keys], None))

            if g1 in 노무비_인당평균_G1:
                def _i_g1(yr, mo, _g1=g1):
                    n = 인원_total(yr, mo)
                    return val_g1_sum(_g1, yr, mo) / n if n else 0.0
                rows.append(('anno0', '인당 급여',
                             [get_cell(_i_g1, ck) for ck in col_keys], 'd1'))

            for g2 in g2s:
                def _g2fn(yr, mo, _g1=g1, _g2=g2): return val_g2_sum(_g1, _g2, yr, mo)
                has_g3 = bool(g3_for(g1, g2))
                child1_type = 'child1_grp' if has_g3 else 'child1'
                rows.append((child1_type, g2, [get_cell(_g2fn, ck) for ck in col_keys], None))

                if g1 in 노무비_인당평균_G1:
                    def _i_g2(yr, mo, _g1=g1, _g2=g2):
                        n = 인원_g2(_g2, yr, mo) or 인원_total(yr, mo)
                        return val_g2_sum(_g1, _g2, yr, mo) / n if n else 0.0
                    rows.append(('anno1', '인당 평균',
                                 [get_cell(_i_g2, ck) for ck in col_keys], 'd1'))

                g3s = g3_for(g1, g2)
                if g3s:
                    근무_set = {g3 for g3 in g3s if '근무시간' in g3}
                    data_g3s = [g3 for g3 in g3s if '근무시간' not in g3]
                    for g3 in data_g3s:
                        def _g3fn(yr, mo, _g1=g1, _g2=g2, _g3=g3):
                            return get(_g1, _g2, _g3, yr, mo)
                        rows.append(('child2', g3, [get_cell(_g3fn, ck) for ck in col_keys], None))

                        if g3.endswith('수당'):
                            prefix = g3[:-2]
                            근무_key = f'{prefix} 근무시간'
                            if 근무_key in 근무_set:
                                def _근무fn(yr, mo, _g1=g1, _g2=g2, _gk=근무_key):
                                    return get(_g1, _g2, _gk, yr, mo)
                                rows.append(('anno2', '근무시간',
                                             [get_cell(_근무fn, ck) for ck in col_keys], 'ip'))
                        elif g1 in 노무비_인당평균_G1:
                            def _i_g3(yr, mo, _g1=g1, _g2=g2, _g3=g3):
                                n = 인원_g2(_g2, yr, mo) or 인원_total(yr, mo)
                                return get(_g1, _g2, _g3, yr, mo) / n if n else 0.0
                            rows.append(('anno2', '인당 평균',
                                         [get_cell(_i_g3, ck) for ck in col_keys], 'd1'))
        else:
            def _sfn(yr, mo, _g1=g1): return get(_g1, '', '', yr, mo)
            rows.append(('sec_alone', g1, [get_cell(_sfn, ck) for ck in col_keys], None))

    # 차트용 데이터
    if '급여' in actual_g1s:
        def _급여fn(yr, mo): return val_g1_sum('급여', yr, mo)
        def _인당fn(yr, mo):
            n = 인원_total(yr, mo)
            return val_g1_sum('급여', yr, mo) / n if n else 0.0
        급여_vals = [get_cell(_급여fn, ck) for ck in col_keys]
        인당_vals  = [get_cell(_인당fn, ck) for ck in col_keys]
    else:
        급여_vals = 인당_vals = [0.0] * len(col_keys)

    return rows, col_headers, 급여_vals, 인당_vals


def _노무비현황_to_html(rows, col_headers):
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    body = ''

    def _fval(v, fmt):
        if fmt == 'd1':
            return f'({_fmt(v, decimal=1)})' if v != 0.0 else '(-)'
        if fmt == 'ip':
            return f'({_fmt(v)})' if v != 0.0 else '(-)'
        return _fmt(v)

    _I1 = '&nbsp;&nbsp;&nbsp;'       # 들여쓰기 1단계
    _I2 = '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'  # 들여쓰기 2단계

    for row_type, label, vals, fmt in rows:
        if row_type in ('sec', 'sec_alone'):
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_HDR_RED if v < 0 else ROW_HDR_NUM}">{_fmt(v)}</td>'

        elif row_type == 'calc':
            cells = f'<td style="{ROW_CAL_LBL}">{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_CAL_RED if v < 0 else ROW_CAL_NUM}">{_fmt(v)}</td>'

        elif row_type == 'child1':
            cells = f'<td style="{ROW_ITEM}">{_I1}{label}</td>'
            for v in vals:
                cells += f'<td style="{_TD_RED if v < 0 else _TD_NUM}">{_fmt(v)}</td>'

        elif row_type == 'child1_grp':
            cells = f'<td style="{ROW_GRP}">{_I1}{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_HDR_RED if v < 0 else ROW_HDR_NUM}">{_fmt(v)}</td>'

        elif row_type == 'child2':
            cells = f'<td style="{ROW_ITEM}">{_I2}{label}</td>'
            for v in vals:
                cells += f'<td style="{_TD_RED if v < 0 else _TD_NUM}">{_fmt(v)}</td>'

        elif row_type == 'anno0':
            cells = f'<td style="{_ROW_ANNO}">{_I1}{label}</td>'
            for v in vals:
                cells += f'<td style="{_TD_ANNO}">{_fval(v, fmt)}</td>'

        elif row_type == 'anno1':
            cells = f'<td style="{_ROW_ANNO}">{_I1}({label})</td>'
            for v in vals:
                cells += f'<td style="{_TD_ANNO}">{_fval(v, fmt)}</td>'

        elif row_type == 'anno2':
            cells = f'<td style="{_ROW_ANNO}">{_I2}({label})</td>'
            for v in vals:
                cells += f'<td style="{_TD_ANNO}">{_fval(v, fmt)}</td>'

        body += f'<tr>{cells}</tr>'

    return _html_table(th_html, body)


def _노무비현황_chart(col_labels, 급여_vals, 인당_vals):
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='급여', x=col_labels, y=급여_vals,
        marker_color='#4a4a5a', marker_line_width=0,
        text=[str(round(v)) if v != 0 else '' for v in 급여_vals],
        textposition='inside', textfont=dict(color='white', size=12),
    ))
    fig.add_trace(go.Scatter(
        name='인당 급여', x=col_labels, y=인당_vals,
        mode='lines+markers+text',
        line=dict(color='#e53e3e', width=2),
        marker=dict(color='white', size=7, line=dict(color='#e53e3e', width=2)),
        text=[f'({v:.1f})' if v != 0 else '' for v in 인당_vals],
        textposition='top center', textfont=dict(size=11, color='#9b2c2c'),
        yaxis='y2',
    ))

    max_급여 = max((v for v in 급여_vals if v > 0), default=100)
    valid_인당 = [v for v in 인당_vals if v > 0]
    min_인당, max_인당 = (min(valid_인당), max(valid_인당)) if valid_인당 else (0, 10)
    dr = max(max_인당 - min_인당, 1)
    y2_total = dr / 0.40
    ymin2 = min_인당 - 0.50 * y2_total

    fig.update_layout(
        height=280,
        margin=dict(l=10, r=60, t=20, b=60),
        legend=dict(orientation='h', y=-0.25, x=0.5, xanchor='center',
                    font=dict(size=12), bgcolor='rgba(0,0,0,0)'),
        xaxis=dict(tickfont=dict(size=10), showgrid=False,
                   linecolor='#e2e8f0', linewidth=1, showline=True),
        yaxis=dict(showgrid=True, gridcolor='#E8EAED',
                   range=[0, max_급여 * 2.2],
                   tickfont=dict(size=10), showline=False, zeroline=False),
        yaxis2=dict(overlaying='y', side='right',
                    range=[ymin2, ymin2 + y2_total],
                    showgrid=False, tickfont=dict(size=10, color='#9b2c2c'),
                    showline=False, zeroline=False),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=11, family='sans-serif'),
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 3: 기능직 근태현황 ──────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

_ROW_GRP_SPAN = 'padding:5px 10px;font-weight:700;background:#F1F3F5;border-bottom:1px solid #dee2e6'


def _build_기능직근무시간(year, month):
    df = load_sheet(Sheets.기능직근태현황_DB)
    df = _drop_empty(df, '연도', '월')
    for col in ['구분1', '구분2']:
        df[col] = df[col].fillna('').astype(str).str.strip()

    # None 보존: 빈 셀(blank)과 명시적 0 구분
    vm = {}
    for _, row in df.iterrows():
        raw = str(row['값']).strip()
        key = (row['구분1'], row['구분2'], int(row['연도']), int(row['월']))
        vm[key] = None if raw in ('', 'nan', '-') else _parse(raw)

    def get(g1, g2, yr, mo):
        v = vm.get((g1, g2, yr, mo))
        return 0.0 if v is None else v

    years = sorted({yr for (_, _, yr, _) in vm})
    actual_g1s = df['구분1'].drop_duplicates().tolist()

    def g2_for(g1):
        return list(dict.fromkeys(
            df[(df['구분1'] == g1) & (df['구분2'] != '')]['구분2'].tolist()
        ))

    def val_g1(g1, yr, mo):
        g2s = g2_for(g1)
        return sum(get(g1, g2, yr, mo) for g2 in g2s) if g2s else get(g1, '', yr, mo)

    def 인원(yr, mo):
        return get(근태_인원수_G1, '', yr, mo)

    def 합계(yr, mo):
        return sum(val_g1(g1, yr, mo) for g1 in actual_g1s if g1 != 근태_인원수_G1)

    def yr_avg(val_fn, yr):
        # 현재 연도는 선택 월 포함 (1~month)
        mos = range(1, 13) if yr < year else range(1, month + 1)
        vals = [val_fn(yr, mo) for mo in mos]
        cnt = sum(1 for v in vals if v != 0.0)
        return sum(vals) / cnt if cnt else 0.0

    recent = _recent_months(year, month, month)   # 당해 연도 1~month월
    col_keys = [(yr, 'avg') for yr in years] + list(recent)

    def get_cell(val_fn, key):
        if key[1] == 'avg':
            return yr_avg(val_fn, key[0])
        return val_fn(key[0], key[1])

    col_headers = [f"'{str(yr)[2:]}년 평균" for yr in years]
    last_yr = None
    for yr, mo in recent:
        if yr != last_yr:
            col_headers.append(f"'{str(yr)[2:]}.{mo}월")
            last_yr = yr
        else:
            col_headers.append(f"{mo}월")

    # rows: (type, label, vals)
    # type: 'total'|'standalone'|'anno'|'grp_hdr'|'child'|'subtotal'
    rows = []

    # 합계
    rows.append(('total', '합계', [get_cell(합계, ck) for ck in col_keys]))

    # 인원수
    rows.append(('standalone', 근태_인원수_G1,
                 [get_cell(lambda yr, mo: get(근태_인원수_G1, '', yr, mo), ck) for ck in col_keys]))

    # 나머지 g1
    for g1 in actual_g1s:
        if g1 == 근태_인원수_G1:
            continue

        g2s = g2_for(g1)
        def _g1fn(yr, mo, _g=g1): return val_g1(_g, yr, mo)

        if not g2s:
            # 단독 행 (정취 근로시간, 심야근무 등)
            rows.append(('standalone', g1, [get_cell(_g1fn, ck) for ck in col_keys]))
            def _인당fn(yr, mo, _g=g1):
                n = 인원(yr, mo)
                return val_g1(_g, yr, mo) / n if n else 0.0
            rows.append(('anno', '인당 시간', [get_cell(_인당fn, ck) for ck in col_keys]))
        else:
            # 그룹 행 (연장주휴공휴, 주휴연장공휴연장교대 등)
            rows.append(('grp_hdr', g1, []))

            for g2 in g2s:
                def _g2fn(yr, mo, _g=g1, _g2=g2): return get(_g, _g2, yr, mo)
                rows.append(('child', g2, [get_cell(_g2fn, ck) for ck in col_keys]))

            rows.append(('subtotal', '소계', [get_cell(_g1fn, ck) for ck in col_keys]))
            def _인당g(yr, mo, _g=g1):
                n = 인원(yr, mo)
                return val_g1(_g, yr, mo) / n if n else 0.0
            rows.append(('anno', '인당 시간', [get_cell(_인당g, ck) for ck in col_keys]))

    return rows, col_headers


def _기능직근무시간_to_html(rows, col_headers):
    n_cols = 1 + len(col_headers)
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    body = ''
    _I1 = '&nbsp;&nbsp;&nbsp;'

    def _fv(v, is_direct=False):
        if v is None:
            return '-'
        rv = round(v)
        if rv == 0:
            return '0' if is_direct else '-'
        return _fmt(v)

    for row_type, label, vals in rows:
        if row_type == 'total':
            cells = f'<td style="{ROW_CAL_LBL}">{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_CAL_NUM}">{_fv(v)}</td>'

        elif row_type == 'standalone':
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_HDR_NUM}">{_fv(v)}</td>'

        elif row_type == 'anno':
            lbl_s = _ROW_ANNO
            cells = f'<td style="{lbl_s}">{_I1}({label})</td>'
            for v in vals:
                cells += f'<td style="{_TD_ANNO}">{_fv(v)}</td>'

        elif row_type == 'grp_hdr':
            cells = f'<td colspan="{n_cols}" style="{_ROW_GRP_SPAN}">{label}</td>'

        elif row_type == 'child':
            cells = f'<td style="{ROW_ITEM}">{_I1}{label}</td>'
            for v in vals:
                cells += f'<td style="{_TD_NUM}">{_fv(v, is_direct=True)}</td>'

        elif row_type == 'subtotal':
            cells = f'<td style="{ROW_HDR_LBL}">{_I1}{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_HDR_NUM}">{_fv(v)}</td>'

        body += f'<tr>{cells}</tr>'

    return _html_table(th_html, body)


def _build_인당연장근무시간(year, month):
    df = load_sheet(Sheets.기능직근태현황_DB)
    df = _drop_empty(df, '연도', '월')
    for col in ['구분1', '구분2']:
        df[col] = df[col].fillna('').astype(str).str.strip()

    vm = {}
    for _, row in df.iterrows():
        raw = str(row['값']).strip()
        key = (row['구분1'], row['구분2'], int(row['연도']), int(row['월']))
        vm[key] = None if raw in ('', 'nan', '-') else _parse(raw)

    def get(g1, g2, yr, mo):
        v = vm.get((g1, g2, yr, mo))
        return 0.0 if v is None else v

    years = sorted({yr for (_, _, yr, _) in vm})

    def g2_for(g1):
        return list(dict.fromkeys(
            df[(df['구분1'] == g1) & (df['구분2'] != '')]['구분2'].tolist()
        ))

    def val_g1(g1, yr, mo):
        g2s = g2_for(g1)
        return sum(get(g1, g2, yr, mo) for g2 in g2s) if g2s else get(g1, '', yr, mo)

    def 인원(yr, mo):
        return get(근태_인원수_G1, '', yr, mo)

    def 인당(g1, yr, mo):
        n = 인원(yr, mo)
        return val_g1(g1, yr, mo) / n if n else 0.0

    def yr_avg_인당(g1, yr):
        mos = range(1, 13) if yr < year else range(1, month + 1)
        vals = [인당(g1, yr, mo) for mo in mos]
        cnt = sum(1 for v in vals if v != 0.0)
        return sum(vals) / cnt if cnt else 0.0

    grp_g1s = df[df['구분2'] != '']['구분1'].drop_duplicates().tolist()

    # x축: 연도 평균 + 최근 3개월
    recent = _recent_months(year, month, 3)
    col_keys = [(yr, 'avg') for yr in years] + list(recent)

    col_labels = [f"'{str(yr)[2:]}년 평균" for yr in years]
    last_yr = None
    for yr, mo in recent:
        if yr != last_yr:
            col_labels.append(f"'{str(yr)[2:]}.{mo}월")
            last_yr = yr
        else:
            col_labels.append(f"{mo}월")

    def cell(g1, key):
        if key[1] == 'avg':
            return yr_avg_인당(g1, key[0])
        return 인당(g1, key[0], key[1])

    series = {g1: [cell(g1, ck) for ck in col_keys] for g1 in grp_g1s}

    disp_names = {}
    for g1 in grp_g1s:
        g2s = g2_for(g1)
        if len(g2s) == 1 and '/' in g2s[0]:
            disp_names[g1] = g2s[0].replace('/', '·')
        else:
            disp_names[g1] = '·'.join(g2s) if g2s else g1

    return grp_g1s, disp_names, col_labels, series


def _인당연장근무시간_chart(grp_g1s, disp_names, col_labels, series):
    colors = ['#e53e3e', '#2d3748']
    fig = go.Figure()

    all_vals = [v for vals in series.values() for v in vals if v]
    y_min = min(all_vals) * 0.75 if all_vals else 0
    y_max = max(all_vals) * 1.20 if all_vals else 1

    for i, g1 in enumerate(grp_g1s):
        color = colors[i % len(colors)]
        vals = series[g1]
        fig.add_trace(go.Scatter(
            x=col_labels, y=vals,
            mode='lines+markers+text',
            name=disp_names[g1],
            line=dict(color=color, width=2),
            marker=dict(color=color, size=8),
            text=[f'{v:.1f}' for v in vals],
            textposition='top center',
            textfont=dict(size=11),
        ))

    fig.update_layout(
        height=260,
        margin=dict(l=10, r=10, t=10, b=60),
        plot_bgcolor='white',
        paper_bgcolor='white',
        legend=dict(orientation='h', yanchor='top', y=-0.18, xanchor='center', x=0.5,
                    font=dict(size=11)),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False,
                   range=[y_min, y_max]),
        xaxis=dict(showgrid=False, tickfont=dict(size=10)),
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════
# ── 탭 4: 성과급 설정 현황 ──────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _build_성과격려현황(year, month):
    df = load_sheet(Sheets.성과격려_DB)
    df = _drop_empty(df, '연도', '월')
    for col in ['구분1', '구분2']:
        df[col] = df[col].fillna('').astype(str).str.strip()

    vm = {}
    for _, row in df.iterrows():
        raw = str(row['값']).strip()
        key = (row['구분1'], row['구분2'], int(row['연도']), int(row['월']))
        vm[key] = None if raw in ('', 'nan', '-') else _parse(raw)

    def get(g1, g2, yr, mo):
        v = vm.get((g1, g2, yr, mo))
        return 0.0 if v is None else v

    df_yr = df[df['연도'] == year]
    g1_items = list(dict.fromkeys(df_yr['구분1'].tolist()))

    item_rows = []
    합_당월계획 = 합_당월실적 = 합_누적계획 = 합_누적실적 = 0.0

    for g1 in g1_items:
        당월계획 = get(g1, '계획', year, month)
        당월실적 = get(g1, '실적', year, month)
        당월차이 = 당월실적 - 당월계획
        누적계획 = sum(get(g1, '계획', year, mo) for mo in range(1, month + 1))
        누적실적 = sum(get(g1, '실적', year, mo) for mo in range(1, month + 1))
        누적차이 = 누적실적 - 누적계획
        item_rows.append(('item', g1, [당월계획, 당월실적, 당월차이, 누적계획, 누적실적, 누적차이]))
        합_당월계획 += 당월계획
        합_당월실적 += 당월실적
        합_누적계획 += 누적계획
        합_누적실적 += 누적실적

    합계 = [합_당월계획, 합_당월실적, 합_당월실적 - 합_당월계획,
            합_누적계획, 합_누적실적, 합_누적실적 - 합_누적계획]
    rows = item_rows + [('total', '합계', 합계)]
    return rows


def _성과격려현황_to_html(rows, month):
    _I = '&nbsp;&nbsp;&nbsp;'
    col_headers = ['구분', '당월 계획', '당월 실적', '당월 차이',
                   f'{month}월 누적 계획', f'{month}월 누적 실적', f'{month}월 누적 차이']
    th_html = '<tr>' + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers) + '</tr>'

    body = ''
    for row_type, label, vals in rows:
        if row_type == 'total':
            lbl_s, num_s = ROW_CAL_LBL, ROW_CAL_NUM
            prefix = ''
        else:
            lbl_s, num_s = ROW_HDR_LBL, _TD_NUM
            prefix = _I

        cells = f'<td style="{lbl_s}">{prefix}{label}</td>'
        for v in vals:
            cells += f'<td style="{num_s}">{_fmt(v)}</td>'
        body += f'<tr>{cells}</tr>'

    return _html_table(th_html, body)


# ── render_page ───────────────────────────────────────────────────────────

def render_page(app, year_state, month_state):

    def _render_title():
        app.markdown(
            f'<h1 style="color:#404448">{int(year_state.value)}년 {int(month_state.value)}월 기타</h1>',
            unsafe_allow_html=True,
        )
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["인원현황", "노무비 현황", "기능직 근태현황", "성과급 설정 현황"])

    with tabs[0]:
        def _render_인원현황():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_headers = _build_인원변동내역(year, month)
            memo = _get_memo(Sheets.인원현황_메모, year, month)
            col_l, col_r = app.columns([6, 4])
            with col_l:
                app.markdown(
                    _sec_title('1) 인원 변동내역', '[단위: 명]')
                    + _인원변동내역_to_html(rows, col_headers),
                    unsafe_allow_html=True,
                )
            with col_r:
                if memo:
                    app.markdown(_memo_block(memo), unsafe_allow_html=True)
        app.If(lambda: True, _render_인원현황)

    with tabs[1]:
        def _render_노무비현황():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_headers, 급여_vals, 인당_vals = _build_노무비현황(year, month)
            memo = _get_memo(Sheets.사무직기능직노무비현황_메모, year, month)
            fig  = _노무비현황_chart(col_headers, 급여_vals, 인당_vals)
            col_l, col_r = app.columns([6, 4])
            with col_l:
                app.markdown(
                    _sec_title('1) 사무직∙기능직 노무비 현황', '[단위: 명, 만개, 백만원]')
                    + _fig_to_iframe(fig)
                    + _노무비현황_to_html(rows, col_headers),
                    unsafe_allow_html=True,
                )
            with col_r:
                if memo:
                    app.markdown(_memo_block(memo), unsafe_allow_html=True)
        app.If(lambda: True, _render_노무비현황)

    with tabs[2]:
        def _render_기능직근태현황():
            year, month = int(year_state.value), int(month_state.value)

            # 1) 기능직 근무시간
            rows, col_headers = _build_기능직근무시간(year, month)
            memo = _get_memo(Sheets.기능직근태현황_메모, year, month)
            tbl_html = _기능직근무시간_to_html(rows, col_headers)
            sec = _sec_title('1) 기능직 근무시간', '[단위: 명, 시간]')
            col_l, col_r = app.columns([6, 4])
            with col_l:
                app.markdown(sec + tbl_html, unsafe_allow_html=True)
            with col_r:
                if memo:
                    app.markdown(_memo_block(memo), unsafe_allow_html=True)

            # 2) 인당 연장 근무 시간
            grp_g1s, disp_names, col_labels, series = _build_인당연장근무시간(year, month)
            fig2 = _인당연장근무시간_chart(grp_g1s, disp_names, col_labels, series)
            col_l2, col_r2 = app.columns([6, 4])
            with col_l2:
                app.markdown(
                    _sec_title('2) 인당 연장 근무 시간', '[단위: 시간]')
                    + _fig_to_iframe(fig2),
                    unsafe_allow_html=True,
                )
        app.If(lambda: True, _render_기능직근태현황)

    with tabs[3]:
        def _render_성과급설정현황():
            year, month = int(year_state.value), int(month_state.value)
            rows = _build_성과격려현황(year, month)
            memo = _get_memo(Sheets.성과격려_메모, year, month)
            tbl_html = _성과격려현황_to_html(rows, month)
            col_l, col_r = app.columns([6, 4])
            with col_l:
                app.markdown(
                    _sec_title('1) 성과∙격려 설정 현황', '[단위: 백만원]') + tbl_html,
                    unsafe_allow_html=True,
                )
            with col_r:
                if memo:
                    app.markdown(_memo_block(memo), unsafe_allow_html=True)
        app.If(lambda: True, _render_성과급설정현황)
