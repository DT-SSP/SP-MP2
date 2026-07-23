import datetime
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from data.loader import load_sheet
from data.config import Sheets
from views.common import (
    parse as _parse, fmt as _fmt,
    prev_month as _prev, drop_empty as _drop_empty,
    layout100 as _layout100,
    TH as _TH, TD_NUM as _TD_NUM, ROW_HDR_LBL as ROW_HDR_LBL, ROW_HDR_NUM as ROW_HDR_NUM, ROW_ITEM as ROW_ITEM,
    html_table as _html_table,
    C_NAVY, C_ORANGE, C_RED, C_CHART_SEC, C_CHART_GRID,
)

# ── 공통 유틸 및 헬퍼 함수 ─────────────────────────────────────────────

def _recent_months(year, month, n_months=12, **kwargs):
    n_val = kwargs.get('n', n_months)
    result = []
    y, m = year, month
    for _ in range(n_val):
        result.insert(0, (y, m))
        y, m = _prev(y, m, 1)
    return result

def _get_memo(sheet_info, year, month):
    try:
        df = load_sheet(sheet_info)
        if df.empty or '연도' not in df.columns or '월' not in df.columns:
            return ''
        df['연도'] = df['연도'].astype(str).str.strip()
        df['월'] = df['월'].astype(str).str.strip()
        row = df[(df['연도'] == str(year)) & (df['월'] == str(month))]
        if '메모' in df.columns and not row.empty:
            return str(row.iloc[0]['메모'])
        return ''
    except Exception:
        return ''

def _to_number(val):
    if pd.isna(val) or val is None:
        return 0.0
    s = str(val).strip()
    if not s or s.lower() == 'nan':
        return 0.0
    neg = s.startswith('(') and s.endswith(')')
    s = s.replace('(', '').replace(')', '').replace(',', '').replace('%', '')
    try:
        v = float(s)
        return -abs(v) if neg else v
    except:
        return 0.0

def _f95_period_layout(month: int):
    periods = []
    for m in range(1, month + 1):
        periods.append((f"{m}월", [m]))
        if m % 3 == 0:
            q = m // 3
            q_months = list(range(q * 3 - 2, q * 3 + 1))
            periods.append((f"{q}분기", q_months))
    if month >= 4:
        periods.append(("누계", list(range(1, month + 1))))
    return periods


# ── 1) 실적요약 데이터 및 그래프 빌더 ───────────────────────────────────────────

def _build_실적요약_data(site_filter, year, month, n_months=12):
    df = load_sheet(Sheets.전체실적요약_DB) if hasattr(Sheets, '전체실적요약_DB') else load_sheet('전체실적요약_DB')
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    df['월'] = pd.to_numeric(df['월'], errors='coerce').fillna(0).astype(int)
    df['사업장'] = df['사업장'].fillna('').astype(str).str.strip()
    df['구분1'] = df['구분1'].fillna('').astype(str).str.strip()

    if site_filter and site_filter != '전체':
        df = df[df['사업장'] == site_filter]

    vm = df.groupby(['구분1', '연도', '월'])['값'].sum().to_dict()
    recent_months = _recent_months(year, month, n_months=n_months)
    
    x_labels, sales_list, volume_list, op_profit_list, op_margin_list = [], [], [], [], []
    M_SALES = 1_000_000
    K_VOL = 1_000

    for yr_c, mo_c in recent_months:
        lbl = f"'{str(yr_c)[2:]}년 {mo_c}월"
        x_labels.append(lbl)

        s_val = vm.get(('매출액', yr_c, mo_c), 0.0) / M_SALES
        v_val = vm.get(('판매량', yr_c, mo_c), 0.0) / K_VOL
        p_val = vm.get(('영업이익', yr_c, mo_c), 0.0) / M_SALES
        margin = (p_val / s_val * 100) if s_val > 0 else 0.0

        sales_list.append(s_val)
        volume_list.append(v_val)
        op_profit_list.append(p_val)
        op_margin_list.append(margin)

    return x_labels, sales_list, volume_list, op_profit_list, op_margin_list


