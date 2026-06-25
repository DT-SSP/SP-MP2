import datetime
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
    html_table as _html_table, layout64 as _layout64,
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


# ── 1) 운반 실적 및 컨테이너당 단가 추이 ─────────────────────────────────

def _build_운반비(year, month):
    df = load_sheet(Sheets.운반실적및컨테이너단가_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')

    # 신규 컬럼 구조: 구분1, 조건, 업체, 연도, 월, 실적
    val_col = '실적' if '실적' in df.columns else '값'
    df[val_col]  = df[val_col].apply(_parse)
    df['조건']   = df['조건'].fillna('').astype(str).str.strip()
    df['업체']   = df['업체'].fillna('').astype(str).str.strip()

    vm = df.set_index(['구분1', '조건', '업체', '연도', '월'])[val_col].to_dict()

    qty_key       = next(k for k in df['구분1'].unique() if '수량' in k)
    expense_items = list(dict.fromkeys(k for k in df['구분1'] if k != qty_key))

    연도_in_db = sorted(df['연도'].unique().tolist())
    prev_yr, prev_mo = _prev(year, month)

    def raw(g1, cond, company, yr, mo):
        return vm.get((g1, cond, company, yr, mo), 0.0)

    def get_conds(yr, mo):
        mask = (df['연도'] == yr) & (df['월'] == mo) & (df['조건'] != '')
        return sorted(df[mask]['조건'].unique().tolist())

    def get_업체s(cond, yr, mo):
        mask = (df['연도'] == yr) & (df['월'] == mo) & (df['조건'] == cond) & (df['업체'] != '')
        return sorted(df[mask]['업체'].unique().tolist())

    def get_month_pairs(yr, mo):
        """업체 있으면 (cond, 업체), 없으면 (cond, '') 형태로 컬럼 pair 목록 반환"""
        pairs = []
        for cond in get_conds(yr, mo):
            businesses = get_업체s(cond, yr, mo)
            if businesses:
                for b in businesses:
                    pairs.append((cond, b))
            else:
                pairs.append((cond, ''))
        return pairs

    def total_agg(g1, yr, mo):
        return raw(g1, '', '', yr, mo)

    prev_pairs = get_month_pairs(prev_yr, prev_mo)
    curr_pairs = get_month_pairs(year, month)

    def yr_avg_total(g1, yr):
        vals = [raw(g1, '', '', yr, m) for m in range(1, 13) if (g1, '', '', yr, m) in vm]
        return sum(vals) / len(vals) if vals else 0.0

    def container_cost_total(yr, mo):
        return sum(total_agg(it, yr, mo) for it in expense_items)

    def pair_cost(cond, company, yr, mo):
        return sum(raw(it, cond, company, yr, mo) for it in expense_items)

    def yr_avg_cost(yr):
        vals = [container_cost_total(yr, m) for m in range(1, 13) if (qty_key, '', '', yr, m) in vm]
        return sum(vals) / len(vals) if vals else 0.0

    def make_row(g1):
        v  = [yr_avg_total(g1, yr) for yr in 연도_in_db]
        v += [raw(g1, c, b, prev_yr, prev_mo) for c, b in prev_pairs]
        v.append(total_agg(g1, prev_yr, prev_mo))
        v += [raw(g1, c, b, year, month) for c, b in curr_pairs]
        v.append(total_agg(g1, year, month))
        v.append(total_agg(g1, year, month) - total_agg(g1, prev_yr, prev_mo))
        return v

    def make_cost_row():
        v  = [yr_avg_cost(yr) for yr in 연도_in_db]
        v += [pair_cost(c, b, prev_yr, prev_mo) for c, b in prev_pairs]
        v.append(container_cost_total(prev_yr, prev_mo))
        v += [pair_cost(c, b, year, month) for c, b in curr_pairs]
        v.append(container_cost_total(year, month))
        v.append(container_cost_total(year, month) - container_cost_total(prev_yr, prev_mo))
        return v

    def make_total_row():
        def tot(yr, mo):
            return container_cost_total(yr, mo) * total_agg(qty_key, yr, mo)
        def pair_tot(c, b, yr, mo):
            return pair_cost(c, b, yr, mo) * raw(qty_key, c, b, yr, mo)
        v  = [yr_avg_total(qty_key, yr) * yr_avg_cost(yr) for yr in 연도_in_db]
        v += [pair_tot(c, b, prev_yr, prev_mo) for c, b in prev_pairs]
        v.append(tot(prev_yr, prev_mo))
        v += [pair_tot(c, b, year, month) for c, b in curr_pairs]
        v.append(tot(year, month))
        v.append(tot(year, month) - tot(prev_yr, prev_mo))
        return v

    rows = [
        ('qty',      qty_key,            make_row(qty_key)),
        ('subtotal', '컨테이너당 운반비', make_cost_row()),
        *[('item',   g1,                 make_row(g1)) for g1 in expense_items],
        ('total',    '총 비용',           make_total_row()),
    ]

    col_spec = {
        'annual_yrs': 연도_in_db,
        'prev': (prev_yr, prev_mo, prev_pairs),
        'curr': (year, month, curr_pairs),
    }
    return rows, col_spec


def _운반비_to_html(rows, col_spec):
    annual_yrs = col_spec['annual_yrs']
    prev_yr, prev_mo, prev_pairs = col_spec['prev']
    curr_yr, curr_mo, curr_pairs = col_spec['curr']

    n_prev = len(prev_pairs) + 1   # pairs + '-'
    n_curr = len(curr_pairs) + 1

    def mo_label(yr, mo):
        return f"'{str(yr)[2:]}.{mo}월" if yr != curr_yr else f"{mo}월"

    def pair_label(cond, company):
        return f"{cond}/{company}" if company else cond

    th1 = f'<th style="{_TH}" rowspan="2">구분</th>'
    for yr in annual_yrs:
        th1 += f'<th style="{_TH}" rowspan="2">\'{str(yr)[2:]}.평균</th>'
    th1 += f'<th style="{_TH}" colspan="{n_prev}">{mo_label(prev_yr, prev_mo)}</th>'
    th1 += f'<th style="{_TH}" colspan="{n_curr}">{curr_mo}월</th>'
    th1 += f'<th style="{_TH}" rowspan="2">전월대비</th>'

    th2 = ''
    for c, b in prev_pairs:
        th2 += f'<th style="{_TH}">{pair_label(c, b)}</th>'
    th2 += f'<th style="{_TH}">-</th>'
    for c, b in curr_pairs:
        th2 += f'<th style="{_TH}">{pair_label(c, b)}</th>'
    th2 += f'<th style="{_TH}">-</th>'

    thead = f'<tr>{th1}</tr><tr>{th2}</tr>'

    body = ''
    for kind, label, vals in rows:
        if kind == 'total':
            lbl_s, num_s, red_s = ROW_CAL_LBL, ROW_CAL_NUM, ROW_CAL_RED
        elif kind == 'subtotal':
            lbl_s, num_s, red_s = ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED
        elif kind == 'item':
            lbl_s, num_s, red_s = ROW_ITEM, _TD_NUM, _TD_RED
        else:  # qty
            lbl_s, num_s, red_s = _TD_LBL, _TD_NUM, _TD_RED

        cells = f'<td style="{lbl_s}">{label}</td>'
        last  = len(vals) - 1
        for i, v in enumerate(vals):
            s = (red_s if v < 0 else num_s) if i == last else num_s
            cells += f'<td style="{s}">{_fmt(v)}</td>'
        body += f'<tr>{cells}</tr>'

    return _html_table(thead, body)


# ── 2) 외주용역비 ─────────────────────────────────────────────────────────

def _build_외주용역비(year, month):
    df = load_sheet(Sheets.외주용역비_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    vm = df.set_index(['구분1', '구분2', '연도', '월'])['값'].to_dict()

    연도_in_db = sorted(df['연도'].unique().tolist())
    recent    = _recent_months(year, month)
    col_hdrs  = _build_col_hdrs(연도_in_db, recent, annual_suffix='년 평균')
    prev_yr, prev_mo = _prev(year, month)

    groups_order = list(dict.fromkeys(df['구분1'].tolist()))

    def raw(g1, g2, yr, mo):
        return vm.get((g1, g2, yr, mo), 0.0)

    def yr_avg(g1, g2, yr):
        vals = [raw(g1, g2, yr, m) for m in range(1, 13) if (g1, g2, yr, m) in vm]
        return sum(vals) / len(vals) if vals else 0.0

    def make_item_vals(g1, g2):
        v = [yr_avg(g1, g2, yr) for yr in 연도_in_db]
        v += [raw(g1, g2, yr_c, mo_c) for yr_c, mo_c in recent]
        v.append(raw(g1, g2, year, month) - raw(g1, g2, prev_yr, prev_mo))
        return v

    def make_rate_vals(g1, qty_key, cost_key, scale):
        def rate(yr, mo):
            q = raw(g1, qty_key, yr, mo)
            return raw(g1, cost_key, yr, mo) * scale / q if q else 0.0

        v = []
        for yr in 연도_in_db:
            q_avg = yr_avg(g1, qty_key, yr)
            c_avg = yr_avg(g1, cost_key, yr)
            v.append(c_avg * scale / q_avg if q_avg else 0.0)
        v += [rate(yr_c, mo_c) for yr_c, mo_c in recent]
        v.append(rate(year, month) - rate(prev_yr, prev_mo))
        return v

    def get_keys(g1):
        types = df[df['구분1'] == g1]['구분2'].unique().tolist()
        qty_key  = next((k for k in types if any(kw in k for kw in _외주_QTY_KW)), None)
        cost_key = next((k for k in types if k != qty_key), None)
        if qty_key is None or cost_key is None:
            raise ValueError(f"외주용역비 구분2 키 자동 감지 실패: {types}")
        return qty_key, cost_key

    groups = []
    for g1 in groups_order:
        qty_key, cost_key = get_keys(g1)
        scale = next((v for kw, v in _외주_단가_배율.items() if kw in qty_key), 100)
        metrics = [
            (qty_key,  make_item_vals(g1, qty_key),                  'qty'),
            (cost_key, make_item_vals(g1, cost_key),                 'cost'),
            ('단가',   make_rate_vals(g1, qty_key, cost_key, scale), 'rate'),
        ]
        groups.append((g1, metrics))

    return groups, col_hdrs


def _외주용역비_to_html(groups, col_hdrs):
    n_cols = len(col_hdrs) + 2  # 구분 + 연도/월 컬럼들 + 전월비
    th = (f'<th style="{_TH}">구분</th>' +
          ''.join(f'<th style="{_TH}">{h}</th>' for h in col_hdrs) +
          f'<th style="{_TH}">전월비</th>')

    body = ''
    for grp_name, metrics in groups:
        body += f'<tr><td colspan="{n_cols}" style="{ROW_GRP}">{grp_name}</td></tr>'
        for metric_name, vals, kind in metrics:
            lbl_s = _TD_LBL if kind == 'rate' else ROW_ITEM
            cells = f'<td style="{lbl_s}">{metric_name}</td>'
            last = len(vals) - 1
            for j, v in enumerate(vals):
                s = (_TD_RED if v < 0 else _TD_NUM) if j == last else _TD_NUM
                cells += f'<td style="{s}">{_fmt(v)}</td>'
            body += f'<tr>{cells}</tr>'

    return _html_table(f'<tr>{th}</tr>', body)


# ── 3) 멕시코향 환차소급 ─────────────────────────────────────────────────

def _build_환차소급(year, month):
    df = load_sheet(Sheets.멕시코향환차소급_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    vm = df.set_index(['연도', '월', '구분1', '구분2'])['값'].to_dict()

    연도_in_db = sorted(df['연도'].unique().tolist())
    g2_types = list(dict.fromkeys(df['구분2'].tolist()))  # SGAM, MCM 순서 유지

    def raw(yr, mo, g1, g2):
        return vm.get((yr, mo, g1, g2), 0.0)

    def total(yr, mo, g1):
        return sum(raw(yr, mo, g1, g2) for g2 in g2_types)

    def make_note(yr, mo, g1):
        parts = [f"{g2} {int(round(raw(yr, mo, g1, g2))):,} USD"
                 for g2 in g2_types if raw(yr, mo, g1, g2) != 0.0]
        return ("- " + ", ".join(parts)) if parts else ""

    rows = []

    for yr in 연도_in_db:
        if yr > year:
            break
        max_mo = month if yr == year else 12
        yr_net = 0.0

        for mo in range(1, max_mo + 1):
            실적_t   = total(yr, mo, '실적')
            취소_t   = total(yr, mo, '예상분 취소')
            예상분_t = total(yr, mo, '예상분')
            monthly_net = 실적_t + 취소_t + 예상분_t

            if 실적_t == 0.0 and 취소_t == 0.0 and 예상분_t == 0.0:
                continue

            yr_net += monthly_net
            prev_yr, prev_mo = _prev(yr, mo)

            rows.append(('month_hdr', f"'{str(yr)[2:]}.{mo}월", monthly_net, ''))

            if 실적_t != 0.0:
                rows.append(('실적',
                              f"'{str(prev_yr)[2:]}.{prev_mo}월분",
                              실적_t, make_note(yr, mo, '실적')))
            if 취소_t != 0.0:
                rows.append(('취소',
                              f"'{str(prev_yr)[2:]}.{prev_mo}월 예상분 취소",
                              취소_t, make_note(yr, mo, '예상분 취소')))
            if 예상분_t != 0.0:
                rows.append(('예상',
                              f"'{str(yr)[2:]}.{mo}월 예상분",
                              예상분_t, make_note(yr, mo, '예상분')))

        rows.append(('cum', f"'{str(yr)[2:]}년 환차소급 누계액", yr_net, ''))

    return rows


def _환차소급_to_html(rows):
    th = (f'<th style="{_TH}">구분</th>'
          f'<th style="{_TH}">금액</th>'
          f'<th style="{_TH}">비고</th>')

    body = ''
    for kind, label, amount, note in rows:
        if kind == 'month_hdr':
            _sec_num = ROW_SEC + (f';text-align:right;color:{_C_RED}' if amount < 0 else ';text-align:right')
            cells = (f'<td style="{ROW_SEC}">{label}</td>'
                     f'<td style="{_sec_num}">{_fmt(amount)}</td>'
                     f'<td style="{ROW_SEC}"></td>')
        elif kind == '취소':
            cells = (f'<td style="{ROW_ITEM}">{label}</td>'
                     f'<td style="{_TD_RED}">{_fmt(amount)}</td>'
                     f'<td style="{_TD_LBL}">{note}</td>')
        elif kind in ('실적', '예상'):
            cells = (f'<td style="{ROW_ITEM}">{label}</td>'
                     f'<td style="{_TD_NUM}">{_fmt(amount)}</td>'
                     f'<td style="{_TD_LBL}">{note}</td>')
        else:  # cum
            num_s = ROW_CAL_RED if amount < 0 else ROW_CAL_NUM
            cells = (f'<td style="{ROW_CAL_LBL}">{label}</td>'
                     f'<td style="{num_s}">{_fmt(amount)}</td>'
                     f'<td style="{ROW_CAL_LBL}"></td>')
        body += f'<tr>{cells}</tr>'

    return _html_table(f'<tr>{th}</tr>', body)


# ── 4) 원주-멕시코 월별 환차소급 현황 ────────────────────────────────────

def _build_원주멕시코환차소급(year, month):
    df = load_sheet(Sheets.원주멕시코환차소급_DB)
    df.columns = df.columns.str.strip()
    df = _drop_empty(df, '연도', '월')

    df_txt = df[df['구분1'] == '지급월'].copy()
    df_num = df[df['구분1'] != '지급월'].copy()
    df_num['값'] = df_num['값'].apply(_parse)

    vm = df_num.set_index(['연도', '월', '구분1'])['값'].to_dict()
    tm = {(r['연도'], r['월']): str(r['값']).strip() for _, r in df_txt.iterrows()}

    연도_in_db = sorted(df['연도'].unique().tolist())
    recent     = _recent_months(year, month)
    col_hdrs   = _build_col_hdrs(연도_in_db, recent, annual_suffix='년 평균')

    def raw(yr, mo, g1):
        return vm.get((yr, mo, g1), 0.0)

    def text(yr, mo):
        sv = str(tm.get((yr, mo), '')).strip()
        return '' if sv in ('0', '0.0', 'nan', '', 'None') else sv

    def yr_avg(g1, yr):
        vals = [raw(yr, m, g1) for m in range(1, 13) if raw(yr, m, g1) != 0.0]
        return sum(vals) / len(vals) if vals else 0.0

    def diff_krw(yr, mo):
        last = raw(yr, mo, '최종환율')
        return (last - raw(yr, mo, '기준환율')) if last else 0.0

    def diff_usd(yr, mo):
        last = raw(yr, mo, '최종환율')
        return diff_krw(yr, mo) / last if last else 0.0

    def yr_avg_diff_krw(yr):
        avg_last = yr_avg('최종환율', yr)
        return (avg_last - yr_avg('기준환율', yr)) if avg_last else 0.0

    def yr_avg_diff_usd(yr):
        avg_last = yr_avg('최종환율', yr)
        return yr_avg_diff_krw(yr) / avg_last if avg_last else 0.0

    def make_num_row(g1):
        v  = [yr_avg(g1, yr) for yr in 연도_in_db]
        v += [raw(yr_c, mo_c, g1) for yr_c, mo_c in recent]
        return v

    rows = [
        ('소급금액', None,
         make_num_row('소급금액'), 'num', 0),
        ('매출액',   None,
         make_num_row('매출액'),   'num', 0),
        ('환율차이', 'KRW',
         [yr_avg_diff_krw(yr) for yr in 연도_in_db] + [diff_krw(yr_c, mo_c) for yr_c, mo_c in recent],
         'num', 0),
        ('환율차이', 'USD',
         [yr_avg_diff_usd(yr) for yr in 연도_in_db] + [diff_usd(yr_c, mo_c) for yr_c, mo_c in recent],
         'num', 2),
        ('기준환율', None,
         make_num_row('기준환율'), 'num', 0),
        ('최종환율', None,
         make_num_row('최종환율'), 'num', 0),
        ('지급월',   None,
         [''] * len(연도_in_db) + [text(yr_c, mo_c) for yr_c, mo_c in recent],
         'text', 0),
    ]

    return rows, col_hdrs


def _원주멕시코환차소급_to_html(rows, col_hdrs):
    th = (f'<th style="{_TH}" colspan="2">구분</th>' +
          ''.join(f'<th style="{_TH}">{h}</th>' for h in col_hdrs))

    body = ''
    for label1, label2, vals, kind, decimal in rows:
        is_krw = (label1 == '환율차이' and label2 == 'KRW')
        is_usd = (label1 == '환율차이' and label2 == 'USD')

        cells = ''
        if is_krw:
            cells += f'<td style="{_TD_LBL}" rowspan="2">환율차이</td>'
            cells += f'<td style="{ROW_ITEM}">KRW</td>'
        elif is_usd:
            cells += f'<td style="{ROW_ITEM}">USD</td>'
        else:
            cells += f'<td style="{_TD_LBL}" colspan="2">{label1}</td>'

        if kind == 'text':
            for v in vals:
                cells += f'<td style="{_TD_LBL}">{v}</td>'
        else:
            for v in vals:
                cells += f'<td style="{_TD_NUM}">{_fmt(v, decimal=decimal)}</td>'

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

    tabs = app.tabs(["멕시코向 운반비", "외주용역비", "멕시코向 환차소급"])

    with tabs[0]:
        def _render_운반비():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_spec = _build_운반비(year, month)
            memo = _get_memo(Sheets.운반실적및컨테이너단가_메모, year, month)
            app.markdown(
                _layout64('1) 운반 실적 및 컨테이너당 단가 추이',
                          _운반비_to_html(rows, col_spec),
                          memo,
                          unit='[단위: EA, 천원]'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_운반비)

    with tabs[1]:
        def _render_외주():
            year, month = int(year_state.value), int(month_state.value)
            groups, col_hdrs = _build_외주용역비(year, month)
            memo = _get_memo(Sheets.외주용역비_메모, year, month)
            app.markdown(
                _layout64('1) 외주용역비',
                          _외주용역비_to_html(groups, col_hdrs),
                          memo,
                          unit='[단위: 만개, 백만원, 원]'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_외주)

    with tabs[2]:
        def _render_환차():
            year, month = int(year_state.value), int(month_state.value)
            rows = _build_환차소급(year, month)
            memo = _get_memo(Sheets.멕시코향환차소급_메모, year, month)
            rows2, col_hdrs2 = _build_원주멕시코환차소급(year, month)
            memo2 = _get_memo(Sheets.원주멕시코환차소급_메모, year, month)
            app.markdown(
                _layout64('1) 국내 월별 환차소급',
                          _환차소급_to_html(rows),
                          memo,
                          unit='[단위: USD]') +
                '<div style="margin-top:24px"></div>' +
                _layout64('2) 국내-멕시코(SGAM) 월별 환차 소급 현황',
                          _원주멕시코환차소급_to_html(rows2, col_hdrs2),
                          memo2,
                          unit='[단위: USD]'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_환차)
