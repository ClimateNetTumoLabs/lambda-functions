# ClimateNet API Lambda

Serves climate readings from RDS (PostgreSQL) over an API Gateway HTTP API.
One table per device (`device8`, `device12`, …), written by `data_to_rds`.

| File                 | Purpose                               |
| :------------------- | :------------------------------------ |
| `lambda_function.py` | The handler                           |
| `install.sh`         | Builds `lambda_function.zip`          |
| `requirements.txt`   | Dependencies                          |
| `local_test.py`      | Test suite against a local PostgreSQL |
| `main.py`            | Smoke test against the real database  |

---

# Setup

First-time setup is steps 1–6. Shipping new code is **1 → 3**.

## 1. Build the zip

```bash
cd climate_net_api
chmod +x install.sh && ./install.sh
```

For an arm64 function:

```bash
PLATFORM=manylinux2014_aarch64 ./install.sh
```

The script prints the packaged extension. It must end in `-linux-gnu.so` and
match the function's architecture, or the function fails at import with
`No module named 'psycopg2._psycopg'`.

## 2. Configure the function

**Configuration → General configuration**, and runtime under
**Code → Runtime settings**.

| Setting      | Value                          |
| :----------- | :----------------------------- |
| Runtime      | `python3.13`                   |
| Architecture | must match the zip from step 1 |
| Memory       | 1024 MB                        |
| Timeout      | 30 s                           |

Memory matters: at 128 MB a large query is OOM-killed and API Gateway returns a
502 with no CORS headers, which reads as a CORS bug.

## 3. Upload the zip

**Code → Upload from ▾ → .zip file** → `lambda_function.zip` → **Save**.

Handler stays `lambda_function.lambda_handler`.

> [!IMPORTANT]
> Uploaded code goes live immediately — there is no staging step. To test
> first, create a second function with the same role, VPC and variables, and
> attach it to a temporary route.

## 4. Set environment variables

**Configuration → Environment variables → Edit**.

| Variable            | Required        | Default                            |
| :------------------ | :-------------- | :--------------------------------- |
| `DB_HOST`           | for `/getData`  | —                                  |
| `DB_USER`           | for `/getData`  | —                                  |
| `DB_PASSWORD`       | for `/getData`  | —                                  |
| `DB_NAME`           | for `/getData`  | —                                  |
| `DB_SSLMODE`        | no              | `require`                          |
| `BOT_SHARED_SECRET` | for `/getDevices` | —                                |
| `DEVICES_URL`       | no              | `https://climatenet.am/api/list/`  |

A missing variable produces a 500 naming it in CloudWatch.

`BOT_SHARED_SECRET` must match the value of the same name in the Django
backend's environment. Django gates the device list on a `Referer`/`Origin`
allowlist or on this secret, and a Lambda sends neither header.

## 5. Connect API Gateway

**Develop → Routes → Create**: method `GET`, path `/getData`, then
**Attach integration → Lambda function**, payload format **2.0**.

Repeat for `/getDevices`, attaching the **same** integration — one function
serves both routes.

## 6. Add test events

**Test → Create new event**. For `/getData`, only `queryStringParameters`
affects the result; for `/getDevices`, only `rawPath`.

<details>
<summary><code>default-window</code> → 200, ~1 day of rows</summary>

```json
{
    "version": "2.0",
    "routeKey": "GET /getData",
    "rawPath": "/getData",
    "rawQueryString": "device_id=8",
    "headers": { "accept": "*/*" },
    "queryStringParameters": { "device_id": "8" },
    "requestContext": { "apiId": "<api-id>", "http": { "method": "GET", "path": "/getData", "protocol": "HTTP/1.1", "sourceIp": "1.1.1.1", "userAgent": "curl/8.4.0" }, "routeKey": "GET /getData", "stage": "$default" },
    "isBase64Encoded": false
}
```

</details>

<details>
<summary><code>narrow-range</code> → 200, plain JSON</summary>

