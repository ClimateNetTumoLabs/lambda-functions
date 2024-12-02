import json
import boto3
from botocore.exceptions import ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
import config
def boto3_rawemailv2():
    SENDER = "baboomian53@gmail.com"
    RECIPIENT = "rnobaboomian@gmail.com"
    CONFIGURATION_SET = "ConfigSet"
    AWS_REGION = "us-east-1"
    SUBJECT = "Customer service contact info"
    ATTACHMENT = "/Users/arno/Desktop/ClimateNet/lambda-functions/mail_service/mail.zip"
    BODY_TEXT = "Hello,\r\nPlease see the attached file for a list of customers to contact."

    
    BODY_HTML = """\
    <html>
    <head/>
    <body>
    <h1>Hello!</h1>
    <p>Please see the attached file for a list of customers to contact.</p>
    </body>
    </html>
    """

    CHARSET = "utf-8"
    msg = MIMEMultipart('mixed')
    
    msg['Subject'] = SUBJECT 
    msg['From'] = SENDER 
    msg['To'] = RECIPIENT
    
    
    msg_body = MIMEMultipart('alternative')
    
    textpart = MIMEText(BODY_TEXT.encode(CHARSET), 'plain', CHARSET)
    htmlpart = MIMEText(BODY_HTML.encode(CHARSET), 'html', CHARSET)
    
    msg_body.attach(textpart)
    msg_body.attach(htmlpart)
    
    att = MIMEApplication(open(ATTACHMENT, 'rb').read())
    
    
    att.add_header('Content-Disposition','attachment',filename=os.path.basename(ATTACHMENT))
    
    
    msg.attach(msg_body)
    msg.attach(att)

    strmsg = str(msg)
    body = bytes (strmsg, 'utf-8')

    
    boto3.setup_default_session(
        aws_access_key_id=config.ACCESS_KEY,
        aws_secret_access_key=config.SECRET_KEY,
        region_name=config.REGION
    )
    client = boto3.client('sesv2')
    response = client.send_email(
    FromEmailAddress=SENDER,
    Destination={
        'ToAddresses': [RECIPIENT]
    },
    Content={
        'Raw': {
            'Data': body
        }
    }
    )
    print(response)
boto3_rawemailv2 ()