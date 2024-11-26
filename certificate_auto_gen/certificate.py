import boto3
from botocore.exceptions import ClientError,BotoCoreError
from response_handler import build_error_response ,build_response,build_simple_response


boto3.setup_default_session(
    aws_access_key_id='',
    aws_secret_access_key='',
    region_name=''
)

# Now, you can create any boto3 client or resource
iot_client = boto3.client('iot')


def create_keys_and_certificate():
    """Create IoT keys and certificate."""
    try:
        response = iot_client.create_keys_and_certificate(setAsActive=True)
        print(f"Certificate created: {response}")
        
        return response
    except ClientError as e:
        print(f"Error creating certificate: {e}")
        raise e

def attach_certificate_to_thing(thing_name, certificate_arn):
    """Attach the certificate to the IoT Thing."""
    try:
        iot_client.attach_thing_principal(
            thingName=thing_name,
            principal=certificate_arn
        )
        print(f"Certificate attached to Thing: {thing_name}")
        attach_policy_to_thing(certificate_arn,"WeatherStationDevicePolicy")
    except ClientError as e:
        print(f"Error attaching certificate to thing: {e}")
        raise e

def list_thing_principals(thing_name):
    """Check if the Thing already has an attached certificate."""
    try:
        response = iot_client.list_thing_principals(thingName=thing_name)
        print(f"Thing principals: {response['principals']}")
        return response['principals']
    except ClientError as e:
        print(f"Error listing thing principals: {e}")
        raise e
        
def check_or_create_thing(thing_name, thing_type=None):
    """Check if a thing exists, create it if it does not, and optionally set its type."""
    try:
        # Try to describe the Thing to check if it exists
        response = iot_client.describe_thing(thingName=thing_name)
        print(f"Thing '{thing_name}' exists: {response}")
        return response

    except ClientError as e:
        # If the Thing does not exist, create it
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"Thing '{thing_name}' not found, creating a new one.")
            create_params = {
                'thingName': thing_name
            }
            if thing_type:
                create_params['thingTypeName'] = thing_type
            
            create_response = iot_client.create_thing(**create_params)
            print(f"Thing '{thing_name}' created: {create_response}")
            return create_response
        else:
            # If another error occurred, raise it
            raise e

def attach_policy_to_thing(arn, policy_name):
    """Attach an IoT policy to the Thing."""
    try:
        iot_client.attach_principal_policy(
            policyName=policy_name,
            principal=arn  # Assuming target can accept a thing name; if not, you may need to attach it to the certificate instead
        )
        print(f"Policy '{policy_name}' attached to Thing: {arn}")
    except ClientError as e:
        print(f"Error attaching policy to thing: {e}")
        raise e

def list_things():
    things = []
    next_token = None

    while True:
        if next_token:
            response = iot_client.list_things(nextToken=next_token)
        else:
            response = iot_client.list_things()

        for thing in response['things']:
            if "Device" in thing['thingName']:  # Check if "Device" is part of the name
                things.append(thing)

        next_token = response.get('nextToken')
        
        if not next_token:
            break  # Exit the loop if there's no more data

    return things
    
def get_ca_certificate(certificate_id):
    response = iot_client.get_certificate(certificate_id)
    return response
    
def delete_thing_certificate(thingname):
    try:
        
        response = iot_client.list_thing_principals(thingName=thingname)
        principals = response.get('principals', [])
        
        if not principals:
            print(f"No certificates attached to Thing: {thingname}")
        else:
            for principal in principals:
                
                certificate_id = principal.split('/')[-1]
                print(f"Found certificate ID: {certificate_id} for Thing: {thingname}")

                iot_client.detach_thing_principal(
                    thingName=thingname,
                    principal=principal
                )
                print(f"Detached certificate ID: {certificate_id} from Thing: {thingname}")
                iot_client.update_certificate(
                    certificateId=certificate_id,
                    newStatus='INACTIVE'
                )
                print(f"Set certificate ID: {certificate_id} to INACTIVE")                
                iot_client.delete_certificate(
                    certificateId=certificate_id,
                    forceDelete=True  
                )
                print(f"Deleted certificate ID: {certificate_id}")
        iot_client.delete_thing(thingName=thingname)
        print(f"Deleted Thing: {thingname}")
        return build_simple_response(f"Deleted Thing: {thingname}",thingname)

    except (BotoCoreError, ClientError) as error:
        print(f"An error occurred: {error}")
        return build_error_response(error)