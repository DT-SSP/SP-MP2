import datetime
import plotly.graph_objects as go
import pandas as pd
from data.loader import load_sheet
from data.config import (
    Sheets,
    품목별매출_품목_순서, 품목별매출_톤_단위_품목,
)
from views.common import (
    parse as _parse, fmt as _fmt,
    prev_month as _prev, drop_empty as _drop_empty, sort_by_order as _sort,
    TH as _TH, TD_NUM as _TD_NUM, TD_RED as _TD_RED,
    ROW_SEC, ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED, ROW_ITEM,
    html_table as _html_table, layout64 as _layout64,
)


# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────

def _recent_months(year, month, n=5):
    result = []
    y, m = year, month
    for _ in range(n):
        result.insert(0, (y, m))
        y, m = _prev(y, m, 1)
    return result


def _build_col_hdrs(연도_in_db, recent, annual_suffix='년'):
    hdrs = []
    for yr in 연도_in_db:
        hdrs.append(f"'{str(yr)[2:]}{annual_suffix}")
    last_yr = None
    for yr_c, mo_c in recent:
        hdrs.append(f"'{str(yr_c)[2:]}.{mo_c}월" if yr_c != last_yr else f"{mo_c}월")
        last_yr = yr_c
    return hdrs


def _sec_title(title, unit):
    return (
        '<div style="display:flex;justify-content:space-between;'
        'align-items:baseline;margin:20px 0 4px 0">'
        f'<h3 style="margin:0;font-size:1.1em;font-weight:600">{title}</h3>'
        f'<span style="font-size:0.8em;color:gray">{unit}</span>'
        '</div>'
    )


def _memo_html(memo):
    if not memo:
        return ''
    return (
        '<div style="margin-top:20px">'
        f'<p style="margin:0;font-size:0.9em;line-height:1.6;white-space:pre-wrap">{memo}</p>'
        '</div>'
    )


_부산물판매_COL_HDRS = [
    '전월중량', '전월단가', '전월금액',
    '당월중량', '당월단가', '당월금액',
    '전월비중량', '전월비단가', '전월비금액',
]


# ── 공통 로더 ─────────────────────────────────────────────────────────────

def _get_연도_목록():
    df = load_sheet(Sheets.품목별매출_DB)
    return sorted(pd.to_numeric(df['연도'], errors='coerce').dropna().astype(int).unique().tolist())


def _get_memo(sheet_info, year, month):
    df = load_sheet(sheet_info)
    df['연도'] = df['연도'].astype(str).str.strip()
    df['월']   = df['월'].astype(str).str.strip()
    row = df[(df['연도'] == str(year)) & (df['월'] == str(month))]
    return str(row.iloc[0]['메모']) if not row.empty else ''


# ── 1) 품목별 매출 ──────────────────────────────────────────────────────────

def _build_품목별매출(year, month):
    df = load_sheet(Sheets.품목별매출_DB)
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)

    vm = df.set_index(['구분1', '구분2', '연도', '월'])['값'].to_dict()
    prev_yr, prev_mo = _prev(year, month, 1)
    yr1, yr2 = year - 2, year - 1

    # DB에서 품목 목록 자동 감지 (소급 제외) → config 순서대로 정렬, 미등록 품목은 뒤에
    db_품목 = [p for p in df[df['구분1'] == '매출액']['구분2'].unique()
               if not str(p).endswith('소급')]
    품목_list = _sort(db_품목, 품목별매출_품목_순서)

    # 판매량 데이터가 있는 품목만 단가/판매량 행 표시
    단가_품목 = set(df[df['구분1'] == '판매량']['구분2'].unique())

    # 합계 판매량: 단가 있는 품목 중 톤 단위 제외 (만개 단위만)
    합계_판매량_품목 = 단가_품목 - 품목별매출_톤_단위_품목

    def raw_g(품목, yr, mo):
        base = vm.get(('매출액', 품목, yr, mo), 0.0)
        소급 = vm.get(('매출액', f'{품목}소급', yr, mo), 0.0)
        return base + 소급

    def raw_q(품목, yr, mo):
        return vm.get(('판매량', 품목, yr, mo), 0.0)  # DB 원값 그대로 (톤 or 개)

    def yr_g(품목, yr):
        return sum(raw_g(품목, yr, m) for m in range(1, 13))

    def yr_q(품목, yr):
        return sum(raw_q(품목, yr, m) for m in range(1, 13))

    def ytd_g(품목):
        return sum(raw_g(품목, year, m) for m in range(1, month + 1))

    def ytd_q(품목):
        return sum(raw_q(품목, year, m) for m in range(1, month + 1))

    def dp(g, q):
        return g / q if q else 0.0

    rows = []

    for 품목 in 품목_list:
        rows.append(('section', 품목))

        g1 = yr_g(품목, yr1) / 1e6
        g2 = yr_g(품목, yr2) / 1e6
        gp = raw_g(품목, prev_yr, prev_mo) / 1e6
        gc = raw_g(품목, year, month) / 1e6
        gy = ytd_g(품목) / 1e6
        rows.append(('sub', '금액', g1, g2, gp, gc, gc - gp, gy))

        if 품목 in 단가_품목:
            is_톤 = (품목 in 품목별매출_톤_단위_품목)
            sc = 1.0 if is_톤 else 1 / 1e4  # 톤: 그대로, 개: 만개 변환

            q1 = yr_q(품목, yr1) * sc
            q2 = yr_q(품목, yr2) * sc
            qp = raw_q(품목, prev_yr, prev_mo) * sc
            qc = raw_q(품목, year, month) * sc
            qy = ytd_q(품목) * sc

            # 단가 분모: 부산물은 톤→kg(*1000)으로 원/kg, 나머지는 개 그대로 원/개
            dsc = 1000 if is_톤 else 1
            d1  = dp(yr_g(품목, yr1),              yr_q(품목, yr1)              * dsc)
            d2  = dp(yr_g(품목, yr2),              yr_q(품목, yr2)              * dsc)
            dp_ = dp(raw_g(품목, prev_yr, prev_mo), raw_q(품목, prev_yr, prev_mo) * dsc)
            dc  = dp(raw_g(품목, year, month),      raw_q(품목, year, month)      * dsc)
            dy  = dp(ytd_g(품목),                   ytd_q(품목)                  * dsc)

            rows.append(('sub', '단가', d1, d2, dp_, dc, dc - dp_, dy))
            rows.append(('sub', '판매량(톤)' if is_톤 else '판매량',
                         q1, q2, qp, qc, qc - qp, qy))

    # 합계
    rows.append(('section', '합계'))

    def tot_g(yr, mo=None):
        if mo is None:
            return sum(yr_g(p, yr) for p in 품목_list)
        return sum(raw_g(p, yr, mo) for p in 품목_list)

    def tot_q(yr, mo=None):
        if mo is None:
            return sum(yr_q(p, yr) for p in 합계_판매량_품목)
        return sum(raw_q(p, yr, mo) for p in 합계_판매량_품목)

    def ytd_tot_g():
        return sum(ytd_g(p) for p in 품목_list)

    def ytd_tot_q():
        return sum(ytd_q(p) for p in 합계_판매량_품목)

    tg1, tg2 = tot_g(yr1) / 1e6, tot_g(yr2) / 1e6
    tgp, tgc = tot_g(prev_yr, prev_mo) / 1e6, tot_g(year, month) / 1e6
    tgy = ytd_tot_g() / 1e6

    tq1, tq2 = tot_q(yr1) / 1e4, tot_q(yr2) / 1e4
    tqp, tqc = tot_q(prev_yr, prev_mo) / 1e4, tot_q(year, month) / 1e4
    tqy = ytd_tot_q() / 1e4

    td1  = dp(tot_g(yr1),              tot_q(yr1))
    td2  = dp(tot_g(yr2),              tot_q(yr2))
    tdp_ = dp(tot_g(prev_yr, prev_mo), tot_q(prev_yr, prev_mo))
    tdc  = dp(tot_g(year, month),      tot_q(year, month))
    tdy  = dp(ytd_tot_g(),             ytd_tot_q())

    rows.append(('total', '금액',   tg1, tg2, tgp, tgc, tgc - tgp, tgy))
    rows.append(('total', '단가',   td1, td2, tdp_, tdc, tdc - tdp_, tdy))
    rows.append(('total', '판매량', tq1, tq2, tqp, tqc, tqc - tqp, tqy))

    col_yr1  = f"'{str(yr1)[2:]}년"
    col_yr2  = f"'{str(yr2)[2:]}년"
    col_전월 = f"'{str(prev_yr)[2:]}년 {prev_mo}월" if prev_yr != year else f"{prev_mo}월"
    col_당월 = f"{month}월"

    return rows, ['구분', col_yr1, col_yr2, col_전월, col_당월, '전월대비', '누계']


