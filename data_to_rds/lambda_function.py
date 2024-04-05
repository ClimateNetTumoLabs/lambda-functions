import psycopg2

import config


def validate_value(key, value):
    try:
        if value is None:
            return "NULL"

        if config.COLUMNS[key] == "SMALLINT":
            return f"'{round(float(value))}'"

        return f"'{value}'"
    except ValueError:
        return f"'{value}'"


def connect_to_db(device_id):
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


def add_message(info, connection, cursor, is_list=False):
    device, data = info['device'], info['data']

    for data_dict in data:
        # Remove this condition and is_list argument after Vazgen Sargsyan
        if is_list:
            data_dict = {
                "time": data_dict[0],
                "temperature": data_dict[2],
                "pressure": data_dict[3],
                "humidity": data_dict[4],
                "pm1": data_dict[5],
                "pm2_5": data_dict[6],
                "pm10": data_dict[7],
                "speed": data_dict[8],
                "rain": data_dict[9],
                "direction": data_dict[10],
            }

        keys = []
        values = []

        for key, value in data_dict.items():
            if key in config.COLUMNS.keys():
                keys.append(key)
                values.append(validate_value(key, value))

        cursor.execute(f"INSERT INTO {device} ({', '.join(keys)}) VALUES ({', '.join(values)})")

    connection.commit()


def lambda_handler(event, context):
    conn, cursor = connect_to_db(event["device"])

    if isinstance(event['data'][0], dict):
        add_message(event, conn, cursor)
    elif isinstance(event['data'][0], list):
        add_message(event, conn, cursor, is_list=True)

    conn.close()
