from datetime import datetime, timedelta

from fastapi.testclient import TestClient


def _future_pickup_iso(hours: int = 2) -> str:
    return (datetime.utcnow() + timedelta(hours=hours)).isoformat()


def _create_order_for_item(
    client: TestClient, user_token: str, organization_id: int, menu_item_id: int
):
    resp = client.post(
        "/orders/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "pickup_time": _future_pickup_iso(),
            "organization_id": organization_id,
            "items": [{"menu_item_id": menu_item_id, "quantity": 1}],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_user_can_rate_ordered_item_once(
    client: TestClient, user_token: str, available_item
):
    _create_order_for_item(
        client, user_token, available_item.organization_id, available_item.id
    )

    create_rating = client.post(
        "/ratings/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"menu_item_id": available_item.id, "rating": 5},
    )
    assert create_rating.status_code == 201, create_rating.text
    data = create_rating.json()
    assert data["menu_item_id"] == available_item.id
    assert data["rating"] == 5

    duplicate = client.post(
        "/ratings/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"menu_item_id": available_item.id, "rating": 4},
    )
    assert duplicate.status_code == 409, duplicate.text


def test_user_cannot_rate_item_without_order(
    client: TestClient, user_token: str, available_item
):
    resp = client.post(
        "/ratings/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"menu_item_id": available_item.id, "rating": 4},
    )
    assert resp.status_code == 400, resp.text


def test_rating_summary_and_my_ratings(
    client: TestClient, user_token: str, available_item
):
    _create_order_for_item(
        client, user_token, available_item.organization_id, available_item.id
    )
    create_rating = client.post(
        "/ratings/",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"menu_item_id": available_item.id, "rating": 3},
    )
    assert create_rating.status_code == 201, create_rating.text

    my_ratings = client.get(
        "/ratings/my",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert my_ratings.status_code == 200, my_ratings.text
    assert any(row["menu_item_id"] == available_item.id for row in my_ratings.json())

    summary = client.get(
        "/ratings/summary",
        headers={"Authorization": f"Bearer {user_token}"},
        params=[("menu_item_ids", str(available_item.id))],
    )
    assert summary.status_code == 200, summary.text
    row = next(
        (r for r in summary.json() if r["menu_item_id"] == available_item.id), None
    )
    assert row is not None
    assert row["rating_count"] == 1
    assert float(row["average_rating"]) == 3.0
