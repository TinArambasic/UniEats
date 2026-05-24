"""
Testovi autentifikacije i korisnickih racuna.
Pokriva: registraciju, prijavu, dohvat profila i rubne slucajeve.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth import get_password_hash
from app.config import settings
from app.models import User, UserOrganization, UserRole

# ---------------------------------------------------------------------------
# Registracija
# ---------------------------------------------------------------------------


def test_register_new_user(client: TestClient):
    """Uspjesna registracija novog korisnika."""
    resp = client.post(
        "/auth/register",
        json={
            "email": "novi@test.com",
            "password": "Lozinka1!",
            "student_card_number": "20000001",
            "student_esi": "ESI2001",
            "first_name": "Ivan",
            "last_name": "Ivic",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["student_card_number"] == "20000001"
    assert data["role"] == "student"
    assert "id" in data
    assert "hashed_password" not in data  # nikad ne vracamo hash


def test_register_duplicate_card_number(client: TestClient, regular_user):
    """Registracija s vec zauzetim brojem kartice vraca 400."""
    resp = client.post(
        "/auth/register",
        json={
            "email": "drugi@test.com",
            "password": "Lozinka1!",
            "student_card_number": "10000001",
            "student_esi": "ESI2002",
        },
    )
    assert resp.status_code == 400
    assert "broj kartice" in resp.json()["detail"].lower()


def test_register_duplicate_email(client: TestClient, regular_user):
    """Registracija s vec registriranim emailom vraca 400."""
    resp = client.post(
        "/auth/register",
        json={
            "email": "marko@test.com",
            "password": "Lozinka1!",
            "student_card_number": "20000003",
            "student_esi": "ESI2003",
        },
    )
    assert resp.status_code == 400


def test_register_short_password(client: TestClient):
    """Kratka lozinka (< 6 znakova) vraca 422 validacijsku gresku."""
    resp = client.post(
        "/auth/register",
        json={
            "email": "x@test.com",
            "password": "123",
            "student_card_number": "20000004",
            "student_esi": "ESI2004",
        },
    )
    assert resp.status_code == 422


def test_register_invalid_email(client: TestClient):
    """Nevazeca email adresa vraca 422."""
    resp = client.post(
        "/auth/register",
        json={
            "email": "not-an-email",
            "password": "Lozinka1!",
            "student_card_number": "20000005",
            "student_esi": "ESI2005",
        },
    )
    assert resp.status_code == 422


def test_register_invalid_card_format(client: TestClient):
    """Broj kartice s nedozvoljenim znakovima vraca 422."""
    resp = client.post(
        "/auth/register",
        json={
            "email": "format@test.com",
            "password": "Lozinka1!",
            "student_card_number": "CARD-001",
            "student_esi": "ESI3001",
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Prijava (login)
# ---------------------------------------------------------------------------


def test_login_success(client: TestClient, regular_user):
    """Uspjesna prijava vraca access_token."""
    resp = client.post(
        "/auth/login", data={"username": "10000001", "password": "Marko123!"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient, regular_user):
    """Pogresna lozinka vraca 401."""
    resp = client.post(
        "/auth/login", data={"username": "10000001", "password": "pogresna"}
    )
    assert resp.status_code == 401


def test_login_nonexistent_user(client: TestClient):
    """Nepostojeci korisnik vraca 401."""
    resp = client.post(
        "/auth/login", data={"username": "99999998", "password": "nesto"}
    )
    assert resp.status_code == 401


def test_login_error_message_generic(client: TestClient, regular_user):
    """Poruka greske ne otkriva postoji li korisnik."""
    wrong_pw = client.post(
        "/auth/login", data={"username": "10000001", "password": "pogresna"}
    )
    missing = client.post(
        "/auth/login", data={"username": "99999998", "password": "nesto"}
    )
    assert wrong_pw.status_code == 401
    assert missing.status_code == 401
    assert wrong_pw.json()["detail"] == missing.json()["detail"]


def test_login_invalid_card_format(client: TestClient):
    """Neispravan format broja kartice vraca 401 genericku gresku."""
    resp = client.post(
        "/auth/login", data={"username": "ABC-123", "password": "pogresna"}
    )
    assert resp.status_code == 401


def test_staff_login_success_admin(client: TestClient, admin_user):
    """Admin se prijavljuje korisnicko ime + lozinka putem staff login endpointa."""
    resp = client.post(
        "/auth/login/staff",
        data={"username": "admin", "password": "Admin123!"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_staff_login_rejects_student_account(client: TestClient, regular_user):
    """Student ne moze koristiti staff login endpoint."""
    resp = client.post(
        "/auth/login/staff",
        data={"username": "marko@test.com", "password": "Marko123!"},
    )
    assert resp.status_code == 401


def test_student_login_rejects_admin_account(client: TestClient, admin_user):
    """Admin/owner ne mogu koristiti student login endpoint."""
    resp = client.post(
        "/auth/login/student",
        data={"username": "admin@test.com", "password": "Admin123!"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Profil (/me)
# ---------------------------------------------------------------------------


def test_get_me_authenticated(client: TestClient, user_token: str):
    """Autentificirani korisnik moze dohvatiti vlastiti profil."""
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 200
    assert resp.json()["student_card_number"] == "10000001"


def test_get_me_no_token(client: TestClient):
    """Zahtjev bez tokena vraca 401."""
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_get_me_invalid_token(client: TestClient):
    """Nevazeci token vraca 401."""
    resp = client.get(
        "/auth/me", headers={"Authorization": "Bearer token.nevazeci.jwt"}
    )
    assert resp.status_code == 401


def test_login_rate_limited(client: TestClient):
    """Prekacenje rate limita vraca 429."""
    for _ in range(settings.LOGIN_RATE_LIMIT_MAX):
        resp = client.post(
            "/auth/login", data={"username": "12345678", "password": "pogresna"}
        )
        assert resp.status_code == 401

    blocked = client.post(
        "/auth/login", data={"username": "12345678", "password": "pogresna"}
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_owner_can_create_admin_user(client: TestClient, owner_token: str):
    """Owner ima ovlast kreirati admin korisnika (username + lozinka umjesto email)."""
    resp = client.post(
        "/auth/admins",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "username": "noviadmin",
            "password": "AdminPass1!",
            "oib": "98765432101",
            "first_name": "Novi",
            "last_name": "Admin",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "admin"
    assert data["username"] == "noviadmin"


def test_admin_cannot_create_admin_user(client: TestClient, admin_token: str):
    """Samo owner smije upravljati admin korisnicima."""
    resp = client.post(
        "/auth/admins",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": "blockedadmin",
            "password": "AdminPass1!",
            "oib": "11111111111",
            "first_name": "Blocked",
            "last_name": "Admin",
        },
    )
    assert resp.status_code == 403


def test_owner_cannot_delete_last_owner(client: TestClient, owner_token: str):
    """Brisanje zadnjeg owner korisnika mora biti blokirano."""
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {owner_token}"})
    owner_id = me.json()["id"]
    resp = client.delete(
        f"/auth/owners/{owner_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 400
    assert "zadnjeg admina organizacije" in resp.json()["detail"].lower()


def test_owner_can_delete_owner_when_multiple_exist(
    client: TestClient,
    owner_token: str,
    session: Session,
    owner_user: User,
):
    """Owner moze obrisati drugog ownera ako nije zadnji."""
    second_owner = User(
        organization_id=owner_user.organization_id,
        email="owner2@test.com",
        hashed_password=get_password_hash("Owner223!"),
        role=UserRole.owner,
        is_active=True,
    )
    session.add(second_owner)
    session.commit()
    session.refresh(second_owner)
    session.add(
        UserOrganization(
            user_id=second_owner.id,
            organization_id=owner_user.organization_id,
        )
    )
    session.commit()

    resp = client.delete(
        f"/auth/owners/{second_owner.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 204


def test_owner_admin_management_is_scoped_to_organization(
    client: TestClient,
    owner_token: str,
    other_admin_user: User,
):
    """Owner ne smije vidjeti djelatnike iz druge organizacije."""
    resp = client.get(
        "/auth/admins", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resp.status_code == 200
    usernames = [u["username"] for u in resp.json()]
    assert "admin-b" not in usernames
    assert other_admin_user.username == "admin-b"


def test_owner_cannot_delete_other_org_admin(
    client: TestClient,
    owner_token: str,
    other_admin_user: User,
):
    """Brisanje djelatnika iz druge organizacije mora vratiti 404."""
    resp = client.delete(
        f"/auth/admins/{other_admin_user.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 404


def test_staff_can_list_only_organization_users(
    client: TestClient,
    admin_token: str,
    regular_user: User,
    other_student_user: User,
):
    """Staff endpoint /auth/users vraca samo korisnike iz iste organizacije."""
    resp = client.get("/auth/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    # Check for users by first_name
    users = resp.json()
    first_names = [u.get("first_name") for u in users if u.get("first_name")]
    # Check that our user (Marko) is in the list (same organization as admin)
    assert "Marko" in first_names, f"Expected Marko in {first_names}"
    # Check that user from other organization is NOT in the list
    assert "Sara" not in first_names, f"Unexpected Sara in {first_names}"
    assert other_student_user.first_name == "Sara"


def test_staff_can_list_users_without_primary_org_when_membership_exists(
    client: TestClient,
    session: Session,
    admin_user: User,
):
    """Fallback na membership radi kad staff korisnik nema primary organization_id."""
    admin_user.organization_id = None
    session.add(admin_user)
    session.commit()

    login = client.post(
        "/auth/login/staff",
        data={"username": "admin", "password": "Admin123!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    resp = client.get("/auth/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
