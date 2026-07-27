"""
Description:
This module provides functions for interacting with a PostgreSQL database and handling HTTP requests in an AWS Lambda function.

Routes:
    - GET /getData:    readings for one device, from RDS.
    - GET /getDevices: the public device list, from the Django backend.

Functions:
    - connect_to_db: Establishes a connection to the PostgreSQL database.
    - get_data_by_date: Retrieves data from the database for a specific device within a given time range.
    - get_devices: Retrieves the public device list from the Django backend.
    - validate_params: Validates query parameters passed to the Lambda function.
    - lambda_handler: Main entry point for the AWS Lambda function.

Dependencies:
    - psycopg2: PostgreSQL adapter for Python.
    - json: JSON serialization and deserialization.
    - datetime: Date and time manipulation.

Configuration comes from environment variables: DB_HOST, DB_USER, DB_PASSWORD,
DB_NAME and the optional DB_SSLMODE for /getData; BOT_SHARED_SECRET and the
optional DEVICES_URL for /getDevices.
"""

import base64
import gzip
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import psycopg2
from psycopg2 import sql

RESPONSE_HEADERS = {
    # charset is explicit so the Armenian device names in /getDevices are
    # decoded as UTF-8 by every client, not just those assuming the JSON default.
    "Content-Type": "application/json; charset=utf-8",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
}

# KEYS[i] labels COLUMNS[i]. Selecting these explicitly rather than SELECT *
# keeps the two from drifting apart when a column is added to the table.
KEYS = ["id", "timestamp", "uv", "lux", "temperature", "pressure", "humidity",
        "pm1", "pm2_5", "pm10", "wind speed", "rain", "wind direction"]

# Rounding and formatting in SQL rather than Python halves the payload for
# identical data and avoids building a Python object per value. The ::float8
# casts matter: round() alone returns Decimal, which serializes as a JSON
# *string* and would change the response contract.
COLUMNS = sql.SQL(', ').join([
    sql.SQL('id'),
    sql.SQL("to_char(time, 'YYYY-MM-DD HH24:MI:SS')"),
    sql.SQL('round(uv::numeric, 2)::float8'),
    sql.SQL('round(lux::numeric, 2)::float8'),
    sql.SQL('round(temperature::numeric, 2)::float8'),
    sql.SQL('pressure'),
    sql.SQL('humidity'),
    sql.SQL('pm1'),
    sql.SQL('pm2_5'),
    sql.SQL('pm10'),
    sql.SQL('round(speed::numeric, 2)::float8'),
    sql.SQL('round(rain::numeric, 2)::float8'),
    sql.SQL('direction'),
])

# Lambda rejects a response payload over 6,291,556 bytes. That is measured on
# the whole JSON document the runtime returns, so the envelope keys and the
# escaping of every quote inside `body` count against it too.
LAMBDA_PAYLOAD_LIMIT = 6291556
# Past this, gzip the body. Level 6 is deliberate: at ~172k rows level 1 lands
# at 6.63 MB base64 (over the limit) and level 6 at 5.83 MB, in 0.57s.
GZIP_THRESHOLD = 5000000
GZIP_LEVEL = 6
# Refuse before fetching rather than running out of memory mid-request. A row
# costs ~890 bytes resident, so 300k rows is already ~270 MB.
MAX_ROWS = 300000

# API Gateway abandons the integration at 30s; fail in the DB before that.
STATEMENT_TIMEOUT_MS = 20000

# /getDevices. The device registry lives in the Django backend, not in RDS —
# there is no device metadata table in the database this Lambda connects to.
DEVICES_URL = os.environ.get('DEVICES_URL', 'https://climatenet.am/api/list/')
DEVICES_TIMEOUT = 10

# An allowlist, not a blocklist. Django's serializer also returns owner_email,
# owner, visibility and request_origin, none of which belong on a public
# endpoint — and a field added to the Django model must not start appearing
# here on its own.
DEVICE_FIELDS = ('id', 'generated_id',
                 'location', 'location_en', 'location_hy',
                 'region', 'region_en', 'region_hy',
                 'country', 'country_en', 'country_hy',
                 'latitude', 'longitude',
                 'LTR390', 'BME280', 'PMS5003', 'Wind', 'Rainfall',
                 'Status', 'last_updated', 'created_at', 'issues')


