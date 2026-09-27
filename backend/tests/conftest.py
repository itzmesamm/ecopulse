import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.database import Base, get_db
from backend.api import security
from backend.main import app


@pytest.fixture
def db_session(monkeypatch):
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    test_session = sessionmaker(bind=test_engine)()
    monkeypatch.setattr(security, "SessionLocal", lambda: test_session)
    monkeypatch.setattr(security, "verify_access_token", lambda token: "test-user")
    app.dependency_overrides[get_db] = lambda: (yield test_session)
    try:
        yield test_session
    finally:
        test_session.rollback()
        test_session.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()
