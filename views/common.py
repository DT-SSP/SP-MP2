"""모든 views에서 공유하는 유틸·CSS·HTML 헬퍼."""
import pandas as pd


# ── 데이터 유틸 ───────────────────────────────────────────────────────────

def parse(s):
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


# ── CSS 상수 ─────────────────────────────────────────────────────────────

TH     = 'background:#6b46c1;color:white;padding:6px 10px;text-align:center;white-space:nowrap;font-weight:500'
TD_LBL = 'padding:5px 10px;text-align:left;border-bottom:1px solid #e2e8f0'
TD_NUM = 'padding:5px 10px;text-align:right;border-bottom:1px solid #e2e8f0'
TD_RED = TD_NUM + ';color:#e53e3e'

# 소계/합계 행 (굵게 + 연보라 배경)
TD_SUB_LBL = 'padding:5px 10px;text-align:left;background:#f0edf8;font-weight:600;border-bottom:1px solid #e2e8f0'
TD_SUB_NUM = 'padding:5px 10px;text-align:right;background:#f0edf8;font-weight:600;border-bottom:1px solid #e2e8f0'
TD_SUB_RED = TD_SUB_NUM + ';color:#e53e3e'

# ── 행 스타일 (테이블 본문 공통) ──────────────────────────────────────────
# 섹션 구분행: 연보라 배경 + 짙은 보라 텍스트
ROW_SEC     = ('padding:5px 10px;font-weight:700;background:#ede9fe;color:#4c1d95;'
               'border-bottom:1px solid #c4b5fd')
# 소그룹 헤더: 연보라 배경, 들여쓰기 (colspan 전체)
ROW_GRP     = ('padding:5px 10px 5px 22px;font-weight:700;background:#f0edf8;'
               'border-bottom:1px solid #d6ccee')
# 소계/그룹합계 행: 연보라 배경 + 굵은 텍스트
ROW_HDR_LBL = ('padding:5px 10px;text-align:left;background:#f0edf8;font-weight:700;'
               'border-bottom:1px solid #d6ccee')
ROW_HDR_NUM = ('padding:5px 10px;text-align:right;background:#f0edf8;font-weight:700;'
               'border-bottom:1px solid #d6ccee')
ROW_HDR_RED = ROW_HDR_NUM + ';color:#e53e3e'
# 집계행: 진한 보라 배경 + 흰 텍스트
ROW_CAL_LBL = ('padding:5px 10px;text-align:left;background:#6b46c1;color:white;font-weight:700;'
               'border-bottom:1px solid #553a9a')
ROW_CAL_NUM = ('padding:5px 10px;text-align:right;background:#6b46c1;color:white;font-weight:700;'
               'border-bottom:1px solid #553a9a')
ROW_CAL_RED = ROW_CAL_NUM + ';color:#fca5a5'
# 일반 항목행: 들여쓰기 22px
ROW_ITEM    = 'padding:5px 10px 5px 22px;text-align:left;border-bottom:1px solid #e2e8f0'


# ── HTML 헬퍼 ────────────────────────────────────────────────────────────

def html_table(th_html, body_html):
    return (
        '<div style="overflow-x:auto">'
        '<table style="border-collapse:collapse;width:100%">'
        f'<thead>{th_html}</thead>'
        f'<tbody>{body_html}</tbody>'
        '</table></div>'
    )


def memo_html(memo):
    return (f'<p style="margin:0;font-size:0.9em;line-height:1.6;white-space:pre-wrap">{memo}</p>'
            if memo else '')


def layout64(title, content_html, memo, unit='[단위: 만개, 백만원]'):
    """6:4 flex 레이아웃 공통 래퍼."""
    return (
        '<div style="margin:0">'
        '<div style="display:flex;gap:16px;margin:0 0 4px 0">'
        f'<div style="flex:6;min-width:0;display:flex;justify-content:space-between;align-items:baseline">'
        f'<h3 style="margin:0;font-size:1.1em;font-weight:600">{title}</h3>'
        f'<span style="font-size:0.8em;color:gray">{unit}</span>'
        '</div>'
        '<div style="flex:4;min-width:0"></div>'
        '</div>'
        '<div style="display:flex;gap:16px;align-items:flex-start">'
        f'<div style="flex:6;min-width:0">{content_html}</div>'
        f'<div style="flex:4;min-width:0">{memo_html(memo)}</div>'
        '</div>'
        '</div>'
    )
