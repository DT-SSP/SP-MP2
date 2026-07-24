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
    
    # ── 1. 기본 전처리 ──
    for col in ['사업장', '구분1', '구분2', '계획/실적']:
        if col not in df.columns:
            df[col] = ''
        df[col] = df[col].fillna('').astype(str).str.strip()
        
    df['값'] = df['값'].apply(_parse)
    
    # DB상 명칭을 일관되게 정규화 (자사계 -> 자사, 외주계 -> 외주)
    df['구분1'] = df['구분1'].replace({'자사계': '자사', '외주계': '외주'})
    
    # ── 2. Raw 데이터 딕셔너리 구축 ──
    vm = {}
    for _, row in df.iterrows():
        key = (row['사업장'], row['구분1'], row['구분2'], row['계획/실적'], int(row['연도']), int(row['월']))
        vm[key] = vm.get(key, 0.0) + float(row['값'])

    # ── 3. 합계 계산을 위한 롤업(Roll-up) ──
    rollups = {}
    for (site, g1, g2, pa, yr, mo), v in vm.items():
        # 사업장, 구분1, 구분2의 (부분합, 전체합)을 모두 구하기 위해 None 조합 생성
        for s in [site, None]:
            for g_1 in [g1, None]:
                for g_2 in [g2, None]:
                    k = (s, g_1, g_2, pa, yr, mo)
                    rollups[k] = rollups.get(k, 0.0) + v

    def get_raw(site, g1, g2, pa, yr, mo):
        return rollups.get((site, g1, g2, pa, yr, mo), 0.0)

    def yr_avg(site, g1, g2, pa, yr):
        vals = [get_raw(site, g1, g2, pa, yr, m) for m in range(1, 13)]
        non_zero = [v for v in vals if v != 0.0]
        return sum(non_zero) / len(non_zero) if non_zero else 0.0

    # ── 4. 열(Column) 헤더 및 값 산출 로직 ──
    prev_mo = month - 1 if month > 1 else 12
    prev_mo_yr = year if month > 1 else year - 1
    
    col_headers = [
        f"'{str(year-1)[2:]}년 연평균",
        f"{str(year)[2:]}년 계획",
        f"'{str(year-1)[2:]}년 12월 실적",
        f"'{str(prev_mo_yr)[2:]}년 {prev_mo}월 실적",
        f"'{str(year)[2:]}년 {month}월 실적",
        f"'{str(year)[2:]}년 연평균",
        "전월대비",
        "계획대비"
    ]

    def calc_row_vals(site, g1, g2):
        v_avg_prev = yr_avg(site, g1, g2, '실적', year-1)
        v_plan_curr = get_raw(site, g1, g2, '계획', year, month)
        v_12_prev = get_raw(site, g1, g2, '실적', year-1, 12)
        v_prev_mo = get_raw(site, g1, g2, '실적', prev_mo_yr, prev_mo)
        v_curr_mo = get_raw(site, g1, g2, '실적', year, month)
        v_avg_curr = yr_avg(site, g1, g2, '실적', year)
        
        v_mom = v_curr_mo - v_prev_mo           # 전월대비
        v_plan_diff = v_curr_mo - v_plan_curr   # 계획대비
        
        return [v_avg_prev, v_plan_curr, v_12_prev, v_prev_mo, v_curr_mo, v_avg_curr, v_mom, v_plan_diff]

    # ── 5. 행(Row) 계층화 생성 ──
    rows = []
    
    # 사업장 순서 고정 (일반적인 순서) 및 DB에 있는 추가 사업장 병합
    sites = ['서울', '포항', '충주', '충주2', '원주']
    db_sites = sorted([s for s in df['사업장'].unique() if s])
    ordered_sites = [s for s in sites if s in db_sites] + [s for s in db_sites if s not in sites]
    if not ordered_sites: 
        ordered_sites = db_sites

    for site in ordered_sites:
        rows.append(('level1', site, calc_row_vals(site, None, None)))
        rows.append(('level2', '자사', calc_row_vals(site, '자사', None)))
        # DB의 '사무기술직'을 UI 표기에 맞춰 '사무직'으로 표시
        rows.append(('level3', '사무직', calc_row_vals(site, '자사', '사무기술직')))
        rows.append(('level3', '기능직', calc_row_vals(site, '자사', '기능직')))
        rows.append(('level2', '외주', calc_row_vals(site, '외주', None)))

    # 하단 총계
    rows.append(('total1', '자사계', calc_row_vals(None, '자사', None)))
    rows.append(('total1', '외주계', calc_row_vals(None, '외주', None)))
    rows.append(('total0', '전체', calc_row_vals(None, None, None)))

    return rows, col_headers


