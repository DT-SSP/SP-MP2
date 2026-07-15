import datetime
import pandas as pd
from data.loader import load_sheet
from data.config import (
    Sheets,
    SONIK2_매출액_순서, SONIK2_판매량_순서, SONIK2_매출원가_순서, SONIK2_판관비_순서,
)
from views.common import (
    parse as _parse, fmt as _fmt,
    prev_month as _prev, drop_empty as _drop_empty, sort_by_order as _sort,
    TH as _TH, TD_NUM as _TD_NUM, TD_RED as _TD_RED, C_RED as _C_RED,
    ROW_SEC, ROW_GRP, ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED,
    ROW_CAL_LBL, ROW_CAL_NUM, ROW_CAL_RED, ROW_ITEM,
    html_table as _html_table, layout64 as _layout64, layout100 as _layout100,
)
import numpy as np

# ── 공통 로더 ─────────────────────────────────────────────────────────────

def _get_연도_목록():
    df = load_sheet(Sheets.손익요약_DB)
    return sorted(pd.to_numeric(df['연도'], errors='coerce').dropna().astype(int).unique().tolist())

def _get_memo(sheet_info, year, month):
    try:
        df = load_sheet(sheet_info)
        # 시트가 비어있거나 '연도', '월' 컬럼이 아예 없으면 빈 문자열 반환
        if df.empty or '연도' not in df.columns or '월' not in df.columns:
            return ''
        
        df['연도'] = df['연도'].astype(str).str.strip()
        df['월']   = df['월'].astype(str).str.strip()
        row = df[(df['연도'] == str(year)) & (df['월'] == str(month))]
        
        if '메모' in df.columns and not row.empty:
            return str(row.iloc[0]['메모'])
        return ''
    except Exception:
        # 어떤 에러가 발생해도 전체 표를 그리는 데는 지장이 없도록 처리
        return ''

# ── 1) 손익요약_국내 ───────────────────────────────────────────────────────

# (구분1, 하위항목순서, 단위)
_SONIK2_GROUPS = [
    ('매출액',   SONIK2_매출액_순서,   1e6),
    ('판매량',   SONIK2_판매량_순서,   1e4),
    ('매출원가', SONIK2_매출원가_순서, 1e6),
    ('판관비',   SONIK2_판관비_순서,   1e6),
]


