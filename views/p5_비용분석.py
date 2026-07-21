import datetime
import plotly.graph_objects as go
import pandas as pd
from data.loader import load_sheet
from data.config import Sheets
from views.common import (
    parse as _parse, fmt as _fmt,
    drop_empty as _drop_empty,
    prev_month as _prev,
    recent_months as _recent_months, build_col_hdrs as _build_col_hdrs,
    TH as _TH, TD_NUM as _TD_NUM, TD_LBL as _TD_LBL, TD_RED as _TD_RED, C_RED as _C_RED,
    ROW_SEC, ROW_GRP, ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED, ROW_ITEM,
    ROW_CAL_LBL, ROW_CAL_NUM, ROW_CAL_RED,
    html_table as _html_table, layout64 as _layout64, layout100 as _layout100, C_NAVY
)

# 외주용역비 수량 키 감지 키워드 (구분2 값에 포함될 경우 qty로 판별)
_외주_QTY_KW = ('수량', '생산량', '시간', '개', 'EA', '톤', 'kg', '량')
# 수량 단위별 단가 환산 배율 (미등록 단위는 기본 100 적용)
_외주_단가_배율 = {'시간': 1_000_000}


def _get_연도_목록():
    df = load_sheet(Sheets.운반실적및컨테이너단가_DB)
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


# ── 1) 부재료 사용량 원단위 ─────────────────────────────────

def _build_부재료_data(사업장, year, month):
    # 1. DB 로드
    df = load_sheet(Sheets.부재료사용량_DB) 
    
    # 컬럼명 공백 제거
    df.columns = df.columns.str.strip()
    
    # 💡 [수정] 선택한 월 기준으로 과거 12개월의 (연, 월) 리스트 명시적 생성
    recent = []
    curr_y, curr_m = year, month
    for _ in range(12):
        recent.insert(0, (curr_y, curr_m))
        curr_y, curr_m = _prev(curr_y, curr_m)
    
    # 2. 필수 컬럼 존재 여부 확인 (시트가 잘못 연결된 경우 방지)
    required_cols = ['사업장', '구분1', '연도', '월', '값']
    for col in required_cols:
        if col not in df.columns:
            return [(f'오류: [{col}] 컬럼 없음', [0.0] * 12)], [f"'{str(y)[2:]}년 {m:02d}월" for y, m in recent]

    # 3. [핵심] 기존 _drop_empty() 함수 사용 배제
    df['사업장'] = df['사업장'].astype(str).str.replace(' ', '', regex=False)
    df['구분1'] = df['구분1'].astype(str).str.strip()
    
    # 연도/월 숫자 강제 변환
    df['연도'] = df['연도'].astype(str).str.replace('년', '', regex=False).str.replace(' ', '', regex=False)
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    
    df['월'] = df['월'].astype(str).str.replace('월', '', regex=False).str.replace(' ', '', regex=False)
    df['월'] = pd.to_numeric(df['월'], errors='coerce').fillna(0).astype(int)

    df['값'] = df['값'].apply(_parse)

    # 4. 사업장 필터링
    target_사업장 = 사업장.replace(' ', '')
    df_target = df[df['사업장'] == target_사업장]
    
    vm = df_target.set_index(['구분1', '연도', '월'])['값'].to_dict()

    # 테이블 헤더용 텍스트 생성 ('25년 03월 형식)
    col_hdrs = [f"'{str(y)[2:]}년 {m:02d}월" for y, m in recent]

    # 5. DB에 등록된 항목 리스트 추출
    items = list(dict.fromkeys(df_target['구분1'].tolist()))
    
    # 💡 [디버깅 안전장치]
    if not items:
        items = [f'데이터 없음 (DB 내 {사업장} 확인 필요)']

    rows = []
    for item in items:
        # 생성한 12개월(recent) 리스트를 바탕으로 값 추출
        vals = [vm.get((item, y, m), 0.0) for y, m in recent]
        rows.append((item, vals))

    return rows, col_hdrs


def _build_부재료_table_html(사업장, rows, col_hdrs):
    """부재료 사용량 테이블 HTML을 생성합니다."""
    th = f'<th style="{_TH}">{사업장}</th>'
    for h in col_hdrs:
        th += f'<th style="{_TH}">{h}</th>'
    thead = f'<tr>{th}</tr>'

    body = ''
    for item, vals in rows:
        cells = f'<td style="{ROW_ITEM}">{item}</td>'
        for v in vals:
            cells += f'<td style="{_TD_NUM}">{_fmt(v)}</td>'
        body += f'<tr>{cells}</tr>'

    return _html_table(thead, body)


