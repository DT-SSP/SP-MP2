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
    TH as _TH, TD_NUM as _TD_NUM, TD_RED as _TD_RED, C_RED as _C_RED,
    ROW_SEC, ROW_GRP, ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED,
    ROW_CAL_LBL, ROW_CAL_NUM, ROW_CAL_RED, ROW_ITEM,
    html_table as _html_table, layout64 as _layout64, layout100 as _layout100,
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


def _build_손익요약표_table(year: int, month: int) -> pd.DataFrame:
    df_raw = load_sheet(Sheets.손익요약표_DB)
    df = df_raw.copy()
    
    # 숫자형 변환 (필요시 '값' 컬럼을 '실적'으로 복제)
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce')
    df['월'] = pd.to_numeric(df['월'], errors='coerce')
    if '값' in df.columns and '실적' not in df.columns:
        df['실적'] = df['값']
    df['실적'] = pd.to_numeric(df['실적'], errors='coerce')
    
    # 결측치 제거
    df = df.dropna(subset=['연도', '월'])

    # ─ 피벗 준비 ─
    pv = df.pivot_table(index=["연도", "월", "구분3", "구분4", "구분2"], values="실적", aggfunc="sum")
    pv_m = df.pivot_table(index=["연도", "월", "구분3", "구분2"], values="실적", aggfunc="sum")

    df_plan = df[df["구분3"] == "계획"].copy()
    pv_plan_dom = df_plan[df_plan["구분4"] == "당월"].pivot_table(index=["연도", "월", "구분2"], values="실적", aggfunc="sum")
    pv_plan_cum = df_plan[df_plan["구분4"] == "누적"].pivot_table(index=["연도", "월", "구분2"], values="실적", aggfunc="sum")

    # ─ 기준 월/전월/전년 ─
    if month == 1:
        prev_year, pm = year - 1, 12
    else:
        prev_year, pm = year, month - 1
    m, y_1, y_2 = month, year - 1, year - 2

    # ─ 값 헬퍼 ─
    def _tf(v):
        if isinstance(v, pd.Series): return np.nan
        return float(v) if pd.notna(v) else np.nan

    def _get(yy, mm, item, g3, g4):
        try:
            return _tf(pv.loc[(yy, mm, g3, g4, item)])
        except KeyError:
            return np.nan

    def get_acc_or_sum(yy, mm, item):
        try:
            return _tf(pv.loc[(yy, mm, "실적", "누적", item)])
        except KeyError: pass
        try:
            s = pv_m.loc[(yy, slice(1, mm), "실적", item)]
            return _tf(getattr(s, "sum", lambda: s)())
        except KeyError:
            return np.nan

    def get_plan_month(yy, mm, item):
        if (yy, mm, item) in pv_plan_dom.index:
            return _tf(pv_plan_dom.loc[(yy, mm, item)])
        cur = _tf(pv_plan_cum.loc[(yy, mm, item)]) if (yy, mm, item) in pv_plan_cum.index else np.nan
        if not pd.isna(cur):
            if mm == 1:
                prev = _tf(pv_plan_cum.loc[(yy - 1, 12, item)]) if (yy - 1, 12, item) in pv_plan_cum.index else 0.0
            else:
                prev = _tf(pv_plan_cum.loc[(yy, mm - 1, item)]) if (yy, mm - 1, item) in pv_plan_cum.index else 0.0
            return cur - prev
        return np.nan

    def _dup_row_before(df_target: pd.DataFrame, src_label: str, before_label: str) -> pd.DataFrame:
        src_rows = df_target[df_target["구분"] == src_label]
        if src_rows.empty: return df_target
        before_idx = df_target.index[df_target["구분"] == before_label]
        if len(before_idx) == 0: return df_target
        insert_pos = int(before_idx.min())
        dup = src_rows.copy(deep=True)
        upper = df_target.iloc[:insert_pos]
        lower = df_target.iloc[insert_pos:]
        return pd.concat([upper, dup, lower], ignore_index=True)

    # ─ 한 줄 ‘구분’ 순서 ─
    order = [
        "매출액", "제품등", "부산물",
        "판매량",
        "매출원가", "제품원가", "C조건 선임", "클레임", "재고평가분", "단가소급 등",
        "매출이익", "매출이익(%)",
        "판관비", "인건비", "관리비", "판매비",
        "영업이익", "영업이익(%)",
        "내수운반", "수출개별",
        "내수", "수출",
    ]

    col_23 = f"'{str(y_2)[-2:]}년"
    col_24 = f"'{str(y_1)[-2:]}년"
    col_pm = f"'{str(prev_year)[-2:]}년 {pm}월"
    col_m = f"'{str(year)[-2:]}년 {m}월①"
    col_pm_pln = f"'{str(prev_year)[-2:]}년 {pm}월계획"
    col_m_pln = f"'{str(year)[-2:]}년 {m}월계획②"
    cols_num = [col_23, col_24, col_pm, col_m, "전월대비", col_pm_pln, col_m_pln, "계획대비(①-②)", "당월누적"]

    out = pd.DataFrame({"구분": order})
    for c in cols_num:
        out[c] = np.nan

    data_items = set(order)

    # 1) 일반 항목 계산
    for lbl in order:
        if lbl.endswith("(%)") or lbl in ["매출액", "매출원가", "판관비", "매출이익", "영업이익"]:
            continue
        out.loc[out["구분"] == lbl, col_23] = _tf(get_acc_or_sum(y_2, 12, lbl))
        out.loc[out["구분"] == lbl, col_24] = _tf(get_acc_or_sum(y_1, 12, lbl))
        out.loc[out["구분"] == lbl, col_pm] = _tf(_get(prev_year, pm, lbl, "실적", "당월"))
        out.loc[out["구분"] == lbl, col_m] = _tf(_get(year, m, lbl, "실적", "당월"))
        out.loc[out["구분"] == lbl, col_pm_pln] = _tf(get_plan_month(prev_year, pm, lbl))
        out.loc[out["구분"] == lbl, col_m_pln] = _tf(get_plan_month(year, m, lbl))
        out.loc[out["구분"] == lbl, "당월누적"] = _tf(get_acc_or_sum(year, m, lbl))

    # 2) 총계 계산 함수
    def _sales_total(col):
        has_sales_item = ("매출액" in data_items) and not pd.isna(_tf(_get(year, m, "매출액", "실적", "당월")))
        if has_sales_item:
            return {
                col_23: _tf(get_acc_or_sum(y_2, 12, "매출액")), col_24: _tf(get_acc_or_sum(y_1, 12, "매출액")),
                col_pm: _tf(_get(prev_year, pm, "매출액", "실적", "당월")), col_m: _tf(_get(year, m, "매출액", "실적", "당월")),
                col_pm_pln: _tf(get_plan_month(prev_year, pm, "매출액")), col_m_pln: _tf(get_plan_month(year, m, "매출액")),
                "당월누적": _tf(get_acc_or_sum(year, m, "매출액"))
            }
        else:
            def v_part(c, item):
                if c == col_23: return _tf(get_acc_or_sum(y_2, 12, item))
                if c == col_24: return _tf(get_acc_or_sum(y_1, 12, item))
                if c == col_pm: return _tf(_get(prev_year, pm, item, "실적", "당월"))
                if c == col_m: return _tf(_get(year, m, item, "실적", "당월"))
                if c == col_pm_pln: return _tf(get_plan_month(prev_year, pm, item))
                if c == col_m_pln: return _tf(get_plan_month(year, m, item))
                if c == "당월누적": return _tf(get_acc_or_sum(year, m, item))
                return np.nan
            summ = {}
            for c in [col_23, col_24, col_pm, col_m, col_pm_pln, col_m_pln, "당월누적"]:
                a, b = v_part(c, "제품등"), v_part(c, "부산물")
                summ[c] = (0.0 if pd.isna(a) else a) + (0.0 if pd.isna(b) else b)
            return summ

    def _cogs_total(col):
        parts = ["매출원가", "제품원가", "C조건 선임", "클레임", "재고평가분", "단가소급 등"]
        def get(item, c):
            if c == col_23: return _tf(get_acc_or_sum(y_2, 12, item))
            if c == col_24: return _tf(get_acc_or_sum(y_1, 12, item))
            if c == col_pm: return _tf(_get(prev_year, pm, item, "실적", "당월"))
            if c == col_m: return _tf(_get(year, m, item, "실적", "당월"))
            if c == col_pm_pln: return _tf(get_plan_month(prev_year, pm, item))
            if c == col_m_pln: return _tf(get_plan_month(year, m, item))
            if c == "당월누적": return _tf(get_acc_or_sum(year, m, item))
            return np.nan
        totals = {}
        for c in [col_23, col_24, col_pm, col_m, col_pm_pln, col_m_pln, "당월누적"]:
            v_direct = get("매출원가", c)
            if not pd.isna(v_direct):
                totals[c] = v_direct
            else:
                s, any_found = 0.0, False
                for p in parts[1:]:
                    v = get(p, c)
                    if not pd.isna(v): s += v; any_found = True
                totals[c] = s if any_found else np.nan
        return totals

    def _sganda_total(col):
        def get(item, c):
            if c == col_23: return _tf(get_acc_or_sum(y_2, 12, item))
            if c == col_24: return _tf(get_acc_or_sum(y_1, 12, item))
            if c == col_pm: return _tf(_get(prev_year, pm, item, "실적", "당월"))
            if c == col_m: return _tf(_get(year, m, item, "실적", "당월"))
            if c == col_pm_pln: return _tf(get_plan_month(prev_year, pm, item))
            if c == col_m_pln: return _tf(get_plan_month(year, m, item))
            if c == "당월누적": return _tf(get_acc_or_sum(year, m, item))
            return np.nan
        totals = {}
        for c in [col_23, col_24, col_pm, col_m, col_pm_pln, col_m_pln, "당월누적"]:
            v_direct = get("판관비", c)
            if not pd.isna(v_direct): totals[c] = v_direct
            else:
                s, any_found = 0.0, False
                for p in ["인건비", "관리비", "판매비"]:
                    v = get(p, c)
                    if not pd.isna(v): s += v; any_found = True
                totals[c] = s if any_found else np.nan
        return totals

    for lbl, calc in [("매출액", _sales_total), ("매출원가", _cogs_total), ("판관비", _sganda_total)]:
        if lbl in out["구분"].values:
            d = calc(None)
            for c in [col_23, col_24, col_pm, col_m, col_pm_pln, col_m_pln, "당월누적"]:
                out.loc[out["구분"] == lbl, c] = _tf(d[c])

    # 3) 이익 계산 
    if "매출이익" in out["구분"].values:
        for c in [col_23, col_24, col_pm, col_m, "당월누적", col_pm_pln, col_m_pln]:
            s = _tf(out.loc[out["구분"] == "매출액", c])
            g = _tf(out.loc[out["구분"] == "매출원가", c])
            out.loc[out["구분"] == "매출이익", c] = np.nan if pd.isna(s) or pd.isna(g) else (s - g)

    if "영업이익" in out["구분"].values:
        for c in [col_23, col_24, col_pm, col_m, "당월누적", col_pm_pln, col_m_pln]:
            gp = _tf(out.loc[out["구분"] == "매출이익", c])
            sg = _tf(out.loc[out["구분"] == "판관비", c])
            out.loc[out["구분"] == "영업이익", c] = np.nan if pd.isna(gp) or pd.isna(sg) else (gp - sg)

    out["전월대비"] = out[col_m].astype(float) - out[col_pm].astype(float)
    out["계획대비(①-②)"] = out[col_m].astype(float) - out[col_m_pln].astype(float)

    # 4) 퍼센트 계산
    def _pct(num, den):
        if pd.isna(num) or pd.isna(den) or den == 0: return np.nan
        return (num / den) * 100.0

    for c in cols_num:
        if c in ["전월대비", "계획대비(①-②)"]: continue
        den = _tf(out.loc[out["구분"] == "매출액", c])
        out.loc[out["구분"] == "매출이익(%)", c] = _pct(_tf(out.loc[out["구분"] == "매출이익", c]), den)
        out.loc[out["구분"] == "영업이익(%)", c] = _pct(_tf(out.loc[out["구분"] == "영업이익", c]), den)

    # 5) 포맷팅
    def fmt_amt(x):
        if pd.isna(x): return ""
        try: v = float(x)
        except: return str(x)
        if v < 0: return f'<span style="color:#d32f2f;">-{abs(int(round(v))):,}</span>'
        return f"{int(round(v)):,}"

    def fmt_pct(x):
        if pd.isna(x): return ""
        try: v = float(x)
        except: return str(x)
        if v < 0: return f'<span style="color:#d32f2f;">-{abs(v):,.1f}</span>'
        return f"{v:,.1f}"

    pct_mask = out["구분"].astype(str).str.endswith("(%)")
    for c in cols_num:
        out.loc[~pct_mask, c] = out.loc[~pct_mask, c].apply(fmt_amt)
        out.loc[pct_mask, c] = out.loc[pct_mask, c].apply(fmt_pct)

    # 중복 삽입
    out = _dup_row_before(out, src_label="판매비", before_label="내수운반")
    out = _dup_row_before(out, src_label="판매량", before_label="내수")

    # 빈 행 삽입 유틸
    def insert_empty_after(df, gubun_value):
        idx_list = df.index[df["구분"].astype(str).str.strip() == gubun_value].tolist()
        if not idx_list: return df
        insert_at = idx_list[-1] + 1
        empty_row = pd.DataFrame([{"구분": ""} for _ in df.columns]) 
        return pd.concat([df.iloc[:insert_at], pd.DataFrame([{"구분": ""}]), df.iloc[insert_at:]], ignore_index=True)

    out = insert_empty_after(out, "영업이익(%)")
    out = insert_empty_after(out, "수출개별")

    # ─ 열 이름 변경 (화면 표시용) ─
    rename_map = {
        col_23: f"'{str(y_2)[-2:]}년",
        col_24: f"'{str(y_1)[-2:]}년",
        col_pm: f"'{str(prev_year)[-2:]}년 {pm}월",
        col_m: f"'{str(year)[-2:]}년 {m}월①",
        col_pm_pln: f"'{str(prev_year)[-2:]}년 {pm}월 계획",
        col_m_pln: f"'{str(year)[-2:]}년 {m}월 계획②",
        "계획대비(①-②)": "계획대비"
    }
    out = out.rename(columns=rename_map)

    # ─ _depth 및 _bold 설정 (Violit 렌더러용) ─
    lv0_items = ['매출액', '판매량', '매출원가', '매출이익', '매출이익(%)', '판관비', '영업이익', '영업이익(%)']
    lv1_items = ['제품등', '부산물', '제품원가', 'C조건 선임', '클레임', '재고평가분', '단가소급 등', '인건비', '관리비', '판매비', '내수운반', '수출개별', '내수', '수출']

    depths, bolds = [], []
    vanmebi_seen = 0

    for val in out['구분']:
        clean = str(val).strip()
        if not clean:
            depths.append(0)
            bolds.append(False)
            continue
            
        if clean == "판매비":
            vanmebi_seen += 1
            lv = 1 if vanmebi_seen == 1 else 0
        elif clean in lv0_items:
            lv = 0
        elif clean in lv1_items:
            lv = 1
        else:
            lv = 0

        depths.append(lv)
        bolds.append(lv == 0)

    out['_depth'] = depths
    out['_bold'] = bolds

    # 내부 메타 컬럼 재배치
    cols = ['구분', '_depth', '_bold'] + [c for c in out.columns if c not in ['구분', '_depth', '_bold']]
    return out[cols].fillna("")


