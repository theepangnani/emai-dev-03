"""Firebase Cloud Messaging (FCM) push notification service.

Uses the FCM HTTP v1 API with OAuth2 service account authentication.
Push is a non-critical channel — all failures are logged and swallowed so
in-app and email notifications continue to work without FCM configured.
"""
import json
import logging
from datetime import datetime, timezone

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

FCM_SEND_URL = (
    "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
)


class PushNotificationService:
    """Firebase Cloud Messaging HTTP v1 API service.

    Authentication uses a Google service account JSON credential stored in
    ``settings.FIREBASE_SERVICE_ACCOUNT_JSON``.  The OAuth2 access token is
    cached in-memory and refreshed automatically on expiry.

    All public methods fail gracefully when Firebase is not configured —
    they log a warning and return an empty result dict instead of raising.
    """

    def __init__(self) -> None:
        self.project_id: str = getattr(settings, "firebase_project_id", "")
        self._access_token: str | None = None
        self._token_expiry: datetime | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_configured(self) -> bool:
        """Return True when Firebase credentials are present."""
        sa_json = getattr(settings, "firebase_service_account_json", "")
        return bool(self.project_id and sa_json)

    async def _get_access_token(self) -> str:
        """Return a valid FCM OAuth2 access token, refreshing if needed.

        Uses ``google-auth`` service account credentials.  The token is
        cached for its lifetime (typically 1 hour).
        """
        now = datetime.now(timezone.utc)

        # Return cached token if still valid (with 60s safety margin)
        if (
            self._access_token
            and self._token_expiry
            and (self._token_expiry - now).total_seconds() > 60
        ):
            return self._access_token

        # Import google-auth here so the rest of the app works even when
        # the library is absent (fails later with a clear error).
        try:
            import google.auth.transport.requests
            from google.oauth2 import service_account
        except ImportError as exc:
            raise RuntimeError(
                "google-auth is required for FCM push notifications. "
                "Add 'google-auth' to requirements.txt."
            ) from exc

        sa_json_str = getattr(settings, "firebase_service_account_json", "")
        sa_info = json.loads(sa_json_str)
        creds = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/firebase.messaging"],
        )
        request = google.auth.transport.requests.Request()
        creds.refresh(request)

        self._access_token = creds.token
        # google-auth sets creds.expiry (datetime without tz) — convert to UTC
        if creds.expiry:
            self._token_expiry = creds.expiry.replace(tzinfo=timezone.utc)
        else:
            # Fallback: assume 1 hour
            from datetime import timedelta
            self._token_expiry = now + timedelta(hours=1)

        return self._access_token  # type: ignore[return-value]

    def _build_message(
        self,
        token: str,
        title: str,
        body: str,
        data: dict | None = None,
        image_url: str | None = None,
    ) -> dict:
        """Construct the FCM v1 message payload."""
        notification: dict = {"title": title, "body": body}
        if image_url:
            notification["image"] = image_url

        message: dict = {
            "token": token,
            "notification": notification,
        }

        if data:
            # FCM data values must be strings
            message["data"] = {k: str(v) for k, v in data.items()}

        return {"message": message}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_to_token(
        self,
        token: str,
        title: str,
        body: str,
        data: dict | None = None,
        image_url: str | None = None,
    ) -> dict:
        """Send a push notification to a single FCM registration token.

        Returns a dict with ``message_id`` on success, or ``error`` on
        failure.  Never raises.
        """
        if not self._is_configured():
            logger.debug(
                "FCM not configured (FIREBASE_PROJECT_ID / "
                "FIREBASE_SERVICE_ACCOUNT_JSON missing) — skipping push."
            )
            return {"skipped": True, "reason": "not_configured"}

        try:
            access_token = await self._get_access_token()
            url = FCM_SEND_URL.format(project_id=self.project_id)
            payload = self._build_message(token, title, body, data, image_url)

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                )

            if resp.status_code == 200:
                result = resp.json()
                return {"message_id": result.get("name", ""), "status": "sent"}

            # Non-200: parse FCM error
            try:
                err_body = resp.json()
                err_msg = (
                    err_body.get("error", {}).get("message", resp.text)
                )
            except Exception:
                err_msg = resp.text

            logger.warning(
                "FCM send failed for token %s: HTTP %s — %s",
                token[:20] + "...",
                resp.status_code,
                err_msg,
            )
            return {
                "error": err_msg,
                "status_code": resp.status_code,
                "token": token,
            }

        except Exception as exc:
            logger.warning("FCM send_to_token exception: %s", exc)
            return {"error": str(exc), "token": token}

    async def send_to_user(
        self,
        user_id: int,
        title: str,
        body: str,
        data: dict | None = None,
        db=None,
    ) -> dict:
        """Send to ALL active push tokens belonging to a user.

        Tokens that return a 404 (UNREGISTERED) response are automatically
        deactivated.  Returns ``{sent: N, failed: M}``.
        """
        if not self._is_configured():
            return {"skipped": True, "reason": "not_configured"}

        if db is None:
            logger.warning("send_to_user called without db session — skipping.")
            return {"sent": 0, "failed": 0}

        try:
            from app.models.push_token import PushToken  # avoid circular import

            tokens = (
                db.query(PushToken)
                .filter(
                    PushToken.user_id == user_id,
                    PushToken.is_active.is_(True),
                )
                .all()
            )
        except Exception as exc:
            logger.warning("Failed to query push tokens for user %s: %s", user_id, exc)
            return {"sent": 0, "failed": 0}

        if not tokens:
            return {"sent": 0, "failed": 0, "no_tokens": True}

        sent = 0
        failed = 0
        now = datetime.now(timezone.utc)

        for pt in tokens:
            result = await self.send_to_token(pt.token, title, body, data)

            if result.get("message_id"):
                sent += 1
                pt.last_used_at = now
            else:
                failed += 1
                # Deactivate token if FCM says it is no longer registered
                status_code = result.get("status_code")
                error_msg = result.get("error", "")
                if status_code == 404 or "UNREGISTERED" in str(error_msg):
                    logger.info(
                        "Deactivating stale FCM token for user %s (token: %s...)",
                        user_id,
                        pt.token[:20],
                    )
                    pt.is_active = False

        try:
            db.commit()
        except Exception as exc:
            logger.warning("DB commit failed after send_to_user: %s", exc)

        return {"sent": sent, "failed": failed}

    async def send_to_users(
        self,
        user_ids: list[int],
        title: str,
        body: str,
        data: dict | None = None,
        db=None,
    ) -> dict:
        """Batch-send the same push notification to multiple users.

        Returns aggregated ``{sent: N, failed: M, users_reached: K}``.
        """
        if not self._is_configured():
            return {"skipped": True, "reason": "not_configured"}

        total_sent = 0
        total_failed = 0
        users_reached = 0

        for uid in user_ids:
            result = await self.send_to_user(uid, title, body, data, db=db)
            s = result.get("sent", 0)
            f = result.get("failed", 0)
            total_sent += s
            total_failed += f
            if s > 0:
                users_reached += 1

        return {
            "sent": total_sent,
            "failed": total_failed,
            "users_reached": users_reached,
        }

    async def send_multicast(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict | None = None,
    ) -> dict:
        """Send the same message to an arbitrary list of tokens.

        FCM HTTP v1 does not support true multicast in a single request, so
        tokens are sent individually.  Returns ``{sent: N, failed: M}``.
        """
        if not self._is_configured():
            return {"skipped": True, "reason": "not_configured"}

        sent = 0
        failed = 0

        for token in tokens:
            result = await self.send_to_token(token, title, body, data)
            if result.get("message_id"):
                sent += 1
            else:
                failed += 1

        return {"sent": sent, "failed": failed, "total": len(tokens)}


