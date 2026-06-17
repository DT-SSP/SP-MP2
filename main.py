import os
import secrets
import urllib.parse
import requests as _req
from typing import Optional
from sqlmodel import SQLModel, Field
from fastapi import Request
from fastapi.responses import RedirectResponse, HTMLResponse

import violit as vl
from violit.state import SESSION_STORE
from violit.context import session_ctx

from views import p1_실적요약, p2_손익분석, p3_매출분석, p4_생산분석
from views import p5_비용분석, p6_재고자산, p7_기타, p8_해외법인

# ── Google OAuth 설정 ──────────────────────────────────────────────────────
try:
    from google_config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, ALLOWED_DOMAIN
except ImportError:
    GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI  = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    ALLOWED_DOMAIN       = os.environ.get("ALLOWED_DOMAIN", "")

# ── 사용자 모델 ───────────────────────────────────────────────────────────
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str           # Google 이메일 주소
    hashed_password: str    # 사용 안 함 (Google 인증만 사용)

# ── 앱 초기화 ─────────────────────────────────────────────────────────────
app = vl.App(title="AT사업본부 경영실적 대시보드", container_width="100%", db="./app.db")
app.setup_auth(User, require_auth=False)

# CSRF 상태 토큰 임시 저장소 {state_token: sid}
_pending_states: dict = {}


# ── 배포 환경: ALLOWED_EMAILS 환경변수로 사용자 자동 등록 ─────────────────
@app.fastapi.on_event("startup")
async def _on_startup():
    allowed = os.environ.get("ALLOWED_EMAILS", "")
    if not allowed:
        return
    for email in [e.strip().lower() for e in allowed.split(",") if e.strip()]:
        if app.db.first(User, User.username == email) is None:
            app.db.add(User(username=email, hashed_password=secrets.token_hex(32)))


# ── Google OAuth 라우트 ───────────────────────────────────────────────────

@app.fastapi.get("/auth/google")
def _google_redirect(state: str = ""):
    if not GOOGLE_CLIENT_ID:
        return HTMLResponse(
            "<h3 style='font-family:sans-serif'>설정 오류</h3>"
            "<p style='font-family:sans-serif'>GOOGLE_CLIENT_ID가 설정되지 않았습니다.<br>"
            "google_config.py를 확인해 주세요.</p>",
            status_code=500,
        )
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }
    return RedirectResponse(
        "https://accounts.google.com/o/oauth2/auth?" + urllib.parse.urlencode(params)
    )


@app.fastapi.get("/auth/google/callback")
def _google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error or not code:
        return RedirectResponse("/")

    # code → access_token
    token_resp = _req.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        return HTMLResponse(
            "<p style='font-family:sans-serif'>Google 인증 실패. 다시 시도해 주세요.</p>",
            status_code=400,
        )

    access_token = token_resp.json().get("access_token", "")

    # access_token → 사용자 이메일
    info_resp = _req.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if info_resp.status_code != 200:
        return HTMLResponse(
            "<p style='font-family:sans-serif'>사용자 정보 조회 실패. 다시 시도해 주세요.</p>",
            status_code=400,
        )

    email = info_resp.json().get("email", "").lower()

    # 1차: 회사 도메인 제한
    if ALLOWED_DOMAIN and not email.endswith(f"@{ALLOWED_DOMAIN}"):
        return HTMLResponse(
            f"<div style='font-family:sans-serif;padding:40px;max-width:400px'>"
            f"<h3 style='color:#c53030'>접근 거부</h3>"
            f"<p><b>{email}</b> 계정은 허용되지 않습니다.</p>"
            f"<p>회사 계정(<b>@{ALLOWED_DOMAIN}</b>)으로 로그인해 주세요.</p>"
            f"<a href='/'>← 돌아가기</a></div>",
            status_code=403,
        )

    # 2차: 사전 등록 계정(화이트리스트) 확인
    user = app.db.first(User, User.username == email)
    if user is None:
        return HTMLResponse(
            f"<div style='font-family:sans-serif;padding:40px;max-width:400px'>"
            f"<h3 style='color:#c53030'>접근 권한 없음</h3>"
            f"<p><b>{email}</b> 계정에 접근 권한이 없습니다.</p>"
            f"<p>관리자에게 권한 부여를 요청해 주세요.</p>"
            f"<a href='/'>← 돌아가기</a></div>",
            status_code=403,
        )

    # 세션에 인증 정보 저장
    sid = _pending_states.pop(state, None) or request.cookies.get("ss_sid", "")
    if sid:
        store = SESSION_STORE.get(sid)
        if store is None:
            store = {}
            SESSION_STORE[sid] = store
        store["auth_user_id"] = user.id

    return RedirectResponse("/")


