import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 – registers ORM models before create_all

from app.database import Base
from app.dependencies import get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test_approval.db"

_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=_engine)
    session = _Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_engine)


@pytest.fixture()
def client(db):
    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def make_headers(user_id: str, *permissions: str) -> dict:
    return {
        "X-User-Id": user_id,
        "X-Permissions": ",".join(permissions),
    }


ALL_PERMISSIONS = (
    "approval:read",
    "approval:create",
    "approval:decide",
    "approval:cancel",
)


def full_headers(user_id: str = "usr_1") -> dict:
    return make_headers(user_id, *ALL_PERMISSIONS)