def _build_손익요약표_table(year: int, month: int) -> pd.DataFrame:
    # 1. 데이터 로드 및 전처리
    df_raw = load_sheet(Sheets.손익요약표_DB)
    df = df_raw.copy()
    
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce')
    df['월'] = pd.to_numeric(df['월'], errors='coerce')
    df['값'] = pd.to_numeric(df['값'], errors='coerce')
    
    # [추가된 부분] 시트 내 시각적 용도로 중복 입력된 행(예: 판매량, 판매비)을 
    # 합산할 때 2배가 되지 않도록 완전히 동일한 조건의 행은 하나만 남기고 제거합니다.
    df = df.drop_duplicates(subset=['구분1', '구분2', '계획/실적', '구분3', '연도', '월'], keep='first')
    
    # 2. 기준 연도/월 변수 설정
    if month == 1:
        prev_year, pm = year - 1, 12
    else:
        prev_year, pm = year, month - 1
    m, y_1, y_2 = month, year - 1, year - 2

    # 3. DB 매핑용 딕셔너리
    item_map = {
        "매출액": ("매출액", ""),
        "제품등": ("매출액", "제품등"),
        "부산물": ("매출액", "부산물"),
        "판매량": ("판매량", ""),
        "매출원가": ("매출원가", ""),
        "제품원가": ("매출원가", "제품원가"),
        "C조건 선임": ("매출원가", "C조건 선임"),
        "클레임": ("매출원가", "클레임"),
        "재고평가분": ("매출원가", "재고평가분"),
        "단가소급 등": ("매출원가", "단가소급 등"),
        "매출이익": ("매출이익", ""),
        "판관비": ("판관비", ""),
        "인건비": ("판관비", "인건비"),
        "관리비": ("판관비", "관리비"),
        "판매비": ("판관비", "판매비"),
        "영업이익": ("영업이익", ""),
        "내수운반": ("판매비", "내수운반"),
        "수출개별": ("판매비", "수출개별"),
        "내수": ("판매량", "내수"),
        "수출": ("판매량", "수출"),
    }

    # 4. 연도별/유형별 데이터 추출 헬퍼 함수 (당월/누적 분기 로직 강화)
    def get_val(yr, mo, label, plan_type="실적", is_acc=False):
        if label not in item_map:
            return np.nan
        
        g1, g2 = item_map[label]
        
        base_mask = (df['연도'] == yr) & (df['계획/실적'] == plan_type) & (df['구분1'] == g1)
        
        if not g2:
            base_mask &= (df['구분2'].isna() | (df['구분2'] == ""))
        else:
            base_mask &= (df['구분2'] == g2)
            
        if yr <= 2024:
            # [수정된 부분] 24년 이전 데이터는 '월' 값이 없으므로(NaN), 월 필터링 제외
            if is_acc:
                mask = base_mask & (df['구분3'] == '누적')
                filtered = df[mask]
                return filtered['값'].sum() if not filtered.empty else np.nan
            else:
                # 24년 이전은 월별 데이터가 없어서 당월(월별 차이) 값을 계산할 수 없음
                # (예: 25년 1월 검색 시 전월(24년 12월) 당월 실적 등은 NaN으로 처리)
                return np.nan
        else:
            if is_acc:
                # 25년 이후 누적 조회: 1월부터 선택한 월까지의 '당월' 값을 합산
                mask = base_mask & (df['월'] <= mo) & (df['구분3'] == '당월')
            else:
                # 25년 이후 당월 조회
                mask = base_mask & (df['월'] == mo) & (df['구분3'] == '당월')
                
            filtered = df[mask]
            return filtered['값'].sum() if not filtered.empty else np.nan

    # 5. 화면 출력 순서 및 계층 구조
    display_order = [
        ("매출액", 0), ("제품등", 1), ("부산물", 1),
        ("판매량", 0),
        ("매출원가", 0), ("제품원가", 1), ("C조건 선임", 1), ("클레임", 1), ("재고평가분", 1), ("단가소급 등", 1),
        ("매출이익", 0), ("매출이익(%)", 0),
        ("판관비", 0), ("인건비", 1), ("관리비", 1), ("판매비", 1),
        ("영업이익", 0), ("영업이익(%)", 0),
        ("판매비", 0), ("내수운반", 1), ("수출개별", 1),
        ("판매량", 0), ("내수", 1), ("수출", 1)
    ]

    col_23 = f"'{str(y_2)[-2:]}년"
    col_24 = f"'{str(y_1)[-2:]}년"
    col_pm = f"'{str(prev_year)[-2:]}년 {pm}월"
    col_m = f"'{str(year)[-2:]}년 {m}월①"
    col_pm_pln = f"'{str(prev_year)[-2:]}년 {pm}월계획"
    col_m_pln = f"'{str(year)[-2:]}년 {m}월계획②"
    cols_num = [col_23, col_24, col_pm, col_m, "전월대비", col_pm_pln, col_m_pln, "계획대비", "당월누적"]

    # 6. 테이블 데이터 구축
    rows = []
    for label, depth in display_order:
        row = {'구분': label, '_depth': depth, '_bold': (depth == 0)}
        
        if label.endswith("(%)"):
            for c in cols_num: 
                row[c] = np.nan
        else:
            # 과거 두 개 연도 컬럼에도 'is_acc=True'를 전달하여 누적(총합)을 정확하게 구함
            row[col_23] = get_val(y_2, 12, label, is_acc=True)
            row[col_24] = get_val(y_1, 12, label, is_acc=True)
            
            row[col_pm] = get_val(prev_year, pm, label)
            row[col_m]  = get_val(year, m, label)
            row[col_pm_pln] = get_val(prev_year, pm, label, plan_type="계획")
            row[col_m_pln]  = get_val(year, m, label, plan_type="계획")
            row['당월누적'] = get_val(year, m, label, is_acc=True)
            
            row['전월대비'] = row[col_m] - row[col_pm] if pd.notna(row[col_m]) and pd.notna(row[col_pm]) else np.nan
            row['계획대비'] = row[col_m] - row[col_m_pln] if pd.notna(row[col_m]) and pd.notna(row[col_m_pln]) else np.nan
            
        rows.append(row)
        
    out = pd.DataFrame(rows)

    # 7. 퍼센트 계산
    def pct(num, den):
        if pd.isna(num) or pd.isna(den) or den == 0: return np.nan
        return (num / den) * 100.0

    calc_cols = [col_23, col_24, col_pm, col_m, col_pm_pln, col_m_pln, '당월누적']
    for c in calc_cols:
        sales_val = out.loc[out['구분'] == '매출액', c].values[0]
        gp_val = out.loc[out['구분'] == '매출이익', c].values[0]
        op_val = out.loc[out['구분'] == '영업이익', c].values[0]
        
        out.loc[out['구분'] == '매출이익(%)', c] = pct(gp_val, sales_val)
        out.loc[out['구분'] == '영업이익(%)', c] = pct(op_val, sales_val)

    # 8. 포맷팅 및 서식 적용 (타입 에러 방지)
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

    out[cols_num] = out[cols_num].astype(object)

    pct_mask = out["구분"].astype(str).str.endswith("(%)")
    for c in cols_num:
        out.loc[~pct_mask, c] = out.loc[~pct_mask, c].apply(fmt_amt)
        out.loc[pct_mask, c] = out.loc[pct_mask, c].apply(fmt_pct)

    # 9. 섹션 분리 (공백행 축소)
    def insert_empty_after(df, label):
        idx_list = df.index[df["구분"] == label].tolist()
        if not idx_list: return df
        idx = idx_list[-1]
        # 컬럼 개수만큼 빈 줄을 만들던 문제를 해결하고 딱 1줄만 생성
        empty_row = pd.DataFrame([{c: "" for c in df.columns}])
        return pd.concat([df.iloc[:idx+1], empty_row, df.iloc[idx+1:]], ignore_index=True)

    out = insert_empty_after(out, "영업이익(%)")
    out = insert_empty_after(out, "수출개별")

    cols = ['구분', '_depth', '_bold'] + cols_num
    return out[cols].fillna("")

def _손익요약표_to_html_table(df):
    rows_html = ''
    
    data_cols = [c for c in df.columns if c not in ('구분', '_depth', '_bold')]

    for _, row in df.iterrows():
        label = str(row["구분"]).strip()
        if not label: # 렌더러에서의 공백 행 처리
            rows_html += f'<tr><td colspan="{len(data_cols) + 1}" style="height:25px; border:none; background-color:#ffffff;"></td></tr>'
            continue

        depth = row.get('_depth', 0)
        is_bold = row.get('_bold', False)
        
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

# ────────────────────────────────────────────────────────────────────────
# 2-1) 수출 환율 차이 Builder & HTML Renderer
# ────────────────────────────────────────────────────────────────────────

