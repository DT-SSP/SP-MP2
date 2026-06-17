import datetime
import pandas as pd
from data.loader import load_sheet
from data.config import (
    Sheets,
    SONIK2_매출액_순서, SONIK2_판매량_순서, SONIK2_매출원가_순서, SONIK2_판관비_순서,
    입고_거래처_순서, 입고실적_합계_G3, 입고실적_서브_G3,
    원소재_거래처_순서, 원소재_G2_순서, 원소재_합계_G2_순서,
    제조노무비_G2_순서, 제조경비_G2_순서,
    급여_G2_순서, 관리비_G2_순서, 판매비_G2_순서, 공통비_G2_순서,
)
from views.common import (
    parse as _parse, fmt as _fmt,
    prev_month as _prev, drop_empty as _drop_empty, sort_by_order as _sort,
    TH as _TH, TD_NUM as _TD_NUM, TD_RED as _TD_RED,
    ROW_SEC, ROW_GRP, ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED,
    ROW_CAL_LBL, ROW_CAL_NUM, ROW_CAL_RED, ROW_ITEM,
    html_table as _html_table, layout64 as _layout64,
)


# ── 공통 로더 ─────────────────────────────────────────────────────────────

def _get_연도_목록():
    df = load_sheet(Sheets.손익요약_DB)
    return sorted(pd.to_numeric(df['연도'], errors='coerce').dropna().astype(int).unique().tolist())


def _get_memo(sheet_info, year, month):
    df = load_sheet(sheet_info)
    df['연도'] = df['연도'].astype(str).str.strip()
    df['월']   = df['월'].astype(str).str.strip()
    row = df[(df['연도'] == str(year)) & (df['월'] == str(month))]
    return str(row.iloc[0]['메모']) if not row.empty else ''


# ── 1) 손익요약_국내 ───────────────────────────────────────────────────────

# (구분1, 하위항목순서, 단위)
_SONIK2_GROUPS = [
    ('매출액',   SONIK2_매출액_순서,   1e6),
    ('판매량',   SONIK2_판매량_순서,   1e4),
    ('매출원가', SONIK2_매출원가_순서, 1e6),
    ('판관비',   SONIK2_판관비_순서,   1e6),
]


