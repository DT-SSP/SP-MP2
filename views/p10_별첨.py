import datetime
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from data.loader import load_sheet
from data.config import Sheets
from views.common import (
    parse as _parse, fmt as _fmt,
    prev_month as _prev, drop_empty as _drop_empty,
    layout100 as _layout100, layout64 as _layout64,
    TH as _TH, TD_NUM as _TD_NUM, ROW_HDR_LBL as ROW_HDR_LBL, ROW_HDR_NUM as ROW_HDR_NUM, ROW_ITEM as ROW_ITEM,
    html_table as _html_table,
    C_NAVY as _C_NAVY, C_ORANGE, C_RED as _C_RED, C_CHART_SEC, C_CHART_GRID, C_LT_GRAY as _C_LT_GRAY,
    sort_by_order as _sort,
    TD_RED as _TD_RED, TD_SUB_NUM as _TD_SUB_NUM, TD_SUB_RED as _TD_SUB_RED,
    ROW_SEC, ROW_HDR_RED,
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
        textfont=dict(color='#1E293B', size=10),
        yaxis='y2', connectgaps=True
    ))

    max_bar = max(max(sales_list or [1]), max(volume_list or [1]))
    max_line = max(op_profit_list) if op_profit_list else 100
    min_line = min(op_profit_list) if op_profit_list else 0

    # 💡 [Fix] 그래프 잘림 방지를 위해 마진/여백/범례 위치 및 자동 크기 최적화
    fig.update_layout(
        barmode='group', height=400,
        margin=dict(l=40, r=40, t=40, b=40),
        autosize=True,
        legend=dict(
            orientation='h', y=-0.15, x=0.5, xanchor='center',
            font=dict(size=11, color='#334155'), bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            tickfont=dict(size=10, color='#64748B'),
            showgrid=False, linecolor='#CBD5E1', linewidth=1, showline=True,
            automargin=True
        ),
        yaxis=dict(
            domain=[0, 0.60], showgrid=True, gridcolor=C_CHART_GRID, gridwidth=1,
            range=[0, max_bar * 1.25], showticklabels=False, showline=False, zeroline=False,
            automargin=True
        ),
        yaxis2=dict(
            domain=[0.65, 1.0], range=[min_line * 1.2 if min_line < 0 else 0, max_line * 1.45],
            showgrid=False, showticklabels=False, showline=False, zeroline=False,
            automargin=True
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=11, family='sans-serif'),
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
            marker=dict(color=color_map[currency], size=7),
            line=dict(color=color_map[currency], width=2.5),
            text=text_labels, textposition='top center',
            textfont=dict(color='#1E293B', size=10), connectgaps=True
        ))

    all_vals = [v for curr in rates for v in rates[curr] if v > 0]
    max_val = max(all_vals) if all_vals else 1500
    min_val = min(all_vals) if all_vals else 0

    # 💡 [Fix] 그래프 잘림 방지 최적화
    fig.update_layout(
        height=400, margin=dict(l=40, r=40, t=40, b=40),
        autosize=True,
        legend=dict(
            orientation='h', y=-0.15, x=0.5, xanchor='center',
            font=dict(size=11, color='#334155'), bgcolor='rgba(0,0,0,0)',
        ),
        xaxis=dict(
            tickfont=dict(size=10, color='#64748B'),
            showgrid=False, linecolor='#CBD5E1', linewidth=1, showline=True,
            automargin=True
        ),
        yaxis=dict(
            showgrid=False, range=[min_val * 0.8, max_val * 1.15],
            showticklabels=False, showline=False, zeroline=False,
            automargin=True
        ),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(size=11, family='sans-serif'),
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


# ── 4) 유형별 손익분석 데이터 및 HTML 렌더러 모듈 ─────────────────────

def _build_산업군별_영업이익_table(year: int, month: int) -> pd.DataFrame:
    df_src = load_sheet(Sheets.산업군별영업이익_DB) 
    df = df_src.copy()
    
    for c in ["구분1", "구분2", "구분3", "구분4"]:
        if c in df.columns:
            df[c] = df[c].fillna('').astype(str).str.strip()
            
    val_col = '실적' if '실적' in df.columns else '값'
    df[val_col] = df[val_col].apply(_to_number)
    df["연도"] = pd.to_numeric(df["연도"], errors='coerce').fillna(0).astype(int)
    df["월"] = pd.to_numeric(df["월"], errors='coerce').fillna(0).astype(int)

    mask = (df["연도"] == int(year)) & (df["월"] == int(month))
    df = df.loc[mask].copy()

    products = ["CHQ", "CD", "STS", "BTB", "PB"]

    tmp = df.pivot_table(
        index=["구분2", "구분3", "구분1"], columns="구분4", values=val_col, aggfunc="sum", fill_value=0.0
    ).reset_index()

    for col in ["매출중량", "매출금액", "영업이익"]:
        if col not in tmp.columns: tmp[col] = 0.0

    tmp["판매중량"], tmp["판매금액"], tmp["영업이익금액"] = tmp["매출중량"], tmp["매출금액"], tmp["영업이익"]
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
    r_내수 = make_row(base_내수, "내수")
    r_내수["_depth"] = 0
    rows.append(r_내수)
    for ind in industry_order:
        r_ind = make_row(base_내수[base_내수["구분3"] == ind], ind)
        r_ind["_depth"] = 1
        rows.append(r_ind)

    base_수출 = tmp[tmp["구분2"] == "수출"]
    r_수출 = make_row(base_수출, "수출")
    r_수출["_depth"] = 0
    rows.append(r_수출)
    for ind in industry_order:
        r_ind = make_row(base_수출[base_수출["구분3"] == ind], ind)
        r_ind["_depth"] = 1
        rows.append(r_ind)

    r_tot = make_row(tmp, "총계")
    r_tot["_depth"] = 0
    rows.append(r_tot)
    for ind in industry_order:
        r_ind = make_row(tmp[tmp["구분3"] == ind], ind)
        r_ind["_depth"] = 1
        rows.append(r_ind)

    df_out = pd.DataFrame(rows)
    cols = ["구분", "_depth"] + [f"{prod}_{m}" for prod in ["총계"] + products for m in ["판매중량", "영업이익_단가", "영업이익_금액", "영업이익_%"]]
    cols = [c for c in cols if c in df_out.columns]
    df_out = df_out[cols]

    for c in [c for c in df_out.columns if "판매중량" in c]:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1000.0, 0)) if pd.notna(x) else x)
    for c in [c for c in df_out.columns if "영업이익_금액" in c and "%" not in c]:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1_000_000.0, 0)) if pd.notna(x) else x)

    return df_out