def _build_수출환율차이_table(year: int, month: int):
    # 데이터 로드 (Sheets 설정에 맞게 변경 필요)
    df = load_sheet(Sheets.수출환율차이_DB) 

    # 1) 기본 전처리
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df["월"] = pd.to_numeric(df["월"], errors="coerce")
    df["값"] = df["값"].astype(str).str.replace(",", "", regex=False)
    df["값"] = pd.to_numeric(df["값"], errors="coerce")

    # 2) 기준월 / 전월 설정
    curr_y, curr_m = year, month
    prev_y, prev_m = (year, month - 1) if month > 1 else (year - 1, 12)

    prev_lab = f"'{str(prev_y)[-2:]}년 {prev_m}월"
    curr_lab = f"'{str(curr_y)[-2:]}년 {curr_m}월"

    df_curr = df[(df["연도"] == curr_y) & (df["월"] == curr_m)].copy()
    df_prev = df[(df["연도"] == prev_y) & (df["월"] == prev_m)].copy()

    # 3) 피벗 함수
    def make_month_pivot(df_m):
        if df_m.empty:
            base = pd.DataFrame(columns=["구분1", "중량", "외화공급가액", "원화공급가액"]).set_index("구분1")
        else:
            tmp = df_m.groupby(["구분1", "구분2"], as_index=False)["값"].sum()
            base = tmp.pivot(index="구분1", columns="구분2", values="값")

        for c in ["중량", "외화공급가액", "원화공급가액"]:
            if c not in base.columns: base[c] = np.nan
        for c in base.columns:
            base[c] = pd.to_numeric(base[c], errors="coerce")

        fx = base["외화공급가액"].replace(0, np.nan)
        base["환율"] = base["원화공급가액"] / fx
        return base[["중량", "외화공급가액", "환율", "원화공급가액"]]

    prev_p = make_month_pivot(df_prev).add_prefix(f"{prev_lab}_")
    curr_p = make_month_pivot(df_curr).add_prefix(f"{curr_lab}_")
    body = prev_p.join(curr_p, how="outer")

    # 4) 통화 순서 고정 및 차이 계산
    order_ccy = ["USD", "JPY", "CNY"]
    body = body.reindex(order_ccy)
    body.index.name = "구분"
    body = body.reset_index()

    prev_fx_col, curr_fx_col = f"{prev_lab}_환율", f"{curr_lab}_환율"
    curr_amt_col = f"{curr_lab}_외화공급가액"

    body["차이단가"] = body[curr_fx_col] - body[prev_fx_col]
    body["영향금액"] = body[curr_amt_col] * body["차이단가"]

    # 5) 총계 행
    sum_cols = [c for c in body.columns if c.endswith("_중량") or c.endswith("_외화공급가액") or c.endswith("_원화공급가액") or c == "영향금액"]
    total_row = {c: np.nan for c in body.columns}
    total_row["구분"] = "총계"
    for col in sum_cols:
        total_row[col] = body.loc[body["구분"].isin(order_ccy), col].sum(min_count=1)
    
    disp = pd.concat([body, pd.DataFrame([total_row])], ignore_index=True)

    # 6) 화면 표시를 위한 컬럼명 및 순서 정리
    block_prev = [f"{prev_lab}_중량", f"{prev_lab}_외화공급가액", f"{prev_lab}_환율", f"{prev_lab}_원화공급가액"]
    block_curr = [f"{curr_lab}_중량", f"{curr_lab}_외화공급가액", f"{curr_lab}_환율", f"{curr_lab}_원화공급가액"]
    ordered = ["구분"] + [c for c in block_prev if c in disp.columns] + [c for c in block_curr if c in disp.columns] + ["차이단가", "영향금액"]
    disp = disp[ordered]

    rename_map = {
        f"{prev_lab}_중량": f"{prev_lab} 중량", f"{prev_lab}_외화공급가액": f"{prev_lab} 외화공급가액",
        f"{prev_lab}_환율": f"{prev_lab} 환율", f"{prev_lab}_원화공급가액": f"{prev_lab} 원화공급가액",
        f"{curr_lab}_중량": f"{curr_lab} 중량", f"{curr_lab}_외화공급가액": f"{curr_lab} 외화공급가액",
        f"{curr_lab}_환율": f"{curr_lab} 환율", f"{curr_lab}_원화공급가액": f"{curr_lab} 원화공급가액",
        "차이단가": "환율차이단가", "영향금액": "환율차이 영향금액",
    }
    disp = disp.rename(columns=rename_map)

    return disp, prev_lab, curr_lab

def _수출환율차이_to_html(df, prev_lab, curr_lab) -> str:
    cols = df.columns.tolist()
    prev_last = f"{prev_lab} 원화공급가액"
    curr_last = f"{curr_lab} 원화공급가액"

    th_html = '<tr>'
    for c in cols:
        border_st = 'border-right: 1px solid #aaa;' if c in [prev_last, curr_last] else ''
        th_html += f'<th style="{_TH}; {border_st} white-space: nowrap;">{c}</th>'
    th_html += '</tr>'

    body_html = ''
    for _, row in df.iterrows():
        is_total = str(row['구분']).strip() == "총계"
        tr_weight = 'font-weight: 700; color: black;' if is_total else ''
        
        body_html += f'<tr style="{tr_weight}">'
        for c in cols:
            val = row[c]
            border_st = 'border-right: 1px solid #aaa;' if c in [prev_last, curr_last] else ''
            
            if c == '구분':
                text, align = str(val), 'left'
            else:
                align = 'right'
                try: val = float(str(val).replace(',', ''))
                except: pass

                if pd.isna(val) or str(val).strip() == '':
                    text = ""
                else:
                    is_neg = False
                    if c.endswith("환율"):
                        text = f"{abs(val):,.2f}"
                        is_neg = val < 0
                    elif c == "환율차이단가":
                        text = f"{abs(val):,.1f}"
                        is_neg = val < 0
                    else: 
                        val_div = val / 1000.0
                        text = f"{abs(int(round(val_div))):,}"
                        is_neg = val_div < 0

                    if is_neg:
                        text = f'<span style="color:#d32f2f;">-{text}</span>'

            td_style = f'border: 1px solid #aaa; padding: 8px 16px; font-size: 15px; text-align: {align}; {border_st}'
            body_html += f'<td style="{td_style}">{text}</td>'
        body_html += '</tr>'

    return _html_table(th_html, body_html)


# ────────────────────────────────────────────────────────────────────────
# 2-2) QD 실적 차이 Builder & HTML Renderer
# ────────────────────────────────────────────────────────────────────────