def _build_손익요약_국내(year, month):
    df = load_sheet(Sheets.손익요약_DB)
    df['값'] = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    yr1 = year - 2
    yr2 = year - 1
    yr_전월, mo_전월 = _prev(year, month, 1)

    vm = df.set_index(['연도', '월', '구분1', '구분2'])['값'].to_dict()

    def yr_sum(yr, g1, subs):
        return sum(vm.get((yr, mo, g1, s), 0.0) for mo in range(1, 13) for s in subs)

    def mo_sum(yr, mo, g1, subs):
        return sum(vm.get((yr, mo, g1, s), 0.0) for s in subs)

    def ytd_sum(g1, subs):
        return sum(vm.get((year, mo, g1, s), 0.0) for mo in range(1, month + 1) for s in subs)

    col_yr1  = f"'{str(yr1)[2:]}년"
    col_yr2  = f"'{str(yr2)[2:]}년"
    col_전월 = f"'{str(yr_전월)[2:]}년 {mo_전월}월"
    col_당월 = f"'{str(year)[2:]}년 {month}월"

    # rows: (type, label, yr1_v, yr2_v, 전월_v, 당월_v, diff_v, ytd_v)
    rows   = []
    totals = {}  # {g1: (yr1, yr2, 전월, 당월, ytd)}

    for g1, config_subs, div in _SONIK2_GROUPS:
        subs = _sort(df[df['구분1'] == g1]['구분2'].unique().tolist(), config_subs)
        t = tuple(x / div for x in (
            yr_sum(yr1, g1, subs),
            yr_sum(yr2, g1, subs),
            mo_sum(yr_전월, mo_전월, g1, subs),
            mo_sum(year, month, g1, subs),
            ytd_sum(g1, subs),
        ))
        totals[g1] = t
        rows.append(('header', g1, t[0], t[1], t[2], t[3], t[3] - t[2], t[4]))

        for s in subs:
            sv = tuple(x / div for x in (
                yr_sum(yr1, g1, [s]),
                yr_sum(yr2, g1, [s]),
                mo_sum(yr_전월, mo_전월, g1, [s]),
                mo_sum(year, month, g1, [s]),
                ytd_sum(g1, [s]),
            ))
            rows.append(('sub', s, sv[0], sv[1], sv[2], sv[3], sv[3] - sv[2], sv[4]))

        if g1 == '매출원가':
            rev = totals['매출액']
            mi  = tuple(rev[i] - t[i] for i in range(5))
            rows.append(('calc', '매출이익', mi[0], mi[1], mi[2], mi[3], mi[3] - mi[2], mi[4]))
            rows.append(('pct', '%',
                         mi[0] / rev[0] * 100 if rev[0] else 0.0,
                         mi[1] / rev[1] * 100 if rev[1] else 0.0,
                         mi[2] / rev[2] * 100 if rev[2] else 0.0,
                         mi[3] / rev[3] * 100 if rev[3] else 0.0,
                         (mi[3] / rev[3] * 100 if rev[3] else 0.0) - (mi[2] / rev[2] * 100 if rev[2] else 0.0),
                         mi[4] / rev[4] * 100 if rev[4] else 0.0,
                         ))

    # 영업이익 (DB 직접 값, 구분2='영업이익')
    rev = totals['매출액']
    ei  = tuple(x / 1e6 for x in (
        yr_sum(yr1, '영업이익', ['영업이익']),
        yr_sum(yr2, '영업이익', ['영업이익']),
        mo_sum(yr_전월, mo_전월, '영업이익', ['영업이익']),
        mo_sum(year, month, '영업이익', ['영업이익']),
        ytd_sum('영업이익', ['영업이익']),
    ))
    rows.append(('calc', '영업이익', ei[0], ei[1], ei[2], ei[3], ei[3] - ei[2], ei[4]))
    rows.append(('pct', '%',
                 ei[0] / rev[0] * 100 if rev[0] else 0.0,
                 ei[1] / rev[1] * 100 if rev[1] else 0.0,
                 ei[2] / rev[2] * 100 if rev[2] else 0.0,
                 ei[3] / rev[3] * 100 if rev[3] else 0.0,
                 (ei[3] / rev[3] * 100 if rev[3] else 0.0) - (ei[2] / rev[2] * 100 if rev[2] else 0.0),
                 ei[4] / rev[4] * 100 if rev[4] else 0.0,
                 ))

    return rows, col_yr1, col_yr2, col_전월, col_당월


def _손익요약_to_html(rows, col_yr1, col_yr2, col_전월, col_당월):
    headers = ['구분', col_yr1, col_yr2, col_전월, col_당월, '전월대비', '누계']
    th_html = f'<tr>{"".join(f"<th style=\"{_TH}\">{h}</th>" for h in headers)}</tr>'

    body_html = ''
    sub_idx   = 0

    for row_type, label, yr1, yr2, 전월, 당월, diff, ytd in rows:
        vals = (yr1, yr2, 전월, 당월, diff, ytd)

        if row_type == 'header':
            sub_idx = 0
            cells = f'<td style="{ROW_HDR_LBL}">{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_HDR_RED if v < 0 else ROW_HDR_NUM}">{_fmt(v)}</td>'

        elif row_type == 'sub':
            bg = ';background:#f9f9fb' if sub_idx % 2 == 1 else ''
            sub_idx += 1
            cells = f'<td style="{ROW_ITEM + bg}">&nbsp;&nbsp;&nbsp;{label}</td>'
            for v in vals:
                cells += f'<td style="{(_TD_RED if v < 0 else _TD_NUM) + bg}">{_fmt(v)}</td>'

        elif row_type == 'calc':
            sub_idx = 0
            cells = f'<td style="{ROW_CAL_LBL}">{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_CAL_RED if v < 0 else ROW_CAL_NUM}">{_fmt(v)}</td>'

        elif row_type == 'pct':
            cells = f'<td style="{ROW_ITEM}">%</td>'
            for v in vals:
                cells += f'<td style="{(_TD_RED if v < 0 else _TD_NUM)}">{_fmt(v, is_pct=True, decimal=1)}</td>'

        body_html += f'<tr>{cells}</tr>'

    return _html_table(th_html, body_html)


