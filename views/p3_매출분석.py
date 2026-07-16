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
    C_NAVY, C_ORANGE, C_RED, C_CHART_SEC, C_CHART_GRID,
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
    df = load_sheet(Sheets.계획대비매출실적_DB)
    return sorted(pd.to_numeric(df['연도'], errors='coerce').dropna().astype(int).unique().tolist())


def _get_memo(sheet_info, year, month):
    df = load_sheet(sheet_info)
    df['연도'] = df['연도'].astype(str).str.strip()
    df['월']   = df['월'].astype(str).str.strip()
    row = df[(df['연도'] == str(year)) & (df['월'] == str(month))]
    return str(row.iloc[0]['메모']) if not row.empty else ''


# ── 1) 계획대비 매출실적 ──────────────────────────────────────────────────────────

def _build_계획대비_매출실적(year, month):
    df = load_sheet(Sheets.계획대비매출실적_DB) 
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)

    vm = df.set_index(['구분1', '구분2', '계획/실적', '연도', '월'])['값'].to_dict()
    prev_yr, prev_mo = _prev(year, month, 1)

    def raw(g1, g2, typ, yr, mo):
        return vm.get((g1, g2, typ, yr, mo), 0.0)

    def ann(g1, g2, typ, yr):
        return sum(raw(g1, g2, typ, yr, m) for m in range(1, 13))

    def ytd(g1, g2, typ, yr, mo):
        return sum(raw(g1, g2, typ, yr, m) for m in range(1, mo + 1))

    # 이미지에 나타난 품목 목록
    품목_list = ['CHQ', 'CD', 'STS', 'BTB', 'PB', '기타']
    단가_품목 = ['CHQ', 'CD', 'STS', 'BTB', 'PB']  # 기타 제외

    def dp(금액, 판매량):
        return 금액 / 판매량 if 판매량 else 0.0

    M = 1_000_000 # 금액 백만원 단위 변환[cite: 1]
    K = 1_000     # 중량 톤 단위 변환 (kg -> ton)
    rows = []

    for 품목 in 품목_list:
        rows.append(('section', 품목))

        # --- 금액 (원 -> 백만원) ---
        ag = ann(품목, '금액', '계획', year)
        pg = raw(품목, '금액', '실적', prev_yr, prev_mo)
        plg = raw(품목, '금액', '계획', year, month)
        cg = raw(품목, '금액', '실적', year, month)
        ytdpg = ytd(품목, '금액', '계획', year, month)
        ytdrg = ytd(품목, '금액', '실적', year, month)

        rows.append(('sub', '금액',
                     ag/M, pg/M, plg/M, cg/M,
                     (cg-plg)/M, (cg-pg)/M,
                     ytdpg/M, ytdrg/M, (ytdrg-ytdpg)/M))

        # --- 중량(kg -> 톤) 및 단가(원/톤) ---
        if 품목 in 단가_품목:
            # 중량을 톤 단위로 변환하기 위해 K(1000)로 나눔
            aq = ann(품목, '중량', '계획', year) / K
            pq = raw(품목, '중량', '실적', prev_yr, prev_mo) / K
            plq = raw(품목, '중량', '계획', year, month) / K
            cq = raw(품목, '중량', '실적', year, month) / K
            ytdpq = ytd(품목, '중량', '계획', year, month) / K
            ytdrq = ytd(품목, '중량', '실적', year, month) / K

            # 단가 계산 (금액(원) / 중량(톤))
            rows.append(('sub', '단가',
                         dp(ag, aq)/ K, dp(pg, pq)/ K, dp(plg, plq)/ K, dp(cg, cq)/ K,
                         (dp(cg, cq) - dp(plg, plq))/ K, (dp(cg, cq) - dp(pg, pq))/ K,
                         dp(ytdpg, ytdpq)/ K, dp(ytdrg, ytdrq)/ K, (dp(ytdrg, ytdrq) - dp(ytdpg, ytdpq))/ K))

            rows.append(('sub', '중량(톤)',
                         aq, pq, plq, cq,
                         cq-plq, cq-pq,
                         ytdpq, ytdrq, ytdrq-ytdpq))

    # --- 합계 섹션 ---
    rows.append(('section', '합계'))

    tag = sum(ann(p, '금액', '계획', year) for p in 품목_list)
    tpg = sum(raw(p, '금액', '실적', prev_yr, prev_mo) for p in 품목_list)
    tplg = sum(raw(p, '금액', '계획', year, month) for p in 품목_list)
    tcg = sum(raw(p, '금액', '실적', year, month) for p in 품목_list)
    tytdpg = sum(ytd(p, '금액', '계획', year, month) for p in 품목_list)
    tytdrg = sum(ytd(p, '금액', '실적', year, month) for p in 품목_list)

    # 합계 중량도 동일하게 K(1000)로 나누어 톤으로 변환
    taq = sum(ann(p, '중량', '계획', year) for p in 단가_품목) / K
    tpq = sum(raw(p, '중량', '실적', prev_yr, prev_mo) for p in 단가_품목) / K
    tplq = sum(raw(p, '중량', '계획', year, month) for p in 단가_품목) / K
    tcq = sum(raw(p, '중량', '실적', year, month) for p in 단가_품목) / K
    tytdpq = sum(ytd(p, '중량', '계획', year, month) for p in 단가_품목) / K
    tytdrq = sum(ytd(p, '중량', '실적', year, month) for p in 단가_품목) / K

    rows.append(('total', '금액',
                 tag/M, tpg/M, tplg/M, tcg/M,
                 (tcg-tplg)/M, (tcg-tpg)/M,
                 tytdpg/M, tytdrg/M, (tytdrg-tytdpg)/M))

    rows.append(('total', '단가',
                 dp(tag, taq)/K, dp(tpg, tpq)/K, dp(tplg, tplq)/K, dp(tcg, tcq)/K,
                 (dp(tcg, tcq) - dp(tplg, tplq))/K, (dp(tcg, tcq) - dp(tpg, tpq))/K,
                 dp(tytdpg, tytdpq)/K, dp(tytdrg, tytdrq)/K, (dp(tytdrg, tytdrq) - dp(tytdpg, tytdpq))/K))

    rows.append(('total', '중량(톤)',
                 taq, tpq, tplq, tcq,
                 tcq-tplq, tcq-tpq,
                 tytdpq, tytdrq, tytdrq-tytdpq))

    # --- 구분행(헤더) 날짜 동적 생성 (예: '24.11월 실적, '24.12월 계획 등) ---
    # 연도가 바뀔 경우 접두사를 포함하여 표기하도록 처리[cite: 1]
    prev_pfx = f"'{str(prev_yr)[2:]}." if prev_yr != year else "'"
    curr_pfx = f"'{str(year)[2:]}."
    
    col_연간계획 = f"'{str(year)[2:]}년 계획"
    col_전월실적 = f"{prev_mo}월 실적"
    col_당월계획 = f"{month}월 계획"
    col_당월실적 = f"{month}월 실적"

    col_headers = ['구분', col_연간계획, col_전월실적, col_당월계획, col_당월실적,
                   '계획비', '전월비', '누계_계획', '누계_실적', '누계_계획비']
    
    return rows, col_headers


