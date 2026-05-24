"""
Testovi za update organizacije i radno vrijeme.
"""

from fastapi.testclient import TestClient


def test_update_organization_persists_fields_and_working_hours(
    client: TestClient,
    admin_token: str,
    organization,
):
    """Azuriranje organizacije mora sacuvati osnovna polja i radno vrijeme."""
    payload = {
        "name": "Org A - Renovirana",
        "address": "Ulica 123",
        "city": "Osijek",
        "phone": "031 123 456",
        "working_hours": [
            {
                "day_of_week": 0,
                "is_closed": False,
                "open_time": "07:30",
                "close_time": "19:00",
            },
            {
                "day_of_week": 1,
                "is_closed": False,
                "open_time": "07:30",
                "close_time": "19:00",
            },
            {
                "day_of_week": 2,
                "is_closed": False,
                "open_time": "07:30",
                "close_time": "19:00",
            },
            {
                "day_of_week": 3,
                "is_closed": False,
                "open_time": "07:30",
                "close_time": "19:00",
            },
            {
                "day_of_week": 4,
                "is_closed": False,
                "open_time": "07:30",
                "close_time": "18:00",
            },
            {
                "day_of_week": 5,
                "is_closed": True,
                "open_time": None,
                "close_time": None,
            },
            {
                "day_of_week": 6,
                "is_closed": True,
                "open_time": None,
                "close_time": None,
            },
        ],
    }
    put_resp = client.put(
        f"/organizations/{organization.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )
    assert put_resp.status_code == 200
    updated = put_resp.json()
    assert updated["name"] == payload["name"]
    assert updated["address"] == payload["address"]
    assert updated["city"] == payload["city"]
    assert updated["phone"] == payload["phone"]

    get_resp = client.get(
        f"/organizations/{organization.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["name"] == payload["name"]
    assert data["address"] == payload["address"]
    assert data["city"] == payload["city"]
    assert data["phone"] == payload["phone"]
    saturday = next(row for row in data["working_hours"] if row["day_of_week"] == 5)
    assert saturday["is_closed"] is True
    assert saturday["open_time"] is None
    assert saturday["close_time"] is None


def test_update_organization_name_conflict_returns_409(
    client: TestClient,
    owner_token: str,
    organization,
    other_organization,
):
    """Promjena naziva na vec postojeci mora vratiti 409 umjesto 500."""
    resp = client.put(
        f"/organizations/{organization.id}",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": other_organization.name},
    )
    assert resp.status_code == 409
    assert "vec postoji" in resp.json()["detail"].lower()