def _build_개별_그룹_dfs(df_out: pd.DataFrame, target_items: list, base_col_name: str = "구분") -> dict:
    item_dfs = {}
    
    for item in target_items:
        item_cols = [c for c in df_out.columns if c.startswith(f"{item}_")]
        sub_df = pd.DataFrame()
        sub_df[base_col_name] = df_out[base_col_name]
        if "_depth" in df_out.columns:
            sub_df["_depth"] = df_out["_depth"]
            
        for c in item_cols:
            clean_col = c.replace(f"{item}_", "")
            sub_df[clean_col] = df_out[c]
            
        item_dfs[item] = sub_df
        
    return item_dfs


def _유형별_영업이익_to_html_table(df: pd.DataFrame) -> str:
    depths = df['_depth'].tolist() if '_depth' in df.columns else [1] * len(df)
    render_df = df.drop(columns=['_depth'], errors='ignore')

    _pad = {0: '8px', 1: '20px', 2: '36px'}
    _prefix = {0: '', 1: '&nbsp;&nbsp;&nbsp;', 2: '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'}

    rows_html = ''
    for (_, row), depth in zip(render_df.iterrows(), depths):
        d = int(depth) if str(depth).lstrip('-').isdigit() else 1
        label = str(row.iloc[0])
        is_sub = (d == 0) or label in ["내수", "수출", "총계", "합계", "실수요", "유통", "계", "포항공장", "충주공장", "충주2공장", "총합계", "정상", "매입매출"]
        pad = _pad.get(d, '20px')
        prefix = _prefix.get(d, '&nbsp;&nbsp;&nbsp;')

        cells = ''
        for i, val in enumerate(row):
            if i == 0:
                s = str(val)
                if is_sub:
                    lbl_st = (f'padding:5px 8px;padding-left:{pad};text-align:left;'
                              f'background:{_C_LT_GRAY};font-weight:600;'
                              f'border-bottom:1px solid #e2e8f0')
                else:
                    lbl_st = (f'padding:5px 8px;padding-left:{pad};text-align:left;'
                              f'border-bottom:1px solid #e2e8f0;')
                cells += f'<td style="{lbl_st}">{prefix}{s}</td>'
            else:
                col_name = render_df.columns[i]
                is_pct = "%" in col_name or "비중" in col_name or "율" in col_name
                if pd.isna(val) or val == '':
                    s = ''
                else:
                    try:
                        v_num = float(val)
                        s = f"{v_num:,.1f}%" if is_pct else _fmt(v_num)
                    except:
                        s = str(val)
                        
                if s.startswith('-'):
                    cells += f'<td style="{_TD_SUB_RED if is_sub else _TD_RED}">{s}</td>'
                else:
                    cells += f'<td style="{_TD_SUB_NUM if is_sub else _TD_NUM}">{s}</td>'
                    
        rows_html += f'<tr style="vertical-align:middle">{cells}</tr>'

    headers = ''.join(f'<th style="{_TH}">{c}</th>' for c in render_df.columns)
    return _html_table(f'<tr>{headers}</tr>', rows_html)


