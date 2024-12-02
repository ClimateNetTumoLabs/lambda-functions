import json
import os
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

def boto3_rawemailv2():
    SENDER = "baboomian53@gmail.com"
    RECIPIENT = "rnobaboomian@gmail.com"
    SUBJECT = "Customer service contact info"
    
    ATTACHMENT = None
    HTML_FILE_PATH = "./html/notify.html"  
    BODY_TEXT = "Hello,\r\nPlease see the attached file for a list of customers to contact."

    CHARSET = "utf-8"

    
    try:
        with open(HTML_FILE_PATH, "r", encoding="utf-8") as html_file:
            BODY_HTML = html_file.read()
    except FileNotFoundError:
        print(f"Error: HTML file not found at {HTML_FILE_PATH}")
        return
    except Exception as e:
        print(f"Error reading HTML file: {e}")
        return

    
    msg = MIMEMultipart('mixed')
    msg['Subject'] = SUBJECT
    msg['From'] = SENDER
    msg['To'] = RECIPIENT

    
    msg_body = MIMEMultipart('alternative')
    textpart = MIMEText(BODY_TEXT.encode(CHARSET), 'plain', CHARSET)
    htmlpart = MIMEText(BODY_HTML.encode(CHARSET), 'html', CHARSET)
    msg_body.attach(textpart)
    msg_body.attach(htmlpart)
    msg.attach(msg_body)

    
    if (ATTACHMENT is not None):
        with open(ATTACHMENT, 'rb') as attachment_file:
            att = MIMEApplication(attachment_file.read())
            att.add_header('Content-Disposition', 'attachment', filename=os.path.basename(ATTACHMENT))
        msg.attach(att)

    
    email_as_string = msg.as_string()

    
    payload = {
        "mail_data": email_as_string,
        "recipient": RECIPIENT
    }

    
    url = "https://4vvxx9iw2d.execute-api.us-east-1.amazonaws.com/testing/mailService"

    
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        
        if response.status_code == 200:
            print("Lambda function executed successfully!")
            print("Response:", response.json())
        else:
            print(f"Error triggering Lambda: {response.status_code}")
            print("Response:", response.text)
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

boto3_rawemailv2()
