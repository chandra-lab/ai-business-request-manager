"""Phase 7 — fill remaining authz / HR negative coverage gaps."""

from __future__ import annotations

from pathlib import Path

from app.models.attachment import Attachment
from app.models.request import ConfidentialityLevel, Request, RequestPriority, RequestStatus
from app.models.user import User


def _hr_case(db, requester: User) -> Request:
    req = Request(
        title="Medical leave coordination",
        description="Confidential medical leave discussion for HR case handling.",
        status=RequestStatus.PENDING_REVIEW,
        priority=RequestPriority.HIGH,
        requester_id=requester.id,
        is_hr_sensitive=True,
        confidentiality=ConfidentialityLevel.HIGHLY_CONFIDENTIAL,
    )
    db.add(req)
    db.flush()
    return req


def test_fleet_manager_cannot_open_hr_case(client, auth_headers, db):
    req = _hr_case(db, db.info["users"]["employee"])
    manager = auth_headers("manager@aibrm.example.com")
    assert client.get(f"/api/v1/requests/{req.id}", headers=manager).status_code == 404


def test_reviewer_cannot_list_hr_notes(client, auth_headers, db):
    req = _hr_case(db, db.info["users"]["employee"])
    reviewer = auth_headers("reviewer@aibrm.example.com")
    # Reviewer cannot view HR case at all → 404 on notes path after require_view
    resp = client.get(f"/api/v1/requests/{req.id}/hr-notes", headers=reviewer)
    assert resp.status_code in {403, 404}


def test_hr_grant_revoke_removes_admin_access(client, auth_headers, db):
    admin_user = db.info["users"]["admin"]
    req = _hr_case(db, db.info["users"]["employee"])
    hr = auth_headers("hr@aibrm.example.com")
    admin = auth_headers("admin@aibrm.example.com")

    assert client.get(f"/api/v1/requests/{req.id}", headers=admin).status_code == 404

    grant = client.post(
        f"/api/v1/requests/{req.id}/hr-access",
        headers=hr,
        json={"user_id": str(admin_user.id)},
    )
    assert grant.status_code == 201, grant.text
    access_id = grant.json()["id"]
    assert client.get(f"/api/v1/requests/{req.id}", headers=admin).status_code == 200

    revoked = client.delete(
        f"/api/v1/requests/{req.id}/hr-access/{access_id}",
        headers=hr,
    )
    assert revoked.status_code == 200
    assert client.get(f"/api/v1/requests/{req.id}", headers=admin).status_code == 404


def test_other_user_cannot_download_hr_attachment(client, auth_headers, db, tmp_path):
    employee = db.info["users"]["employee"]
    req = _hr_case(db, employee)
    # Persist a fake attachment row + file
    upload_root = Path("/tmp/aibrm-test-uploads")
    upload_root.mkdir(parents=True, exist_ok=True)
    rel = f"{req.id}/secret.txt"
    full = upload_root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text("confidential", encoding="utf-8")
    att = Attachment(
        request_id=req.id,
        uploaded_by_id=employee.id,
        filename="secret.txt",
        content_type="text/plain",
        size_bytes=12,
        storage_path=rel,
    )
    db.add(att)
    db.flush()

    other = auth_headers("other@aibrm.example.com")
    resp = client.get(
        f"/api/v1/requests/{req.id}/attachments/{att.id}",
        headers=other,
    )
    assert resp.status_code in {403, 404}

    # Requester can download their own HR attachment
    emp = auth_headers("employee@aibrm.example.com")
    ok = client.get(
        f"/api/v1/requests/{req.id}/attachments/{att.id}",
        headers=emp,
    )
    assert ok.status_code == 200