def _라디오_선택_section(title, per_item_dfs, item_labels, prefix="type_op", memo='', unit='[단위: 톤, 백만원, %]'):
    safe = [c.replace(' ', '_') for c in item_labels]

    hide_sel = ', '.join(f'#fp_{prefix}_{s}' for s in safe)
    css = f'{hide_sel}{{display:none}}'
    for s in safe:
        css += (f'#ft_{prefix}_{s}:checked~#fp_{prefix}_{s}{{display:block!important}}'
                f'#ft_{prefix}_{s}:checked~.ftbar>#fl_{prefix}_{s}'
                f'{{background:{_C_NAVY}!important;color:white!important;border-color:{_C_NAVY}!important}}')

    inputs = ''.join(
        f'<input type="radio" id="ft_{prefix}_{s}" name="ftab_{prefix}" {"checked" if i == 0 else ""} '
        f'style="position:absolute;opacity:0;pointer-events:none">'
        for i, s in enumerate(safe)
    )

    tab_bar = f'<div class="ftbar" style="display:flex;margin-bottom:6px;border-bottom:2px solid {_C_NAVY}">'
    tab_bar += ''.join(
        f'<label id="fl_{prefix}_{s}" for="ft_{prefix}_{s}" style="padding:5px 16px;cursor:pointer;'
        f'border:1px solid #DEE2E6;border-bottom:none;margin-right:2px;'
        f'font-size:0.9em;font-weight:500;border-radius:4px 4px 0 0;'
        f'background:white;color:#555">{item}</label>'
        for item, s in zip(item_labels, safe)
    )
    tab_bar += '</div>'

    panels = ''.join(
        f'<div id="fp_{prefix}_{s}">{_유형별_영업이익_to_html_table(per_item_dfs[item])}</div>'
        for item, s in zip(item_labels, safe)
    )

    tab_html = f'<style>{css}</style>' + inputs + tab_bar + panels
    return _layout100(title, tab_html, memo, unit)


