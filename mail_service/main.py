import json
from lambda_function import lambda_handler

def main():
    recipient = "rnobaboomian@gmail.com"
    try:
        with open("./html/notify.html", "r") as html_file:
            notify_html = html_file.read().replace("{{recipient_email}}", recipient)

  
       
        with open("./html/decline.html", "r") as html_file:
            decline_html = html_file.read().replace("{{recipient_email}}", recipient)
           
        with open("./html/termination.html", "r") as html_file:
            termination_html = html_file.read().replace("{{recipient_email}}", recipient)
            
        with open("./html/approval.html", "r") as html_file:
            approve_html = html_file.read().replace("{{recipient_email}}", recipient)
    except FileNotFoundError:
        return "file not found"
        
    notify = {
        "recipient": recipient,  
        'subject':"Thanks for Your Request - ClimateNet DIY Kit",
        'body_html':notify_html
    }
    approval = {
        "recipient": recipient,  
        'subject':"Thanks for Your Request - ClimateNet DIY Kit",
        'body_html':approve_html
    }
    decline = {
        "recipient": recipient,  
        'subject':"Thanks for Your Request - ClimateNet DIY Kit",
        'body_html':decline_html
    }
    termination = {
        "recipient": recipient,  
        'subject':"Thanks for Your Request - ClimateNet DIY Kit",
        'body_html':termination_html
    }
    test_event = {
        "recipient": recipient,  
        "subject": "Welcome to ClimateNet!",  
        "body_text": "Welcome to ClimateNet! We're thrilled to have you join us.",
            
    }
    test_event2 = {
        "recipient": recipient,  
        "subject": "Welcome to ClimateNet!",  
        "body_text": "Welcome to ClimateNet! We're thrilled to have you join us.",
            
    }

    
    print("Calling Lambda function...")
    response = lambda_handler(notify, None)
    response2 = lambda_handler(approval, None)
    response2 = lambda_handler(decline, None)
    response2 = lambda_handler(termination, None)

    
    print("\nLambda Response:")
    print(json.dumps(response, indent=4))
    print("\nLambda Response:")
    print(json.dumps(response2, indent=4))

if __name__ == "__main__":
    main()
