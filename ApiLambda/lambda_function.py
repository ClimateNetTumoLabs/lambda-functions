import psycopg2
import json
from config import host, user, password, db_name
from datetime import datetime, timedelta


GET_RAW_PATH = "/getData"


def connect_to_db():
    try:
        connection = psycopg2.connect(
            host=host,
            user=user,
            password=password,
            database=db_name
        )

        cursor = connection.cursor()

        return connection, cursor

    except Exception as ex:
        print("Error", ex)
        return False


def get_data_for_period(deviceID, cursor, start_time, end_time):
    query = f"SELECT * FROM {deviceID} WHERE time BETWEEN %s AND %s"
    cursor.execute(query, (start_time, end_time))

    data = cursor.fetchall()

    return data


def lambda_handler(event, context):
    rawPath = event['rawPath']
    query_params = event.get('queryStringParameters', {})

    device_id = query_params.get('device_id')
    if not device_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Missing device_id parameter'})
        }

    if rawPath == '/getData':
        
        start_time = query_params.get('start_time')
        end_time = query_params.get('end_time')

        if (start_time and not end_time) or (end_time and not start_time):
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Both start_time and end_time must be provided'})
            }

        conn, cursor = connect_to_db()
        
        if start_time and end_time:
            end_time = datetime.strptime(end_time, '%Y-%m-%d')
            end_time = (end_time + timedelta(days=1)).strftime('%Y-%m-%d')
            data = get_data_for_period(f"device{device_id}", cursor, start_time, end_time)
        else:
            today = datetime.utcnow().strftime('%Y-%m-%d')
            end_of_day = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')

            data = get_data_for_period(f"device{device_id}", cursor, today, end_of_day)

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