```json
{
    "version": "2.0",
    "routeKey": "GET /getData",
    "rawPath": "/getData",
    "rawQueryString": "device_id=8&start_time=2026-07-20&end_time=2026-07-21",
    "headers": { "accept": "*/*" },
    "queryStringParameters": { "device_id": "8", "start_time": "2026-07-20", "end_time": "2026-07-21" },
    "requestContext": { "apiId": "<api-id>", "http": { "method": "GET", "path": "/getData", "protocol": "HTTP/1.1", "sourceIp": "1.1.1.1", "userAgent": "curl/8.4.0" }, "routeKey": "GET /getData", "stage": "$default" },
    "isBase64Encoded": false
}
```

</details>

<details>
<summary><code>wide-range</code> → 200 with <code>isBase64Encoded: true</code></summary>

```json
{
    "version": "2.0",
    "routeKey": "GET /getData",
    "rawPath": "/getData",
    "rawQueryString": "device_id=8&start_time=2023-01-01&end_time=2026-07-22",
    "headers": { "accept": "*/*" },
    "queryStringParameters": { "device_id": "8", "start_time": "2023-01-01", "end_time": "2026-07-22" },
    "requestContext": { "apiId": "<api-id>", "http": { "method": "GET", "path": "/getData", "protocol": "HTTP/1.1", "sourceIp": "1.1.1.1", "userAgent": "curl/8.4.0" }, "routeKey": "GET /getData", "stage": "$default" },
    "isBase64Encoded": false
}
```

</details>

<details>
<summary><code>bad-input</code> → 400 with CORS headers</summary>

```json
{
    "version": "2.0",
    "routeKey": "GET /getData",
    "rawPath": "/getData",
    "rawQueryString": "device_id=abc",
    "headers": { "accept": "*/*" },
    "queryStringParameters": { "device_id": "abc" },
    "requestContext": { "apiId": "<api-id>", "http": { "method": "GET", "path": "/getData", "protocol": "HTTP/1.1", "sourceIp": "1.1.1.1", "userAgent": "curl/8.4.0" }, "routeKey": "GET /getData", "stage": "$default" },
    "isBase64Encoded": false
}
```

</details>

<details>
<summary><code>devices</code> → 200, the public device list</summary>

```json
{
    "version": "2.0",
    "routeKey": "GET /getDevices",
    "rawPath": "/getDevices",
    "rawQueryString": "",
    "headers": { "accept": "*/*" },
    "queryStringParameters": null,
    "requestContext": { "apiId": "<api-id>", "http": { "method": "GET", "path": "/getDevices", "protocol": "HTTP/1.1", "sourceIp": "1.1.1.1", "userAgent": "curl/8.4.0" }, "routeKey": "GET /getDevices", "stage": "$default" },
    "isBase64Encoded": false
}
```

</details>

On `wide-range` the console shows base64 gibberish — that is the gzip working,
not a failure. Check **Duration** < 30,000 ms and **Max memory used** < 1024 MB.

Then verify over HTTP, where browsers decompress automatically:

```text
https://<api-id>.execute-api.us-east-1.amazonaws.com/getData?device_id=8&start_time=2023-01-01&end_time=2026-07-22
```

---

# API

Two routes, one Lambda.

## `GET /getDevices`

The public device list — which `device_id` values `/getData` will accept. Takes
no parameters.

```json
[
    {
        "id": 1,
        "generated_id": 8,
        "location": "V. Sargsyan",
        "location_en": "V. Sargsyan",
        "location_hy": "Վ․ Սարգսյան",
        "region": "Yerevan",
        "region_en": "Yerevan",
        "region_hy": "Երևան",
        "country": "Armenia",
        "country_en": "Armenia",
        "country_hy": "Հայաստան",
        "latitude": "40.185285",
        "longitude": "44.560020",
        "LTR390": "valid",
        "BME280": "valid",
        "PMS5003": "valid",
        "Wind": "valid",
        "Rainfall": "valid",
        "Status": "online",
        "last_updated": "2026-07-27T12:54:17.510741+04:00",
        "created_at": "2023-11-16T16:32:00+04:00",
        "issues": []
    }
]
```

