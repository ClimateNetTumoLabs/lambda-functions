"""
Local test for the climate_net_api Lambda.

Runs the handler against a throwaway local PostgreSQL database seeded with the
same schema data_to_rds creates, so the wide-range behaviour can be exercised
without touching RDS.

Run:
    createdb climatenet_test
    python local_test.py

Connection settings come from the standard libpq environment variables
(PGHOST, PGUSER, PGPASSWORD, PGDATABASE); PGDATABASE defaults to climatenet_test.
"""

import base64
import gzip
import inspect
import io
import json
import os
import urllib.error
from datetime import datetime, timedelta, timezone

import psycopg2
from psycopg2 import sql

DB_NAME = os.environ.get('PGDATABASE', 'climatenet_test')
DEVICE_ID = '8'
TABLE = f'device{DEVICE_ID}'
EMPTY_TABLE = 'device999'
SEED_DAYS = 120
SEED_INTERVAL = '1 minute'

# The handler reads these; point it at the local database. Set before import so
# nothing depends on a config.py holding production credentials.
os.environ.setdefault('DB_HOST', os.environ.get('PGHOST', 'localhost'))
os.environ.setdefault('DB_USER', os.environ.get('PGUSER', os.environ.get('USER', 'postgres')))
os.environ.setdefault('DB_PASSWORD', os.environ.get('PGPASSWORD', ''))
os.environ.setdefault('DB_NAME', DB_NAME)
os.environ.setdefault('DB_SSLMODE', 'disable')  # local server has no TLS

import lambda_function
from lambda_function import KEYS, LAMBDA_PAYLOAD_LIMIT, MAX_ROWS, lambda_handler


def connect():
    return psycopg2.connect(host=os.environ['DB_HOST'], user=os.environ['DB_USER'],
                            password=os.environ['DB_PASSWORD'] or None,
                            database=DB_NAME)


def seed():
    """
    Creates and fills the device tables, topping up to the present on reruns.

    The default-window test asserts against the newest reading, so a table
    seeded days ago would otherwise drift and fail for the wrong reason.
    """
    connection = connect()
    connection.autocommit = True
    with connection.cursor() as cursor:
        for table in (TABLE, EMPTY_TABLE):
            # Exactly the DDL data_to_rds/lambda_function.py::create_table emits.
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id SERIAL PRIMARY KEY,
                    time TIMESTAMP, uv REAL, lux REAL, temperature REAL,
                    pressure SMALLINT, humidity SMALLINT, pm1 SMALLINT,
                    pm2_5 SMALLINT, pm10 SMALLINT, speed REAL, rain REAL,
                    direction TEXT
                )""")
            # No extra index, matching production: the only index is the
            # SERIAL primary key that this DDL creates.

        cursor.execute(f'SELECT count(*), max(time) FROM {TABLE}')
        existing, newest = cursor.fetchone()

        if existing:
            start = sql.Literal(newest) + sql.SQL(f" + interval '{SEED_INTERVAL}'")
            print(f'{TABLE} has {existing} rows, topping up from {newest}...')
        else:
            start = sql.SQL(f"(now() AT TIME ZONE 'UTC') - interval '{SEED_DAYS} days'")
            print(f'Seeding {TABLE} with {SEED_DAYS} days at {SEED_INTERVAL}...')

        cursor.execute(sql.SQL(f"""
            INSERT INTO {TABLE}
                (time, uv, lux, temperature, pressure, humidity,
                 pm1, pm2_5, pm10, speed, rain, direction)
            SELECT g, random()*11, random()*90000, random()*40, 900+random()*100,
                   random()*100, random()*50, random()*80, random()*120,
                   random()*15, random()*3, 'NW'
            FROM generate_series({{start}}, (now() AT TIME ZONE 'UTC'),
                                 interval '{SEED_INTERVAL}') g
        """).format(start=start))
        added = cursor.rowcount

        # Trim to a fixed window. Topping up without trimming grows the table
        # every run, and the payload-limit test sits close enough to the cap
        # that unbounded growth would fail it within days.
        cursor.execute(f"""DELETE FROM {TABLE} WHERE time <
            (now() AT TIME ZONE 'UTC') - interval '{SEED_DAYS} days'""")
        trimmed = cursor.rowcount

        cursor.execute(f'SELECT count(*) FROM {TABLE}')
        print(f'{cursor.fetchone()[0]} rows total (+{added}, -{trimmed}).\n')
    connection.close()


def call(**query_params):
    """Invokes the handler with an API Gateway HTTP API style event."""
    event = {'queryStringParameters': query_params or None,
             'requestContext': {'http': {'sourceIp': '212.34.238.10'}}}
    return lambda_handler(event, None)


def decode(response):
    """Returns the parsed body, transparently un-gzipping when compressed."""
    if response.get('isBase64Encoded'):
        return json.loads(gzip.decompress(base64.b64decode(response['body'])))
    return json.loads(response['body'])


def envelope_size(response):
    """Bytes the runtime actually returns to Lambda, including body escaping."""
    return len(json.dumps(response))


def row_count(where, params=()):
    connection = connect()
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT count(*) FROM {TABLE} WHERE {where}', params)
        count = cursor.fetchone()[0]
    connection.close()
    return count


def wide_range():
    """A range comfortably wider than the seeded data."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return ((now - timedelta(days=SEED_DAYS + 1)).strftime('%Y-%m-%d'),
            (now + timedelta(days=1)).strftime('%Y-%m-%d'))