def _계획대비_매출실적_to_html(rows, col_headers):
    n_cols = len(col_headers)
    th_cells = "".join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
    th_html = f'<tr>{th_cells}</tr>'

    body_html = ''
    sub_idx = 0

    for row in rows:
        if row[0] == 'section':
            sub_idx = 0
            body_html += f'<tr><td colspan="{n_cols}" style="{ROW_SEC}">{row[1]}</td></tr>'
        elif row[0] == 'sub':
            _, label, *vals = row
            bg = ';background:#f9f9fb' if sub_idx % 2 == 1 else ';background:white'
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

def _build_판매현황_등급별(year, month):
    df = load_sheet(Sheets.등급별판매구성_DB)
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    
    # [강력한 데이터 클렌징] '년' 글자와 모든 공백 제거
    df['연도'] = df['연도'].astype(str).str.replace('년', '', regex=False).str.replace(' ', '', regex=False)
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    
    # [강력한 데이터 클렌징] .0 제거 및 '월 평균' 등의 공백 제거
    df['월'] = df['월'].astype(str).str.replace('.0', '', regex=False).str.replace(' ', '', regex=False)
    
    df['구분1'] = df['구분1'].fillna('').astype(str).str.strip()
    df['구분2'] = df['구분2'].fillna('').astype(str).str.strip()

    vm = df.set_index(['구분1', '구분2', '연도', '월'])['값'].to_dict()

    def raw(g1, g2, yr, mo):
        return vm.get((g1, g2, yr, str(mo)), 0.0)

    def yr_avg(g1, g2, yr):
        val_avg = raw(g1, g2, yr, '월평균')
        if val_avg != 0.0:
            return val_avg
        vals = [v for m in range(1, 13) if (v := raw(g1, g2, yr, m)) != 0]
        return sum(vals) / len(vals) if vals else 0.0

    yr_1, yr_curr = year - 1, year
    recent_6 = _recent_months(year, month, n=6) 

    col_hdrs = [f"'{str(yr_1)[2:]}년 월평균", f"'{str(yr_curr)[2:]}년 월평균"]
    
    last_yr = None
    for yr_c, mo_c in recent_6:
        col_hdrs.append(f"'{str(yr_c)[2:]}.{mo_c}월" if yr_c != last_yr else f"{mo_c}월")
        last_yr = yr_c

    categories = [
        ('정상입고품', '산업재 혹은 중국재', '정상입고품(산업재/중국재)'),
        ('정상입고품', '정상', '정상입고품(정상)'),
        ('B급', '', 'B급')
    ]

    rows = []
    for g1, g2, label in categories:
        vals = [yr_avg(g1, g2, yr_1), yr_avg(g1, g2, yr_curr)]
        for yr_c, mo_c in recent_6:
            vals.append(raw(g1, g2, yr_c, mo_c))
        rows.append(('sub', label, vals))

    계_vals = [sum(r[2][i] for r in rows) for i in range(len(col_hdrs))]
    rows.append(('total', '합계', 계_vals))

    return rows, col_hdrs
