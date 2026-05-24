"""
Testovi narudzbi - unit i integracijski testovi.

Unit testovi: validacija rubnih slucajeva (nedostupan artikal, proslo
              vrijeme preuzimanja, prazna lista artikala, ...)
Integracijski testovi: end-to-end tokovi kroz vise endpointa.
"""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import MenuItem


def _future(hours: int = 2) -> str:
    """Vraca ISO timestamp u buducnosti."""
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat()


def _past(hours: int = 1) -> str:
    """Vraca ISO timestamp u proslosti."""
    return (datetime.utcnow() - timedelta(hours=hours)).isoformat()


# ---------------------------------------------------------------------------
# Kreiranje narudzbe - validacije (unit)
# ---------------------------------------------------------------------------


def test_create_order_success(client: TestClient, user_token: str, available_item):
    """Uspjesno kreiranje narudzbe s dostupnim artiklom."""
    resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": available_item.id, "quantity": 2}],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 2
    assert data["total_price"] == round(available_item.price * 2, 2)


def test_create_order_unavailable_item(
    client: TestClient, user_token: str, unavailable_item
):
    """Narudzba nedostupnog artikla vraca 400 s jasnom porukom."""
    resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": unavailable_item.id, "quantity": 1}],
        },
    )
    assert resp.status_code == 400
    assert "nije dostupan" in resp.json()["detail"]


def test_create_order_past_pickup_time(
    client: TestClient, user_token: str, available_item
):
    """Proslo vrijeme preuzimanja vraca 400."""
    resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _past(),
            "items": [{"menu_item_id": available_item.id, "quantity": 1}],
        },
    )
    assert resp.status_code == 400
    assert "buducnosti" in resp.json()["detail"]


def test_create_order_empty_items(client: TestClient, user_token: str):
    """Prazna lista artikala vraca 400."""
    resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"pickup_time": _future(), "items": []},
    )
    assert resp.status_code == 400


def test_create_order_nonexistent_item(client: TestClient, user_token: str):
    """Nepostojeci artikal vraca 404."""
    resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": 99999, "quantity": 1}],
        },
    )
    assert resp.status_code == 404


def test_create_order_no_auth(client: TestClient, available_item):
    """Kreiranje narudzbe bez tokena vraca 401."""
    resp = client.post(
        "/orders/",
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": available_item.id, "quantity": 1}],
        },
    )
    assert resp.status_code == 401


def test_create_order_invalid_quantity(
    client: TestClient, user_token: str, available_item
):
    """Kolicina 0 ili negativna vraca 422."""
    resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": available_item.id, "quantity": 0}],
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Pregled narudzbi
# ---------------------------------------------------------------------------


def test_get_my_orders(client: TestClient, user_token: str, available_item):
    """Korisnik vidi vlastite narudzbe."""
    client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": available_item.id, "quantity": 1}],
        },
    )
    resp = client.get("/orders/my", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_get_popular_orders_for_student(
    client: TestClient, user_token: str, available_item
):
    """Student moze dohvatiti popularna jela iz stvarnih narudzbi."""
    create = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": available_item.id, "quantity": 2}],
        },
    )
    assert create.status_code == 201

    resp = client.get(
        "/orders/popular", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(int(row["menu_item_id"]) == int(available_item.id) for row in data)


def test_get_popular_orders_requires_auth(client: TestClient):
    """Popularnost jela bez tokena vraca 401."""
    resp = client.get("/orders/popular")
    assert resp.status_code == 401


def test_admin_get_all_orders(
    client: TestClient, user_token: str, admin_token: str, available_item
):
    """Admin vidi sve narudzbe."""
    client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": available_item.id, "quantity": 1}],
        },
    )
    resp = client.get("/orders/all", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_user_cannot_access_all_orders(client: TestClient, user_token: str):
    """Obicni korisnik ne moze vidjeti sve narudzbe - vraca 403."""
    resp = client.get("/orders/all", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 403


def test_admin_all_orders_scoped_to_organization(
    client: TestClient,
    admin_token: str,
    other_user_token: str,
    other_organization,
    session: Session,
):
    """Admin ne vidi narudzbe druge organizacije."""
    foreign_item = MenuItem(
        organization_id=other_organization.id,
        code=77701,
        name="OrgB Artikl",
        price=13.0,
        category="Test",
        group_code=999,
        unit="KOM",
        is_available=True,
    )
    session.add(foreign_item)
    session.commit()
    session.refresh(foreign_item)

    create_foreign = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {other_user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": foreign_item.id, "quantity": 1}],
        },
    )
    assert create_foreign.status_code == 201
    foreign_order_id = create_foreign.json()["id"]

    resp = client.get("/orders/all", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    ids = [o["id"] for o in resp.json()]
    assert foreign_order_id not in ids


def test_admin_cannot_update_order_status_from_other_organization(
    client: TestClient,
    admin_token: str,
    other_user_token: str,
    other_organization,
    session: Session,
):
    """Admin ne smije mijenjati status narudzbe iz druge organizacije."""
    foreign_item = MenuItem(
        organization_id=other_organization.id,
        code=77702,
        name="OrgB Artikl 2",
        price=14.0,
        category="Test",
        group_code=999,
        unit="KOM",
        is_available=True,
    )
    session.add(foreign_item)
    session.commit()
    session.refresh(foreign_item)

    create_foreign = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {other_user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": foreign_item.id, "quantity": 1}],
        },
    )
    assert create_foreign.status_code == 201
    foreign_order_id = create_foreign.json()["id"]

    patch_resp = client.patch(
        f"/orders/{foreign_order_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "confirmed"},
    )
    assert patch_resp.status_code == 403


def test_cancel_own_pending_order(client: TestClient, user_token: str, available_item):
    """Korisnik moze otkazati vlastitu narudzbu u statusu 'pending'."""
    create_resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": available_item.id, "quantity": 1}],
        },
    )
    order_id = create_resp.json()["id"]

    cancel_resp = client.delete(
        f"/orders/{order_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert cancel_resp.status_code == 204


def test_cannot_cancel_completed_order(
    client: TestClient, user_token: str, admin_token: str, available_item
):
    """Nije moguce otkazati narudzbu u statusu 'completed'."""
    create_resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": available_item.id, "quantity": 1}],
        },
    )
    order_id = create_resp.json()["id"]

    # Admin postavlja status na 'completed'
    client.patch(
        f"/orders/{order_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "completed"},
    )

    cancel_resp = client.delete(
        f"/orders/{order_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert cancel_resp.status_code == 400


# ---------------------------------------------------------------------------
# Uredivanje narudzbe i praznjenje kosarice
# ---------------------------------------------------------------------------


def test_update_order_items(client: TestClient, user_token: str, available_item):
    """Korisnik moze urediti stavke narudzbe u statusu pending."""
    create_resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": available_item.id, "quantity": 1}],
        },
    )
    order_id = create_resp.json()["id"]

    update_resp = client.patch(
        f"/orders/{order_id}",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "items": [{"menu_item_id": available_item.id, "quantity": 3}],
        },
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["items"][0]["quantity"] == 3
    assert data["total_price"] == round(available_item.price * 3, 2)


