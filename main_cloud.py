import mimetypes
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')

import datetime
import logging
import os
import threading
from contextvars import ContextVar
from urllib.parse import urlencode

import httpx
import pandas as pd
import violit as vl
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer
from violit.context import layout_ctx, session_ctx

from data.config import Sheets
from data.loader import load_sheet, preload_all, refresh_all
from views import p1_실적요약, p2_손익분석, p3_매출분석, p4_생산분석, p5_비용분석, p6_재고자산, p7_채권분석, p8_인원현황, p9_해외법인, p10_별첨
import asyncio 
import time  
from views.common import prev_month

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

# ── 1. 인증 및 권한 설정 ────────────────────────────────────────────────
# 데이터 새로고침 버튼을 볼 수 있는 관리자 이메일 목록
_ADMIN_USERS: set[str] = {"gawon.yi@seah.co.kr", "jaeseok.heo@seah.co.kr", "daeseong.kang@seah.co.kr", "sejong.hyun@seah.co.kr", "sangwoo.ryu"}

# 접근 허용 이메일 목록 (환경변수 ALLOWED_EMAILS에 쉼표로 구분해 등록)
_ALLOWED_EMAILS: set[str] = {
    e.strip()
    for e in os.environ.get("ALLOWED_EMAILS", "").split(",")
    if e.strip()
}

# Cloud Run은 내부적으로 HTTP로 처리하므로 redirect_uri를 env로 고정
_BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")