Pass `generated_id` to `/getData` as `device_id`.

Unlike `/getData`, this data does **not** come from RDS — there is no device
registry in the database. The Lambda fetches it from the Django backend
(`DEVICES_URL`) using `BOT_SHARED_SECRET`, and copies out the fields above.

> [!IMPORTANT]
> The field list in `DEVICE_FIELDS` is an **allowlist**, not a blocklist. The
> Django response also carries `owner`, `owner_email`, `owner_is_admin`,
> `visibility` and `request_origin`, none of which belong on a public endpoint.
> Adding a field to the Django model must never publish it here automatically —
> keep this an allowlist.

Only devices with public visibility are returned; the backend applies that
filter, and also excludes devices with no data.

Responses are UTF-8 with `Content-Type: application/json; charset=utf-8`, so
Armenian text arrives readable rather than as `\uXXXX` escapes. Both forms are
valid JSON and parse identically, but the escaped form is unreadable in curl and
about twice the bytes.

| Code | Meaning                                          |
| :--- | :----------------------------------------------- |
| 200  | Success                                          |
| 502  | The Django backend is unreachable or refused     |
| 500  | `BOT_SHARED_SECRET` unset; details in CloudWatch |

## `GET /getData`

| Parameter    | Required          | Format                                   |
| :----------- | :---------------- | :--------------------------------------- |
| `device_id`  | yes               | integer                                  |
| `start_time` | with `end_time`   | `YYYY-MM-DD`                             |
| `end_time`   | with `start_time` | `YYYY-MM-DD`, inclusive of the whole day |

Omitting both times returns the 24 hours before the newest reading in that
device's table.

```json
{
    "keys": ["id", "timestamp", "uv", "lux", "temperature", "pressure", "humidity", "pm1", "pm2_5", "pm10", "wind speed", "rain", "wind direction"],
    "data": [[86245, "2026-07-21 17:30:00", 5, 52428, 33.01, 866, 31, 4, 4, 4, 1.47, 0, "NE"]]
}
```

`keys[i]` labels `data[…][i]`. Rows ascend by timestamp.

| Code | Meaning                             |
| :--- | :---------------------------------- |
| 200  | Success, possibly gzipped           |
| 400  | Bad parameters                      |
| 413  | Range too large — see below         |
| 500  | Server error; details in CloudWatch |

`/getData` never calls the Django backend, so it is unaffected if the backend
is down.

---

# Compression and `--compressed`

Lambda caps a response at 6,291,556 bytes. Bodies over 5 MB are gzipped, which
roughly doubles how much fits in one response.

Compression triggers on **response size, not the `Accept-Encoding` header**.
curl does not send that header by default, so negotiating on it would leave the
most common curl request uncompressed and over the cap.

| Client | Behaviour |
| :--- | :--- |
| Browser, `fetch()` | Decompresses automatically. **No frontend change needed.** |
| Python `requests` | Decompresses automatically |
| `curl --compressed` | Decompresses |
| `curl` (bare) | Prints raw gzip **binary** to the terminal |

So for any range that might be large, use `--compressed`:

```bash
curl -s --compressed "$INVOKE_URL/getData?device_id=8&start_time=2023-01-01&end_time=2026-07-22"
```

Without it, curl still receives the full response — it just does not decode it.
To decode after the fact:

```bash
curl -s "$INVOKE_URL/getData?device_id=8" | gunzip
```

---

# Limit: when a range is too large

Even gzipped, a response has a ceiling. It is not a fixed row count — it depends
on how well the readings compress. Measured on a full response envelope:

