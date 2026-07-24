import datetime
import pandas as pd
from data.loader import load_sheet
from data.config import Sheets
from views.common import (
    parse as _parse, fmt as _fmt,
    drop_empty as _drop_empty,
    recent_months as _recent_months,
    TD_LBL as _TD_LBL, 
    html_table as _html_table, layout64 as _layout64,
    C_NAVY, C_ORANGE, C_RED, C_CHART_SEC, C_CHART_GRID,
    ROW_SEC, ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED, ROW_ITEM,
    TH as _TH, TD_NUM as _TD_NUM, TD_RED as _TD_RED,
)

def _get_memo(sheet_info, year, month):
    df = load_sheet(sheet_info)
    df['연도'] = df['연도'].astype(str).str.strip()
    df['월']   = df['월'].astype(str).str.strip()
    row = df[(df['연도'] == str(year)) & (df['월'] == str(month))]
    return str(row.iloc[0]['메모']) if not row.empty else ''


# ── 외상매출금 및 받을어음 현황 ───────────────────────────────────────────

def _build_외상매출받을어음_현황(year, month):
    # DB 시트 로드 (Sheets.채권_DB는 설정 파일에 맞게 수정 필요)
    df = load_sheet(Sheets.외상매출받을어음_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    
    # 구분1(외상매출금/받을어음), 구분2(원화/외화 등) 인덱스 설정
    vm = df.set_index(['구분1', '구분2', '연도', '월'])['값'].to_dict()

    def raw(g1, g2, yr, mo):
        # 억원 단위로 변환
        return vm.get((g1, g2, yr, mo), 0.0) / 100000000.0

    prev2_year = year - 2
    prev1_year = year - 1
    recent = _recent_months(year, month) # 최근 3개월 (예: '25 12월, '26 1월, '26 2월)
    
    # 헤더 생성
    prev2_yr_str = str(prev2_year)[-2:]
    prev1_yr_str = str(prev1_year)[-2:]
    col_hdrs = [f"'{prev2_yr_str}년말", f"'{prev1_yr_str}년말"]
    for y, m in recent:
        col_hdrs.append(f"'{str(y)[-2:]}년 {m}월")
    col_hdrs.append("구성")

    structure = {
        '외상매출금': ['원화', '외화'],
        '받을어음': ['자수', '타수']
    }

    # 구성(%) 계산을 위한 당월 총 합계 사전 계산
    grand_total_target = 0.0
    for g1, sub_items in structure.items():
        for g2 in sub_items:
            grand_total_target += raw(g1, g2, year, month)

    rows = []
    num_cols = 2 + len(recent)
    합계_vals = [0.0] * num_cols

    for g1, sub_items in structure.items():
        소계_vals = [0.0] * num_cols
        
        for g2 in sub_items:
            # 과거 연말(12월) 실적 및 최근 N개월 실적 추출
            v_p2 = raw(g1, g2, prev2_year, 12)
            v_p1 = raw(g1, g2, prev1_year, 12)
            v_recents = [raw(g1, g2, y, m) for y, m in recent]
            
            row_data = [v_p2, v_p1] + v_recents
            target_val = raw(g1, g2, year, month)
            ratio = (target_val / grand_total_target * 100) if grand_total_target else 0.0
            
            rows.append(('item', g2, row_data, ratio))
            소계_vals = [a + b for a, b in zip(소계_vals, row_data)]
            
        # 소계 행 추가
        target_sub_val = 소계_vals[-1] # recent 배열의 마지막 값이 당월
        ratio_sub = (target_sub_val / grand_total_target * 100) if grand_total_target else 0.0
        rows.append(('total', g1, 소계_vals, ratio_sub))
        
        # 전체 합계 누적
        합계_vals = [a + b for a, b in zip(합계_vals, 소계_vals)]

    # 최종 합계 행 추가
    rows.append(('total', '합계', 합계_vals, 100.0 if grand_total_target else 0.0))

    return rows, col_hdrs

def _외상매출받을어음_표_to_html(rows, col_hdrs):
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in ['구분'] + col_hdrs)
    body = ''
    
    for kind, label, vals, ratio in rows:
        lbl_s = ROW_HDR_LBL if kind == 'total' else ROW_ITEM
        num_s = ROW_HDR_NUM if kind == 'total' else _TD_NUM
        
        cells = f'<td style="{lbl_s}">{label}</td>'
        
        # ⭕ 실적 값 랜더링 (소수점 첫째자리 표기)
        for v in vals:
            cells += f'<td style="{num_s}">{_fmt(v, decimal=1)}</td>'
            
        # ⭕ 구성비 랜더링 (소수점 첫째자리%)
        cells += f'<td style="{num_s}">{_fmt(ratio, decimal=1)}%</td>'
        body += f'<tr>{cells}</tr>'
        
    return _html_table(f'<tr>{th}</tr>', body)

