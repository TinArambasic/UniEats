"""
Zajednicki fixture-i za sve testove.

Koristi in-memory SQLite bazu (:memory:) - svaki test dobiva
cistu bazu zahvaljujuci StaticPool-u i drop_all/create_all.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.auth import get_password_hash
from app.database import get_session
from app.main import app
from app.models import MenuItem, Organization, User, UserOrganization, UserRole
from app.services.rate_limiter import reset_rate_limiter as reset_rate_limiter_state

TEST_DB_URL = "sqlite://"


def _attach_membership(session: Session, user: User, organization_id: int) -> None:
    link = UserOrganization(user_id=user.id, organization_id=organization_id)
    session.add(link)
    session.commit()


@pytest.fixture(name="engine", scope="function")
def engine_fixture():
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session", scope="function")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="organization")
def organization_fixture(session: Session) -> Organization:
    org = Organization(name="Org A", is_active=True)
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


@pytest.fixture(name="other_organization")
def other_organization_fixture(session: Session) -> Organization:
    org = Organization(name="Org B", is_active=True)
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


@pytest.fixture(name="client", scope="function")
def client_fixture(session: Session):
    def _get_session_override():
        return session

    app.dependency_overrides[get_session] = _get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    reset_rate_limiter_state()
    yield
    reset_rate_limiter_state()


# ---------------------------------------------------------------------------
# Korisnici
# ---------------------------------------------------------------------------


@pytest.fixture(name="admin_user")
def admin_user_fixture(session: Session, organization: Organization) -> User:
    user = User(
        organization_id=organization.id,
        username="admin",  # Username for staff login
        oib="12345678901",  # OIB for staff identification
        hashed_password=get_password_hash("Admin123!"),
        role=UserRole.admin,
        first_name="Admin",
        last_name="User",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    _attach_membership(session, user, organization.id)
    return user


@pytest.fixture(name="owner_user")
def owner_user_fixture(session: Session, organization: Organization) -> User:
    user = User(
        organization_id=organization.id,
        username="owner",  # Username for staff login
        oib="12345678902",  # OIB for staff identification
        hashed_password=get_password_hash("Owner123!"),
        role=UserRole.owner,
        first_name="Owner",
        last_name="User",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    _attach_membership(session, user, organization.id)
    return user


@pytest.fixture(name="regular_user")
def regular_user_fixture(session: Session, organization: Organization) -> User:
    user = User(
        organization_id=organization.id,
        email="marko@test.com",
        hashed_password=get_password_hash("Marko123!"),
        role=UserRole.student,
        student_card_number="10000001",
        student_esi="ESI1001",
        first_name="Marko",
        last_name="Horvat",
        subsidy_remaining=10.0,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    _attach_membership(session, user, organization.id)
    return user


@pytest.fixture(name="admin_token")
def admin_token_fixture(client: TestClient, admin_user: User) -> str:
    resp = client.post(
        "/auth/login/staff",
        data={"username": "admin", "password": "Admin123!"},  # Use username, not email
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture(name="owner_token")
def owner_token_fixture(client: TestClient, owner_user: User) -> str:
    resp = client.post(
        "/auth/login/staff",
        data={"username": "owner", "password": "Owner123!"},  # Use username, not email
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture(name="user_token")
def user_token_fixture(client: TestClient, regular_user: User) -> str:
    resp = client.post(
        "/auth/login/student",
        data={"username": "10000001", "password": "Marko123!"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Artikli
# ---------------------------------------------------------------------------


@pytest.fixture(name="available_item")
def available_item_fixture(session: Session, organization: Organization) -> MenuItem:
    item = MenuItem(
        organization_id=organization.id,
        code=10001,
        name="Pizza Margherita",
        price=32.0,
        is_available=True,
        category="Pizza",
        group_code=999,
        unit="KOM",
        calories_kcal=650,
        protein_g=22,
        carbs_g=70,
        fat_g=28,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@pytest.fixture(name="unavailable_item")
def unavailable_item_fixture(session: Session, organization: Organization) -> MenuItem:
    item = MenuItem(
        organization_id=organization.id,
        code=10002,
        name="Rasprodano jelo",
        price=20.0,
        is_available=False,
        category="Ostalo",
        group_code=999,
        unit="KOM",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@pytest.fixture(name="other_owner_user")
def other_owner_user_fixture(
    session: Session, other_organization: Organization
) -> User:
    user = User(
        organization_id=other_organization.id,
        username="owner-b",  # Username for staff login
        oib="22345678901",  # OIB for staff identification
        hashed_password=get_password_hash("OwnerB123!"),
        role=UserRole.owner,
        is_active=True,
        first_name="Owner",
        last_name="B",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    _attach_membership(session, user, other_organization.id)
    return user


@pytest.fixture(name="other_admin_user")
def other_admin_user_fixture(
    session: Session, other_organization: Organization
) -> User:
    user = User(
        organization_id=other_organization.id,
        username="admin-b",  # Username for staff login
        oib="22345678902",  # OIB for staff identification
        hashed_password=get_password_hash("AdminB123!"),
        role=UserRole.admin,
        is_active=True,
        first_name="Admin",
        last_name="B",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    _attach_membership(session, user, other_organization.id)
    return user


@pytest.fixture(name="other_student_user")
def other_student_user_fixture(
    session: Session, other_organization: Organization
) -> User:
    user = User(
        organization_id=other_organization.id,
        email="student-b@test.com",
        hashed_password=get_password_hash("StudentB123!"),
        role=UserRole.student,
        student_card_number="20000009",
        student_esi="ESI2009",
        first_name="Sara",
        last_name="Kovac",
        subsidy_remaining=8.0,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    _attach_membership(session, user, other_organization.id)
    return user


@pytest.fixture(name="other_owner_token")
def other_owner_token_fixture(client: TestClient, other_owner_user: User) -> str:
    resp = client.post(
        "/auth/login/staff",
        data={"username": "owner-b", "password": "OwnerB123!"},  # Use username
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture(name="other_admin_token")
def other_admin_token_fixture(client: TestClient, other_admin_user: User) -> str:
    resp = client.post(
        "/auth/login/staff",
        data={"username": "admin-b", "password": "AdminB123!"},  # Use username
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture(name="other_user_token")
def other_user_token_fixture(client: TestClient, other_student_user: User) -> str:
    resp = client.post(
        "/auth/login/student",
        data={"username": "20000009", "password": "StudentB123!"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]