def _품목별매출_to_html(rows, col_headers):
    n_cols  = len(col_headers)
    th_html = f'<tr>{"".join(f"<th style=\"{_TH}\">{h}</th>" for h in col_headers)}</tr>'

    body_html = ''
    sub_idx   = 0

    for row in rows:
        if row[0] == 'section':
            sub_idx = 0
            body_html += f'<tr><td colspan="{n_cols}" style="{ROW_SEC}">{row[1]}</td></tr>'
        elif row[0] == 'sub':
            _, label, *vals = row
            bg = ';background:#f9f9fb' if sub_idx % 2 == 1 else ''
            sub_idx += 1
            cells = f'<td style="{ROW_ITEM + bg}">{label}</td>'
            for v in vals:
                cells += f'<td style="{(_TD_RED if v < 0 else _TD_NUM) + bg}">{_fmt(v)}</td>'
            body_html += f'<tr>{cells}</tr>'
        elif row[0] == 'total':
            _, label, *vals = row
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_HDR_RED if v < 0 else ROW_HDR_NUM}">{_fmt(v)}</td>'
            body_html += f'<tr>{cells}</tr>'

    return _html_table(th_html, body_html)


# ── 판매구성 - 1) 제품별 판매현황 ─────────────────────────────────────────

def _build_판매구성_제품별(year, month):
    df = load_sheet(Sheets.판매구성_DB)
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)

    pdf = df[(df['구분1'] == '제품') & (df['구분2'] == '판매량') &
             (df['구분3'].isin(['열전', '열후']))]
    vm = pdf.set_index(['구분3', '연도', '월'])['값'].to_dict()

    def raw(품목, yr, mo):
        return vm.get((품목, yr, mo), 0.0)

    def yr_avg(품목, yr):
        vals = [raw(품목, yr, m) for m in range(1, 13) if raw(품목, yr, m) > 0]
        return sum(vals) / len(vals) if vals else 0.0

    연도_in_db = sorted(pdf['연도'].unique().tolist())
    recent = _recent_months(year, month)
    col_hdrs = _build_col_hdrs(연도_in_db, recent)

    data = {}
    for 품목 in ['열전', '열후']:
        vals = [yr_avg(품목, yr) / 1e4 for yr in 연도_in_db]
        vals += [raw(품목, yr_c, mo_c) / 1e4 for yr_c, mo_c in recent]
        data[품목] = vals

    n = len(연도_in_db) + len(recent)
    계_vals  = [data['열전'][i] + data['열후'][i] for i in range(n)]
    비중_vals = [
        data['열후'][i] / 계_vals[i] * 100 if 계_vals[i] else 0.0
        for i in range(n)
    ]

    rows = [
        ('sub',   '열전',    data['열전']),
        ('sub',   '열후',    data['열후']),
        ('total', '계',      계_vals),
        ('pct',   '열후비중', 비중_vals),
    ]
    return rows, col_hdrs, data, 계_vals, 비중_vals


