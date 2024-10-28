import json
from botocore.exceptions import ClientError
from certificate import create_keys_and_certificate, attach_certificate_to_thing, list_thing_principals, check_or_create_thing,list_things
from response_handler import build_response, build_error_response

def lambda_handler(event, context):
    try:
        certificate_response = create_keys_and_certificate()

        # List existing things
        existing_things = list_things()  # Assuming this function retrieves a list of all things
        thing_count = len(existing_things)
        
        # Generate new thing name
        new_thing_name = f"DeviceTest{thing_count + 1}"

        # Check if a specific thing name was provided
        thing_name = event.get('thingName', new_thing_name)
        
        check_or_create_thing(new_thing_name)
        attached_principals = list_thing_principals(new_thing_name)

        if not attached_principals:
            attach_certificate_to_thing(new_thing_name, certificate_response['certificateArn'])
            message = f"Certificate created and attached to Thing: {new_thing_name}"
        else:
            return build_error_response(f"Thing: {new_thing_name} already has an attached certificate.")

        return build_response(message, certificate_response)

    except ClientError as e:
        return build_error_response(e)
