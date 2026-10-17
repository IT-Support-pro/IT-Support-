import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User, Store, EnrollmentKey, AlertRule
from app.security import hash_password, hash_secret
from scripts.seed import DEFAULT_ALERT_RULES

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        # Seed default alert rules
        for r in DEFAULT_ALERT_RULES:
            db.add(AlertRule(**r))
        db.commit()
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def seed_data(db_session):
    admin = User(
        username="admin",
        password_hash=hash_password("AdminSecurePassword123!"),
        role="admin",
        is_active=True
    )
    tech = User(
        username="tech1",
        password_hash=hash_password("TechSecurePassword123!"),
        role="technician",
        is_active=True
    )
    viewer = User(
        username="viewer1",
        password_hash=hash_password("ViewerSecurePassword123!"),
        role="viewer",
        is_active=True
    )
    store = Store(code="ISL-01", name="Islamabad 01", region="North")
    db_session.add_all([admin, tech, viewer, store])
    db_session.commit()

    raw_key = "HBK-TEST-KEY-1234"
    key_rec = EnrollmentKey(
        store_id=store.id,
        key_hash=hash_secret(raw_key),
        created_by=admin.id,
        revoked=False
    )
    db_session.add(key_rec)
    db_session.commit()

    return {
        "admin": admin,
        "tech": tech,
        "viewer": viewer,
        "store": store,
        "enrollment_key": raw_key
    }