def _판매현황_등급별_to_html(rows, col_hdrs):
    # 테이블 헤더 (<th>) 구성
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in ['구분'] + col_hdrs)
    
    body = ''
    sub_idx = 0
    
    # 테이블 본문 (<td>) 구성[cite: 1]
    for kind, label, vals in rows:
        if kind == 'sub':
            bg = ';background:#f9f9fb' if sub_idx % 2 else ';background:white'
            sub_idx += 1
            cells = f'<td style="{ROW_ITEM + bg}">{label}</td>'
            cells += ''.join(f'<td style="{_TD_NUM + bg}">{_fmt(v)}</td>' for v in vals)
        elif kind == 'total':
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            cells += ''.join(f'<td style="{ROW_HDR_NUM}">{_fmt(v)}</td>' for v in vals)
            
        body += f'<tr>{cells}</tr>'
        
    return _html_table(f'<tr>{th}</tr>', body)

def _build_판매현황_등급별_chart(x_labels, rows):
    fig = go.Figure()

    # 1) 기본 색상 활용: 짙은회색(NAVY), 회색(SEC), 주황색(ORANGE)
    colors = [C_NAVY, C_CHART_SEC, C_ORANGE]
    color_idx = 0
    
    totals = [0] * len(x_labels)

    for kind, label, vals in rows:
        if kind == 'sub':
            fig.add_trace(go.Bar(
                name=label,
                x=x_labels,
                y=vals,
                marker_color=colors[color_idx % len(colors)],
                marker_line_width=0,
                text=[f"{int(v):,}" if v > 0 else '' for v in vals],
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(color='white', size=11),
            ))
            color_idx += 1
            
            # 합계 계산
            for i, v in enumerate(vals):
                totals[i] += v

    # 💡 [추가] 막대 최상단에 합계 표시
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=[t for t in totals], 
        mode='text',
        text=[f"<b>{int(t):,}</b>" for t in totals],
        textposition='top center',
        textfont=dict(color='#2d3748', size=12),
        showlegend=False,
        hoverinfo='skip'
    ))

    max_tot = max(totals) if totals else 30000

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
            showgrid=True, gridcolor=C_CHART_GRID, gridwidth=1,
            range=[0, max_tot * 1.20], # 합계 표시를 위한 여백 확보
            showticklabels=False, showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig

# ── 판매구성 - 2) CHQ 제품 판매현황 (B급 제외) ───────────────────────────────