def _build_실적요약_chart(x_labels, sales_list, volume_list, op_profit_list, op_margin_list):
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='매출액', x=x_labels, y=sales_list,
        marker_color='#334155', marker_line_width=0,
        text=[f"{int(v):,}" if v > 0 else '' for v in sales_list],
        textposition='inside', insidetextanchor='middle',
        textfont=dict(color='white', size=10), yaxis='y'
    ))

    fig.add_trace(go.Bar(
        name='판매량', x=x_labels, y=volume_list,
        marker_color='#E05638', marker_line_width=0,
        text=[f"{int(v):,}" if v > 0 else '' for v in volume_list],
        textposition='inside', insidetextanchor='middle',
        textfont=dict(color='white', size=10), yaxis='y'
    ))

    line_text = [
        f"<b>{int(p):,}</b><br>({m:.1f}%)" if p != 0 else ''
        for p, m in zip(op_profit_list, op_margin_list)
    ]

    fig.add_trace(go.Scatter(
        name='영업이익', x=x_labels, y=op_profit_list,
        mode='lines+markers+text',
        marker=dict(color='#64748B', size=7),
        line=dict(color='#64748B', width=2.5),
        text=line_text, textposition='top center',
        textfont=dict(color='#1E293B', size=11),
        yaxis='y2', connectgaps=True
    ))

    max_bar = max(max(sales_list or [1]), max(volume_list or [1]))
    max_line = max(op_profit_list) if op_profit_list else 100
    min_line = min(op_profit_list) if op_profit_list else 0

    fig.update_layout(
        barmode='group', height=450, margin=dict(l=20, r=20, t=50, b=60),
        legend=dict(
            orientation='h', y=-0.18, x=0.5, xanchor='center',
            font=dict(size=12, color='#334155'), bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            tickfont=dict(size=11, color='#64748B'),
            showgrid=False, linecolor='#CBD5E1', linewidth=1, showline=True,
        ),
        yaxis=dict(
            domain=[0, 0.62], showgrid=True, gridcolor=C_CHART_GRID, gridwidth=1,
            range=[0, max_bar * 1.25], showticklabels=False, showline=False, zeroline=False,
        ),
        yaxis2=dict(
            domain=[0.68, 1.0], range=[min_line * 1.2 if min_line < 0 else 0, max_line * 1.45],
            showgrid=False, showticklabels=False, showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig


# ── 2) 환율 추이 데이터 및 그래프 빌더 ───────────────────────────────────────────

def _build_환율추이_data(year, month):
    df = load_sheet(Sheets.환율_DB) if hasattr(Sheets, '환율_DB') else load_sheet('환율_DB')
    df = _drop_empty(df, '연도', '월')
    df['값'] = df['값'].apply(_parse)
    
    df['연도'] = pd.to_numeric(df['연도'], errors='coerce').fillna(0).astype(int)
    df['월'] = pd.to_numeric(df['월'], errors='coerce').fillna(0).astype(int)
    df['구분1'] = df['구분1'].fillna('').astype(str).str.strip()

    vm = df.groupby(['구분1', '연도', '월'])['값'].sum().to_dict()

    prev_yr = year - 1
    recent_4 = _recent_months(year, month, n_months=4)

    time_slots = [(prev_yr, 12, f"'{str(prev_yr)[2:]}년말")]
    last_yr = None
    for yr_c, mo_c in recent_4:
        lbl = f"'{str(yr_c)[2:]}년 {mo_c}월" if yr_c != last_yr else f"{mo_c}월"
        time_slots.append((yr_c, mo_c, lbl))
        last_yr = yr_c

    x_labels = [slot[2] for slot in time_slots]
    rates = {'USD': [], 'CNH': [], 'THB': []}
    for yr_c, mo_c, _ in time_slots:
        for currency in ['USD', 'CNH', 'THB']:
            val = vm.get((currency, yr_c, mo_c), 0.0)
            rates[currency].append(val)

    return x_labels, rates


def _build_환율추이_chart(x_labels, rates):
    fig = go.Figure()

    color_map = {'USD': '#334155', 'CNH': '#E05638', 'THB': '#0284C7'}

    for currency in ['USD', 'CNH', 'THB']:
        vals = rates.get(currency, [])
        text_labels = [f"<b>{v:,.1f}</b>" if v > 0 else '' for v in vals]
        
        fig.add_trace(go.Scatter(
            name=currency, x=x_labels, y=vals,
            mode='lines+markers+text',
            marker=dict(color=color_map[currency], size=8),
            line=dict(color=color_map[currency], width=2.5),
            text=text_labels, textposition='top center',
            textfont=dict(color='#1E293B', size=11), connectgaps=True
        ))

    all_vals = [v for curr in rates for v in rates[curr] if v > 0]
    max_val = max(all_vals) if all_vals else 1500
    min_val = min(all_vals) if all_vals else 0

    fig.update_layout(
        height=480, margin=dict(l=20, r=20, t=50, b=60),
        legend=dict(
            orientation='h', y=-0.20, x=0.5, xanchor='center',
            font=dict(size=12, color='#334155'), bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            tickfont=dict(size=11, color='#64748B'),
            showgrid=False, linecolor='#CBD5E1', linewidth=1, showline=True,
        ),
        yaxis=dict(
            showgrid=False, range=[min_val * 0.8, max_val * 1.15],
            showticklabels=False, showline=False, zeroline=False,
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=12, family='sans-serif'),
    )
    return fig


# ── 3) 손익계산서 (수정정상원가 기반) 빌더 ───────────────────────────────

def _build_손익계산서_table(year: int, month: int):
    df_raw = load_sheet(Sheets.손익계산서_DB) if hasattr(Sheets, '손익계산서_DB') else load_sheet('손익계산서_DB')
    df = df_raw.copy()

    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df["월"] = pd.to_numeric(df["월"].astype(str).str.extract(r"(\d+)")[0], errors="coerce")

    def _parse_number(x):
        s = str(x).strip() if x is not None else ""
        if s == "" or s.lower() == "nan": return np.nan
        neg = s.startswith("(") and s.endswith(")")
        s = s.replace("(", "").replace(")", "").replace(",", "")
        try:
            v = float(s)
            return -abs(v) if neg else v
        except:
            return np.nan

    if "값" in df.columns and "실적" not in df.columns:
        df = df.rename(columns={"값": "실적"})

    df["실적"] = df["실적"].map(_parse_number).fillna(0)

    for c in ["구분1", "구분2", "구분3"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str).str.strip()

    df = df[(df["연도"] == year)]
    periods = _f95_period_layout(month)

    def get_val(g1, g2, g3, m_list):
        cond = df["월"].isin(m_list)
        if g1: cond &= (df["구분1"] == g1)
        if g2: cond &= (df["구분2"] == g2)
        if g3: cond &= (df["구분3"] == g3)
        
        divisor = 1000.0 if g3 == "수량" else 1000000.0
        return df.loc[cond, "실적"].sum() / divisor if cond.any() else 0.0

    display_mapping = [
        ("매출액", "매출액", "", "", 0),
        ("제품 매출", "", "제품 매출", "", 1),
        ("수량", "", "수량", "", 2),
        ("부산물 매출", "", "부산물 매출", "", 1),

        ("변동비", "변동비", "", "", 0),
        ("재료비", "", "재료비", "", 1),
        ("DM%", "", "DM%", "", 2),

        ("변동비 가공비", "", "가공비", "", 1),
        ("부재료비", "", "", "부재료비", 2),
        ("외주용역비", "", "", "외주용역비", 2),
        ("수선비", "", "", "수선비", 2),
        ("변동비 가공비 기타", "", "", "기타", 2),

        ("운반비", "", "운반비", "", 1),
        ("C조건 선임", "", "", "C조건 선임", 2),
        ("수출개별비", "", "", "수출개별비", 2),
        ("국내 운반비", "", "", "국내 운반비", 2),

        ("한계이익", "한계이익", "", "", 0),
        ("한계이익율", "", "(이익율)", "", 1),

        ("고정비", "고정비", "", "", 0),
        ("고정비 가공비", "", "가공비", "", 1),
        ("감가상각비", "", "", "감가상각비", 2),
        ("제조노무비", "", "", "제조노무비", 2),
        ("고정비 가공비 기타", "", "", "기타", 2),
        ("판관비 기타", "", "기타", "", 1),
        ("재고자산평가", "재고자산평가, X등급 매출 등", "", "", 0),

        ("영업이익", "영업이익", "", "", 0),
        ("영업이익율", "", "(이익율)", "", 1),

        ("기타수익", "기타수익", "", "", 0),
        ("기타비용", "기타비용", "", "", 0),
        ("금융수익", "금융수익", "", "", 0),
        ("금융비용", "금융비용", "", "", 0),

        ("경상이익", "경상이익", "", "", 0),
        ("경상이익율", "", "(이익율)", "", 1),

        ("재경마감", "경상이익_재경마감", "", "", 0),
        ("재경마감 이익율", "", "(이익율)", "", 1),
    ]

    out_data = []
    for key, g1, g2, g3, depth in display_mapping:
        out_data.append({"_key": key, "_depth": depth, "구분1": g1, "구분2": g2, "구분3": g3})

    yy_str = str(year)[-2:]
    col_headers = []

    for label, m_list in periods:
        disp_col = f"'{yy_str}.{label}" if "월" in label or "분기" in label else label
        col_headers.append(disp_col)

        qty = get_val("매출액", "제품 매출", "수량", m_list)
        sales_prod = get_val("매출액", "제품 매출", "", m_list)
        sales_sub = get_val("매출액", "부산물 매출", "", m_list)
        sales_total = sales_prod + sales_sub

        mat_cost = get_val("변동비", "재료비", "", m_list)

        v_submat = get_val("변동비", "가공비", "부재료비", m_list)
        v_outsrc = get_val("변동비", "가공비", "외주용역비", m_list)
        v_repair = get_val("변동비", "가공비", "수선비", m_list)
        v_etc = get_val("변동비", "가공비", "기타", m_list)
        v_process_total = v_submat + v_outsrc + v_repair + v_etc

        t_ccond = get_val("변동비", "운반비", "C조건 선임", m_list)
        t_exp = get_val("변동비", "운반비", "수출개별비", m_list)
        t_dom = get_val("변동비", "운반비", "국내 운반비", m_list)
        transport_total = t_ccond + t_exp + t_dom

        var_cost_total = mat_cost + v_process_total + transport_total

        f_deprec = get_val("고정비", "가공비", "감가상각비", m_list)
        f_labor = get_val("고정비", "가공비", "제조노무비", m_list)
        f_etc = get_val("고정비", "가공비", "기타", m_list)
        f_process_total = f_deprec + f_labor + f_etc

        f_sgna_etc = get_val("고정비", "판관비", "", m_list)
        inv_eval = get_val("재고자산평가, X등급 매출 등", "재고자산평가, X등급 매출 등", "", m_list)

        fixed_cost_total = f_process_total + f_sgna_etc 

        nonop_rev1 = get_val("기타수익", "", "", m_list)
        nonop_exp1 = get_val("기타비용", "", "", m_list)
        nonop_rev2 = get_val("금융수익", "", "", m_list)
        nonop_exp2 = get_val("금융비용", "", "", m_list)

        dm_pct = ((sales_prod - mat_cost) / sales_prod * 100.0) if sales_prod != 0 else 0.0
        margin_profit = sales_total - var_cost_total
        margin_pct = (margin_profit / sales_total * 100.0) if sales_total != 0 else 0.0

        op_profit = margin_profit - fixed_cost_total + inv_eval
        op_pct = (op_profit / sales_total * 100.0) if sales_total != 0 else 0.0

        ord_profit = op_profit + nonop_rev1 - nonop_exp1 + nonop_rev2 - nonop_exp2
        ord_pct = (ord_profit / sales_total * 100.0) if sales_total != 0 else 0.0

        ord_profit_fin = get_val("경상이익_재경마감", "", "", m_list)
        ord_fin_pct = (ord_profit_fin / sales_total * 100.0) if sales_total != 0 else 0.0

        vals_map = {
            "매출액": sales_total, "제품 매출": sales_prod, "수량": qty, "부산물 매출": sales_sub,
            "변동비": var_cost_total, "재료비": mat_cost, "DM%": dm_pct,
            "변동비 가공비": v_process_total, "부재료비": v_submat, "외주용역비": v_outsrc, "수선비": v_repair, "변동비 가공비 기타": v_etc,
            "운반비": transport_total, "C조건 선임": t_ccond, "수출개별비": t_exp, "국내 운반비": t_dom,
            "한계이익": margin_profit, "한계이익율": margin_pct,
            "고정비": fixed_cost_total, "고정비 가공비": f_process_total, "감가상각비": f_deprec, "제조노무비": f_labor,
            "고정비 가공비 기타": f_etc, "판관비 기타": f_sgna_etc, "재고자산평가": inv_eval,
            "영업이익": op_profit, "영업이익율": op_pct,
            "기타수익": nonop_rev1, "기타비용": nonop_exp1, "금융수익": nonop_rev2, "금융비용": nonop_exp2,
            "경상이익": ord_profit, "경상이익율": ord_pct,
            "재경마감": ord_profit_fin, "재경마감 이익율": ord_fin_pct,
        }

        for row in out_data:
            row[disp_col] = vals_map.get(row["_key"], np.nan)

    res_df = pd.DataFrame(out_data)
    
    def _merge_label(r):
        g3, g2, g1 = str(r["구분3"]).strip(), str(r["구분2"]).strip(), str(r["구분1"]).strip()
        if g3 and g3 != "nan": return g3
        if g2 and g2 != "nan": return g2
        if g1 and g1 != "nan": return g1
        return ""

    res_df["구분"] = res_df.apply(_merge_label, axis=1)
    cols = ["구분", "_depth"] + col_headers
    return res_df[cols]


def _손익계산서_to_html_table(df):
    data_cols = [c for c in df.columns if c not in ('구분', '_depth', '_key', '구분1', '구분2', '구분3')]

    bold_labels = {"매출액", "변동비", "한계이익", "고정비", "영업이익", "경상이익", "경상이익_재경마감"}
    pct_labels = {"DM%", "(이익율)"}
    qty_labels = {"수량"}

    def fmt_num(v):
        if pd.isna(v) or v == "": return ""
        try:
            v = float(v)
            if v == 0: return "0"
            if v < 0: return f'<span style="color:#d32f2f;">-{abs(int(round(v))):,}</span>'
            return f"{int(round(v)):,}"
        except: return str(v)

    def fmt_pct(v):
        if pd.isna(v) or v == "": return ""
        try:
            v = float(v)
            if v < 0: return f'<span style="color:#d32f2f;">-{abs(v):,.1f}%</span>'
            return f"{v:,.1f}%"
        except: return str(v)

    def fmt_t(v):
        if pd.isna(v) or v == "": return ""
        try:
            v = float(v)
            return f"{v:,.0f}t"
        except: return str(v)

    rows_html = ''
    for _, row in df.iterrows():
        label = str(row["구분"]).strip()
        depth = int(row.get('_depth', 0))
        is_bold = label in bold_labels or depth == 0

        style_lbl = ROW_HDR_LBL if is_bold else ROW_ITEM
        style_num = ROW_HDR_NUM if is_bold else _TD_NUM

        padding = depth * 16
        cells = f'<td style="{style_lbl}; padding-left:{padding}px;">{label}</td>'

        for col in data_cols:
            val = row[col]
            if label in pct_labels:
                formatted = fmt_pct(val)
            elif label in qty_labels:
                formatted = fmt_t(val)
            else:
                formatted = fmt_num(val)

            cells += f'<td style="{style_num}">{formatted}</td>'
            
        rows_html += f'<tr>{cells}</tr>'

    headers_html = f'<th style="{_TH}">구분</th>'
    headers_html += ''.join(f'<th style="{_TH}">{c}</th>' for c in data_cols)

    return _html_table(f'<tr>{headers_html}</tr>', rows_html)


# ── 4) 유형별 손익분석 6개 데이터 모듈 ───────────────────────────────────

def build_f96(df_src: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    df = df_src.copy()
    if '값' in df.columns and '실적' not in df.columns:
        df = df.rename(columns={'값': '실적'})
    df["실적"] = df["실적"].apply(_to_number)
    df["연도"] = df["연도"].astype(int)
    df["월"] = df["월"].astype(int)

    mask = (df["연도"] == int(year)) & (df["월"] == int(month))
    df = df.loc[mask].copy()

    products = ["CHQ", "CD", "STS", "BTB", "PB"]
    df = df[df["구분1"].isin(products)]

    tmp = (
        df.pivot_table(
            index=["구분2", "구분3", "구분1"],
            columns="구분4",
            values="실적",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
    )

    for col in ["매출중량", "매출금액", "영업이익"]:
        if col not in tmp.columns:
            tmp[col] = 0.0

    tmp["판매중량"] = tmp["매출중량"]
    tmp["판매금액"] = tmp["매출금액"]
    tmp["영업이익금액"] = tmp["영업이익"]
    metrics_cols = ["판매중량", "판매금액", "영업이익금액"]

    def make_row(sub: pd.DataFrame, label: str) -> dict:
        row = {"구분": label}
        prod_sums = {}

        for p in products:
            d = sub[sub["구분1"] == p]
            vals = d[metrics_cols].sum() if not d.empty else pd.Series([0.0, 0.0, 0.0], index=metrics_cols)

            qty, amt, op = vals["판매중량"], vals["판매금액"], vals["영업이익금액"]

            row[f"{p}_판매중량"] = qty
            row[f"{p}_영업이익_단가"] = op / qty if qty != 0 else 0.0
            row[f"{p}_영업이익_금액"] = op
            row[f"{p}_영업이익_%"] = (op / amt * 100.0) if amt != 0 else 0.0

            prod_sums[p] = (qty, amt, op)

        total_qty = sum(q for q, _, _ in prod_sums.values())
        total_amt = sum(a for _, a, _ in prod_sums.values())
        total_op = sum(o for _, _, o in prod_sums.values())

        row["총계_판매중량"] = total_qty
        row["총계_영업이익_단가"] = total_op / total_qty if total_qty != 0 else 0.0
        row["총계_영업이익_금액"] = total_op
        row["총계_영업이익_%"] = (total_op / total_amt * 100.0) if total_amt != 0 else 0.0

        return row

    industry_order = ["자동차", "산업기계", "건설", "전자", "기타", "조선", "항공"]
    rows = []

    base_내수 = tmp[tmp["구분2"] == "내수"]
    rows.append(make_row(base_내수, "내수"))
    for ind in industry_order:
        sub = base_내수[base_내수["구분3"] == ind]
        rows.append(make_row(sub, ind))

    base_수출 = tmp[tmp["구분2"] == "수출"]
    rows.append(make_row(base_수출, "수출"))
    for ind in industry_order:
        sub = base_수출[base_수출["구분3"] == ind]
        rows.append(make_row(sub, ind))

    rows.append(make_row(tmp, "총계"))
    for ind in industry_order:
        sub = tmp[tmp["구분3"] == ind]
        rows.append(make_row(sub, ind))

    df_out = pd.DataFrame(rows)

    cols = ["구분"]
    def block(prod):
        return [f"{prod}_판매중량", f"{prod}_영업이익_단가", f"{prod}_영업이익_금액", f"{prod}_영업이익_%"]

    cols += block("총계")
    for p in products:
        cols += block(p)

    cols = [c for c in cols if c in df_out.columns]
    df_out = df_out[cols]

    weight_cols = [c for c in df_out.columns if "판매중량" in c]
    op_cols = [c for c in df_out.columns if "영업이익_금액" in c]

    for c in weight_cols:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1000.0, 0)) if pd.notna(x) else x)
    for c in op_cols:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1_000_000.0, 0)) if pd.notna(x) else x)

    return df_out


