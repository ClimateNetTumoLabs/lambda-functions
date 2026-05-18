"""
Mail service Lambda — event-based email delivery via AWS SES v2.

Accepts structured event payloads from Django:
    {
        "event": "approval",
        "recipient": "user@example.com",
        "name": "John Doe",
        "attachment": "<base64>",            # optional
        "attachment_filename": "certs.zip"    # optional
    }

Sender is configured in config.SENDER
"""

import json
import os
import base64
import boto3
from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

import config
from response_handler import (
    build_response,
    build_error_response,
    build_simple_response,
    build_bad_request_response,
)

# ---- Template registry ------------------------------------------------
# Each event type maps to a subject line and an HTML template file.
# To add a new email type, drop an HTML file in mail/ and add a mapping.

TEMPLATES = {
    "notify": {
        "subject": "Thanks for Your Request – ClimateNet DIY Kit",
        "file": "notify.html",
    },
    "approval": {
        "subject": "Your ClimateNet DIY Kit Has Been Approved!",
        "file": "approval.html",
    },
    "rejection": {
        "subject": "Update on Your ClimateNet DIY Kit Request",
        "file": "decline.html",
    },
    "termination": {
        "subject": "ClimateNet Device Termination Notice",
        "file": "termination.html",
    },
}

import urllib.request
import time
from email.utils import make_msgid

# Base URL where templates are hosted on S3/Static hosting
_TEMPLATE_BASE_URL = "https://climatenet.am/statics/mail"

# In-memory cache for fetched templates to speed up warm invocations
_TEMPLATE_CACHE = {}


def lambda_handler(event, context):
    """
    Entry point.  Accepts API Gateway events with a JSON body.
    """
    try:
        body = _parse_body(event)
    except Exception as exc:
        return build_bad_request_response(f"Invalid request body: {exc}")

    if body is None:
        return build_bad_request_response("Request body is required.")

    event_type = body.get("event")
    recipient = body.get("recipient")
    name = body.get("name", "")

    # --- Validation -------------------------------------------------------
    if not event_type:
        return build_bad_request_response(
            "Missing 'event'. Valid values: " + ", ".join(TEMPLATES.keys())
        )
    if event_type not in TEMPLATES:
        return build_bad_request_response(
            f"Unknown event '{event_type}'. Valid values: "
            + ", ".join(TEMPLATES.keys())
        )
    if not recipient:
        return build_bad_request_response("Missing 'recipient' (email address).")

    # --- Render template --------------------------------------------------
    template_cfg = TEMPLATES[event_type]
    subject = template_cfg["subject"]
    cache_buster = int(time.time())

    try:
        html_body = _render_template(template_cfg["file"], {
            "recipient_name": name,
            "recipient_email": name or recipient,
            "access_uuid": body.get("access_uuid", ""),
            "cache_buster": cache_buster,
        })
    except FileNotFoundError:
        return build_error_response(
            f"Template file not found: {template_cfg['file']}"
        )

    # --- Build MIME message -----------------------------------------------
    attachment_data = body.get("attachment")          # base64-encoded
    attachment_filename = body.get("attachment_filename", "attachment.zip")

    raw_email = _build_mime(
        sender=config.SENDER,
        recipient=recipient,
        subject=subject,
        html_body=html_body,
        attachment_b64=attachment_data,
        attachment_filename=attachment_filename,
    )

    # --- Send via SES v2 --------------------------------------------------
    try:
        ses_response = _send_raw_email(
            sender=config.SENDER,
            recipient=recipient,
            raw_data=raw_email,
        )
    except ClientError as exc:
        return build_error_response(f"SES send failed: {exc}")

    return build_response(
        f"Email '{event_type}' sent to {recipient}.",
        ses_response,
    )


# ---- Internal helpers ---------------------------------------------------

def _parse_body(event):
    """Extract and parse the JSON body from the API Gateway event."""
    body = event.get("body", "")
    if not body:
        return None

    # API Gateway may base64-encode the body
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    elif isinstance(body, str):
        # Try raw JSON first; fall back to base64 decode
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            body = base64.b64decode(body).decode("utf-8")

    if isinstance(body, dict):
        return body
    return json.loads(body)


def _render_template(filename, variables):
    """
    Fetch an HTML template from remote URL (with caching) and substitute {{variable}} placeholders.
    It wraps the specific template inside a shared 'base.html'.
    """
    def _fetch(name):
        if name in _TEMPLATE_CACHE:
            return _TEMPLATE_CACHE[name]
        url = f"{_TEMPLATE_BASE_URL}/{name}"
        try:
            with urllib.request.urlopen(url) as response:
                html_content = response.read().decode("utf-8")
                _TEMPLATE_CACHE[name] = html_content
                return html_content
        except Exception as e:
            raise FileNotFoundError(f"Failed to fetch template from {url}: {e}")

    # Fetch inner template and base template
    inner_html = _fetch(filename)
    base_html = _fetch("base.html")

    # Inject variables into inner template
    for key, value in variables.items():
        inner_html = inner_html.replace("{{" + key + "}}", str(value))
        
    # Wrap with base template
    final_html = base_html.replace("{{content}}", inner_html)
    
    # Inject variables into base template (like recipient_name if needed in base)
    for key, value in variables.items():
        final_html = final_html.replace("{{" + key + "}}", str(value))

    return final_html


def _build_mime(sender, recipient, subject, html_body,
                attachment_b64=None, attachment_filename="attachment.zip"):
    """
    Build a raw MIME email string.
    """
    charset = "utf-8"
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg["Reply-To"] = "labs@tumo.org"
    
    unique_msg_id = make_msgid(domain="climatenet.am")
    msg["Message-ID"] = unique_msg_id
    # Setting a unique References header forces strict email clients like Gmail to treat this as a standalone thread
    msg["References"] = unique_msg_id

    # HTML body
    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(html_body.encode(charset), "html", charset))
    msg.attach(body_part)

    # Optional attachment
    if attachment_b64:
        try:
            raw_bytes = base64.b64decode(attachment_b64)
            att = MIMEApplication(raw_bytes)
            att.add_header(
                "Content-Disposition", "attachment",
                filename=attachment_filename,
            )
            msg.attach(att)
        except Exception as exc:
            print(f"Warning: failed to attach file: {exc}")

    return msg.as_string()


def _send_raw_email(sender, recipient, raw_data):
    """
    Send a raw email via AWS SES v2.
    """
    boto3.setup_default_session(
        aws_access_key_id=config.ACCESS_KEY,
        aws_secret_access_key=config.SECRET_KEY,
        region_name=config.REGION,
    )
    client = boto3.client("sesv2")
    response = client.send_email(
        FromEmailAddress=sender,
        Destination={"ToAddresses": [recipient]},
        Content={"Raw": {"Data": raw_data}},
    )
    print(f"SES response: {response}")
    return response