# ── 부서별 채권기일 현황 ──────────────────────────────────────────────────

def _get_past_month(y, m, offset):
    """지정된 개월 수만큼 과거의 연도와 월을 반환합니다."""
    m -= offset
    while m <= 0:
        m += 12
        y -= 1
    return y, m

def _build_부서별_채권기일_현황(year, month):
    df = load_sheet(Sheets.부서별채권기일_DB) 
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)

    vm = df.set_index(['구분1', '구분2', '연도', '월'])['값'].to_dict()

    def raw(g1, g2, yr, mo):
        return vm.get((g1, g2, yr, mo), 0.0)

    # 기준일자 계산
    y_p2, m_p2 = year - 2, 12
    y_p1, m_p1 = year - 1, 12
    y_m2, m_m2 = _get_past_month(year, month, 2)
    y_m1, m_m1 = _get_past_month(year, month, 1)

    periods = [
        (y_p2, m_p2),
        (y_p1, m_p1),
        (y_m2, m_m2),
        (y_m1, m_m1),
        (year, month)
    ]

    # 컬럼 헤더 생성
    col_headers = [
        '구분',
        f"'{str(y_p2)[-2:]}년말",
        f"'{str(y_p1)[-2:]}년말",
        f"'{str(y_m2)[-2:]}년 {m_m2}월",
        f"'{str(y_m1)[-2:]}년 {m_m1}월",
        f"'{str(year)[-2:]}년 {month}월"
    ]

    부서_list = [
        ('선재', '선재영업팀'),
        ('봉강', '봉강영업팀'),
        ('부산', '부산영업소'),
        ('대구', '대구영업소'),
        ('내수', '내수'),
        ('수출', '수출')
    ]
    metrics = ['매출', '채권', '일수']

    # 금액(매출, 채권) 억원 단위 변환을 위한 나누기 값
    UNIT = 100_000_000.0

    rows = []

    for db_key, display_name in 부서_list:
        rows.append(('section', display_name))

        for metric in metrics:
            vals = []
            for py, pm in periods:
                # 26년 5월 이후 여부 확인
                is_after_2605 = (py > 2026) or (py == 2026 and pm >= 5)
                
                # 내수 데이터 산출 로직 적용
                if db_key == '내수' and is_after_2605:
                    val = sum(raw(k, metric, py, pm) for k in ['선재', '봉강', '부산', '대구'])
                else:
                    val = raw(db_key, metric, py, pm)
                
                # 매출과 채권은 억원 단위로 변환, 일수는 그대로 표기
                if metric in ['매출', '채권']:
                    val = val / UNIT
                vals.append(val)
            
            rows.append(('sub', metric, *vals))

    # --- 합계 섹션 ---
    rows.append(('section', '합계'))
    for metric in metrics:
        vals = []
        for py, pm in periods:
            # 26년 5월 이후 여부 확인
            is_after_2605 = (py > 2026) or (py == 2026 and pm >= 5)
            
            if is_after_2605:
                # 26년 5월부터는 전체 = 내수(선재+봉강+부산+대구) + 수출
                val_naesu = sum(raw(k, metric, py, pm) for k in ['선재', '봉강', '부산', '대구'])
                val_suchul = raw('수출', metric, py, pm)
                val_total = val_naesu + val_suchul
                
                if metric in ['매출', '채권']:
                    val_total = val_total / UNIT
            else:
                # 26년 5월 이전 기존 로직
                if metric == '일수':
                    # 시트에 있는 '합계', '일수' 값을 계산 없이 바로 가져옵니다
                    val_total = raw('전체', '일수', py, pm)
                else:
                    # 매출과 채권은 내수, 수출 단순 합산 후 억원 단위 변환
                    val_total = (raw('내수', metric, py, pm) + raw('수출', metric, py, pm)) / UNIT
                
            vals.append(val_total)
        
        rows.append(('total', metric, *vals))

    return rows, col_headers