def _build_부서_메이커별_영업이익_table(year: int, month: int) -> pd.DataFrame:
    df_src = load_sheet(Sheets.부서메이커별영업이익_DB)
    df = df_src.copy()
    
    if '값' in df.columns and '실적' not in df.columns:
        df = df.rename(columns={'값': '실적'})
    df["실적"] = df["실적"].apply(_to_number)
    df["연도"] = df["연도"].astype(int)
    df["월"] = df["월"].astype(int)

    mask = (df["연도"] == int(year)) & (df["월"] == int(month))
    df = df.loc[mask].copy()

    teams = ["선재영업팀", "봉강영업팀", "부산영업소", "대구영업소", "글로벌영업팀"]
    if "구분1" in df.columns:
        df = df[df["구분1"].isin(teams)]

    col_cat = "분류" if "분류" in df.columns else "구분3" if "구분3" in df.columns else "구분4"
    tmp = df.pivot_table(
        index=["구분2", "구분1"], columns=col_cat, values="실적", aggfunc="sum", fill_value=0.0
    ).reset_index()

    for col in ["매출중량", "매출금액", "영업이익"]:
        if col not in tmp.columns: tmp[col] = 0.0

    tmp["판매중량"], tmp["판매금액"], tmp["영업이익금액"] = tmp["매출중량"], tmp["매출금액"], tmp["영업이익"]
    metrics_cols = ["판매중량", "판매금액", "영업이익금액"]

    def make_row(sub: pd.DataFrame, maker_label: str) -> dict:
        row = {"구분": maker_label}
        team_sums = {}
        for t in teams:
            d = sub[sub["구분1"] == t]
            vals = d[metrics_cols].sum() if not d.empty else pd.Series([0.0, 0.0, 0.0], index=metrics_cols)
            qty, amt, op = vals["판매중량"], vals["판매금액"], vals["영업이익금액"]
            row[f"{t}_판매중량"] = qty
            row[f"{t}_영업이익_단가"] = op / qty if qty != 0 else 0.0
            row[f"{t}_영업이익_금액"] = op
            row[f"{t}_영업이익_%"] = (op / amt * 100.0) if amt != 0 else 0.0
            team_sums[t] = (qty, amt, op)

        total_qty = sum(q for q, _, _ in team_sums.values())
        total_amt = sum(a for _, a, _ in team_sums.values())
        total_op = sum(o for _, _, o in team_sums.values())

        row["총계_판매중량"] = total_qty
        row["총계_영업이익_단가"] = total_op / total_qty if total_qty != 0 else 0.0
        row["총계_영업이익_금액"] = total_op
        row["총계_영업이익_%"] = (total_op / total_amt * 100.0) if total_amt != 0 else 0.0
        return row

    industry_order = ["포스코", "JFE STEEL(S)", "세아창원특수강", "현대제철", "세아베스틸", "기타"]
    rows = []
    for ind in industry_order:
        sub = tmp[tmp["구분2"] == ind]
        r = make_row(sub, ind)
        r["_depth"] = 1
        rows.append(r)

    total_row = make_row(tmp, "합계")
    total_row["_depth"] = 0
    rows.append(total_row)

    df_out = pd.DataFrame(rows)
    cols = ["구분", "_depth"] + [f"{grp}_{m}" for grp in ["총계"] + teams for m in ["판매중량", "영업이익_단가", "영업이익_금액", "영업이익_%"]]
    cols = [c for c in cols if c in df_out.columns]
    df_out = df_out[cols]

    for c in [c for c in df_out.columns if "판매중량" in c]:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1000.0, 0)) if pd.notna(x) else x)
    for c in [c for c in df_out.columns if "영업이익_금액" in c and "%" not in c]:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1_000_000.0, 0)) if pd.notna(x) else x)

    return df_out


