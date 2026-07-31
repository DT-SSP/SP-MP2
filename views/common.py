"""모든 views에서 공유하는 유틸·CSS·HTML 헬퍼 (세아 브랜드 컬러 적용)."""
import pandas as pd

# ── 데이터 유틸 (기존 로직 동일) ───────────────────────────────────────────

def parse(s):
    if pd.isna(s):  # None, NaN, pd.NA → 0
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().replace(',', '').replace(' ', '')
    if not s or s == '-':
        return 0.0
    if s.startswith('(') and s.endswith(')'):
        return -float(s[1:-1])
    try:
        return float(s)
    except Exception:
        return 0.0


def fmt(v, is_pct=False, decimal=0):
    if is_pct:
        if decimal:
            v = round(v, decimal)
            return f"-{abs(v):.{decimal}f}" if v < 0 else f"{v:.{decimal}f}"
        v = round(v)
        return f"-{abs(v)}" if v < 0 else str(v)
    if decimal:
        v = round(v, decimal)
        return f"-{abs(v):,.{decimal}f}" if v < 0 else f"{v:,.{decimal}f}"
    v = round(v)
    return f"-{abs(v):,}" if v < 0 else f"{v:,}"


def pct(a, b):
    return a / b * 100 if b else 0.0


def prev_month(year, month, n=1):
    m, y = month - n, year
    while m < 1:
        m += 12
        y -= 1
    return y, m


def drop_empty(df, *cols):
    """Google Sheets 빈 행 제거 후 int 변환."""
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=list(cols)).copy()
    for c in cols:
        df[c] = df[c].astype(int)
    return df


def sort_by_order(items, order):
    """order 기준으로 정렬, 미지정 항목은 뒤에 추가."""
    order_set = set(order)
    result    = [x for x in order if x in set(items)]
    result   += [x for x in items if x not in order_set]
    return result


def recent_months(year, month, n=5):
    result = []
    y, m = year, month
    for _ in range(n):
        result.insert(0, (y, m))
        y, m = prev_month(y, m, 1)
    return result


def build_col_hdrs(연도_in_db, recent, annual_suffix='년'):
    hdrs = []
    for yr in 연도_in_db:
        hdrs.append(f"'{str(yr)[2:]}{annual_suffix}")
    last_yr = None
    for yr_c, mo_c in recent:
        hdrs.append(f"'{str(yr_c)[2:]}.{mo_c}월" if yr_c != last_yr else f"{mo_c}월")
        last_yr = yr_c
    return hdrs


def get_memo(load_sheet_fn, sheet_info, year, month):
    df = load_sheet_fn(sheet_info)
    df['연도'] = df['연도'].astype(str).str.strip()
    df['월']   = df['월'].astype(str).str.strip()
    row = df[(df['연도'] == str(year)) & (df['월'] == str(month))]
    return str(row.iloc[0]['메모']) if not row.empty else ''

def layout_title_only(title, unit=''):
    """_layout100과 완전히 동일한 소제목(타이틀) 디자인을 렌더링합니다."""
    return (
        '<div style="margin:0 0 8px 0; width:100%; box-sizing:border-box">'
        '<div style="display:flex; justify-content:space-between; align-items:baseline; '
        'border-bottom:1px solid #dee2e6; padding-bottom:4px; width:100%">'
        f'<h3 style="margin:0; font-size:1.1em; font-weight:700; color:{C_NAVY}">{title}</h3>'
        f'<span style="font-size:0.8em; color:gray">{unit}</span>'
        '</div></div>'
    )

# ── CSS 상수 (세아 컬러 시스템 및 QD 폰트 크기 기준 적용) ─────────────────────────────────

# SeAH 공식 컬러 정의
C_NAVY = '#53565A'    # 메인 네이비
C_ORANGE = '#EA5421'  # 포인트 오렌지
C_RED = '#DC2626'     # 경고/하락 레드
C_LT_GRAY = '#F1F3F5' # 보조 배경 (아주 연한 회색)
C_LT_ORANGE = '#FDEEE9' # 강조용 연한 오렌지

# 차트 전용 색상
C_CHART_SEC  = '#8A8D91'  # 보조 시리즈 (중간 회색)
C_CHART_GRID = '#E8EAED'  # 그리드 선 (중립 회색)