def _build_QD실적차이_table(year: int, month: int):
    df = load_sheet(Sheets.QD_DB)
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df["월"] = pd.to_numeric(df["월"], errors="coerce")
    
    def _coerce_numeric(val):
        if pd.isna(val): return np.nan
        s = str(val).strip()
        if s.startswith("(") and s.endswith(")"): s = "-" + s[1:-1]
        s = s.replace(",", "")
        try: return float(s) if s else np.nan
        except: return np.nan

    df["값"] = df["값"].apply(_coerce_numeric)

    curr_y, curr_m = year, month
    prev_y, prev_m = (year, month - 1) if month > 1 else (year - 1, 12)
    prev_label = f"'{str(prev_y)[-2:]}년 {prev_m}월"
    curr_label = f"'{str(curr_y)[-2:]}년 {curr_m}월"

    df_prev = df[(df["연도"] == prev_y) & (df["월"] == prev_m)].copy()
    df_curr = df[(df["연도"] == curr_y) & (df["월"] == curr_m)].copy()

    companies = ["태양금속공업㈜ 外", "(주)진합 外", "(주)청우", "(주)풍강", "기타"]
    result_rows = []

    for company in companies:
        row_data = {"구분": company}
        
        # 전월 (구분2 == "실적" 으로 필터링 수정)
        prev_qty = df_prev[(df_prev["구분1"] == company) & (df_prev["구분2"] == "실적") & (df_prev["구분3"] == "중량")]["값"].sum()
        prev_amt = df_prev[(df_prev["구분1"] == company) & (df_prev["구분2"] == "실적") & (df_prev["구분3"] == "금액")]["값"].sum()
        prev_price = prev_amt / prev_qty if prev_qty != 0 else 0
        
        # 당월 (구분2 == "실적" 으로 필터링 수정)
        curr_qty = df_curr[(df_curr["구분1"] == company) & (df_curr["구분2"] == "실적") & (df_curr["구분3"] == "중량")]["값"].sum()
        curr_amt = df_curr[(df_curr["구분1"] == company) & (df_curr["구분2"] == "실적") & (df_curr["구분3"] == "금액")]["값"].sum()
        curr_price = curr_amt / curr_qty if curr_qty != 0 else 0

        # 데이터 추가
        row_data.update({
            f"{prev_label} 중량": prev_qty, f"{prev_label} 단가": prev_price, f"{prev_label} 금액": prev_amt,
            f"{curr_label} 중량": curr_qty, f"{curr_label} 단가": curr_price, f"{curr_label} 금액": curr_amt,
            "단가차이 중량": curr_qty - prev_qty, "단가차이 단가": curr_price - prev_price, "단가차이 금액": curr_amt - prev_amt
        })
        result_rows.append(row_data)

    # 합계 행
    total_row = {"구분": "합계"}
    for col in result_rows[0].keys():
        if col != "구분": total_row[col] = sum(row.get(col, 0) for row in result_rows)
    result_rows.append(total_row)

    body = pd.DataFrame(result_rows)
    col_order = ["구분", f"{prev_label} 중량", f"{prev_label} 단가", f"{prev_label} 금액",
                 f"{curr_label} 중량", f"{curr_label} 단가", f"{curr_label} 금액",
                 "단가차이 중량", "단가차이 단가", "단가차이 금액"]
    
    return body[col_order]

def _QD실적차이_to_html(df) -> str:
    cols = df.columns.tolist()
    th_html = '<tr>'
    for c in cols:
        th_html += f'<th style="{_TH}; white-space: nowrap;">{c}</th>'
    th_html += '</tr>'

    body_html = ''
    for _, row in df.iterrows():
        is_total = str(row['구분']).strip() == "합계"
        tr_weight = 'font-weight: 700; color: black;' if is_total else ''
        
        body_html += f'<tr style="{tr_weight}">'
        for c in cols:
            val = row[c]
            if c == '구분':
                text, align = str(val), 'left'
            else:
                align = 'right'
                try: val = float(str(val).replace(',', ''))
                except: pass

                if pd.isna(val) or str(val).strip() == '':
                    text = ""
                else:
                    c_str = str(c)
                    if "금액" in c_str: divisor = 1000000.0
                    elif "단가" in c_str: divisor = 1.0
                    elif "중량" in c_str: divisor = 1000.0
                    else: divisor = 1.0

                    val_div = val / divisor
                    text = f"{abs(int(round(val_div))):,}"
                    if val_div < 0:
                        text = f'<span style="color:#d32f2f;">-{text}</span>'

            td_style = f'border: 1px solid #aaa; padding: 8px 16px; font-size: 15px; text-align: {align};'
            body_html += f'<td style="{td_style}">{text}</td>'
        body_html += '</tr>'

    return _html_table(th_html, body_html)

# ────────────────────────────────────────────────────────────────────────
# 공통 유틸 함수
# ────────────────────────────────────────────────────────────────────────
def _month_shift(y: int, m: int, delta: int):
    t = y * 12 + (m - 1) + delta
    return t // 12, t % 12 + 1

# ────────────────────────────────────────────────────────────────────────
# 3-1) 포스코 對 JFE 입고가격 Builder 
# ────────────────────────────────────────────────────────────────────────