def _build_CHQ_B급제외_data(year, month):
    df = load_sheet(Sheets.CHQ제품판매현황_B급제외_DB)
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    
    # [강력한 데이터 클렌징]
    df['연도'] = df['연도'].astype(str).str.replace('년', '', regex=False).str.replace(' ', '', regex=False)
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    df['월'] = df['월'].astype(str).str.replace('.0', '', regex=False).str.replace(' ', '', regex=False)
    
    df = df[(df['구분2'] == 'CHQ') & (df['구분1'] != 'B급')]
    df['구분3'] = df['구분3'].fillna('').astype(str).str.strip()

    vm = df.groupby(['구분3', '연도', '월'])['값'].sum().to_dict()

    def raw(g3, yr, mo):
        return vm.get((g3, yr, str(mo)), 0.0)

    def yr_avg(g3, yr):
        if yr <= 2024:
            val_avg = raw(g3, yr, '월평균')
            if val_avg != 0.0:
                return val_avg
        vals = [v for m in range(1, 13) if (v := raw(g3, yr, m)) != 0]
        return sum(vals) / len(vals) if vals else 0.0

    yr_2, yr_1 = year - 2, year - 1
    recent_4 = _recent_months(year, month, n=4) 

    col_hdrs = [f"'{str(yr_2)[2:]}년 월평균", f"'{str(yr_1)[2:]}년 월평균"]
    last_yr = None
    for yr_c, mo_c in recent_4:
        col_hdrs.append(f"'{str(yr_c)[2:]}.{mo_c}월" if yr_c != last_yr else f"{mo_c}월")
        last_yr = yr_c

    target_g3 = ['열처리', '비열처리']
    rows = []
    
    for g3 in target_g3:
        vals = [yr_avg(g3, yr_2), yr_avg(g3, yr_1)]
        for yr_c, mo_c in recent_4:
            vals.append(raw(g3, yr_c, mo_c))
        rows.append(('sub', g3, vals))

    return rows, col_hdrs

