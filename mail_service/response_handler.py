import json

def build_response(message, response):
    """Build a successful response."""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': message,
            'res': response,
        }, default=str)
    }

def build_simple_response(message, response):
    """Build a successful response."""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': message,
            'res': response,
        }, default=str)
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
            'message': 'Mail service failed',
            'error': str(error)
        })
    }