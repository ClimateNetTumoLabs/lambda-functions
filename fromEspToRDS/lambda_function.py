"""
Description:
Complete Lambda function with proper timestamp handling
"""

import json
import psycopg2
import traceback
import config  # Import your existing config file


def validate_value(key, value):
    """Validates and formats a value based on the specified column type."""
    try:
        # Handle NULL values
        if value is None or str(value).lower() == "nan" or value == "":
            return "NULL"

        column_type = config.COLUMNS.get(key, "VARCHAR(255)")

        # SMALLINT - round to integer
        if column_type == "SMALLINT":
            return str(int(round(float(value))))

        # REAL/FLOAT - return as number (no quotes)
        if column_type == "REAL" or column_type == "FLOAT":
            return str(round(float(value), 2))

        # INTEGER
        if column_type == "INTEGER" or column_type == "INT":
            return str(int(value))

        # VARCHAR/TEXT - add single quotes and escape any existing quotes
        if "VARCHAR" in column_type or "TEXT" in column_type or "CHAR" in column_type:
            # Escape single quotes by doubling them
            escaped_value = str(value).replace("'", "''")
            return f"'{escaped_value}'"

        # Default: treat as string
        escaped_value = str(value).replace("'", "''")
        return f"'{escaped_value}'"

    except (ValueError, TypeError) as e:
        print(f"Validation error for {key}={value}: {str(e)}")
        return "NULL"


def connect_to_db():
    """Establishes a connection to the PostgreSQL database."""
    try:
        connection = psycopg2.connect(
            host=config.HOST,
            user=config.USER,
            password=config.PASSWORD,
            database=config.DB_NAME,
            connect_timeout=5
        )
        return connection
    except Exception as e:
        raise Exception(f"Failed to connect to DB. Error: {str(e)}")


def create_table(device, connection):
    """Creates a table in the database for the specified device."""
    try:
        column_definitions = [f"{column_name} {column_type}"
                            for column_name, column_type in config.COLUMNS.items()]
        query_columns = ",\n    ".join(column_definitions)

        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {device} (
            id SERIAL PRIMARY KEY, 
            {query_columns}
        );
        """

        with connection.cursor() as cursor:
            cursor.execute(create_table_query)
            connection.commit()

        print(f"Table {device} ready")
    except Exception as e:
        raise Exception(f"Failed to create table for device {device}. Error: {str(e)}")


def add_message(device, data, connection):
    """Inserts messages into the specified device's table."""
    try:
        with connection.cursor() as cursor:
            for data_dict in data:
                keys = []
                values = []

                for key, value in data_dict.items():
                    if key in config.COLUMNS.keys():
                        keys.append(key)
                        values.append(validate_value(key, value))

                if not keys:
                    print("No valid columns found in data")
                    continue

                data_keys = ', '.join(keys)
                data_values = ', '.join(values)

                query = f"INSERT INTO {device} ({data_keys}) VALUES ({data_values})"
                print(f"Executing: {query}")
                cursor.execute(query)

            connection.commit()
            print(f"Successfully inserted {len(data)} record(s)")

    except Exception as e:
        connection.rollback()
        raise Exception(f"Failed to insert messages for device {device}. Error: {str(e)}")


def lambda_handler(event, context):
    """
    Handles the Lambda function execution.
    """
    connection = None

    try:
        # Log the incoming event
        print("Received event:")
        print(json.dumps(event, indent=2))

        # Parse body if it's from API Gateway
        if 'body' in event:
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        else:
            body = event

        # Extract device and data
        device = body.get('device')
        device_data = body.get('data')

        # Validation
        if not device:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Parameter "device" is missing'})
            }

        if not device_data:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Parameter "data" is missing'})
            }

        if not isinstance(device_data, list):
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'error': 'Parameter "data" must be an array'})
            }

        print(f"Processing device: {device}")
        print(f"Data records: {len(device_data)}")

        # Database operations
        connection = connect_to_db()
        create_table(device=device, connection=connection)
        add_message(device=device, data=device_data, connection=connection)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Data inserted successfully',
                'device': device,
                'records': len(device_data)
            })
        }

    except Exception as e:
        error_msg = str(e)
        stack_trace = traceback.format_exc()

        print(f"ERROR: {error_msg}")
        print(f"Stack trace:\n{stack_trace}")

        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'message': error_msg
            })
        }

    finally:
        if connection:
            connection.close()
            print("Database connection closed")