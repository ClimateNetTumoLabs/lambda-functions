import psycopg2

import config

columns = {
    "time": "TIMESTAMP",
    "uv": "REAL",
    "lux": "REAL",
    "temperature": "REAL",
    "pressure": "SMALLINT",
    "humidity": "SMALLINT",
    "pm1": "SMALLINT",
    "pm2_5": "SMALLINT",
    "pm10": "SMALLINT",
    "speed": "REAL",
    "rain": "REAL",
    "direction": "TEXT"
}


def validate_value(key, value):
    try:
        if value is None:
            return "NULL"

        if columns[key] == "SMALLINT":
            return f"'{round(float(value))}'"

        return f"'{value}'"
    except ValueError:
        return f"'{value}'"


def connect_to_db(device_id):
    column_definitions = [f"{column_name} {column_type}" for column_name, column_type in columns.items()]
    query_columns = ",\n    ".join(column_definitions)

    create_table_query = f"""
CREATE TABLE IF NOT EXISTS {device_id} (
    id SERIAL PRIMARY KEY,
    {query_columns}
);
 """

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

    except Exception as ex:
        print("Error", ex)
        return False


def add_message(info, connection, cursor):
    table_columns = list(columns.keys())

    device = info['device']

    for data in info['data']:
        fields = []
        values = []
        for key, value in data.items():
            if key in table_columns:
                fields.append(key)
                values.append(validate_value(key, value))

        cursor.execute(f"INSERT INTO {device} ({', '.join(fields)}) VALUES ({', '.join(values)})")

    connection.commit()


def add_message2(info, connection, cursor):
    table_columns = list(columns.keys())
    device = info['device']

    for data in info['data']:
        data_dict = {
            "time": data[0],
            "temperature": data[2],
            "pressure": data[3],
            "humidity": data[4],
            "pm1": data[5],
            "pm2_5": data[6],
            "pm10": data[7],
            "speed": data[8],
            "rain": data[9],
            "direction": data[10],
        }

        fields = []
        values = []
        for key, value in data_dict.items():
            if key in table_columns:
                fields.append(key)
                values.append(validate_value(key, value))

        cursor.execute(f"INSERT INTO {device} ({', '.join(fields)}) VALUES ({', '.join(values)})")

    connection.commit()


def lambda_handler(event, context):
    conn, cursor = connect_to_db(event["device"])

    if isinstance(event['data'][0], dict):
        add_message(event, conn, cursor)
    elif isinstance(event['data'][0], list):
        add_message2(event, conn, cursor)

    conn.close()
    return True