def build_f97(df_src: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    df = df_src.copy()
    if '값' in df.columns and '실적' not in df.columns:
        df = df.rename(columns={'값': '실적'})
    df["실적"] = df["실적"].apply(_to_number)
    df["연도"] = df["연도"].astype(int)
    df["월"] = df["월"].astype(int)

    mask = (df["연도"] == int(year)) & (df["월"] == int(month))
    df = df.loc[mask].copy()

    products = ["CHQ", "CD", "STS", "BTB", "PB"]
    df = df[df["구분1"].isin(products)]

    tmp = df.pivot_table(
        index=["구분2", "구분3", "구분1"],
        columns="구분4",
        values="실적",
        aggfunc="sum",
        fill_value=0.0
    ).reset_index()

    for col in ["매출중량", "매출금액", "영업이익"]:
        if col not in tmp.columns:
            tmp[col] = 0.0

    tmp["판매중량"] = tmp["매출중량"]
    tmp["판매금액"] = tmp["매출금액"]
    tmp["영업이익금액"] = tmp["영업이익"]
    metrics_cols = ["판매중량", "판매금액", "영업이익금액"]

    def make_row(sub: pd.DataFrame, label2: str) -> dict:
        row = {"구분2": label2}
        prod_sums = {}

        for p in products:
            d = sub[sub["구분1"] == p]
            vals = d[metrics_cols].sum() if not d.empty else pd.Series([0.0, 0.0, 0.0], index=metrics_cols)

            qty, amt, op = vals["판매중량"], vals["판매금액"], vals["영업이익금액"]

            row[f"{p}_판매중량"] = qty
            row[f"{p}_단가"] = op / qty if qty != 0 else 0.0
            row[f"{p}_영업이익"] = op
            row[f"{p}_%"] = (op / amt * 100.0) if amt != 0 else 0.0

            prod_sums[p] = (qty, amt, op)

        total_qty = sum(q for q, _, _ in prod_sums.values())
        total_amt = sum(a for _, a, _ in prod_sums.values())
        total_op = sum(o for _, _, o in prod_sums.values())

        row["총계_판매중량"] = total_qty
        row["총계_단가"] = total_op / total_qty if total_qty != 0 else 0.0
        row["총계_영업이익"] = total_op
        row["총계_%"] = (total_op / total_amt * 100.0) if total_amt != 0 else 0.0

        return row

    rows = []
    channels = ["실수요", "유통", "계"]
    for ch in channels:
        sub = tmp[tmp["구분2"] == ch] if ch != "계" else tmp
        rows.append(make_row(sub, ch))

    df_out = pd.DataFrame(rows)

    tot_q = df_out.loc[df_out["구분2"] == "계", "총계_판매중량"].values[0] if not df_out.empty else 0
    df_out["비중"] = df_out["총계_판매중량"].apply(lambda q: (q / tot_q * 100.0) if tot_q != 0 else 0.0)

    cols = ["구분2", "비중"]
    def block(prod):
        return [f"{prod}_판매중량", f"{prod}_단가", f"{prod}_영업이익", f"{prod}_%"]

    cols += block("총계")
    for p in products:
        cols += block(p)

    cols = [c for c in cols if c in df_out.columns]
    df_out = df_out[cols]

    for c in [col for col in df_out.columns if "판매중량" in col]:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1000.0, 0)) if pd.notna(x) else x)
    for c in [col for col in df_out.columns if "영업이익" in col and "%" not in col]:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1_000_000.0, 0)) if pd.notna(x) else x)

    return df_out


