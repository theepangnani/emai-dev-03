"""Newsletter service — AI generation, template management, and SendGrid delivery."""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.newsletter import Newsletter, NewsletterTemplate, NewsletterStatus, NewsletterAudience
from app.models.user import User, UserRole
from app.schemas.newsletter import NewsletterCreate, NewsletterUpdate

logger = logging.getLogger(__name__)


class NewsletterService:
    # ────────────────────────────────────────────────────────────────────────
    # CRUD
    # ────────────────────────────────────────────────────────────────────────

    def create_newsletter(self, user_id: int, data: NewsletterCreate, db: Session) -> Newsletter:
        """Create a new newsletter draft."""
        newsletter = Newsletter(
            created_by=user_id,
            title=data.title,
            subject=data.subject,
            content=data.content,
            html_content=data.html_content,
            audience=data.audience,
            status=NewsletterStatus.DRAFT,
        )
        db.add(newsletter)
        db.commit()
        db.refresh(newsletter)
        logger.info(f"Created newsletter draft id={newsletter.id} by user_id={user_id}")
        return newsletter

    def get_newsletters(self, user_id: int, db: Session) -> list[Newsletter]:
        """Return newsletters. Admins see all; teachers see their own."""
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.has_role(UserRole.ADMIN):
            return db.query(Newsletter).order_by(Newsletter.created_at.desc()).all()
        return (
            db.query(Newsletter)
            .filter(Newsletter.created_by == user_id)
            .order_by(Newsletter.created_at.desc())
            .all()
        )

    def get_newsletter(self, newsletter_id: int, db: Session) -> Optional[Newsletter]:
        return db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()

    def update_newsletter(
        self, newsletter_id: int, user_id: int, data: NewsletterUpdate, db: Session
    ) -> Optional[Newsletter]:
        newsletter = self._get_owned(newsletter_id, user_id, db)
        if not newsletter:
            return None
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(newsletter, field, value)
        db.commit()
        db.refresh(newsletter)
        return newsletter

    def delete_newsletter(self, newsletter_id: int, user_id: int, db: Session) -> bool:
        newsletter = self._get_owned(newsletter_id, user_id, db)
        if not newsletter:
            return False
        if newsletter.status == NewsletterStatus.SENT:
            return False  # Cannot delete sent newsletters
        db.delete(newsletter)
        db.commit()
        return True

    # ────────────────────────────────────────────────────────────────────────
    # AI generation
    # ────────────────────────────────────────────────────────────────────────

    def generate_ai_newsletter(
        self,
        user_id: int,
        topic: str,
        key_points: list[str],
        audience: NewsletterAudience,
        tone: str,
        db: Session,
    ) -> Newsletter:
        """Use GPT-4o-mini to generate a fully-formed HTML newsletter and save as draft."""
        from openai import OpenAI
        from app.core.config import settings

        client = OpenAI(api_key=settings.openai_api_key if hasattr(settings, "openai_api_key") else "")

        audience_label = {
            NewsletterAudience.ALL: "all school community members (parents, teachers, and students)",
            NewsletterAudience.PARENTS: "parents",
            NewsletterAudience.TEACHERS: "teachers",
            NewsletterAudience.STUDENTS: "students",
        }.get(audience, "all school community members")

        key_points_text = "\n".join(f"- {p}" for p in key_points) if key_points else "No specific points provided."

        prompt = f"""You are writing a school newsletter for ClassBridge.

Topic: {topic}
Audience: {audience_label}
Tone: {tone}
Key points to cover:
{key_points_text}

Generate a complete school newsletter with:
1. An engaging title (keep it under 80 characters)
2. A clear email subject line (keep it under 100 characters)
3. Full HTML body content with proper formatting: headings, paragraphs, bullet lists where appropriate.
   Use inline CSS for styling. Make it look professional and match a school communication style.
   The HTML should be just the body content (no <html>/<head>/<body> tags — it will be wrapped in a template).

Respond in exactly this JSON format:
{{
  "title": "...",
  "subject": "...",
  "html_content": "..."
}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7,
        )

        import json
        result = json.loads(response.choices[0].message.content)

        title = result.get("title", f"Newsletter: {topic}")
        subject = result.get("subject", f"School Update: {topic}")
        html_content = result.get("html_content", "")

        # Strip raw text from HTML for the plain content field
        import re
        plain_content = re.sub(r"<[^>]+>", "", html_content).strip()

        newsletter = Newsletter(
            created_by=user_id,
            title=title,
            subject=subject,
            content=plain_content or topic,
            html_content=html_content,
            audience=audience,
            status=NewsletterStatus.DRAFT,
        )
        db.add(newsletter)
        db.commit()
        db.refresh(newsletter)
        logger.info(f"AI-generated newsletter id={newsletter.id} topic='{topic}' by user_id={user_id}")
        return newsletter

    # ────────────────────────────────────────────────────────────────────────
    # Send / schedule
    # ────────────────────────────────────────────────────────────────────────

    def send_newsletter(
        self, newsletter_id: int, user_id: int, db: Session
    ) -> dict[str, int]:
        """Send newsletter to all users matching the audience filter."""
        newsletter = db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()
        if not newsletter:
            raise ValueError("Newsletter not found")

        if newsletter.status == NewsletterStatus.SENT:
            raise ValueError("Newsletter has already been sent")

        recipients = self._get_recipients(newsletter.audience, db)
        if not recipients:
            logger.warning(f"No recipients found for newsletter id={newsletter_id} audience={newsletter.audience}")

        from app.services.email_service import send_emails_batch, wrap_branded_email

        html_body = newsletter.html_content or f"<p>{newsletter.content}</p>"
        wrapped_html = wrap_branded_email(html_body)

        email_tuples = [
            (user.email, newsletter.subject, wrapped_html)
            for user in recipients
            if user.email
        ]

        sent_count = send_emails_batch(email_tuples)
        failed_count = max(0, len(email_tuples) - sent_count)

        newsletter.status = NewsletterStatus.SENT
        newsletter.sent_at = datetime.now(timezone.utc)
        newsletter.recipient_count = sent_count
        db.commit()

        logger.info(
            f"Newsletter id={newsletter_id} sent: {sent_count} delivered, {failed_count} failed"
        )
        return {"sent_count": sent_count, "failed_count": failed_count, "newsletter_id": newsletter_id}

    def schedule_newsletter(
        self,
        newsletter_id: int,
        scheduled_at: datetime,
        user_id: int,
        db: Session,
    ) -> Optional[Newsletter]:
        newsletter = self._get_owned(newsletter_id, user_id, db)
        if not newsletter:
            return None
        if newsletter.status == NewsletterStatus.SENT:
            raise ValueError("Cannot schedule a newsletter that has already been sent")

        newsletter.scheduled_at = scheduled_at
        newsletter.status = NewsletterStatus.SCHEDULED
        db.commit()
        db.refresh(newsletter)
        logger.info(f"Newsletter id={newsletter_id} scheduled for {scheduled_at} by user_id={user_id}")
        return newsletter

    # ────────────────────────────────────────────────────────────────────────
    # Templates
    # ────────────────────────────────────────────────────────────────────────

    def get_templates(self, db: Session) -> list[NewsletterTemplate]:
        return db.query(NewsletterTemplate).filter(NewsletterTemplate.is_active == True).all()

    def seed_templates(self, db: Session) -> None:
        """Seed default newsletter templates if the table is empty."""
        existing = db.query(NewsletterTemplate).count()
        if existing > 0:
            return

        templates = [
            NewsletterTemplate(
                name="Monthly Update",
                description="A monthly summary of school news, upcoming events, and achievements.",
                content_template="""<h2 style="color:#4f46e5;font-size:24px;margin-bottom:8px;">Monthly School Update</h2>
