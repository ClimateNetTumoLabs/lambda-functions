"""
Local test for cognito-custom-message Lambda.

Run:
    python local_test.py
"""

import json
import os

# Simulate the Lambda environment variable
os.environ.setdefault("REDIRECT_URL", "https://climatenet.am/verify")

from lambda_function import lambda_handler, REDIRECT_URL


def test_signup():
    """Simulate a CustomMessage_SignUp event."""
    event = {
        "version": "1",
        "region": "us-east-1",
        "userPoolId": "us-east-1_jYZ2nnwaB",
        # This pool uses email as a username attribute, so the event's
        # userName is Cognito's generated internal UUID — NOT the email.
        "userName": "840884d8-10d1-7035-be7f-00082e74d343",
        "triggerSource": "CustomMessage_SignUp",
        "request": {
            "userAttributes": {
                "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "email": "testuser@example.com",
                "email_verified": "false",
                "cognito:user_status": "UNCONFIRMED",
            },
            "codeParameter": "{####}",
            "linkParameter": "{##Click Here##}",
            "usernameParameter": None,
        },
        "response": {
            "smsMessage": None,
            "emailMessage": None,
            "emailSubject": None,
        },
        "callerContext": {
            "awsSdkVersion": "aws-sdk-python-boto3-1.26.0",
            "clientId": "4tu98tl1sh8bsqq5fhjdk0udqm",
        },
    }

    result = lambda_handler(event, None)

    print("=" * 60)
    print("TEST: CustomMessage_SignUp")
    print("=" * 60)
    print(f"Subject: {result['response']['emailSubject']}")
    print(f"HTML length: {len(result['response']['emailMessage'])} chars")
    print()
    print("--- HTML Preview (first 500 chars) ---")
    print(result["response"]["emailMessage"][:500])
    print("...")
    print()

    # Verify the link placeholder is embedded
    assert "{####}" in result["response"]["emailMessage"], "Code placeholder {####} missing!"
    # The link must carry the EMAIL, not the internal UUID username —
    # Django's pending-registration cache is keyed by email.
    assert "username=testuser%40example.com" in result["response"]["emailMessage"], \
        "Email missing from verify link!"
    assert "username=840884d8" not in result["response"]["emailMessage"], \
        "Internal UUID username leaked into the verify link!"
    # The code must live in a URL fragment (#), never a query string (?) —
    # fragments aren't sent to the server, so they don't leak into access
    # logs, proxy logs, or a cross-origin Referer header.
    assert f"{REDIRECT_URL}#code=" in result["response"]["emailMessage"], \
        "Verify link must use a # fragment, not a ? query string, for code/username!"
    print("✅ Signup email assertions passed.\n")


def test_signup_email_with_plus_is_url_encoded():
    """Emails with '+' aliases must survive the round trip — unencoded,
    '+' decodes to a space in query strings on the frontend."""
    event = {
        "userName": "840884d8-10d1-7035-be7f-00082e74d343",
        "triggerSource": "CustomMessage_SignUp",
        "request": {
            "userAttributes": {
                "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "email": "someone+alias@example.com",
            },
            "codeParameter": "{####}",
        },
        "response": {"smsMessage": None, "emailMessage": None, "emailSubject": None},
    }

    result = lambda_handler(event, None)

    print("=" * 60)
    print("TEST: CustomMessage_SignUp email with '+' is URL-encoded")
    print("=" * 60)
    assert "username=someone%2Balias%40example.com" in result["response"]["emailMessage"], \
        "Email with '+' was not URL-encoded in the verify link!"
    assert "username=someone+alias@example.com" not in result["response"]["emailMessage"], \
        "Raw unencoded email leaked into the link!"
    print("✅ Email URL-encoding assertions passed.\n")


def test_resend_code():
    """CustomMessage_ResendCode must be handled identically to SignUp."""
    event = {
        "userName": "840884d8-10d1-7035-be7f-00082e74d343",
        "triggerSource": "CustomMessage_ResendCode",
        "request": {
            "userAttributes": {
                "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "email": "testuser@example.com",
            },
            "codeParameter": "{####}",
        },
        "response": {"smsMessage": None, "emailMessage": None, "emailSubject": None},
    }

    result = lambda_handler(event, None)

    print("=" * 60)
    print("TEST: CustomMessage_ResendCode")
    print("=" * 60)
    assert "{####}" in result["response"]["emailMessage"], "Code placeholder {####} missing!"
    assert "username=testuser%40example.com" in result["response"]["emailMessage"], \
        "Email missing from resend link!"
    print("✅ Resend-code email assertions passed.\n")


def test_forgot_password():
    """Simulate a CustomMessage_ForgotPassword event."""
    event = {
        "version": "1",
        "region": "us-east-1",
        "userPoolId": "us-east-1_jYZ2nnwaB",
        "userName": "840884d8-10d1-7035-be7f-00082e74d343",
        "triggerSource": "CustomMessage_ForgotPassword",
        "request": {
            "userAttributes": {
                "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "email": "testuser@example.com",
                "email_verified": "true",
            },
            "codeParameter": "{####}",
            "linkParameter": "{##Click Here##}",
            "usernameParameter": None,
        },
        "response": {
            "smsMessage": None,
            "emailMessage": None,
            "emailSubject": None,
        },
        "callerContext": {
            "awsSdkVersion": "aws-sdk-python-boto3-1.26.0",
            "clientId": "4tu98tl1sh8bsqq5fhjdk0udqm",
        },
    }

    result = lambda_handler(event, None)

    print("=" * 60)
    print("TEST: CustomMessage_ForgotPassword")
    print("=" * 60)
    print(f"Subject: {result['response']['emailSubject']}")
    print(f"HTML length: {len(result['response']['emailMessage'])} chars")
    print()

    assert "{####}" in result["response"]["emailMessage"], "Code placeholder {####} missing!"
    assert "action=reset" in result["response"]["emailMessage"], "Reset action param missing!"
    assert "username=testuser%40example.com" in result["response"]["emailMessage"], \
        "Email missing from reset link!"
    assert f"{REDIRECT_URL}#code=" in result["response"]["emailMessage"], \
        "Reset link must use a # fragment, not a ? query string, for code/username!"
    print("✅ Forgot-password email assertions passed.\n")


if __name__ == "__main__":
    test_signup()
    test_signup_email_with_plus_is_url_encoded()
    test_resend_code()
    test_forgot_password()
    print("🎉 All tests passed.")
