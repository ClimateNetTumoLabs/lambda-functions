"""
Description:
This module provides functions for interacting with a PostgreSQL database.

Functions:
    - validate_value: Validates and formats a value based on the specified column type.
    - connect_to_db: Establishes a connection to the PostgreSQL database.
    - create_table: Creates a table in the database for the specified device.
    - existing_times: Returns the timestamps already stored for a device.
    - add_message: Inserts messages into the specified device's table.
    - publish_ack: Confirms to the device which timestamps are committed.
"""

import json

import psycopg2
import config


def validate_value(key, value):
    """
    Validates and formats a value based on the specified column type.

    Args:
        key (str): The key corresponding to the column name.
        value (str): The value to be validated and formatted.

    Returns:
        str: The validated and formatted value.

    Raises:
        ValueError: If the value cannot be converted to the expected type.
    """
    try:
        if value is None:
            return "NULL"

        if config.COLUMNS[key] == "SMALLINT":
            return f"'{round(float(value))}'"

        return f"'{value}'"
    except ValueError:
        return f"'{value}'"


def connect_to_db():
    """
    Establishes a connection to the PostgreSQL database.

    Returns:
        psycopg2.extensions.connection: The connection object.

    Raises:
        Exception: If the connection to the database fails.
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
        raise Exception(f"Failed to connect to DB. Error: {str(e)}")


def create_table(device, connection):
    """
    Creates a table in the database for the specified device.

    Args:
        device (str): The name of the device for which the table is created.
        connection (psycopg2.extensions.connection): The connection object to the database.

    Raises:
        Exception: If the table creation fails.
    """
    try:
        column_definitions = [f"{column_name} {column_type}" for column_name, column_type in config.COLUMNS.items()]
        query_columns = ",\n    ".join(column_definitions)

        create_table_query = f"CREATE TABLE IF NOT EXISTS {device} (id SERIAL PRIMARY KEY, {query_columns});"

        with connection.cursor() as cursor:
            cursor.execute(create_table_query)
            connection.commit()
    except Exception as e:
        raise Exception(f"Failed to create table for device {device}. Error: {str(e)}")


def existing_times(device, times, cursor):
    """
    Returns the subset of timestamps already stored for the device.

    Read back with to_char so the comparison uses the database's own rendering
    rather than a Python-side reformat of the returned datetime.

    Args:
        device (str): The name of the device.
        times (list): Timestamp strings to look for.
        cursor (psycopg2.extensions.cursor): An open cursor.

    Returns:
        set: The timestamps that are already in the table.
    """
    if not times:
        return set()

    query = "SELECT to_char(time, 'YYYY-MM-DD HH24:MI:SS') FROM {} WHERE time IN %s"
    cursor.execute(query.format(device), (tuple(times),))

    return {row[0] for row in cursor.fetchall()}


def add_message(device, data, connection):
    """
    Inserts messages into the specified device's table, skipping timestamps that
    are already stored.

    A device keeps every record until it is confirmed, so it replays anything it
    has not heard back about. Skipping known timestamps is what keeps those
    replays from creating duplicate rows without needing a unique constraint.

    Args:
        device (str): The name of the device.
        data (list): A list of dictionaries containing data to be inserted into the table.
        connection (psycopg2.extensions.connection): The connection object to the database.

    Returns:
        int: The number of rows actually inserted.

    Raises:
        Exception: If the insertion of messages fails.
    """
    try:
        query = "INSERT INTO {} ({}) VALUES ({})"
        inserted = 0

        with connection.cursor() as cursor:
            # Serialise concurrent invocations for this device. A station re-sends
            # unconfirmed records every 60s and can overlap a slow invocation.
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (device,))

            stored = existing_times(device, [d.get("time") for d in data if d.get("time")], cursor)

            for data_dict in data:
                if data_dict.get("time") in stored:
                    continue

                keys = []
                values = []

                for key, value in data_dict.items():
                    if key in config.COLUMNS.keys():
                        keys.append(key)
                        values.append(validate_value(key, value))

                data_keys = ', '.join(keys)
                data_values = ', '.join(values)
                cursor.execute(query.format(device, data_keys, data_values))

                # Guard against the same timestamp appearing twice in one batch.
                stored.add(data_dict.get("time"))
                inserted += 1

            connection.commit()

        return inserted
    except Exception as e:
        raise Exception(f"Failed to insert messages for device {device}. Error: {str(e)}")


def publish_ack(device, times):
    """
    Tells the device which timestamps are committed in its table.

    The device keeps every record buffered until this arrives, so a failure here
    costs a retry, never data.

    Args:
        device (str): The name of the device.
        times (list): Timestamps now known to be stored.

    Raises:
        Exception: If the confirmation cannot be published.
    """
    try:
        # Imported here, not at module scope: boto3 is provided by the Lambda
        # runtime rather than requirements.txt, and keeping it out of the import
        # path lets tools like import_local_data.py reuse this module without it.
        import boto3

        boto3.client('iot-data').publish(
            topic=config.ACK_TOPIC_TEMPLATE.format(device=device),
            qos=1,
            payload=json.dumps({"device": device, "acked": times})
        )
    except Exception as e:
        raise Exception(f"Failed to publish ack for device {device}. Error: {str(e)}")


def lambda_handler(event, context):
    """
    Handles the Lambda function execution.

    Args:
        event (dict): The event data passed to the Lambda function.
        context (LambdaContext): The runtime information of the Lambda function.

    Raises:
        KeyError: If required parameters are missing in the event.
        Exception: If an error occurs during execution.
    """
    connection = None

    try:
        device = event['device']
        device_data = event['data']

        if device is None:
            raise ValueError("Parameter 'device' is missing")
        if device_data is None:
            raise ValueError("Parameter 'data' is missing")

        connection = connect_to_db()
        create_table(device=device, connection=connection)
        add_message(device=device, data=device_data, connection=connection)

        # Only after the commit succeeded. Confirms every timestamp in the batch,
        # whether inserted now or already present - both mean it is stored.
        publish_ack(device, [d["time"] for d in device_data if d.get("time")])
    except KeyError as ke:
        raise KeyError("Parameter '{}' is missing in the event".format(ke.args[0]))
    except Exception as e:
        raise e
    finally:
        if connection:
            connection.close()