def _build_부서_사업장_메이커별_영업이익_table(year: int, month: int) -> pd.DataFrame:
    df_src = load_sheet(Sheets.부서사업장메이커별영업이익_DB)
    df = df_src.copy()
    if '값' in df.columns and '실적' not in df.columns:
        df = df.rename(columns={'값': '실적'})
    df["실적"] = df["실적"].apply(_to_number)
    df["연도"] = df["연도"].astype(int)
    df["월"] = df["월"].astype(int)

    mask = (df["연도"] == int(year)) & (df["월"] == int(month))
    df = df.loc[mask].copy()

    teams = ["선재영업팀", "봉강영업팀", "부산영업소", "대구영업소", "글로벌영업팀"]
    df = df[df["구분1"].isin(teams)]

    tmp = df.pivot_table(
        index=["구분2", "구분3", "구분1"], columns="구분4", values="실적", aggfunc="sum", fill_value=0.0
    ).reset_index()

    for col in ["매출중량", "매출금액", "영업이익"]:
        if col not in tmp.columns: tmp[col] = 0.0

    tmp["판매중량"], tmp["판매금액"], tmp["영업이익금액"] = tmp["매출중량"], tmp["매출금액"], tmp["영업이익"]
    metrics_cols = ["판매중량", "판매금액", "영업이익금액"]

    def make_row(sub: pd.DataFrame, label: str) -> dict:
        row = {"구분": label}
        team_sums = {}
        for t in teams:
            d = sub[sub["구분1"] == t]
            vals = d[metrics_cols].sum() if not d.empty else pd.Series([0.0, 0.0, 0.0], index=metrics_cols)
            qty, amt, op = vals["판매중량"], vals["판매금액"], vals["영업이익금액"]
            row[f"{t}_판매중량"] = qty
            row[f"{t}_영업이익_단가"] = op / qty if qty != 0 else 0.0
            row[f"{t}_영업이익_금액"] = op
            row[f"{t}_영업이익_%"] = (op / amt * 100.0) if amt != 0 else 0.0
            team_sums[t] = (qty, amt, op)

        total_qty = sum(q for q, _, _ in team_sums.values())
        total_amt = sum(a for _, a, _ in team_sums.values())
        total_op = sum(o for _, _, o in team_sums.values())

        row["총계_판매중량"] = total_qty
        row["총계_영업이익_단가"] = total_op / total_qty if total_qty != 0 else 0.0
        row["총계_영업이익_금액"] = total_op
        row["총계_영업이익_%"] = (total_op / total_amt * 100.0) if total_amt != 0 else 0.0
        return row

    industry_order_default = ["포스코", "JFE STEEL(S)", "세아창원특수강", "현대제철", "세아베스틸", "기타"]
    industry_order_충주2 = ["JFE STEEL(S)", "세아베스틸", "포스코", "세아창원특수강", "기타", "현대제철"]

    rows = []
    for ch in ["포항공장", "충주공장", "충주2공장"]:
        base_ch = tmp[tmp["구분2"] == ch]
        r_ch = make_row(base_ch, ch)
        r_ch["_depth"] = 0
        rows.append(r_ch)
        
        order = industry_order_충주2 if ch == "충주2공장" else industry_order_default
        for ind in order:
            sub = base_ch[base_ch["구분3"] == ind]
            r_ind = make_row(sub, ind)
            r_ind["_depth"] = 1
            rows.append(r_ind)

    r_tot = make_row(tmp, "총합계")
    r_tot["_depth"] = 0
    rows.append(r_tot)

    df_out = pd.DataFrame(rows)
    cols = ["구분", "_depth"] + [f"{grp}_{m}" for grp in ["총계"] + teams for m in ["판매중량", "영업이익_단가", "영업이익_금액", "영업이익_%"]]
    cols = [c for c in cols if c in df_out.columns]
    df_out = df_out[cols]

    for c in [c for c in df_out.columns if "판매중량" in c]:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1000.0, 0)) if pd.notna(x) else x)
    for c in [c for c in df_out.columns if "영업이익_금액" in c and "%" not in c]:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1_000_000.0, 0)) if pd.notna(x) else x)

    return df_out