def _response(status_code, payload):
    """Builds an API Gateway proxy response, compressing oversized bodies."""
    # ensure_ascii=False so Armenian text is emitted as UTF-8 rather than as
    # \uXXXX escapes. Both are valid JSON and parse identically, but the
    # escaped form is unreadable in curl and roughly twice the bytes.
    body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
    # Measure bytes, not characters: with ensure_ascii=False one Armenian
    # character is 1 character but 2-3 bytes, and the limits below are byte
    # limits.
    encoded = body.encode()
    headers = dict(RESPONSE_HEADERS)

    if len(encoded) < GZIP_THRESHOLD:
        return {'statusCode': status_code, 'headers': headers, 'body': body}

    # Triggered by size, not by Accept-Encoding: curl sends no Accept-Encoding
    # by default, so negotiating would send the common case down the
    # uncompressed path and straight into the payload limit.
    headers['Content-Encoding'] = 'gzip'
    compressed = base64.b64encode(gzip.compress(encoded, GZIP_LEVEL)).decode()

    response = {'statusCode': status_code, 'headers': headers,
                'body': compressed, 'isBase64Encoded': True}

    if len(json.dumps(response).encode()) >= LAMBDA_PAYLOAD_LIMIT:
        return _error(413, 'Response too large even compressed. '
                           'Request a narrower date range.')

    return response


def _error(status_code, message):
    """Builds an error response. Never compressed, so it cannot recurse."""
    return {
        'statusCode': status_code,
        'headers': dict(RESPONSE_HEADERS),
        'body': json.dumps({'error': message}, ensure_ascii=False)
    }


def _is_integer(value):
    """True for plain ASCII integers. str.isdigit() alone accepts '²' and '٣'."""
    value = str(value)
    return value.isascii() and value.isdigit()


def connect_to_db():
    """
    Establishes a connection to the PostgreSQL database.

    Returns:
        psycopg2.extensions.connection: A connection object to the database.

    Raises:
        RuntimeError: If configuration is missing or the connection fails.
    """
    settings = {name: os.environ.get(name) for name in
                ('DB_HOST', 'DB_USER', 'DB_PASSWORD', 'DB_NAME')}
    # DB_PASSWORD only has to be present, not non-empty: trust and peer auth
    # legitimately use a blank password.
    missing = [name for name, value in settings.items()
               if value is None or (not value and name != 'DB_PASSWORD')]
    if missing:
        raise RuntimeError(
            f"Missing environment variable(s): {', '.join(missing)}")

    try:
        return psycopg2.connect(
            host=settings['DB_HOST'],
            user=settings['DB_USER'],
            password=settings['DB_PASSWORD'],
            database=settings['DB_NAME'],
            connect_timeout=5,
            # libpq defaults to 'prefer', which silently falls back to
            # plaintext if the TLS handshake fails.
            sslmode=os.environ.get('DB_SSLMODE', 'require')
        )
    except Exception as e:
        raise RuntimeError("Failed to connect to the database") from e


def get_data_by_date(device, connection, start_time=None, end_time=None):
    """
    Retrieves data from the database for a specific device within a time range.

    Args:
        device (str): The device table name, e.g. 'device8'.
        connection (psycopg2.extensions.connection): The database connection object.
        start_time (str, optional): Start of the range, 'YYYY-MM-DD'. Defaults to None.
        end_time (str, optional): End of the range, 'YYYY-MM-DD'. Defaults to None.

    Returns:
        list: A list of tuples containing the fetched data, or None if the
              range holds more rows than can be returned.

    Raises:
        RuntimeError: If fetching data from the database fails.
    """
    table = sql.Identifier(device)

    if start_time and end_time:
        end_time = (datetime.strptime(end_time, '%Y-%m-%d')
                    + timedelta(days=1)).strftime('%Y-%m-%d')
        where = sql.SQL('time BETWEEN %s AND %s')
        params = (start_time, end_time)
    else:
        # Anchored to the newest reading rather than the caller's clock, so it
        # needs no assumption about which timezone devices report in. As a
        # subquery it is one round trip, and an empty table yields no rows by
        # construction instead of raising on None.
        where = sql.SQL(
            'time > (SELECT max(time) FROM {}) - interval \'24 hours\''
        ).format(table)
        params = ()

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL('SET LOCAL statement_timeout = {}')
                           .format(sql.Literal(STATEMENT_TIMEOUT_MS)))

            # Counting first turns an impossible request into a fast 413
            # instead of an out-of-memory kill part way through fetchall().
            cursor.execute(
                sql.SQL('SELECT count(*) FROM {table} WHERE {where}')
                .format(table=table, where=where), params)
            if cursor.fetchone()[0] > MAX_ROWS:
                return None

            # ORDER BY is required, not cosmetic: without it Postgres switches
            # to a parallel sequential scan on wide ranges and the workers
            # return rows interleaved.
            cursor.execute(
                sql.SQL('SELECT {columns} FROM {table} WHERE {where} '
                        'ORDER BY time, id')
                .format(columns=COLUMNS, table=table, where=where), params)
            return cursor.fetchall()

    except Exception as e:
        print(e)
        raise RuntimeError(f"Failed to fetch data for device {device}") from e