def _build_부재료_chart(사업장, rows, col_hdrs):
    """부재료 사용량 Plotly 차트를 생성합니다."""
    fig = go.Figure()

    # 이미지에 맞춘 기본 색상 배열 (필요시 수정)
    colors = ['#1f77b4', '#aec7e8', '#d62728', '#ff9896', '#2ca02c']

    for idx, (item, vals) in enumerate(rows):
        fig.add_trace(go.Scatter(
            name=item,
            x=col_hdrs,
            y=vals,
            mode='lines+markers+text',
            text=[f"{v:.1f}" if v else '' for v in vals],
            textposition='top center',
            textfont=dict(size=10, color='#4a5568'),
            marker=dict(size=6, color=colors[idx % len(colors)]),
            line=dict(width=2, color=colors[idx % len(colors)])
        ))

    # 차트 레이아웃 설정
    fig.update_layout(
        #title=dict(text=f"[{사업장}]", font=dict(size=13, color="#404448", weight='bold')),
        height=350,
        margin=dict(l=10, r=120, t=40, b=40),
        legend=dict(
            orientation='v', 
            y=0.5, x=1.02, # 범례를 우측 중앙에 배치
            xanchor='left', yanchor='middle',
            font=dict(size=11), bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            tickfont=dict(size=10, color='#4a5568'),
            showgrid=False, linecolor='#e2e8f0', linewidth=1, showline=True,
            tickangle=45
        ),
        yaxis=dict(
            showgrid=True, gridcolor='#e2e8f0', gridwidth=1,
            showticklabels=False, showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=11, family='sans-serif'),
    )
    return fig

# ── 1-2) 주요 부재료 단가 추이 (4번 항목 전용) ───────────────────────────

def _build_단가추이_data(year, month):
    df = load_sheet(Sheets.부재료단가추이_DB) 
    df.columns = df.columns.str.strip()
    
    # 12개월 (연, 월) 리스트 명시적 생성
    recent = []
    curr_y, curr_m = year, month
    for _ in range(12):
        recent.insert(0, (curr_y, curr_m))
        curr_y, curr_m = _prev(curr_y, curr_m)
    
    required_cols = ['구분1', '연도', '월', '값']
    for col in required_cols:
        if col not in df.columns:
            return [(f'오류: [{col}] 컬럼 없음', [0.0] * 12)], [f"'{str(y)[2:]}년 {m:02d}월" for y, m in recent]

    # 데이터 클렌징 (사업장 제외)
    df['구분1'] = df['구분1'].astype(str).str.strip()
    df['연도'] = df['연도'].astype(str).str.replace('년', '', regex=False).str.replace(' ', '', regex=False)
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    df['월'] = df['월'].astype(str).str.replace('월', '', regex=False).str.replace(' ', '', regex=False)
    df['월'] = pd.to_numeric(df['월'], errors='coerce').fillna(0).astype(int)
    df['값'] = df['값'].apply(_parse)

    vm = df.set_index(['구분1', '연도', '월'])['값'].to_dict()
    col_hdrs = [f"'{str(y)[2:]}년 {m:02d}월" for y, m in recent]

    items = list(dict.fromkeys(df['구분1'].tolist()))
    if not items:
        items = ['데이터 없음 (DB 시트 연결 확인 필요)']

    rows = []
    for item in items:
        vals = [vm.get((item, y, m), 0.0) for y, m in recent]
        rows.append((item, vals))

    return rows, col_hdrs


def _build_단가추이_table_html(rows, col_hdrs):
    th = f'<th style="{_TH}"></th>'
    for h in col_hdrs:
        th += f'<th style="{_TH}">{h}</th>'
    thead = f'<tr>{th}</tr>'

    body = ''
    for item, vals in rows:
        cells = f'<td style="{ROW_ITEM}">{item}</td>'
        for v in vals:
            cells += f'<td style="{_TD_NUM}">{_fmt(v)}</td>'
        body += f'<tr>{cells}</tr>'

    return _html_table(thead, body)


