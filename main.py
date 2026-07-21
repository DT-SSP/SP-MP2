import mimetypes
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')

import datetime
import logging
import os
import threading
from typing import Optional
from sqlmodel import SQLModel, Field

import pandas as pd
import violit as vl
from violit.context import layout_ctx

from data.config import Sheets
from data.loader import load_sheet, preload_all, refresh_all
from views import p1_실적요약 ,p2_손익분석, p3_매출분석, p4_생산분석, p5_비용분석, p6_재고자산
#from views import p2_손익분석, p3_매출분석, p4_생산분석
#from views import p5_비용분석, p6_재고자산, p7_기타, p8_해외법인

# 데이터 새로고침 버튼을 볼 수 있는 관리자 아이디 목록
_ADMIN_USERS: set[str] = {"gawon.yi", "jaeseok.heo"}

_REFRESH_STATE: dict = {"status": "idle"}  # idle | running | done | error
_REFRESH_LOCK = threading.Lock()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


def _get_연도_목록():
    df = load_sheet(Sheets.손익_DB)
    return sorted(pd.to_numeric(df['연도'], errors='coerce').dropna().astype(int).unique().tolist())


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    hashed_password: str


def _run_refresh_bg():
    all_sheets = [v for k, v in vars(Sheets).items()
                  if not k.startswith("_") and isinstance(v, tuple)]
    try:
        refresh_all(all_sheets, max_workers=2)
        _REFRESH_STATE["status"] = "done"
    except Exception as e:
        logging.error(f"[refresh] 실패: {e}")
        _REFRESH_STATE["status"] = "error"
    finally:
        _REFRESH_LOCK.release()


app = vl.App(title="선재사업부문 경영실적 대시보드",container_width="100%", db="./app.db")
app.setup_auth(User, require_auth=False)


@app.fastapi.on_event("startup")
async def _on_startup():
    all_sheets = [v for k, v in vars(Sheets).items()
                  if not k.startswith("_") and isinstance(v, tuple)]
    preload_all(all_sheets)


login_error = vl.State("login_error", False)

# Session-level year/month state — lives outside page functions so the
# static sidebar can update them and all views can read them.
_today = datetime.date.today()
year_state  = vl.State("selected_year",  _today.year)
month_state = vl.State("selected_month", _today.month)


# ── App-level sidebar (registered statically so it works immediately
#    after login without needing an F5 refresh) ──────────────────────
def _sidebar_controls():
    if not app.auth.is_authenticated():
        return
    연도_목록 = _get_연도_목록()
    cur_year = year_state.value
    default_year_idx = 연도_목록.index(cur_year) if cur_year in 연도_목록 else len(연도_목록) - 1
    
    _token = layout_ctx.set("main")
    try:
        app.divider()
        app.subheader("조회 기간")
        app.selectbox("연도", 연도_목록, index=default_year_idx,
                      on_change=lambda v: year_state.set(int(v)))
        app.selectbox("월", list(range(1, 13)), index=month_state.value - 1,
                      on_change=lambda v: month_state.set(int(v)))
        app.divider()
        def _do_logout():
            app.auth.logout()
            app.switch_page("Login")
        app.button("로그아웃", on_click=_do_logout)

        # 관리자 전용: 데이터 새로고침
        user = app.auth.current_user()
        if user and user.username in _ADMIN_USERS:
            status = _REFRESH_STATE["status"]
            if status == "running":
                app.markdown(
                    '<p style="font-size:0.8em;color:#888;margin:4px 0">⏳ 데이터 갱신 중...<br>'
                    '<span style="font-size:0.9em">완료 후 페이지를 새로고침하세요</span></p>',
                    unsafe_allow_html=True,
                )
            elif status == "done":
                app.markdown(
                    '<p style="font-size:0.8em;color:#16a34a;margin:4px 0">✅ 갱신 완료!</p>',
                    unsafe_allow_html=True,
                )
                app.button("확인", on_click=lambda: _REFRESH_STATE.update({"status": "idle"}))
            elif status == "error":
                app.markdown(
                    '<p style="font-size:0.8em;color:#dc2626;margin:4px 0">❌ 갱신 실패 (서버 로그 확인)</p>',
                    unsafe_allow_html=True,
                )
                app.button("확인", on_click=lambda: _REFRESH_STATE.update({"status": "idle"}))
            else:
                def _do_refresh():
                    if _REFRESH_LOCK.acquire(blocking=False):
                        _REFRESH_STATE["status"] = "running"
                        threading.Thread(target=_run_refresh_bg, daemon=True).start()
                app.button("데이터 새로고침", on_click=_do_refresh)
    finally:
        layout_ctx.reset(_token)



