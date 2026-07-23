"""
Smoke test against the real database.

Reads DB_HOST, DB_USER, DB_PASSWORD, DB_NAME from the environment, the same as
the deployed function:

    DB_HOST=... DB_USER=... DB_PASSWORD=... DB_NAME=... python main.py

For tests that need no credentials and no RDS, use local_test.py instead.
"""

import base64
import gzip
import json
from lambda_function import lambda_handler


def main():
    # Mock event to simulate API Gateway request
    event = {
        "queryStringParameters": {
            "device_id": "8",
            # Uncomment to test a specific range. Format is YYYY-MM-DD.
            # "start_time": "2025-01-06",
            # "end_time": "2025-01-07"
        },
        "requestContext": {
            "http": {
                "sourceIp": '212.34.238.10'
            }
        }
    }

    context = {}

    try:
        response = lambda_handler(event, context)

        # Wide ranges come back gzipped; decode so the output stays readable.
        if response.get('isBase64Encoded'):
            body = gzip.decompress(base64.b64decode(response['body'])).decode()
            print(f"(response was gzipped, {len(response['body'])} bytes on the wire)")
        else:
            body = response['body']

        print("Lambda Function Response:")
        print(f"statusCode: {response['statusCode']}")
        parsed = json.loads(body)
        if 'data' in parsed:
            print(f"rows: {len(parsed['data'])}")
            print(json.dumps({'keys': parsed['keys'], 'data': parsed['data'][:3]}, indent=2))
        else:
            print(json.dumps(parsed, indent=2))
    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    main()