def _build_단가추이_chart(rows, col_hdrs):
    fig = go.Figure()

    colors = ['#1f77b4', '#ff7f0e', '#7f7f7f', '#bcbd22', '#ffbb78', '#d62728']

    for idx, (item, vals) in enumerate(rows):
        fig.add_trace(go.Scatter(
            name=item,
            x=col_hdrs,
            y=vals,
            mode='lines+markers+text',
            text=[f"{v:.1f}" if v else '' for v in vals],
            textposition='top center',
            textfont=dict(size=10, color='#4a5568'),
            marker=dict(size=6, color=colors[idx % len(colors)]),
            line=dict(width=2, color=colors[idx % len(colors)])
        ))

    fig.update_layout(
        height=350,
        margin=dict(l=10, r=120, t=40, b=40),
        legend=dict(
            orientation='v', 
            y=0.5, x=1.02, 
            xanchor='left', yanchor='middle',
            font=dict(size=11), bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            tickfont=dict(size=10, color='#4a5568'),
            showgrid=False, linecolor='#e2e8f0', linewidth=1, showline=True,
            tickangle=45
        ),
        yaxis=dict(
            showgrid=True, gridcolor='#e2e8f0', gridwidth=1,
            showticklabels=False, showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=11, family='sans-serif'),
    )
    return fig

# ── 클레임 현황 (월 평균 & 당월) ──────────────────────────────────────────

def _build_월평균클레임_data(year, month):
    df = load_sheet(Sheets.월평균클레임_DB) 
    df.columns = df.columns.str.strip()

    required_cols = ['구분1', '연도', '월', '값']
    for col in required_cols:
        if col not in df.columns:
            return [('item', f'오류: [{col}] 없음', [0.0] * 4)], [f"'{str(year-3)[2:]}년", f"'{str(year-2)[2:]}년", f"'{str(year-1)[2:]}년", f"'{str(year)[2:]}년"]

    # 데이터 클렌징
    df['구분1'] = df['구분1'].astype(str).str.strip()
    df['연도'] = df['연도'].astype(str).str.replace('년', '', regex=False).str.replace(' ', '', regex=False)
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    
    # 값 파싱 및 백만원 단위 환산
    df = df.copy()
    df['값'] = df['값'].apply(_parse) / 1_000_000.0
    df['값'] = df['값'].round(0).astype(int)
    #df['값'] = df['값'].apply(_parse)

    # 연도별 월평균 계산
    avg_df = df.groupby(['구분1', '연도'])['값'].mean().reset_index()
    vm = avg_df.set_index(['구분1', '연도'])['값'].to_dict()

    # 최근 4개년 (예: '23, '24, '25, '26)
    years = [year - 3, year - 2, year - 1, year]
    col_hdrs = [f"'{str(y)[2:]}년" for y in years]

    items = ['선재', '봉강', '부산', '대구', '글로벌']
    rows = []
    totals = [0.0] * len(years)

    for item in items:
        vals = [vm.get((item, y), 0.0) for y in years]
        rows.append(('item', item, vals))
        for i, v in enumerate(vals):
            totals[i] += v

    rows.append(('total', '합계', totals))
    return rows, col_hdrs

def _build_월평균클레임_table_html(rows, col_hdrs):
    th = f'<th style="{_TH}">구분</th>' + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_hdrs)
    body = ''
    for kind, label, vals in rows:
        lbl_s = ROW_HDR_LBL if kind == 'total' else ROW_ITEM
        num_s = ROW_HDR_NUM if kind == 'total' else _TD_NUM
        
        cells = f'<td style="{lbl_s}">{label}</td>'
        for v in vals:
            formatted_v = f"{v:,.0f}" if v != 0 else "0"
            cells += f'<td style="{num_s}">{formatted_v}</td>'
        body += f'<tr>{cells}</tr>'
        
    return _html_table(f'<tr>{th}</tr>', body)


