"""Tests for Customer Database (Parent Contacts) CRUD API."""
import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def admin_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = "contacts_admin@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name="Contacts Admin",
            role=UserRole.ADMIN,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture()
def parent_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = "contacts_parent@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name="Contacts Parent",
            role=UserRole.PARENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture()
def admin_headers(client, admin_user):
    return _auth(client, admin_user.email)


@pytest.fixture()
def parent_headers(client, parent_user):
    return _auth(client, parent_user.email)


@pytest.fixture()
def sample_contact_data():
    return {
        "full_name": "Jane Doe",
        "email": "jane.doe@example.com",
        "phone": "+14165551234",
        "school_name": "Riverside PS",
        "child_name": "Tommy Doe",
        "child_grade": "Grade 5",
        "status": "lead",
        "source": "manual",
        "tags": ["interested", "demo-booked"],
        "consent_given": False,
    }


def _create_contact(client, headers, data=None):
    """Helper to create a contact and return the response JSON."""
    payload = data or {
        "full_name": "Test Contact",
        "email": "test.contact@example.com",
        "status": "lead",
        "source": "manual",
    }
    resp = client.post("/api/admin/contacts", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Auth Tests ────────────────────────────────────────────────────────────────

class TestContactsAuth:
    def test_non_admin_cannot_list(self, client, parent_headers):
        resp = client.get("/api/admin/contacts", headers=parent_headers)
        assert resp.status_code == 403

    def test_non_admin_cannot_create(self, client, parent_headers, sample_contact_data):
        resp = client.post("/api/admin/contacts", json=sample_contact_data, headers=parent_headers)
        assert resp.status_code == 403

    def test_non_admin_cannot_delete(self, client, parent_headers):
        resp = client.delete("/api/admin/contacts/1", headers=parent_headers)
        assert resp.status_code == 403

    def test_unauthenticated_gets_401(self, client):
        resp = client.get("/api/admin/contacts")
        assert resp.status_code in (401, 403)


# ── Create Tests ──────────────────────────────────────────────────────────────

class TestContactCreate:
    def test_create_valid_contact(self, client, admin_headers, sample_contact_data):
        resp = client.post("/api/admin/contacts", json=sample_contact_data, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["full_name"] == "Jane Doe"
        assert data["email"] == "jane.doe@example.com"
        assert data["status"] == "lead"
        assert data["tags"] == ["interested", "demo-booked"]
        assert data["id"] is not None

    def test_create_missing_full_name(self, client, admin_headers):
        resp = client.post("/api/admin/contacts", json={"email": "x@y.com"}, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_empty_full_name(self, client, admin_headers):
        resp = client.post("/api/admin/contacts", json={"full_name": ""}, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_duplicate_email_still_succeeds(self, client, admin_headers):
        payload = {"full_name": "Dup One", "email": "dup@example.com", "status": "lead", "source": "manual"}
        r1 = client.post("/api/admin/contacts", json=payload, headers=admin_headers)
        assert r1.status_code == 201
        payload2 = {"full_name": "Dup Two", "email": "dup@example.com", "status": "lead", "source": "manual"}
        r2 = client.post("/api/admin/contacts", json=payload2, headers=admin_headers)
        assert r2.status_code == 201

    def test_create_with_consent_sets_consent_date(self, client, admin_headers):
        payload = {"full_name": "Consented User", "consent_given": True, "status": "lead", "source": "manual"}
        resp = client.post("/api/admin/contacts", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        assert resp.json()["consent_date"] is not None

    def test_create_invalid_status(self, client, admin_headers):
        payload = {"full_name": "Bad Status", "status": "invalid_status", "source": "manual"}
        resp = client.post("/api/admin/contacts", json=payload, headers=admin_headers)
        assert resp.status_code == 422


# ── List Tests ────────────────────────────────────────────────────────────────

class TestContactList:
    def test_list_returns_items_and_total(self, client, admin_headers):
        _create_contact(client, admin_headers, {"full_name": "List Test", "status": "lead", "source": "manual"})
        resp = client.get("/api/admin/contacts", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_search_by_name(self, client, admin_headers):
        _create_contact(client, admin_headers, {"full_name": "UniqueSearchName99", "status": "lead", "source": "manual"})
        resp = client.get("/api/admin/contacts?search=UniqueSearchName99", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any("UniqueSearchName99" in c["full_name"] for c in data["items"])

    def test_status_filter(self, client, admin_headers):
        _create_contact(client, admin_headers, {"full_name": "Archived Pal", "status": "archived", "source": "manual"})
        resp = client.get("/api/admin/contacts?status=archived", headers=admin_headers)
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "archived"

    def test_pagination(self, client, admin_headers):
        # Create a few contacts
        for i in range(3):
            _create_contact(client, admin_headers, {"full_name": f"Page{i}", "status": "lead", "source": "manual"})
        resp = client.get("/api/admin/contacts?skip=0&limit=2", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2


# ── Get Single Contact Tests ──────────────────────────────────────────────────

class TestContactGet:
    def test_get_contact(self, client, admin_headers):
        created = _create_contact(client, admin_headers)
        resp = client.get(f"/api/admin/contacts/{created['id']}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["full_name"] == created["full_name"]

    def test_get_nonexistent_contact(self, client, admin_headers):
        resp = client.get("/api/admin/contacts/999999", headers=admin_headers)
        assert resp.status_code == 404


# ── Update Tests ──────────────────────────────────────────────────────────────

class TestContactUpdate:
    def test_partial_update_status(self, client, admin_headers):
        created = _create_contact(client, admin_headers)
        resp = client.patch(
            f"/api/admin/contacts/{created['id']}",
            json={"status": "contacted"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "contacted"

    def test_update_consent_sets_date(self, client, admin_headers):
        created = _create_contact(client, admin_headers, {"full_name": "No Consent", "status": "lead", "source": "manual", "consent_given": False})
        resp = client.patch(
            f"/api/admin/contacts/{created['id']}",
            json={"consent_given": True},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["consent_date"] is not None

    def test_update_nonexistent_contact(self, client, admin_headers):
        resp = client.patch("/api/admin/contacts/999999", json={"status": "lead"}, headers=admin_headers)
        assert resp.status_code == 404


# ── Delete Tests ──────────────────────────────────────────────────────────────

class TestContactDelete:
    def test_delete_contact(self, client, admin_headers):
        created = _create_contact(client, admin_headers)
        resp = client.delete(f"/api/admin/contacts/{created['id']}", headers=admin_headers)
        assert resp.status_code == 204
        # Verify gone
        resp2 = client.get(f"/api/admin/contacts/{created['id']}", headers=admin_headers)
        assert resp2.status_code == 404

    def test_delete_nonexistent(self, client, admin_headers):
        resp = client.delete("/api/admin/contacts/999999", headers=admin_headers)
        assert resp.status_code == 404


# ── Stats Tests ───────────────────────────────────────────────────────────────

class TestContactStats:
    def test_stats_returns_correct_structure(self, client, admin_headers):
        _create_contact(client, admin_headers, {"full_name": "Stats Lead", "status": "lead", "source": "manual"})
        resp = client.get("/api/admin/contacts/stats", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "by_status" in data
        assert "recent_outreach_count" in data
        assert "contacts_without_consent" in data
        assert data["total"] >= 1


# ── Notes Tests ───────────────────────────────────────────────────────────────

class TestContactNotes:
    def test_add_note(self, client, admin_headers):
        created = _create_contact(client, admin_headers)
        resp = client.post(
            f"/api/admin/contacts/{created['id']}/notes",
            json={"note_text": "Called, left voicemail"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["note_text"] == "Called, left voicemail"

    def test_list_notes_newest_first(self, client, admin_headers):
        created = _create_contact(client, admin_headers)
        cid = created["id"]
        client.post(f"/api/admin/contacts/{cid}/notes", json={"note_text": "Note 1"}, headers=admin_headers)
        client.post(f"/api/admin/contacts/{cid}/notes", json={"note_text": "Note 2"}, headers=admin_headers)
        resp = client.get(f"/api/admin/contacts/{cid}/notes", headers=admin_headers)
        assert resp.status_code == 200
        notes = resp.json()
        assert len(notes) >= 2
        # Newest first
        assert notes[0]["note_text"] == "Note 2"

    def test_delete_note(self, client, admin_headers):
        created = _create_contact(client, admin_headers)
        cid = created["id"]
        note_resp = client.post(f"/api/admin/contacts/{cid}/notes", json={"note_text": "To delete"}, headers=admin_headers)
        note_id = note_resp.json()["id"]
        resp = client.delete(f"/api/admin/contacts/{cid}/notes/{note_id}", headers=admin_headers)
        assert resp.status_code == 204

    def test_add_note_to_nonexistent_contact(self, client, admin_headers):
        resp = client.post("/api/admin/contacts/999999/notes", json={"note_text": "Oops"}, headers=admin_headers)
        assert resp.status_code == 404


# ── Bulk Operations Tests ─────────────────────────────────────────────────────

class TestBulkOps:
    def test_bulk_delete(self, client, admin_headers):
        c1 = _create_contact(client, admin_headers, {"full_name": "Bulk Del 1", "status": "lead", "source": "manual"})
        c2 = _create_contact(client, admin_headers, {"full_name": "Bulk Del 2", "status": "lead", "source": "manual"})
        resp = client.post("/api/admin/contacts/bulk-delete", json={"ids": [c1["id"], c2["id"]]}, headers=admin_headers)
        assert resp.status_code == 204

    def test_bulk_status_change(self, client, admin_headers):
        c1 = _create_contact(client, admin_headers, {"full_name": "Bulk Stat 1", "status": "lead", "source": "manual"})
        c2 = _create_contact(client, admin_headers, {"full_name": "Bulk Stat 2", "status": "lead", "source": "manual"})
        resp = client.post(
            "/api/admin/contacts/bulk-status",
            json={"ids": [c1["id"], c2["id"]], "status": "contacted"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["updated_count"] == 2

    def test_bulk_tag_add(self, client, admin_headers):
        c1 = _create_contact(client, admin_headers, {"full_name": "Tag Add", "status": "lead", "source": "manual"})
        resp = client.post(
            "/api/admin/contacts/bulk-tag",
            json={"ids": [c1["id"]], "tag": "vip", "action": "add"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["updated_count"] == 1
        # Verify tag is there
        get_resp = client.get(f"/api/admin/contacts/{c1['id']}", headers=admin_headers)
        assert "vip" in get_resp.json()["tags"]

    def test_bulk_tag_remove(self, client, admin_headers):
        c1 = _create_contact(client, admin_headers, {"full_name": "Tag Remove", "status": "lead", "source": "manual", "tags": ["removeme"]})
        resp = client.post(
            "/api/admin/contacts/bulk-tag",
            json={"ids": [c1["id"]], "tag": "removeme", "action": "remove"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["updated_count"] == 1


# ── CSV Export Tests ──────────────────────────────────────────────────────────

class TestCSVExport:
    def test_csv_export_content_type(self, client, admin_headers):
        _create_contact(client, admin_headers, {"full_name": "CSV Person", "status": "lead", "source": "manual"})
        resp = client.get("/api/admin/contacts/export/csv", headers=admin_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "Full Name" in resp.text
