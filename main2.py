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
from views import p1_실적요약 ,p2_손익분석, p3_매출분석, p4_생산분석, p5_비용분석, p6_재고자산, p7_채권분석, p8_기타, p9_해외법인
import asyncio 
import time  
from views.common import prev_month


# 데이터 새로고침 버튼을 볼 수 있는 관리자 아이디 목록
_ADMIN_USERS: set[str] = {"gawon.yi", "jaeseok.heo", "daeseong.kang", "sejong.hyun"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


PAGE_SHEETS_MAP = {
    "1. 실적요약": [
        Sheets.손익_DB, Sheets.손익_메모, Sheets.손익_국내_메모,
        Sheets.현금흐름표_연결_DB, Sheets.현금흐름표_연결_메모,
        Sheets.재무상태표_DB, Sheets.재무상태표_메모, Sheets.재무상태표_국내_메모,
        Sheets.회전일_DB, Sheets.회전일_메모, Sheets.회전일_국내_메모,
        Sheets.품목손익_DB, Sheets.품목손익_메모, Sheets.수정원가기준손익_DB,
        Sheets.원재료입고기초단가차이_DB, Sheets.원재료입고단가차이_거래처기준_DB,
        Sheets.제품수불표_DB, Sheets.현금흐름표_별도_DB, Sheets.현금흐름표_별도_메모,
        Sheets.안정성_DB, Sheets.안정성_메모, Sheets.수익성_DB, Sheets.수익성_메모,
        Sheets.판매계획및실적_DB, Sheets.판매계획및실적_메모
    ],
    "2. 손익분석": [
        Sheets.손익요약표_DB, Sheets.손익요약표_메모,
        Sheets.수출환율차이_DB, Sheets.수출환율차이_메모,
        Sheets.QD_DB, Sheets.포스코JFE입고가격_DB, Sheets.포스코JFE입고가격_메모,
        Sheets.포스코JFE투입비중_DB, Sheets.포스코JFE투입비중_메모,
        Sheets.메이커별입고추이_DB, Sheets.메이커별입고추이_메모,
        Sheets.제조가공비_DB, Sheets.제조가공비_메모,
        Sheets.판매비와관리비_DB, Sheets.판매비와관리비_메모,
        Sheets.성과급및격려금_DB, Sheets.성과급및격려금_메모
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
        Sheets.부재료사용량_DB, Sheets.부재료사용량_메모,
        Sheets.부재료단가추이_DB, Sheets.부재료단가추이_메모,
        Sheets.월평균클레임_DB, Sheets.월평균클레임_메모,
        Sheets.당월클레임_DB,
        Sheets.영업외비용_DB, Sheets.영업외비용_메모
    ],
    "6. 재고자산분석": [ 
        Sheets.재고현황_DB, Sheets.재고현황_메모,
        Sheets.연령별재고현황_DB, Sheets.연령별재고현황_메모,
        Sheets.등급별재고현황_DB, Sheets.등급별재고현황_메모
    ],
    "7. 채권분석": [
        Sheets.외상매출받을어음_DB, Sheets.외상매출받을어음_메모,
        Sheets.부서별채권기일_DB, Sheets.부서별채권기일_메모,
        Sheets.결제조건초과채권_DB, Sheets.결제조건초과채권_메모,
        Sheets.부서별초과채권_DB, Sheets.부서별초과채권_메모
    ],
    "8. 기타": [
        Sheets.인원_DB
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
    ]
}

_REFRESH_STATES = {page: vl.State(f"refresh_status_{page}", "idle") for page in PAGE_SHEETS_MAP}
_REFRESH_LOCK = threading.Lock()

def _get_연도_목록():
    df = load_sheet(Sheets.손익_DB)
    return sorted(pd.to_numeric(df['연도'], errors='coerce').dropna().astype(int).unique().tolist())


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    hashed_password: str

def _run_refresh_bg(target_sheets: list, page_name: str):
    is_success = False
    try:
        # 지정된 시트만 새로고침 진행
        refresh_all(target_sheets, max_workers=2)
        _REFRESH_STATES[page_name].set("done") # 완료 상태로 업데이트
        is_success = True
    except Exception as e:
        logging.error(f"[refresh] {page_name} 실패: {e}")
        _REFRESH_STATES[page_name].set("error") # 에러 상태로 업데이트
    finally:
        # 다른 페이지가 새로고침을 할 수 있도록 락을 먼저 해제
        _REFRESH_LOCK.release()
    
    # 락 해제 후, 성공적으로 끝났다면 2초 뒤에 다시 idle 상태로 복구
    if is_success:
        time.sleep(2)  # 2초 동안 ✅ 표시 유지
        _REFRESH_STATES[page_name].set("idle") # 🔄 아이콘으로 복구

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

_default_year, _default_month = prev_month(_today.year, _today.month, 1)
year_state  = vl.State("selected_year",  _default_year)
month_state = vl.State("selected_month", _default_month)


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
        app.selectbox("연도", 연도_목록, index=default_year_idx, on_change=lambda v: year_state.set(int(v)))
        app.selectbox("월", list(range(1, 13)), index=month_state.value - 1, on_change=lambda v: month_state.set(int(v)))
        app.divider()
        
        def _do_logout():
            app.auth.logout()
            app.switch_page("Login")
        app.button("로그아웃", on_click=_do_logout)

        # ------------------ 변경된 부분 ------------------
        # 관리자 전용: 각 페이지 버튼 옆에 작은 새로고침 버튼
        user = app.auth.current_user()
        if user and user.username in _ADMIN_USERS:
            app.divider()

            # 파이썬 반복문 내에서 콜백 함수 꼬임을 방지하기 위한 클로저 헬퍼
            def make_refresh_callback(t_sheets, p_name):
                # UI 프레임워크 규칙에 맞게 겉은 일반(동기) 함수로 선언
                def _do_refresh():
                    if _REFRESH_LOCK.acquire(blocking=False):
                        _REFRESH_STATES[p_name].set("running") # 즉시 ⏳ 모래시계로 변경
                        
                        # 실제 수행할 비동기 작업을 내부 함수로 정의
                        async def _bg_task():
                            try:
                                # 무거운 작업을 스레드로 넘겨 UI 멈춤 방지
                                await asyncio.to_thread(refresh_all, t_sheets, max_workers=2)
                                
                                _REFRESH_STATES[p_name].set("done") # ✅ 체크 표시로 변경
                                await asyncio.sleep(2)              # 2초 대기
                                _REFRESH_STATES[p_name].set("idle") # 🔄 원래 아이콘으로 복구
                                
                            except Exception as e:
                                logging.error(f"[refresh] {p_name} 실패: {e}")
                                _REFRESH_STATES[p_name].set("error")
                            finally:
                                _REFRESH_LOCK.release()

                        # 현재 실행 중인 이벤트 루프에 비동기 작업을 던져주고 즉시 종료
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(_bg_task())
                        except RuntimeError:
                            # 만약 이벤트 루프가 없는 스레드 환경이라면 일반 스레드 방식으로 우회 실행
                            threading.Thread(target=lambda: asyncio.run(_bg_task()), daemon=True).start()

                return _do_refresh

            # 매핑된 페이지들을 순회하며 UI 렌더링
            for page_name, target_sheets in PAGE_SHEETS_MAP.items():
                c1, c2 = app.columns([8, 2]) # 8:2 비율로 영역 분할
                with c1:
                    app.button(
                        page_name, 
                        on_click=lambda p=page_name: app.switch_page(p), 
                        key=f"nav_{page_name}"
                    )
                with c2:
                    # .value 속성을 통해 현재 상태 값 가져오기
                    status = _REFRESH_STATES[page_name].value
                    
                    if status == "idle":
                        app.button("🔄", on_click=make_refresh_callback(target_sheets, page_name), key=f"ref_{page_name}")
                    elif status == "running":
                        app.markdown("<div style='padding-top:8px;'>⏳</div>", unsafe_allow_html=True)
                    elif status == "done":
                        app.button("✅", on_click=make_refresh_callback(target_sheets, page_name), key=f"done_{page_name}")
                    elif status == "error":
                        app.button("❌", on_click=lambda p=page_name: _REFRESH_STATES[p].set("idle"), key=f"err_{page_name}")
        # -------------------------------------------------

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
    vl.Page(_protected(p7_채권분석.render_page),     title="7. 채권분석"),
    vl.Page(_protected(p8_기타.render_page),         title="8. 기타"),
    vl.Page(_protected(p9_해외법인.render_page),     title="9. 해외법인실적"),
])


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 8001)))