# [QD 기준 적용] 공통 폰트 및 패딩 스타일
_QD_STYLE = 'font-size:15px;padding:8px 16px;'

# 테이블 헤더: 네이비 배경 + 흰색 텍스트
TH = f'background:{C_NAVY};color:white;{_QD_STYLE}text-align:center !important;vertical-align:middle;white-space:nowrap;font-weight:500'

# 일반 데이터 행
TD_LBL = f'{_QD_STYLE}text-align:left;border-bottom:1px solid #e2e8f0'
TD_NUM = f'{_QD_STYLE}text-align:right;border-bottom:1px solid #e2e8f0'
TD_RED = f'{TD_NUM};color:{C_RED}'

# 소계/합계 행 (연한 회색 배경 + 굵은 글씨)
TD_SUB_LBL = f'{_QD_STYLE}text-align:left;background:{C_LT_GRAY};font-weight:600;border-bottom:1px solid #dee2e6'
TD_SUB_NUM = f'{_QD_STYLE}text-align:right;background:{C_LT_GRAY};font-weight:600;border-bottom:1px solid #dee2e6'
TD_SUB_RED = f'{TD_SUB_NUM};color:{C_RED}'

# ── 행 스타일 (테이블 본문 공통) ──────────────────────────────────────────

# 섹션 구분행
ROW_SEC = (f'{_QD_STYLE}font-weight:700;background:#CFD4DA;color:#404448;'
           f'border-bottom:2px solid #A8B0BA')

# 소그룹 헤더
ROW_GRP = (f'font-size:15px;padding:8px 16px 8px 28px;font-weight:700;background:{C_LT_GRAY};'
           f'border-bottom:1px solid #dee2e6')

# 소계/그룹합계 행
ROW_HDR_LBL = f'{_QD_STYLE}text-align:left;background:{C_LT_GRAY};font-weight:700;border-bottom:1px solid #dee2e6'
ROW_HDR_NUM = f'{_QD_STYLE}text-align:right;background:{C_LT_GRAY};font-weight:700;border-bottom:1px solid #dee2e6'
ROW_HDR_RED = f'{ROW_HDR_NUM};color:{C_RED}'

# 최하단 집계행(Total)
ROW_CAL_LBL = (f'{_QD_STYLE}text-align:left;background:{C_NAVY};color:white;font-weight:700;'
               f'border-bottom:1px solid {C_NAVY}')
ROW_CAL_NUM = (f'{_QD_STYLE}text-align:right;background:{C_NAVY};color:white;font-weight:700;'
               f'border-bottom:1px solid {C_NAVY}')
ROW_CAL_RED = f'{ROW_CAL_NUM};color:#FFB8B8'

# 일반 항목행
ROW_ITEM = 'font-size:15px;padding:8px 16px 8px 28px;text-align:left;border-bottom:1px solid #e2e8f0'

# ── CSS 상수 (틀 고정 추가 헬퍼) ─────────────────────────────────

# 1. 상단 헤더 고정 (위아래 스크롤 시 고정, z-index: 2)
TH_STICKY = f'position: sticky; top: 0; z-index: 2; {TH}'

# 2. 좌상단 모서리 고정 (위아래/좌우 스크롤 시 모두 고정, 최상단 덮기 위해 z-index: 3)
TH_CORNER_STICKY = f'position: sticky; top: 0; left: 0; z-index: 3; {TH}'

# 3. 좌측 일반 데이터 행 고정 (좌우 스크롤 시 고정, 배경색 흰색, z-index: 1)
TD_LBL_STICKY = f'position: sticky; left: 0; z-index: 1; background: #ffffff; {TD_LBL}'

# 4. 좌측 소계/합계 행 고정 (배경색을 C_LT_GRAY로 유지)
ROW_HDR_LBL_STICKY = f'position: sticky; left: 0; z-index: 1; background: {C_LT_GRAY}; {ROW_HDR_LBL}'
TD_SUB_LBL_STICKY = f'position: sticky; left: 0; z-index: 1; background: {C_LT_GRAY}; {TD_SUB_LBL}'

