import json
from datetime import datetime
from lambda_function import lambda_handler

def main():
    # Mock event to simulate API Gateway request
    #   ip = event['requestContext']['http']['sourceIp']
    event = {
        "queryStringParameters": {
            "device_id": "8",
              # Replace with a valid device ID
            # Uncomment these lines to test with specific start and end times
            # "start_time": "2025-01-06T00:00:00",
            # "end_time": "2025-01-07T00:00:00"
        },
        "requestContext":{
            "http":{
                "sourceIp":'212.34.238.10'
            }
        }
    }

    
    context = {}

    
    try:
        response = lambda_handler(event, context)
        print("Lambda Function Response:")
        print(json.dumps(response, indent=2))
    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    main()