# ── 2. 페이지 및 시트 매핑 설정 ──────────────────────────────────────────
PAGE_SHEETS_MAP = {
    "1. 실적요약": [
            Sheets.손익_DB, Sheets.손익_메모, Sheets.손익_국내_메모,
            Sheets.현금흐름표_연결_DB, Sheets.현금흐름표_연결_메모,
            Sheets.재무상태표_DB, Sheets.재무상태표_메모, Sheets.재무상태표_국내_메모,
            Sheets.회전일_DB, Sheets.회전일_메모, Sheets.회전일_국내_메모,
            Sheets.품목손익_DB, Sheets.품목손익_메모, Sheets.수정원가기준손익_DB,Sheets.수정원가기준손익_메모,
            Sheets.원재료입고기초단가차이_DB, Sheets.원재료입고단가차이_거래처기준_DB,
            Sheets.제품수불표_DB, Sheets.현금흐름표_별도_DB, Sheets.현금흐름표_별도_메모,
            Sheets.안정성_DB, Sheets.안정성_메모, Sheets.수익성_DB, Sheets.수익성_메모_연결, Sheets.수익성_대표이사_DB, Sheets.수익성_대표이사_메모,
            Sheets.판매계획및실적_DB, Sheets.판매계획및실적_메모, Sheets.이익계획및실적_DB
        ],
    "2. 손익분석": [
        Sheets.손익요약표_DB, Sheets.손익요약표_메모,
        Sheets.수출환율차이_DB, Sheets.수출환율차이_메모,
        Sheets.QD_DB, Sheets.QD_메모,
        Sheets.포스코JFE입고가격_DB, Sheets.포스코JFE입고가격_메모,
        Sheets.포스코지원금_DB, Sheets.포스코지원금_메모,
        Sheets.포스코JFE투입비중_DB, Sheets.포스코JFE투입비중_메모,
        Sheets.메이커별입고추이_DB, Sheets.메이커별입고추이_메모,
        Sheets.제조가공비_DB, Sheets.제조가공비_메모,
        Sheets.판매비와관리비_DB, Sheets.판매비와관리비_메모,
        Sheets.성과급및격려금_DB, Sheets.성과급및격려금_메모,
        Sheets.전월대비손익차이_DB, Sheets.전월대비손익차이_메모,
    ],
    "3. 매출분석": [
        Sheets.계획대비매출실적_DB, Sheets.계획대비매출실적_메모,
        Sheets.등급별판매구성_DB, Sheets.등급별판매구성_메모,
        Sheets.CHQ제품판매현황_B급제외_DB, Sheets.CHQ제품판매현황_B급제외_메모,
        Sheets.CHQ제품판매현황_산업중국재_DB, Sheets.CHQ제품판매현황_산업중국재_메모,
        Sheets.CD제품판매현황_B급제외_DB, Sheets.CD제품판매현황_B급제외_메모,
        Sheets.CD제품판매현황_산업중국재_DB, Sheets.CD제품판매현황_산업중국재_메모,
        Sheets.비가공품판매현황_DB, Sheets.비가공품판매현황_메모,
        Sheets.동일거래매입매출현황_DB, Sheets.동일거래매입매출현황_메모,
        Sheets.PSI_매입매출포함_DB, Sheets.PSI_매입매출제외_DB
    ],
    "4. 생산분석": [
        Sheets.전체생산실적_DB, Sheets.전체생산실적_메모,
        Sheets.부적합발생추이_포항_충주_충주2_DB,
        Sheets.부적합발생추이_포항_메모, Sheets.부적합발생추이_충주_충주2_메모
    ],
    "5. 비용분석": [
        Sheets.부재료사용량_DB, Sheets.부재료사용량_포항_메모, Sheets.부재료사용량_충주_메모, Sheets.부재료사용량_충주2_메모,
        Sheets.월평균클레임_DB, Sheets.당월클레임_메모,
        Sheets.당월클레임_DB,
        Sheets.영업외비용_DB, Sheets.영업외비용_메모, 
    ],
    "6. 재고자산분석": [ 
        Sheets.재고현황_DB, Sheets.재고현황_메모,
        Sheets.연령별재고현황_DB, Sheets.연령별재고현황_메모,
        Sheets.총재고_메모,
        Sheets.등급별재고현황_DB, Sheets.등급별재고현황_메모
    ],
    "7. 채권분석": [
        Sheets.외상매출받을어음_DB, Sheets.외상매출받을어음_메모,
        Sheets.부서별채권기일_DB, Sheets.부서별채권기일_메모,
        Sheets.결제조건초과채권_DB, Sheets.결제조건초과채권_메모,
        Sheets.부서별초과채권_DB, Sheets.부서별초과채권_메모
    ],
    "8. 인원현황": [
        Sheets.인원_DB, Sheets.인원_메모
    ],
    "9. 해외법인실적": [
        Sheets.해외손익요약_DB, Sheets.해외손익요약_중국_메모, Sheets.해외손익요약_태국_메모,
        Sheets.해외현금흐름_DB, Sheets.해외현금흐름_중국_메모, Sheets.해외현금흐름_태국_메모,
        Sheets.해외재무상태표_DB, Sheets.해외재무상태표_중국_메모, Sheets.해외재무상태표_태국_메모,
        Sheets.해외등급별판매_DB, Sheets.해외등급별판매_메모,
        Sheets.해외판매현황_DB, Sheets.해외판매현황_CHQ_메모, Sheets.해외판매현황_비가공품_메모, Sheets.해외판매현황_제품임가공_메모,
        Sheets.해외손익차이_DB, Sheets.해외손익차이_메모,
        Sheets.해외재고자산_DB, Sheets.해외재고자산_중국_메모, Sheets.해외재고자산_태국_메모,
        Sheets.해외부적합장기재고_DB, Sheets.해외부적합장기재고_중국_메모, Sheets.해외부적합장기재고_태국_메모,
        Sheets.해외연령별재고_DB, Sheets.해외연령별재고_중국_메모, Sheets.해외연령별재고_태국_메모,
        Sheets.해외채권_DB, Sheets.해외채권_중국_메모, Sheets.해외채권_태국_메모,
        Sheets.해외인원_DB, Sheets.해외인원_메모, Sheets.해외인원_생산량_메모
    ],
    "10. 별첨" : [
            Sheets.전체실적요약_DB, Sheets.환율_DB, Sheets.손익계산서_DB,Sheets.산업군별영업이익_DB,
            Sheets.메이커별영업이익_DB, Sheets.실수요유통영업이익_DB,
            Sheets.산업군별영업이익_메모, Sheets.실수요유통영업이익_메모, Sheets.메이커별영업이익_메모,
            Sheets.부서메이커별영업이익_메모, Sheets.부서사업장메이커별영업이익_메모, Sheets.부서별인당영업이익_메모,
            Sheets.부서메이커별영업이익_DB, Sheets.부서사업장메이커별영업이익_DB, Sheets.부서별인당영업이익_DB
            ]
    }

_REFRESH_STATES = {page: vl.State(f"refresh_status_{page}", "idle") for page in PAGE_SHEETS_MAP}
_REFRESH_LOCK = threading.Lock()

def _get_연도_목록():
    df = load_sheet(Sheets.등급별판매구성_메모)
    return sorted(pd.to_numeric(df['연도'], errors='coerce').dropna().astype(int).unique().tolist())


# ── 3. Google OAuth 미들웨어 및 로직 ──────────────────────────────────────
_GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO  = "https://www.googleapis.com/oauth2/v3/userinfo"

