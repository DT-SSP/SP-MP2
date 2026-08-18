import datetime
import pandas as pd
from data.loader_local import load_sheet
from data.config import (
    Sheets,
    SONIK2_매출액_순서, SONIK2_판매량_순서, SONIK2_매출원가_순서, SONIK2_판관비_순서,
)
from views.common import (
    parse as _parse, fmt as _fmt,
    prev_month as _prev, drop_empty as _drop_empty, sort_by_order as _sort,
    TH as _TH, TD_NUM as _TD_NUM, TD_RED as _TD_RED, C_RED as _C_RED,
    ROW_SEC, ROW_GRP, ROW_HDR_LBL, ROW_HDR_NUM, ROW_HDR_RED, C_NAVY as _C_NAVY,
    ROW_CAL_LBL, ROW_CAL_NUM, ROW_CAL_RED, ROW_ITEM, C_LT_GRAY as _C_LT_GRAY, TD_LBL as _TD_LBL,
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
        
        # '년도' 컬럼이 존재할 경우 '연도'로 이름 변경하여 일관성 유지
        if '년도' in df.columns:
            df.rename(columns={'년도': '연도'}, inplace=True)
            
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
        "제품 등": ("매출액", "제품등"),
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
        ("매출액", 0), ("제품 등", 1), ("부산물", 1),
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
    col_pm = f"'{str(prev_year)[-2:]}.{pm}월"
    col_m = f"'{str(year)[-2:]}.{m}월"
    col_pm_pln = f"'{str(prev_year)[-2:]}.{pm}월 계획"
    col_m_pln = f"'{str(year)[-2:]}.{m}월 계획"
    cols_num = [col_23, col_24, col_pm, col_m, "전월대비", col_pm_pln, col_m_pln, "계획대비", "누적"]

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
            row['누적'] = get_val(year, m, label, is_acc=True)
            
            row['전월대비'] = row[col_m] - row[col_pm] if pd.notna(row[col_m]) and pd.notna(row[col_pm]) else np.nan
            row['계획대비'] = row[col_m] - row[col_m_pln] if pd.notna(row[col_m]) and pd.notna(row[col_m_pln]) else np.nan
            
        rows.append(row)
        
    out = pd.DataFrame(rows)

    # 7. 퍼센트 계산
    def pct(num, den):
        if pd.isna(num) or pd.isna(den) or den == 0: return np.nan
        return (num / den) * 100.0

    calc_cols = [col_23, col_24, col_pm, col_m, col_pm_pln, col_m_pln, '누적']
    for c in calc_cols:
        sales_val = out.loc[out['구분'] == '매출액', c].values[0]
        gp_val = out.loc[out['구분'] == '매출이익', c].values[0]
        op_val = out.loc[out['구분'] == '영업이익', c].values[0]
        
        out.loc[out['구분'] == '매출이익(%)', c] = pct(gp_val, sales_val)
        out.loc[out['구분'] == '영업이익(%)', c] = pct(op_val, sales_val)

    # [추가] % 항목의 전월대비, 계획대비 차이(%p) 계산
    for pct_label in ['매출이익(%)', '영업이익(%)']:
        m_val = out.loc[out['구분'] == pct_label, col_m].values[0]
        pm_val = out.loc[out['구분'] == pct_label, col_pm].values[0]
        m_pln_val = out.loc[out['구분'] == pct_label, col_m_pln].values[0]
        
        out.loc[out['구분'] == pct_label, '전월대비'] = m_val - pm_val if pd.notna(m_val) and pd.notna(pm_val) else np.nan
        out.loc[out['구분'] == pct_label, '계획대비'] = m_val - m_pln_val if pd.notna(m_val) and pd.notna(m_pln_val) else np.nan

    # 8. 포맷팅 및 서식 적용 (타입 에러 방지)
    def fmt_amt(x):
        if pd.isna(x): return ""
        try: v = float(x)
        except: return str(x)
        if v < 0: return f'<span style="color:#d32f2f;">-{abs(int(round(v))):,}</span>'
        return f"{int(round(v)):,}"

    # [수정] 일반 % 서식
    def fmt_pct(x):
        if pd.isna(x): return ""
        try: v = float(x)
        except: return str(x)
        if v < 0: return f'<span style="color:#d32f2f;">-{abs(v):,.1f}%</span>'
        return f"{v:,.1f}%"
        
    # [추가] 전월대비, 계획대비용 %p 서식
    def fmt_pct_diff(x):
        if pd.isna(x): return ""
        try: 
            v = float(x)
        except: 
            return ""  # 숫자로 변환할 수 없는 경우 빈 문자열 반환 (필요에 따라 return str(x)로 변경 가능)
            
        if v is None: return ""
        if v > 0: return f"↑{v:.1f}%p"
        if v < 0: return f"↓{abs(v):.1f}%p"
        return f"{v:.1f}%p"

    out[cols_num] = out[cols_num].astype(object)

    pct_mask = out["구분"].astype(str).str.endswith("(%)")
    for c in cols_num:
        out.loc[~pct_mask, c] = out.loc[~pct_mask, c].apply(fmt_amt)
        # [추가] 전월대비와 계획대비 열에는 %p 포맷 적용, 그 외는 % 적용
        if c in ['전월대비', '계획대비']:
            out.loc[pct_mask, c] = out.loc[pct_mask, c].apply(fmt_pct_diff)
        else:
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

        # 1. 기본 표시 라벨 치환 (%)
        if label in ["매출이익(%)", "영업이익(%)"]:
            display_label = "(%)"
        else:
            display_label = label

        depth = row.get('_depth', 0)
        is_bold = row.get('_bold', False)
        
        # 2. [추가] depth가 1인 경우, 라벨 텍스트 맨 앞에 띄어쓰기 한 칸(&nbsp;) 추가
        if depth == 1:
            display_label = f"&nbsp;{display_label}"
        
        style_label = ROW_HDR_LBL if is_bold else ROW_ITEM
        style_num = ROW_HDR_NUM if is_bold else _TD_NUM
        
        # (참고: padding-left는 전체적인 들여쓰기 여백을 잡아줍니다)
        padding = depth * 16
        cells = f'<td style="{style_label}; padding-left:{padding}px;">{display_label}</td>' 
        
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

            td_style = f'border: 1px solid #aaa; padding: 6px 8px; font-size: 14px; text-align: {align}; {border_st}'
            body_html += f'<td style="{td_style}">{text}</td>'
        body_html += '</tr>'

    return _html_table(th_html, body_html)


# ────────────────────────────────────────────────────────────────────────
# 2-1) 전월대비 손익차이 Builder & HTML Renderer (p9_해외법인.py의 로직을 그대로 이식)
# ────────────────────────────────────────────────────────────────────────

def _build_손익차이_table(year, month):
    df = load_sheet(Sheets.전월대비손익차이_DB)

    if df.empty or '연도' not in df.columns:
        return pd.DataFrame(columns=['구분', '_depth', '소계', '영업', '생산', '구매', '기타'])

    df.columns = df.columns.str.strip()
    df['값'] = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    df = df[(df['연도'] == year) & (df['월'] == month)]

    for c in ['구분1', '구분2', '구분3', '구분4']:
        df[c] = df[c].fillna('').astype(str).str.strip()

    g4_cols = ['영업', '생산', '구매', '기타']

    def get_val(g1, g2, g3, g4):
        mask = (df['구분1'] == g1) & (df['구분2'] == g2) & (df['구분3'] == g3) & (df['구분4'] == g4)
        return df[mask]['값'].sum()

    # 매출이익차이(총) — 제품수불차이(수량/판가/원가) + 기타차이로 구성
    gross_vals   = [get_val('매출이익차이', '',        '',     g4) for g4 in g4_cols]
    qty_vals     = [get_val('매출이익차이', '제품수불차이', '수량차이', g4) for g4 in g4_cols]
    price_vals   = [get_val('매출이익차이', '제품수불차이', '판가차이', g4) for g4 in g4_cols]
    cost_vals    = [get_val('매출이익차이', '제품수불차이', '원가차이', g4) for g4 in g4_cols]

    supply_vals  = [q + p + c for q, p, c in zip(qty_vals, price_vals, cost_vals)]
    etc_vals     = [get_val('매출이익차이', '기타차이',   '',     g4) for g4 in g4_cols]

    # 매출이익차이 = 제품수불차이 + 기타차이
    gross_vals   = [s + e for s, e in zip(supply_vals, etc_vals)] 

    sgna_vals = [get_val('판매비와관리비차이', '', '', g4) for g4 in g4_cols]
    # 영업이익차이 = 매출이익차이 + 판매비와관리비차이
    op_diff_vals = [g + s for g, s in zip(gross_vals, sgna_vals)]

    def format_row(label, depth, vals):
        # 소계 : 각 분류별 금액의 합산임 (영업+생산+구매+기타)
        total = sum(vals)
        return {
            '구분':   label,
            '_depth': depth,
            '소계':   _fmt(total),
            '영업':   _fmt(vals[0]),
            '생산':   _fmt(vals[1]),
            '구매':   _fmt(vals[2]),
            '기타':   _fmt(vals[3]),
        }

    rows = [
        format_row('매출이익차이',      0, gross_vals),
        format_row('제품수불차이',      1, supply_vals),
        format_row('수량차이',          2, qty_vals),
        format_row('판가차이',          2, price_vals),
        format_row('원가차이',          2, cost_vals),
        format_row('기타차이',          1, etc_vals),
        format_row('판매비와관리비 차이', 0, sgna_vals),
        format_row('영업이익 차이',      0, op_diff_vals),
    ]

    return pd.DataFrame(rows, columns=['구분', '_depth', '소계', '영업', '생산', '구매', '기타'])


def _손익차이_to_html_table(df):
    if df.empty:
        return ""

    depths = df['_depth'].tolist() if '_depth' in df.columns else [0] * len(df)
    render_df = df.drop(columns=['_depth'], errors='ignore')

    rows_html = ''
    for (_, row), depth in zip(render_df.iterrows(), depths):
        label = str(row.iloc[0])

        is_highlight = label in ['매출이익차이', '영업이익 차이']
        
        # 하이라이트 행 배경색 및 폰트 두께 설정
        bg = f';background:{_C_LT_GRAY}' if is_highlight else ''
        fw = 'font-weight:700;' if is_highlight else ''

        indent = '&nbsp;&nbsp;&nbsp;&nbsp;' * depth

        cells = ''
        for i, val in enumerate(row):
            s = str(val)
            if i == 0:
                # 구분 셀: _TD_LBL 스타일 적용
                cells += f'<td style="{_TD_LBL}{bg};{fw}">{indent}{s}</td>'
            else:
                # 숫자 셀: 음수일 경우 _TD_RED, 일반은 _TD_NUM 스타일 적용
                base_style = _TD_RED if s.startswith('-') else _TD_NUM
                cells += f'<td style="{base_style}{bg};{fw}">{s}</td>'

        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'

    # 헤더: _TH 스타일 적용 (white-space 및 text-align 보장)
    headers = ''.join(f'<th style="{_TH}; white-space: nowrap;">{c}</th>' for c in render_df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)

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
        
        # 전월 (구분2 == "실적" 으로 필터링)
        prev_qty = df_prev[(df_prev["구분1"] == company) & (df_prev["구분2"] == "실적") & (df_prev["구분3"] == "중량")]["값"].sum()
        prev_amt = df_prev[(df_prev["구분1"] == company) & (df_prev["구분2"] == "실적") & (df_prev["구분3"] == "금액")]["값"].sum()
        prev_price = prev_amt / prev_qty if prev_qty != 0 else 0
        
        # 당월 (구분2 == "실적" 으로 필터링)
        curr_qty = df_curr[(df_curr["구분1"] == company) & (df_curr["구분2"] == "실적") & (df_curr["구분3"] == "중량")]["값"].sum()
        curr_amt = df_curr[(df_curr["구분1"] == company) & (df_curr["구분2"] == "실적") & (df_curr["구분3"] == "금액")]["값"].sum()
        curr_price = curr_amt / curr_qty if curr_qty != 0 else 0

        # 단가차이 (구분2 == "단가차이" 시트 데이터 직접 조회)
        diff_qty = df_curr[(df_curr["구분1"] == company) & (df_curr["구분2"] == "단가차이") & (df_curr["구분3"] == "중량")]["값"].sum()
        diff_amt = df_curr[(df_curr["구분1"] == company) & (df_curr["구분2"] == "단가차이") & (df_curr["구분3"] == "금액")]["값"].sum()
        
        # [수정] 단가차이의 단가를 금액 / 중량 * 1000으로 계산
        if diff_qty != 0:
            diff_price = (diff_amt / diff_qty) * 1000.0
        else:
            diff_price = 0

        # 데이터 추가
        row_data.update({
            f"{prev_label} 중량": prev_qty, f"{prev_label} 단가": prev_price, f"{prev_label} 금액": prev_amt,
            f"{curr_label} 중량": curr_qty, f"{curr_label} 단가": curr_price, f"{curr_label} 금액": curr_amt,
            "단가차이 중량": diff_qty/1000, "단가차이 단가": diff_price, "단가차이 금액": diff_amt
        })
        result_rows.append(row_data)

    # 합계 행
    total_row = {"구분": "합계"}
    for col in result_rows[0].keys():
        if col != "구분": total_row[col] = sum(row.get(col, 0) for row in result_rows)
        
    tot_prev_qty = total_row.get(f"{prev_label} 중량", 0)
    tot_prev_amt = total_row.get(f"{prev_label} 금액", 0)
    total_row[f"{prev_label} 단가"] = (tot_prev_amt / tot_prev_qty) if tot_prev_qty != 0 else 0
    
    tot_curr_qty = total_row.get(f"{curr_label} 중량", 0)
    tot_curr_amt = total_row.get(f"{curr_label} 금액", 0)
    total_row[f"{curr_label} 단가"] = (tot_curr_amt / tot_curr_qty) if tot_curr_qty != 0 else 0
    
    # [수정] 합계 행의 단가 차이도 새로 계산된 (금액 / 중량) * 1000 로직 적용
    # (주의: 저장된 단가차이 중량은 이미 / 1000 처리가 되어 있으므로 원복해서 계산)
    tot_diff_qty_original = total_row.get("단가차이 중량", 0) * 1000.0
    tot_diff_amt = total_row.get("단가차이 금액", 0)
    
    if tot_diff_qty_original != 0:
        total_row["단가차이 단가"] = (tot_diff_amt / tot_diff_qty_original) * 1000.0
    else:
        total_row["단가차이 단가"] = 0
    
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
                    
                    # [수정] 단가차이 단가 컬럼은 1000으로 나누고 소수점 첫째 자리 반올림
                    if c_str == "단가차이 단가":
                        val_div = val / 1000.0
                        text = f"{abs(val_div):,.1f}"
                    else:
                        if "금액" in c_str: divisor = 1000000.0
                        elif "단가" in c_str: divisor = 1.0
                        elif "중량" in c_str: divisor = 1000.0
                        else: divisor = 1.0

                        val_div = val / divisor
                        text = f"{abs(int(round(val_div))):,}"
                        
                    # 음수일 경우 붉은색 서식 적용
                    if val_div < 0:
                        text = f'<span style="color:#d32f2f;">-{text}</span>'

            td_style = f'border: 1px solid #aaa; padding: 6px 8px; font-size: 14px; text-align: {align};'
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
    d["kind"] = d["kind"].replace("", np.nan).ffill().fillna("")

    frames_dict = {}
    col_order = []
    monthly_years = [year - 3, year - 2, year - 1]
    
    d_base = d[d["구분3"] == "월평균"]
    for y in monthly_years:
        dd = d_base[d_base["연도"] == y]
        cname = f"'{str(y)[-2:]}.평균"
        
        if cname not in col_order:
            col_order.append(cname)
        if not dd.empty and cname not in frames_dict:
            frames_dict[cname] = dd.pivot_table(index=["kind", "party", "item"], values="값", aggfunc="first").rename(columns={"값": cname})

    dyn = [_month_shift(year, month, -2), _month_shift(year, month, -1), (year, month)]
    for y, m in dyn:
        cname = f"'{str(y)[-2:]}.{m}월"
        
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
        if p == "JFE 입고 환율": return "환율"
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
        
        # [수정] 이미지와 완전히 동일한 배치를 위한 순서 재정의 (환율 위치 상단으로 이동)
        correct_order = [
            "포스코 할인단가(원)", 
            "환율",
            "탄소강_포스코_SWRCH45FS ⓐ", 
            "탄소강_포스코_SWRCH45FS_변동폭(천원/톤)",
            "탄소강_JFE_SWRCH45K-M ⓑ", 
            "탄소강_JFE_SWRCH45K-M(USD)", 
            "탄소강_JFE_SWRCH45K-M_변동폭(USD/톤)",
            "탄소강_차이 ⓐ-ⓑ", 
            "합금강_포스코_SCM435H Y73 ⓒ", 
            "합금강_포스코_SCM435H Y73_변동폭(천원/톤)",
            "합금강_JFE_SCM435H ⓓ", 
            "합금강_JFE_SCM435H_USD", 
            "합금강_JFE_SCM435H_변동폭(USD/톤)",
            "합금강_차이 ⓒ-ⓓ"
        ]
        wide = wide.set_index("구분").reindex(correct_order).reset_index()

    ordered_cols = ["구분"] + col_order
    return wide[ordered_cols] if not wide.empty else pd.DataFrame(columns=ordered_cols)

def _포스코_JFE_입고가격_to_html(df) -> str:
    cols = df.columns.tolist()
    th_html = '<tr>' + ''.join(f'<th style="{_TH}; white-space: nowrap;">{c}</th>' for c in cols) + '</tr>'

    body_html = ''
    
    # 1. 배경색(연보라/회색)이 들어갈 항목
    bg_items = [
        "탄소강_포스코_SWRCH45FS ⓐ", 
        "탄소강_JFE_SWRCH45K-M ⓑ", 
        "탄소강_JFE_SWRCH45K-M_변동폭(USD/톤)",
        "합금강_포스코_SCM435H Y73 ⓒ", 
        "합금강_JFE_SCM435H ⓓ", 
        "합금강_JFE_SCM435H_변동폭(USD/톤)"
    ]
    
    # 2. 공백(빈 줄)을 추가할 기준 항목
    spacer_after = ["환율", "탄소강_차이 ⓐ-ⓑ"]
    
    # 3. 블록별 구분을 위해 위/아래 굵은 테두리 선을 추가할 항목
    thick_top = ["포스코 할인단가(원)", "탄소강_포스코_SWRCH45FS ⓐ", "합금강_포스코_SCM435H Y73 ⓒ"]
    thick_bottom = ["환율", "탄소강_차이 ⓐ-ⓑ", "합금강_차이 ⓒ-ⓓ"]

    for _, row in df.iterrows():
        label = str(row['구분']).strip()
        is_variance_row = "변동폭" in label
        
        # 교차 배경색 지정
        bg_color = "#F2F2FA" if label in bg_items else "#FFFFFF"
        
        # 테두리 굵기 지정
        border_top = "2px solid #555" if label in thick_top else "1px solid #d3d3d3"
        border_bottom = "2px solid #555" if label in thick_bottom else "1px solid #d3d3d3"
        
        body_html += f'<tr style="background-color: {bg_color};">'
        
        for c in cols:
            val = row[c]
            
            # 셀 기본 테두리 및 여백 설정
            td_base_style = f'border: 1px solid #d3d3d3; border-top: {border_top}; border-bottom: {border_bottom}; padding: 6px 8px; font-size: 14px; white-space: nowrap;'

            if c == '구분':
                td_style = f'{td_base_style} text-align: left;'
                body_html += f'<td style="{td_style}">{label}</td>'
            else:
                if pd.isna(val) or str(val).strip() == "":
                    text = ""
                else:
                    try:
                        f_val = float(val)
                        if is_variance_row:
                            if f_val > 0:
                                text = f'↑{f_val:,.0f}'
                            elif f_val < 0:
                                text = f'↓{abs(f_val):,.0f}'
                            else:
                                text = "↑0"
                        else:
                            text = f"{f_val:,.0f}"
                    except ValueError:
                        text = str(val)
                        
                num_td_style = f'{_TD_NUM}; {td_base_style} text-align: right;'
                body_html += f'<td style="{num_td_style}">{text}</td>'
        body_html += '</tr>'
        
        # 해당 블록이 끝난 후 공백 행(Spacer) 삽입
        if label in spacer_after:
            body_html += f'<tr><td colspan="{len(cols)}" style="height: 18px; border: none; background-color: #ffffff;"></td></tr>'

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

    val_col = "값" if "값" in d.columns else "실적"
    d["val"] = d[val_col].apply(to_num)
    
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
        col = f"'{str(y)[-2:]}.평균"
        
        if col not in col_order:
            col_order.append(col)
            
        if y <= 2025:
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
        col = f"'{str(y)[-2:]}.{m}월"
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

    # 구분1이 메이커명, 구분2가 중량/금액 지표
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

    # 당월 (curr)
    cw, ca = get_val(w, year, month), get_val(a, year, month)
    # 전월 (prev)
    pw, pa = get_val(w, prev_y, prev_m), get_val(a, prev_y, prev_m)
    # 전전월 (prev2) -> 전월 단가 증감 계산용
    p2w, p2a = get_val(w, prev2_y, prev2_m), get_val(a, prev2_y, prev2_m)

    def calc_price(amt, wgt):
        wgt = wgt.where(wgt > 0)
        return (amt / wgt) * 1000.0

    def calc_share(wgt):
        tot = wgt.sum()
        return (wgt / tot * 100.0) if tot > 0 else wgt * 0

    diff_prev = calc_price(pa, pw) - calc_price(p2a, p2w)
    diff_curr = calc_price(ca, cw) - calc_price(pa, pw)

    rows = []
    for mk in makers:
        rows.append({"구분": f"{mk}_중량", 
                     f"'{str(base_year)[-2:]}.평균": bw.get(mk), f"'{str(base_year)[-2:]}.비중": calc_share(bw).get(mk),
                     f"'{str(prev_y)[-2:]}.{prev_m}월": pw.get(mk), f"'{str(prev_y)[-2:]}.{prev_m}월 비중": calc_share(pw).get(mk),
                     f"'{str(year)[-2:]}.{month}월": cw.get(mk), f"'{str(year)[-2:]}.{month}월 비중": calc_share(cw).get(mk),
                     f"'{str(year)[-2:]}.평균": sw.get(mk), f"'{str(year)[-2:]}.비중": calc_share(sw).get(mk)})
        rows.append({"구분": f"{mk}_단가", 
                     f"'{str(base_year)[-2:]}.평균": calc_price(ba, bw).get(mk), f"'{str(base_year)[-2:]}.비중": np.nan,
                     f"'{str(prev_y)[-2:]}.{prev_m}월": calc_price(pa, pw).get(mk), f"'{str(prev_y)[-2:]}.{prev_m}월 비중": np.nan,
                     f"'{str(year)[-2:]}.{month}월": calc_price(ca, cw).get(mk), f"'{str(year)[-2:]}.{month}월 비중": np.nan,
                     f"'{str(year)[-2:]}.평균": calc_price(sa, sw).get(mk), f"'{str(year)[-2:]}.비중": np.nan})
        rows.append({"구분": f"{mk}_증감", 
                     f"'{str(base_year)[-2:]}.평균": np.nan, f"'{str(base_year)[-2:]}.비중": np.nan,
                     f"'{str(prev_y)[-2:]}.{prev_m}월": diff_prev.get(mk), f"'{str(prev_y)[-2:]}.{prev_m}월 비중": np.nan,
                     f"'{str(year)[-2:]}.{month}월": diff_curr.get(mk), f"'{str(year)[-2:]}.{month}월 비중": np.nan,
                     f"'{str(year)[-2:]}.평균": np.nan, f"'{str(year)[-2:]}.비중": np.nan})

    # ── 1. 총계 계산 (변수 선언) ──────────────────────────────────────────
    tot_bw, tot_ba = bw.sum(), ba.sum()
    tot_pw, tot_pa = pw.sum(), pa.sum()
    tot_cw, tot_ca = cw.sum(), ca.sum()
    tot_sw, tot_sa = sw.sum(), sa.sum()
    
    tot_p2w, tot_p2a = p2w.sum(), p2a.sum()

    tot_price_b = (tot_ba / tot_bw * 1000.0) if tot_bw > 0 else np.nan
    tot_price_p = (tot_pa / tot_pw * 1000.0) if tot_pw > 0 else np.nan
    tot_price_c = (tot_ca / tot_cw * 1000.0) if tot_cw > 0 else np.nan
    tot_price_s = (tot_sa / tot_sw * 1000.0) if tot_sw > 0 else np.nan
    tot_price_p2 = (tot_p2a / tot_p2w * 1000.0) if tot_p2w > 0 else np.nan

    tot_diff_prev = tot_price_p - tot_price_p2 if pd.notna(tot_price_p) and pd.notna(tot_price_p2) else np.nan
    tot_diff_curr = tot_price_c - tot_price_p if pd.notna(tot_price_c) and pd.notna(tot_price_p) else np.nan

    # ── 2. 총계 행 추가 (메이커 행과 컬럼 Key 명칭 완전 통일) ─────────────────
    rows.append({"구분": "총계_중량", 
                 f"'{str(base_year)[-2:]}.평균": tot_bw, f"'{str(base_year)[-2:]}.비중": 100.0 if tot_bw > 0 else np.nan,
                 f"'{str(prev_y)[-2:]}.{prev_m}월": tot_pw, f"'{str(prev_y)[-2:]}.{prev_m}월 비중": 100.0 if tot_pw > 0 else np.nan,
                 f"'{str(year)[-2:]}.{month}월": tot_cw, f"'{str(year)[-2:]}.{month}월 비중": 100.0 if tot_cw > 0 else np.nan,
                 f"'{str(year)[-2:]}.평균": tot_sw, f"'{str(year)[-2:]}.비중": 100.0 if tot_sw > 0 else np.nan})

    rows.append({"구분": "총계_단가", 
                 f"'{str(base_year)[-2:]}.평균": tot_price_b, f"'{str(base_year)[-2:]}.비중": np.nan,
                 f"'{str(prev_y)[-2:]}.{prev_m}월": tot_price_p, f"'{str(prev_y)[-2:]}.{prev_m}월 비중": np.nan,
                 f"'{str(year)[-2:]}.{month}월": tot_price_c, f"'{str(year)[-2:]}.{month}월 비중": np.nan,
                 f"'{str(year)[-2:]}.평균": tot_price_s, f"'{str(year)[-2:]}.비중": np.nan})

    rows.append({"구분": "총계_증감", 
                 f"'{str(base_year)[-2:]}.평균": np.nan, f"'{str(base_year)[-2:]}.비중": np.nan,
                 f"'{str(prev_y)[-2:]}.{prev_m}월": tot_diff_prev, f"'{str(prev_y)[-2:]}.{prev_m}월 비중": np.nan,
                 f"'{str(year)[-2:]}.{month}월": tot_diff_curr, f"'{str(year)[-2:]}.{month}월 비중": np.nan,
                 f"'{str(year)[-2:]}.평균": np.nan, f"'{str(year)[-2:]}.비중": np.nan})
        
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
                    if "비중" in c:
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

# ────────────────────────────────────────────────────────────────────────
# 4) 제조 가공비 요약 Builder & HTML Renderer
# ────────────────────────────────────────────────────────────────────────

def _build_제조가공비_table(year: int, month: int):
    # 데이터 로드
    df_raw = load_sheet(Sheets.제조가공비_DB)
    
    # 🟢 급료와임금 데이터 살리기
    if '구분2' in df_raw.columns:
        df_raw['구분2'] = df_raw['구분2'].astype(str).str.replace("급료와임금", "급여")

    # --- 내부 연산 모듈 로직 통합 ---
    df = df_raw.copy()
    
    # 🔴 [추가] 구분2가 비어있는 경우(ex. 원재투입중량) 구분1의 이름으로 채워 넣음
    df['구분2'] = df['구분2'].replace(['nan', 'None', '', ' '], np.nan)
    if '구분1' in df.columns:
        df['구분2'] = df['구분2'].fillna(df['구분1'])
    
    c_y, c_m, c_it, c_site, c_val = "연도", "월", "구분2", "사업장", "값"
    
    df[c_y] = pd.to_numeric(df[c_y], errors="coerce")
    df[c_m] = pd.to_numeric(df[c_m], errors="coerce")
    df[c_val] = pd.to_numeric(df[c_val].astype(str).str.replace(",", ""), errors="coerce").fillna(0)

    def _site_norm(s: str) -> str:
        s = str(s).strip()
        if "포항" in s: return "포항"
        if "충주2" in s: return "충주2"
        if "충주" in s: return "충주"
        return "기타"

    if c_site not in df.columns:
        df[c_site] = df.get("구분1", "")

    df["__site__"] = df[c_site].map(_site_norm)
    df = df[df["__site__"].isin(["포항", "충주", "충주2"])]

    # 와이드 형태로 피벗
    pv = (
        df.groupby([c_y, c_m, c_it, "__site__"])[c_val].sum().reset_index()
        .pivot(index=[c_y, c_m, c_it], columns="__site__", values=c_val)
        .reset_index()
    )
    for c in ["포항", "충주", "충주2"]:
        if c not in pv.columns:
            pv[c] = 0.0

    pv.rename(columns={c_y: "연도", c_m: "월", c_it: "항목"}, inplace=True)
    pv["계"] = pv[["포항", "충주", "충주2"]].sum(axis=1)
    wide = pv[["연도", "월", "항목", "포항", "충주", "충주2", "계"]]

    # 🔴 [수정] 부모(구분1)가 먼저 나오고, 그 아래에 자식(구분2)들이 오도록 순서 재정렬
    # 엑셀 기준 부재료비는 제조경비 하위이므로 그룹화 편입
    ORDER = [
        "제조노무비", "급여", "상여금", "잡급", "퇴직급여충당금", 
        "제조경비", "부재료비", "전력비", "수도료", "감가상각비", "수선비", "소모품비", "복리후생비", "지급임차료", "지급수수료", "외주용역비", "외주가공비", "기타", 
        "총합", "원재투입중량", "투입중량 원단위(천원)"
        ]
    LABOR = ["급여", "상여금", "잡급", "퇴직급여충당금"]
    OH = ["부재료비", "전력비", "수도료", "감가상각비", "수선비", "소모품비", "복리후생비", "지급임차료", "지급수수료", "외주용역비", "외주가공비", "기타"]

    def _month_list_loc(y: int, m: int):
        d = wide[(wide["연도"] == y) & (wide["월"] == m)]
        base = d.groupby("항목")[["포항", "충주", "충주2", "계"]].sum()
        
        def _row_sum(names):
            if not names: return pd.Series([0,0,0,0], index=["포항", "충주", "충주2", "계"])
            return base.reindex(names).fillna(0).sum()

        labor = _row_sum(LABOR)
        oh = _row_sum(OH)
        
        # 🔴 [수정] 제조경비(OH) 안에 부재료비가 편입되었으므로 material 변수를 별도로 더하지 않음
        total = labor.add(oh, fill_value=0)

        weight = d[d["항목"].astype(str).str.replace(" ", "") == "원재투입중량"][["포항", "충주", "충주2", "계"]].sum()
        if weight.empty: weight = pd.Series([np.nan]*4, index=["포항", "충주", "충주2", "계"])

        weight_ton = weight.apply(lambda v: v / 1000.0 if v > 100000 else v)

        # 백만원 / 톤 (원단위)
        unit = (total / 1000000.0) / weight_ton.replace({0: np.nan}) * 1000

        rows = {}
        for name in ORDER:
            if name == "제조노무비": rows[name] = labor
            elif name == "제조경비": rows[name] = oh
            elif name == "총합": rows[name] = total
            elif name == "원재투입중량": rows[name] = weight
            elif name == "투입중량 원단위(천원)": rows[name] = unit
            else: rows[name] = base.reindex([name]).fillna(0).sum()
            
        snap = pd.DataFrame(rows).T[["포항", "충주", "충주2", "계"]]
        snap.index.name = "구분"
        return snap

    prev_y, prev_m = _month_shift(year, month, -1)
    prev_snap = _month_list_loc(prev_y, prev_m)
    curr_snap = _month_list_loc(year, month)

    idx = prev_snap.index.union(curr_snap.index)
    prev = prev_snap.reindex(idx).fillna(0.0)
    curr = curr_snap.reindex(idx).fillna(0.0)
    diff = curr - prev

    disp = pd.concat([prev, curr, diff], axis=1).reset_index()
    
    # --- 화면 출력 노출용 재치환 및 정렬 ---
    disp["구분"] = disp["구분"].astype(str).str.strip().replace("급여", "급료와임금")
    order_map = {"급료와임금" if name.strip() == "급여" else name.strip(): i for i, name in enumerate(ORDER)}
    disp["__ord__"] = disp["구분"].map(order_map).fillna(9999)
    disp = disp.sort_values(by="__ord__").drop(columns="__ord__").reset_index(drop=True)

    # 동적 단층 컬럼명 지정
    yy_str = str(year)[-2:]
    prev_m_label = f"'{str(prev_y)[-2:]}.{prev_m}월"
    curr_m_label = f"'{yy_str}.{month}월"

    disp.columns = [
        '구분',
        '포항/본사 ①', '충주 ②', '충주2 ③', f'{prev_m_label} ①+②+③',
        '포항/본사 ④', '충주 ⑤', '충주2 ⑥', f'{curr_m_label} ④+⑤+⑥',
        '포항/본사 ⑦', '충주 ⑧', '충주2 ⑨', '전월대비 ⑦+⑧+⑨'
    ]
    
    return disp

def _제조가공비_to_html(df) -> str:
    cols = df.columns.tolist()
    th_html = '<tr>' + ''.join(f'<th style="{_TH}; white-space: nowrap;">{c}</th>' for c in cols) + '</tr>'

    # 구분1(부모) 및 총계 라인들만 볼드 및 들여쓰기 0 적용
    lv0_items = ['제조노무비', '제조경비', '총합', '원재투입중량', '투입중량 원단위(천원)']
    
    body_html = ''
    for _, row in df.iterrows():
        label = str(row['구분']).strip()
        if not label: continue

        # 들여쓰기가 0인 항목(lv0_items)일 경우 배경색(회색) 적용
        bg_style = 'background-color: #f2f2f2;' if label in lv0_items else ''
        
        # 적용된 배경색을 tr 태그에 삽입
        body_html += f'<tr style="{bg_style}">'
        
        for c in cols:
            val = row[c]
            
            if c == '구분':
                if label in lv0_items:
                    padding = 0
                    font_weight = '700'
                else:
                    padding = 16
                    font_weight = '400'
                
                text = f'<span style="padding-left:{padding}px; font-weight:{font_weight};">{label}</span>'
                body_html += f'<td style="border: 1px solid #aaa; padding: 6px 8px; font-size: 14px; text-align: left; white-space: nowrap;">{text}</td>'
            else:
                if pd.isna(val) or str(val).strip() == "":
                    text = ""
                else:
                    try:
                        v = float(val)

                        is_weight = "원재투입중량" in label
                        is_unit = "원단위" in label

                        if is_weight:
                            # 중량이 kg 단위로 들어온 경우 톤으로 환산해서 표시
                            v_ton = v / 1000.0 if v > 100000 else v
                            text = f"{int(round(v_ton)):,}"
                        elif is_unit:
                            # 원단위는 소수점 1자리로 표시
                            text = f"{v:,.1f}" if abs(v) < 100 else f"{int(round(v)):,}"
                            if v < 0:
                                text = f'<span style="color:#d32f2f;">{text}</span>'
                        else:
                            # 일반 금액 항목 (백만원 단위로 환산)
                            v_div = v / 1000000.0
                            
                            if "잡급" in label:
                                if v_div == 0: text = "0"
                                elif v_div < 0: text = f'<span style="color:#d32f2f;">-{abs(v_div):,.1f}</span>'
                                else: text = f"{v_div:,.1f}"
                            else:
                                v_round = int(round(v_div))
                                if v_round < 0:
                                    text = f'<span style="color:#d32f2f;">-{abs(v_round):,}</span>'
                                else:
                                    text = f"{v_round:,}"

                    except:
                        text = str(val)
                        
                body_html += f'<td style="{_TD_NUM}">{text}</td>'
        body_html += '</tr>'

    return _html_table(th_html, body_html)

# ────────────────────────────────────────────────────────────────────────
# 5) 판매비와 관리비 Builder & HTML Renderer
# ────────────────────────────────────────────────────────────────────────

def _build_판관비_table(year: int, month: int):
    df_src = load_sheet(Sheets.판매비와관리비_DB)
    
    # --- 내부 연산 모듈 로직 통합 ---
    df = df_src.copy()
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df["값"] = pd.to_numeric(df["값"].astype(str).str.replace(",", ""), errors="coerce").fillna(0)

    # 구분2(급여 등)와 구분1(판매량)을 합쳐서 기준 생성
    df["구분2"] = df["구분2"].fillna("").astype(str).str.strip()
    df["구분1"] = df["구분1"].fillna("").astype(str).str.strip()
    df["항목"] = df["구분2"].replace("", np.nan).fillna(df["구분1"])

    # ★ 추가된 부분: 표에 표시될 항목 이름 일괄 변경 ★
    df["항목"] = df["항목"].replace({
        "판관-운반비": "운반비",
        "판관-수출개별비": "수출개별비"
    })

    # 24년 이하 월평균 데이터 분리 (월을 숫자로 강제 변환하기 '전'에 추출)
    avg_rows = df[df["월"].astype(str).str.contains("평균", na=False)].copy()
    avg_explicit = avg_rows.groupby(["연도", "항목"])["값"].sum().reset_index()
    avg_explicit.rename(columns={"값": "계"}, inplace=True)

    # 일반(숫자 월) 데이터 추출을 위해 숫자로 변환
    df["월_숫자"] = pd.to_numeric(df["월"], errors="coerce")
    df_num = df[df["월_숫자"].notna()].copy()
    df_num["월"] = df_num["월_숫자"].astype(int)

    wide = df_num.groupby(["연도", "월", "항목"])["값"].sum().reset_index()
    wide.rename(columns={"값": "계"}, inplace=True)

    # 구분행 순서를 부모 항목 -> 하위 항목 순으로 바르게 정렬
    # ★ 수정된 부분: SGNA_ORDER 및 SELL 리스트 내 이름도 변경된 이름으로 일치시킴 ★
    SGNA_ORDER = [
        "인건비", "급여", "상여금", "퇴직급여충당금",
        "관리비", "복리후생비", "지급임차료", "사용권자산 감가상각비", "접대비", "세금과공과",
        "대손상각비", "지급수수료", "A/S비", "경상연구비", "기타",
        "판매비", "운반비", "수출개별비", 
        "합계", "", "판매량", "인건비 및 관리비 원단위", "운반비 원단위"
    ]

    LABOR = ["급여", "상여금", "퇴직급여충당금"]
    ADMIN = ["복리후생비", "지급임차료", "사용권자산 감가상각비", "접대비", "세금과공과", "대손상각비", "지급수수료", "A/S비", "경상연구비", "기타"]
    SELL = ["운반비", "수출개별비"]

    def _sgna_from_base(base, sales_override=None):
        def _sum(keys): return float(base.reindex(keys).fillna(0).sum())
        labor = _sum(LABOR)
        admin = _sum(ADMIN)
        sell = _sum(SELL)

        # 판매량 탐색
        idx = [str(x) for x in base.index]
        sales_key = next((x for x in idx if "판매량" in x.replace(" ", "")), None)
        sales_val = float(base.get(sales_key, 0.0)) if sales_key else 0.0

        sales_qty = float(sales_override) if sales_override is not None and pd.notna(sales_override) and sales_override != 0 else sales_val

        total = labor + admin + sell
        unit_la = ((labor + admin) / sales_qty * 1000.0) if sales_qty else float("nan")
        unit_f = (sell / sales_qty * 1000.0) if sales_qty else float("nan")

        out = {k: float(base.get(k, 0.0)) for k in LABOR + ADMIN + SELL}
        out["판매량"] = sales_val
        out["인건비"] = labor
        out["관리비"] = admin
        out["판매비"] = sell
        out["합계"] = total
        out["인건비 및 관리비 원단위"] = unit_la
        out["운반비 원단위"] = unit_f
        out[""] = np.nan
        return pd.Series(out).reindex(SGNA_ORDER)

    def _sgna_list_loc(y, m):
        d = wide[(wide["연도"] == y) & (wide["월"] == m)]
        base = d.groupby("항목")["계"].sum()
        return _sgna_from_base(base)

    m2_y, m2_m = _month_shift(year, month, -2)
    m1_y, m1_m = _month_shift(year, month, -1)

    s_m2 = _sgna_list_loc(m2_y, m2_m)
    s_m1 = _sgna_list_loc(m1_y, m1_m)
    s_m0 = _sgna_list_loc(year, month)
    diff = s_m0 - s_m1

    avg_years = [year - 2, year - 1]
    avg_data = {}

    # [수정] reversed()를 제거하여 과거 연도(24년)부터 순차적으로 배치되도록 수정
    for y in avg_years:
        if y <= 2024:
            # 24년 이전: 명시된 '월평균' 데이터 사용
            base_df = avg_explicit[avg_explicit["연도"] == y]
            base = base_df.set_index("항목")["계"].astype(float)
            
            sales_key = next((x for x in base.index if "판매량" in str(x).replace(" ","")), None)
            sales_avg = base.get(sales_key, np.nan) if sales_key else np.nan

            if pd.isna(sales_avg) or sales_avg == 0:
                wide_y = wide[wide["연도"] == int(y)]
                sales_rows = wide_y[wide_y["항목"].astype(str).str.replace(" ","").str.contains("판매량", na=False)]
                sales_avg = sales_rows.groupby("월")["계"].sum().mean() if not sales_rows.empty else np.nan
        else:
            # 25년 이후: 숫자 월(1,2,3..)을 바탕으로 고유 월 수로 나누어 계산
            wide_y = wide[wide["연도"] == int(y)]
            unique_months = wide_y["월"].nunique()
            
            if unique_months > 0:
                base = wide_y.groupby("항목")["계"].sum() / unique_months
            else:
                base = pd.Series(dtype=float)
                
            sales_key = next((x for x in base.index if "판매량" in str(x).replace(" ","")), None)
            sales_avg = base.get(sales_key, np.nan) if sales_key else np.nan

        s_avg = _sgna_from_base(base, sales_avg)
        avg_data[f"'{str(y)[-2:]}.평균"] = s_avg.values

    final_data = {"구분": SGNA_ORDER}
    final_data.update(avg_data)
    final_data[f"'{str(m2_y)[-2:]}.{m2_m}월"] = s_m2.values
    final_data[f"'{str(m1_y)[-2:]}.{m1_m}월"] = s_m1.values
    final_data[f"'{str(year)[-2:]}.{month}월"] = s_m0.values
    final_data["전월대비"] = diff.values

    disp = pd.DataFrame(final_data)

    # ── Lv class 들여쓰기를 위한 데이터 매핑 ──
    lv0_items = ['인건비', '관리비', '판매비', '합계', '판매량', '인건비 및 관리비 원단위', '운반비 원단위', '']
    disp['_lv'] = disp['구분'].apply(lambda x: 0 if str(x).strip() in lv0_items else 1)

    return disp

def _판관비_to_html(df) -> str:
    cols = [c for c in df.columns if c != '_lv']
    th_html = '<tr>' + ''.join(f'<th style="{_TH}; white-space: nowrap;">{c}</th>' for c in cols) + '</tr>'

    body_html = ''
    for _, row in df.iterrows():
        lv = row.get('_lv', 0)
        label = str(row['구분'])
        
        # 상위구분 (Lv.0) 볼드 처리
        is_bold = (lv == 0 and label.strip() != "")
        fw_style = " font-weight: bold;" if is_bold else ""
        
        body_html += '<tr>'
        for c in cols:
            val = row[c]
            if c == '구분':
                padding = lv * 16
                text = f'<span style="padding-left:{padding}px">{label}</span>'
                body_html += f'<td style="border: 1px solid #aaa; padding: 6px 8px; font-size: 14px; text-align: left; white-space: nowrap; {fw_style}">{text}</td>'
            else:
                if pd.isna(val) or str(val).strip() == "":
                    text = ""
                else:
                    try:
                        fv = float(val)
                        
                        # [수정] 오직 '판매량'만 100만 나누기에서 제외합니다. (원단위는 스케일링 대상에 포함)
                        if label == "판매량":
                            iv = int(round(fv))
                            if iv < 0: text = f'<span style="color:red">-{abs(iv):,}</span>'
                            else: text = f"{iv:,}"
                        else:
                            is_avg = "평균" in str(c)
                            divide_1m = True

                            if is_avg and any(y_str in str(c) for y_str in ["'24", "'23", "'22", "'21"]):
                                divide_1m = False

                            # 원단위 포함 모든 금액성 데이터를 백만으로 나누어 반올림 처리
                            iv = int(round(fv / 1_000_000 if divide_1m else fv))
                            
                            if c == "전월대비":
                                if iv < 0: text = f'<span style="color:red">-{abs(iv):,}</span>'
                                elif iv > 0: text = f"{iv:,}"
                                else: text = "0"
                            else:
                                if iv < 0: text = f'<span style="color:red">-{abs(iv):,}</span>'
                                else: text = f"{iv:,}"
                    except:
                        text = str(val)
                body_html += f'<td style="{_TD_NUM}{fw_style}">{text}</td>'
        body_html += '</tr>'

    return _html_table(th_html, body_html)

def _build_성과급_table(year, month):
    df_raw = load_sheet(Sheets.성과급및격려금_DB)
    df_raw['값'] = df_raw['값'].apply(_parse)
    
    # _drop_empty가 '연간', '월별' 등 숫자가 아닌 문자열 월(Month) 데이터를 비정상 값으로 
    # 간주해 삭제할 가능성이 있으므로, 필터링을 거치기 전 원본에서 먼저 추출합니다.
    df_100 = df_raw.copy()
    df_100['연도'] = df_100['연도'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df_100['월'] = df_100['월'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    
    for c in ['구분1', '구분2']:
        if c in df_100.columns:
            df_100[c] = df_100[c].fillna('').astype(str).str.strip()
            
    val_100_map = df_100.groupby(['구분1', '구분2', '연도', '월'])['값'].sum().to_dict()

    def get_100_val(g1, g2, time_label):
        return val_100_map.get((str(g1), str(g2), str(year), str(time_label)), 0.0)

    # ── 기존 실적 데이터 처리 ──
    df = _drop_empty(df_raw, '연도', '월')

    for c in ['구분1', '구분2', '계획/실적', '구분3']:
        if c in df.columns:
            df[c] = df[c].fillna('').astype(str).str.strip()

    df['연도'] = df['연도'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df['월'] = df['월'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

    val_map = df.groupby(['구분1', '구분2', '계획/실적', '구분3', '연도', '월'])['값'].sum().to_dict()

    def get_val(g1, g2, mode, g3, yr, mo):
        return val_map.get((str(g1), str(g2), str(mode), str(g3), str(yr), str(mo)), 0.0)

    def 당월_v(g1, g2):
        return get_val(g1, g2, '실적', '당월', year, month)

    def 전년_v(g1, g2):
        return sum(get_val(g1, g2, '실적', '당월', year - 1, m) for m in range(1, 13))

    def 누적_v(g1, g2):
        return sum(get_val(g1, g2, '실적', '당월', year, m) for m in range(1, month + 1))

    # 앞서 추출해둔 안전한 map에서 데이터 호출
    def 연간_v(g1, g2):
        return get_100_val(g1, g2, '연간')

    def 월별_v(g1, g2):
        return get_100_val(g1, g2, '월별')

    def metrics(items):
        연간 = sum(연간_v(g1, g2) for g1, g2 in items)
        월 = sum(월별_v(g1, g2) for g1, g2 in items)
        전년 = sum(전년_v(g1, g2) for g1, g2 in items)
        당월 = sum(당월_v(g1, g2) for g1, g2 in items)
        누적 = sum(누적_v(g1, g2) for g1, g2 in items)
        퍼센트 = (누적 / 전년 * 100) if 전년 != 0 else np.nan
        
        return {
            '전년': 전년,
            '당월': 당월,
            '누적': 누적,
            '%': 퍼센트,
            '연간': 연간,
            '월': 월,
        }

    # 계층 매핑 구조
    성과_직원_제조 = [('성과', '직원_제조')]
    성과_직원_판관 = [('성과', '직원_판관')]
    성과_직원_합 = 성과_직원_제조 + 성과_직원_판관

    성과_임원_제조 = [('성과', '임원_제조')] 
    성과_임원_판관 = [('성과', '임원_판관')]
    성과_임원_합 = 성과_임원_제조 + 성과_임원_판관

    성과_합 = 성과_직원_합 + 성과_임원_합

    격려_제조 = [('격려', '제조')]
    격려_판관 = [('격려', '판관')]
    격려_합 = 격려_제조 + 격려_판관

    외주_항목 = [('외주', '외주')]

    합계_항목 = 성과_합 + 격려_합 + 외주_항목

    rows_info = [
        ('성과', 0, True, 성과_합, False),
        ('직원', 1, True, 성과_직원_합, False),
        ('제조', 2, False, 성과_직원_제조, False),
        ('판관', 2, False, 성과_직원_판관, False),
        ('임원', 1, True, 성과_임원_합, False),
        ('제조', 2, False, 성과_임원_제조, False),
        ('판관', 2, False, 성과_임원_판관, False),
        (None, 0, False, None, False),
        ('격려', 0, True, 격려_합, False),
        ('제조', 1, False, 격려_제조, False),
        ('판관', 1, False, 격려_판관, False),
        (None, 0, False, None, False),
        ('외주', 0, True, 외주_항목, False),
        (None, 0, False, None, False),
        ('합계', 0, True, 합계_항목, True),
    ]

    rows = []
    for label, depth, bold, items, top_border in rows_info:
        if label is None:
            rows.append({'_spacer': True})
            continue
        
        m = metrics(items)
        
        pct_val = m['%']
        if pd.isna(pct_val):
            pct_str = ""
        else:
            pct_str = f"{int(round(pct_val))}%"

        rows.append({
            '_spacer':    False,
            '_depth':     depth,
            '_bold':      bold,
            '_top_border': top_border,
            '구분':       label,
            '전년':       _fmt(m['전년'], decimal=0),
            '당월':       _fmt(m['당월'], decimal=0),
            '누적':       _fmt(m['누적'], decimal=0),
            '%':          pct_str,
            '연간':       _fmt(m['연간'], decimal=0),
            '월':         _fmt(m['월'],   decimal=0),
        })

    return rows

def _성과급_to_html(rows) -> str:
    col_keys = ['전년', '당월', '누적', '%', '연간', '월']

    # % 컬럼 추가에 따른 실적 colspan 변경 (3 -> 4)
    th_html = (
        f'<tr><th rowspan="2" style="{_TH}">구분</th>'
        f'<th colspan="4" style="{_TH}">실적</th>'
        f'<th colspan="2" style="{_TH}">성과급 100% (자사)</th></tr>'
        f'<tr><th style="{_TH}">전년</th><th style="{_TH}">당월</th><th style="{_TH}">누적</th><th style="{_TH}">%</th>'
        f'<th style="{_TH}">연간</th><th style="{_TH}">월</th></tr>'
    )

    body_html = ''
    n_cols = 1 + len(col_keys)
    for row in rows:
        if row.get('_spacer'):
            body_html += f'<tr><td colspan="{n_cols}" style="height:10px;border:none;background:#ffffff"></td></tr>'
            continue

        is_bold = row['_bold']
        style_label = ROW_HDR_LBL if is_bold else ROW_ITEM
        style_num   = ROW_HDR_NUM if is_bold else _TD_NUM
        style_red   = ROW_HDR_RED if is_bold else _TD_RED
        if row.get('_top_border'):
            border = f'border-top:2px solid {_C_NAVY};'
            style_label += f';{border}'
            style_num   += f';{border}'
            style_red   += f';{border}'

        padding = row['_depth'] * 16
        cells = f'<td style="{style_label};padding-left:{10 + padding}px">{row["구분"]}</td>'
        for c in col_keys:
            s = str(row[c])
            cells += f'<td style="{style_red if s.startswith("-") else style_num}">{s}</td>'
        body_html += f'<tr>{cells}</tr>'

    return _html_table(th_html, body_html)


def _build_포스코지원금_table(year, month):
    df = load_sheet(Sheets.포스코지원금_DB)
    df['값'] = df['값'].apply(_parse)
    df = _drop_empty(df, '연도', '월')

    # 1. 연도/월 숫자 변환 및 당월 누적 필터링 추가
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce')
    df['월'] = pd.to_numeric(df['월'], errors='coerce')
    
    # 선택한 연/월 이전의 데이터만 집계 (미래 데이터 합산 방지)
    mask = (df['연도'] < year) | ((df['연도'] == year) & (df['월'] <= month))
    df = df[mask]

    for c in ['구분1', '구분2', '구분3']:
        df[c] = df[c].fillna('').astype(str).str.strip()

    # 2. 데이터에 존재하는 실제 분기(구분1) 추출 (정렬 후 최근 2개)
    unique_q = sorted([q for q in df['구분1'].unique() if q])
    q_labels = unique_q[-2:] if len(unique_q) >= 2 else unique_q
    
    # 만약 데이터가 하나도 없다면 화면이 깨지지 않도록 기본값 세팅
    if not q_labels:
        cur_q = (month - 1) // 3 + 1
        prev_q = 4 if cur_q == 1 else cur_q - 1
        prev_y = year - 1 if cur_q == 1 else year
        q_labels = [f"{str(prev_y)[2:]}.{prev_q}Q", f"{str(year)[2:]}.{cur_q}Q"]

    # 동일 분기에 대해 매월 동일한 값이 들어있으므로, 중복을 제거하고 최신(last) 데이터만 남겨 합산 방지
    df_unique = df.sort_values(['연도', '월']).drop_duplicates(subset=['구분1', '구분2', '구분3'], keep='last')
    val_map = df_unique.groupby(['구분1', '구분2', '구분3'])['값'].sum().to_dict()

    def get_val(q_label, g2, g3):
        return val_map.get((q_label, g2, g3), 0.0)

    def calc(lbl, target_items):
        v_qty_raw = sum(get_val(lbl, it, '주문량') for it in target_items)
        v_amt_raw = sum(get_val(lbl, it, '할인금액') for it in target_items)
        
        # 단위 맞추기
        v_qty = v_qty_raw / 1000.0 if v_qty_raw else 0.0
        v_amt = v_amt_raw / 1000000.0 if v_amt_raw else 0.0
        price = (v_amt_raw / v_qty) if v_qty else 0.0
        
        return v_qty, price, v_amt

    rows = []
    
    # 3. 기존 항목 (단가, 할인금액 포함)
    items_vol = ['수출지원(ES)', '일반재', '특가지원(SP)']
    for item in items_vol:
        row = {'구분': item, '_bold': False, '_type': 'normal'}
        for lbl in q_labels:
            v_qty, price, v_amt = calc(lbl, [item])
            row[f'{lbl}_주문량']  = _fmt(v_qty, decimal=0)
            row[f'{lbl}_단가']    = _fmt(price/1000, decimal=0)
            row[f'{lbl}_할인금액'] = _fmt(v_amt, decimal=0)
        rows.append(row)

    # 물량 할인 = 수출지원(ES) + 일반재 + 특가지원(SP)
    total_vol_row = {'구분': '물량 할인', '_bold': True, '_type': 'normal'}
    for lbl in q_labels:
        v_qty, price, v_amt = calc(lbl, items_vol)
        total_vol_row[f'{lbl}_주문량']  = _fmt(v_qty, decimal=0)
        total_vol_row[f'{lbl}_단가']    = _fmt(price/1000, decimal=0)
        total_vol_row[f'{lbl}_할인금액'] = _fmt(v_amt, decimal=0)
    rows.append(total_vol_row)

    # 4. 신규 추가 항목 (주문량만 산출, 단가/할인금액 제외)
    items_other = ['연계 할인', '중국 대응재']
    for item in items_other:
        row = {'구분': item, '_bold': False, '_type': 'qty_only'}
        for lbl in q_labels:
            v_qty, _, _ = calc(lbl, [item])
            row[f'{lbl}_주문량']  = _fmt(v_qty, decimal=0)
            row[f'{lbl}_단가']    = ''
            row[f'{lbl}_할인금액'] = ''
        rows.append(row)

    # 총계 = 물량할인 + 연계할인 + 중국대응재 (주문량 합산)
    all_items = items_vol + items_other
    total_all_row = {'구분': '총계', '_bold': True, '_type': 'qty_only'}
    for lbl in q_labels:
        v_qty, _, _ = calc(lbl, all_items)
        total_all_row[f'{lbl}_주문량']  = _fmt(v_qty, decimal=0)
        total_all_row[f'{lbl}_단가']    = ''
        total_all_row[f'{lbl}_할인금액'] = ''
    rows.append(total_all_row)

    return rows, q_labels

def _포스코지원금_to_html(rows, q_labels) -> str:
    sub_cols = ['주문량', '단가', '할인금액']

    th_html = f'<tr><th rowspan="2" style="{_TH}">구분</th>'
    for lbl in q_labels:
        th_html += f'<th colspan="3" style="{_TH}">{lbl}</th>'
    th_html += '</tr><tr>'
    for _ in q_labels:
        for sc in sub_cols:
            th_html += f'<th style="{_TH}">{sc}</th>'
    th_html += '</tr>'

    body_html = ''
    for row in rows:
        is_bold = row.get('_bold', False)
        row_type = row.get('_type', 'normal')
        
        style_label = ROW_HDR_LBL if is_bold else ROW_ITEM
        style_num   = ROW_HDR_NUM if is_bold else _TD_NUM
        style_red   = ROW_HDR_RED if is_bold else _TD_RED
        
        # 주문량 외 빈칸(연계할인, 중국대응재, 총계)을 위한 짙은 회색 배경 스타일
        style_empty = 'border: 1px solid #aaa; background-color: #595959;'

        cells = f'<td style="{style_label}">{row["구분"]}</td>'
        for lbl in q_labels:
            for sc in sub_cols:
                if row_type == 'qty_only' and sc in ['단가', '할인금액']:
                    # 빈 셀은 회색 배경 처리
                    cells += f'<td style="{style_empty}"></td>'
                else:
                    s = str(row[f'{lbl}_{sc}'])
                    cells += f'<td style="{style_red if s.startswith("-") else style_num}">{s}</td>'
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

    tabs = app.tabs(["손익요약", "전월대비 손익차이", "원재료", "제조가공비", "판매비와 관리비", "성과급 및 격려금"])

    with tabs[0]:
        # p2_손익분석.py 하단 _render_손익요약 함수
        def _render_손익요약():
            year, month = int(year_state.value), int(month_state.value)

            # 1. 표 데이터 및 HTML 생성
            df_table = _build_손익요약표_table(year, month)
            html = _손익요약표_to_html_table(df_table)
            
            # (중복 div 감싸기 제거)
            
            # 2. 구글 시트에서 해당 연/월의 메모 가져오기
            memo = _get_memo(Sheets.손익요약표_메모, year, month)
            
            # 3. 레이아웃에 memo 인자 추가하여 렌더링
            app.markdown(_layout100("1) 손익요약표", html, memo=memo, unit="[단위: 톤, 백만원]"), unsafe_allow_html=True)

        app.If(lambda: True, _render_손익요약)

        
    with tabs[1]:
        def _render_차이():
            year, month = int(year_state.value), int(month_state.value)
            
            # 1) 전월대비 손익차이
            try:
                df_diff = _build_손익차이_table(year, month)
                html_diff = _손익차이_to_html_table(df_diff)
                memo_diff = _get_memo(Sheets.전월대비손익차이_메모, year, month)
                app.markdown(
                    _layout64("1) 전월대비 손익차이", html_diff, memo=memo_diff, unit="[단위: 백만원]"),
                    unsafe_allow_html=True
                )
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>전월대비 손익차이 생성 중 오류: {e}</p>", unsafe_allow_html=True)

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
                memo_qd = _get_memo(Sheets.QD_메모, year, month)

                app.markdown(
                    _layout100("3) QD 실적 차이", html_qd, memo=memo_qd, unit="[단위: 톤, 천원, 백만원]"), 
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

            # 1-2) 포스코 분기별 지원금
            try:
                rows_bs, q_labels_bs = _build_포스코지원금_table(year, month)
                html_bs = _포스코지원금_to_html(rows_bs, q_labels_bs)
                memo_bs = _get_memo(Sheets.포스코지원금_메모, year, month)
                app.markdown(_layout64("1-2) 포스코 분기별 지원금", html_bs, memo=memo_bs, unit="[단위: 톤, 백만원]"), unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>포스코 분기별 지원금 생성 오류: {e}</p>", unsafe_allow_html=True)

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

    with tabs[3]:
        def _render_제조가공비():
            year, month = int(year_state.value), int(month_state.value)
            
            try:
                df_mfg = _build_제조가공비_table(year, month)
                html_mfg = _제조가공비_to_html(df_mfg)
                memo_mfg = _get_memo(Sheets.제조가공비_메모, year, month)
                
                # 제조 가공비 요약은 100 layout 적용
                app.markdown(
                    _layout100("1) 제조 가공비 요약", html_mfg, memo=memo_mfg, unit="[단위: 톤, 백만원]"),
                    unsafe_allow_html=True,
                )
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>제조 가공비 요약 생성 중 오류: {e}</p>", unsafe_allow_html=True)
                
        app.If(lambda: True, _render_제조가공비)

    with tabs[4]:
        def _render_판관비():
            year, month = int(year_state.value), int(month_state.value)
            
            try:
                df_sgna = _build_판관비_table(year, month)
                html_sgna = _판관비_to_html(df_sgna)
                memo_sgna = _get_memo(Sheets.판매비와관리비_메모, year, month)
                
                # 판매비와 관리비는 64 layout 적용
                app.markdown(
                    _layout64("1) 판매비와 관리비", html_sgna, memo=memo_sgna, unit="[단위: 톤, 백만원]"),
                    unsafe_allow_html=True,
                )
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>판매비와 관리비 생성 중 오류: {e}</p>", unsafe_allow_html=True)

        app.If(lambda: True, _render_판관비)

    with tabs[5]:
        def _render_성과급():
            year, month = int(year_state.value), int(month_state.value)

            try:
                df_bonus = _build_성과급_table(year, month)
                html_bonus = _성과급_to_html(df_bonus)
                memo_bonus = _get_memo(Sheets.성과급및격려금_메모, year, month)

                app.markdown(
                    _layout64("1) 성과급 및 격려금", html_bonus, memo=memo_bonus, unit="[단위: 백만원]"),
                    unsafe_allow_html=True,
                )
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>성과급 및 격려금 생성 중 오류: {e}</p>", unsafe_allow_html=True)

        app.If(lambda: True, _render_성과급)