def _build_당월클레임_data(year, month):
    df = load_sheet(Sheets.당월클레임_DB)
    df.columns = df.columns.str.strip()

    required_cols = ['구분1', '구분2', '연도', '월', '값']
    for col in required_cols:
        if col not in df.columns:
            return [('item', f'오류: [{col}] 없음', [0.0] * 4)], ["오류"] * 4

    # 데이터 클렌징
    df['구분1'] = df['구분1'].astype(str).str.strip()
    df['구분2'] = df['구분2'].astype(str).str.strip()
    df['연도'] = df['연도'].astype(str).str.replace('년', '', regex=False).str.replace(' ', '', regex=False)
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    df['월'] = df['월'].astype(str).str.replace('월', '', regex=False).str.replace(' ', '', regex=False)
    df['월'] = pd.to_numeric(df['월'], errors='coerce').fillna(0).astype(int)
    
    # 값 파싱 및 백만원 단위 환산
    df = df.copy()
    df['값'] = df['값'].apply(_parse) / 1_000_000.0
    df['값'] = df['값'].round(0).astype(int)
    #df['값'] = df['값'].apply(_parse)

    vm = df.groupby(['구분1', '구분2', '연도', '월'])['값'].sum().to_dict()

    # 최근 3개월 (과거순 -> 당월)
    recent = []
    curr_y, curr_m = year, month
    for _ in range(3):
        recent.insert(0, (curr_y, curr_m))
        curr_y, curr_m = _prev(curr_y, curr_m)

    col_hdrs = [f"'{str(y)[2:]}년 {m}월" for y, m in recent] + ['증감']

    items = ['선재', '봉강', '부산', '대구', '글로벌']
    sub_items = ['선별비', '불량 보상']

    rows = []
    grand_totals = {'total': [0.0]*3, '선별비': [0.0]*3, '불량 보상': [0.0]*3}

    for item in items:
        item_totals = [0.0] * 3
        sub_rows = []
        for sub in sub_items:
            vals = [vm.get((item, sub, y, m), 0.0) for y, m in recent]
            for i, v in enumerate(vals):
                item_totals[i] += v
                grand_totals[sub][i] += v
                grand_totals['total'][i] += v
            
            # 증감 계산 (최근월 - 직전월)
            diff = vals[-1] - vals[-2] if len(vals) >= 2 else 0.0
            sub_rows.append(('sub', sub, vals + [diff]))

        diff_total = item_totals[-1] - item_totals[-2] if len(item_totals) >= 2 else 0.0
        rows.append(('item', item, item_totals + [diff_total]))
        rows.extend(sub_rows)

    # 전체 합계 행 구성
    diff_g = grand_totals['total'][-1] - grand_totals['total'][-2]
    rows.append(('total', '합계', grand_totals['total'] + [diff_g]))
    
    for sub in sub_items:
        diff_s = grand_totals[sub][-1] - grand_totals[sub][-2]
        rows.append(('sub', sub, grand_totals[sub] + [diff_s]))

    return rows, col_hdrs

def _build_당월클레임_table_html(rows, col_hdrs):
    th = f'<th style="{_TH}">클레임비</th>' + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_hdrs)
    body = ''
    for kind, label, vals in rows:
        if kind == 'total':
            lbl_s, num_s = ROW_HDR_LBL, ROW_HDR_NUM
        elif kind == 'item':
            lbl_s, num_s = ROW_ITEM, _TD_NUM
        else:
            lbl_s, num_s = f'{ROW_ITEM}; color: #4b5563;', _TD_NUM
            label = f'&nbsp;&nbsp;&nbsp;&nbsp; {label}'

        cells = f'<td style="{lbl_s}">{label}</td>'
        for i, v in enumerate(vals):
            is_diff = (i == len(vals) - 1) # 증감 컬럼 여부
            
            # 음수일 경우 붉은색 텍스트 적용
            s = ROW_HDR_RED if (kind == 'total' and is_diff and v < 0) else \
                _TD_RED if (is_diff and v < 0) else num_s
            
            formatted_v = f"{v:,.0f}" if v != 0 else "0"
            if formatted_v == "-0": formatted_v = "0"
            
            cells += f'<td style="{s}">{formatted_v}</td>'
        body += f'<tr>{cells}</tr>'
        
    return _html_table(f'<tr>{th}</tr>', body)

# ── 3) 영업외 비용 내역 (최근 3개월) ──────────────────────────────────────