def build_f98(df_src: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    return build_f99(df_src, year, month)


def build_f99(df_src: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    df = df_src.copy()
    if '값' in df.columns and '실적' not in df.columns:
        df = df.rename(columns={'값': '실적'})
    df["실적"] = df["실적"].apply(_to_number)
    df["연도"] = df["연도"].astype(int)
    df["월"] = df["월"].astype(int)

    mask = (df["연도"] == int(year)) & (df["월"] == int(month))
    df = df.loc[mask].copy()

    products = ["선재영업팀", "봉강영업팀", "부산영업소", "대구영업소", "글로벌영업팀"]
    if "구분1" in df.columns:
        df = df[df["구분1"].isin(products)]

    col_cat = "분류" if "분류" in df.columns else "구분3" if "구분3" in df.columns else "구분4"
    tmp = df.pivot_table(
        index=["구분2", "구분1"],
        columns=col_cat,
        values="실적",
        aggfunc="sum",
        fill_value=0.0
    ).reset_index()

    for col in ["매출중량", "매출금액", "영업이익"]:
        if col not in tmp.columns:
            tmp[col] = 0.0

    tmp["판매중량"] = tmp["매출중량"]
    tmp["판매금액"] = tmp["매출금액"]
    tmp["영업이익금액"] = tmp["영업이익"]
    metrics_cols = ["판매중량", "판매금액", "영업이익금액"]

    def make_row(sub: pd.DataFrame, industry_label: str) -> dict:
        row = {"구분1": industry_label}
        prod_sums = {}

        for p in products:
            d = sub[sub["구분1"] == p]
            vals = d[metrics_cols].sum() if not d.empty else pd.Series([0.0, 0.0, 0.0], index=metrics_cols)

            qty, amt, op = vals["판매중량"], vals["판매금액"], vals["영업이익금액"]

            row[f"{p}_판매중량"] = qty
            row[f"{p}_판매금액"] = amt
            row[f"{p}_영업이익"] = op
            row[f"{p}_단가"] = op / qty if qty != 0 else 0.0
            row[f"{p}_%"] = (op / amt * 100.0) if amt != 0 else 0.0

            prod_sums[p] = (qty, amt, op)

        total_qty = sum(q for q, _, _ in prod_sums.values())
        total_amt = sum(a for _, a, _ in prod_sums.values())
        total_op = sum(o for _, _, o in prod_sums.values())

        row["총계_판매중량"] = total_qty
        row["총계_판매금액"] = total_amt
        row["총계_영업이익"] = total_op
        row["총계_단가"] = total_op / total_qty if total_qty != 0 else 0.0
        row["총계_%"] = (total_op / total_amt * 100.0) if total_amt != 0 else 0.0

        return row

    industry_order = ["포스코", "JFE STEEL(S)", "세아창원특수강", "현대제철", "세아베스틸", "기타"]

    rows = []
    for ind in industry_order:
        sub = tmp[tmp["구분2"] == ind]
        rows.append(make_row(sub, ind))

    total_row = make_row(tmp, "합계")
    rows.append(total_row)

    df_out = pd.DataFrame(rows)
    df_out["비중"] = 0.0

    denom = total_row["총계_판매중량"]
    if denom != 0:
        mask_industry = df_out.index < (len(df_out) - 1)
        df_out.loc[mask_industry, "비중"] = (df_out.loc[mask_industry, "총계_판매중량"] / denom * 100.0)

    df_out.loc[df_out.index == (len(df_out) - 1), "비중"] = ""

    cols = ["구분1", "비중"]
    def block(prod):
        return [f"{prod}_판매중량", f"{prod}_단가", f"{prod}_영업이익", f"{prod}_%"]

    cols += block("총계")
    for p in products:
        cols += block(p)

    cols = [c for c in cols if c in df_out.columns]
    df_out = df_out[cols]

    weight_and_sales_cols = [c for c in df_out.columns if ("판매중량" in c) or ("판매금액" in c)]
    op_profit_amount_cols = [c for c in df_out.columns if ("영업이익" in c and "%" not in c)]

    for c in weight_and_sales_cols:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1000.0, 0)) if pd.notna(x) and x != "" else x)
    for c in op_profit_amount_cols:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1_000_000.0, 0)) if pd.notna(x) and x != "" else x)

    return df_out