# ── 1) 거래처 및 강종별 입고 현황 ─────────────────────────────────────────

def _build_거래처입고현황(year, month):
    df = load_sheet(Sheets.거래처강종별입고현황_DB)
    df = df.rename(columns={'구분 1': 'g1', '구분 2': 'g2', '구분 3': 'g3'})

    df['연도'] = pd.to_numeric(df['연도'], errors='coerce')
    df = df.dropna(subset=['연도']).copy()
    df['연도'] = df['연도'].astype(int)
    df['월'] = df['월'].apply(
        lambda x: int(float(x)) if str(x).strip().replace('.', '', 1).isdigit() else str(x).strip()
    )

    # 원시 float 맵 (양수만, YTD 평균 계산용)
    vm = {}
    for _, row in df.iterrows():
        s = str(row['값']).strip()
        if not s or s in ('-', 'nan'):
            continue
        try:
            v = float(s)
        except ValueError:
            continue
        if v > 0:
            vm[(row['g1'], row['g2'], row['g3'], row['연도'], row['월'])] = v

    def _disp(v, g3):
        if v == 0.0:
            return '-'
        return f"{round(v * 100)}%" if g3 == '입고비중' else _fmt(v)

    dm = {k: _disp(v, k[2]) for k, v in vm.items()}

    def get_ytd(g1, g2, g3):
        """1월~선택월 평균 (DB에 값 있는 월만)"""
        nums = [vm[(g1, g2, g3, year, m)] for m in range(1, month + 1)
                if (g1, g2, g3, year, m) in vm]
        if not nums:
            return '-'
        return _disp(sum(nums) / len(nums), g3)

    def get_col(g1, g2, g3, col_key):
        return get_ytd(g1, g2, g3) if col_key == 'ytd' else dm.get((g1, g2, g3) + col_key, '-')

    yr3, yr2, yr1 = year - 3, year - 2, year - 1
    y_m2, m_m2 = _prev(year, month, 2)
    y_m1, m_m1 = _prev(year, month, 1)

    col_keys = [
        (yr3, '평균'), (yr2, '평균'), (yr1, '평균'), 'ytd',
        (y_m2, m_m2), (y_m1, m_m1), (year, month),
    ]
    col_headers = [
        f"'{str(yr3)[2:]}년 평균", f"'{str(yr2)[2:]}년 평균",
        f"'{str(yr1)[2:]}년 평균", f"'{str(year)[2:]}년 평균",
        f"'{str(y_m2)[2:]}.{m_m2}월", f"{m_m1}월", f"{month}월",
    ]

    rows = []

    # 입고실적: section → group → item
    rows.append(('section', '입고실적', []))
    for g2 in _sort(df[df['g1'] == '입고실적']['g2'].unique().tolist(), 입고_거래처_순서):
        rows.append(('group', g2, []))
        g3_cfg = 입고실적_합계_G3 if g2 == '합계' else 입고실적_서브_G3
        for g3 in _sort(
            df[(df['g1'] == '입고실적') & (df['g2'] == g2)]['g3'].unique().tolist(), g3_cfg
        ):
            rows.append(('item', g3, [get_col('입고실적', g2, g3, ck) for ck in col_keys]))

    # 입고단가: section → group → item (강종 동적)
    rows.append(('section', '입고단가', []))
    for g2 in _sort(df[df['g1'] == '입고단가']['g2'].unique().tolist(), 입고_거래처_순서):
        rows.append(('group', g2, []))
        for g3 in df[(df['g1'] == '입고단가') & (df['g2'] == g2)]['g3'].unique().tolist():
            rows.append(('item', g3, [get_col('입고단가', g2, g3, ck) for ck in col_keys]))

    return rows, col_headers