_GOOGLE_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="20" height="20">'
    '<path fill="#4285F4" d="M47.5 24.6c0-1.6-.1-3.1-.4-4.6H24v8.7h13.2c-.6 3-2.3 5.5-4.9 7.2v6h7.9c4.6-4.3 7.3-10.6 7.3-17.3z"/>'
    '<path fill="#34A853" d="M24 48c6.5 0 12-2.1 16-5.8l-7.9-6c-2.2 1.5-5 2.3-8.1 2.3-6.2 0-11.5-4.2-13.4-9.9H2.4v6.2C6.4 42.5 14.6 48 24 48z"/>'
    '<path fill="#FBBC05" d="M10.6 28.6c-.5-1.5-.8-3-.8-4.6s.3-3.1.8-4.6v-6.2H2.4C.9 16.3 0 20 0 24s.9 7.7 2.4 10.8l8.2-6.2z"/>'
    '<path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.5l6.8-6.8C35.9 2.4 30.4 0 24 0 14.6 0 6.4 5.5 2.4 13.2l8.2 6.2C12.5 13.7 17.8 9.5 24 9.5z"/>'
    '</svg>'
)


# ── 페이지 래퍼 (로그아웃 버튼) ───────────────────────────────────────────

def _nav_go(title: str):
    p = app._navigation_pages_by_title.get(title)
    if p:
        for s in app._navigation_states:
            s.set(p.key)


def _protected(render_fn):
    def _page():
        if not app.auth.is_authenticated():
            sid = session_ctx.get() or ""
            state = secrets.token_urlsafe(16)
            _pending_states[state] = sid
            app.markdown(
                '<div style="display:flex;flex-direction:column;align-items:center;'
                'justify-content:center;padding:80px 20px;text-align:center">'
                '<p style="font-size:2.5em;margin:0 0 12px">🔒</p>'
                '<p style="font-size:1.15em;color:#4c1d95;font-weight:600;margin:0 0 6px">'
                '로그인이 필요합니다</p>'
                '<p style="color:#666;font-size:0.9em;margin:0 0 24px">'
                '이 자료는 권한이 있는 임직원만 열람할 수 있습니다.</p>'
                f'<a href="/auth/google?state={state}" style="'
                'display:inline-flex;align-items:center;gap:10px;'
                'padding:12px 20px;background:#fff;border:1px solid #dadce0;'
                'border-radius:8px;color:#3c4043;text-decoration:none;'
                'font-size:0.95em;font-weight:500;'
                'box-shadow:0 1px 3px rgba(0,0,0,.08);">'
                f'{_GOOGLE_ICON_SVG}Google 계정으로 로그인'
                '</a>'
                '</div>',
                unsafe_allow_html=True,
            )
            return

        render_fn(app)

        with app.sidebar:
            app.divider()

            def _do_logout():
                app.auth.logout()
                _nav_go("1. 실적요약")

            app.button("로그아웃", on_click=_do_logout)
    return _page


# ── 네비게이션 ────────────────────────────────────────────────────────────

app.navigation([
    vl.Page(_protected(p1_실적요약.render_page),        title="1. 실적요약"),
    vl.Page(_protected(p2_손익분석.render_page),        title="2. 손익분석"),
    vl.Page(_protected(p3_매출분석.render_page),        title="3. 매출분석"),
    vl.Page(_protected(p4_생산분석.render_page),        title="4. 생산분석"),
    vl.Page(_protected(p5_비용분석.render_page),        title="5. 비용분석"),
    vl.Page(_protected(p6_재고자산.render_page),        title="6. 재고자산분석"),
    vl.Page(_protected(p7_기타.render_page),            title="7. 기타"),
    vl.Page(_protected(p8_해외법인.render_page),        title="8. 해외법인실적"),
])

if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 8000)))