def get_devices():
    """
    Retrieves the public device list from the Django backend.

    The backend already restricts anonymous callers to devices with public
    visibility, so no filtering is needed here beyond the field allowlist.

    Returns:
        list: One dict per device, limited to DEVICE_FIELDS.

    Raises:
        RuntimeError: If BOT_SHARED_SECRET is not configured.
        urllib.error.URLError: If the backend is unreachable or refuses.
    """
    secret = os.environ.get('BOT_SHARED_SECRET')
    if not secret:
        raise RuntimeError('Missing environment variable: BOT_SHARED_SECRET')

    # Django gates this endpoint on a Referer/Origin allowlist or on this
    # shared secret. A Lambda sends neither header, so the secret is the only
    # way through.
    request = urllib.request.Request(
        DEVICES_URL, headers={'X-Bot-Secret': secret,
                              'Accept': 'application/json'})

    with urllib.request.urlopen(request, timeout=DEVICES_TIMEOUT) as response:
        devices = json.loads(response.read().decode())

    return [{field: device.get(field) for field in DEVICE_FIELDS}
            for device in devices]


def validate_params(query_params):
    """
    Validates query parameters passed to the Lambda function.

    Args:
        query_params (dict): A dictionary containing the query parameters.

    Returns:
        dict: The validated parameters, or an API Gateway error response if the
              parameters are rejected (identified by a 'statusCode' key).
    """
    # API Gateway sends queryStringParameters: null when the URL has no query.
    query_params = query_params or {}

    device_id = query_params.get('device_id')
    if not device_id:
        return _error(400, 'Missing device_id parameter')

    if not _is_integer(device_id):
        return _error(400, 'Invalid format for device_id. It must be an integer.')

    start_time = query_params.get('start_time')
    end_time = query_params.get('end_time')

    if start_time and end_time:
        try:
            start = datetime.strptime(start_time, '%Y-%m-%d')
            end = datetime.strptime(end_time, '%Y-%m-%d')
        except ValueError:
            return _error(400, 'Invalid date format. It must be YYYY-MM-DD.')

        if start > end:
            return _error(400, 'start_time must not be after end_time')

        return {'device': f'device{device_id}',
                'start_time': start_time, 'end_time': end_time}
    elif not start_time and not end_time:
        return {'device': f'device{device_id}'}
    else:
        return _error(400, 'Both start_time and end_time must be provided')


def lambda_handler(event, context):
    """
    Main entry point for the AWS Lambda function.

    Args:
        event (dict): The event data passed to the Lambda function.
        context (LambdaContext): The runtime information provided by AWS Lambda.

    Returns:
        dict: A dictionary containing the HTTP response.
    """
    connection = None

    try:
        # rawPath is present on payload format 2.0; the requestContext fallback
        # covers a stage-prefixed path. Matching the last segment survives both.
        path = (event.get('rawPath')
                or event.get('requestContext', {}).get('http', {}).get('path', ''))

        # Returns before connect_to_db: the device list comes from Django, so
        # this route never opens a database connection.
        if path.rstrip('/').rsplit('/', 1)[-1] == 'getDevices':
            return _response(200, get_devices())

        validation_result = validate_params(event.get('queryStringParameters'))

        if 'statusCode' in validation_result:
            return validation_result

        connection = connect_to_db()

        data = get_data_by_date(
            validation_result['device'],
            connection,
            validation_result.get('start_time'),
            validation_result.get('end_time')
        )

        if data is None:
            return _error(413, f'Range holds more than {MAX_ROWS} readings. '
                               'Request a narrower date range.')

        return _response(200, {'keys': KEYS, 'data': data})

    except urllib.error.URLError as e:
        # HTTPError subclasses URLError, so a 403 from a wrong shared secret
        # lands here too — logged, with a generic message to the caller.
        print(e)
        return _error(502, 'Could not reach the device registry.')
    except Exception as e:
        # Logged, not returned: database errors quote the failing query and
        # schema. Returned through _error so the CORS headers survive, which a
        # re-raise would not do.
        print(e)
        return _error(500, 'Server error occurred while fetching data from the database.')
    finally:
        if connection:
            connection.close()
