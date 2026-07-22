"""
Local test for cognito-post-confirmation Lambda.

Run:
    python local_test.py

NOTE: This test invokes the handler but the actual HTTP POST to Django
will fail unless you have the Django server running locally. The test
verifies that the handler processes the event without raising and
gracefully handles the connection error.
"""

import json
import os

# Simulate Lambda environment variables — point to localhost for testing
os.environ.setdefault(
    "DJANGO_WEBHOOK_URL",
    "http://localhost:8000/api/webhooks/cognito-confirm/",
)
os.environ.setdefault("WEBHOOK_SHARED_SECRET", "test-secret-for-local-dev")

from lambda_function import lambda_handler


def test_confirm_signup():
    """Simulate a PostConfirmation_ConfirmSignUp event."""
    event = {
        "version": "1",
        "region": "us-east-1",
        "userPoolId": "us-east-1_jYZ2nnwaB",
        "userName": "testuser123",
        "triggerSource": "PostConfirmation_ConfirmSignUp",
        "request": {
            "userAttributes": {
                "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "email_verified": "true",
                "cognito:user_status": "CONFIRMED",
                "email": "testuser@example.com",
            }
        },
        "response": {},
        "callerContext": {
            "awsSdkVersion": "aws-sdk-python-boto3-1.26.0",
            "clientId": "4tu98tl1sh8bsqq5fhjdk0udqm",
        },
    }

    print("=" * 60)
    print("TEST: PostConfirmation_ConfirmSignUp")
    print("=" * 60)
    print(f"Payload that would be POSTed to Django:")
    print(
        json.dumps(
            {
                "sub": event["request"]["userAttributes"]["sub"],
                "username": event["userName"],
                "email": event["request"]["userAttributes"]["email"],
            },
            indent=2,
        )
    )
    print()

    result = lambda_handler(event, None)

    # The handler must ALWAYS return the event, even if the webhook fails
    assert result is event, "Handler must return the original event!"
    assert result["triggerSource"] == "PostConfirmation_ConfirmSignUp"
    print("✅ Handler returned the event without raising.")
    print("   (HTTP POST may have failed — that's expected without a running Django server)")
    print()


def test_ignored_trigger():
    """Verify that non-ConfirmSignUp triggers are passed through."""
    event = {
        "version": "1",
        "triggerSource": "PostConfirmation_ConfirmForgotPassword",
        "userName": "testuser123",
        "request": {
            "userAttributes": {
                "sub": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "email": "testuser@example.com",
            }
        },
        "response": {},
    }

    print("=" * 60)
    print("TEST: Ignored trigger (ConfirmForgotPassword)")
    print("=" * 60)

    result = lambda_handler(event, None)
    assert result is event, "Handler must pass through non-signup triggers!"
    print("✅ Non-signup trigger correctly passed through.\n")


if __name__ == "__main__":
    test_confirm_signup()
    test_ignored_trigger()
    print("🎉 All tests passed.")