| Data | Max rows in one response | ≈ years at 15-min readings |
| :--- | ---: | ---: |
| Clean 2-decimal values | 172,435 | 4.92 |
| Noisy, high-precision values | 119,264 | 3.40 |

**Nothing is silently truncated.** Past the ceiling the request is refused with
`413` and the response is empty of data:

```json
{ "error": "Response too large even compressed. Request a narrower date range." }
```

A separate `413` fires first if the range holds more than 300,000 readings,
which stops the function running out of memory before it fetches anything:

```json
{ "error": "Range holds more than 300000 readings. Request a narrower date range." }
```

### Working around it

Split the request into date chunks and concatenate `data` client-side. `keys` is
identical in every response, and rows ascend by timestamp, so chunks joined in
date order need no re-sorting.

Aim for **≤100,000 rows per request**:

| Reading interval | Rows per year | Safe chunk |
| :--- | ---: | :--- |
| 1 min | 525,600 | ~2 months |
| 5 min | 105,120 | ~11 months |
| 10 min | 52,560 | ~1.5 years |
| 15 min | 35,040 | ~2.5 years |
| 30 min | 17,520 | ~5 years |
| 60 min | 8,760 | ~10 years |

```bash
for year in 2021 2022 2023 2024 2025 2026; do
  curl -s --compressed "$INVOKE_URL/getData?device_id=8&start_time=$year-01-01&end_time=$year-12-31" \
    -o "device8_$year.json"
done
```

If a single device ever needs more than this in one call, the fix is streaming
the response from S3 rather than returning it inline — a design change, not a
tuning knob.

---

# Local testing

Runs the handler against a local PostgreSQL seeded with the `data_to_rds`
schema. Never touches RDS or production credentials.

```bash
createdb climatenet_test
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python local_test.py
```

First run seeds ~172k rows; later runs top up. To reseed:

```bash
psql -d climatenet_test -c 'DROP TABLE device8, device999'
```

20 tests cover the payload cap, gzip round-trip, row ordering, the default
window, empty tables, input validation and malformed events.

The `/getDevices` tests stub the HTTP call, so they need no network. The stub
payload deliberately includes `owner_email` and the other private fields, and
`test_devices_never_leaks_private_fields` asserts they never reach the response
body — that is the one to keep green if you touch `DEVICE_FIELDS`.

Against the real database:

```bash
DB_HOST=... DB_USER=... DB_PASSWORD=... DB_NAME=... ./venv/bin/python main.py
```

---

# Rollback

Snapshot first with **Actions ▾ → Publish new version** (freezes code _and_
config). Restore **code and runtime together** — the zip's `psycopg2` binary is
built for one Python version, so reverting the runtime alone breaks the import.

> [!WARNING]
> Reverting to `python3.9` is possible only until **March 3, 2027**.

---

# Troubleshooting

| Symptom                               | Fix                                                                |
| :------------------------------------ | :----------------------------------------------------------------- |
| `No module named 'psycopg2._psycopg'` | Rebuild with `install.sh`, matching `PLATFORM` to the architecture |
| Every request times out at 30 s       | Match VPC, subnets and security groups to RDS                      |
| `Missing environment variable(s): …`  | Step 4                                                             |
| 502, browser reports CORS error       | Raise memory to 1024 MB; real error is in CloudWatch               |
| Console shows base64 gibberish        | Expected — response was gzipped                                    |
| curl prints binary                    | Add `--compressed`                                                 |
| `/getDevices` returns 502             | Backend down, or `BOT_SHARED_SECRET` does not match Django's. Real cause in CloudWatch |
| `/getDevices` returns 500             | `BOT_SHARED_SECRET` not set on the function                        |
| `/getDevices` returns readings        | Path mismatch — the handler matches the last segment, `getDevices` |

**Known limitation:** CORS headers are attached to every response the function
returns, but not to ones API Gateway generates itself (502, 504, 429). Those
reach the browser without CORS headers. Only configuring CORS on the HTTP API
fixes it — and that makes API Gateway override the function's headers.