def _부서별_채권기일_to_html(rows, col_headers):
    # views.common에 ROW_SEC가 없다면 아래 주석을 해제하여 사용하세요.
    # ROW_SEC = "background:#eef1f6;font-weight:bold;text-align:center;border:1px solid #c0c0c0;padding:5px;"
    
    n_cols = len(col_headers)
    th_cells = "".join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
    th_html = f'<tr>{th_cells}</tr>'

    body_html = ''
    sub_idx = 0

    for row in rows:
        if row[0] == 'section':
            sub_idx = 0
            # 섹션 행은 헤더(구분)를 포함하여 전체 열을 병합합니다.
            body_html += f'<tr><td colspan="{n_cols}" style="{ROW_SEC}">{row[1]}</td></tr>'
        elif row[0] == 'sub':
            _, label, *vals = row
            # 홀수 번째 행은 옅은 배경색, 짝수 번째 행은 흰색으로 교차 적용
            bg = ';background:#f9f9fb' if sub_idx % 2 == 1 else ';background:white'
            sub_idx += 1
            cells = f'<td style="{ROW_ITEM + bg}">{label}</td>'
            for v in vals:
                cells += f'<td style="{(_TD_RED if v < 0 else _TD_NUM) + bg}">{_fmt(v, decimal=0)}</td>'
            body_html += f'<tr>{cells}</tr>'
        elif row[0] == 'total':
            _, label, *vals = row
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_HDR_RED if v < 0 else ROW_HDR_NUM}">{_fmt(v, decimal=0)}</td>'
            body_html += f'<tr>{cells}</tr>'

    return _html_table(th_html, body_html)

# ── 결제조건 초과채권 현황 ────────────────────────────────────────────────

