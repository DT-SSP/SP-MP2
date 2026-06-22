"""
사용자 관리 스크립트.

사용법:
  python create_user.py add <아이디> <비밀번호>
  python create_user.py delete <아이디>
  python create_user.py list

예시:
  python create_user.py add hong.gildong 비밀번호123
  python create_user.py add kim.manager pass1234
  python create_user.py list
  python create_user.py delete hong.gildong
"""
import sys
from typing import Optional
from sqlmodel import SQLModel, Field, Session, select, create_engine
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    hashed_password: str


engine = create_engine("sqlite:///./app.db")
SQLModel.metadata.create_all(engine)


def add_user(username: str, password: str):
    username = username.strip()
    with Session(engine) as s:
        if s.exec(select(User).where(User.username == username)).first():
            print(f"[이미 등록됨] {username}")
            return
        s.add(User(username=username, hashed_password=hash_password(password)))
        s.commit()
    print(f"[완료] {username} — 사용자 등록")


def delete_user(username: str):
    username = username.strip()
    with Session(engine) as s:
        user = s.exec(select(User).where(User.username == username)).first()
        if user is None:
            print(f"[없음] {username}")
            return
        s.delete(user)
        s.commit()
    print(f"[완료] {username} — 사용자 삭제")


def list_users():
    with Session(engine) as s:
        users = s.exec(select(User)).all()
    if not users:
        print("등록된 사용자가 없습니다.")
        return
    print(f"{'#':>3}  아이디")
    print("-" * 45)
    for i, u in enumerate(users, 1):
        print(f"{i:>3}  {u.username}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
    elif args[0] == "add" and len(args) == 3:
        add_user(args[1], args[2])
    elif args[0] == "delete" and len(args) == 2:
        delete_user(args[1])
    elif args[0] == "list":
        list_users()
    else:
        print(__doc__)