def build_f100(df_src: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    df = df_src.copy()
    if '값' in df.columns and '실적' not in df.columns:
        df = df.rename(columns={'값': '실적'})
    df["실적"] = df["실적"].apply(_to_number)
    df["연도"] = df["연도"].astype(int)
    df["월"] = df["월"].astype(int)

    mask = (df["연도"] == int(year)) & (df["월"] == int(month))
    df = df.loc[mask].copy()

    products = ["선재영업팀", "봉강영업팀", "부산영업소", "대구영업소", "글로벌영업팀"]
    df = df[df["구분1"].isin(products)]

    tmp = df.pivot_table(
        index=["구분2", "구분3", "구분1"],
        columns="구분4",
        values="실적",
        aggfunc="sum",
        fill_value=0.0
    ).reset_index()

    for col in ["매출중량", "매출금액", "영업이익"]:
        if col not in tmp.columns:
            tmp[col] = 0.0

    tmp["판매중량"] = tmp["매출중량"]
    tmp["판매금액"] = tmp["매출금액"]
    tmp["영업이익금액"] = tmp["영업이익"]
    metrics_cols = ["판매중량", "판매금액", "영업이익금액"]

    def make_row(sub: pd.DataFrame, label1: str, label2: str, ch_tag: str) -> dict:
        row = {"구분1": label1, "구분2": label2, "채널": ch_tag}
        prod_sums = {}

        for p in products:
            d = sub[sub["구분1"] == p]
            vals = d[metrics_cols].sum() if not d.empty else pd.Series([0.0, 0.0, 0.0], index=metrics_cols)

            qty, amt, op = vals["판매중량"], vals["판매금액"], vals["영업이익금액"]

            row[f"{p}_판매중량"] = qty
            row[f"{p}_판매금액"] = amt
            row[f"{p}_영업이익"] = op
            row[f"{p}_단가"] = op / qty if qty != 0 else 0.0
            row[f"{p}_%"] = (op / amt * 100.0) if amt != 0 else 0.0

            prod_sums[p] = (qty, amt, op)

        total_qty = sum(q for q, _, _ in prod_sums.values())
        total_amt = sum(a for _, a, _ in prod_sums.values())
        total_op = sum(o for _, _, o in prod_sums.values())

        row["총계_판매중량"] = total_qty
        row["총계_판매금액"] = total_amt
        row["총계_영업이익"] = total_op
        row["총계_단가"] = total_op / total_qty if total_qty != 0 else 0.0
        row["총계_%"] = (total_op / total_amt * 100.0) if total_amt != 0 else 0.0

        return row

    industry_order_default = ["포스코", "JFE STEEL(S)", "세아창원특수강", "현대제철", "세아베스틸", "기타"]
    industry_order_충주2 = ["JFE STEEL(S)", "세아베스틸", "포스코", "세아창원특수강", "기타", "현대제철"]

    rows = []
    for ch in ["포항공장", "충주공장", "충주2공장"]:
        base_ch = tmp[tmp["구분2"] == ch]
        rows.append(make_row(base_ch, ch, "", ch))

        order = industry_order_충주2 if ch == "충주2공장" else industry_order_default
        for ind in order:
            sub = base_ch[base_ch["구분3"] == ind]
            rows.append(make_row(sub, "", ind, ch))

    total_row = make_row(tmp, "총합계", "", "총합계")
    rows.append(total_row)

    df_out = pd.DataFrame(rows)
    df_out["비중"] = ""

    for ch in ["포항공장", "충주공장", "충주2공장"]:
        mask_ch = df_out["채널"] == ch
        if not mask_ch.any(): continue

        total_qty_series = df_out.loc[mask_ch & (df_out["구분1"] == ch), "총계_판매중량"]
        if total_qty_series.empty: continue

        denom = total_qty_series.iloc[0]
        if denom == 0: continue

        numer_mask = mask_ch & df_out["구분2"].isin(["포스코", "JFE STEEL(S)", "세아창원특수강", "현대제철", "세아베스틸", "기타"])
        df_out.loc[numer_mask, "비중"] = (df_out.loc[numer_mask, "총계_판매중량"] / denom * 100.0)

    cols = ["구분1", "구분2", "비중"]
    def block(prod):
        return [f"{prod}_판매중량", f"{prod}_단가", f"{prod}_영업이익", f"{prod}_%"]

    cols += block("총계")
    for p in products:
        cols += block(p)

    cols = [c for c in cols if c in df_out.columns]
    df_out = df_out[cols]

    weight_and_sales_cols = [c for c in df_out.columns if ("판매중량" in c) or ("판매금액" in c)]
    op_profit_amount_cols = [c for c in df_out.columns if ("영업이익" in c and "%" not in c)]

    for c in weight_and_sales_cols:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1000.0, 0)) if pd.notna(x) and x != "" else x)
    for c in op_profit_amount_cols:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1_000_000.0, 0)) if pd.notna(x) and x != "" else x)

    return df_out


