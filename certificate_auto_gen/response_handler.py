import json

def build_response(message, response):
    """Build a successful response."""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': message,
            'certificateArn': response['certificateArn'],
            'certificateId': response['certificateId'],
            'certificatePem': response['certificatePem'],
            'keyPair': {
                'PrivateKey': response['keyPair']['PrivateKey'],
                'PublicKey': response['keyPair']['PublicKey'],
            },
        })
    }
    
    
def build_simple_response(message, response):
    """Build a successful response."""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': message,
            'res':response
        })
    }

def build_bad_request_response(message):
    """Build a 400 bad-request response."""
    return {
        'statusCode': 400,
        'body': json.dumps({
            'message': message,
        })
    }


def build_error_response(error):
    """Build an error response."""
    return {
        'statusCode': 500,
        'body': json.dumps({
            'message': 'Certificate generation or attachment failed',
            'error': str(error)
        })
    }