_signer: URLSafeSerializer | None = None

def _get_signer() -> URLSafeSerializer:
    global _signer
    if _signer is None:
        _signer = URLSafeSerializer(os.environ.get("SESSION_SECRET_KEY", "fallback-secret"), salt="at-mp-auth")
    return _signer

def _parse_auth_cookie(scope) -> str | None:
    headers = dict(scope.get("headers", []))
    raw = headers.get(b"cookie", b"").decode("latin-1")
    cookies = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k.strip()] = v.strip()
    token = cookies.get("at_auth")
    if not token:
        return None
    try:
        return _get_signer().loads(token)
    except BadSignature:
        return None

# Violit ss_sid → email 매핑
_sid_email: dict[str, str] = {}

def _parse_ss_sid(scope) -> str | None:
    headers = dict(scope.get("headers", []))
    raw = headers.get(b"cookie", b"").decode("latin-1")
    for part in raw.split(";"):
        part = part.strip()
        if part.startswith("ss_sid="):
            return part[len("ss_sid="):]
    return None

# HTTP 요청용 ContextVar
_current_user: ContextVar[str | None] = ContextVar("current_user", default=None)

def get_current_user() -> str | None:
    """렌더 및 웹소켓 Context 내에서 현재 사용자 이메일 동적 판단"""
    user = _current_user.get()
    if user:
        return user
    
    try:
        sid = session_ctx.get()
        if sid and sid in _sid_email:
            return _sid_email[sid]
    except Exception:
        pass

    return _sid_email.get("_latest_auth_email")

def is_authenticated() -> bool:
    return get_current_user() is not None

_AUTH_PUBLIC_PREFIXES = ("/auth/", "/_violit/", "/static/", "/favicon")

class _GoogleAuthMiddleware:
    def __init__(self, app):
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            email = _parse_auth_cookie(scope)
            sid = _parse_ss_sid(scope)
            
            if email:
                if sid:
                    _sid_email[sid] = email
                _sid_email["_latest_auth_email"] = email

        if scope["type"] == "websocket":
            await self._app(scope, receive, send)
            return

        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        path = scope.get("path", "")
        email = _parse_auth_cookie(scope)
        token = _current_user.set(email)
        
        try:
            if email is None and not any(path.startswith(p) for p in _AUTH_PUBLIC_PREFIXES):
                response = RedirectResponse("/auth/google")
                await response(scope, receive, send)
                return
            await self._app(scope, receive, send)
        finally:
            _current_user.reset(token)

# ── 4. Violit 앱 초기화 ───────────────────────────────────────────────────
app = vl.App(title="선재사업부문 경영실적 대시보드", container_width="100%", db="./app.db")
app.fastapi.add_middleware(_GoogleAuthMiddleware)

@app.fastapi.on_event("startup")
async def _on_startup():
    all_sheets = [v for k, v in vars(Sheets).items()
                  if not k.startswith("_") and isinstance(v, tuple)]
    threading.Thread(target=preload_all, args=(all_sheets,), daemon=True).start()

# ── 5. OAuth 라우터 (FastAPI) ──────────────────────────────────────────────
def _redirect_uri(request: Request) -> str:
    base = _BASE_URL or str(request.base_url).rstrip("/")
    return base + "/auth/callback"

@app.fastapi.get("/auth/google")
async def auth_google(request: Request):
    redirect_uri = _redirect_uri(request)
    params = {
        "client_id":     os.environ.get("GOOGLE_CLIENT_ID", ""),
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "online",
        "prompt":        "select_account",
    }
    return RedirectResponse(_GOOGLE_AUTH_URL + "?" + urlencode(params))