with app.sidebar:
    app.If(app.auth.is_authenticated, _sidebar_controls)


def login_page():
    _, col, _ = app.columns([1, 2, 1])
    with col:
        # 변경점: 타이틀 색상을 세아 다크 네이비(#323C47)로 변경하고, 자물쇠 아이콘에 오렌지(#EA5421) 포인트 추가
        app.markdown(
            '<div style="text-align:center;padding:48px 0 28px">'
            '<p style="font-size:1.4em;font-weight:700;color:#323C47;margin:0"><span style="color:#EA5421;">🔒</span> 선재사업부문 경영실적 대시보드</p>'
            '<p style="color:#666;font-size:0.9em;margin:8px 0 0">권한이 있는 임직원만 열람할 수 있습니다.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        username = app.text_input("아이디", placeholder="아이디를 입력하세요")
        password = app.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")

        if login_error.value:
            # 변경점: 에러 메시지 색상을 세아 경고 레드(#DC2626)로 변경
            app.markdown(
                '<p style="color:#DC2626;font-size:0.9em;margin:4px 0">아이디 또는 비밀번호가 올바르지 않습니다.</p>',
                unsafe_allow_html=True,
            )

        def _do_login():
            if app.auth.login(username.value, password.value):
                app.switch_page("1. 실적요약")
            else:
                login_error.set(True)

        app.button("로그인", on_click=_do_login)


def _protected(render_fn):
    def _page():
        if not app.auth.is_authenticated():
            # 변경점: 접근 권한 경고 아이콘과 텍스트를 세아 경고 레드(#DC2626)로 통일성 있게 변경
            app.markdown(
                '<div style="display:flex;flex-direction:column;align-items:center;'
                'justify-content:center;padding:80px 20px;text-align:center">'
                '<p style="font-size:2em;margin:0 0 12px">🔒</p>'
                '<p style="font-size:1.1em;color:#DC2626;font-weight:600;margin:0 0 8px">'
                '접근 권한이 없습니다</p>'
                '<p style="color:#666;font-size:0.9em;margin:0 0 24px">'
                '이 자료는 로그인 후 열람할 수 있습니다.</p>'
                '</div>',
                unsafe_allow_html=True,
            )
            return
        render_fn(app, year_state, month_state)
    return _page

def _public(render_fn):
    def _page():
        render_fn(app, year_state, month_state)
    return _page

app.navigation([
    vl.Page(login_page,                              title="Login"),
    vl.Page(_protected(p1_실적요약.render_page),     title="1. 실적요약"),
    vl.Page(_protected(p2_손익분석.render_page),     title="2. 손익분석"),
    vl.Page(_protected(p3_매출분석.render_page),     title="3. 매출분석"),
    vl.Page(_protected(p4_생산분석.render_page),     title="4. 생산분석"),
    vl.Page(_protected(p5_비용분석.render_page),     title="5. 비용분석"),
    vl.Page(_protected(p6_재고자산.render_page),     title="6. 재고자산분석"),
])

'''
app.navigation([
    vl.Page(_public(p1_실적요약.render_page),        title="1. 실적요약")
])
'''

'''
app.navigation([
    vl.Page(login_page,                              title="Login"),
    vl.Page(_protected(p1_실적요약.render_page),     title="1. 실적요약"),
    vl.Page(_protected(p2_손익분석.render_page),     title="2. 손익분석"),
    vl.Page(_protected(p3_매출분석.render_page),     title="3. 매출분석"),
    vl.Page(_protected(p4_생산분석.render_page),     title="4. 생산분석"),
    vl.Page(_protected(p5_비용분석.render_page),     title="5. 비용분석"),
    vl.Page(_protected(p6_재고자산.render_page),     title="6. 재고자산분석"),
    vl.Page(_protected(p7_기타.render_page),         title="7. 기타"),
    vl.Page(_protected(p8_해외법인.render_page),     title="8. 해외법인실적"),
])
'''

if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 8000)))