<p style="color:#6b7280;font-size:14px;margin-bottom:24px;">[Month] [Year]</p>

<h3 style="color:#1f2937;font-size:18px;margin-bottom:8px;">Principal's Message</h3>
<p style="color:#374151;line-height:1.6;">[Write a brief welcoming message from the principal here]</p>

<h3 style="color:#1f2937;font-size:18px;margin-top:24px;margin-bottom:8px;">Upcoming Events</h3>
<ul style="color:#374151;line-height:2;padding-left:20px;">
  <li>[Event 1] — [Date]</li>
  <li>[Event 2] — [Date]</li>
  <li>[Event 3] — [Date]</li>
</ul>

<h3 style="color:#1f2937;font-size:18px;margin-top:24px;margin-bottom:8px;">School News</h3>
<p style="color:#374151;line-height:1.6;">[Share important school updates, policy changes, or announcements here]</p>

<h3 style="color:#1f2937;font-size:18px;margin-top:24px;margin-bottom:8px;">Reminders</h3>
<ul style="color:#374151;line-height:2;padding-left:20px;">
  <li>[Reminder 1]</li>
  <li>[Reminder 2]</li>
</ul>""",
                is_active=True,
            ),
            NewsletterTemplate(
                name="Event Announcement",
                description="Announce a specific school event with date, location, and details.",
                content_template="""<h2 style="color:#4f46e5;font-size:24px;margin-bottom:8px;">You're Invited!</h2>
