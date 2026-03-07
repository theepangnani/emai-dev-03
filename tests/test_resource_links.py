import pytest
from unittest.mock import patch
from conftest import PASSWORD, _auth


@pytest.fixture()
def setup(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.course import Course
    from app.models.course_content import CourseContent
    from app.models.resource_link import ResourceLink

    owner = db_session.query(User).filter(User.email == "rlinks_owner@test.com").first()
    if owner:
        outsider = db_session.query(User).filter(User.email == "rlinks_outsider@test.com").first()
        cc = (
            db_session.query(CourseContent)
            .join(Course)
            .filter(Course.name == "Resource Links Test Course")
            .first()
        )
        cc_with_urls = (
            db_session.query(CourseContent)
            .join(Course)
            .filter(CourseContent.title == "Lesson With URLs")
            .first()
        )
        cc_no_text = (
            db_session.query(CourseContent)
            .join(Course)
            .filter(CourseContent.title == "Lesson No Text")
            .first()
        )
        return {
            "owner": owner,
            "outsider": outsider,
            "course_content": cc,
            "course_content_with_urls": cc_with_urls,
            "course_content_no_text": cc_no_text,
        }

    hashed = get_password_hash(PASSWORD)
    owner = User(
        email="rlinks_owner@test.com",
        full_name="RLinks Owner",
        role=UserRole.PARENT,
        hashed_password=hashed,
    )
    outsider = User(
        email="rlinks_outsider@test.com",
        full_name="RLinks Outsider",
        role=UserRole.PARENT,
        hashed_password=hashed,
    )
    db_session.add_all([owner, outsider])
    db_session.flush()

    course = Course(name="Resource Links Test Course", created_by_user_id=owner.id)
    db_session.add(course)
    db_session.flush()

    cc = CourseContent(
        course_id=course.id,
        title="Lesson 1",
        content_type="notes",
        created_by_user_id=owner.id,
    )
    cc_with_urls = CourseContent(
        course_id=course.id,
        title="Lesson With URLs",
        content_type="notes",
        created_by_user_id=owner.id,
        text_content=(
            "Analytic Geometry:\n"
            "Equation of the median: https://www.youtube.com/watch?v=4Qa6jDc9Tb0\n"
            "External resource: https://example.com/page\n"
        ),
    )
    cc_no_text = CourseContent(
        course_id=course.id,
        title="Lesson No Text",
        content_type="notes",
        created_by_user_id=owner.id,
        text_content="",
    )
    db_session.add_all([cc, cc_with_urls, cc_no_text])
    db_session.commit()

    return {
        "owner": owner,
        "outsider": outsider,
        "course_content": cc,
        "course_content_with_urls": cc_with_urls,
        "course_content_no_text": cc_no_text,
    }


# ── GET /api/course-contents/{id}/links ─────────────────────────


class TestGetResourceLinks:
    def test_returns_empty_for_no_links(self, client, setup):
        headers = _auth(client, "rlinks_owner@test.com")
        resp = client.get(
            f"/api/course-contents/{setup['course_content'].id}/links",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_grouped_links(self, client, setup, db_session):
        from app.models.resource_link import ResourceLink

        cc_id = setup["course_content"].id
        # Create links under two different headings
        link1 = ResourceLink(
            course_content_id=cc_id,
            url="https://www.youtube.com/watch?v=ABC123",
            resource_type="youtube",
            title="Video A",
            topic_heading="Topic 1",
            youtube_video_id="ABC123",
            display_order=0,
        )
        link2 = ResourceLink(
            course_content_id=cc_id,
            url="https://example.com",
            resource_type="external_link",
            title="Example",
            topic_heading="Topic 2",
            display_order=0,
        )
        db_session.add_all([link1, link2])
        db_session.commit()

        headers = _auth(client, "rlinks_owner@test.com")
        resp = client.get(f"/api/course-contents/{cc_id}/links", headers=headers)
        assert resp.status_code == 200
        groups = resp.json()
        assert len(groups) == 2
        headings = {g["topic_heading"] for g in groups}
        assert headings == {"Topic 1", "Topic 2"}

        # Clean up for other tests
        db_session.delete(link1)
        db_session.delete(link2)
        db_session.commit()

    def test_404_for_nonexistent_content(self, client, setup):
        headers = _auth(client, "rlinks_owner@test.com")
        resp = client.get("/api/course-contents/999999/links", headers=headers)
        assert resp.status_code == 404

    def test_unauthenticated(self, client, setup):
        resp = client.get(f"/api/course-contents/{setup['course_content'].id}/links")
        assert resp.status_code == 401


# ── POST /api/course-contents/{id}/links ────────────────────────


class TestCreateResourceLink:
    @patch("app.api.routes.resource_links.enrich_youtube_metadata")
    def test_create_youtube_link(self, mock_enrich, client, setup):
        mock_enrich.return_value = {
            "title": "Enriched Title",
            "thumbnail_url": "https://i.ytimg.com/vi/ABC123/hqdefault.jpg",
        }
        headers = _auth(client, "rlinks_owner@test.com")
        resp = client.post(
            f"/api/course-contents/{setup['course_content'].id}/links",
            json={
                "url": "https://www.youtube.com/watch?v=ABC123",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["resource_type"] == "youtube"
        assert data["youtube_video_id"] == "ABC123"
        assert data["title"] == "Enriched Title"
        assert data["course_content_id"] == setup["course_content"].id

    def test_create_external_link(self, client, setup):
        headers = _auth(client, "rlinks_owner@test.com")
        resp = client.post(
            f"/api/course-contents/{setup['course_content'].id}/links",
            json={
                "url": "https://example.com/docs",
                "title": "Example Docs",
                "topic_heading": "Resources",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["resource_type"] == "external_link"
        assert data["youtube_video_id"] is None
        assert data["title"] == "Example Docs"
        assert data["topic_heading"] == "Resources"

    def test_unauthenticated(self, client, setup):
        resp = client.post(
            f"/api/course-contents/{setup['course_content'].id}/links",
            json={"url": "https://example.com"},
        )
        assert resp.status_code == 401

    def test_non_owner_forbidden(self, client, setup):
        headers = _auth(client, "rlinks_outsider@test.com")
        resp = client.post(
            f"/api/course-contents/{setup['course_content'].id}/links",
            json={"url": "https://example.com"},
            headers=headers,
        )
        assert resp.status_code == 403


# ── PATCH /api/resource-links/{id} ──────────────────────────────


class TestUpdateResourceLink:
    def test_update_title_and_heading(self, client, setup, db_session):
        from app.models.resource_link import ResourceLink

        link = ResourceLink(
            course_content_id=setup["course_content"].id,
            url="https://example.com/update-test",
            resource_type="external_link",
            title="Original",
            display_order=0,
        )
        db_session.add(link)
        db_session.commit()
        db_session.refresh(link)

        headers = _auth(client, "rlinks_owner@test.com")
        resp = client.patch(
            f"/api/resource-links/{link.id}",
            json={"title": "Updated Title", "topic_heading": "New Topic"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["topic_heading"] == "New Topic"
        # URL should remain unchanged
        assert data["url"] == "https://example.com/update-test"

    def test_404_for_nonexistent_link(self, client, setup):
        headers = _auth(client, "rlinks_owner@test.com")
        resp = client.patch(
            "/api/resource-links/999999",
            json={"title": "Won't work"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_non_owner_forbidden(self, client, setup, db_session):
        from app.models.resource_link import ResourceLink

        link = ResourceLink(
            course_content_id=setup["course_content"].id,
            url="https://example.com/forbidden-update",
            resource_type="external_link",
            title="Forbidden",
            display_order=0,
        )
        db_session.add(link)
        db_session.commit()
        db_session.refresh(link)

        headers = _auth(client, "rlinks_outsider@test.com")
        resp = client.patch(
            f"/api/resource-links/{link.id}",
            json={"title": "Hacked"},
            headers=headers,
        )
        assert resp.status_code == 403


# ── DELETE /api/resource-links/{id} ─────────────────────────────


class TestDeleteResourceLink:
    def test_delete_successfully(self, client, setup, db_session):
        from app.models.resource_link import ResourceLink

        link = ResourceLink(
            course_content_id=setup["course_content"].id,
            url="https://example.com/delete-me",
            resource_type="external_link",
            title="Delete Me",
            display_order=0,
        )
        db_session.add(link)
        db_session.commit()
        db_session.refresh(link)

        headers = _auth(client, "rlinks_owner@test.com")
        resp = client.delete(f"/api/resource-links/{link.id}", headers=headers)
        assert resp.status_code == 204

        # Verify it's gone
        assert db_session.query(ResourceLink).filter(ResourceLink.id == link.id).first() is None

    def test_404_for_nonexistent_link(self, client, setup):
        headers = _auth(client, "rlinks_owner@test.com")
        resp = client.delete("/api/resource-links/999999", headers=headers)
        assert resp.status_code == 404

    def test_non_owner_forbidden(self, client, setup, db_session):
        from app.models.resource_link import ResourceLink

        link = ResourceLink(
            course_content_id=setup["course_content"].id,
            url="https://example.com/no-delete",
            resource_type="external_link",
            title="No Delete",
            display_order=0,
        )
        db_session.add(link)
        db_session.commit()
        db_session.refresh(link)

        headers = _auth(client, "rlinks_outsider@test.com")
        resp = client.delete(f"/api/resource-links/{link.id}", headers=headers)
        assert resp.status_code == 403


# ── POST /api/course-contents/{id}/extract-links ────────────────


class TestExtractResourceLinks:
    @patch("app.api.routes.resource_links.extract_and_enrich_links")
    def test_extracts_links_from_text(self, mock_extract, client, setup):
        from app.services.link_extraction_service import ExtractedLink

        mock_extract.return_value = [
            ExtractedLink(
                url="https://www.youtube.com/watch?v=4Qa6jDc9Tb0",
                resource_type="youtube",
                title="Equation of the median",
                topic_heading="Analytic Geometry",
                youtube_video_id="4Qa6jDc9Tb0",
                display_order=0,
            ),
            ExtractedLink(
                url="https://example.com/page",
                resource_type="external_link",
                title="External resource",
                display_order=1,
            ),
        ]
        headers = _auth(client, "rlinks_owner@test.com")
        resp = client.post(
            f"/api/course-contents/{setup['course_content_with_urls'].id}/extract-links",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["resource_type"] == "youtube"
        assert data[0]["youtube_video_id"] == "4Qa6jDc9Tb0"
        assert data[1]["resource_type"] == "external_link"

    @patch("app.api.routes.resource_links.extract_and_enrich_links")
    def test_replaces_existing_links(self, mock_extract, client, setup, db_session):
        from app.models.resource_link import ResourceLink
        from app.services.link_extraction_service import ExtractedLink

        cc_id = setup["course_content_with_urls"].id

        # Create a pre-existing link
        old_link = ResourceLink(
            course_content_id=cc_id,
            url="https://example.com/old",
            resource_type="external_link",
            title="Old Link",
            display_order=0,
        )
        db_session.add(old_link)
        db_session.commit()

        mock_extract.return_value = [
            ExtractedLink(
                url="https://example.com/new",
                resource_type="external_link",
                title="New Link",
                display_order=0,
            ),
        ]

        headers = _auth(client, "rlinks_owner@test.com")
        resp = client.post(
            f"/api/course-contents/{cc_id}/extract-links",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "New Link"

        # Verify old link is gone
        db_session.expire_all()
        remaining = (
            db_session.query(ResourceLink)
            .filter(ResourceLink.course_content_id == cc_id)
            .all()
        )
        titles = [l.title for l in remaining]
        assert "Old Link" not in titles
        assert "New Link" in titles

    def test_empty_text_returns_400(self, client, setup):
        headers = _auth(client, "rlinks_owner@test.com")
        resp = client.post(
            f"/api/course-contents/{setup['course_content_no_text'].id}/extract-links",
            headers=headers,
        )
        assert resp.status_code == 400

    def test_non_owner_forbidden(self, client, setup):
        headers = _auth(client, "rlinks_outsider@test.com")
        resp = client.post(
            f"/api/course-contents/{setup['course_content_with_urls'].id}/extract-links",
            headers=headers,
        )
        assert resp.status_code == 403
