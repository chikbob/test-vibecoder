from __future__ import annotations

from app.models.approval_request import ApprovalRequestEvent, IdempotencyRecord, OutboxEvent


def test_create_and_get_approval_request(client, auth_headers):
    create_response = client.post(
        "/api/v1/workspaces/ws_1/approval-requests",
        headers={**auth_headers, "Idempotency-Key": "create-1"},
        json={
            "sourceType": "publication",
            "sourceId": "pub_123",
            "title": "Instagram reel draft",
            "description": "Needs final approval",
            "reviewerUserIds": ["usr_1", "usr_2"],
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["status"] == "pending"
    assert created["workspaceId"] == "ws_1"

    get_response = client.get(
        f"/api/v1/workspaces/ws_1/approval-requests/{created['id']}",
        headers=auth_headers,
    )

    assert get_response.status_code == 200
    assert get_response.json()["id"] == created["id"]


def test_workspace_isolation(client, auth_headers):
    create_response = client.post(
        "/api/v1/workspaces/ws_1/approval-requests",
        headers=auth_headers,
        json={
            "sourceType": "publication",
            "sourceId": "pub_123",
            "title": "Draft",
            "description": "Needs approval",
            "reviewerUserIds": ["usr_1"],
        },
    )
    request_id = create_response.json()["id"]

    mismatch_response = client.get(
        f"/api/v1/workspaces/ws_2/approval-requests/{request_id}",
        headers={**auth_headers, "X-Auth-Workspace-Id": "ws_2"},
    )

    assert mismatch_response.status_code == 404


def test_create_is_idempotent(client, auth_headers):
    payload = {
        "sourceType": "publication",
        "sourceId": "pub_123",
        "title": "Draft",
        "description": "Needs approval",
        "reviewerUserIds": ["usr_1"],
    }
    headers = {**auth_headers, "Idempotency-Key": "same-create"}

    first = client.post("/api/v1/workspaces/ws_1/approval-requests", headers=headers, json=payload)
    second = client.post("/api/v1/workspaces/ws_1/approval-requests", headers=headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    list_response = client.get("/api/v1/workspaces/ws_1/approval-requests", headers=auth_headers)
    assert len(list_response.json()["items"]) == 1


def test_reusing_idempotency_key_with_different_payload_fails(client, auth_headers):
    first = client.post(
        "/api/v1/workspaces/ws_1/approval-requests",
        headers={**auth_headers, "Idempotency-Key": "same-key"},
        json={
            "sourceType": "publication",
            "sourceId": "pub_123",
            "title": "Draft",
            "description": "Needs approval",
            "reviewerUserIds": ["usr_1"],
        },
    )
    second = client.post(
        "/api/v1/workspaces/ws_1/approval-requests",
        headers={**auth_headers, "Idempotency-Key": "same-key"},
        json={
            "sourceType": "publication",
            "sourceId": "pub_999",
            "title": "Other draft",
            "description": "Changed",
            "reviewerUserIds": ["usr_1"],
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_final_state_cannot_change(client, auth_headers):
    created = client.post(
        "/api/v1/workspaces/ws_1/approval-requests",
        headers=auth_headers,
        json={
            "sourceType": "publication",
            "sourceId": "pub_123",
            "title": "Draft",
            "description": "Needs approval",
            "reviewerUserIds": ["usr_1"],
        },
    ).json()

    approved = client.post(
        f"/api/v1/workspaces/ws_1/approval-requests/{created['id']}/approve",
        headers=auth_headers,
        json={"comment": "Approved"},
    )
    rejected = client.post(
        f"/api/v1/workspaces/ws_1/approval-requests/{created['id']}/reject",
        headers=auth_headers,
        json={"reason": "Too late"},
    )

    assert approved.status_code == 200
    assert rejected.status_code == 409


def test_successful_changes_leave_audit_and_outbox_trail(client, auth_headers, db_session_factory):
    created = client.post(
        "/api/v1/workspaces/ws_1/approval-requests",
        headers={**auth_headers, "Idempotency-Key": "trail-create"},
        json={
            "sourceType": "publication",
            "sourceId": "pub_123",
            "title": "Draft",
            "description": "Needs approval",
            "reviewerUserIds": ["usr_1"],
        },
    ).json()

    approved = client.post(
        f"/api/v1/workspaces/ws_1/approval-requests/{created['id']}/approve",
        headers={**auth_headers, "Idempotency-Key": "trail-approve"},
        json={"comment": "Approved"},
    )

    assert approved.status_code == 200

    db = db_session_factory()
    try:
        events = db.query(ApprovalRequestEvent).filter(ApprovalRequestEvent.approval_request_id == created["id"]).all()
        outbox = db.query(OutboxEvent).filter(OutboxEvent.aggregate_id == created["id"]).all()
        idempotency = db.query(IdempotencyRecord).all()
    finally:
        db.close()

    assert [event.event_type for event in events] == [
        "approval_request.created",
        "approval_request.approved",
    ]
    assert len(outbox) == 2
    assert len(idempotency) == 2
