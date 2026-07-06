import pytest

from tests.conftest import ALL_PERMISSIONS, full_headers, make_headers

WORKSPACE = "ws_test"
BASE = f"/api/v1/workspaces/{WORKSPACE}/approval-requests"

SAMPLE = {
    "sourceType": "publication",
    "sourceId": "pub_123",
    "title": "Instagram reel draft",
    "description": "Needs final approval",
    "reviewerUserIds": ["usr_2", "usr_3"],
}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def test_create_request_returns_201(client):
    r = client.post(BASE, json=SAMPLE, headers=full_headers())
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "pending"
    assert data["workspaceId"] == WORKSPACE
    assert data["sourceType"] == "publication"
    assert data["createdBy"] == "usr_1"
    assert data["decision"] is None
    assert "id" in data


def test_create_requires_approval_create(client):
    r = client.post(BASE, json=SAMPLE, headers=make_headers("usr_1", "approval:read"))
    assert r.status_code == 403


def test_create_missing_auth_headers_returns_422(client):
    r = client.post(BASE, json=SAMPLE)
    assert r.status_code == 422


def test_create_invalid_source_type_returns_422(client):
    r = client.post(BASE, json={**SAMPLE, "sourceType": "blog"}, headers=full_headers())
    assert r.status_code == 422


def test_create_empty_reviewer_ids_returns_422(client):
    r = client.post(BASE, json={**SAMPLE, "reviewerUserIds": []}, headers=full_headers())
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_idempotent_create_returns_same_id(client):
    headers = {**full_headers(), "Idempotency-Key": "key-abc"}
    r1 = client.post(BASE, json=SAMPLE, headers=headers)
    assert r1.status_code == 201
    r2 = client.post(BASE, json=SAMPLE, headers=headers)
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


def test_requests_without_idempotency_key_create_duplicates(client):
    headers = full_headers()
    client.post(BASE, json=SAMPLE, headers=headers)
    client.post(BASE, json=SAMPLE, headers=headers)
    r = client.get(BASE, headers=full_headers())
    assert len(r.json()) == 2


# ---------------------------------------------------------------------------
# List & get
# ---------------------------------------------------------------------------

def test_list_requests(client):
    h = full_headers()
    client.post(BASE, json=SAMPLE, headers=h)
    client.post(BASE, json={**SAMPLE, "title": "Second"}, headers=h)
    r = client.get(BASE, headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_requires_approval_read(client):
    r = client.get(BASE, headers=make_headers("usr_1", "approval:create"))
    assert r.status_code == 403


def test_list_workspace_isolation(client):
    client.post(BASE, json=SAMPLE, headers=full_headers())
    r = client.get(f"/api/v1/workspaces/other-ws/approval-requests", headers=full_headers())
    assert r.status_code == 200
    assert r.json() == []


def test_get_request(client):
    request_id = client.post(BASE, json=SAMPLE, headers=full_headers()).json()["id"]
    r = client.get(f"{BASE}/{request_id}", headers=full_headers())
    assert r.status_code == 200
    assert r.json()["id"] == request_id


def test_get_request_wrong_workspace_returns_404(client):
    request_id = client.post(BASE, json=SAMPLE, headers=full_headers()).json()["id"]
    r = client.get(
        f"/api/v1/workspaces/other-ws/approval-requests/{request_id}",
        headers=full_headers(),
    )
    assert r.status_code == 404


def test_get_nonexistent_returns_404(client):
    r = client.get(f"{BASE}/nonexistent-id", headers=full_headers())
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Approve
# ---------------------------------------------------------------------------

def test_approve_request(client):
    request_id = client.post(BASE, json=SAMPLE, headers=full_headers()).json()["id"]
    r = client.post(
        f"{BASE}/{request_id}/approve",
        json={"comment": "Approved"},
        headers=full_headers(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "approved"
    assert data["decision"]["action"] == "approve"
    assert data["decision"]["actorUserId"] == "usr_1"
    assert data["decision"]["comment"] == "Approved"


def test_approve_requires_approval_decide(client):
    request_id = client.post(BASE, json=SAMPLE, headers=full_headers()).json()["id"]
    r = client.post(
        f"{BASE}/{request_id}/approve",
        json={"comment": "ok"},
        headers=make_headers("usr_1", "approval:read", "approval:create"),
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Reject
# ---------------------------------------------------------------------------

def test_reject_request(client):
    request_id = client.post(BASE, json=SAMPLE, headers=full_headers()).json()["id"]
    r = client.post(
        f"{BASE}/{request_id}/reject",
        json={"reason": "Brand tone is wrong"},
        headers=full_headers(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "rejected"
    assert data["decision"]["reason"] == "Brand tone is wrong"


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

def test_cancel_request(client):
    request_id = client.post(BASE, json=SAMPLE, headers=full_headers()).json()["id"]
    r = client.post(
        f"{BASE}/{request_id}/cancel",
        json={"reason": "Draft was removed"},
        headers=full_headers(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "cancelled"
    assert data["decision"]["reason"] == "Draft was removed"


def test_cancel_requires_approval_cancel(client):
    request_id = client.post(BASE, json=SAMPLE, headers=full_headers()).json()["id"]
    r = client.post(
        f"{BASE}/{request_id}/cancel",
        json={"reason": "Gone"},
        headers=make_headers("usr_1", "approval:read", "approval:create", "approval:decide"),
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Final-state guard
# ---------------------------------------------------------------------------

def test_double_decide_returns_409(client):
    request_id = client.post(BASE, json=SAMPLE, headers=full_headers()).json()["id"]
    client.post(f"{BASE}/{request_id}/approve", json={"comment": "ok"}, headers=full_headers())
    r = client.post(
        f"{BASE}/{request_id}/reject",
        json={"reason": "Nope"},
        headers=full_headers(),
    )
    assert r.status_code == 409


def test_cancel_already_approved_returns_409(client):
    request_id = client.post(BASE, json=SAMPLE, headers=full_headers()).json()["id"]
    client.post(f"{BASE}/{request_id}/approve", json={}, headers=full_headers())
    r = client.post(
        f"{BASE}/{request_id}/cancel",
        json={"reason": "Too late"},
        headers=full_headers(),
    )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

def test_decision_reflected_in_get(client):
    request_id = client.post(BASE, json=SAMPLE, headers=full_headers("usr_approver")).json()["id"]
    client.post(
        f"{BASE}/{request_id}/approve",
        json={"comment": "LGTM"},
        headers=full_headers("usr_approver"),
    )
    r = client.get(f"{BASE}/{request_id}", headers=full_headers())
    data = r.json()
    assert data["decision"]["actorUserId"] == "usr_approver"
    assert data["decision"]["comment"] == "LGTM"