def test_wide_range_fits_in_the_payload_limit():
    """The reported bug: a wide range serialised past Lambda's 6 MB cap."""
    start, end = wide_range()
    response = call(device_id=DEVICE_ID, start_time=start, end_time=end)

    assert response['statusCode'] == 200, decode(response)
    size = envelope_size(response)
    assert size < LAMBDA_PAYLOAD_LIMIT, \
        f'envelope is {size} bytes, over the {LAMBDA_PAYLOAD_LIMIT} limit'
    print(f'PASS wide range: {size / 1048576:.2f} MB envelope, under the limit')


def test_wide_range_returns_every_row():
    """"All the data is visible" — the whole point of the change."""
    start, end = wide_range()
    response = call(device_id=DEVICE_ID, start_time=start, end_time=end)
    body = decode(response)

    # end_time is expanded by a day, matching the handler's inclusive semantics.
    expected = row_count('time BETWEEN %s AND %s',
                         (start, (datetime.strptime(end, '%Y-%m-%d')
                                  + timedelta(days=1)).strftime('%Y-%m-%d')))
    assert len(body['data']) == expected, \
        f'returned {len(body["data"])} rows, expected {expected}'
    assert response.get('isBase64Encoded'), 'a range this wide should be compressed'
    assert response['headers']['Content-Encoding'] == 'gzip'
    print(f'PASS all data: {len(body["data"])} rows returned in one response')


def test_small_range_is_uncompressed():
    """The common case must look exactly as it does in production today."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    response = call(device_id=DEVICE_ID,
                    start_time=(now - timedelta(days=1)).strftime('%Y-%m-%d'),
                    end_time=now.strftime('%Y-%m-%d'))
    body = decode(response)

    assert response['statusCode'] == 200
    assert not response.get('isBase64Encoded'), 'small ranges must not be compressed'
    assert 'Content-Encoding' not in response['headers']
    assert body['keys'] == KEYS
    assert len(body['data'][0]) == len(KEYS), 'row width does not match keys'
    assert response['headers']['Access-Control-Allow-Origin'] == '*'
    print(f'PASS small range: {len(body["data"])} rows, plain JSON, CORS present')


def test_rows_are_ordered():
    """Without ORDER BY, wide ranges came back interleaved by parallel workers."""
    start, end = wide_range()
    body = decode(call(device_id=DEVICE_ID, start_time=start, end_time=end))

    times = [row[KEYS.index('timestamp')] for row in body['data']]
    assert times == sorted(times), 'rows are not in ascending time order'
    print(f'PASS ordering: {len(times)} rows ascending')


def test_serialisation_is_compact():
    """Rounding and formatting in SQL is what halves the payload."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    body = decode(call(device_id=DEVICE_ID,
                       start_time=(now - timedelta(days=1)).strftime('%Y-%m-%d'),
                       end_time=now.strftime('%Y-%m-%d')))
    row = body['data'][0]

    timestamp = row[KEYS.index('timestamp')]
    assert '.' not in timestamp, f'timestamp carries microseconds: {timestamp}'
    datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')

    for key in ('uv', 'lux', 'temperature', 'wind speed', 'rain'):
        value = row[KEYS.index(key)]
        # Rounding via ::numeric would return Decimal, which serialises as a
        # JSON string and would silently change the contract.
        assert isinstance(value, (int, float)), f'{key} is {type(value)}, not a number'
        assert round(value, 2) == value, f'{key} carries more than 2 decimals: {value}'
    print(f'PASS serialisation: second-precision timestamps, 2dp numeric floats')


