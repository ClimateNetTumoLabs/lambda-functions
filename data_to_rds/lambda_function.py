"""
Description:
This module provides functions for interacting with a PostgreSQL database.

Functions:
    - validate_value: Validates and formats a value based on the specified column type.
    - connect_to_db: Establishes a connection to the PostgreSQL database.
    - create_table: Creates a table in the database for the specified device.
    - add_message: Inserts messages into the specified device's table.
"""

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


def add_message(device, data, connection):
    """
    Inserts messages into the specified device's table.

    Args:
        device (str): The name of the device.
        data (list): A list of dictionaries containing data to be inserted into the table.
        connection (psycopg2.extensions.connection): The connection object to the database.

    Raises:
        Exception: If the insertion of messages fails.
    """
    try:
        query = "INSERT INTO {} ({}) VALUES ({})"

        with connection.cursor() as cursor:
            for data_dict in data:
                keys = []
                values = []

                for key, value in data_dict.items():
                    if key in config.COLUMNS.keys():
                        keys.append(key)
                        values.append(validate_value(key, value))

                data_keys = ', '.join(keys)
                data_values = ', '.join(values)
                cursor.execute(query.format(device, data_keys, data_values))

            connection.commit()
    except Exception as e:
        raise Exception(f"Failed to insert messages for device {device}. Error: {str(e)}")


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
    except KeyError as ke:
        raise KeyError("Parameter '{}' is missing in the event".format(ke.args[0]))
    except Exception as e:
        raise e
    finally:
        if connection:
            connection.close()
