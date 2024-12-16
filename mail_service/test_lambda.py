import json
import boto3
from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
import config
from response_handler import build_error_response,build_response,build_simple_response

def lambda_handler(event, context):
    body = event.get('body')
    mail_data = None
    recipient = None
        # Parse JSON if body exists and is not already a dictionary
    if body:
        if isinstance(body, str):
            body = json.loads(body)

        mail_data= body.get('mail_data') if body else None
        recipient= body.get('recipient') if body else None


    if(body is None or mail_data is None  or recipient is None):
        return build_error_response({'err' : "body and mail_data is required",'context': {'mail_data':mail_data , 'recipient':recipient}})
    
    boto3.setup_default_session(
        aws_access_key_id=config.ACCESS_KEY,
        aws_secret_access_key=config.SECRET_KEY,
        region_name=config.REGION
    )
    client = boto3.client('sesv2')
    response = client.send_email(
    FromEmailAddress=config.SENDER,
    Destination={
        'ToAddresses': [recipient]
    },
    Content={
        'Raw': {
            'Data': mail_data
        }
    }
    )
    print(response)
    return build_response("ok 200!",response)