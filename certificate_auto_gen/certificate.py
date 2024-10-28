import boto3
from botocore.exceptions import ClientError

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
        
def check_or_create_thing(thing_name):
    try:
        # Step 1: Try to describe the Thing to check if it exists
        response = iot_client.describe_thing(thingName=thing_name)
        print(f"Thing '{thing_name}' exists: {response}")
        return response

    except ClientError as e:
        # Step 2: If the Thing does not exist, create it
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"Thing '{thing_name}' not found, creating a new one.")
            create_response = iot_client.create_thing(thingName=thing_name)
            print(f"Thing '{thing_name}' created: {create_response}")
            return create_response
        else:
            # If another error occurred, raise it
            raise e


import boto3

def list_things():
    things = []
    next_token = None

    while True:
        if next_token:
            response = iot_client.list_things(nextToken=next_token)
        else:
            response = iot_client.list_things()

        things.extend(response['things'])
        next_token = response.get('nextToken')
        
        if not next_token:
            break  # Exit the loop if there's no more data

    return things