def build_f101(df_src: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    df = df_src.copy()
    if '값' in df.columns and '실적' not in df.columns:
        df = df.rename(columns={'값': '실적'})
    df["실적"] = df["실적"].apply(_to_number)
    df["연도"] = df["연도"].astype(int)
    df["월"] = df["월"].astype(int)

    pivot = df.pivot_table(
        index=["연도", "월", "구분1", "구분2"],
        columns="구분3",
        values="실적",
        aggfunc="sum",
        fill_value=0.0
    ).reset_index()

    for col in ["매출중량", "매출금액", "영업이익", "인원"]:
        if col not in pivot.columns:
            pivot[col] = 0.0

    mask_ytd = (pivot["연도"] == year) & (pivot["월"] <= month)
    sub_ytd = pivot.loc[mask_ytd].copy()
    n_months_ytd = sub_ytd[["연도", "월"]].drop_duplicates()["월"].nunique()

    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)

    sub_prev = pivot.loc[(pivot["연도"] == prev_year) & (pivot["월"] == prev_month)].copy()
    sub_cur = pivot.loc[(pivot["연도"] == year) & (pivot["월"] == month)].copy()

    def prepare_period(sub: pd.DataFrame, avg_monthly: bool = False, n_months: int | None = None):
        if sub.empty:
            return pd.DataFrame(columns=["구분1", "구분2", "매출중량", "매출금액", "영업이익"]), {}

        sales_df = sub.groupby(["구분1", "구분2"], as_index=False).agg(
            매출중량=("매출중량", "sum"), 매출금액=("매출금액", "sum"), 영업이익=("영업이익", "sum")
        )

        if avg_monthly:
            if n_months is None or n_months <= 0:
                n_months = sub[["연도", "월"]].drop_duplicates()["월"].nunique()
            if n_months > 0:
                for col in ["매출중량", "매출금액", "영업이익"]:
                    sales_df[col] = sales_df[col] / n_months

        staff_map = sub[(sub["구분1"] == "정상") & (sub["인원"] > 0)].groupby("구분2")["인원"].mean().to_dict()
        return sales_df, staff_map

    sales_ytd, staff_ytd = prepare_period(sub_ytd, avg_monthly=True, n_months=n_months_ytd)
    sales_prev, staff_prev = prepare_period(sub_prev)
    sales_cur, staff_cur = prepare_period(sub_cur)

    def _metrics_for_period(sales_df: pd.DataFrame, staff_map: dict, section: str, team: str | None) -> dict:
        if section == "중계": section = "총계"

        if sales_df.empty:
            qty = amt = op = 0.0
        else:
            if section in ("정상", "매입매출"):
                cond = (sales_df["구분1"] == section)
                if team is not None: cond &= (sales_df["구분2"] == team)
                d = sales_df.loc[cond]
            elif section in ("총계", "종합계"):
                d = sales_df[sales_df["구분2"] == team] if team is not None else sales_df
            else:
                d = sales_df

            qty = d["매출중량"].sum()
            amt = d["매출금액"].sum()
            op = d["영업이익"].sum()

        staff = sum(staff_map.values()) if team is None else staff_map.get(team, 0.0)

        unit_price = amt / qty if qty != 0 else 0.0
        op_margin = (op / amt * 100.0) if amt != 0 else 0.0
        percap_qty = qty / staff if staff != 0 else 0.0
        percap_profit = op / staff if staff != 0 else 0.0

        return {
            "판매중량": qty, "판매단가": unit_price, "영업이익": op, "영업이익율": op_margin,
            "인원": staff, "인당중량": percap_qty, "인당영업이익": percap_profit,
        }

    def make_row(section: str, team: str | None, label1: str, label2: str) -> dict:
        row = {"구분1": label1, "구분2": label2}
        for prefix, s_df, s_staff in [("누적_", sales_ytd, staff_ytd), ("전월_", sales_prev, staff_prev), ("당월_", sales_cur, staff_cur)]:
            m = _metrics_for_period(s_df, s_staff, section, team)
            for k, v in m.items():
                row[f"{prefix}{k}"] = v
        return row

    teams = ["선재영업팀", "봉강영업팀", "부산영업소", "대구영업소", "글로벌영업팀"]
    rows = []

    rows.append(make_row("정상", None, "정상", ""))
    for t in teams: rows.append(make_row("정상", t, "", t))

    rows.append(make_row("매입매출", None, "매입매출", ""))
    for t in teams: rows.append(make_row("매입매출", t, "", t))

    rows.append(make_row("중계", None, "총계", ""))
    for t in teams: rows.append(make_row("총계", t, "", t))

    rows.append(make_row("총계", None, "총합계", ""))

    df_out = pd.DataFrame(rows)

    metrics_order = ["판매중량", "판매단가", "영업이익", "영업이익율", "인원", "인당중량", "인당영업이익"]
    cols_order = ["구분1", "구분2"] + [f"{p}{m}" for p in ["누적_", "전월_", "당월_"] for m in metrics_order]
    cols_order = [c for c in cols_order if c in df_out.columns]
    df_out = df_out[cols_order]

    for c in [c for c in df_out.columns if ("판매중량" in c) or ("인당중량" in c)]:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1000.0, 0)) if pd.notna(x) else x)

    for c in [c for c in df_out.columns if ("영업이익" in c and "율" not in c)]:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1_000_000.0, 0)) if pd.notna(x) else x)

    return df_out


# ── 5) 유형별 손익분석 렌더링 HTML 생성 함수 ─────────────────────────────