def _build_포스코_JFE_입고가격_table(year: int, month: int):
    df = load_sheet(Sheets.포스코JFE입고가격_DB) 
    
    d = df.copy()
    d.columns = d.columns.str.strip()
    
    d["연도"] = pd.to_numeric(d["연도"], errors="coerce")
    d["월"] = pd.to_numeric(d["월"], errors="coerce")

    is_valid_g2 = d["구분2"].notna() & (d["구분2"].astype(str).str.strip() != "")
    d["kpi_src"] = np.where(is_valid_g2, d["구분2"], d["구분1"])

    def parse_kpi(s):
        if not isinstance(s, str): return "", "", ""
        s = s.strip()
        if s in ("포스코 할인단가(원)", "환율"): return "", s, ""
        if s == "차이": return np.nan, "차이", ""
        parts = s.split("_")
        if len(parts) == 1: return "", s, ""
        kind = parts[0]
        rest = parts[1:]
        if rest and rest[0] == "포스코":
            return kind, "포스코", "_".join(rest[1:]) if len(rest) > 1 else ""
        return kind, "JFE", "_".join(rest)

    kp = d["kpi_src"].astype(str).apply(parse_kpi)
    d["kind"] = kp.apply(lambda x: x[0])
    d["party"] = kp.apply(lambda x: x[1])
    d["item"] = kp.apply(lambda x: x[2])

    d = d.sort_values(["연도", "월", "구분3"])
    
    # [수정된 부분] groupby(["연도", "월"])를 사용하지 않고 위에서 아래로 빈칸 채우기
    # 월 값이 NaN인 '월평균' 데이터가 삭제되는 현상을 방지합니다.
    d["kind"] = d["kind"].replace("", np.nan).ffill().fillna("")

    frames_dict = {}
    col_order = []
    monthly_years = [year - 4, year - 3, year - 2, year - 1]
    
    d_base = d[d["구분3"] == "월평균"]
    for y in monthly_years:
        # 월평균 데이터는 연도로만 필터링
        dd = d_base[d_base["연도"] == y]
        cname = f"'{str(y)[-2:]}년 12월" if y == year - 1 else f"'{str(y)[-2:]}년 월평균"
        
        if cname not in col_order:
            col_order.append(cname)
        if not dd.empty and cname not in frames_dict:
            frames_dict[cname] = dd.pivot_table(index=["kind", "party", "item"], values="값", aggfunc="first").rename(columns={"값": cname})

    dyn = [_month_shift(year, month, -2), _month_shift(year, month, -1), (year, month)]
    for y, m in dyn:
        cname = f"'{str(y)[-2:]}년 {m}월"
        
        if cname not in col_order:
            col_order.append(cname)
        dd = d[(d["연도"] == y) & (d["월"] == m)]
        if not dd.empty and cname not in frames_dict:
            frames_dict[cname] = dd.pivot_table(index=["kind", "party", "item"], values="값", aggfunc="first").rename(columns={"값": cname})

    frames_list = [frames_dict[c] for c in col_order if c in frames_dict]
    wide = frames_list[0].join(frames_list[1:], how="outer") if frames_list else pd.DataFrame()
    
    for c in col_order:
        if c not in wide.columns: wide[c] = np.nan
    wide = wide.reset_index()

    def make_label(row):
        k, p, i = str(row["kind"]).strip(), str(row["party"]).strip(), str(row["item"]).strip()
        if p == "포스코 할인단가(원)": return "포스코 할인단가(원)"
        if p == "환율": return "환율"
        if p == "차이": return "탄소강_차이 ⓐ-ⓑ" if k == "탄소강" else "합금강_차이 ⓒ-ⓓ" if k == "합금강" else ""
        imap = {
            ("탄소강", "SWRCH45FS"): "탄소강_포스코_SWRCH45FS ⓐ",
            ("탄소강", "변동폭(천원/톤)"): "탄소강_포스코_SWRCH45FS_변동폭(천원/톤)",
            ("탄소강", "SWRCH45K-M"): "탄소강_JFE_SWRCH45K-M ⓑ",
            ("탄소강", "(USD)"): "탄소강_JFE_SWRCH45K-M(USD)",
            ("탄소강", "변동폭(USD/톤)"): "탄소강_JFE_SWRCH45K-M_변동폭(USD/톤)",
            ("합금강", "SCM435H Y73"): "합금강_포스코_SCM435H Y73 ⓒ",
            ("합금강", "변동폭(천원/톤)"): "합금강_포스코_SCM435H Y73_변동폭(천원/톤)",
            ("합금강", "SCM435H"): "합금강_JFE_SCM435H ⓓ",
            ("합금강", "(USD)"): "합금강_JFE_SCM435H_USD",
            ("합금강", "변동폭(USD/톤)"): "합금강_JFE_SCM435H_변동폭(USD/톤)",
        }
        return imap.get((k, i), "")

    if not wide.empty:
        wide["구분"] = wide.apply(make_label, axis=1)
        wide = wide.drop_duplicates(subset=["구분"], keep="last") 
        correct_order = [
            "포스코 할인단가(원)", "탄소강_포스코_SWRCH45FS ⓐ", "탄소강_포스코_SWRCH45FS_변동폭(천원/톤)",
            "탄소강_JFE_SWRCH45K-M ⓑ", "탄소강_JFE_SWRCH45K-M(USD)", "탄소강_JFE_SWRCH45K-M_변동폭(USD/톤)",
            "탄소강_차이 ⓐ-ⓑ", "합금강_포스코_SCM435H Y73 ⓒ", "합금강_포스코_SCM435H Y73_변동폭(천원/톤)",
            "합금강_JFE_SCM435H ⓓ", "합금강_JFE_SCM435H_USD", "합금강_JFE_SCM435H_변동폭(USD/톤)",
            "합금강_차이 ⓒ-ⓓ", "환율"
        ]
        wide = wide.set_index("구분").reindex(correct_order).reset_index()

    ordered_cols = ["구분"] + col_order
    return wide[ordered_cols] if not wide.empty else pd.DataFrame(columns=ordered_cols)

def _포스코_JFE_입고가격_to_html(df) -> str:
    cols = df.columns.tolist()
    th_html = '<tr>' + ''.join(f'<th style="{_TH}; white-space: nowrap;">{c}</th>' for c in cols) + '</tr>'

    body_html = ''
    lv0_items = ["포스코 할인단가(원)", "탄소강_포스코_SWRCH45FS ⓐ", "탄소강_JFE_SWRCH45K-M ⓑ", "탄소강_차이 ⓐ-ⓑ",
                 "합금강_포스코_SCM435H Y73 ⓒ", "합금강_JFE_SCM435H ⓓ", "합금강_차이 ⓒ-ⓓ", "환율"]

    for _, row in df.iterrows():
        body_html += '<tr>'
        
        # 현재 행이 '변동폭' 데이터인지 확인
        is_variance_row = "변동폭" in str(row['구분'])
        
        for c in cols:
            val = row[c]
            if c == '구분':
                pad = 0 if str(val).strip() in lv0_items else 16
                text = f'<span style="padding-left:{pad}px">{val}</span>'
                body_html += f'<td style="border: 1px solid #aaa; padding: 8px 16px; font-size: 15px; text-align: left; white-space: nowrap;">{text}</td>'
            else:
                # 데이터가 비어있는지 확인
                if pd.isna(val) or str(val).strip() == "":
                    text = ""
                else:
                    try:
                        f_val = float(val)
                        
                        # 변동폭 행일 경우 증감 아이콘 및 색상 처리
                        if is_variance_row:
                            if f_val > 0:
                                text = f'<span style="color:#1565C0;">▲ {f_val:,.1f}</span>'  # 파란색 상향
                            elif f_val < 0:
                                text = f'<span style="color:#C62828;">▼ {abs(f_val):,.1f}</span>' # 빨간색 하향
                            else:
                                text = "0.0"
                        else:
                            # 일반 수치형 데이터 (소수점 1자리, 천 단위 콤마)
                            text = f"{f_val:,.1f}"
                            
                    except ValueError:
                        # 숫자로 변환할 수 없는 예외적인 경우(텍스트 등) 그대로 출력
                        text = str(val)
                        
                body_html += f'<td style="{_TD_NUM}">{text}</td>'
        body_html += '</tr>'

    return _html_table(th_html, body_html)