def test_default_window_follows_the_data():
    """No start/end means 24h back from the newest reading in the table."""
    connection = connect()
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT max(time) FROM {TABLE}')
        newest = cursor.fetchone()[0]
    connection.close()

    expected = row_count('time > %s', (newest - timedelta(hours=24),))
    body = decode(call(device_id=DEVICE_ID))

    assert len(body['data']) == expected, \
        f'returned {len(body["data"])} rows, expected {expected}'
    # The old ipinfo.io lookup built this window in the caller's timezone, so a
    # UTC+4 caller silently got ~20 hours instead of 24.
    assert expected > 0, 'no rows in the default window; reseed the table'
    print(f'PASS default window: {len(body["data"])} rows back from {newest}')


def test_empty_table_returns_no_rows():
    """max(time) on an empty table is NULL; that must not raise."""
    response = call(device_id=EMPTY_TABLE.removeprefix('device'))
    body = decode(response)

    assert response['statusCode'] == 200, body
    assert body['data'] == [], f'expected no rows, got {len(body["data"])}'
    print('PASS empty table: returns an empty data array, not a 500')


def test_no_ip_geolocation():
    """
    The removed ipinfo.io lookup must not come back.

    /getDevices does make an outbound call, so this no longer forbids HTTP
    outright — only the per-request IP geolocation that silently shifted the
    default window into the caller's timezone.
    """
    source = open(lambda_function.__file__).read()
    assert 'ipinfo' not in source and 'pytz' not in source, \
        'handler performs IP geolocation again'
    # The readings path specifically must stay free of network calls.
    assert 'urllib' not in inspect.getsource(lambda_function.get_data_by_date), \
        'the /getData path now makes an outbound HTTP call'
    print('PASS no IP geolocation on the readings path')


def test_reads_config_from_environment():
    """Credentials must come from the environment, not a bundled config.py."""
    source = open(lambda_function.__file__).read()
    assert 'import config' not in source, 'handler still imports config.py'

    saved = os.environ.pop('DB_HOST')
    try:
        response = call(device_id=DEVICE_ID)
        assert response['statusCode'] == 500, 'missing DB_HOST should fail cleanly'
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
    finally:
        os.environ['DB_HOST'] = saved
    print('PASS env config: missing variable fails as a 500 with CORS headers')


def test_rejects_bad_input():
    """Bad input is a 400 with a message and CORS headers, never a 500."""
    cases = [
        ('missing device_id', {}, 'Missing device_id'),
        ('non numeric device_id', {'device_id': 'abc'}, 'must be an integer'),
        # str.isdigit() is True for these, so they used to reach the SQL layer.
        ('unicode digit device_id', {'device_id': '٣'}, 'must be an integer'),
        ('superscript device_id', {'device_id': '²'}, 'must be an integer'),
        ('bad date format', {'device_id': DEVICE_ID, 'start_time': '06-01-2025',
                             'end_time': '07-01-2025'}, 'Invalid date format'),
        ('only start_time', {'device_id': DEVICE_ID,
                             'start_time': '2025-01-06'}, 'Both start_time and end_time'),
        ('reversed range', {'device_id': DEVICE_ID, 'start_time': '2025-06-01',
                            'end_time': '2025-01-01'}, 'must not be after'),
    ]
    for name, params, expected in cases:
        response = call(**params)
        assert response['statusCode'] == 400, f'{name}: got {response["statusCode"]}'
        assert expected in decode(response)['error'], \
            f'{name}: unexpected message {decode(response)["error"]}'
        assert response['headers']['Access-Control-Allow-Origin'] == '*', \
            f'{name}: error response is missing CORS headers'
    print(f'PASS input validation: {len(cases)} rejected cases, all with CORS')


