import io
import json
import base64
import zipfile
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
    
    # Make sure to import this function
)
from response_handler import build_response, build_error_response ,build_simple_response

def lambda_handler(event, context):
    try:
        # Create certificate and keys
        # print(event)
        # return {'msg':"hello"}
        # return {
        #     'statusCode': 200,
        #     'body': json.dumps({
        #         'message': event.get('body'),
        #         'status': "ok"
        #     })
        #         }
        body = event.get('body')
        
        # Parse JSON if body exists and is not already a dictionary
        if body:
            if isinstance(body, str):
                body = json.loads(body)
        delete = body.get('delete') if body else None
        thing_name = body.get('thingName') if body else None
        
        # return build_simple_response("ok",delete)
        if(event.get('httpMethod') == "POST"):
            if(delete):
                print("ok")
                if(thing_name):
                    return delete_thing_certificate(thing_name)
                    # return build_simple_response("ok",thing_name)
            return build_error_response("Thing name is empty!")
            
        certificate_response = create_keys_and_certificate()
        
        # Retrieve CA certificate using its ID
        ca_certificate_id = certificate_response['certificateArn'].split('/')[-1]  # Extract CA cert ID
        ca_certificate_response = certificate_response # Use the new function to get CA cert
        ca_certificate_pem = certificate_response['certificatePem']

        # List existing things to determine the next device name
        existing_things = list_things()
        thing_count = len(existing_things)
        
        # Generate new thing name
        new_thing_name = f"Device{thing_count + 1}"
        
        # Specify the thing type and policy name
        thing_type = "WeatherStationDevices"
        policy_name = "WeatherStationDevicePolicy"  # Replace with your desired policy name
        
        # Check or create the thing
        check_or_create_thing(new_thing_name, thing_type)
        attached_principals = list_thing_principals(new_thing_name)

        if not attached_principals:
            attach_certificate_to_thing(new_thing_name, certificate_response['certificateArn'])
            # attach_policy_to_thing(new_thing_name, policy_name)  # Attach the policy
            message = f"Certificate created and attached to Thing: {new_thing_name}"
        else:
            return build_error_response(f"Thing: {new_thing_name} already has an attached certificate.")

        # Create an in-memory ZIP file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Write certificate, keys, and device ID to files with specified names
            zip_file.writestr("certificate.pem.crt", certificate_response.get('certificatePem', ''))
            zip_file.writestr("private.pem.key", certificate_response.get('keyPair', {}).get('PrivateKey', ''))
            zip_file.writestr("public.pem.key", certificate_response.get('keyPair', {}).get('PublicKey', ''))
            zip_file.writestr("rootCA.pem", ca_certificate_pem)  # Use the CA certificate PEM
            zip_file.writestr("deviceID.txt", new_thing_name)

        # Encode ZIP as base64 for HTTP response
        zip_buffer.seek(0)
        zip_base64 = base64.b64encode(zip_buffer.read()).decode('utf-8')

        # Return the ZIP file for download
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/zip',
                'Content-Disposition': 'attachment; filename="certificates.zip"'
            },
            'body': zip_base64,
            'isBase64Encoded': True
        }

    except ClientError as e:
        return build_error_response(e)
