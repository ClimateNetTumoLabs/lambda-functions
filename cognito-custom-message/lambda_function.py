"""
AWS Lambda: cognito-custom-message

Cognito trigger: Custom Message
Handles: CustomMessage_SignUp, CustomMessage_ResendCode, CustomMessage_ForgotPassword

Reads REDIRECT_URL from environment variables and constructs a modern HTML
email containing a verification link with the code and username embedded.
"""

import os
from urllib.parse import quote

# ── Global scope: read env once (warm-start optimization) ────────────────────
REDIRECT_URL = os.environ.get("REDIRECT_URL", "https://climatenet.am/verify")


def lambda_handler(event, context):
    trigger = event.get("triggerSource", "")

    if trigger in ("CustomMessage_SignUp", "CustomMessage_ResendCode"):
        event = _handle_signup(event)
    elif trigger == "CustomMessage_ForgotPassword":
        event = _handle_forgot_password(event)

    return event


# ── Handlers ─────────────────────────────────────────────────────────────────

def _link_identity(event):
    """
    The identity to embed in the link. This pool uses email as a username
    attribute, so event["userName"] is Cognito's generated internal UUID —
    useless to Django, whose pending-registration cache is keyed by email.
    Cognito's ConfirmSignUp accepts the email alias just as well as the
    UUID, so the email works for both sides of the confirm call.
    Query-string encoded: emails containing "+" (a common alias pattern)
    otherwise get silently decoded to a space by URLSearchParams.
    """
    identity = event["request"]["userAttributes"].get("email") or event["userName"]
    return quote(identity, safe="")


def _handle_signup(event):
    """Build a branded verification email with a clickable link."""
    code_placeholder = event["request"]["codeParameter"]  # resolves to {####}

    # A URL fragment (#) is never sent to a server, unlike a query string
    # (?) - keeps the code out of proxy/server access logs and off any
    # cross-origin Referer header.
    verify_link = f"{REDIRECT_URL}#code={code_placeholder}&username={_link_identity(event)}"

    event["response"]["emailSubject"] = "Verify your ClimateNet account"
    event["response"]["emailMessage"] = _render_email(
        greeting="Welcome to ClimateNet!",
        message_html=(
            "<p class=\"message\">Thanks for signing up. Click the button below to verify your "
            "email address and activate your account.</p>"
        ),
        button_label="Verify Email",
        button_url=verify_link,
        footer_note=(
            f"If the button doesn't work, copy and paste this link into your browser:<br>{verify_link}"
        ),
    )
    return event


def _handle_forgot_password(event):
    """Build a branded password-reset email with the reset code."""
    code_placeholder = event["request"]["codeParameter"]  # resolves to {####}

    reset_link = f"{REDIRECT_URL}#code={code_placeholder}&username={_link_identity(event)}&action=reset"

    event["response"]["emailSubject"] = "Reset your ClimateNet password"
    event["response"]["emailMessage"] = _render_email(
        greeting="Password reset requested",
        message_html=(
            "<p class=\"message\">We received a request to reset your password. "
            "Click the button below to choose a new password.</p>"
        ),
        button_label="Reset Password",
        button_url=reset_link,
        footer_note=(
            "If you didn't request this, you can safely ignore this email."
            f"<br><br>Or copy and paste this link into your browser:<br>{reset_link}"
        ),
    )
    return event


# ── Email template ───────────────────────────────────────────────────────────

def _render_email(greeting, message_html, button_label, button_url, footer_note):
    return f"""\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>ClimateNet</title>
    <style>
      body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        margin: 0;
        padding: 40px 20px;
        background-color: #efefef;
        color: #333232;
      }}
      .wrapper {{
        max-width: 600px;
        margin: 0 auto;
        background-color: #ffffff;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border: 1px solid #e5e7eb;
      }}
      .header {{
        height: 120px;
        background-image: url("https://climatenet.am/statics/mail/banner.jpg");
        background-size: cover;
        background-position: left center;
      }}
      .content {{
        padding: 40px;
      }}
      .greeting {{
        font-size: 20px;
        font-weight: 600;
        margin-top: 0;
        margin-bottom: 20px;
        color: #010101;
      }}
      .message {{
        font-size: 16px;
        line-height: 1.6;
        margin-bottom: 20px;
        color: #333232;
      }}
      .footerNote {{
        font-size: 13px;
        line-height: 1.5;
        color: #6b7280;
        margin-top: 8px;
      }}
      .signature {{
        margin-top: 40px;
        font-size: 15px;
        color: #333232;
        line-height: 1.5;
      }}
      .btn {{
        display: inline-block;
        padding: 12px 24px;
        background-color: #0a8e62;
        color: #ffffff !important;
        text-decoration: none;
        border-radius: 6px;
        font-weight: 600;
        margin-top: 10px;
        margin-bottom: 10px;
        text-align: center;
      }}
      .btn:hover {{
        background-color: #087a52;
      }}
      @media (max-width: 600px) {{
        .content {{
          padding: 25px;
        }}
        .header {{
          height: 100px;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="wrapper">
      <div class="header"></div>
      <div class="content">
        <h1 class="greeting">{greeting}</h1>
        {message_html}
        <a href="{button_url}" target="_blank" class="btn">{button_label}</a>
        <p class="footerNote">{footer_note}</p>

        <div class="signature">
          Best regards,<br />
          <strong>The ClimateNet Team</strong>

          <br />
          <br />
          <table cellpadding="0" cellspacing="0" border="0" style="font-family: Arial, sans-serif; max-width: 420px; width: 100%">
            <tr>
              <td style="border-bottom: 1px solid #aaaaaa; padding-bottom: 8px"></td>
            </tr>
            <tr>
              <td style="padding: 12px 0 4px 0; vertical-align: middle">
                <span style="font-family: Arial, sans-serif; font-size: 20px; color: #0a8e62; font-weight: bold; vertical-align: middle; line-height: 1">Climate</span
                ><img src="https://climatenet.am/media/Logos/globe.svg" alt="Globe" width="22" height="22" style="vertical-align: middle; margin: 0 4px; display: inline-block" /><span
                  style="font-family: Arial, sans-serif; font-size: 20px; color: #0a8e62; font-weight: normal; vertical-align: middle; line-height: 1"
                  >Net</span
                >
              </td>
            </tr>
            <tr>
              <td style="padding-top: 10px; font-size: 11px; color: #888888">
                <div style="margin-bottom: 4px">
                  <a href="mailto:labs@tumo.org" style="color: #888888; text-decoration: none">labs@tumo.org</a>
                </div>
                <div style="margin-bottom: 4px">
                  <a href="https://climatenet.am/" style="color: #888888; text-decoration: none">climatenet.am</a>
                </div>
                <div>
                  <a href="https://www.google.com/maps/search/TUMO+Labs" style="color: #888888; text-decoration: none">Halabyan 2A | Yerevan, Armenia</a>
                </div>
              </td>
            </tr>
          </table>
        </div>
      </div>
    </div>
  </body>
</html>"""