def _손익요약표_to_html_table(df):
    rows_html = ''
    
    # 메타 데이터를 제외한 실제 데이터 컬럼만 순회
    data_cols = [c for c in df.columns if c not in ('구분', '_depth', '_bold')]

    for _, row in df.iterrows():
        label = str(row["구분"]).strip()
        if not label: # 공백 행 처리
            rows_html += f'<tr><td colspan="{len(data_cols) + 1}" style="height:15px; border:none;"></td></tr>'
            continue

        depth = row.get('_depth', 0)
        is_bold = row.get('_bold', False)
        
        # Violit 기본 스타일링 상수에 들여쓰기 덧입힘
        style_label = ROW_HDR_LBL if is_bold else ROW_ITEM
        style_num = ROW_HDR_NUM if is_bold else _TD_NUM
        
        padding = depth * 16
        cells = f'<td style="{style_label}; padding-left:{padding}px;">{label}</td>'
        
        for col in data_cols:
            val = row[col]
            cells += f'<td style="{style_num}">{val}</td>'
        rows_html += f'<tr>{cells}</tr>'

    headers_html = f'<th style="{_TH}">구분</th>'
    headers_html += ''.join(f'<th style="{_TH}">{c}</th>' for c in data_cols)
    
    return _html_table(f'<tr>{headers_html}</tr>', rows_html)


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

        rows.append(('sec', g1, [_fv(g1_prev), _fv(g1_curr), _fd(g1_curr - g1_prev),
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
        if row_type == 'sec':
            item_idx = 0
            cells = f'<td style="{ROW_SEC}">{label}</td>'
            for v in vals:
                _sec_num = ROW_SEC + (f';text-align:right;color:{_C_RED}' if str(v).startswith('-') and v != '-' else ';text-align:right')
                cells += f'<td style="{_sec_num}">{v}</td>'
        elif row_type == 'calc':
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

def render_page(app, year_state, month_state):

    def _render_title():
        app.markdown(
            f'<h1 style="color:#404448">{int(year_state.value)}년 {int(month_state.value)}월 손익분석</h1>',
            unsafe_allow_html=True,
        )
    app.If(lambda: True, _render_title)

    tabs = app.tabs(["손익요약", "전월∙계획 대비 손익차이", "원재료", "제조가공비", "판매비와 관리비"])

    with tabs[0]:
        def _render_손익요약():
            year, month = int(year_state.value), int(month_state.value)

            df_table = _build_손익요약표_table(year, month)
            html = _손익요약표_to_html_table(df_table)
            app.markdown(_layout100("손익요약표", html, unit="[단위: 백만원]"), unsafe_allow_html=True)

        app.If(lambda: True, _render_손익요약)

        

'''    
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
        '''
