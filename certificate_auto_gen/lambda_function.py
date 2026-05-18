import io
import json
import base64
import zipfile
import urllib.request
import config
from botocore.exceptions import ClientError
from certificate import (
    create_keys_and_certificate,
    attach_certificate_to_thing,
    list_thing_principals,
    check_or_create_thing,
    attach_policy_to_thing,
    get_ca_certificate,
    delete_thing_certificate,
)
from response_handler import (
    build_response,
    build_error_response,
    build_simple_response,
    build_bad_request_response,
)

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

        http_method = event.get('httpMethod', '')
        delete = body.get('delete') if body else None
        thing_name = body.get('thingName') if body else None

        # ------------------------------------------------------------------
        # POST — delete or create
        # ------------------------------------------------------------------
        if http_method == "POST":
            # Delete flow
            if delete:
                if thing_name:
                    return delete_thing_certificate(thing_name)
                return build_bad_request_response("thingName is required for deletion.")

            # Create flow — thingName is required
            if not thing_name:
                return build_bad_request_response(
                    "thingName is required. Send {'thingName': 'UserDevice123456'}."
                )

            return _create_thing_and_certificate(thing_name)

        # ------------------------------------------------------------------
        # Any other method — unsupported
        # ------------------------------------------------------------------
        return build_bad_request_response(
            "Unsupported HTTP method. Use POST with a JSON body."
        )

    except ClientError as e:
        return build_error_response(e)
    except Exception as e:
        return build_error_response(str(e))


def _create_thing_and_certificate(new_thing_name):
    """Create an AWS IoT Thing, generate certificates, and return a ZIP."""

    # Extract the numeric suffix for the device ID (e.g. "UserDevice643781" → "643781")
    device_id = ''.join(filter(str.isdigit, new_thing_name)) or new_thing_name

    certificate_response = create_keys_and_certificate()

    # Retrieve Root CA certificate
    ca_certificate_pem = fetch_amazon_root_ca()

    # Specify the thing type and policy name
    thing_type = "WeatherStationDevices"

    # Check or create the thing
    check_or_create_thing(new_thing_name, thing_type)
    attached_principals = list_thing_principals(new_thing_name)

    if attached_principals:
        return build_error_response(
            f"Thing: {new_thing_name} already has an attached certificate."
        )

    attach_certificate_to_thing(new_thing_name, certificate_response['certificateArn'])

    environment_file = (
        f"DEVICE_ID={device_id}\n"
        f"MQTT_TOPIC={config.MQTT_TOPIC}\n"
        f"MQTT_BROKER_ENDPOINT={config.MQTT_ENDPOINT}\n\n"
        f"#Custom database names must include the .json extension, for example: local_data.json\n"
        f"LOCAL_DB="
    )

    # Create an in-memory ZIP file
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("certificates/certificate.pem.crt", certificate_response.get('certificatePem', ''))
        zip_file.writestr("certificates/private.pem.key", certificate_response.get('keyPair', {}).get('PrivateKey', ''))
        zip_file.writestr("certificates/public.pem.key", certificate_response.get('keyPair', {}).get('PublicKey', ''))
        zip_file.writestr("certificates/rootCA.pem", ca_certificate_pem)
        zip_file.writestr(".env", environment_file)

    # Encode ZIP as base64 for HTTP response
    zip_buffer.seek(0)
    zip_base64 = base64.b64encode(zip_buffer.read()).decode('utf-8')

    # Return the ZIP file for download
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/zip',
            'Content-Disposition': f'attachment; filename="{new_thing_name}_credentials.zip"',
            'id': new_thing_name
        },
        'body': zip_base64,
        'param': new_thing_name,
        'isBase64Encoded': True
    }
