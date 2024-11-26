import boto3
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    ses_client = boto3.client("ses", region_name="us-east-1")

    sender = "baboomian53@gmail.com"
    recipient = event.get("recipient")
    subject = event.get("subject", "Default Subject")
    body_text = event.get("body_text", "Default text message body")
    body_html = event.get("body_html", "<html><body><p>Default HTML message body</p></body></html>")

    if not recipient:
        return {"statusCode": 400, "body": "Recipient email is required"}

    email_params = {
        "Source": sender,
        "Destination": {
            "ToAddresses": [recipient]
        },
        "Message": {
            "Subject": {
                "Data": subject
            },
            "Body": {
                "Text": {
                    "Data": body_text
                },
                "Html": {
                    "Data": body_html
                }
            }
        }
    }

    try:
        response = ses_client.send_email(**email_params)
        print(f"Email sent! Message ID: {response['MessageId']}")
        return {"statusCode": 200, "body": "Email sent successfully!"}
    except ClientError as e:
        print(f"Error sending email: {e.response['Error']['Message']}")
        return {"statusCode": 500, "body": "Error sending email"}