def _build_초과채권_내수(year, month):
    # DB 시트 로드 (설정 파일에 맞게 수정 필요)
    df = load_sheet(Sheets.결제조건초과채권_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    
    vm = df.set_index(['구분1', '연도', '월'])['값'].to_dict()

    def raw(g1, yr, mo):
        # 백만원 단위로 변환
        return vm.get((g1, yr, mo), 0.0) / 1000000.0

    recent = _recent_months(year, month) # 최근 3개월 (예: '25 12월, '26 1월, '26 2월)
    y_p2 = year - 2
    y_p1 = year - 1
    
    # 컬럼 헤더 생성
    col_hdrs = [f"'{str(y_p2)[-2:]}년말", f"'{str(y_p1)[-2:]}년말"]
    for y, m in recent:
        col_hdrs.append(f"'{str(y)[-2:]}년 {m}월")
    col_hdrs.append("전월대비")

    rows = []
    
    # 1. 외상매출금
    ar_vals = [raw('외상매출금', y_p2, 12), raw('외상매출금', y_p1, 12)]
    for y, m in recent:
        ar_vals.append(raw('외상매출금', y, m))
    ar_diff = ar_vals[-1] - ar_vals[-2]
    rows.append(('item', '외상매출금', ar_vals, ar_diff))

    # 2. 조건초과채권
    od_vals = [raw('조건초과채권', y_p2, 12), raw('조건초과채권', y_p1, 12)]
    for y, m in recent:
        od_vals.append(raw('조건초과채권', y, m))
    od_diff = od_vals[-1] - od_vals[-2]
    rows.append(('item', '조건초과채권', od_vals, od_diff))

    # 3. % (비율)
    pct_vals = []
    for ar, od in zip(ar_vals, od_vals):
        pct = (od / ar * 100) if ar else 0.0
        pct_vals.append(pct)
    pct_diff = pct_vals[-1] - pct_vals[-2]
    rows.append(('pct', '%', pct_vals, pct_diff))

    # 4. 이자비용
    int_vals = [raw('이자비용', y_p2, 12), raw('이자비용', y_p1, 12)]
    for y, m in recent:
        int_vals.append(raw('이자비용', y, m))
    int_diff = int_vals[-1] - int_vals[-2]
    rows.append(('item', '이자비용', int_vals, int_diff))

    return rows, col_hdrs

def _초과채권_내수_to_html(rows, col_hdrs):
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in ['구분'] + col_hdrs)
    body = ''
    
    for kind, label, vals, diff in rows:
        cells = f'<td style="{ROW_ITEM}">{label}</td>'
        
        if kind == 'pct':
            for v in vals:
                # 백분율(%) 값 소수점 첫째 자리까지 표시
                cells += f'<td style="{_TD_NUM}">{_fmt(v, decimal=1)}%</td>'
            cells += f'<td style="{_TD_NUM}">{_fmt(diff, decimal=1)}%</td>'
        else:
            for v in vals:
                # 일반 수치 데이터 소수점 첫째 자리까지 표시
                cells += f'<td style="{_TD_NUM}">{_fmt(v, decimal=1)}</td>'
            cells += f'<td style="{_TD_RED if diff < 0 else _TD_NUM}">{_fmt(diff, decimal=1)}</td>'
            
        body += f'<tr>{cells}</tr>'
        
    return _html_table(f'<tr>{th}</tr>', body)



def _build_부서별_초과채권(year, month):
    df = load_sheet(Sheets.부서별초과채권_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)

    vm = df.set_index(['구분1', '구분2', '연도', '월'])['값'].to_dict()

    def raw(dept, metric, yr, mo):
        return vm.get((dept, metric, yr, mo), 0.0) / 1000000.0

    prev_y, prev_m = _get_past_month(year, month, 1)
    y_p1 = year - 1
    
    col_hdrs = [
        f"'{str(y_p1)[-2:]}년말", 
        f"'{str(prev_y)[-2:]}년 {prev_m}월말", 
        "발생", 
        "수금", 
        f"'{str(year)[-2:]}년 {month}월말", 
        "증감", 
        "이자비용 (월)"
    ]
    
    depts = ['선재영업팀', '봉강영업팀', '부산영업소', '대구영업소', 'STS서울영업팀', 'STS부산영업팀', '글로벌구매팀']
    rows = []
    totals = [0.0] * 7
    
    for dept in depts:
        v_yend = raw(dept, '당월말', y_p1, 12)
        v_mend = raw(dept, '당월말', prev_y, prev_m)
        v_gen = raw(dept, '발생', year, month)
        v_col = raw(dept, '수금', year, month)
        v_cur = raw(dept, '당월말', year, month)
        v_diff = v_cur - v_mend  # 당월말 - 전월말 (증감)
        v_int = raw(dept, '이자비용', year, month)
        
        row_data = [v_yend, v_mend, v_gen, v_col, v_cur, v_diff, v_int]
        rows.append(('item', dept, row_data))
        
        totals = [a + b for a, b in zip(totals, row_data)]
        
    rows.append(('total', '합계', totals))
    
    return rows, col_hdrs