<h3 style="color:#1f2937;font-size:20px;margin-bottom:16px;">[Event Name]</h3>

<div style="background:#f3f4f6;border-radius:8px;padding:16px;margin-bottom:24px;">
  <p style="color:#374151;margin:4px 0;"><strong>Date:</strong> [Date]</p>
  <p style="color:#374151;margin:4px 0;"><strong>Time:</strong> [Start Time] – [End Time]</p>
  <p style="color:#374151;margin:4px 0;"><strong>Location:</strong> [Venue / Room / Online link]</p>
</div>

<h3 style="color:#1f2937;font-size:18px;margin-bottom:8px;">About This Event</h3>
<p style="color:#374151;line-height:1.6;">[Describe the event in 2–3 sentences. What will happen? Why should families attend?]</p>

<h3 style="color:#1f2937;font-size:18px;margin-top:24px;margin-bottom:8px;">What to Bring</h3>
<ul style="color:#374151;line-height:2;padding-left:20px;">
  <li>[Item 1]</li>
  <li>[Item 2]</li>
</ul>

<p style="color:#374151;margin-top:24px;">For questions, please contact <a href="mailto:[contact email]" style="color:#4f46e5;">[contact name]</a>.</p>""",
                is_active=True,
            ),
            NewsletterTemplate(
                name="Achievement Spotlight",
                description="Celebrate student and staff achievements with a spotlight newsletter.",
                content_template="""<h2 style="color:#4f46e5;font-size:24px;margin-bottom:8px;">Achievement Spotlight</h2>
<p style="color:#6b7280;font-size:14px;margin-bottom:24px;">Celebrating excellence in our school community</p>

<h3 style="color:#1f2937;font-size:18px;margin-bottom:8px;">Student of the Month</h3>
<p style="color:#374151;line-height:1.6;">
  Congratulations to <strong>[Student Name]</strong> from [Grade/Class] for [reason for recognition].
  [Add 1–2 sentences about their achievement.]
</p>

<h3 style="color:#1f2937;font-size:18px;margin-top:24px;margin-bottom:8px;">Academic Achievements</h3>
<ul style="color:#374151;line-height:2;padding-left:20px;">
  <li>[Achievement 1] — [Student/Group Name]</li>
  <li>[Achievement 2] — [Student/Group Name]</li>
  <li>[Achievement 3] — [Student/Group Name]</li>
</ul>

<h3 style="color:#1f2937;font-size:18px;margin-top:24px;margin-bottom:8px;">Sports &amp; Extracurricular Highlights</h3>
<p style="color:#374151;line-height:1.6;">[Describe recent sports wins, competitions, performances, or club successes]</p>

<h3 style="color:#1f2937;font-size:18px;margin-top:24px;margin-bottom:8px;">Staff Spotlight</h3>
<p style="color:#374151;line-height:1.6;">
  A special thank you to <strong>[Staff Name]</strong> for [reason]. [Add a brief sentence about their contribution.]
</p>

<p style="color:#374151;margin-top:24px;font-style:italic;">
  Keep up the amazing work, [School Name] community! We are proud of every one of you.
</p>""",
                is_active=True,
            ),
        ]

        for template in templates:
            db.add(template)
        db.commit()
        logger.info("Seeded 3 default newsletter templates")

    # ────────────────────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────────────────────

    def _get_owned(self, newsletter_id: int, user_id: int, db: Session) -> Optional[Newsletter]:
        """Return newsletter if owned by user_id or user is admin."""
        newsletter = db.query(Newsletter).filter(Newsletter.id == newsletter_id).first()
        if not newsletter:
            return None
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.has_role(UserRole.ADMIN):
            return newsletter
        if newsletter.created_by == user_id:
            return newsletter
        return None

    def _get_recipients(self, audience: NewsletterAudience, db: Session) -> list[User]:
        """Query users matching the audience filter."""
        query = db.query(User).filter(User.is_active == True, User.email != None)

        if audience == NewsletterAudience.ALL:
            return query.all()

        role_map = {
            NewsletterAudience.PARENTS: UserRole.PARENT,
            NewsletterAudience.TEACHERS: UserRole.TEACHER,
            NewsletterAudience.STUDENTS: UserRole.STUDENT,
        }
        target_role = role_map.get(audience)
        if not target_role:
            return query.all()

        # Match users whose primary role OR comma-separated roles column includes the target
        role_value = target_role.value
        from sqlalchemy import or_
        return (
            query.filter(
                or_(
                    User.role == target_role,
                    User.roles.like(f"%{role_value}%"),
                )
            )
            .all()
        )
