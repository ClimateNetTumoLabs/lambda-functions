import json

def build_response(message, response):
    """Build a successful response."""
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': message,
            'res': response,
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

def build_error_response(error):
    """Build an error response."""
    return {
        'statusCode': 500,
        'body': json.dumps({
            'message': 'mail service  failed',
            'error': str(error)
        })
    }