def _rows_to_html(rows, col_headers):
    ITM_ST = 'padding:5px 10px 5px 32px;text-align:left;border-bottom:1px solid #e2e8f0'

    n_cols = 1 + len(col_headers)
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )

    body_html = ''
    item_idx = 0

    for row_type, label, vals in rows:
        if row_type == 'section':
            item_idx = 0
            body_html += f'<tr><td colspan="{n_cols}" style="{ROW_SEC}">{label}</td></tr>'

        elif row_type == 'group':
            item_idx = 0
            body_html += f'<tr><td colspan="{n_cols}" style="{ROW_GRP}">&nbsp;&nbsp;&nbsp;{label}</td></tr>'

        elif row_type == 'item':
            bg = ';background:#f9f9fb' if item_idx % 2 == 1 else ''
            item_idx += 1
            cells = f'<td style="{ITM_ST + bg}">{label}</td>'
            for v in vals:
                is_neg = str(v).startswith('-') and v != '-'
                cells += f'<td style="{(_TD_RED if is_neg else _TD_NUM) + bg}">{v}</td>'
            body_html += f'<tr>{cells}</tr>'

    return _html_table(th_html, body_html)


# ── 2) 원소재 투입 비중 ────────────────────────────────────────────────────

def _build_원소재투입비중(year, month):
    df = load_sheet(Sheets.원소재투입비중_DB)
    df = df.rename(columns={'구분 1': 'g1', '구분 2': 'g2'})

    df['연도'] = pd.to_numeric(df['연도'], errors='coerce')
    df = df.dropna(subset=['연도']).copy()
    df['연도'] = df['연도'].astype(int)
    df['월'] = df['월'].apply(
        lambda x: int(float(x)) if str(x).strip().replace('.', '', 1).isdigit() else str(x).strip()
    )

    def _disp(v, g2):
        if v == 0.0:
            return '-'
        return f"{v * 100:.1f}%" if g2 == '비중' else _fmt(v)

    vm = {}
    for _, row in df.iterrows():
        s = str(row['값']).strip()
        if not s or s in ('-', 'nan'):
            continue
        try:
            v = float(s)
        except ValueError:
            continue
        if v > 0:
            vm[(row['g1'], row['g2'], row['연도'], row['월'])] = v

    dm = {k: _disp(v, k[1]) for k, v in vm.items()}

    def get_ytd(g1, g2):
        if g2 in ('출고량', '출고금액'):
            nums = [vm[(g1, g2, year, m)] for m in range(1, month + 1) if (g1, g2, year, m) in vm]
            return '-' if not nums else _disp(sum(nums) / len(nums), g2)

        if g2 == '출고단가':
            금액 = [vm[(g1, '출고금액', year, m)] for m in range(1, month + 1) if (g1, '출고금액', year, m) in vm]
            량   = [vm[(g1, '출고량',   year, m)] for m in range(1, month + 1) if (g1, '출고량',   year, m) in vm]
            s_량 = sum(량)
            return '-' if not 금액 or not 량 or s_량 == 0 else _disp(sum(금액) / s_량 * 1000, g2)

        if g2 == '비중':
            months = [m for m in range(1, month + 1)
                      if (g1, '출고금액', year, m) in vm and ('합계', '출고금액', year, m) in vm]
            if not months:
                return '-'
            my_sum  = sum(vm[(g1, '출고금액', year, m)] for m in months)
            tot_sum = sum(vm[('합계', '출고금액', year, m)] for m in months)
            return '-' if not tot_sum else _disp(my_sum / tot_sum, g2)

        return '-'

    def get_col(g1, g2, ck):
        return get_ytd(g1, g2) if ck == 'ytd' else dm.get((g1, g2) + ck, '-')

    yr3, yr2, yr1 = year - 3, year - 2, year - 1
    col_keys = [(yr3, '평균'), (yr2, '평균'), (yr1, '평균'), 'ytd'] + [(year, m) for m in range(1, month + 1)]
    col_headers = [
        f"'{str(yr3)[2:]}년 평균", f"'{str(yr2)[2:]}년 평균", f"'{str(yr1)[2:]}년 평균",
        f"'{str(year)[2:]}년 평균",
    ] + [f"'{str(year)[2:]}.{m}월" if m == 1 else f"{m}월" for m in range(1, month + 1)]

    rows = []
    for g1 in _sort(df['g1'].unique().tolist(), 원소재_거래처_순서):
        rows.append(('group', g1, []))
        g2_order = 원소재_합계_G2_순서 if g1 == '합계' else 원소재_G2_순서
        for g2 in _sort(df[df['g1'] == g1]['g2'].unique().tolist(), g2_order):
            rows.append(('item', g2, [get_col(g1, g2, ck) for ck in col_keys]))

    return rows, col_headers