# ────────────────────────────────────────────────────────────────────────
# 3-2) 포스코/JFE 투입비중 Builder 
# ────────────────────────────────────────────────────────────────────────

def _build_포스코_JFE_투입비중_table(year: int, month: int):
    df = load_sheet(Sheets.포스코JFE투입비중_DB)
    
    d = df.copy()
    # [수정] 엑셀 컬럼명에 포함된 보이지 않는 공백 제거 (KeyError: '연도' 방지)
    d.columns = d.columns.str.strip()
    
    d["연도"] = pd.to_numeric(d["연도"], errors="coerce")
    d["월"] = pd.to_numeric(d["월"], errors="coerce")
    
    def to_num(x):
        s = str(x).replace(",", "").strip()
        if s.endswith("%"): s = s[:-1]
        try: return float(s)
        except: return np.nan

    d["val"] = d["실적"].apply(to_num)
    
    is_valid_g2 = d["구분2"].notna() & (d["구분2"].astype(str).str.strip() != "")
    d["kpi_src"] = np.where(is_valid_g2, d["구분2"], d["구분1"])

    def split_kpi(v):
        p = str(v).split("_")
        return (p[0], p[1], p[2]) if len(p)==3 else (p[0], p[1], "") if len(p)==2 else (v, "", "")
        
    ks = d["kpi_src"].apply(split_kpi)
    d["kind"] = ks.apply(lambda x: x[0])
    d["sub"] = ks.apply(lambda x: x[1])
    d["metric"] = ks.apply(lambda x: x[2])
    
    single = ~d["kind"].isin(["탄소강", "합금강"])
    d.loc[single, "kind"] = ""
    d.loc[single, "sub"] = d.loc[single, "kpi_src"]

    frames_dict = {}
    col_order = []
    
    # ── 1. 과거 3개년 월평균 처리 로직 ──
    for y in [year - 3, year - 2, year - 1]:
        col = f"'{str(y)[-2:]}년 월평균"
        
        if col not in col_order:
            col_order.append(col)
            
        if y <= 2024:
            # [수정] 24년 이전 투입비중도 '월' 값이 비어있을 수 있으므로 연도로만 필터링
            dd = d[(d["구분3"] == "월평균") & (d["연도"] == y)]
            if not dd.empty and col not in frames_dict:
                frames_dict[col] = dd.pivot_table(index=["kind", "sub", "metric"], values="val", aggfunc="first").rename(columns={"val": col})
        else:
            # 25년 이후: '당월' 실적들을 묶어서 평균(mean) 자동 계산
            dd = d[(d["구분3"] == "당월") & (d["연도"] == y)]
            if not dd.empty and col not in frames_dict:
                frames_dict[col] = dd.pivot_table(index=["kind", "sub", "metric"], values="val", aggfunc="mean").rename(columns={"val": col})

    # ── 2. 최근 4개월 당월 처리 로직 ──
    for i in range(3, -1, -1):
        y, m = _month_shift(year, month, -i)
        col = f"'{str(y)[-2:]}년 {m}월"
        dd = d[(d["연도"] == y) & (d["월"] == m)]
        
        if col not in col_order:
            col_order.append(col)
        if not dd.empty and col not in frames_dict:
            frames_dict[col] = dd.pivot_table(index=["kind", "sub", "metric"], values="val", aggfunc="first").rename(columns={"val": col})

    frames_list = [frames_dict[c] for c in col_order if c in frames_dict]
    wide = frames_list[0].join(frames_list[1:], how="outer") if frames_list else pd.DataFrame()
    
    if not wide.empty:
        for k in ["탄소강", "합금강"]:
            for m_type in ["중량", "비중"]:
                for sub_p in ["포스코", "JFE"]:
                    if (k, sub_p, m_type) not in wide.index: wide.loc[(k, sub_p, m_type), :] = np.nan
            for c in wide.columns:
                pw = wide.loc[(k, "포스코", "중량"), c] if (k, "포스코", "중량") in wide.index else np.nan
                jw = wide.loc[(k, "JFE", "중량"), c] if (k, "JFE", "중량") in wide.index else np.nan
                denom = (0 if pd.isna(pw) else pw) + (0 if pd.isna(jw) else jw)
                if denom > 0:
                    wide.loc[(k, "포스코", "비중"), c] = pw / denom * 100.0
                    wide.loc[(k, "JFE", "비중"), c] = jw / denom * 100.0
    
        jfe_share = {}
        for c in wide.columns:
            jw = sum(wide.loc[(k, "JFE", "중량"), c] for k in ["탄소강", "합금강"] if (k, "JFE", "중량") in wide.index and pd.notna(wide.loc[(k, "JFE", "중량"), c]))
            pw = sum(wide.loc[(k, "포스코", "중량"), c] for k in ["탄소강", "합금강"] if (k, "포스코", "중량") in wide.index and pd.notna(wide.loc[(k, "포스코", "중량"), c]))
            denom = jw + pw
            jfe_share[c] = jw / denom * 100.0 if denom > 0 else np.nan
            
        wide.loc[("", "JFE 사용비중", "비중"), :] = pd.Series(jfe_share)

        wide = wide.reset_index()
        
        def make_label(row):
            k, s, m = str(row.get("kind", "")), str(row.get("sub", "")), str(row.get("metric", ""))
            if s == "JFE 사용비중": return "JFE 사용비중"
            if s == "전월(전년)대비 손익영향 금액": return "전월(전년)대비 손익영향 금액"
            if s == "평균단가": return f"{k}_평균단가"
            return f"{k}_{s}_{m}"
        
        wide["구분"] = wide.apply(make_label, axis=1)
        wide = wide.drop_duplicates(subset=["구분"], keep="last") 
        
        correct_order = [
            "탄소강_포스코_중량", "탄소강_포스코_비중", "탄소강_JFE_중량", "탄소강_JFE_비중", "탄소강_평균단가",
            "합금강_포스코_중량", "합금강_포스코_비중", "합금강_JFE_중량", "합금강_JFE_비중", "합금강_평균단가",
            "JFE 사용비중", "전월(전년)대비 손익영향 금액"
        ]
        wide = wide.set_index("구분").reindex(correct_order).reset_index()

    ordered_cols = ["구분"] + col_order
    return wide[ordered_cols] if not wide.empty else pd.DataFrame(columns=ordered_cols)

