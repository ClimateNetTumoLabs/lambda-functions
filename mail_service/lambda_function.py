import boto3
from botocore.exceptions import ClientError
import config
def lambda_handler(event, context):
    boto3.setup_default_session(
        aws_access_key_id=config.ACCESS_KEY,
        aws_secret_access_key=config.SECRET_KEY,
        region_name=config.REGION
    )
    ses_client = boto3.client("ses")

    sender = "baboomian53@gmail.com"
    recipient = event.get("recipient")
    subject = event.get("subject", "Welcome to ClimateNet!")
    body_text = event.get("body_text", "Welcome to ClimateNet! We're thrilled to have you.")
    body_html_template = event.get("body_html")

    if not recipient:
        return {"statusCode": 400, "body": "Recipient email is required"}
    
    if not body_html_template:
        return {"statusCode": 400, "body": "HTML content is required"}

    # Replace placeholder in the HTML template if exists
    body_html = body_html_template.replace("{{recipient_email}}", recipient)

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
        return {"statusCode": 200, "body": "Email sent successfully!", "recipient": recipient}
    except ClientError as e:
        print(f"Error sending email: {e.response['Error']['Message']}")
        return {"statusCode": 500, "body": f"Error sending email: {e.response['Error']['Message']}"}
