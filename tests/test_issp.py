"""
Testovi ISSP SRCE integracije.

These tests verify that the ISSP service handles configuration states properly:
- When ISSP is not configured, returns structured 503 error response
- No raw exception messages or stack traces are exposed to the client
"""

from fastapi.testclient import TestClient


def test_issp_status_endpoint_is_available(client: TestClient):
    """Status endpoint exists and returns expected payload shape."""
    resp = client.get("/students/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "message" in data
    assert isinstance(data["enabled"], bool)


def test_issp_status_legacy_alias(client: TestClient):
    """Legacy alias should stay available for older frontend builds."""
    primary = client.get("/students/status")
    legacy = client.get("/students/issp/status")
    assert primary.status_code == 200
    assert legacy.status_code == 200
    assert legacy.json() == primary.json()


def test_get_card_info_when_disabled(client: TestClient, user_token: str):
    """Test that card-info endpoint returns structured error when ISSP is not configured.

    The response should:
    - Return HTTP 503 Service Unavailable (not 501)
    - Include structured JSON with 'error' and 'message' fields
    - NOT expose environment variable names or internal configuration details
    - Provide a user-friendly message in Croatian
    """
    resp = client.get(
        "/students/card-info",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    # Should return 503 Service Unavailable, not 501
    assert resp.status_code == 503, f"Expected 503, got {resp.status_code}"

    # Should return JSON with structured error
    data = resp.json()
    assert "error" in data, "Response should contain 'error' field"
    assert "message" in data, "Response should contain 'message' field"

    # Error code should be specific
    assert data["error"] == "ISSP_NOT_CONFIGURED"

    # Message should be user-friendly (in Croatian)
    assert "Studentska iskaznica" in data["message"]
    assert "nije dostupna" in data["message"] or "nije konfigurirana" in data["message"]

    # Should NOT expose internal details
    response_text = resp.text.lower()
    assert "issp_client_id" not in response_text, "Should not expose env var names"
    assert "issp_client_secret" not in response_text, "Should not expose env var names"
    assert "traceback" not in response_text, "Should not expose stack traces"
    assert "exception" not in response_text, "Should not expose exception details"


def test_card_lookup_post_when_disabled(client: TestClient, user_token: str):
    """POST lookup returns structured 503 when ISSP is not configured."""
    resp = client.post(
        "/students/card-lookup?card_number=123456&esi=ESI123456",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 503
    data = resp.json()
    assert data["error"] == "ISSP_NOT_CONFIGURED"


def test_card_lookup_get_legacy_alias_when_disabled(
    client: TestClient, user_token: str
):
    """GET lookup alias remains supported for backward compatibility."""
    resp = client.get(
        "/students/card-lookup?card_number=123456&esi=ESI123456",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 503
    data = resp.json()
    assert data["error"] == "ISSP_NOT_CONFIGURED"


def test_issp_link_when_disabled(client: TestClient, user_token: str):
    """Link endpoint returns structured 503 when ISSP is disabled."""
    resp = client.post(
        "/students/issp/link",
        headers={"Authorization": f"Bearer {user_token}"},
        json={
            "method": "manual",
            "card_number": "123456",
            "esi": "ESI123456",
        },
    )
    assert resp.status_code == 503
    data = resp.json()
    assert data["error"] == "ISSP_NOT_CONFIGURED"


def test_issp_sync_when_disabled(client: TestClient, user_token: str):
    """Sync endpoint returns structured 503 when ISSP is disabled."""
    resp = client.post(
        "/students/issp/sync",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp.status_code == 503
    data = resp.json()
    assert data["error"] == "ISSP_NOT_CONFIGURED"


def test_issp_link_forbidden_for_staff_role(client: TestClient, admin_token: str):
    """Only student role can use ISSP link endpoint."""
    resp = client.post(
        "/students/issp/link",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "method": "manual",
            "card_number": "123456",
            "esi": "ESI123456",
        },
    )
    assert resp.status_code == 403