def _build_부서별_인당_영업이익_table(year: int, month: int) -> pd.DataFrame:
    df_src = load_sheet(Sheets.부서별인당영업이익_DB)
    df = df_src.copy()
    if '값' in df.columns and '실적' not in df.columns:
        df = df.rename(columns={'값': '실적'})
    df["실적"] = df["실적"].apply(_to_number)
    df["연도"] = df["연도"].astype(int)
    df["월"] = df["월"].astype(int)

    pivot = df.pivot_table(
        index=["연도", "월", "구분1", "구분2"], columns="구분3", values="실적", aggfunc="sum", fill_value=0.0
    ).reset_index()

    for col in ["매출중량", "매출금액", "영업이익", "인원"]:
        if col not in pivot.columns: pivot[col] = 0.0

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
            if n_months is None or n_months <= 0: n_months = sub[["연도", "월"]].drop_duplicates()["월"].nunique()
            if n_months > 0:
                for col in ["매출중량", "매출금액", "영업이익"]: sales_df[col] = sales_df[col] / n_months

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

    def make_row(section: str, team: str | None, label: str) -> dict:
        row = {"구분": label}
        for prefix, s_df, s_staff in [("누적_", sales_ytd, staff_ytd), ("전월_", sales_prev, staff_prev), ("당월_", sales_cur, staff_cur)]:
            m = _metrics_for_period(s_df, s_staff, section, team)
            for k, v in m.items(): row[f"{prefix}{k}"] = v
        return row

    teams = ["선재영업팀", "봉강영업팀", "부산영업소", "대구영업소", "글로벌영업팀"]
    rows = []

    r_norm = make_row("정상", None, "정상")
    r_norm["_depth"] = 0
    rows.append(r_norm)
    for t in teams: 
        r_t = make_row("정상", t, t)
        r_t["_depth"] = 1
        rows.append(r_t)

    r_buy = make_row("매입매출", None, "매입매출")
    r_buy["_depth"] = 0
    rows.append(r_buy)
    for t in teams: 
        r_t = make_row("매입매출", t, t)
        r_t["_depth"] = 1
        rows.append(r_t)

    r_tot = make_row("중계", None, "총계")
    r_tot["_depth"] = 0
    rows.append(r_tot)
    for t in teams: 
        r_t = make_row("총계", t, t)
        r_t["_depth"] = 1
        rows.append(r_t)

    r_all = make_row("총계", None, "총합계")
    r_all["_depth"] = 0
    rows.append(r_all)

    df_out = pd.DataFrame(rows)
    metrics_order = ["판매중량", "판매단가", "영업이익", "영업이익율", "인원", "인당중량", "인당영업이익"]
    cols_order = ["구분", "_depth"] + [f"{p}{m}" for p in ["누적_", "전월_", "당월_"] for m in metrics_order]
    cols_order = [c for c in cols_order if c in df_out.columns]
    df_out = df_out[cols_order]

    for c in [c for c in df_out.columns if ("판매중량" in c) or ("인당중량" in c)]:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1000.0, 0)) if pd.notna(x) else x)
    for c in [c for c in df_out.columns if ("영업이익" in c and "율" not in c)]:
        df_out[c] = df_out[c].apply(lambda x: int(round(float(x) / 1_000_000.0, 0)) if pd.notna(x) else x)

    return df_out


def _build_인당_영업이익_period_dfs(df_out: pd.DataFrame) -> dict:
    # 💡 [Fix] 요청사항 반영: '총계' 탭 제외 후 ['누적', '전월', '당월'] 만 생성
    periods = ["누적", "전월", "당월"]
    period_dfs = {}

    metrics = ["판매중량", "판매단가", "영업이익", "영업이익율", "인원", "인당중량", "인당영업이익"]
    for p in periods:
        sub_df = pd.DataFrame()
        sub_df["구분"] = df_out["구분"]
        sub_df["_depth"] = df_out["_depth"]
        for m in metrics:
            col_key = f"{p}_{m}"
            if col_key in df_out.columns:
                sub_df[m] = df_out[col_key]
        period_dfs[p] = sub_df

    return period_dfs


# ── render_page ───────────────────────────────────────────────────────────