def _인원변동내역_to_html(rows, col_headers):
    th_html = (
        f'<tr><th style="{_TH}text-align:center;">구분</th>'
        + ''.join(f'<th style="{_TH}text-align:center;">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    body_html = ''
    
    # 음수일 경우 괄호가 아닌 '-' 기호를 직접 붙이도록 포맷팅 룰 지정
    def fmt_val(v):
        if pd.isna(v) or v == 0: return '0'
        if v < 0: return f"-{abs(v):,.0f}"
        return f"{v:,.0f}"

    for row_type, label, vals in rows:
        if row_type == 'total0':
            lbl_style = ROW_CAL_LBL
            num_style = ROW_CAL_NUM
            prefix = ''
        elif row_type == 'total1':
            lbl_style = ROW_CAL_LBL + '; font-weight:normal; background-color:#fafafa; color:#4a5568;'
            num_style = ROW_CAL_NUM + '; font-weight:normal; background-color:#fafafa; color:#4a5568;'
            prefix = ''
        elif row_type == 'level1':
            lbl_style = ROW_HDR_LBL + '; font-size:0.95em;'
            num_style = ROW_HDR_NUM + '; font-size:0.95em;'
            prefix = ''
        elif row_type == 'level2':
            lbl_style = ROW_ITEM + '; font-size:0.9em; font-weight:600;'
            num_style = _TD_NUM + '; font-size:0.9em; font-weight:600;'
            prefix = '&nbsp;&nbsp;&nbsp;&nbsp;'
        elif row_type == 'level3':
            lbl_style = ROW_ITEM + '; font-size:0.9em; color:#4a5568;'
            num_style = _TD_NUM + '; font-size:0.9em; color:#4a5568;'
            prefix = '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
            
        cells = f'<td style="{lbl_style}">{prefix}{label}</td>'
        
        for v in vals:
            # 음수일 경우 기존 폰트 속성 유지하며 빨간색 텍스트로 치환
            if v < 0:
                n_style = num_style.replace('color:#4a5568;', '') + '; color:red;'
                if row_type == 'total0': 
                    n_style = ROW_CAL_RED
            else:
                n_style = num_style
                
            cells += f'<td style="{n_style}">{fmt_val(v)}</td>'
            
        body_html += f'<tr>{cells}</tr>'

    return _html_table(th_html, body_html)
# ── render_page ───────────────────────────────────────────────────────────

def render_page(app, year_state, month_state):

    def _render_title():
        app.markdown(
            f'<h1 style="color:#404448">{int(year_state.value)}년 {int(month_state.value)}월 기타</h1>',
            unsafe_allow_html=True,
        )
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["인원현황"])

    with tabs[0]:
        def _render_인원현황():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_headers = _build_인원변동내역(year, month)
            memo = ""
            col_l, col_r = app.columns([6, 4])
            with col_l:
                app.markdown(
                    _sec_title('1) 인원 변동내역', '(단위 : 명)')
                    + _인원변동내역_to_html(rows, col_headers),
                    unsafe_allow_html=True,
                )
            with col_r:
                if memo:
                    app.markdown(_memo_block(memo), unsafe_allow_html=True)
        app.If(lambda: True, _render_인원현황)
