import json
import base64
from lambda_function import lambda_handler

# def save_zip_file(base64_content, output_file):
#     """Save the Base64 encoded ZIP content to a file."""
#     try:
#         with open(output_file, "wb") as f:
#             f.write(base64.b64decode(base64_content))
#         print(f"ZIP file saved as {output_file}")
#     except Exception as e:
#         print(f"Error saving ZIP file: {e}")

if __name__ == "__main__":
#     # Simulate an API Gateway POST event
#     test_event = {
#         "httpMethod": "GET",
#         # "body": json.dumps({
#         #     "thingName": "TestDevice",
#         #     "delete": False
#         # })
#         "thingName": "TestDevice",

#     }

#     # Call the lambda handler function
#     response = lambda_handler(test_event, None)
#     # print(response['id'])
#     # Check if the response contains a ZIP file
#     if response.get("statusCode") == 200 and response.get("isBase64Encoded"):
#         zip_content_base64 = response["body"]
#         output_file = f"{response['id']}certificates.zip"
#         save_zip_file(zip_content_base64, output_file)
#     else:
#         print(f"Lambda function failed with response: {response}")
    id = 10
    endpoint = "/api"
    """ DEVICE_ID=

    # LOCAL DB CONFIGS
    LOCAL_DB_DB_NAME=data.db

    # MQTT BROKER CONFIGS
    MQTT_BROKER_ENDPOINT=
    """

    enviroment_file = f"DEVICE_ID={id}\nLOCAL_DB_DB_NAME=data.db\nMQTT_BROKER_ENDPOINT={endpoint}"
    print(enviroment_file)