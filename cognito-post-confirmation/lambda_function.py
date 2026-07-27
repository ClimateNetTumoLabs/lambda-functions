"""
AWS Lambda: cognito-post-confirmation

Cognito trigger: Post Confirmation
Handles: PostConfirmation_ConfirmSignUp

After a user successfully confirms their account, this Lambda fires a
webhook to the Django backend so it can persist the user profile.

Uses only stdlib (urllib) — no external dependencies.
"""

import json
import logging
import os
import urllib.request
import urllib.error

# ── Global scope: initialise once per container (warm-start optimization) ────
logger = logging.getLogger()
logger.setLevel(logging.INFO)

DJANGO_WEBHOOK_URL = os.environ.get(
    "DJANGO_WEBHOOK_URL",
    "https://climatenet.am/api/webhooks/cognito-confirm/",
)
WEBHOOK_SHARED_SECRET = os.environ.get("WEBHOOK_SHARED_SECRET", "")


def lambda_handler(event, context):
    trigger = event.get("triggerSource", "")

    if trigger != "PostConfirmation_ConfirmSignUp":
        # Not our concern — pass through unchanged
        return event

    try:
        _notify_django(event)
    except Exception:
        # Log but never raise — a Lambda error here would block Cognito
        # from completing the confirmation flow.
        logger.exception("Failed to notify Django webhook")

    return event


def _notify_django(event):
    """POST the confirmed user's identity to the Django webhook."""
    user_attrs = event["request"]["userAttributes"]

    payload = json.dumps({
        "sub": user_attrs["sub"],
        "username": event["userName"],
        "email": user_attrs.get("email", ""),
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Secret": WEBHOOK_SHARED_SECRET,
    }

    req = urllib.request.Request(
        DJANGO_WEBHOOK_URL,
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.getcode()
            body = resp.read().decode("utf-8")
            logger.info(
                "Django webhook responded: status=%d body=%s",
                status_code,
                body[:200],
            )
    except urllib.error.HTTPError as exc:
        logger.error(
            "Django webhook HTTP error: status=%d body=%s",
            exc.code,
            exc.read().decode("utf-8", errors="replace")[:500],
        )
        raise
    except urllib.error.URLError as exc:
        logger.error("Django webhook URL error: %s", exc.reason)
        raise
