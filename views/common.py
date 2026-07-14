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



# ── CSS 상수 (세아 컬러 시스템 적용) ─────────────────────────────────

# SeAH 공식 컬러 정의
C_NAVY = '#53565A'    # 메인 네이비
C_ORANGE = '#EA5421'  # 포인트 오렌지
C_RED = '#DC2626'     # 경고/하락 레드
C_LT_GRAY = '#F1F3F5' # 보조 배경 (아주 연한 회색)
C_LT_ORANGE = '#FDEEE9' # 강조용 연한 오렌지

# 차트 전용 색상
C_CHART_SEC  = '#8A8D91'  # 보조 시리즈 (중간 회색)
C_CHART_GRID = '#E8EAED'  # 그리드 선 (중립 회색)

# 테이블 헤더: 네이비 배경 + 흰색 텍스트
TH = f'background:{C_NAVY};color:white;padding:6px 10px;text-align:center !important;vertical-align:middle;white-space:nowrap;font-weight:500'

# 일반 데이터 행
TD_LBL = 'padding:5px 10px;text-align:left;border-bottom:1px solid #e2e8f0'
TD_NUM = 'padding:5px 10px;text-align:right;border-bottom:1px solid #e2e8f0'
TD_RED = f'{TD_NUM};color:{C_RED}'

# 소계/합계 행 (연한 회색 배경 + 굵은 글씨)
TD_SUB_LBL = f'padding:5px 10px;text-align:left;background:{C_LT_GRAY};font-weight:600;border-bottom:1px solid #dee2e6'
TD_SUB_NUM = f'padding:5px 10px;text-align:right;background:{C_LT_GRAY};font-weight:600;border-bottom:1px solid #dee2e6'
TD_SUB_RED = f'{TD_SUB_NUM};color:{C_RED}'

# ── 행 스타일 (테이블 본문 공통) ──────────────────────────────────────────

# 섹션 구분행: 중간 회색 배경 + 진한 회색 텍스트
ROW_SEC = (f'padding:5px 10px;font-weight:700;background:#CFD4DA;color:#404448;'
           f'border-bottom:2px solid #A8B0BA')

# 소그룹 헤더: 연한 회색 배경, 들여쓰기
ROW_GRP = (f'padding:5px 10px 5px 22px;font-weight:700;background:{C_LT_GRAY};'
           f'border-bottom:1px solid #dee2e6')

# 소계/그룹합계 행
ROW_HDR_LBL = f'padding:5px 10px;text-align:left;background:{C_LT_GRAY};font-weight:700;border-bottom:1px solid #dee2e6'
ROW_HDR_NUM = f'padding:5px 10px;text-align:right;background:{C_LT_GRAY};font-weight:700;border-bottom:1px solid #dee2e6'
ROW_HDR_RED = f'{ROW_HDR_NUM};color:{C_RED}'

# 최하단 집계행(Total): 진한 네이비 배경 + 흰색 텍스트
ROW_CAL_LBL = (f'padding:5px 10px;text-align:left;background:{C_NAVY};color:white;font-weight:700;'
               f'border-bottom:1px solid {C_NAVY}')
ROW_CAL_NUM = (f'padding:5px 10px;text-align:right;background:{C_NAVY};color:white;font-weight:700;'
               f'border-bottom:1px solid {C_NAVY}')
ROW_CAL_RED = f'{ROW_CAL_NUM};color:#FFB8B8' # 네이비 배경 위에서 잘 보이는 연한 핑크/레드

# 일반 항목행
ROW_ITEM = 'padding:5px 10px 5px 22px;text-align:left;border-bottom:1px solid #e2e8f0'


# ── HTML 헬퍼 ────────────────────────────────────────────────────────────

def html_table(th_html, body_html):
    return (
        '<div style="overflow-x:auto">'
        '<table style="border-collapse:collapse;width:100%;font-family:sans-serif">'
        f'<thead style="border-top:2px solid {C_NAVY}">{th_html}</thead>'
        f'<tbody>{body_html}</tbody>'
        '</table></div>'
    )

def memo_html(memo):
    return (f'<p style="margin:0;font-size:0.9em;line-height:1.6;white-space:pre-wrap">{memo}</p>'
            if memo else '')

def layout64(title, content_html, memo, unit='[단위: 만개, 백만원]'):
    """6:4 flex 레이아웃 (세아 스타일 적용)."""
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
        f'<div style="flex:6;min-width:0">{content_html}</div>'
        f'<div style="flex:4;min-width:0">{memo_html(memo)}</div>'
        '</div>'
        '</div>'
    )

def layout100(title, content_html, memo='', unit=''):
    title_html = f'<div style="font-size:16px;font-weight:700;color:{C_NAVY};margin-bottom:8px;">{title}</div>'
    unit_html = f'<div style="text-align:right; font-size:13px; color:#666; margin-bottom:4px;">{unit}</div>' if unit else ''
    
    memo_html = ''
    if memo:
        memo_html = f'''
        <div class="t3-special-memo" style="margin-top:10px; padding:10px; background:#f8f9fa; border-radius:4px; font-size:13px; color:#444;">
            {memo}
        </div>
        '''

    return f'<div style="width:100%; margin-bottom:20px;">{title_html}{unit_html}{content_html}{memo_html}</div>'