def render_page(app, year_state, month_state):

    def _render_title():
        app.markdown(
            f'<h1 style="color:#404448">{int(year_state.value)}년 {int(month_state.value)}월 별첨</h1>',
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
                    f'<h3 style="margin:20px 0 10px 0;font-size:1.1em;font-weight:600;color:#404448">{title_text}</h3>',
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
                '<h3 style="margin:20px 0 10px 0;font-size:1.1em;font-weight:600;color:#404448">1) 환율 추이 (USD, CNH, THB)</h3>',
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
            
            app.markdown(_layout100("1) 손익계산서 수정정상원가", html, memo=memo, unit="(단위: 톤, 백만원)"), unsafe_allow_html=True)

        app.If(lambda: True, _render_손익계산서_탭)

    # 4. 유형별 손익분석 탭
    with tabs[3]:
        def _render_유형별손익분석_탭():
            year, month = int(year_state.value), int(month_state.value)
            teams_labels = ["총계", "선재영업팀", "봉강영업팀", "부산영업소", "대구영업소", "글로벌영업팀"]

            # 1) 산업군별 영업이익
            try:
                df1 = _build_산업군별_영업이익_table(year, month)
                per_item_dfs1 = _build_개별_그룹_dfs(df1, ["총계", "CHQ", "CD", "STS", "BTB", "PB"])
                item_labels1 = ["총계", "CHQ", "CD", "STS", "BTB", "PB"]
                memo1 = ''
                app.markdown(_라디오_선택_section("1) 산업군별 영업이익 (B급 제외)", per_item_dfs1, item_labels1, prefix="ind_op", memo=memo1, unit="(단위: 톤, 백만원, %)"), unsafe_allow_html=True)
                app.markdown("<br>", unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>1) 산업군별 영업이익 생성 오류: {e}</p>", unsafe_allow_html=True)

            # 4) 부서/메이커별 영업이익
            try:
                df4 = _build_부서_메이커별_영업이익_table(year, month)
                per_team_dfs4 = _build_개별_그룹_dfs(df4, teams_labels)
                memo4 = ''
                app.markdown(_라디오_선택_section("4) 부서/메이커별 영업이익 (B급 및 매입매출 제외)", per_team_dfs4, teams_labels, prefix="dept_maker_op", memo=memo4, unit="(단위: 톤, 백만원, %)"), unsafe_allow_html=True)
                app.markdown("<br>", unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>4) 부서/메이커별 영업이익 생성 오류: {e}</p>", unsafe_allow_html=True)

            # 5) 부서/사업장/메이커별 영업이익
            try:
                df5 = _build_부서_사업장_메이커별_영업이익_table(year, month)
                per_team_dfs5 = _build_개별_그룹_dfs(df5, teams_labels)
                memo5 = ''
                app.markdown(_라디오_선택_section("5) 부서/사업장/메이커별 영업이익 (B급 및 매입매출 제외)", per_team_dfs5, teams_labels, prefix="dept_site_maker_op", memo=memo5, unit="(단위: 톤, 백만원, %)"), unsafe_allow_html=True)
                app.markdown("<br>", unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>5) 부서/사업장/메이커별 영업이익 생성 오류: {e}</p>", unsafe_allow_html=True)

            # 6) 부서별/인당 영업이익 (총계 탭 제외, 누적/전월/당월 탭 적용)
            try:
                df6 = _build_부서별_인당_영업이익_table(year, month)
                per_period_dfs6 = _build_인당_영업이익_period_dfs(df6)
                period_labels6 = ["누적", "전월", "당월"]
                memo6 = ''
                app.markdown(_라디오_선택_section("6) 부서별/인당 영업이익 (B급 제외)", per_period_dfs6, period_labels6, prefix="per_capita_op", memo=memo6, unit="(단위: 톤, 백만원, %)"), unsafe_allow_html=True)
            except Exception as e:
                app.markdown(f"<p style='color:#d32f2f;'>6) 부서별/인당 영업이익 생성 오류: {e}</p>", unsafe_allow_html=True)

        app.If(lambda: True, _render_유형별손익분석_탭)