def _build_영업외비용_data(year, month):
    df = load_sheet(Sheets.영업외비용_DB)
    df.columns = df.columns.str.strip()
    
    required_cols = ['구분1', '구분2', '구분3', '연도', '월', '값']
    for col in required_cols:
        if col not in df.columns:
            if col == '구분3':
                df['구분3'] = '' # 구분3이 없는 DB 구조일 경우 빈 문자열로 안전하게 처리
            else:
                return [('item', f'오류: [{col}] 없음', [0.0] * 4)], ["오류"] * 4

    # 데이터 클렌징
    df['구분1'] = df['구분1'].astype(str).str.strip()
    df['구분2'] = df['구분2'].astype(str).str.strip()
    df['구분3'] = df['구분3'].fillna('').astype(str).str.strip()
    
    df['연도'] = df['연도'].astype(str).str.replace('년', '', regex=False).str.replace(' ', '', regex=False)
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    df['월'] = df['월'].astype(str).str.replace('월', '', regex=False).str.replace(' ', '', regex=False)
    df['월'] = pd.to_numeric(df['월'], errors='coerce').fillna(0).astype(int)
    
    # 값 파싱 및 백만원 단위 환산
    df = df.copy()
    df['값'] = df['값'].apply(_parse) / 1_000_000.0
    df['값'] = df['값'].round(0).astype(int)
    #df['값'] = df['값'].apply(_parse)

    vm = df.groupby(['구분1', '구분2', '구분3', '연도', '월'])['값'].sum().to_dict()
    
    # 최근 3개월 (이미지 요청사항에 따라 역순 배열: 당월 -> 전월 -> 전전월)
    recent = []
    curr_y, curr_m = year, month
    for _ in range(3):
        recent.append((curr_y, curr_m))
        curr_y, curr_m = _prev(curr_y, curr_m)
        
    col_hdrs = [f"'{str(y)[2:]}년 {m}월 실적" for y, m in recent] + ['증감']
    
    rows = []
    grand_totals = [0.0] * 3
    
    # 구분1(상위구분) 목록 추출 (순서 유지를 위해 unique 사용)
    g1_list = df[df['구분1'] != '']['구분1'].unique()
    
    for g1 in g1_list:
        g1_totals = [0.0] * 3
        g2_list = df[df['구분1'] == g1]['구분2'].unique()
        
        for g2 in g2_list:
            g2_totals = [0.0] * 3
            g3_list = df[(df['구분1'] == g1) & (df['구분2'] == g2)]['구분3'].unique()
            
            # 하위 항목(고철매각 등)이 존재하는지 여부 확인
            has_sub = len([g for g in g3_list if g != '']) > 0
            sub_rows = []
            
            for g3 in g3_list:
                vals = [vm.get((g1, g2, g3, y, m), 0.0) for y, m in recent]
                
                # 하드코딩 없이 하위->중위->상위 순으로 누적 합산(Roll-up)
                for i, v in enumerate(vals):
                    g2_totals[i] += v
                    g1_totals[i] += v
                    grand_totals[i] += v
                    
                if has_sub:
                    label = '기타' if g3 == '' else g3
                    # 이미지의 증감 계산 로직 반영: 당월(0번 인덱스) - 전전월(2번 인덱스)
                    diff = vals[0] - vals[2] if len(vals) == 3 else 0.0
                    sub_rows.append(('sub', label, vals + [diff]))
                    
            # 중위구분 행 추가
            diff_g2 = g2_totals[0] - g2_totals[2] if len(g2_totals) == 3 else 0.0
            rows.append(('item', g2, g2_totals + [diff_g2]))
            
            # 하위구분이 있으면 중위구분 아래에 펼쳐서 추가
            if has_sub:
                rows.extend(sub_rows)
                
        # 상위구분 합계 행 추가 (예: 기타비용 합계)
        diff_g1 = g1_totals[0] - g1_totals[2] if len(g1_totals) == 3 else 0.0
        rows.append(('total', f'{g1} 합계', g1_totals + [diff_g1]))
        
    # 총 합계 행 추가
    diff_grand = grand_totals[0] - grand_totals[2] if len(grand_totals) == 3 else 0.0
    rows.append(('total', '총 합계', grand_totals + [diff_grand]))
    
    return rows, col_hdrs


