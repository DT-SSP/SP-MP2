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


# ── 월평균 생산실적 ────────────────────────────────────────────────────

def _build_생산실적(year, month):

    df = load_sheet(Sheets.전체생산실적_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    
    # 구분1(상위구분), 구분2(하위구분)를 모두 인덱스로 설정
    vm = df.set_index(['구분1', '구분2', '연도', '월'])['값'].to_dict()

    def raw(g1, g2, yr, mo):
        return vm.get((g1, g2, yr, mo), 0.0)

    def yr_avg(g1, g2, yr):
        # 당해년도(조회 중인 연도)는 아직 발생하지 않은 미래월(빈 값이 0으로 채워진 행 포함)이
        # 평균에 섞이지 않도록 조회월까지만 집계한다. 과거 연도는 12개월 전체를 집계.
        last_mo = month if yr == year else 12
        vals = [raw(g1, g2, yr, m) for m in range(1, last_mo + 1) if (g1, g2, yr, m) in vm]
        return sum(vals) / len(vals) if vals else 0.0

    연도_in_db = sorted(df['연도'].unique().tolist())
    recent = _recent_months(year, month)
    col_hdrs = _build_col_hdrs(연도_in_db, recent, annual_suffix='.평균')

    prev_yr, prev_mo = _prev(year, month)
    
    # 상위구분과 하위구분 매핑
    structure = {
        'CHQ': ['포항', '충주'],
        'CD': ['포항', '충주2'],
        'STS': ['포항', '충주2'],
        'BTB': ['포항', '충주2'],
        'PB': ['충주2']
    }

    rows = []
    합계_main = [0.0] * (len(연도_in_db) + len(recent))
    합계_당월 = 0.0
    합계_전월 = 0.0

    factory_totals = {
        '포항': {'main': [0.0] * (len(연도_in_db) + len(recent)), '당월': 0.0, '전월': 0.0},
        '충주': {'main': [0.0] * (len(연도_in_db) + len(recent)), '당월': 0.0, '전월': 0.0},
        '충주2': {'main': [0.0] * (len(연도_in_db) + len(recent)), '당월': 0.0, '전월': 0.0}
    }


    for g1, sub_items in structure.items():
        소계_main = [0.0] * (len(연도_in_db) + len(recent))
        소계_당월 = 0.0
        소계_전월 = 0.0

        # 하위구분(포항, 충주 등) 데이터 계산
        for g2 in sub_items:
            main = [yr_avg(g1, g2, yr) for yr in 연도_in_db] + \
                   [raw(g1, g2, yr_c, mo_c) for yr_c, mo_c in recent]
            당월 = raw(g1, g2, year, month)
            전월 = raw(g1, g2, prev_yr, prev_mo)
            mom = 당월 - 전월
            pct = (mom / 전월 * 100) if 전월 else 0.0
            
            rows.append(('item', g2, main, mom, pct))
            
            소계_main = [a + b for a, b in zip(소계_main, main)]
            소계_당월 += 당월
            소계_전월 += 전월

            if g2 in factory_totals:
                factory_totals[g2]['main'] = [a + b for a, b in zip(factory_totals[g2]['main'], main)]
                factory_totals[g2]['당월'] += 당월
                factory_totals[g2]['전월'] += 전월

        # 상위구분(CHQ, CD) 소계 계산
        mom_소계 = 소계_당월 - 소계_전월
        pct_소계 = (mom_소계 / 소계_전월 * 100) if 소계_전월 else 0.0
        rows.append(('total', f'{g1}', 소계_main, mom_소계, pct_소계))

        합계_main = [a + b for a, b in zip(합계_main, 소계_main)]
        합계_당월 += 소계_당월
        합계_전월 += 소계_전월

    # 전체 합계 계산
    mom_합 = 합계_당월 - 합계_전월
    pct_합 = (mom_합 / 합계_전월 * 100) if 합계_전월 else 0.0
    rows.append(('total', '합계', 합계_main, mom_합, pct_합))

    for f_name in ['포항', '충주', '충주2']:
        f_main = factory_totals[f_name]['main']
        f_당월 = factory_totals[f_name]['당월']
        f_전월 = factory_totals[f_name]['전월']
        
        f_mom = f_당월 - f_전월
        f_pct = (f_mom / f_전월 * 100) if f_전월 else 0.0
        
        rows.append(('total', f'{f_name} 합계', f_main, f_mom, f_pct))

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
        cells += f'<td style="{red_s if pct < 0 else num_s}">{_fmt(pct, decimal=1)}%</td>'
        body += f'<tr>{cells}</tr>'
    return _html_table(f'<tr>{th}</tr>', body)


# ── 부적합 발생 현황 ────────────────────────────────────────────────

def _build_부적합_포항(year, month):
    df = load_sheet(Sheets.부적합발생추이_포항_충주_충주2_DB) 
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    
    # 구분1(포항/충주), 구분2(CHQ/CD), 구분3(공정성/소재성) 모두 인덱스로 설정
    vm = df.set_index(['구분1', '구분2', '구분3', '연도', '월'])['값'].to_dict()

    def raw(g1, g2, g3, yr, mo):
        return vm.get((g1, g2, g3, yr, mo), 0.0)

    # 전년도 평균 계산용 함수
    def prev_yr_avg(g1, g2, g3, prev_yr):
        vals = [raw(g1, g2, g3, prev_yr, m) for m in range(1, 13) if (g1, g2, g3, prev_yr, m) in vm]
        return sum(vals) / len(vals) if vals else 0.0

    prev_year = year - 1
    recent = _recent_months(year, month)
    
    # 헤더 생성: ['25년 월평균, '26년 목표, '25년 12월, '26년 1월, '26년 2월, 합계, 월평균]
    prev_yr_str = str(prev_year)[-2:]
    curr_yr_str = str(year)[-2:]
    col_hdrs = [f"'{prev_yr_str}.평균", f"'{curr_yr_str}.목표"]
    for y, m in recent:
        col_hdrs.append(f"'{str(y)[-2:]}.{m}월")
    col_hdrs.extend(["누적", "평균"])

    rows = []
    num_cols = 2 + len(recent) + 2
    
    # 포항 전체(Grand Total) 누적용 리스트 초기화
    grand_total_공정성 = [0.0] * num_cols
    grand_total_소재성 = [0.0] * num_cols
    grand_total = [0.0] * num_cols

    for g2 in ['CHQ', 'CD']:
        subtotal = [0.0] * num_cols
        
        for g3 in ['공정성', '소재성']:
            p_avg = prev_yr_avg('포항', g2, g3, prev_year)
            # 1) 목표: 전년도 각 분류별 월평균의 50% 반영
            target = p_avg * 0.5
            
            recents = [raw('포항', g2, g3, y, m) for y, m in recent]
            
            # 2) 합계: 선택한 연도(year)의 1월부터 선택월(month)까지의 누적 합계
            ytd_vals = [raw('포항', g2, g3, year, m) for m in range(1, month + 1)]
            sum_r = sum(ytd_vals)
            
            # 3) 월평균: 누적 합계를 누적월(month)로 나눈 값
            avg_r = sum_r / month if month > 0 else 0.0
            
            row_data = [p_avg, target] + recents + [sum_r, avg_r]
            rows.append(('item', g3, row_data))
            
            # 제품군(CHQ, CD) 소계 누적
            subtotal = [a + b for a, b in zip(subtotal, row_data)]
            
            # 전체 합계(공정성/소재성 분리) 누적
            if g3 == '공정성':
                grand_total_공정성 = [a + b for a, b in zip(grand_total_공정성, row_data)]
            else:
                grand_total_소재성 = [a + b for a, b in zip(grand_total_소재성, row_data)]
                
        # 제품군(CHQ, CD) 소계 행 추가
        rows.append(('total', g2, subtotal))
        # 포항 전체 누적
        grand_total = [a + b for a, b in zip(grand_total, subtotal)]

    # 포항 하단 합계 영역 구성 (공정성 -> 소재성 -> 포항 총계)
    rows.append(('item', '공정성', grand_total_공정성))
    rows.append(('item', '소재성', grand_total_소재성))
    rows.append(('total', '포항', grand_total))

    return rows, col_hdrs

def _build_부적합_충주(year, month):
    df = load_sheet(Sheets.부적합발생추이_포항_충주_충주2_DB) 
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    
    vm = df.set_index(['구분1', '구분2', '구분3', '연도', '월'])['값'].to_dict()

    def raw(g1, g2, g3, yr, mo):
        return vm.get((g1, g2, g3, yr, mo), 0.0)

    def prev_yr_avg(g1, g2, g3, prev_yr):
        vals = [raw(g1, g2, g3, prev_yr, m) for m in range(1, 13) if (g1, g2, g3, prev_yr, m) in vm]
        return sum(vals) / len(vals) if vals else 0.0

    prev_year = year - 1
    recent = _recent_months(year, month)
    
    prev_yr_str = str(prev_year)[-2:]
    curr_yr_str = str(year)[-2:]
    col_hdrs = [f"'{prev_yr_str}.평균", f"'{curr_yr_str}.목표"]
    for y, m in recent:
        col_hdrs.append(f"'{str(y)[-2:]}.{m}월")
    col_hdrs.extend(["누적", "평균"])

    rows = []
    num_cols = 2 + len(recent) + 2
    
    grand_total_공정성 = [0.0] * num_cols
    grand_total_소재성 = [0.0] * num_cols
    grand_total = [0.0] * num_cols

    g1 = '충주'
    g2_list = sorted(list(set([k[1] for k in vm.keys() if k[0] == g1])))
    if not g2_list:
        g2_list = ['CHQ']

    for g2 in g2_list:
        subtotal = [0.0] * num_cols
        
        for g3 in ['공정성', '소재성']:
            p_avg = prev_yr_avg(g1, g2, g3, prev_year)
            target = p_avg * 0.5
            recents = [raw(g1, g2, g3, y, m) for y, m in recent]
            sum_r = sum([raw(g1, g2, g3, year, m) for m in range(1, month + 1)])
            avg_r = sum_r / month if month > 0 else 0.0
            
            row_data = [p_avg, target] + recents + [sum_r, avg_r]
            rows.append(('item', g3, row_data))
            
            subtotal = [a + b for a, b in zip(subtotal, row_data)]
            
            if g3 == '공정성':
                grand_total_공정성 = [a + b for a, b in zip(grand_total_공정성, row_data)]
            else:
                grand_total_소재성 = [a + b for a, b in zip(grand_total_소재성, row_data)]
                
        rows.append(('total', 'CHQ(충주)', subtotal))
        grand_total = [a + b for a, b in zip(grand_total, subtotal)]

    # 수정된 부분: 하단 총계를 계산하기 위해 변수 3개 추가 반환
    return rows, col_hdrs, grand_total_공정성, grand_total_소재성, grand_total

def _build_부적합_충주2(year, month):
    df = load_sheet(Sheets.부적합발생추이_포항_충주_충주2_DB) 
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    
    vm = df.set_index(['구분1', '구분2', '구분3', '연도', '월'])['값'].to_dict()

    def raw(g1, g2, g3, yr, mo):
        return vm.get((g1, g2, g3, yr, mo), 0.0)

    def prev_yr_avg(g1, g2, g3, prev_yr):
        vals = [raw(g1, g2, g3, prev_yr, m) for m in range(1, 13) if (g1, g2, g3, prev_yr, m) in vm]
        return sum(vals) / len(vals) if vals else 0.0

    prev_year = year - 1
    recent = _recent_months(year, month)
    
    prev_yr_str = str(prev_year)[-2:]
    curr_yr_str = str(year)[-2:]
    col_hdrs = [f"'{prev_yr_str}.평균", f"'{curr_yr_str}.목표"]
    for y, m in recent:
        col_hdrs.append(f"'{str(y)[-2:]}.{m}월")
    col_hdrs.extend(["누적", "평균"])

    rows = []
    num_cols = 2 + len(recent) + 2
    
    grand_total_공정성 = [0.0] * num_cols
    grand_total_소재성 = [0.0] * num_cols
    grand_total = [0.0] * num_cols

    g1 = '충주2'
    g2_list = sorted(list(set([k[1] for k in vm.keys() if k[0] == g1])))
    if not g2_list:
        g2_list = ['CD']

    for g2 in g2_list:
        subtotal = [0.0] * num_cols
        
        for g3 in ['공정성', '소재성']:
            p_avg = prev_yr_avg(g1, g2, g3, prev_year)
            target = p_avg * 0.5
            recents = [raw(g1, g2, g3, y, m) for y, m in recent]
            sum_r = sum([raw(g1, g2, g3, year, m) for m in range(1, month + 1)])
            avg_r = sum_r / month if month > 0 else 0.0
            
            row_data = [p_avg, target] + recents + [sum_r, avg_r]
            rows.append(('item', g3, row_data))
            
            subtotal = [a + b for a, b in zip(subtotal, row_data)]
            
            if g3 == '공정성':
                grand_total_공정성 = [a + b for a, b in zip(grand_total_공정성, row_data)]
            else:
                grand_total_소재성 = [a + b for a, b in zip(grand_total_소재성, row_data)]
                
        rows.append(('total', '마봉강(충주2)', subtotal))
        grand_total = [a + b for a, b in zip(grand_total, subtotal)]

    # 수정된 부분: 하단 총계를 계산하기 위해 변수 3개 추가 반환
    return rows, col_hdrs, grand_total_공정성, grand_total_소재성, grand_total

def _부적합_표_to_html(rows, col_hdrs):
    th = ''.join(f'<th style="{_TH}">{h}</th>' for h in ['구분'] + col_hdrs)
    body = ''
    for kind, label, vals in rows:
        lbl_s = ROW_HDR_LBL if kind == 'total' else ROW_ITEM
        num_s = ROW_HDR_NUM if kind == 'total' else _TD_NUM
        cells = f'<td style="{lbl_s}">{label}</td>'
        cells += ''.join(f'<td style="{num_s}">{_fmt(v)}</td>' for v in vals)
        body += f'<tr>{cells}</tr>'
    return _html_table(f'<tr>{th}</tr>', body)

# ── render_page ───────────────────────────────────────────────────────────

def render_page(app, year_state, month_state):

    def _render_title():
        app.markdown(
            f'<h1 style="color:#404448">{int(year_state.value)}년 {int(month_state.value)}월 생산분석</h1>',
            unsafe_allow_html=True,
        )
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["생산실적", "부적합 발생내역(포항공장)", "부적합 발생내역(충주공장)"])

    with tabs[0]:
        def _render_생산실적():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_hdrs = _build_생산실적(year, month)
            memo = _get_memo(Sheets.전체생산실적_메모, year, month)
            app.markdown(
                _layout64('1) 전체 생산실적',
                          _생산실적_to_html(rows, col_hdrs),
                          memo,
                          unit='(단위: 톤)'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_생산실적)

    with tabs[1]:
        def _render_불량_포항():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_hdrs = _build_부적합_포항(year, month)
            memo = _get_memo(Sheets.부적합발생추이_포항_메모, year, month) 

            app.markdown(
                _layout64('1) 부적합 발생내역 (포항)',
                          _부적합_표_to_html(rows, col_hdrs),
                          memo,
                          unit='(단위 : 톤, %)'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_불량_포항)
        
    with tabs[2]:
        def _render_불량_충주():
            year, month = int(year_state.value), int(month_state.value)
            
            # 1) 충주 1공장 데이터 가져오기 (반환된 총계 3개 포함)
            rows1, col_hdrs, g1_공, g1_소, g1_합 = _build_부적합_충주(year, month)
            
            # 2) 충주 2공장 데이터 가져오기 (반환된 총계 3개 포함)
            rows2, _, g2_공, g2_소, g2_합 = _build_부적합_충주2(year, month)
            
            # 3) 두 공장의 데이터를 하나의 리스트로 통합하며 행 이름(Label) 변경
            combined_rows = []
            for kind, label, vals in rows1:
                new_label = f"{label}" if kind == 'item' else f"{label}"
                combined_rows.append((kind, new_label, vals))
                
            for kind, label, vals in rows2:
                new_label = f"{label}" if kind == 'item' else f"{label}"
                combined_rows.append((kind, new_label, vals))

            final_공정성 = [a + b for a, b in zip(g1_공, g2_공)]
            final_소재성 = [a + b for a, b in zip(g1_소, g2_소)]
            final_총계 = [a + b for a, b in zip(g1_합, g2_합)]
            
            combined_rows.append(('item', '공정성', final_공정성))
            combined_rows.append(('item', '소재성', final_소재성))
            combined_rows.append(('total', '충주', final_총계))
            # -----------------------------------------------------------------
                
            # 통합된 메모 (기존 충주 1공장 메모 사용)
            memo = _get_memo(Sheets.부적합발생추이_충주_충주2_메모, year, month)
            
            # 4) 하나의 레이아웃으로 렌더링
            app.markdown(
                _layout64('1) 부적합 발생내역 (충주)',
                          _부적합_표_to_html(combined_rows, col_hdrs),
                          memo,
                          unit='(단위 : 톤, %)'),
                unsafe_allow_html=True,
            )
            
        app.If(lambda: True, _render_불량_충주)