def _render_type_analysis_html(df: pd.DataFrame, table_type: int = 1) -> str:
    body = df.copy()
    
    # 1. 포맷터 정의
    def fmt_num(v):
        try: v = float(str(v).replace(",", "").replace("%", ""))
        except: return ""
        if v < 0: return f'<span style="color:#d32f2f;">-{abs(v):,.0f}</span>'
        return f"{v:,.0f}"

    def fmt_diff(v):
        try: v = float(str(v).replace(",", "").replace("%", ""))
        except: return ""
        if v < 0: return f'<span style="color:#d32f2f;">({abs(v):,.0f})</span>'
        return f"{v:,.0f}"

    def fmt_pct(v):
        s = str(v)
        if s.strip() == "": return ""
        try: v = float(s.replace(",", "").replace("%", ""))
        except: return s
        if v < 0: return f'<span style="color:#d32f2f;">-{abs(v):,.1f}%</span>'
        return f"{v:,.1f}%"

    th_style = "border:1px solid #aaa; background:white; padding:8px 12px; text-align:center; font-weight:700; font-size:13px; white-space:nowrap;"
    td_style = "border:1px solid #aaa; padding:6px 12px; text-align:right; font-weight:400; font-size:13px;"
    td_left_style = "border:1px solid #aaa; padding:6px 12px; text-align:left; font-weight:400; font-size:13px; white-space:nowrap;"

    # 표 1, 4, 5
    if table_type in (1, 4, 5):
        if table_type == 5:
            body["구분"] = body.apply(
                lambda r: str(r["구분1"]) if str(r["구분1"]).strip() not in ["", "nan"]
                else str(r["구분2"]) if str(r["구분2"]).strip() not in ["", "nan"] else "", axis=1
            )
            body = body.drop(columns=[c for c in ["구분1", "구분2"] if c in body.columns])
            cols = ["구분"] + [c for c in body.columns if c != "구분"]
            body = body[cols]
        elif "구분1" in body.columns and "구분" not in body.columns:
            body = body.rename(columns={"구분1": "구분"})

        num_cols = [c for c in body.columns if any(k in c for k in ["판매중량", "단가", "금액"]) and "%" not in c]
        pct_cols = [c for c in body.columns if "_%" in c or c == "비중"]

        for c in num_cols: body[c] = body[c].map(fmt_num)
        for c in pct_cols: body[c] = body[c].map(fmt_pct)

        col_names = list(body.columns)
        th_cells = "".join(f'<th style="{th_style}">{c}</th>' for c in col_names)

        tr_html = ""
        for _, row in body.iterrows():
            tds = ""
            row_label = str(row[col_names[0]]).strip()
            for ci, c in enumerate(col_names):
                val = "" if str(row[c]) == "nan" else str(row[c])
                style = td_left_style if ci == 0 else td_style
                if ci == 0:
                    tds += f'<td style="{style}">{val}</td>'
                else:
                    tds += f'<td style="{style}" title="{row_label}, {c}">{val}</td>'
            tr_html += f'<tr>{tds}</tr>\n'

        return f"""<div style="overflow-x:auto; width:100%;">
            <table style="border-collapse:collapse; width:100%; font-family:\'Noto Sans KR\', sans-serif;">
            <thead><tr>{th_cells}</tr></thead>
            <tbody>{tr_html}</tbody>
            </table></div>"""

    # 표 2, 3
    elif table_type in (2, 3):
        hdr1, hdr2, hdr3 = {c: "" for c in body.columns}, {c: "" for c in body.columns}, {c: "" for c in body.columns}
        if "구분2" in hdr1: hdr1["구분2"] = "구분"
        elif "구분1" in hdr1: hdr1["구분1"] = "구분"

        products = ["총계", "CHQ", "CD", "STS", "BTB", "PB"]
        metrics = ["판매중량", "단가", "영업이익", "%"]

        for prod in products:
            for m in metrics:
                col = f"{prod}_{m}"
                if col not in body.columns: continue
                hdr1[col] = prod
                hdr2[col] = "판매" if m == "판매중량" else "영업이익"
                hdr3[col] = "중량" if m == "판매중량" else "단가" if m == "단가" else "금액" if m == "영업이익" else "%"

        if "비중" in hdr1:
            hdr1["비중"], hdr2["비중"], hdr3["비중"] = "", "비중", ""

        hdr_df = pd.DataFrame([hdr1, hdr2, hdr3])
        body_merged = pd.concat([hdr_df, body], ignore_index=True)

        data_rows = body_merged.index >= 3
        diff_cols = [c for c in body_merged.columns if ("단가" in c or "판매금액" in c or "영업이익" in c) and not c.endswith("_%")]
        pct_cols = [c for c in body_merged.columns if c.endswith("_%")]
        ratio_cols = [c for c in body_merged.columns if c == "비중"]

        body_merged.loc[data_rows, diff_cols] = body_merged.loc[data_rows, diff_cols].map(fmt_diff)
        body_merged.loc[data_rows, pct_cols] = body_merged.loc[data_rows, pct_cols].map(fmt_pct)
        body_merged.loc[data_rows, ratio_cols] = body_merged.loc[data_rows, ratio_cols].map(fmt_pct)

        tr_html = ""
        col_names = list(body_merged.columns)
        for r_idx, row in body_merged.iterrows():
            tds = ""
            for c_idx, c in enumerate(col_names):
                val = "" if str(row[c]) == "nan" else str(row[c])
                if r_idx < 3:
                    style = f"{th_style} background-color:white;"
                    tds += f'<td style="{style}">{val}</td>'
                else:
                    style = td_left_style if c_idx in (0, 1) else td_style
                    lbl1 = str(row.iloc[0]).strip() if str(row.iloc[0]).strip() not in ["", "nan"] else ""
                    lbl2 = str(row.iloc[1]).strip() if len(row) > 1 and str(row.iloc[1]).strip() not in ["", "nan"] else ""
                    row_lbl = f"{lbl1} {lbl2}".strip()
                    col_lbl = f"{hdr1[c]} {hdr2[c]} {hdr3[c]}".strip()
                    tds += f'<td style="{style}" title="{row_lbl}, {col_lbl}">{val}</td>'
            tr_html += f'<tr>{tds}</tr>\n'

        return f"""<div style="overflow-x:auto; width:100%;">
            <table style="border-collapse:collapse; width:100%; font-family:\'Noto Sans KR\', sans-serif;">
            <tbody>{tr_html}</tbody>
            </table></div>"""

    # 표 6
    elif table_type == 6:
        if "구분1" in body.columns or "구분2" in body.columns:
            body["구분"] = body.apply(
                lambda r: str(r["구분1"]) if str(r["구분1"]).strip() not in ["", "nan"]
                else str(r["구분2"]) if str(r["구분2"]).strip() not in ["", "nan"] else "", axis=1
            )
            body = body.drop(columns=[c for c in ["구분1", "구분2"] if c in body.columns])
            cols = ["구분"] + [c for c in body.columns if c != "구분"]
            body = body[cols]

        num_cols = [c for c in body.columns if any(k in c for k in ["판매중량", "단가", "금액", "인원", "인당"]) and "%" not in c and "율" not in c]
        pct_cols = [c for c in body.columns if "영업이익율" in c or c.endswith("_%")]

        for c in num_cols: body[c] = body[c].map(fmt_num)
        for c in pct_cols: body[c] = body[c].map(fmt_pct)

        col_names = list(body.columns)
        th_cells = "".join(f'<th style="{th_style}">{c}</th>' for c in col_names)

        tr_html = ""
        for _, row in body.iterrows():
            tds = ""
            row_label = str(row[col_names[0]]).strip()
            for ci, c in enumerate(col_names):
                val = "" if str(row[c]) == "nan" else str(row[c])
                style = td_left_style if ci == 0 else td_style
                if ci == 0:
                    tds += f'<td style="{style}">{val}</td>'
                else:
                    tds += f'<td style="{style}" title="{row_label}, {c}">{val}</td>'
            tr_html += f'<tr>{tds}</tr>\n'

        return f"""<div style="overflow-x:auto; width:100%;">
            <table style="border-collapse:collapse; width:100%; font-family:\'Noto Sans KR\', sans-serif;">
            <thead><tr>{th_cells}</tr></thead>
            <tbody>{tr_html}</tbody>
            </table></div>"""

    return ""


# ── render_page ───────────────────────────────────────────────────────────

