import json
import boto3
from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
import config
import base64
from response_handler import build_error_response,build_response,build_simple_response

def lambda_handler(event, context):
    
   
    mail_data = None
    recipient = None
    body = event.get('body', '')
    
    
    body = base64.b64decode(body).decode('utf-8')
    # body_data = json.loads(body)
    # return build_simple_response("ok",body_data.get('recipient',''))

        # Parse JSON if body exists and is not already a dictionary
    # if event.get("isBase64Encoded"):
    #     decoded_body = base64.b64decode(event["body"]).decode("utf-8")
    # else:
    #     decoded_body = event["body"]
        
        # Parse the JSON from the decoded body
    body_data = json.loads(body)
    mail_data = body_data.get('mail_data')
    recipient = body_data.get('recipient')
    if(body_data is None or mail_data is None  or recipient is None):
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