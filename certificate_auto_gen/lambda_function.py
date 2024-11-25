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
    delete_thing_certificate  # Make sure to import this function
)
from response_handler import build_response, build_error_response

def lambda_handler(event, context):
    try:
        # Create certificate and keys
        delete = event.get('delete')
        if(delete):
            print("ok")
            if(event.get('thingName')):
                return delete_thing_certificate(event.get('thingName'))
            return build_error_response("Thing name is empty!")
        certificate_response = create_keys_and_certificate()
        
        # Retrieve CA certificate using its ID
        ca_certificate_id = certificate_response['certificateArn']  # Extract CA cert ID
        # ca_certificate_response = get_ca_certificate(ca_certificate_id)  # Use the new function to get CA cert
        # ca_certificate_pem = ca_certificate_response['certificatePem']
        response = client.get_certificate_authority_certificate(
            CertificateAuthorityArn=ca_certificate_id
        )
        return response
        # List existing things to determine the next device name
        # existing_things = list_things()
        # thing_count = len(existing_things)
        
        # # Generate new thing name
        # new_thing_name = f"Device{thing_count + 1}"
        
        # # Specify the thing type and policy name
        # thing_type = "WeatherStationDevices"
        # policy_name = "WeatherStationDevicePolicy"  # Replace with your desired policy name
        
        # # Check or create the thing
        # check_or_create_thing(new_thing_name, thing_type)
        # attached_principals = list_thing_principals(new_thing_name)

        # if not attached_principals:
        #     attach_certificate_to_thing(new_thing_name, certificate_response['certificateArn'])
        #     attach_policy_to_thing(new_thing_name, policy_name)  # Attach the policy
        #     message = f"Certificate created and attached to Thing: {new_thing_name}"
        # else:
        #     return build_error_response(f"Thing: {new_thing_name} already has an attached certificate.")

        # # Create an in-memory ZIP file
        # zip_buffer = io.BytesIO()
        # with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        #     # Write certificate, keys, and device ID to files with specified names
        #     zip_file.writestr("certificate.pem.crt", certificate_response.get('certificatePem', ''))
        #     zip_file.writestr("private.pem.key", certificate_response.get('keyPair', {}).get('PrivateKey', ''))
        #     zip_file.writestr("public.pem.key", certificate_response.get('keyPair', {}).get('PublicKey', ''))
        #     zip_file.writestr("rootCA.pem", ca_certificate_pem)  # Use the CA certificate PEM
        #     zip_file.writestr("deviceID.txt", new_thing_name)

        # # Encode ZIP as base64 for HTTP response
        # zip_buffer.seek(0)
        # zip_base64 = base64.b64encode(zip_buffer.read()).decode('utf-8')

        # Return the ZIP file for download
        # return {
        #     'statusCode': 200,
        #     'headers': {
        #         'Content-Type': 'application/zip',
        #         'Content-Disposition': 'attachment; filename="certificates.zip"'
        #     },
        #     'body': zip_base64,
        #     'isBase64Encoded': True
        # }

    except ClientError as e:
        return build_error_response(e)