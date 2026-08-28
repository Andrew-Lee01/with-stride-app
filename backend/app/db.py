import os

from sqlmodel import SQLModel, create_engine, Session

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "gait.db")

# 배포 환경(Render 등)에서는 DATABASE_URL(예: Neon Postgres)을 넣어 영구 저장.
# 로컬 개발에서는 지정 안 하면 파일 기반 SQLite를 그대로 사용.
_raw_url = os.environ.get("DATABASE_URL")
if _raw_url:
    # Render/Neon이 주는 postgres:// 스킴을 SQLAlchemy가 이해하는 postgresql://로 보정
    DATABASE_URL = _raw_url.replace("postgres://", "postgresql://", 1)
    connect_args = {}
else:
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