def _build_CHQ_B급제외_chart(x_labels, rows):
    fig = go.Figure()

    # 💡 2개 색상 활용: 짙은회색, 회색
    color_map = {
        '열처리': C_NAVY,       
        '비열처리': C_CHART_SEC 
    }
    
    totals = [0] * len(x_labels)

    for kind, label, vals in rows:
        if kind == 'sub':
            fig.add_trace(go.Bar(
                name=label,
                x=x_labels,
                y=vals,
                marker_color=color_map.get(label, C_NAVY),
                marker_line_width=0,
                text=[f"{int(v):,}" if v > 0 else '' for v in vals],
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(color='white', size=12),
            ))
            for i, v in enumerate(vals):
                totals[i] += v

    # 💡 [추가] 막대 최상단에 합계 표시
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=[t for t in totals], 
        mode='text',
        text=[f"<b>{int(t):,}</b>" for t in totals],
        textposition='top center',
        textfont=dict(color='#2d3748', size=12),
        showlegend=False,
        hoverinfo='skip'
    ))

    max_tot = max(totals) if totals else 30000

    fig.update_layout(
        barmode='stack', 
        height=380,
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
            showgrid=True, gridcolor=C_CHART_GRID, gridwidth=1,
            range=[0, max_tot * 1.20],
            showticklabels=False, showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig

# ── 판매구성 - 3) CHQ 산업/중국재 제품 판매현황 ───────────────────────────────

def _build_CHQ_산업중국재_data(year, month):
    df = load_sheet(Sheets.CHQ제품판매현황_산업중국재_DB)
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    
    # [강력한 데이터 클렌징]
    df['연도'] = df['연도'].astype(str).str.replace('년', '', regex=False).str.replace(' ', '', regex=False)
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    df['월'] = df['월'].astype(str).str.replace('.0', '', regex=False).str.replace(' ', '', regex=False)
    
    df = df[df['구분2'] == '산업/중국재']
    df['구분3'] = df['구분3'].fillna('').astype(str).str.strip()

    vm = df.groupby(['구분3', '연도', '월'])['값'].sum().to_dict()

    def raw(g3, yr, mo):
        return vm.get((g3, yr, str(mo)), 0.0)

    def yr_avg(g3, yr):
        if yr <= 2024:
            val_avg = raw(g3, yr, '월평균')
            if val_avg != 0.0:
                return val_avg
        vals = [v for m in range(1, 13) if (v := raw(g3, yr, m)) != 0]
        return sum(vals) / len(vals) if vals else 0.0

    yr_2, yr_1 = year - 2, year - 1
    recent_4 = _recent_months(year, month, n=4) 

    col_hdrs = [f"'{str(yr_2)[2:]}년 월평균", f"'{str(yr_1)[2:]}년 월평균"]
    last_yr = None
    for yr_c, mo_c in recent_4:
        col_hdrs.append(f"'{str(yr_c)[2:]}.{mo_c}월" if yr_c != last_yr else f"{mo_c}월")
        last_yr = yr_c

    target_g3 = ['열처리', '비열처리']
    rows = []
    
    for g3 in target_g3:
        vals = [yr_avg(g3, yr_2), yr_avg(g3, yr_1)]
        for yr_c, mo_c in recent_4:
            vals.append(raw(g3, yr_c, mo_c))
        rows.append(('sub', g3, vals))

    return rows, col_hdrs

def _build_CHQ_산업중국재_chart(x_labels, rows):
    fig = go.Figure()

    # 💡 2개 색상 활용: 짙은회색, 회색
    color_map = {
        '열처리': C_NAVY,       
        '비열처리': C_CHART_SEC 
    }
    
    totals = [0] * len(x_labels)

    for kind, label, vals in rows:
        if kind == 'sub':
            fig.add_trace(go.Bar(
                name=label,
                x=x_labels,
                y=vals,
                marker_color=color_map.get(label, C_NAVY),
                marker_line_width=0,
                text=[f"{int(v):,}" if v > 0 else '' for v in vals],
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(color='white', size=12),
            ))
            for i, v in enumerate(vals):
                totals[i] += v

    # 💡 [추가] 막대 최상단에 합계 표시
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=[t for t in totals], 
        mode='text',
        text=[f"<b>{int(t):,}</b>" for t in totals],
        textposition='top center',
        textfont=dict(color='#2d3748', size=12),
        showlegend=False,
        hoverinfo='skip'
    ))

    max_tot = max(totals) if totals else 5000

    fig.update_layout(
        barmode='stack',
        height=380,
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
            showgrid=True, gridcolor=C_CHART_GRID, gridwidth=1,
            range=[0, max_tot * 1.20],
            showticklabels=False, showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig

# ── 판매구성 - CD 제품 판매현황 (B급 제외 / 산업중국재) ─────────────────────────

def _build_CD_B급제외_data(year, month):
    df = load_sheet(Sheets.CD제품판매현황_B급제외_DB) 
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    
    # [강력한 데이터 클렌징]
    df['연도'] = df['연도'].astype(str).str.replace('년', '', regex=False).str.replace(' ', '', regex=False)
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    df['월'] = df['월'].astype(str).str.replace('.0', '', regex=False).str.replace(' ', '', regex=False)
    
    df['구분3'] = df['구분3'].fillna('').astype(str).str.strip()

    vm = df.groupby(['구분3', '연도', '월'])['값'].sum().to_dict()

    def raw(g, yr, mo):
        return vm.get((g, yr, str(mo)), 0.0)

    def yr_avg(g, yr):
        if yr <= 2024:
            val_avg = raw(g, yr, '월평균')
            if val_avg != 0.0:
                return val_avg
        vals = [v for m in range(1, 13) if (v := raw(g, yr, m)) != 0]
        return sum(vals) / len(vals) if vals else 0.0

    yr_2, yr_1 = year - 2, year - 1
    recent_4 = _recent_months(year, month, n=4) 

    col_hdrs = [f"'{str(yr_2)[2:]}년 월평균", f"'{str(yr_1)[2:]}년 월평균"]
    for yr_c, mo_c in recent_4:
        col_hdrs.append(f"'{str(yr_c)[2:]}년 {mo_c}월")

    target_g = ['합금강', '쾌삭강', '일/탄']
    rows = []
    
    for g in target_g:
        vals = [yr_avg(g, yr_2), yr_avg(g, yr_1)]
        for yr_c, mo_c in recent_4:
            vals.append(raw(g, yr_c, mo_c))
        rows.append(('sub', g, vals))

    return rows, col_hdrs

def _build_CD_B급제외_chart(x_labels, rows):
    fig = go.Figure()

    # 💡 3개 색상 활용: 짙은회색, 회색, 주황색
    color_map = {
        '일/탄': C_NAVY,       # 짙은 회색
        '쾌삭강': C_CHART_SEC, # 회색
        '합금강': C_ORANGE     # 주황색
    }
    
    totals = [0] * len(x_labels)

    for kind, label, vals in rows:
        if kind == 'sub':
            fig.add_trace(go.Bar(
                name=label,
                x=x_labels,
                y=vals,
                marker_color=color_map.get(label, C_NAVY),
                marker_line_width=0,
                text=[f"{int(v):,}" if v > 0 else '' for v in vals],
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(color='white', size=11),
            ))
            for i, v in enumerate(vals):
                totals[i] += v

    fig.add_trace(go.Scatter(
        x=x_labels,
        y=[t for t in totals], 
        mode='text',
        text=[f"<b>{int(t):,}</b>" for t in totals],
        textposition='top center',
        textfont=dict(color='#2d3748', size=12),
        showlegend=False,
        hoverinfo='skip'
    ))

    max_tot = max(totals) if totals else 10000

    fig.update_layout(
        barmode='stack',
        height=380,
        margin=dict(l=10, r=20, t=30, b=60),
        legend=dict(
            orientation='h', y=-0.22, x=0.5, xanchor='center',
            font=dict(size=12), bgcolor='rgba(0,0,0,0)',
            traceorder='reversed'
        ),
        xaxis=dict(
            tickfont=dict(size=11, color='#4a5568'),
            showgrid=False, linecolor='#e2e8f0', linewidth=1, showline=True,
        ),
        yaxis=dict(
            showgrid=True, gridcolor=C_CHART_GRID, gridwidth=1,
            range=[0, max_tot * 1.20],
            showticklabels=False, showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig

def _build_CD_산업중국재_data(year, month):
    df = load_sheet(Sheets.CD제품판매현황_산업중국재_DB) 
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    
    # [강력한 데이터 클렌징]
    df['연도'] = df['연도'].astype(str).str.replace('년', '', regex=False).str.replace(' ', '', regex=False)
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    df['월'] = df['월'].astype(str).str.replace('.0', '', regex=False).str.replace(' ', '', regex=False)
    
    df['구분4'] = df['구분4'].fillna('').astype(str).str.strip()
    vm = df.groupby(['구분4', '연도', '월'])['값'].sum().to_dict()

    def raw(g, yr, mo):
        return vm.get((g, yr, str(mo)), 0.0)

    def yr_avg(g, yr):
        if yr <= 2024:
            val_avg = raw(g, yr, '월평균')
            if val_avg != 0.0:
                return val_avg
        vals = [v for m in range(1, 13) if (v := raw(g, yr, m)) != 0]
        return sum(vals) / len(vals) if vals else 0.0

    yr_2, yr_1 = year - 2, year - 1
    recent_4 = _recent_months(year, month, n=4) 

    col_hdrs = [f"'{str(yr_2)[2:]}년 월평균", f"'{str(yr_1)[2:]}년 월평균"]
    for yr_c, mo_c in recent_4:
        col_hdrs.append(f"'{str(yr_c)[2:]}년 {mo_c}월")

    target_g = ['합금강', '일/탄']
    rows = []
    
    for g in target_g:
        vals = [yr_avg(g, yr_2), yr_avg(g, yr_1)]
        for yr_c, mo_c in recent_4:
            vals.append(raw(g, yr_c, mo_c))
        rows.append(('sub', g, vals))

    return rows, col_hdrs

def _build_CD_산업중국재_chart(x_labels, rows):
    fig = go.Figure()

    # 💡 2개 색상 활용: 짙은회색, 회색
    color_map = {
        '일/탄': C_NAVY,       # 짙은 회색
        '합금강': C_CHART_SEC  # 회색
    }
    
    totals = [0] * len(x_labels)

    for kind, label, vals in rows:
        if kind == 'sub':
            fig.add_trace(go.Bar(
                name=label,
                x=x_labels,
                y=vals,
                marker_color=color_map.get(label, C_NAVY),
                marker_line_width=0,
                text=[f"{int(v):,}" if v > 0 else '' for v in vals],
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(color='white', size=11),
            ))
            for i, v in enumerate(vals):
                totals[i] += v

    fig.add_trace(go.Scatter(
        x=x_labels,
        y=[t for t in totals], 
        mode='text',
        text=[f"<b>{int(t):,}</b>" for t in totals],
        textposition='top center',
        textfont=dict(color='#2d3748', size=12),
        showlegend=False,
        hoverinfo='skip'
    ))

    max_tot = max(totals) if totals else 3000

    fig.update_layout(
        barmode='stack',
        height=380,
        margin=dict(l=10, r=20, t=30, b=60),
        legend=dict(
            orientation='h', y=-0.22, x=0.5, xanchor='center',
            font=dict(size=12), bgcolor='rgba(0,0,0,0)',
            traceorder='reversed'
        ),
        xaxis=dict(
            tickfont=dict(size=11, color='#4a5568'),
            showgrid=False, linecolor='#e2e8f0', linewidth=1, showline=True,
        ),
        yaxis=dict(
            showgrid=True, gridcolor=C_CHART_GRID, gridwidth=1,
            range=[0, max_tot * 1.20],
            showticklabels=False, showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig

# ── render_page ───────────────────────────────────────────────────────────

def render_page(app, year_state, month_state):

    def _render_title():
        app.markdown(
            f'<h1 style="color:#404448">{int(year_state.value)}년 {int(month_state.value)}월 매출분석</h1>',
            unsafe_allow_html=True,
        )
    app.If(lambda: True, _render_title)

    # 탭 명칭을 요구사항에 맞게 변경
    tabs = app.tabs(["계획대비 매출실적", "판매구성"])

    with tabs[0]:
        def _render_계획대비_매출실적():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_headers = _build_계획대비_매출실적(year, month)
            # 필요한 경우 관련 메모 DB 연동
            memo = _get_memo(Sheets.계획대비매출실적_메모, year, month) 
            app.markdown(
                _layout64("1) 계획대비 매출실적",
                          _계획대비_매출실적_to_html(rows, col_headers),
                          memo, unit='[단위: 톤, 백만원, 원/톤]'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_계획대비_매출실적)

    with tabs[1]:
        def _render_판매구성():
            year, month = int(year_state.value), int(month_state.value)
            
            rows_등급, hdrs_등급 = _build_판매현황_등급별(year, month)
            rows_CHQ, hdrs_CHQ = _build_CHQ_B급제외_data(year, month)
            rows_산업, hdrs_산업 = _build_CHQ_산업중국재_data(year, month)
            rows_CD_B급제외, hdrs_CD_B급제외 = _build_CD_B급제외_data(year, month)
            rows_CD_산업, hdrs_CD_산업 = _build_CD_산업중국재_data(year, month)
            
            col_l, _ = app.columns([6, 4])
            with col_l:
                # 1. 등급별 판매현황
                app.markdown(
                    _sec_title('1) 등급별 판매현황', '[단위: 톤]')
                    + _판매현황_등급별_to_html(rows_등급, hdrs_등급),
                    unsafe_allow_html=True,
                )
                app.plotly_chart(
                    _build_판매현황_등급별_chart(hdrs_등급, rows_등급),
                    use_container_width=True,
                )

                # 2) CHQ 제품 판매현황 (수정)
                app.markdown(
                    _sec_title('2) CHQ 제품 판매현황', '[월별 CHQ 판매 추이 (산업/중국材 포함, B급 제외)]'),
                    unsafe_allow_html=True,
                )
                app.plotly_chart(
                    _build_CHQ_B급제외_chart(hdrs_CHQ, rows_CHQ),
                    use_container_width=True
                )

                # 3)산업/중국재 제품 판매현황 (수정 - 좌측 제목을 비움)
                app.markdown(
                    _sec_title('', '[월별 산업/중국材 판매 추이(B급 제외)]'),
                    unsafe_allow_html=True,
                )
                app.plotly_chart(
                    _build_CHQ_산업중국재_chart(hdrs_산업, rows_산업),
                    use_container_width=True
                )
                
                # 4) CD 강종류별 판매현황 (B급 제외) (추가)
                app.markdown(
                    _sec_title('3) CD 강종류별 판매현황', '[월별 CD 판매 추이 (산업/중국材 포함, B급 제외)]'),
                    unsafe_allow_html=True,
                )
                app.plotly_chart(
                    _build_CD_B급제외_chart(hdrs_CD_B급제외, rows_CD_B급제외),
                    use_container_width=True
                )

                # 5) CD 산업/중국재 판매현황 (추가 - 좌측 제목을 비움)
                app.markdown(
                    _sec_title('', '[월별 산업/중국材 CD 판매 추이(B급 제외)]'),
                    unsafe_allow_html=True,
                )
                app.plotly_chart(
                    _build_CD_산업중국재_chart(hdrs_CD_산업, rows_CD_산업),
                    use_container_width=True
                )

        app.If(lambda: True, _render_판매구성)