"""Tests for holiday_dates CRUD endpoints (#2024)."""

import pytest
from conftest import PASSWORD, _auth


ADMIN_EMAIL = "hol_admin@test.com"
USER_EMAIL = "hol_user@test.com"


def _register(client, email, role="parent", full_name="Test User"):
    return client.post("/api/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": full_name, "role": role,
    })


@pytest.fixture(autouse=True)
def _setup_users(client, db_session):
    """Create an admin and a regular user for tests via API or DB."""
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash

    # Register via API if not exists (admin can't self-register, so register as parent then upgrade)
    if not db_session.query(User).filter(User.email == ADMIN_EMAIL).first():
        resp = _register(client, ADMIN_EMAIL, "parent", "Holiday Admin")
        assert resp.status_code in (200, 201, 409), resp.text
        # Upgrade to admin role via DB
        db_session.expire_all()
        user = db_session.query(User).filter(User.email == ADMIN_EMAIL).first()
        if user:
            user.role = UserRole.ADMIN
            user.roles = "admin"
            db_session.commit()

    if not db_session.query(User).filter(User.email == USER_EMAIL).first():
        resp = _register(client, USER_EMAIL, "parent", "Holiday User")
        assert resp.status_code in (200, 201, 409), resp.text


def test_create_holiday_date_admin(client):
    headers = _auth(client, ADMIN_EMAIL)
    resp = client.post("/api/holiday-dates", json={
        "name": "Labour Day",
        "date": "2026-09-07",
        "board_code": "YRDSB",
        "is_recurring": False,
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Labour Day"
    assert data["date"] == "2026-09-07"
    assert data["board_code"] == "YRDSB"
    assert data["is_recurring"] is False


def test_create_holiday_date_non_admin_forbidden(client):
    headers = _auth(client, USER_EMAIL)
    resp = client.post("/api/holiday-dates", json={
        "name": "Test Holiday",
        "date": "2026-12-25",
    }, headers=headers)
    assert resp.status_code == 403


def test_list_holiday_dates(client):
    headers = _auth(client, ADMIN_EMAIL)
    client.post("/api/holiday-dates", json={
        "name": "Thanksgiving",
        "date": "2026-10-12",
        "board_code": "YRDSB",
    }, headers=headers)
    client.post("/api/holiday-dates", json={
        "name": "Christmas",
        "date": "2026-12-25",
        "board_code": "TDSB",
    }, headers=headers)

    user_headers = _auth(client, USER_EMAIL)
    resp = client.get("/api/holiday-dates", headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


def test_list_holiday_dates_filter_board(client):
    headers = _auth(client, ADMIN_EMAIL)
    client.post("/api/holiday-dates", json={
        "name": "Board A Holiday",
        "date": "2027-01-15",
        "board_code": "BOARD_A",
    }, headers=headers)

    user_headers = _auth(client, USER_EMAIL)
    resp = client.get("/api/holiday-dates?board_code=BOARD_A", headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert all(h["board_code"] == "BOARD_A" for h in data)


def test_update_holiday_date(client):
    headers = _auth(client, ADMIN_EMAIL)
    resp = client.post("/api/holiday-dates", json={
        "name": "Old Name",
        "date": "2027-04-01",
    }, headers=headers)
    holiday_id = resp.json()["id"]

    resp = client.put(f"/api/holiday-dates/{holiday_id}", json={
        "name": "New Name",
        "is_recurring": True,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"
    assert resp.json()["is_recurring"] is True


def test_update_holiday_date_not_found(client):
    headers = _auth(client, ADMIN_EMAIL)
    resp = client.put("/api/holiday-dates/99999", json={
        "name": "Ghost",
    }, headers=headers)
    assert resp.status_code == 404


def test_delete_holiday_date(client):
    headers = _auth(client, ADMIN_EMAIL)
    resp = client.post("/api/holiday-dates", json={
        "name": "To Delete",
        "date": "2027-05-01",
    }, headers=headers)
    holiday_id = resp.json()["id"]

    resp = client.delete(f"/api/holiday-dates/{holiday_id}", headers=headers)
    assert resp.status_code == 204

    user_headers = _auth(client, USER_EMAIL)
    resp = client.get("/api/holiday-dates", headers=user_headers)
    ids = [h["id"] for h in resp.json()]
    assert holiday_id not in ids


def test_delete_holiday_date_not_found(client):
    headers = _auth(client, ADMIN_EMAIL)
    resp = client.delete("/api/holiday-dates/99999", headers=headers)
    assert resp.status_code == 404


def test_delete_holiday_date_non_admin_forbidden(client):
    headers_admin = _auth(client, ADMIN_EMAIL)
    resp = client.post("/api/holiday-dates", json={
        "name": "Protected",
        "date": "2027-06-01",
    }, headers=headers_admin)
    holiday_id = resp.json()["id"]

    headers_user = _auth(client, USER_EMAIL)
    resp = client.delete(f"/api/holiday-dates/{holiday_id}", headers=headers_user)
    assert resp.status_code == 403


def test_seed_yrdsb_2026_27(db_session):
    from app.api.routes.holiday_dates import seed_yrdsb_2026_27
    count = seed_yrdsb_2026_27(db_session)
    assert count > 0

    # Running again should not insert duplicates
    count2 = seed_yrdsb_2026_27(db_session)
    assert count2 == 0
