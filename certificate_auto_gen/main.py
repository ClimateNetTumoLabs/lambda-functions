from lambda_function import lambda_handler
import json

# Simulated event data (make sure it matches your Lambda expectations)
event = {
    "httpMethod": "POST",  # Mimic an HTTP POST request
    "body": json.dumps({
        "thingName": "TestUfar",
        "delete": True
    })
}
event2 = {
    "httpMethod": "GET",  # Mimic an HTTP POST request
    
        "thingName": "TestUfar",
        "delete": False
}

# Simulated context (you can leave it empty for testing)
context = {}

# Invoke the Lambda function
response = lambda_handler(event, context)

# Print the Lambda response
print("Lambda Response:")
print(response)