# ── 1) 전월비·계획대비 비용 증감 (공통 빌더) ─────────────────────────────────

def _build_비용표(sheet, g1_cfgs, year, month):
    df = load_sheet(sheet)
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)

    vm = df.set_index(['구분1', '구분2', '구분3', '연도', '월'])['값'].to_dict()
    prev_yr, prev_mo = _prev(year, month, 1)

    def get(g1, g2, g3, yr, mo):
        return vm.get((g1, g2, g3, yr, mo), 0.0)

    def _fv(v):
        if v == 0: return '-'
        return f"{v:.1f}" if 0 < abs(v) < 1 else _fmt(v)

    def _fd(v):
        if v == 0: return '0'
        if 0 < abs(v) < 1:
            s = f"{abs(v):.1f}"
            return f"-{s}" if v < 0 else s
        n = round(abs(v))
        return f"-{n:,}" if v < 0 else f"{n:,}"

    rows = []
    총_prev = 총_curr = 총_plan = 0.0

    for g1, g2_cfg in g1_cfgs:
        g2_list = _sort(df[df['구분1'] == g1]['구분2'].unique().tolist(), g2_cfg)
        g1_prev = g1_curr = g1_plan = 0.0

        for g2 in g2_list:
            p  = get(g1, g2, '실적', prev_yr, prev_mo)
            c  = get(g1, g2, '실적', year, month)
            pl = get(g1, g2, '계획', year, month)
            rows.append(('item', g2, [_fv(p), _fv(c), _fd(c - p), _fv(pl), _fd(c - pl)]))
            g1_prev += p; g1_curr += c; g1_plan += pl

        rows.append(('calc', g1, [_fv(g1_prev), _fv(g1_curr), _fd(g1_curr - g1_prev),
                                   _fv(g1_plan), _fd(g1_curr - g1_plan)]))
        총_prev += g1_prev; 총_curr += g1_curr; 총_plan += g1_plan

    rows.append(('calc', '총합', [_fv(총_prev), _fv(총_curr), _fd(총_curr - 총_prev),
                                   _fv(총_plan), _fd(총_curr - 총_plan)]))

    prev_hdr = f"{prev_mo}월" if prev_yr == year else f"'{str(prev_yr)[2:]}.{prev_mo}월"
    return rows, [prev_hdr, f"{month}월", '전월비', '계획', '계획비']


def _build_제조가공비(year, month):
    return _build_비용표(
        Sheets.제조가공비_DB,
        [('제조노무비', 제조노무비_G2_순서), ('제조경비', 제조경비_G2_순서)],
        year, month,
    )