def _포스코_JFE_투입비중_to_html(df) -> str:
    cols = df.columns.tolist()
    th_html = '<tr>' + ''.join(f'<th style="{_TH}; white-space: nowrap;">{c}</th>' for c in cols) + '</tr>'

    body_html = ''
    lv0_items = ["탄소강_평균단가", "합금강_평균단가", "JFE 사용비중", "전월(전년)대비 손익영향 금액"]

    for _, row in df.iterrows():
        body_html += '<tr>'
        for c in cols:
            val = row[c]
            if c == '구분':
                pad = 0 if str(val).strip() in lv0_items else 16
                text = f'<span style="padding-left:{pad}px">{val}</span>'
                body_html += f'<td style="border: 1px solid #aaa; padding: 8px 16px; font-size: 15px; text-align: left; white-space: nowrap;">{text}</td>'
            else:
                if pd.isna(val): 
                    text = ""
                else:
                    is_pct = "비중" in str(row["구분"])
                    if is_pct:
                        v_str = f"{abs(val):.1f}%"
                    else:
                        v_str = f"{abs(int(round(val))):,}"
                    
                    if val < 0:
                        text = f'<span style="color:#d32f2f;">-{v_str}</span>'
                    else:
                        text = v_str
                body_html += f'<td style="{_TD_NUM}">{text}</td>'
        body_html += '</tr>'

    return _html_table(th_html, body_html)


# ────────────────────────────────────────────────────────────────────────
# 3-3) 메이커별 입고추이 Builder 
# ────────────────────────────────────────────────────────────────────────

def _build_메이커별_입고추이_table(year: int, month: int):
    df = load_sheet(Sheets.메이커별입고추이_DB)
    
    d = df.copy()
    d["연도"] = pd.to_numeric(d["연도"], errors="coerce")
    d["월"] = pd.to_numeric(d["월"], errors="coerce")
    d["값"] = pd.to_numeric(d["값"].astype(str).str.replace(",", ""), errors="coerce")

    # [수정] 구분1이 메이커명, 구분2가 중량/금액 지표
    w = d[d["구분2"] == "중량"].pivot_table(index="구분1", columns=["연도", "월"], values="값", aggfunc="sum")
    a = d[d["구분2"] == "금액"].pivot_table(index="구분1", columns=["연도", "월"], values="값", aggfunc="sum")

    base_year = year - 1
    makers = ["포스코", "JFE", "세아창원특수강", "현대제철", "세아베스틸"]
    tail = sorted([m for m in d["구분1"].dropna().unique() if m not in makers])
    makers += tail

    def get_avg(piv, y, m_end=12):
        if piv.empty: return pd.Series(index=makers, dtype=float)
        mask = (piv.columns.get_level_values(0) == y) & (piv.columns.get_level_values(1) <= m_end)
        return piv.loc[:, mask].mean(axis=1) if mask.any() else pd.Series(index=makers, dtype=float)

    def get_val(piv, y, m):
        if piv.empty or (y, m) not in piv.columns: return pd.Series(index=makers, dtype=float)
        return piv[(y, m)]

    bw = get_avg(w, base_year).reindex(makers)
    ba = get_avg(a, base_year).reindex(makers)
    sw = get_avg(w, year, month).reindex(makers)
    sa = get_avg(a, year, month).reindex(makers)

    prev_y, prev_m = _month_shift(year, month, -1)
    prev2_y, prev2_m = _month_shift(year, month, -2)
    prev3_y, prev3_m = _month_shift(year, month, -3)

    pw, pa = get_val(w, prev_y, prev_m), get_val(a, prev_y, prev_m)
    p2w, p2a = get_val(w, prev2_y, prev2_m), get_val(a, prev2_y, prev2_m)
    p3w, p3a = get_val(w, prev3_y, prev3_m), get_val(a, prev3_y, prev3_m)

    def calc_price(amt, wgt):
        wgt = wgt.where(wgt > 0)
        return (amt / wgt) * 1000.0

    def calc_share(wgt):
        tot = wgt.sum()
        return (wgt / tot * 100.0) if tot > 0 else wgt * 0

    diff_p2 = calc_price(p2a, p2w) - calc_price(p3a, p3w)
    diff_p1 = calc_price(pa, pw) - calc_price(p2a, p2w)

    rows = []
    for mk in makers:
        rows.append({"구분": f"{mk}_중량", 
                     f"'{str(base_year)[-2:]}년 월평균": bw.get(mk), f"'{str(base_year)[-2:]}년 매입비중": calc_share(bw).get(mk),
                     f"'{str(prev2_y)[-2:]}년 {prev2_m}월": p2w.get(mk), f"'{str(prev2_y)[-2:]}년 {prev2_m}월 매입비중": calc_share(p2w).get(mk),
                     f"'{str(prev_y)[-2:]}년 {prev_m}월": pw.get(mk), f"'{str(prev_y)[-2:]}년 {prev_m}월 매입비중": calc_share(pw).get(mk),
                     f"'{str(year)[-2:]}년 월평균": sw.get(mk), f"'{str(year)[-2:]}년 매입비중": calc_share(sw).get(mk)})
        rows.append({"구분": f"{mk}_단가", 
                     f"'{str(base_year)[-2:]}년 월평균": calc_price(ba, bw).get(mk), f"'{str(base_year)[-2:]}년 매입비중": np.nan,
                     f"'{str(prev2_y)[-2:]}년 {prev2_m}월": calc_price(p2a, p2w).get(mk), f"'{str(prev2_y)[-2:]}년 {prev2_m}월 매입비중": np.nan,
                     f"'{str(prev_y)[-2:]}년 {prev_m}월": calc_price(pa, pw).get(mk), f"'{str(prev_y)[-2:]}년 {prev_m}월 매입비중": np.nan,
                     f"'{str(year)[-2:]}년 월평균": calc_price(sa, sw).get(mk), f"'{str(year)[-2:]}년 매입비중": np.nan})
        rows.append({"구분": f"{mk}_증감", 
                     f"'{str(base_year)[-2:]}년 월평균": np.nan, f"'{str(base_year)[-2:]}년 매입비중": np.nan,
                     f"'{str(prev2_y)[-2:]}년 {prev2_m}월": diff_p2.get(mk), f"'{str(prev2_y)[-2:]}년 {prev2_m}월 매입비중": np.nan,
                     f"'{str(prev_y)[-2:]}년 {prev_m}월": diff_p1.get(mk), f"'{str(prev_y)[-2:]}년 {prev_m}월 매입비중": np.nan,
                     f"'{str(year)[-2:]}년 월평균": np.nan, f"'{str(year)[-2:]}년 매입비중": np.nan})
        
    return pd.DataFrame(rows)

