"""
Description:
This module provides functions for interacting with a PostgreSQL database and handling HTTP requests in an AWS Lambda function.

Functions:
    - connect_to_db: Establishes a connection to the PostgreSQL database.
    - get_data_by_date: Retrieves data from the database for a specific device within a given time range.
    - validate_params: Validates query parameters passed to the Lambda function.
    - lambda_handler: Main entry point for the AWS Lambda function.

Dependencies:
    - psycopg2: PostgreSQL adapter for Python.
    - json: JSON serialization and deserialization.
    - datetime: Date and time manipulation.
    - timedelta: Time duration calculation.
    - config: Module containing database connection configuration.
"""

import psycopg2
import json
from datetime import datetime, timedelta
import config
import urllib.request
import urllib.request
import pytz


def get_timezone(ip: str) -> str:
    """
    Get the current time in the timezone of the given IP address.

    Args:
        ip (str): The IP address to lookup.

    Returns:
        str: The current time in the format 'YYYY-MM-DD HH:MM:SS' if found, otherwise None.
    """
    url = f"http://ipinfo.io/{ip}/json"
    try:

        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())
        
        timezone = data.get('timezone')
        if not timezone:
            return None
        
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz)
        return current_time
    except Exception:
        return None

def connect_to_db():
    """
    Establishes a connection to the PostgreSQL database.

    Returns:
        psycopg2.extensions.connection: A connection object to the database.

    Raises:
        RuntimeError: If connection to the database fails.
    """
    try:
        connection = psycopg2.connect(
            host=config.HOST,
            user=config.USER,
            password=config.PASSWORD,
            database=config.DB_NAME
        )
        return connection
    except Exception as e:
        raise RuntimeError("Failed to connect to the database") from e


def get_data_by_date(device_id, connection, start_time=None, end_time=None , ip = None):
    """
    Retrieves data from the database for a specific device within a given time range.

    Args:
        device_id (int): The ID of the device.
        connection (psycopg2.extensions.connection): The database connection object.
        start_time (str, optional): The start time of the data range in 'YYYY-MM-DD' format. Defaults to None.
        end_time (str, optional): The end time of the data range in 'YYYY-MM-DD' format. Defaults to None.

    Returns:
        list: A list of tuples containing the fetched data.

    Raises:
        RuntimeError: If fetching data from the database fails.
    """
    try:
        if not start_time or not end_time:
            now = get_timezone(ip=ip)
            if now is None:
                now = datetime.utcnow()
            start_time = (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            end_time = now.strftime('%Y-%m-%d %H:%M:%S')
        else:
            end_time = (datetime.strptime(end_time, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

        with connection.cursor() as cursor:
            query = f'SELECT * FROM {device_id} WHERE time BETWEEN %s AND %s'
            cursor.execute(query, (start_time, end_time))
            data = cursor.fetchall()

        return data

    except Exception as e:
        print(e)
        raise RuntimeError(f"Failed to fetch data for device {device_id}") from e


def validate_params(query_params):
    """
    Validates query parameters passed to the Lambda function.

    Args:
        query_params (dict): A dictionary containing the query parameters.

    Returns:
        dict: A dictionary containing the validated parameters or an error response.

    Raises:
        ValueError: If device_id is not an integer.
        RuntimeError: If start_time and end_time are provided but have invalid format, or if both are missing.
    """
    device_id = query_params.get('device_id')
    if not device_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing device_id parameter'})
        }

    if not (isinstance(device_id, int) or device_id.isdigit()):
        return {
            'statusCode': 400,
            'body': json.dumps(
                {'error': 'Invalid format for device_id. It must be an integer.'}
            )
        }

    start_time = query_params.get('start_time')
    end_time = query_params.get('end_time')

    if start_time and end_time:
        try:
            datetime.strptime(start_time, '%Y-%m-%d')
            datetime.strptime(end_time, '%Y-%m-%d')
        except ValueError:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid date format. It must be YYYY-MM-DD.'})
            }

        return {'device': f'device{device_id}', 'start_time': start_time, 'end_time': end_time}
    elif not start_time and not end_time:
        return {'device': f'device{device_id}'}
    else:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Both start_time and end_time must be provided'})
        }


def lambda_handler(event, context):
    """
    Main entry point for the AWS Lambda function.

    Args:
        event (dict): The event data passed to the Lambda function.
        context (LambdaContext): The runtime information provided by AWS Lambda.

    Returns:
        dict: A dictionary containing the HTTP response.

    Raises:
        RuntimeError: If an error occurs during the execution of the function.
    """
    connection = None

    try:
        query_params = event.get('queryStringParameters', {})
        ip = event['requestContext']['http']['sourceIp']
        validation_result = validate_params(query_params)

        if 'statusCode' in validation_result:
            return validation_result

        device = validation_result['device']
        start_time = validation_result.get('start_time')
        end_time = validation_result.get('end_time')

        connection = connect_to_db()

        if start_time and end_time:
            data = get_data_by_date(device, connection, start_time, end_time)
        else:
            data = get_data_by_date(device, connection,ip=ip)

        return {
            'statusCode': 200,
            'body': json.dumps({'keys' : ["id","timestamp","uv","lux","temprature","pressure" ,"humidity" , "pm1" ,"pm2_5","pm10","speed" ,"rain"],'data': data}, default=str)
        }
    except Exception as e:
        print(e)
        raise RuntimeError("Server error occurred while fetching data from the database.") from e
    finally:
        if connection:
            connection.close()
