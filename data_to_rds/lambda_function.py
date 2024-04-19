import psycopg2

import config


def validate_value(key, value):
    """
    Validate and format a value based on its data type as specified in the config file.

    Args:
        key (str): The key representing the column name for which the value is being validated.
        value: The value to be validated and formatted.

    Returns:
        str: The validated and formatted value as a string.

    Note:
        This function checks the data type of the value based on the corresponding column type
        specified in the config file. It performs the following validations and formatting:
        - If the value is None, it returns 'NULL'.
        - If the column type is 'SMALLINT', it rounds the value to the nearest integer and returns it as a string.
        - Otherwise, it returns the value as a string with single quotes around it.
        If the value cannot be converted to the specified data type, it returns the original value as a string.
    """
    try:
        if value is None:
            return "NULL"

        if config.COLUMNS[key] == "SMALLINT":
            return f"'{round(float(value))}'"

        return f"'{value}'"
    except ValueError:
        return f"'{value}'"


def connect_to_db(device_id):
    """
    Establish a connection to the PostgreSQL database and create a table for the specified device ID.

    Args:
        device_id (str): The ID of the device for which the table will be created.

    Returns:
        tuple: A tuple containing the connection object and cursor object.
            - connection (psycopg2.extensions.connection): The connection to the PostgreSQL database.
            - cursor (psycopg2.extensions.cursor): The cursor object for executing queries on the database.

    Note:
        This function creates a table in the database for the specified device ID, using column definitions
        provided in the config file. If the table already exists, it will not be recreated.
    """
    column_definitions = [f"{column_name} {column_type}" for column_name, column_type in config.COLUMNS.items()]
    query_columns = ",\n    ".join(column_definitions)

    create_table_query = f"CREATE TABLE IF NOT EXISTS {device_id} (id SERIAL PRIMARY KEY, {query_columns});"

    try:
        connection = psycopg2.connect(
            host=config.HOST,
            user=config.USER,
            password=config.PASSWORD,
            database=config.DB_NAME
        )
        cursor = connection.cursor()
        cursor.execute(create_table_query)
        connection.commit()
        return connection, cursor

    except psycopg2.OperationalError:
        return None, None


def add_message(info, connection, cursor):
    """
    Add message data to the database table for the specified device.

    Args:
        info (dict): Information about the message including device ID and message data.
        connection (psycopg2.extensions.connection): The connection to the PostgreSQL database.
        cursor (psycopg2.extensions.cursor): The cursor object for executing queries on the database.

    Returns:
        None

    Note:
        This function inserts message data into the database table specified by the device ID in the 'info' dictionary.
        The function then validates and inserts the message data into the database.
    """
    device, data = info['device'], info['data']

    for data_dict in data:
        keys = []
        values = []

        for key, value in data_dict.items():
            if key in config.COLUMNS.keys():
                keys.append(key)
                values.append(validate_value(key, value))

        cursor.execute(f"INSERT INTO {device} ({', '.join(keys)}) VALUES ({', '.join(values)})")

    connection.commit()


def lambda_handler(event, context):
    """
    Lambda function handler for adding message data to the database.

    Args:
        event (dict): The event data passed to the lambda function.
        context (LambdaContext): The runtime information of the lambda function.

    Returns:
        None

    Note:
        This function connects to the PostgreSQL database using the device ID from the event data,
        then adds the message data from the event to the database table for the specified device.
        It determines the format of the message data (list or dictionary) and calls the 'add_message' function
        accordingly, with an optional 'is_list' argument set to True if the data is provided as a list.
        After adding the message data, it closes the database connection.
    """
    conn, cursor = connect_to_db(event["device"])

    if isinstance(event['data'][0], dict) and cursor:
        add_message(event, conn, cursor)

    conn.close()