@app.fastapi.get("/auth/callback")
async def auth_callback(request: Request, code: str = None, error: str = None):
    if error or not code:
        return HTMLResponse(
            f'<p style="font-family:sans-serif">로그인 실패: {error or "코드 없음"} '
            f'<a href="/auth/google">다시 시도</a></p>'
        )

    redirect_uri = _redirect_uri(request)
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(_GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     os.environ.get("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
        })
        token_data = token_resp.json()

    access_token = token_data.get("access_token")
    if not access_token:
        return HTMLResponse(
            '<p style="font-family:sans-serif">토큰 발급 실패. '
            '<a href="/auth/google">다시 시도</a></p>'
        )

    async with httpx.AsyncClient() as client:
        info_resp = await client.get(
            _GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_info = info_resp.json()

    email: str = user_info.get("email", "")
    if email not in _ALLOWED_EMAILS:
        return HTMLResponse(
            f'<p style="font-family:sans-serif;color:red">'
            f'접근 권한이 없습니다. 등록된 이메일이 아닙니다. ({email})</p>',
            status_code=403,
        )

    auth_token = _get_signer().dumps(email)
    response = RedirectResponse("/", status_code=302)
    
    response.set_cookie(
        "at_auth", auth_token,
        httponly=True, samesite="lax",
        max_age=86400 * 30,
        secure=True,
        path="/"
    )
    return response

@app.fastapi.get("/auth/logout")
async def auth_logout():
    response = RedirectResponse("/auth/google", status_code=302)
    response.delete_cookie("at_auth")
    return response


# ── 6. 공통 상태 및 사이드바 ───────────────────────────────────────────────
_today = datetime.date.today()
_default_year, _default_month = prev_month(_today.year, _today.month, 1)
year_state  = vl.State("selected_year",  _default_year)
month_state = vl.State("selected_month", _default_month)

_LOGOUT_BTN = (
    '<a href="/auth/logout" style="display:block;width:100%;box-sizing:border-box;'
    'padding:0.4em 0.75em;border:1px solid #d1d5db;border-radius:6px;'
    'text-align:center;text-decoration:none;color:inherit;font-size:0.9em;'
    'cursor:pointer;background:transparent;margin-top:16px;">로그아웃</a>'
)

def _sidebar_controls():
    연도_목록 = _get_연도_목록()
    cur_year = year_state.value
    default_year_idx = 연도_목록.index(cur_year) if cur_year in 연도_목록 else len(연도_목록) - 1
    
    _token = layout_ctx.set("main")
    try:
        app.divider()
        app.subheader("조회 기간")
        app.selectbox("연도", 연도_목록, index=default_year_idx, on_change=lambda v: year_state.set(int(v)))
        app.selectbox("월", list(range(1, 13)), index=month_state.value - 1, on_change=lambda v: month_state.set(int(v)))
        app.divider()
        
        email = get_current_user() or ""
        is_admin = email in _ADMIN_USERS

        if is_admin:
            # 1. 현재 페이지 다운로드 JS 스크립트 추가 (xlsx 단일 시트 다운로드 적용)
            current_search_period = f"{year_state.value}년{month_state.value:02d}월"
            download_js = r"""<style>
.dl-btn-container { width: 100%; margin-top: 8px; }
.dl-btn-container p { margin: 0 !important; padding: 0 !important; }
.custom-dl-btn {
    width: 100%; padding: 8px 16px; background-color: #ffffff; color: #404448;
    border: 1px solid #ced4da; border-radius: 4px; font-size: 14px; font-weight: 500;
    cursor: pointer; transition: all 0.2s ease; box-sizing: border-box; text-align: center;
}
.custom-dl-btn:hover { background-color: #f8f9fa; border-color: #adb5bd; }
</style>
<div class="dl-btn-container">
    <button class="custom-dl-btn" onclick="downloadAllTables()">현재 페이지 다운로드</button>
</div>
<script>
// 라이브러리 동적 로드 후 실행
function downloadAllTables() {
    if (typeof XLSX === 'undefined') {
        let script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js';
        script.onload = function() {
            executeExcelDownload();
        };
        document.head.appendChild(script);
    } else {
        executeExcelDownload();
    }
}

function executeExcelDownload() {
    let tables = Array.from(document.querySelectorAll('table'));
    if (tables.length === 0) { alert("현재 페이지에 다운로드할 표가 없습니다."); return; }
    
    let wb = XLSX.utils.book_new();
    let ws_data = []; 
    let tableCount = 0;
    
    tables.forEach((table) => {
        if (table.rows.length === 0) return;
        tableCount++;
        
        // 표 구분을 위한 빈 줄과 제목 추가
        if (tableCount > 1) {
            ws_data.push([]);
            ws_data.push([]);
        }
        ws_data.push([`=== 표 ${tableCount} ===`]);
        
        Array.from(table.rows).forEach(row => {
            let rowData = Array.from(row.cells).map(cell => {
                let clone = cell.cloneNode(true);
                let brs = clone.querySelectorAll('br');
                for(let i=0; i<brs.length; i++) { brs[i].replaceWith(' '); }
                return clone.textContent.trim();
            });
            ws_data.push(rowData);
        });
    });
    
    if(tableCount === 0) { alert("다운로드할 데이터가 없습니다."); return; }
    
    let ws = XLSX.utils.aoa_to_sheet(ws_data);
    XLSX.utils.book_append_sheet(wb, ws, "데이터");
    
    let pageName = "다운로드";
    if (window.location.hash) {
        pageName = decodeURIComponent(window.location.hash.substring(1));
        pageName = pageName.replace(/[^a-zA-Z0-9가-힣_\-\. ]/g, '').trim();
    }
    if (!pageName) pageName = document.title || "선재경영실적";
    
    let now = new Date();
    let yyyy = now.getFullYear();
    let MM = String(now.getMonth() + 1).padStart(2, '0');
    let dd = String(now.getDate()).padStart(2, '0');
    let hh = String(now.getHours()).padStart(2, '0');
    let mm = String(now.getMinutes()).padStart(2, '0');
    let ss = String(now.getSeconds()).padStart(2, '0');
    let timeStr = `${yyyy}${MM}${dd}_${hh}${mm}${ss}`;
    
    let searchPeriod = "__SEARCH_PERIOD__";
    let fileName = `${pageName}_${searchPeriod}_${timeStr}.xlsx`;
    
    XLSX.writeFile(wb, fileName);
}
</script>""".replace("__SEARCH_PERIOD__", current_search_period)
            
            app.markdown(download_js, unsafe_allow_html=True)
            app.markdown('<style>.nav-container{display:none}</style>', unsafe_allow_html=True)
            app.divider()

            # 2. 관리자 전용 새로고침 및 네비게이션 버튼
            def make_refresh_callback(t_sheets, p_name):
                def _do_refresh():
                    if _REFRESH_LOCK.acquire(blocking=False):
                        _REFRESH_STATES[p_name].set("running")
                        
                        async def _bg_task():
                            try:
                                await asyncio.to_thread(refresh_all, t_sheets, max_workers=2)
                                _REFRESH_STATES[p_name].set("done")
                                app.switch_page(p_name)
                                await asyncio.sleep(2)
                                _REFRESH_STATES[p_name].set("idle")
                            except Exception as e:
                                logging.error(f"[refresh] {p_name} 실패: {e}")
                                _REFRESH_STATES[p_name].set("error")
                            finally:
                                _REFRESH_LOCK.release()

                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(_bg_task())
                        except RuntimeError:
                            threading.Thread(target=lambda: asyncio.run(_bg_task()), daemon=True).start()
                return _do_refresh

            for page_name, target_sheets in PAGE_SHEETS_MAP.items():
                c1, c2 = app.columns([8, 2])
                with c1:
                    app.button(page_name, on_click=lambda p=page_name: app.switch_page(p), key=f"nav_{page_name}")
                with c2:
                    status = _REFRESH_STATES[page_name].value
                    if status == "idle":
                        app.button("🔄", on_click=make_refresh_callback(target_sheets, page_name), key=f"ref_{page_name}")
                    elif status == "running":
                        app.markdown("<div style='padding-top:8px;'>⏳</div>", unsafe_allow_html=True)
                    elif status == "done":
                        app.button("✅", on_click=make_refresh_callback(target_sheets, page_name), key=f"done_{page_name}")
                    elif status == "error":
                        app.button("❌", on_click=lambda p=page_name: _REFRESH_STATES[p].set("idle"), key=f"err_{page_name}")

        # 3. OAuth 로그아웃 버튼
        app.markdown(_LOGOUT_BTN, unsafe_allow_html=True)

    finally:
        layout_ctx.reset(_token)

with app.sidebar:
    app.If(lambda: True, _sidebar_controls)


# ── 7. 페이지 설정 ────────────────────────────────────────────────────────
def _protected(render_fn):
    def _page():
        render_fn(app, year_state, month_state)
    return _page

app.navigation([
    vl.Page(_protected(p1_실적요약.render_page),     title="1. 실적요약"),
    vl.Page(_protected(p2_손익분석.render_page),     title="2. 손익분석"),
    vl.Page(_protected(p3_매출분석.render_page),     title="3. 매출분석"),
    vl.Page(_protected(p4_생산분석.render_page),     title="4. 생산분석"),
    vl.Page(_protected(p5_비용분석.render_page),     title="5. 비용분석"),
    vl.Page(_protected(p6_재고자산.render_page),     title="6. 재고자산분석"),
    vl.Page(_protected(p7_채권분석.render_page),     title="7. 채권분석"),
    vl.Page(_protected(p8_인원현황.render_page),     title="8. 인원현황"),
    vl.Page(_protected(p9_해외법인.render_page),     title="9. 해외법인실적"),
    vl.Page(_protected(p10_별첨.render_page),        title="10. 별첨"),
])

if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 8000)))