import io
import json
import base64
import zipfile
import urllib.request # Add the requests library
from botocore.exceptions import ClientError
from certificate import (
    create_keys_and_certificate,
    attach_certificate_to_thing,
    list_thing_principals,
    check_or_create_thing,
    list_things,
    attach_policy_to_thing,
    get_ca_certificate,
    delete_thing_certificate,
)
from response_handler import build_response, build_error_response, build_simple_response

def fetch_amazon_root_ca():
    """
    Fetch the AmazonRootCA1.pem file using urllib.
    """
    url = "https://www.amazontrust.com/repository/AmazonRootCA1.pem"
    try:
        with urllib.request.urlopen(url) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch Amazon Root CA: {e}")

def lambda_handler(event, context):
    try:
        body = event.get('body')

        # Parse JSON if body exists and is not already a dictionary
        if body:
            if isinstance(body, str):
                body = json.loads(body)

        delete = body.get('delete') if body else None
        thing_name = body.get('thingName') if body else None

        if event.get('httpMethod') == "POST":
            if delete:
                if thing_name:
                    return delete_thing_certificate(thing_name)
                return build_error_response("Thing name is empty!")

        certificate_response = create_keys_and_certificate()

        # Retrieve CA certificate
        
        root_ca_response = fetch_amazon_root_ca()

        # if root_ca_response.status_code == 200:
        ca_certificate_pem = root_ca_response
        # else:
            # return build_error_response(f"Failed to download Root CA. HTTP Status Code: {root_ca_response.status_code}")

        # List existing things to determine the next device name
        existing_things = list_things()
        thing_count = len(existing_things)

        # Generate new thing name
        new_thing_name = f"Device{thing_count + 1}"

        # Specify the thing type and policy name
        thing_type = "WeatherStationDevices"
        policy_name = "WeatherStationDevicePolicy"

        # Check or create the thing
        check_or_create_thing(new_thing_name, thing_type)
        attached_principals = list_thing_principals(new_thing_name)

        if not attached_principals:
            attach_certificate_to_thing(new_thing_name, certificate_response['certificateArn'])
        else:
            return build_error_response(f"Thing: {new_thing_name} already has an attached certificate.")

        # Create an in-memory ZIP file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Write certificate, keys, and device ID to files with specified names
            zip_file.writestr("certificate.pem.crt", certificate_response.get('certificatePem', ''))
            zip_file.writestr("private.pem.key", certificate_response.get('keyPair', {}).get('PrivateKey', ''))
            zip_file.writestr("public.pem.key", certificate_response.get('keyPair', {}).get('PublicKey', ''))
            zip_file.writestr("rootCA.pem", ca_certificate_pem)  # Use the Root CA certificate
            zip_file.writestr("deviceID.txt", new_thing_name)

        # Encode ZIP as base64 for HTTP response
        zip_buffer.seek(0)
        zip_base64 = base64.b64encode(zip_buffer.read()).decode('utf-8')

        # Return the ZIP file for download
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Content-Disposition': 'attachment; filename="certificates.zip"'
            },
            'body': json.dumps({
                'id': new_thing_name,
                'zipFile': zip_base64
            }),
            'isBase64Encoded': True
        }

    except ClientError as e:
        return build_error_response(e)
    except Exception as e:
        return build_error_response(str(e))