# ---------------------------------------------------------------------------
# Singleton — import this in routes / services
# ---------------------------------------------------------------------------
push_service = PushNotificationService()


# ---------------------------------------------------------------------------
# Integration hook for existing notification system
# ---------------------------------------------------------------------------

async def send_push_for_notification(
    notification_data: dict,
    user_id: int,
    db=None,
) -> None:
    """Called after an in-app notification is created.

    Sends an FCM push to all active devices registered for the user.
    This is non-critical: failures are logged but never re-raised.

    Args:
        notification_data: Dict containing at least ``message`` and ``type``
            fields (same shape as the Notification model dict/schema).
        user_id: Recipient user id.
        db: SQLAlchemy ``Session``.  Must be provided for token lookup.
    """
    try:
        title = "ClassBridge"
        body = notification_data.get("message") or notification_data.get("content", "You have a new notification")
        # Truncate body for push display
        if len(body) > 200:
            body = body[:197] + "..."

        push_data = {
            "notification_type": notification_data.get("type", ""),
            "url": notification_data.get("url") or notification_data.get("link", ""),
        }

        await push_service.send_to_user(
            user_id=user_id,
            title=title,
            body=body,
            data=push_data,
            db=db,
        )
    except Exception as exc:
        logger.warning(
            "send_push_for_notification failed for user %s: %s", user_id, exc
        )