def _부서별_초과채권_to_html(rows, col_hdrs):
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in ['구분'] + col_hdrs)
    body = ''
    
    for kind, label, vals in rows:
        lbl_s = ROW_HDR_LBL if kind == 'total' else ROW_ITEM
        num_s = ROW_HDR_NUM if kind == 'total' else _TD_NUM
        
        cells = f'<td style="{lbl_s}">{label}</td>'
        
        for idx, v in enumerate(vals):
            # 5번째 인덱스는 '증감' 컬럼이므로 음수일 때 빨간색 처리
            if idx == 5 and v < 0:
                # 증감(음수) 값 소수점 첫째 자리까지 표시
                cells += f'<td style="{ROW_HDR_RED if kind == "total" else _TD_RED}">{_fmt(v, decimal=1)}</td>'
            else:
                # 나머지 데이터 소수점 첫째 자리까지 표시
                cells += f'<td style="{num_s}">{_fmt(v, decimal=1)}</td>'
                
        body += f'<tr>{cells}</tr>'
        
    return _html_table(f'<tr>{th}</tr>', body)

# ── render_page ───────────────────────────────────────────────────────────

def render_page(app, year_state, month_state):

    def _render_title():
        app.markdown(
            f'<h1 style="color:#404448">{int(year_state.value)}년 {int(month_state.value)}월 채권 분석</h1>',
            unsafe_allow_html=True,
        )
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["외상매출금 및 받을어음 현황", "부서별 채권기일 현황", "결제조건 초과채권 현황"])

    with tabs[0]:
        def _render_외상매출금_현황():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_hdrs = _build_외상매출받을어음_현황(year, month)
            
            memo = _get_memo(Sheets.외상매출받을어음_메모, year, month)
            
            app.markdown(
                _layout64('1) 외상매출금 및 받을어음 현황',
                          _외상매출받을어음_표_to_html(rows, col_hdrs),
                          memo,
                          unit='(단위 : 억원)'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_외상매출금_현황)

    with tabs[1]:
        def _render_부서별_기일():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_headers = _build_부서별_채권기일_현황(year, month)
            
            memo = _get_memo(Sheets.부서별채권기일_메모, year, month)
            
            app.markdown(
                _layout64('1) 부서별 채권기일 현황',
                          _부서별_채권기일_to_html(rows, col_headers),
                          memo,
                          unit='(단위 : 억원, 일)'),
                unsafe_allow_html=True,
            )

            app.markdown(
                '<p style="margin:4px 0 0 0; font-size:0.8em; color:gray; text-align:left;">'
                '※ 글로벌구매팀(BW), STS영업팀 채권 제외'
                '</p>',
                unsafe_allow_html=True,
            )

        app.If(lambda: True, _render_부서별_기일)

    with tabs[2]:
        def _render_초과채권():
            year, month = int(year_state.value), int(month_state.value)
            
            # 1) 결제조건 초과채권 현황(내수)
            rows1, col_hdrs1 = _build_초과채권_내수(year, month)
            memo10 = _get_memo(Sheets.결제조건초과채권_메모, year, month)
            
            app.markdown(
                _layout64('1) 결제조건 초과채권 현황(내수)',
                          _초과채권_내수_to_html(rows1, col_hdrs1),
                          memo10,
                          unit='(단위 : 백만원)'),
                unsafe_allow_html=True,
            )
            
            app.markdown("<br><hr style='border-top: 1px solid #ddd;'><br>", unsafe_allow_html=True)

            # 2) 부서별 결제조건 초과채권 발생/수금 현황
            rows2, col_hdrs2 = _build_부서별_초과채권(year, month)
            memo2 = _get_memo(Sheets.부서별초과채권_메모, year, month) if hasattr(Sheets, '부서별초과채권_메모') else ""
            
            app.markdown(
                _layout64('2) 부서별 결제조건 초과채권 발생/수금 현황',
                          _부서별_초과채권_to_html(rows2, col_hdrs2),
                          memo2,
                          unit='(단위 : 백만원)'),
                unsafe_allow_html=True,
            )
            
        app.If(lambda: True, _render_초과채권)