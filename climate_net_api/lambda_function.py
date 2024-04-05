from datetime import datetime, timedelta
import json
import psycopg2

import config


def connect_to_db():
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
    if not start_time or not end_time:
        now = datetime.utcnow()
        start_time = now.strftime('%Y-%m-%d')
        end_time = (now + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        end_time = (datetime.strptime(end_time, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    query = f"SELECT * FROM {device_id} WHERE time BETWEEN %s AND %s"
    cursor.execute(query, (start_time, end_time))
    data = cursor.fetchall()

    return data


def lambda_handler(event, context):
    raw_path = event['rawPath']
    query_params = event.get('queryStringParameters', {})

    device_id = query_params.get('device_id')
    if not device_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing device_id parameter'})
        }

    if raw_path == '/getData':
        
        start_time = query_params.get('start_time')
        end_time = query_params.get('end_time')

        if not end_time or not start_time:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Both start_time and end_time must be provided'})
            }

        conn, cursor = connect_to_db()
        if not conn:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to connect to the database'})
            }

        if start_time and end_time:
            data = get_data_by_date(f"device{device_id}", cursor, start_time, end_time)
        else:
            data = get_data_by_date(f"device{device_id}", cursor)

        cursor.close()
        conn.close()

        return {
            'statusCode': 200,
            'body': json.dumps({'data': data}, default=str)
        }

    else:
        return {
            'statusCode': 404,
            'body': json.dumps({'error': 'Not Found'})
        }