def _build_영업외비용_table_html(rows, col_hdrs):
    th = f'<th style="{_TH}">구분</th>' + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_hdrs)
    body = ''
    
    for kind, label, vals in rows:
        if kind == 'total':
            lbl_s, num_s = ROW_HDR_LBL, ROW_HDR_NUM
        elif kind == 'item':
            lbl_s, num_s = ROW_ITEM, _TD_NUM
        else: # sub (고철매각작업비 등 들여쓰기)
            lbl_s, num_s = f'{ROW_ITEM}; color: #4b5563;', _TD_NUM
            label = f'&nbsp;&nbsp;&nbsp;&nbsp; {label}'
            
        cells = f'<td style="{lbl_s}">{label}</td>'
        for i, v in enumerate(vals):
            is_diff = (i == len(vals) - 1)
            
            # 음수 붉은색 처리
            s = ROW_HDR_RED if (kind == 'total' and v < 0) else \
                _TD_RED if (v < 0) else num_s
                
            formatted_v = f"{v:,.0f}"  
            if formatted_v == "-0": formatted_v = "0"
            
            cells += f'<td style="{s}">{formatted_v}</td>'
        body += f'<tr>{cells}</tr>'
        
    return _html_table(f'<tr>{th}</tr>', body)

# ── render_page ───────────────────────────────────────────────────────────

def render_page(app, year_state, month_state):

    def _render_title():
        app.markdown(
            f'<h1 style="color:#404448">{int(year_state.value)}년 {int(month_state.value)}월 비용분석</h1>',
            unsafe_allow_html=True,
        )
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["사용량 원단위 추이", "클레임 현황", "영업외 비용 내역"])

    with tabs[0]:
        def _render_사용량():
            year, month = int(year_state.value), int(month_state.value)
            unit_text = '※ 사용량원단위 : 부재료사용량/공정처리량'
            
            # 1~3번 항목 (사업장별 부재료 사용량)
            locations = [
                ('1) 부재료 사용량 원단위 (포항)', '포항'),
                ('2) 부재료 사용량 원단위 (충주)', '충주'),
                ('3) 부재료 사용량 원단위 (충주2)', '충주2')
            ]

            for title, loc in locations:
                rows, hdrs = _build_부재료_data(loc, year, month)
                
                app.markdown(
                    _layout100(title,
                              _build_부재료_table_html(loc, rows, hdrs),
                              "",
                              unit=unit_text),
                    unsafe_allow_html=True,
                )
                
                fig = _build_부재료_chart(loc, rows, hdrs)
                app.plotly_chart(fig, use_container_width=True)
                

                app.markdown('<div style="margin-top:48px;"></div>', unsafe_allow_html=True)

            rows_단가, hdrs_단가 = _build_단가추이_data(year, month)
            
            app.markdown(
                _layout100('4) 단가 추이',
                          _build_단가추이_table_html(rows_단가, hdrs_단가),
                          ""),
                unsafe_allow_html=True,
            )
            
            fig_단가 = _build_단가추이_chart(rows_단가, hdrs_단가)
            app.plotly_chart(fig_단가, use_container_width=True)

        app.If(lambda: True, _render_사용량)

    with tabs[1]:
        def _render_클레임():
            year, month = int(year_state.value), int(month_state.value)
            unit_text = '(단위 : 백만원)'

            # 1. 월 평균 클레임 지급액
            rows_월평균, hdrs_월평균 = _build_월평균클레임_data(year, month)
            app.markdown(
                _layout64('1) 월 평균 클레임 지급액',
                          _build_월평균클레임_table_html(rows_월평균, hdrs_월평균),
                          "",
                          unit=unit_text),
                unsafe_allow_html=True,
            )

            # 항목 간 여백
            app.markdown('<div style="margin-top:48px;"></div>', unsafe_allow_html=True)

            # 2. 당월 클레임 내역
            rows_당월, hdrs_당월 = _build_당월클레임_data(year, month)
            app.markdown(
                _layout64('2) 당월 클레임 내역',
                          _build_당월클레임_table_html(rows_당월, hdrs_당월),
                          "",
                          unit=unit_text),
                unsafe_allow_html=True,
            )
            
        app.If(lambda: True, _render_클레임)

    with tabs[2]:
        def _render_영업외비용():
            year, month = int(year_state.value), int(month_state.value)
            
            # 1. 데이터 및 메모 가져오기
            rows, hdrs = _build_영업외비용_data(year, month)
            memo = _get_memo(Sheets.영업외비용_메모, year, month)
            
            # 2. _layout64 컴포넌트에 표와 메모 함께 렌더링
            app.markdown(
                _layout64('1) 영업외 비용 (최근 3개월)',
                          _build_영업외비용_table_html(rows, hdrs),
                          memo,
                          unit='(단위 : 백만원)'),
                unsafe_allow_html=True,
            )
            
        app.If(lambda: True, _render_영업외비용)