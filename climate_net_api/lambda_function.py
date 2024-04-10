import psycopg2

import json
from datetime import datetime, timedelta

import config


def connect_to_db():
    """
    Establish a connection to the PostgreSQL database using the parameters specified in the config file.

    Returns:
        tuple: A tuple containing the connection object and cursor object.
            - connection (psycopg2.extensions.connection): The connection to the PostgreSQL database.
            - cursor (psycopg2.extensions.cursor): The cursor object for executing queries on the database.

        If the connection fails, returns (None, None).
    """
    try:
        connection = psycopg2.connect(
            host=config.HOST,
            user=config.USER,
            password=config.PASSWORD,
            database=config.DB_NAME
        )
        cursor = connection.cursor()
        return connection, cursor

    except psycopg2.OperationalError:
        return None, None


def get_data_by_date(device_id, cursor, start_time=None, end_time=None):
    """
    Retrieve data from the database for a specified device within a given time range.

    Args:
        device_id (str): The ID of the device for which data is to be retrieved.
        cursor (psycopg2.extensions.cursor): The cursor object for executing queries on the database.
        start_time (str, optional): The start of the time range in the format 'YYYY-MM-DD'. Defaults to None.
        end_time (str, optional): The end of the time range in the format 'YYYY-MM-DD'. Defaults to None.

    Returns:
        list: A list of tuples containing the retrieved data rows from the database.

    Note:
        If start_time or end_time is not provided, the function defaults to retrieving data for the current UTC date.
        The end_time is exclusive, meaning data up to but not including the end_time will be retrieved.
    """
    if not start_time or not end_time:
        now = datetime.utcnow()
        start_time = now.strftime('%Y-%m-%d')
        end_time = (now + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        end_time = (datetime.strptime(end_time, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    query = f'SELECT * FROM {device_id} WHERE time BETWEEN %s AND %s'
    cursor.execute(query, (start_time, end_time))
    data = cursor.fetchall()

    return data


def lambda_handler(event, context):
    """
    Lambda function handler for retrieving data from the database based on query parameters.

    Args:
        event (dict): The event data passed to the lambda function.
        context (LambdaContext): The runtime information of the lambda function.

    Returns:
        dict: A dictionary containing the HTTP response with status code and body.

    Note:
        This function expects the event to contain queryStringParameters, which should include:
        - 'device_id': The ID of the device for which data is to be retrieved (required).
        - 'start_time': The start of the time range in the format 'YYYY-MM-DD' (optional).
        - 'end_time': The end of the time range in the format 'YYYY-MM-DD' (optional).

        If 'start_time' and 'end_time' are provided, data will be retrieved for the specified time range.
        If 'start_time' and 'end_time' are not provided, data for the current day will be retrieved.
    """
    query_params = event.get('queryStringParameters', {})

    device_id = query_params.get('device_id')
    if not device_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing device_id parameter'})
        }

    start_time = query_params.get('start_time', '')
    end_time = query_params.get('end_time', '')

    conn, cursor = connect_to_db()
    if not conn:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to connect to the database'})
        }

    if start_time and end_time:
        data = get_data_by_date(f'device{device_id}', cursor, start_time, end_time)

    elif not start_time and not end_time:
        data = get_data_by_date(f'device{device_id}', cursor)

    else:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Both start_time and end_time must be provided'})
        }

    cursor.close()
    conn.close()

    return {
        'statusCode': 200,
        'body': json.dumps({'data': data}, default=str)
    }
