"""Tests for Outreach Templates CRUD API."""
import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def admin_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = "tpl_admin@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name="Template Admin",
            role=UserRole.ADMIN,
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
def sample_template():
    return {
        "name": "Welcome Email",
        "subject": "Welcome to ClassBridge, {{full_name}}!",
        "body_html": "<p>Hello {{full_name}}, welcome!</p>",
        "body_text": "Hello {{full_name}}, welcome!",
        "template_type": "email",
        "variables": ["full_name"],
    }


def _create_template(client, headers, data=None):
    payload = data or {
        "name": "Test Template",
        "body_text": "Hello {{full_name}}",
        "template_type": "email",
        "variables": ["full_name"],
    }
    resp = client.post("/api/admin/outreach-templates", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestTemplateCreate:
    def test_create_template(self, client, admin_headers, sample_template):
        resp = client.post("/api/admin/outreach-templates", json=sample_template, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Welcome Email"
        assert data["is_active"] is True
        assert data["template_type"] == "email"
        assert "full_name" in data["variables"]

    def test_create_missing_body_text(self, client, admin_headers):
        resp = client.post("/api/admin/outreach-templates", json={"name": "No Body"}, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_missing_name(self, client, admin_headers):
        resp = client.post("/api/admin/outreach-templates", json={"body_text": "hi"}, headers=admin_headers)
        assert resp.status_code == 422


class TestTemplateList:
    def test_list_templates(self, client, admin_headers):
        _create_template(client, admin_headers)
        resp = client.get("/api/admin/outreach-templates", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_filter_by_type(self, client, admin_headers):
        _create_template(client, admin_headers, {"name": "SMS T", "body_text": "hi", "template_type": "sms", "variables": []})
        resp = client.get("/api/admin/outreach-templates?template_type=sms", headers=admin_headers)
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["template_type"] == "sms"


class TestTemplateGetUpdateDelete:
    def test_get_single_template(self, client, admin_headers):
        created = _create_template(client, admin_headers)
        resp = client.get(f"/api/admin/outreach-templates/{created['id']}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_nonexistent(self, client, admin_headers):
        resp = client.get("/api/admin/outreach-templates/999999", headers=admin_headers)
        assert resp.status_code == 404

    def test_update_template(self, client, admin_headers):
        created = _create_template(client, admin_headers)
        resp = client.patch(
            f"/api/admin/outreach-templates/{created['id']}",
            json={"name": "Updated Name"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_soft_delete(self, client, admin_headers):
        created = _create_template(client, admin_headers)
        resp = client.delete(f"/api/admin/outreach-templates/{created['id']}", headers=admin_headers)
        assert resp.status_code == 204
        # Verify is_active=false
        get_resp = client.get(f"/api/admin/outreach-templates/{created['id']}", headers=admin_headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["is_active"] is False

    def test_delete_nonexistent(self, client, admin_headers):
        resp = client.delete("/api/admin/outreach-templates/999999", headers=admin_headers)
        assert resp.status_code == 404


class TestTemplatePreview:
    def test_preview_renders_variables(self, client, admin_headers):
        created = _create_template(client, admin_headers, {
            "name": "Preview Test",
            "subject": "Hi {{full_name}}",
            "body_text": "Hello {{full_name}}, your child {{child_name}} is great!",
            "body_html": "<p>Hello {{full_name}}</p>",
            "template_type": "email",
            "variables": ["full_name", "child_name"],
        })
        resp = client.post(
            f"/api/admin/outreach-templates/{created['id']}/preview",
            json={"variable_values": {"full_name": "Alice", "child_name": "Bob"}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Alice" in data["rendered_subject"]
        assert "Bob" in data["rendered_text"]

    def test_preview_html_escapes(self, client, admin_headers):
        created = _create_template(client, admin_headers, {
            "name": "Escape Test",
            "body_text": "Hi {{full_name}}",
            "body_html": "<p>{{full_name}}</p>",
            "template_type": "email",
            "variables": ["full_name"],
        })
        resp = client.post(
            f"/api/admin/outreach-templates/{created['id']}/preview",
            json={"variable_values": {"full_name": "<script>alert('xss')</script>"}},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # HTML should be escaped in rendered_html
        assert "<script>" not in data["rendered_html"]
        assert "&lt;script&gt;" in data["rendered_html"]
        # Plain text is NOT escaped
        assert "<script>" in data["rendered_text"]