def test_update_order_not_pending(
    client: TestClient, user_token: str, admin_token: str, available_item
):
    """Narudzba izvan statusa pending se ne moze urediti."""
    create_resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": available_item.id, "quantity": 1}],
        },
    )
    order_id = create_resp.json()["id"]

    client.patch(
        f"/orders/{order_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "confirmed"},
    )

    update_resp = client.patch(
        f"/orders/{order_id}",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"notes": "Kasnim 10 min"},
    )
    assert update_resp.status_code == 400


def test_clear_cart_items(client: TestClient, user_token: str, available_item):
    """Praznjenje kosarice brise stavke i otkazuje narudzbu."""
    create_resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": available_item.id, "quantity": 1}],
        },
    )
    order_id = create_resp.json()["id"]

    clear_resp = client.delete(
        f"/orders/{order_id}/items",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert clear_resp.status_code == 204

    get_resp = client.get(
        f"/orders/{order_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "cancelled"
    assert get_resp.json()["items"] == []


# ---------------------------------------------------------------------------
# Integracijski testovi (end-to-end)
# ---------------------------------------------------------------------------


def test_integration_full_order_lifecycle(
    client: TestClient, user_token: str, admin_token: str
):
    """
    [INTEGRACIJSKI] Kompletan tok narudzbe:
    admin kreira artikal -> korisnik narucuje -> admin potvrdjuje -> admin oznacava kao spremno.
    """
    # 1. Admin dodaje novi artikal na jelovnik
    item_resp = client.post(
        "/menu/items",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "code": 40001,
            "name": "Burger Deluxe",
            "price": 55.0,
            "is_available": True,
            "group_code": 412,
            "unit": "KOM",
        },
    )
    assert item_resp.status_code == 201
    item_id = item_resp.json()["id"]

    # 2. Korisnik pregleda jelovnik i vidi novi artikal
    menu_resp = client.get(
        "/menu/items",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert menu_resp.status_code == 200
    assert any(i["id"] == item_id for i in menu_resp.json())

    # 3. Korisnik kreira narudzbu
    order_resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(hours=3),
            "notes": "Bez luka",
            "items": [{"menu_item_id": item_id, "quantity": 1}],
        },
    )
    assert order_resp.status_code == 201
    order = order_resp.json()
    assert order["status"] == "pending"
    assert order["total_price"] == 55.0
    order_id = order["id"]

    # 4. Admin potvrdjuje narudzbu
    confirm_resp = client.patch(
        f"/orders/{order_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "confirmed"},
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "confirmed"

    # 5. Admin oznacava narudzbu kao spremno
    ready_resp = client.patch(
        f"/orders/{order_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "ready"},
    )
    assert ready_resp.status_code == 200
    assert ready_resp.json()["status"] == "ready"

    # 6. Korisnik vidi svoju narudzbu u novom statusu
    my_orders = client.get(
        "/orders/my", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert my_orders.status_code == 200
    my_order = next(o for o in my_orders.json() if o["id"] == order_id)
    assert my_order["status"] == "ready"


def test_integration_availability_blocks_order(
    client: TestClient, user_token: str, admin_token: str
):
    """
    [INTEGRACIJSKI] Admin deaktivira artikal - korisnik vise ne moze naruciti.
    Provjera poslovnog pravila: zabrana narudzbe nedostupnog artikla.
    """
    # Admin kreira dostupan artikal
    item_resp = client.post(
        "/menu/items",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "code": 40002,
            "name": "Sezonski specijalitet",
            "price": 75.0,
            "is_available": True,
            "group_code": 412,
            "unit": "KOM",
        },
    )
    item_id = item_resp.json()["id"]

    # Narudzba je OK dok je artikal dostupan
    ok_resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": item_id, "quantity": 1}],
        },
    )
    assert ok_resp.status_code == 201

    # Admin deaktivira artikal
    client.put(
        f"/menu/items/{item_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"is_available": False},
    )

    # Sada narudzba mora biti odbijena
    blocked_resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future(),
            "items": [{"menu_item_id": item_id, "quantity": 1}],
        },
    )
    assert blocked_resp.status_code == 400
    assert "nije dostupan" in blocked_resp.json()["detail"]

    # Artikal vise nije vidljiv u jelovniku
    menu_resp = client.get(
        "/menu/items?available_only=true",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert not any(i["id"] == item_id for i in menu_resp.json())