def test_survives_malformed_events():
    """A request with no query string or no requestContext must not 500."""
    for name, event in [
        ('null queryStringParameters', {'queryStringParameters': None}),
        ('absent queryStringParameters', {}),
        ('no requestContext', {'queryStringParameters': {'device_id': DEVICE_ID}}),
    ]:
        response = lambda_handler(event, None)
        assert response['statusCode'] in (200, 400), \
            f'{name}: got {response["statusCode"]}'
    print('PASS malformed events handled')


def test_oversized_range_is_refused_cleanly():
    """Past MAX_ROWS the handler must 413, not run out of memory."""
    saved = lambda_function.MAX_ROWS
    lambda_function.MAX_ROWS = 10
    try:
        start, end = wide_range()
        response = call(device_id=DEVICE_ID, start_time=start, end_time=end)
        assert response['statusCode'] == 413, f'got {response["statusCode"]}'
        assert 'narrower' in decode(response)['error']
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
    finally:
        lambda_function.MAX_ROWS = saved
    print('PASS oversized range: 413 with a clear message')


# ── /getDevices ──────────────────────────────────────────────────────────────
# The device list comes from Django, so these stub the HTTP call rather than
# depending on the network. The payload mirrors what DeviceDetailSerializer
# actually returns, including the fields that must never be re-published.

DJANGO_DEVICE = {
    'id': 1, 'generated_id': 8,
    'location': 'V. Sargsyan', 'location_en': 'V. Sargsyan',
    'location_hy': 'Վ․ Սարգսյան',
    'region': 'Yerevan', 'region_en': 'Yerevan', 'region_hy': 'Երևան',
    'country': 'Armenia', 'country_en': 'Armenia', 'country_hy': 'Հայաստան',
    'latitude': '40.185285', 'longitude': '44.560020',
    'LTR390': 'valid', 'BME280': 'valid', 'PMS5003': 'valid',
    'Wind': 'valid', 'Rainfall': 'valid', 'Status': 'online',
    'last_updated': '2026-07-27T12:54:17.510741+04:00',
    'created_at': '2023-11-16T16:32:00+04:00', 'issues': [],
    # Present in the real response, must not reach the caller.
    'owner': 3, 'owner_email': 'owner@example.com', 'owner_is_admin': False,
    'visibility': 'public', 'request_origin': 'a1b2c3d4',
}

LEAKY_FIELDS = ('owner', 'owner_email', 'owner_is_admin',
                'visibility', 'request_origin')


def call_devices(payload=None, raises=None):
    """Invokes /getDevices with the Django call stubbed out."""
    def fake_urlopen(request, timeout=None):
        assert request.get_header('X-bot-secret'), 'shared secret not sent'
        if raises:
            raise raises
        return io.BytesIO(json.dumps(payload).encode())

    saved = lambda_function.urllib.request.urlopen
    lambda_function.urllib.request.urlopen = fake_urlopen
    os.environ.setdefault('BOT_SHARED_SECRET', 'test-secret')
    try:
        return lambda_handler({'rawPath': '/getDevices',
                               'requestContext': {'http': {'path': '/getDevices'}}},
                              None)
    finally:
        lambda_function.urllib.request.urlopen = saved


def test_devices_returns_allowlisted_fields():
    """Every device carries exactly the agreed field set, in order."""
    response = call_devices([DJANGO_DEVICE])
    body = decode(response)

    assert response['statusCode'] == 200, body
    assert isinstance(body, list), f'expected a JSON array, got {type(body)}'
    assert tuple(body[0]) == lambda_function.DEVICE_FIELDS, \
        f'field set drifted: {tuple(body[0])}'
    assert body[0]['generated_id'] == 8
    assert response['headers']['Access-Control-Allow-Origin'] == '*'
    print(f'PASS devices: {len(lambda_function.DEVICE_FIELDS)} allowlisted fields')


def test_devices_never_leaks_private_fields():
    """The security-critical one: owner_email must never reach the public API."""
    response = call_devices([DJANGO_DEVICE])

    for field in LEAKY_FIELDS:
        assert field not in decode(response)[0], f'{field} leaked into the body'
        assert field not in response['body'], f'{field} present in raw body'
    print(f'PASS devices: {len(LEAKY_FIELDS)} private fields withheld')