def _판매구성_제품별_to_html(rows, col_hdrs):
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in ['구분'] + col_hdrs)
    body = ''
    sub_idx = 0
    for kind, label, vals in rows:
        if kind == 'sub':
            bg = ';background:#f9f9fb' if sub_idx % 2 else ''
            sub_idx += 1
            cells = f'<td style="{ROW_ITEM + bg}">{label}</td>'
            cells += ''.join(f'<td style="{_TD_NUM + bg}">{_fmt(v)}</td>' for v in vals)
        elif kind == 'total':
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            cells += ''.join(f'<td style="{ROW_HDR_NUM}">{_fmt(v)}</td>' for v in vals)
        elif kind == 'pct':
            cells = f'<td style="{ROW_ITEM}">{label}</td>'
            cells += ''.join(
                f'<td style="{_TD_NUM}">{_fmt(v, is_pct=True, decimal=1)}%</td>'
                for v in vals
            )
        body += f'<tr>{cells}</tr>'
    return _html_table(f'<tr>{th}</tr>', body)


def _build_제품별판매_chart(x_labels, data, 계_vals, 비중_vals):
    fig = go.Figure()

    # 열전: 짙은 보라 (TH 색과 동일)
    fig.add_trace(go.Bar(
        name='열전', x=x_labels, y=data['열전'],
        marker_color='#6b46c1',
        marker_line_width=0,
        text=[str(round(v)) for v in data['열전']],
        textposition='inside',
        textfont=dict(color='white', size=13),
    ))
    # 열후: 연보라
    fig.add_trace(go.Bar(
        name='열후', x=x_labels, y=data['열후'],
        marker_color='#a78bfa',
        marker_line_width=0,
        text=[str(round(v)) for v in data['열후']],
        textposition='inside',
        textfont=dict(color='white', size=13),
    ))
    # 열후비중: 앰버 라인 (보라와 대비)
    fig.add_trace(go.Scatter(
        name='열후비중',
        x=x_labels, y=비중_vals,
        mode='lines+markers+text',
        line=dict(color='#d97706', width=2),
        marker=dict(color='white', size=7,
                    line=dict(color='#d97706', width=2)),
        text=[f"{v:.1f}%" for v in 비중_vals],
        textposition='top center',
        textfont=dict(size=12, color='#92400e'),
        yaxis='y2',
    ))

    max_계   = max(계_vals)   if 계_vals   else 50
    min_비중 = min(비중_vals) if 비중_vals else 0
    max_비중 = max(비중_vals) if 비중_vals else 50

    # 바: 하단 40%, 라인: 50~90% 구간 (40% 차지)
    #   좌축 max = max_계 × 2.5  →  바 상단 = 40% 높이
    #   라인 min → 50% 높이, max → 90% 높이
    data_range = max(max_비중 - min_비중, 5)
    y2_total   = data_range / 0.40   # 데이터가 차트의 40% 차지
    ymin2      = min_비중 - 0.50 * y2_total   # min이 50% 높이
    ymax2      = ymin2 + y2_total

    # 우축 눈금: 데이터 범위만 표시
    step = max(2, int(data_range / 4))
    t_min = (int(min_비중) // step) * step
    t_max = (int(max_비중) // step + 2) * step
    tick_vals = [v for v in range(t_min, t_max + 1, step) if v >= 0]

    fig.update_layout(
        barmode='stack',
        height=380,
        margin=dict(l=10, r=45, t=15, b=60),
        legend=dict(
            orientation='h', y=-0.28, x=0.5, xanchor='center',
            font=dict(size=12),
            bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            tickfont=dict(size=11, color='#4a5568'),
            showgrid=False,
            linecolor='#e2e8f0',
            linewidth=1,
            showline=True,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#f0edf8',
            gridwidth=1,
            range=[0, max_계 * 2.5],
            tickfont=dict(size=11, color='#4a5568'),
            showline=False,
            zeroline=False,
        ),
        yaxis2=dict(
            overlaying='y', side='right',
            range=[ymin2, ymax2],
            tickvals=tick_vals,
            ticktext=[f"{v}%" for v in tick_vals],
            showgrid=False,
            tickfont=dict(size=11, color='#b45309'),
            showline=False,
            zeroline=False,
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig


# ── 판매구성 - 2) 부산물 매출 판매 현황 ────────────────────────────────────

def _build_부산물매출(year, month):
    df = load_sheet(Sheets.부산물매출_DB)
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)

    vm = df.set_index(['구분1', '연도', '월'])['값'].to_dict()

    def raw(구분, yr, mo):
        return vm.get((구분, yr, mo), 0.0)

    연도_in_db = sorted(df['연도'].unique().tolist())
    recent = _recent_months(year, month)
    col_hdrs = _build_col_hdrs(연도_in_db, recent)

    중량_vals, 금액_vals, 단가_vals = [], [], []

    for yr in 연도_in_db:
        ws = [v for m in range(1, 13) if (v := raw('중량', yr, m)) > 0]
        gs = [v for m in range(1, 13) if (v := raw('금액', yr, m)) > 0]
        total_w, total_g = sum(ws), sum(gs)
        중량_vals.append(sum(ws) / len(ws) if ws else 0.0)
        금액_vals.append(sum(gs) / len(gs) if gs else 0.0)
        단가_vals.append(total_g * 1000 / total_w if total_w else 0.0)

    for yr_c, mo_c in recent:
        w = raw('중량', yr_c, mo_c)
        g = raw('금액', yr_c, mo_c)
        중량_vals.append(w)
        금액_vals.append(g)
        단가_vals.append(g * 1000 / w if w else 0.0)

    rows = [
        ('sub', '중량',     중량_vals),
        ('sub', '금액',     금액_vals),
        ('sub', '단가(원)', 단가_vals),
    ]
    return rows, col_hdrs, 중량_vals, 단가_vals


def _부산물매출_to_html(rows, col_hdrs):
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in ['구분'] + col_hdrs)
    body = ''
    sub_idx = 0
    for _, label, vals in rows:
        bg = ';background:#f9f9fb' if sub_idx % 2 else ''
        sub_idx += 1
        cells = f'<td style="{ROW_ITEM + bg}">{label}</td>'
        cells += ''.join(f'<td style="{_TD_NUM + bg}">{_fmt(v)}</td>' for v in vals)
        body += f'<tr>{cells}</tr>'
    return _html_table(f'<tr>{th}</tr>', body)


def _build_부산물매출_chart(x_labels, 중량_vals, 단가_vals):
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='중량(톤)',
        x=x_labels, y=중량_vals,
        marker_color='#6b46c1',
        marker_line_width=0,
        text=[str(round(v)) for v in 중량_vals],
        textposition='inside',
        textfont=dict(color='white', size=13),
    ))
    fig.add_trace(go.Scatter(
        name='단가(원)',
        x=x_labels, y=단가_vals,
        mode='lines+markers+text',
        line=dict(color='#d97706', width=2),
        marker=dict(color='white', size=7, line=dict(color='#d97706', width=2)),
        text=[str(round(v)) for v in 단가_vals],
        textposition='top center',
        textfont=dict(size=12, color='#92400e'),
        yaxis='y2',
    ))

    max_중량 = max(중량_vals) if 중량_vals else 300
    min_단가 = min(단가_vals) if 단가_vals else 0
    max_단가 = max(단가_vals) if 단가_vals else 400

    data_range = max(max_단가 - min_단가, 20)
    y2_total = data_range / 0.40
    ymin2    = min_단가 - 0.50 * y2_total
    ymax2    = ymin2 + y2_total

    step = max(20, int(data_range / 4))
    t_min = (int(min_단가) // step) * step
    t_max = (int(max_단가) // step + 2) * step
    tick_vals = [v for v in range(t_min, t_max + 1, step) if v >= 0]

    fig.update_layout(
        height=380,
        margin=dict(l=10, r=50, t=15, b=60),
        legend=dict(
            orientation='h', y=-0.28, x=0.5, xanchor='center',
            font=dict(size=12), bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            tickfont=dict(size=11, color='#4a5568'),
            showgrid=False, linecolor='#e2e8f0', linewidth=1, showline=True,
        ),
        yaxis=dict(
            showgrid=True, gridcolor='#f0edf8', gridwidth=1,
            range=[0, max_중량 * 2.5],
            tickfont=dict(size=11, color='#4a5568'),
            showline=False, zeroline=False,
        ),
        yaxis2=dict(
            overlaying='y', side='right',
            range=[ymin2, ymax2],
            tickvals=tick_vals,
            ticktext=[str(v) for v in tick_vals],
            showgrid=False,
            tickfont=dict(size=11, color='#b45309'),
            showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig


# ── 판매구성 - 3) 총 투입량 대비 부산물 중량 변동 추이 ────────────────────

def _build_부산물증량(year, month):
    df = load_sheet(Sheets.부산물증량_DB)
    df = _drop_empty(df, '연도', '월')
    df['실적'] = df['실적'].apply(_parse)

    vm = df.set_index(['구분1', '구분2', '연도', '월'])['실적'].to_dict()

    def raw(g1, g2, yr, mo):
        return vm.get((g1, g2, yr, mo), 0.0)

    def 환산중량(yr, mo):
        b = raw('원자재 출고', '랙바',      yr, mo)
        s = raw('원자재 출고', '랙바(사급)', yr, mo)
        p = raw('원자재 출고', '피니언',    yr, mo)
        return b + (s * 3.3 * 10) + (p * 0.276 * 10)

    def yr_avg(g1, g2, yr):
        vals = [v for m in range(1, 13) if (v := raw(g1, g2, yr, m)) > 0]
        return sum(vals) / len(vals) if vals else 0.0

    def yr_avg_환산(yr):
        vals = [v for m in range(1, 13) if (v := 환산중량(yr, m)) > 0]
        return sum(vals) / len(vals) if vals else 0.0

    연도_in_db = sorted(df['연도'].unique().tolist())
    recent = _recent_months(year, month)
    col_hdrs = _build_col_hdrs(연도_in_db, recent)

    rows = []

    # 원자재 출고 섹션
    rows.append(('sec', '원자재 출고'))
    for g2, dec in [('랙바', 0), ('랙바(사급)', 1), ('피니언', 1)]:
        vals = [yr_avg('원자재 출고', g2, yr) for yr in 연도_in_db]
        vals += [raw('원자재 출고', g2, yr_c, mo_c) for yr_c, mo_c in recent]
        rows.append(('item', g2, vals, dec))

    # 환산중량 합계행
    환산_vals = [yr_avg_환산(yr) for yr in 연도_in_db]
    환산_vals += [환산중량(yr_c, mo_c) for yr_c, mo_c in recent]
    rows.append(('total', '환산중량', 환산_vals, 0))

    # 부산물 섹션
    rows.append(('sec', '부산물'))
    판매량_vals = [yr_avg('부산물', '판매량', yr) for yr in 연도_in_db]
    판매량_vals += [raw('부산물', '판매량', yr_c, mo_c) for yr_c, mo_c in recent]
    rows.append(('item', '판매량', 판매량_vals, 0))

    출고대비_vals = [
        판매량_vals[i] / 환산_vals[i] * 100 if 환산_vals[i] else 0.0
        for i in range(len(판매량_vals))
    ]
    rows.append(('pct', '(출고대비)', 출고대비_vals))

    매출액_vals = [yr_avg('부산물', '매출액', yr) for yr in 연도_in_db]
    매출액_vals += [raw('부산물', '매출액', yr_c, mo_c) for yr_c, mo_c in recent]
    rows.append(('item', '매출액', 매출액_vals, 0))

    return rows, col_hdrs, 환산_vals, 판매량_vals, 매출액_vals


def _부산물증량_to_html(rows, col_hdrs):
    n = len(col_hdrs) + 1
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in ['구분'] + col_hdrs)
    body = ''
    sub_idx = 0
    for row in rows:
        kind = row[0]
        if kind == 'sec':
            sub_idx = 0
            body += f'<tr><td colspan="{n}" style="{ROW_SEC}">{row[1]}</td></tr>'
        elif kind == 'item':
            _, label, vals, dec = row
            bg = ';background:#f9f9fb' if sub_idx % 2 else ''
            sub_idx += 1
            cells = f'<td style="{ROW_ITEM + bg}">{label}</td>'
            cells += ''.join(
                f'<td style="{_TD_NUM + bg}">{_fmt(v, decimal=dec)}</td>' for v in vals
            )
            body += f'<tr>{cells}</tr>'
        elif kind == 'total':
            _, label, vals, dec = row
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            cells += ''.join(
                f'<td style="{ROW_HDR_NUM}">{_fmt(v, decimal=dec)}</td>' for v in vals
            )
            body += f'<tr>{cells}</tr>'
        elif kind == 'pct':
            _, label, vals = row
            bg = ';background:#f9f9fb' if sub_idx % 2 else ''
            sub_idx += 1
            cells = f'<td style="{ROW_ITEM + bg}">{label}</td>'
            cells += ''.join(
                f'<td style="{_TD_NUM + bg}">{_fmt(v, is_pct=True, decimal=1)}%</td>'
                for v in vals
            )
            body += f'<tr>{cells}</tr>'
    return _html_table(f'<tr>{th}</tr>', body)


def _build_부산물증량_chart(x_labels, 환산_vals, 판매량_vals, 매출액_vals):
    fig = go.Figure()
    # 바: y1 (좌측)
    fig.add_trace(go.Bar(
        name='원자재 출고(환산중량)',
        x=x_labels, y=환산_vals,
        marker_color='#6b46c1', marker_line_width=0,
        text=[str(round(v)) for v in 환산_vals],
        textposition='inside',
        textfont=dict(color='white', size=13),
    ))
    # 두 라인: y2 (우측) — 바 스케일에 묻히지 않도록 분리
    fig.add_trace(go.Scatter(
        name='부산물 판매량',
        x=x_labels, y=판매량_vals,
        mode='lines+markers+text',
        line=dict(color='#d97706', width=2),
        marker=dict(color='white', size=7, line=dict(color='#d97706', width=2)),
        text=[str(round(v)) for v in 판매량_vals],
        textposition='top center',
        textfont=dict(size=12, color='#92400e'),
        yaxis='y2',
    ))
    fig.add_trace(go.Scatter(
        name='부산물 매출액',
        x=x_labels, y=매출액_vals,
        mode='lines+markers+text',
        line=dict(color='#9ca3af', width=2),
        marker=dict(color='white', size=7, line=dict(color='#9ca3af', width=2)),
        text=[str(round(v)) for v in 매출액_vals],
        textposition='top center',
        textfont=dict(size=12, color='#6b7280'),
        yaxis='y2',
    ))

    max_환산 = max(환산_vals) if 환산_vals else 1500

    # y2: 두 라인 모두 포함하는 범위로 바 위에 띄우기
    # (바: 하단 40%, 라인 전체: 50~90%)
    all_line = [v for v in 판매량_vals + 매출액_vals if v > 0]
    min_line  = min(all_line) if all_line else 0
    max_line  = max(all_line) if all_line else 300
    dr        = max(max_line - min_line, 20)
    y2_total  = dr / 0.40
    ymin2     = min_line - 0.50 * y2_total
    ymax2     = ymin2 + y2_total

    fig.update_layout(
        height=380,
        margin=dict(l=10, r=20, t=15, b=60),
        legend=dict(
            orientation='h', y=-0.28, x=0.5, xanchor='center',
            font=dict(size=12), bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            tickfont=dict(size=11, color='#4a5568'),
            showgrid=False, linecolor='#e2e8f0', linewidth=1, showline=True,
        ),
        yaxis=dict(
            showgrid=True, gridcolor='#f0edf8', gridwidth=1,
            range=[0, max_환산 * 2.5],
            showticklabels=False,
            showline=False, zeroline=False,
        ),
        yaxis2=dict(
            overlaying='y', side='right',
            range=[ymin2, ymax2],
            showticklabels=False,
            showgrid=False, showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig


# ── 판매구성 - 4) 전월대비 부산물 판매 차이 ────────────────────────────────────

def _build_부산물판매(year, month):
    df = load_sheet(Sheets.부산물판매_DB)
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)

    vm = df.set_index(['구분1', '구분2', '연도', '월'])['값'].to_dict()
    prev_yr, prev_mo = _prev(year, month, 1)

    def raw(g1, g2, yr, mo):
        return vm.get((g1, g2, yr, mo), 0.0)

    def 단가(g1, yr, mo):
        w = raw(g1, '중량', yr, mo)
        return raw(g1, '금액', yr, mo) / w * 1000 if w else 0.0

    def 평균단가(yr, mo):
        w = raw('합금', '중량', yr, mo) + raw('분철', '중량', yr, mo)
        g = raw('합금', '금액', yr, mo) + raw('분철', '금액', yr, mo)
        return g / w * 1000 if w else 0.0

    def row_vals(g1):
        pw = raw(g1, '중량', prev_yr, prev_mo)
        pg = raw(g1, '금액', prev_yr, prev_mo)
        pd_ = 단가(g1, prev_yr, prev_mo)
        cw = raw(g1, '중량', year, month)
        cg = raw(g1, '금액', year, month)
        cd = 단가(g1, year, month)
        return [pw, pd_, pg, cw, cd, cg, cw - pw, cd - pd_, cg - pg]

    합금_v = row_vals('합금')
    분철_v = row_vals('분철')
    pw_tot = 합금_v[0] + 분철_v[0]
    pg_tot = 합금_v[2] + 분철_v[2]
    cw_tot = 합금_v[3] + 분철_v[3]
    cg_tot = 합금_v[5] + 분철_v[5]
    pd_tot = 평균단가(prev_yr, prev_mo)
    cd_tot = 평균단가(year, month)
    합계_v = [pw_tot, pd_tot, pg_tot, cw_tot, cd_tot, cg_tot,
              cw_tot - pw_tot, cd_tot - pd_tot, cg_tot - pg_tot]

    rows = [
        ('item', '합금', 합금_v),
        ('item', '분철', 분철_v),
        ('total', '합계', 합계_v),
    ]

    # 차트: 연도별 평균 + 최근 5개월 단가 추이
    연도_in_db = sorted(df['연도'].unique().tolist())
    recent = _recent_months(year, month)

    def yr_단가(g1, yr):
        w = sum(raw(g1, '중량', yr, m) for m in range(1, 13))
        g = sum(raw(g1, '금액', yr, m) for m in range(1, 13))
        return g / w * 1000 if w else 0.0

    def yr_평균단가(yr):
        w = sum(raw('합금', '중량', yr, m) + raw('분철', '중량', yr, m) for m in range(1, 13))
        g = sum(raw('합금', '금액', yr, m) + raw('분철', '금액', yr, m) for m in range(1, 13))
        return g / w * 1000 if w else 0.0

    x_hdrs = _build_col_hdrs(연도_in_db, recent)
    합금_t = [yr_단가('합금', yr) for yr in 연도_in_db] + [단가('합금', y, m) for y, m in recent]
    분철_t = [yr_단가('분철', yr) for yr in 연도_in_db] + [단가('분철', y, m) for y, m in recent]
    평균_t = [yr_평균단가(yr) for yr in 연도_in_db] + [평균단가(y, m) for y, m in recent]

    return rows, x_hdrs, 합금_t, 분철_t, 평균_t


def _부산물판매_to_html(rows):
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in ['구분'] + _부산물판매_COL_HDRS)
    body = ''
    for kind, label, vals in rows:
        if kind == 'item':
            cells = f'<td style="{ROW_ITEM}">{label}</td>'
            for v in vals:
                s = _TD_RED if v < 0 else _TD_NUM
                cells += f'<td style="{s}">{_fmt(v)}</td>'
        else:
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            for v in vals:
                s = ROW_HDR_RED if v < 0 else ROW_HDR_NUM
                cells += f'<td style="{s}">{_fmt(v)}</td>'
        body += f'<tr>{cells}</tr>'
    return _html_table(f'<tr>{th}</tr>', body)


def _build_부산물판매_chart(x_labels, 합금단가, 분철단가, 평균단가):
    fig = go.Figure()
    traces = [
        ('합금단가', 합금단가, '#4c1d95', 'top center'),
        ('분철단가', 분철단가, '#a78bfa', 'bottom center'),
        ('평균단가', 평균단가, '#e53e3e', 'top center'),
    ]
    for name, vals, color, pos in traces:
        fig.add_trace(go.Scatter(
            name=name, x=x_labels, y=vals,
            mode='lines+markers+text',
            line=dict(color=color, width=2),
            marker=dict(color='white', size=7, line=dict(color=color, width=2)),
            text=[str(round(v)) if v else '' for v in vals],
            textposition=pos,
            textfont=dict(size=12, color=color),
        ))

    all_v = [v for v in 합금단가 + 분철단가 + 평균단가 if v > 0]
    min_v = min(all_v) if all_v else 0
    max_v = max(all_v) if all_v else 500
    pad   = (max_v - min_v) * 0.35

    fig.update_layout(
        height=320,
        margin=dict(l=10, r=20, t=15, b=60),
        legend=dict(
            orientation='h', y=-0.28, x=0.5, xanchor='center',
            font=dict(size=12), bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            tickfont=dict(size=11, color='#4a5568'),
            showgrid=False, linecolor='#e2e8f0', linewidth=1, showline=True,
        ),
        yaxis=dict(
            showgrid=True, gridcolor='#f0edf8', gridwidth=1,
            range=[min_v - pad, max_v + pad],
            showticklabels=False,
            showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig


# ── 판매구성 - 5) 만도 사급 매출 현황 ─────────────────────────────────────────

def _build_만도사급(year, month):
    df = load_sheet(Sheets.판매구성_DB)
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    df_s = df[df['구분1'] == '사급'].copy()
    vm = df_s.set_index(['구분2', '구분3', '연도', '월'])['값'].to_dict()

    def raw(g2, g3, yr, mo):
        return vm.get((g2, g3, yr, mo), 0.0)

    def 금액_원(prod, yr, mo):
        if prod == '피니언':
            return raw('매출액', '피니언-선삭', yr, mo) + raw('매출액', '피니언-열처리', yr, mo)
        return raw('매출액', prod, yr, mo)

    def 판매량_개(prod, yr, mo):
        if prod == '피니언':
            return raw('판매량', '피니언-선삭', yr, mo) + raw('판매량', '피니언-열처리', yr, mo)
        return raw('판매량', prod, yr, mo)

    def 단가(prod, yr, mo):
        q = 판매량_개(prod, yr, mo)
        return 금액_원(prod, yr, mo) / q if q else 0.0

    products = ['열전', '열후', '피니언']

    연도_in_db = sorted(df['연도'].unique().tolist())
    recent = _recent_months(year, month)
    col_hdrs = _build_col_hdrs(연도_in_db, recent, annual_suffix='.평균')

    rows = []
    금액_by_prod = {}

    for prod in products:
        rows.append(('sec', prod, []))
        g_vals, d_vals, q_vals = [], [], []

        for yr in 연도_in_db:
            g_yr = sum(금액_원(prod, yr, m) for m in range(1, 13))
            q_yr = sum(판매량_개(prod, yr, m) for m in range(1, 13))
            g_vals.append(g_yr / 12 / 1e6)
            d_vals.append(g_yr / q_yr if q_yr else 0.0)
            q_vals.append(q_yr / 12 / 1e4)

        for yr_c, mo_c in recent:
            g_vals.append(금액_원(prod, yr_c, mo_c) / 1e6)
            d_vals.append(단가(prod, yr_c, mo_c))
            q_vals.append(판매량_개(prod, yr_c, mo_c) / 1e4)

        금액_by_prod[prod] = g_vals
        rows.append(('item', '금액', g_vals))
        rows.append(('item', '단가', d_vals))
        rows.append(('item', '판매량', q_vals))

    # 합계
    rows.append(('sec', '합계', []))
    tot_g_v, tot_d_v, tot_q_v = [], [], []

    for yr in 연도_in_db:
        g_tot = sum(금액_원(p, yr, m) for p in products for m in range(1, 13))
        q_tot = sum(판매량_개(p, yr, m) for p in products for m in range(1, 13))
        tot_g_v.append(g_tot / 12 / 1e6)
        tot_d_v.append(g_tot / q_tot if q_tot else 0.0)
        tot_q_v.append(q_tot / 12 / 1e4)

    for yr_c, mo_c in recent:
        g_tot = sum(금액_원(p, yr_c, mo_c) for p in products)
        q_tot = sum(판매량_개(p, yr_c, mo_c) for p in products)
        tot_g_v.append(g_tot / 1e6)
        tot_d_v.append(g_tot / q_tot if q_tot else 0.0)
        tot_q_v.append(q_tot / 1e4)

    rows.append(('total', '금액', tot_g_v))
    rows.append(('total', '단가', tot_d_v))
    rows.append(('total', '판매량', tot_q_v))

    return rows, col_hdrs, 금액_by_prod['열전'], 금액_by_prod['열후'], 금액_by_prod['피니언']


def _만도사급_to_html(rows, col_hdrs):
    ncols = len(col_hdrs)
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in ['구분'] + col_hdrs)
    body = ''
    for kind, label, vals in rows:
        dec = 1 if label == '판매량' else 0
        if kind == 'sec':
            body += f'<tr><td colspan="{ncols + 1}" style="{ROW_SEC}">{label}</td></tr>'
        elif kind == 'item':
            cells = f'<td style="{ROW_ITEM}">{label}</td>'
            for v in vals:
                cells += f'<td style="{_TD_NUM}">{_fmt(v, decimal=dec)}</td>'
            body += f'<tr>{cells}</tr>'
        elif kind == 'total':
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_HDR_NUM}">{_fmt(v, decimal=dec)}</td>'
            body += f'<tr>{cells}</tr>'
    return _html_table(f'<tr>{th}</tr>', body)


# ── 판매구성 - 6) 양산차종 매출 현황 ─────────────────────────────────────────

def _build_양산차종(year, month):
    df = load_sheet(Sheets.판매구성_DB)
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    df_p = df[(df['구분1'] == '제품') & (df['구분2'] == '판매량')].copy()
    vm = df_p.set_index(['구분3', '연도', '월'])['값'].to_dict()

    def raw(g3, yr, mo):
        return vm.get((g3, yr, mo), 0.0)

    연도_in_db = sorted(df['연도'].unique().tolist())
    recent = _recent_months(year, month)
    col_hdrs = _build_col_hdrs(연도_in_db, recent, annual_suffix='.평균')

    양산_v, as_v, 합계_v, 비중_v = [], [], [], []

    for yr in 연도_in_db:
        s = sum(raw('양산', yr, m) for m in range(1, 13)) / 12 / 1e4
        a = sum(raw('AS', yr, m) for m in range(1, 13)) / 12 / 1e4
        t = s + a
        양산_v.append(s); as_v.append(a); 합계_v.append(t)
        비중_v.append(s / t * 100 if t else 0.0)

    for yr_c, mo_c in recent:
        s = raw('양산', yr_c, mo_c) / 1e4
        a = raw('AS', yr_c, mo_c) / 1e4
        t = s + a
        양산_v.append(s); as_v.append(a); 합계_v.append(t)
        비중_v.append(s / t * 100 if t else 0.0)

    rows = [
        ('item', '양산차종', 양산_v),
        ('item', 'AS 차종', as_v),
        ('total', '합계', 합계_v),
        ('pct', '양산차종 비중', 비중_v),
    ]
    return rows, col_hdrs, 양산_v, as_v, 비중_v


def _양산차종_to_html(rows, col_hdrs):
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in ['구분'] + col_hdrs)
    body = ''
    for kind, label, vals in rows:
        if kind == 'item':
            cells = f'<td style="{ROW_ITEM}">{label}</td>'
            for v in vals:
                cells += f'<td style="{_TD_NUM}">{_fmt(v)}</td>'
        elif kind in ('total', 'pct'):
            suffix = '%' if kind == 'pct' else ''
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            cells += ''.join(f'<td style="{ROW_HDR_NUM}">{_fmt(v)}{suffix}</td>' for v in vals)
        body += f'<tr>{cells}</tr>'
    return _html_table(f'<tr>{th}</tr>', body)


def _build_양산차종_chart(x_labels, 양산_vals, as_vals, 비중_vals):
    totals = [y + a for y, a in zip(양산_vals, as_vals)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='양산차종', x=x_labels, y=양산_vals,
        marker_color='#6b46c1', marker_line_width=0,
        text=[str(round(v)) for v in 양산_vals],
        textposition='inside', textfont=dict(color='white', size=13),
        insidetextanchor='middle',
    ))
    fig.add_trace(go.Bar(
        name='AS 차종', x=x_labels, y=as_vals,
        marker_color='#d97706', marker_line_width=0,
        text=[str(round(v)) for v in as_vals],
        textposition='inside', textfont=dict(color='white', size=12),
        insidetextanchor='middle',
    ))
    fig.add_trace(go.Scatter(
        name='양산차종 비중', x=x_labels, y=비중_vals,
        mode='lines+markers+text',
        line=dict(color='#1f2937', width=2),
        marker=dict(color='white', size=7, line=dict(color='#1f2937', width=2)),
        text=[f"{round(v)}%" for v in 비중_vals],
        textposition='top center',
        textfont=dict(size=12, color='#1f2937'),
        yaxis='y2',
    ))

    max_tot = max(totals) if totals else 30
    비중_data = [v for v in 비중_vals if v > 0]
    min_b = min(비중_data) if 비중_data else 80
    max_b = max(비중_data) if 비중_data else 100
    dr    = max(max_b - min_b, 2)
    y2_total = dr / 0.40
    ymin2 = min_b - 0.50 * y2_total
    ymax2 = ymin2 + y2_total

    fig.update_layout(
        barmode='stack',
        height=360,
        margin=dict(l=10, r=20, t=30, b=60),
        legend=dict(
            orientation='h', y=-0.22, x=0.5, xanchor='center',
            font=dict(size=12), bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            tickfont=dict(size=11, color='#4a5568'),
            showgrid=False, linecolor='#e2e8f0', linewidth=1, showline=True,
        ),
        yaxis=dict(
            showgrid=True, gridcolor='#f0edf8', gridwidth=1,
            range=[0, max_tot * 2.5],
            showticklabels=False, showline=False, zeroline=False,
        ),
        yaxis2=dict(
            overlaying='y', side='right',
            range=[ymin2, ymax2],
            showticklabels=False, showgrid=False, showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig


def _build_만도사급_chart(x_labels, 열전_vals, 열후_vals, 피니언_vals):
    totals = [a + b + c for a, b, c in zip(열전_vals, 열후_vals, 피니언_vals)]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='열후 금액', x=x_labels, y=열후_vals,
        marker_color='#a78bfa', marker_line_width=0,
        text=[str(round(v)) for v in 열후_vals],
        textposition='inside',
        textfont=dict(color='white', size=13),
        insidetextanchor='middle',
    ))
    fig.add_trace(go.Bar(
        name='피니언 금액', x=x_labels, y=피니언_vals,
        marker_color='#d97706', marker_line_width=0,
    ))
    fig.add_trace(go.Bar(
        name='열전 금액', x=x_labels, y=열전_vals,
        marker_color='#6b46c1', marker_line_width=0,
        text=[str(round(t)) for t in totals],
        textposition='outside',
        textfont=dict(size=12, color='#374151'),
    ))

    max_tot = max(totals) if totals else 100

    fig.update_layout(
        barmode='stack',
        height=340,
        margin=dict(l=10, r=20, t=30, b=60),
        legend=dict(
            orientation='h', y=-0.22, x=0.5, xanchor='center',
            font=dict(size=12), bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            tickfont=dict(size=11, color='#4a5568'),
            showgrid=False, linecolor='#e2e8f0', linewidth=1, showline=True,
        ),
        yaxis=dict(
            showgrid=True, gridcolor='#f0edf8', gridwidth=1,
            range=[0, max_tot * 1.25],
            showticklabels=False,
            showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig


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
        app.title(f"{int(year_state.value)}년 {int(month_state.value)}월 매출분석")
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["품목별 매출", "판매구성"])

    with tabs[0]:
        def _render_품목별매출():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_headers = _build_품목별매출(year, month)
            memo = _get_memo(Sheets.품목별매출_메모, year, month)
            app.markdown(
                _layout64("1) 품목별 매출",
                          _품목별매출_to_html(rows, col_headers),
                          memo, unit='[단위: 만개, 백만원]'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_품목별매출)

    with tabs[1]:
        def _render_판매구성():
            year, month = int(year_state.value), int(month_state.value)
            rows1, col_hdrs1, data1, 계_vals1, 비중_vals1       = _build_판매구성_제품별(year, month)
            rows2, col_hdrs2, 중량_vals, 단가_vals              = _build_부산물매출(year, month)
            rows3, col_hdrs3, 환산_vals, 판매량_vals, 매출액_vals = _build_부산물증량(year, month)
            rows4, x_hdrs4, 합금단가_t, 분철단가_t, 평균단가_t    = _build_부산물판매(year, month)
            memo4 = _get_memo(Sheets.부산물판매_메모, year, month)
            rows5, col_hdrs5, 열전_t, 열후_t, 피니언_t            = _build_만도사급(year, month)
            memo5 = _get_memo(Sheets.판매구성_메모, year, month)
            rows6, col_hdrs6, 양산_t, as_t, 비중_t               = _build_양산차종(year, month)

            col_l, _ = app.columns([6, 4])
            with col_l:
                app.markdown(
                    _sec_title('1) 제품별 판매현황', '[단위: 만개]')
                    + _판매구성_제품별_to_html(rows1, col_hdrs1),
                    unsafe_allow_html=True,
                )
                app.plotly_chart(
                    _build_제품별판매_chart(col_hdrs1, data1, 계_vals1, 비중_vals1),
                    use_container_width=True,
                )
                app.markdown(
                    _sec_title('2) 부산물 매출 판매 현황', '[단위: 톤, 백만원]')
                    + _부산물매출_to_html(rows2, col_hdrs2),
                    unsafe_allow_html=True,
                )
                app.plotly_chart(
                    _build_부산물매출_chart(col_hdrs2, 중량_vals, 단가_vals),
                    use_container_width=True,
                )
                app.markdown(
                    _sec_title('3) 총 투입량 대비 부산물 중량 변동 추이',
                               '[단위: 톤, 만개, 백만원]')
                    + _부산물증량_to_html(rows3, col_hdrs3),
                    unsafe_allow_html=True,
                )
                app.plotly_chart(
                    _build_부산물증량_chart(col_hdrs3, 환산_vals, 판매량_vals, 매출액_vals),
                    use_container_width=True,
                )

            col_l4, col_r4 = app.columns([6, 4])
            with col_l4:
                app.markdown(
                    _sec_title('4) 전월대비 부산물 판매 차이', '[단위: kg, 천원, 원/kg]')
                    + _부산물판매_to_html(rows4),
                    unsafe_allow_html=True,
                )
                app.plotly_chart(
                    _build_부산물판매_chart(x_hdrs4, 합금단가_t, 분철단가_t, 평균단가_t),
                    use_container_width=True,
                )
            with col_r4:
                if memo4:
                    app.markdown(_memo_html(memo4), unsafe_allow_html=True)

            col_l5, col_r5 = app.columns([6, 4])
            with col_l5:
                app.markdown(
                    _sec_title('5) 만도 사급 매출 현황', '[단위: 만개, 백만원, 원/개]')
                    + _만도사급_to_html(rows5, col_hdrs5),
                    unsafe_allow_html=True,
                )
                app.plotly_chart(
                    _build_만도사급_chart(col_hdrs5, 열전_t, 열후_t, 피니언_t),
                    use_container_width=True,
                )
            with col_r5:
                if memo5:
                    app.markdown(_memo_html(memo5), unsafe_allow_html=True)

            col_l6, _ = app.columns([6, 4])
            with col_l6:
                app.markdown(
                    _sec_title('6) 양산차종 매출 현황', '[단위: 만대]')
                    + _양산차종_to_html(rows6, col_hdrs6),
                    unsafe_allow_html=True,
                )
                app.plotly_chart(
                    _build_양산차종_chart(col_hdrs6, 양산_t, as_t, 비중_t),
                    use_container_width=True,
                )

        app.If(lambda: True, _render_판매구성)