def _메이커별_입고추이_to_html(df) -> str:
    cols = df.columns.tolist()
    th_html = '<tr>' + ''.join(f'<th style="{_TH}; white-space: nowrap;">{c}</th>' for c in cols) + '</tr>'

    body_html = ''
    for _, row in df.iterrows():
        body_html += '<tr>'
        for c in cols:
            val = row[c]
            if c == '구분':
                body_html += f'<td style="border: 1px solid #aaa; padding: 8px 16px; font-size: 15px; text-align: left; white-space: nowrap;">{val}</td>'
            else:
                if pd.isna(val) or val == "":
                    text = ""
                else:
                    v = float(val)
                    if "매입비중" in c:
                        text = f"{v:.1f}%"
                    elif "증감" in str(row["구분"]):
                        iv = int(round(v / 1000))
                        if iv > 0: text = f'<span style="color:#1565C0;">▲ {iv:,}</span>'
                        elif iv < 0: text = f'<span style="color:#C62828;">▼ {abs(iv):,}</span>'
                        else: text = "0"
                    else:
                        text = f"{int(round(v / 1000)):,}"
                        
                body_html += f'<td style="{_TD_NUM}">{text}</td>'
        body_html += '</tr>'

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

            # 1. 표 데이터 및 HTML 생성
            df_table = _build_손익요약표_table(year, month)
            html = _손익요약표_to_html_table(df_table)
            
            # 2. 구글 시트에서 해당 연/월의 메모 가져오기
            # (주의: Sheets.손익요약표_메모 부분은 config.py에 정의된 Enum 명칭에 맞게 사용해주세요)
            memo = _get_memo(Sheets.손익요약표_메모, year, month)
            
            # 3. 레이아웃에 memo 인자 추가하여 렌더링
            app.markdown(_layout100("손익요약표", html, memo=memo, unit="[단위: 백만원]"), unsafe_allow_html=True)

        app.If(lambda: True, _render_손익요약)

        
    with tabs[1]:
        def _render_차이():
            year, month = int(year_state.value), int(month_state.value)
            
            # 1) 전월대비 손익차이
            app.markdown("<h4>1) 전월대비 손익차이 </h4>", unsafe_allow_html=True)
            app.markdown("<div style='text-align:right; font-size:13px; color:#666;'>[단위: 백만원]</div><hr/>", unsafe_allow_html=True)

            # 2) 수출 환율 차이
            try:
                df_fx, prev_lab, curr_lab = _build_수출환율차이_table(year, month)
                html_fx = _수출환율차이_to_html(df_fx, prev_lab, curr_lab)
                memo_fx = _get_memo(Sheets.수출환율차이_메모, year, month)
                
                app.markdown(
                    _layout100("2) 수출 환율 차이", html_fx, memo=memo_fx, unit="[단위: 톤, 천원, 천단위(외화)]"), 
                    unsafe_allow_html=True
                )
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>수출 환율 차이 생성 중 오류: {e}</p>", unsafe_allow_html=True)

            # 3) QD 실적 차이
            try:
                df_qd = _build_QD실적차이_table(year, month)
                html_qd = _QD실적차이_to_html(df_qd)
                
                app.markdown(
                    _layout100("3) QD 실적 차이", html_qd, unit="[단위: 톤, 천원, 백만원]"), 
                    unsafe_allow_html=True
                )
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>QD 실적 차이 생성 중 오류: {e}</p>", unsafe_allow_html=True)

        app.If(lambda: True, _render_차이)

    with tabs[2]:
        def _render_원재료():
            year, month = int(year_state.value), int(month_state.value)

            # 1) 포스코 對 JFE 입고가격
            try:
                df1 = _build_포스코_JFE_입고가격_table(year, month)
                html1 = _포스코_JFE_입고가격_to_html(df1)
                memo1 = _get_memo(Sheets.포스코JFE입고가격_메모, year, month) # config.py 설정 명칭에 맞게 변경 필요
                app.markdown(_layout64("1) 포스코 對 JFE 입고가격", html1, memo=memo1, unit="[단위: 천원/톤]"), unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>포스코 對 JFE 입고가격 생성 오류: {e}</p>", unsafe_allow_html=True)
            
            app.markdown("<hr/>", unsafe_allow_html=True)

            # 2) 포스코/JFE 투입비중
            try:
                df2 = _build_포스코_JFE_투입비중_table(year, month)
                html2 = _포스코_JFE_투입비중_to_html(df2)
                memo2 = _get_memo(Sheets.포스코JFE투입비중_메모, year, month)
                app.markdown(_layout64("2) 포스코/JFE 투입비중", html2, memo=memo2, unit="[단위: 백만원, 톤]"), unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>포스코/JFE 투입비중 생성 오류: {e}</p>", unsafe_allow_html=True)

            app.markdown("<hr/>", unsafe_allow_html=True)

            # 3) 메이커별 입고추이
            try:
                df3 = _build_메이커별_입고추이_table(year, month)
                html3 = _메이커별_입고추이_to_html(df3)
                memo3 = _get_memo(Sheets.메이커별입고추이_메모, year, month)
                app.markdown(_layout64("3) 메이커별 입고추이", html3, memo=memo3, unit="[단위: 톤, 톤/천원]"), unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>메이커별 입고추이 생성 오류: {e}</p>", unsafe_allow_html=True)

        app.If(lambda: True, _render_원재료)

'''    
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