def render_page(app, year_state, month_state):

    def _render_title():
        app.markdown(
            f'<h1 style="color:#2D3748;font-size:2em;font-weight:700;">{int(year_state.value)}년 {int(month_state.value)}월 별첨</h1>',
            unsafe_allow_html=True,
        )
    app.If(lambda: True, _render_title)

    tabs = app.tabs([
        "실적요약", 
        "환율 추이", 
        "손익계산서", 
        "유형별 손익분석 (수정정상원가 기반)"
    ])

    # 1. 실적요약 탭
    with tabs[0]:
        def _render_실적요약_탭():
            year, month = int(year_state.value), int(month_state.value)
            
            sites = [
                ('전체', '1) 전체 실적요약 (해외법인 포함)'),
                ('본사', '2) 본사 실적요약'),
                ('중국', '3) 중국 실적요약'),
                ('태국', '4) 태국 실적요약'),
            ]

            for site_filter, title_text in sites:
                x_labels, sales, volume, op_profit, op_margin = _build_실적요약_data(
                    site_filter, year, month, n_months=12
                )
                
                app.markdown(
                    f'<h3 style="margin:30px 0 10px 0;font-size:1.25em;font-weight:700;color:#1E293B">{title_text}</h3>',
                    unsafe_allow_html=True
                )
                
                app.plotly_chart(
                    _build_실적요약_chart(x_labels, sales, volume, op_profit, op_margin),
                    use_container_width=True
                )
                
                app.markdown("<br>", unsafe_allow_html=True)

        app.If(lambda: True, _render_실적요약_탭)

    # 2. 환율 추이 탭
    with tabs[1]:
        def _render_환율추이_탭():
            year, month = int(year_state.value), int(month_state.value)
            x_labels, rates = _build_환율추이_data(year, month)

            app.markdown(
                '<h3 style="margin:20px 0 10px 0;font-size:1.25em;font-weight:700;color:#1E293B">1) 환율 추이 (USD, CNH, THB)</h3>',
                unsafe_allow_html=True
            )

            app.plotly_chart(
                _build_환율추이_chart(x_labels, rates),
                use_container_width=True
            )

        app.If(lambda: True, _render_환율추이_탭)

    # 3. 손익계산서 탭
    with tabs[2]:
        def _render_손익계산서_탭():
            year, month = int(year_state.value), int(month_state.value)

            df_table = _build_손익계산서_table(year, month)
            html = _손익계산서_to_html_table(df_table)
            
            memo = _get_memo(Sheets.손익계산서_메모, year, month) if hasattr(Sheets, '손익계산서_메모') else ''
            
            app.markdown(_layout100("1) 손익계산서 수정정상원가", html, memo=memo, unit="[단위: 톤, 백만원]"), unsafe_allow_html=True)

        app.If(lambda: True, _render_손익계산서_탭)

    # 4. 유형별 손익분석 탭 (6개 표 렌더링)
    with tabs[3]:
        def _render_유형별손익분석_탭():
            year, month = int(year_state.value), int(month_state.value)

            # 1) 산업군별 영업이익 (f_96)
            try:
                df_src96 = load_sheet(Sheets.f_96) if hasattr(Sheets, 'f_96') else load_sheet('f_96')
                disp96 = build_f96(df_src96, year, month)
                html96 = _render_type_analysis_html(disp96, table_type=1)
                memo96 = _get_memo(Sheets.f_96_메모, year, month) if hasattr(Sheets, 'f_96_메모') else ''
                app.markdown(_layout100("1) 산업군별 영업이익 (- B급 제외)", html96, memo=memo96, unit="[단위: 톤, 백만원]"), unsafe_allow_html=True)
                app.markdown("<br>", unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>1) 산업군별 영업이익 생성 오류: {e}</p>", unsafe_allow_html=True)

            # 2) 실수요/유통 영업이익 (f_97)
            try:
                df_src97 = load_sheet(Sheets.f_97) if hasattr(Sheets, 'f_97') else load_sheet('f_97')
                disp97 = build_f97(df_src97, year, month)
                html97 = _render_type_analysis_html(disp97, table_type=2)
                memo97 = _get_memo(Sheets.f_97_메모, year, month) if hasattr(Sheets, 'f_97_메모') else ''
                app.markdown(_layout100("2) 실수요/유통 영업이익 (- B급 제외)", html97, memo=memo97, unit="[단위: 톤, 백만원]"), unsafe_allow_html=True)
                app.markdown("<br>", unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>2) 실수요/유통 영업이익 생성 오류: {e}</p>", unsafe_allow_html=True)

            # 3) 메이커별 영업이익 (f_98)
            try:
                df_src98 = load_sheet(Sheets.f_98) if hasattr(Sheets, 'f_98') else load_sheet('f_98')
                disp98 = build_f98(df_src98, year, month)
                html98 = _render_type_analysis_html(disp98, table_type=3)
                memo98 = _get_memo(Sheets.f_98_메모, year, month) if hasattr(Sheets, 'f_98_메모') else ''
                app.markdown(_layout100("3) 메이커별 영업이익 (- B급 및 매입매출 제외)", html98, memo=memo98, unit="[단위: 톤, 백만원]"), unsafe_allow_html=True)
                app.markdown("<br>", unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>3) 메이커별 영업이익 생성 오류: {e}</p>", unsafe_allow_html=True)

            # 4) 부서/메이커별 영업이익 (f_99)
            try:
                df_src99 = load_sheet(Sheets.f_99) if hasattr(Sheets, 'f_99') else load_sheet('f_99')
                disp99 = build_f99(df_src99, year, month)
                html99 = _render_type_analysis_html(disp99, table_type=4)
                memo99 = _get_memo(Sheets.f_99_메모, year, month) if hasattr(Sheets, 'f_99_메모') else ''
                app.markdown(_layout100("4) 부서/메이커별 영업이익 (- B급 및 매입매출 제외)", html99, memo=memo99, unit="[단위: 톤, 백만원]"), unsafe_allow_html=True)
                app.markdown("<br>", unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>4) 부서/메이커별 영업이익 생성 오류: {e}</p>", unsafe_allow_html=True)

            # 5) 부서/사업장/메이커별 영업이익 (f_100)
            try:
                df_src100 = load_sheet(Sheets.f_100) if hasattr(Sheets, 'f_100') else load_sheet('f_100')
                disp100 = build_f100(df_src100, year, month)
                html100 = _render_type_analysis_html(disp100, table_type=5)
                memo100 = _get_memo(Sheets.f_100_메모, year, month) if hasattr(Sheets, 'f_100_메모') else ''
                app.markdown(_layout100("5) 부서/사업장/메이커별 영업이익 (- B급 및 매입매출 제외)", html100, memo=memo100, unit="[단위: 톤, 백만원]"), unsafe_allow_html=True)
                app.markdown("<br>", unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>5) 부서/사업장/메이커별 영업이익 생성 오류: {e}</p>", unsafe_allow_html=True)

            # 6) 부서별/인당 영업이익 (f_101)
            try:
                df_src101 = load_sheet(Sheets.f_101) if hasattr(Sheets, 'f_101') else load_sheet('f_101')
                disp101 = build_f101(df_src101, year, month)
                html101 = _render_type_analysis_html(disp101, table_type=6)
                memo101 = _get_memo(Sheets.f_101_메모, year, month) if hasattr(Sheets, 'f_101_메모') else ''
                app.markdown(_layout100("6) 부서별/인당 영업이익 (- B급 제외)", html101, memo=memo101, unit="[단위: 톤, 백만원]"), unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>6) 부서별/인당 영업이익 생성 오류: {e}</p>", unsafe_allow_html=True)

        app.If(lambda: True, _render_유형별손익분석_탭)