# ── HTML 헬퍼 ────────────────────────────────────────────────────────────
'''
def html_table(th_html, body_html):
    return (
        '<div style="overflow-x:auto">'
        '<table style="border-collapse:collapse;width:100%;font-family:sans-serif">'
        f'<thead style="border-top:2px solid {C_NAVY}">{th_html}</thead>'
        f'<tbody>{body_html}</tbody>'
        '</table></div>'
    )

'''

'''
def html_table(th_html, body_html):
    return (
        #max-height로 표의 최대 높이를 제한하고, overflow: auto로 상하/좌우 스크롤을 켬
        '<div style="max-height: 500px; overflow: auto;">'
        '<table style="border-collapse:collapse;width:100%;font-family:sans-serif">'
        f'<thead style="border-top:2px solid {C_NAVY}">{th_html}</thead>'
        f'<tbody>{body_html}</tbody>'
        '</table></div>'
    )

'''
def html_table(th_html, body_html):
    return (
        # 1. 표 전체를 감싸는 박스의 높이를 제한하고 스크롤이 생기도록 설정
        '<div style="max-height: 800px; overflow-y: auto; overflow-x: auto;">'
        '<table style="border-collapse: collapse; width: 100%; font-family: sans-serif;">'
        
        # 2. 헤더(thead)에 position: sticky; top: 0; 을 주어 스크롤을 내려도 천장에 붙어있게 설정
        # 3. z-index: 10을 주어 데이터가 헤더 밑으로 숨어서 지나가게 설정
        f'<thead style="position: sticky; top: 0; z-index: 10; background: {C_NAVY}; border-top: 2px solid {C_NAVY};">'
        f'{th_html}'
        '</thead>'
        
        # 4. 실제 데이터 영역 (이 부분만 스크롤됨)
        f'<tbody>{body_html}</tbody>'
        
        '</table>'
        '</div>'
    )

def memo_html(memo):
    return (f'<p style="margin:0;font-size:0.9em;line-height:1.6;white-space:pre-wrap">{memo}</p>'
            if memo else '')

def layout64(title, content_html, memo, unit='[단위: 만개, 백만원]'):
    return (
        '<div style="margin:0">'
        '<div style="display:flex;gap:16px;margin:0 0 8px 0;border-bottom:1px solid #dee2e6;padding-bottom:4px">'
        f'<div style="flex:6;min-width:0;display:flex;justify-content:space-between;align-items:baseline">'
        f'<h3 style="margin:0;font-size:1.1em;font-weight:700;color:{C_NAVY}">{title}</h3>'
        f'<span style="font-size:0.8em;color:gray">{unit}</span>'
        '</div>'
        '<div style="flex:4;min-width:0">'
        '</div>'
        '</div>'
        '<div style="display:flex;gap:16px;align-items:flex-start">'
        # 💡 수정된 부분: flex:6 래퍼에 width:100%; max-width:100%; overflow:hidden; 속성 추가
        f'<div style="flex:6; min-width:0; width:100%; max-width:100%; overflow:hidden;">{content_html}</div>'
        f'<div style="flex:4;min-width:0">{memo_html(memo)}</div>'
        '</div>'
        '</div>'
    )

def layout100(title, content_html, memo='', unit=''):
    """layout64와 동일한 Flexbox 메커니즘을 적용하여 리사이징 시 비율이 유지되는 100% 레이아웃."""
    
    title_section = (
        '<div style="display:flex; justify-content:space-between; align-items:baseline; '
        'margin:0 0 8px 0; border-bottom:1px solid #dee2e6; padding-bottom:4px; width:100%">'
        f'<h3 style="margin:0; font-size:1.1em; font-weight:700; color:{C_NAVY}">{title}</h3>'
        f'<span style="font-size:0.8em; color:gray">{unit}</span>'
        '</div>'
    )
    
    memo_content = memo_html(memo)
    memo_section = f'<div style="flex:1; min-width:0; width:100%; margin-top:10px">{memo_content}</div>' if memo_content else ''

    return (
        '<div style="margin:0 0 20px 0; width:100%; box-sizing:border-box">'
        f'{title_section}'
        # layout64와 완전히 동일하게 flex 및 min-width:0 조합 적용
        '<div style="display:flex; flex-direction:column; width:100%; min-width:0">'
            f'<div style="flex:1; min-width:0; width:100%; max-width:100%; overflow:hidden">{content_html}</div>'
            f'{memo_section}'
        '</div>'
        '</div>'
    )