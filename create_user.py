"""
접근 권한 관리 스크립트.
Google 로그인 시 허용할 이메일 계정을 사전 등록합니다.

사용법:
  python create_user.py add hong.gildong@company.com
  python create_user.py delete hong.gildong@company.com
  python create_user.py list

예시:
  python create_user.py add kim.ceo@at.co.kr
  python create_user.py add lee.vp@at.co.kr
  python create_user.py list
  python create_user.py delete lee.vp@at.co.kr
"""
import sys
import secrets
from typing import Optional
from sqlmodel import SQLModel, Field, Session, select, create_engine


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    hashed_password: str


engine = create_engine("sqlite:///./app.db")
SQLModel.metadata.create_all(engine)


def add_user(email: str):
    email = email.strip().lower()
    with Session(engine) as s:
        if s.exec(select(User).where(User.username == email)).first():
            print(f"[이미 등록됨] {email}")
            return
        s.add(User(username=email, hashed_password=secrets.token_hex(32)))
        s.commit()
    print(f"[완료] {email} — 접근 권한 부여")


def delete_user(email: str):
    email = email.strip().lower()
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == email)).first()
        if user is None:
            print(f"[없음] {email}")
            return
        s.delete(user)
        s.commit()
    print(f"[완료] {email} — 접근 권한 제거")


def list_users():
    with Session(engine) as s:
        users = s.exec(select(User)).all()
    if not users:
        print("등록된 계정이 없습니다.")
        return
    print(f"{'#':>3}  이메일")
    print("-" * 45)
    for i, u in enumerate(users, 1):
        print(f"{i:>3}  {u.username}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
    elif args[0] == "add" and len(args) >= 2:
        for email in args[1:]:
            add_user(email)
    elif args[0] == "delete" and len(args) == 2:
        delete_user(args[1])
    elif args[0] == "list":
        list_users()
    else:
        print(__doc__)