def test_devices_armenian_text_is_not_escaped():
    """Armenian must arrive as UTF-8, not as \\uXXXX escapes."""
    response = call_devices([DJANGO_DEVICE])

    assert 'Վ․ Սարգսյան' in response['body'], \
        'Armenian is \\u-escaped; json.dumps needs ensure_ascii=False'
    assert '\\u054e' not in response['body'], 'body still contains escapes'
    assert 'charset=utf-8' in response['headers']['Content-Type']
    assert decode(response)[0]['location_hy'] == 'Վ․ Սարգսյան'
    print('PASS devices: Armenian returned as readable UTF-8')


def test_payload_limits_are_measured_in_bytes():
    """
    Non-ASCII makes len(str) smaller than the byte count.

    The cap is a byte limit, so measuring characters would let an oversized
    response through.
    """
    source = inspect.getsource(lambda_function._response)
    assert 'len(body)' not in source, \
        '_response measures characters, not bytes; non-ASCII would slip past the cap'

    # Armenian is 2 bytes per character in UTF-8, so this is 3 MB of characters
    # but 6 MB of payload — under the threshold by one measure, over by the other.
    huge = [{'x': 'Ա' * 3_000_000}]
    body = json.dumps(huge, separators=(',', ':'), ensure_ascii=False)
    assert len(body) < lambda_function.GZIP_THRESHOLD < len(body.encode()), \
        'test fixture no longer straddles the threshold'

    response = lambda_function._response(200, huge)
    assert response.get('isBase64Encoded'), \
        'a body over the byte threshold was returned uncompressed'
    print('PASS limits measured in bytes, not characters')


def test_devices_route_needs_no_database():
    """The device list comes from Django, so no DB connection may be opened."""
    saved = {name: os.environ.pop(name) for name in
             ('DB_HOST', 'DB_USER', 'DB_NAME') if name in os.environ}
    try:
        response = call_devices([DJANGO_DEVICE])
        assert response['statusCode'] == 200, decode(response)
    finally:
        os.environ.update(saved)
    print('PASS devices: works with the DB variables unset')


def test_devices_upstream_failure_is_502():
    """A backend outage is a clean 502, not a 500 or a stack trace."""
    response = call_devices(raises=urllib.error.URLError('connection refused'))
    body = decode(response)

    assert response['statusCode'] == 502, f'got {response["statusCode"]}'
    assert 'registry' in body['error']
    assert response['headers']['Access-Control-Allow-Origin'] == '*'
    print('PASS devices: upstream failure returns 502 with CORS')


def test_devices_missing_secret_fails_cleanly():
    """Without the shared secret Django would 403; fail before calling it."""
    saved = os.environ.pop('BOT_SHARED_SECRET', None)
    try:
        response = lambda_handler({'rawPath': '/getDevices'}, None)
        assert response['statusCode'] == 500, f'got {response["statusCode"]}'
        assert response['headers']['Access-Control-Allow-Origin'] == '*'
    finally:
        if saved is not None:
            os.environ['BOT_SHARED_SECRET'] = saved
    print('PASS devices: missing secret fails as a 500 with CORS')


def test_getdata_route_still_works():
    """Path dispatch must not have broken the original route."""
    for path in ('/getData', '/prod/getData', None):
        event = {'queryStringParameters': {'device_id': DEVICE_ID}}
        if path:
            event['rawPath'] = path
        response = lambda_handler(event, None)
        assert response['statusCode'] == 200, f'{path}: {decode(response)}'
        assert 'keys' in decode(response), f'{path}: not the readings payload'
    print('PASS /getData unaffected by path dispatch')


if __name__ == '__main__':
    seed()
    for test in [
        test_wide_range_fits_in_the_payload_limit,
        test_wide_range_returns_every_row,
        test_small_range_is_uncompressed,
        test_rows_are_ordered,
        test_serialisation_is_compact,
        test_default_window_follows_the_data,
        test_empty_table_returns_no_rows,
        test_no_ip_geolocation,
        test_reads_config_from_environment,
        test_rejects_bad_input,
        test_survives_malformed_events,
        test_oversized_range_is_refused_cleanly,
        test_devices_returns_allowlisted_fields,
        test_devices_never_leaks_private_fields,
        test_devices_armenian_text_is_not_escaped,
        test_payload_limits_are_measured_in_bytes,
        test_devices_route_needs_no_database,
        test_devices_upstream_failure_is_502,
        test_devices_missing_secret_fails_cleanly,
        test_getdata_route_still_works,
    ]:
        test()
    print('\nAll tests passed.')