def _build_판관비(year, month):
    return _build_비용표(
        Sheets.판관비_DB,
        [
            ('급여',   급여_G2_순서),
            ('관리비', 관리비_G2_순서),
            ('판매비', 판매비_G2_순서),
            ('공통비', 공통비_G2_순서),
        ],
        year, month,
    )


def _제조가공비_to_html(rows, col_headers):
    th_html = (
        f'<tr><th style="{_TH}">구분</th>'
        + ''.join(f'<th style="{_TH}">{h}</th>' for h in col_headers)
        + '</tr>'
    )
    body_html = ''
    item_idx  = 0

    for row_type, label, vals in rows:
        if row_type == 'calc':
            item_idx = 0
            cells = f'<td style="{ROW_CAL_LBL}">{label}</td>'
            for v in vals:
                cells += f'<td style="{ROW_CAL_RED if str(v).startswith("-") and v != "-" else ROW_CAL_NUM}">{v}</td>'
        elif row_type == 'item':
            bg = ';background:#f9f9fb' if item_idx % 2 == 1 else ''
            item_idx += 1
            cells = f'<td style="{ROW_ITEM + bg}">{label}</td>'
            for v in vals:
                cells += f'<td style="{(_TD_RED if str(v).startswith("-") and v != "-" else _TD_NUM) + bg}">{v}</td>'
        body_html += f'<tr>{cells}</tr>'

    return _html_table(th_html, body_html)


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
        app.title(f"{int(year_state.value)}년 {int(month_state.value)}월 손익분석")
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["손익요약", "전월∙계획 대비 손익차이", "원재료", "제조가공비", "판매비와 관리비"])

    with tabs[0]:
        def _render_손익요약():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_yr1, col_yr2, col_전월, col_당월 = _build_손익요약_국내(year, month)
            memo = _get_memo(Sheets.손익요약_메모, year, month)
            app.markdown(
                _layout64("1) 손익요약_국내",
                          _손익요약_to_html(rows, col_yr1, col_yr2, col_전월, col_당월),
                          memo),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_손익요약)

    with tabs[1]:
        def _render_차이():
            app.markdown("개발 예정")
        app.If(lambda: True, _render_차이)

    with tabs[2]:
        def _render_원재료():
            year, month = int(year_state.value), int(month_state.value)

            rows1, hdrs1 = _build_거래처입고현황(year, month)
            memo1 = _get_memo(Sheets.거래처강종별입고현황_메모, year, month)

            rows2, hdrs2 = _build_원소재투입비중(year, month)
            memo2 = _get_memo(Sheets.원소재투입비중_메모, year, month)

            app.markdown(
                _layout64("1) 거래처 및 강종별 입고 현황", _rows_to_html(rows1, hdrs1), memo1,
                          unit='[단위: 톤, 백만원]'),
                unsafe_allow_html=True,
            )
            app.markdown(
                _layout64("2) 원소재 투입 비중", _rows_to_html(rows2, hdrs2), memo2,
                          unit='[단위: 백만원, 톤]'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_원재료)

    with tabs[3]:
        def _render_제조가공비():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_headers = _build_제조가공비(year, month)
            memo = _get_memo(Sheets.제조가공비_메모, year, month)
            app.markdown(
                _layout64("1) 전월비, 계획대비 제조비용 증감",
                          _제조가공비_to_html(rows, col_headers),
                          memo, unit='[단위: 백만원]'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_제조가공비)

    with tabs[4]:
        def _render_판관비():
            year, month = int(year_state.value), int(month_state.value)
            rows, col_headers = _build_판관비(year, month)
            memo = _get_memo(Sheets.판관비_메모, year, month)
            app.markdown(
                _layout64("1) 전월비, 계획대비 판관비 증감",
                          _제조가공비_to_html(rows, col_headers),
                          memo, unit='[단위: 백만원]'),
                unsafe_allow_html=True,
            )
        app.If(lambda: True, _render_판관비)
