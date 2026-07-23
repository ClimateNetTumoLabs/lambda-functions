# ClimateNet Lambda Functions

AWS Lambda functions supporting the ClimateNet backend and IoT telemetry
network: data ingestion from weather stations, the public data API, device
certificate provisioning, transactional email, and Cognito sign-up triggers.

Each directory is one independently deployed Lambda.

---

## Functions

| Directory                                                 | Trigger                      | Target         | Purpose                                                                      |
| :-------------------------------------------------------- | :--------------------------- | :------------- | :--------------------------------------------------------------------------- |
| [`climate_net_api`](climate_net_api/)                     | API Gateway — `GET /getData` | RDS PostgreSQL | Serves historical and recent climate readings to the frontend                |
| [`data_to_rds`](data_to_rds/)                             | AWS IoT Core (MQTT)          | RDS PostgreSQL | Stores sensor payloads from the station fleet                                |
| [`fromEspToRDS`](fromEspToRDS/)                           | API Gateway (HTTP POST)      | RDS PostgreSQL | Same, for the portable ESP-based air monitors                                |
| [`certificate_auto_gen`](certificate_auto_gen/)           | API Gateway (HTTP)           | AWS IoT Core   | Provisions IoT Things, creates certificates and keys, packages them as a ZIP |
| [`mail_service`](mail_service/)                           | API Gateway (HTTP)           | AWS SES v2     | Sends branded HTML email, optionally with attachments                        |
| [`cognito-custom-message`](cognito-custom-message/)       | Cognito — Custom Message     | Cognito        | Replaces the default verification email with a branded one                   |
| [`cognito-post-confirmation`](cognito-post-confirmation/) | Cognito — Post Confirmation  | Django backend | Notifies Django once a user confirms their email                             |

### How they fit together

```text
Weather stations ──MQTT──►  IoT Core  ──►  data_to_rds  ──┐
Portable monitors ──HTTP──────────────►  fromEspToRDS  ──┤
                                                          ▼
                                                  RDS PostgreSQL
                                                   device8, device12, …
                                                          │
Frontend  ──GET /getData──►  API Gateway  ──►  climate_net_api
```

```text
                        ┌──►  certificate_auto_gen  ──►  IoT Core (Thing + certs)
Django backend  ────────┤
                        └──►  mail_service  ──►  SES  ──►  user's inbox

User signs up  ──►  Cognito  ──┬──►  cognito-custom-message   (verification email)
                               └──►  cognito-post-confirmation (webhook to Django)
```

---

## Configuration

Two conventions are in use. **Environment variables are preferred for new work** —
they keep credentials out of the deployment package.

### Environment variables

| Function                    | Variables                                                                 |
| :-------------------------- | :------------------------------------------------------------------------ |
| `climate_net_api`           | `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_SSLMODE` _(optional)_ |
| `cognito-custom-message`    | `REDIRECT_URL`                                                            |
| `cognito-post-confirmation` | `DJANGO_WEBHOOK_URL`, `WEBHOOK_SHARED_SECRET`                             |

Set under **Lambda → Configuration → Environment variables**.

### `config.py`

The remaining functions import a local `config.py` that ships inside the zip.
Copy the template and fill it in — it is gitignored, so it never reaches the
repository:

```bash
cp data_to_rds/config.py.template data_to_rds/config.py
cp certificate_auto_gen/config_template.py certificate_auto_gen/config.py
cp mail_service/config_template.py mail_service/config.py
```

| Function               | Keys                                                                |
| :--------------------- | :------------------------------------------------------------------ |
| `data_to_rds`          | `HOST`, `USER`, `PASSWORD`, `DB_NAME`, `COLUMNS`                    |
| `fromEspToRDS`         | Same as `data_to_rds` — no template in-tree, reuse that one         |
| `certificate_auto_gen` | `ACCESS_KEY`, `SECRET_KEY`, `REGION`, `MQTT_ENDPOINT`, `MQTT_TOPIC` |
| `mail_service`         | `ACCESS_KEY`, `SECRET_KEY`, `REGION`, `SENDER`                      |

---

## Deploying

Functions with a `requirements.txt` need their dependencies packaged into the
zip. Those without one use only the standard library or the boto3 already
present in the Lambda runtime, so the handler file can be uploaded directly.

| Function                    | Dependencies              | Packaging                 | Targets             |
| :-------------------------- | :------------------------ | :------------------------ | :------------------ |
| `climate_net_api`           | `psycopg2-binary==2.9.11` | `./install.sh`            | Python 3.13, x86_64 |
| `data_to_rds`               | `psycopg2-binary==2.9.9`  | `./install.sh`            | Python 3.10, x86_64 |
| `fromEspToRDS`              | `psycopg2-binary==2.9.11` | `./install.sh`            | Python 3.13, x86_64 |
| `certificate_auto_gen`      | boto3 (in runtime)        | Upload the files directly | —                   |
| `mail_service`              | boto3 (in runtime)        | Upload the files directly | —                   |
| `cognito-custom-message`    | none                      | Upload the file directly  | —                   |
| `cognito-post-confirmation` | none                      | Upload the file directly  | —                   |

> [!IMPORTANT]
> `psycopg2` ships a compiled C extension, so the wheel must match the **Lambda
> runtime**, not the machine building the zip. A plain `pip install` on macOS
> produces a macOS binary and the function fails at import with
> `No module named 'psycopg2._psycopg'`.
>
> All three `install.sh` scripts avoid this by passing `--platform` and
> `--python-version` to pip, so they work on macOS without Docker. **The runtime
> each targets must match the runtime configured on the function** — see the
> table above. Only `climate_net_api/install.sh` makes these overridable
> (`PLATFORM`, `PYTHON_VERSION`); the other two hard-code x86_64.

> [!NOTE]
> `data_to_rds` builds against **Python 3.10**, which AWS deprecates on
> **Oct 31 2026** (function updates blocked from Mar 3 2027). Moving it to 3.13
> means bumping `--python-version` in its `install.sh`, rebuilding, and changing
> the runtime on the function — the zip and the runtime must move together, or
> the `psycopg2` import breaks.

> [!WARNING]
> If API Gateway points at the unqualified function ARN — the default — uploaded
> code is **live immediately**. There is no staging step. To test first, create a
> second function with the same role, VPC and configuration, and attach it to a
> temporary route.

---

## Testing

`climate_net_api`, `cognito-custom-message` and `cognito-post-confirmation` have
runnable local tests that need no AWS resources:

```bash
cd climate_net_api
createdb climatenet_test
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python local_test.py
```

```bash
cd cognito-post-confirmation && python3 local_test.py
```

`climate_net_api/local_test.py` seeds a local PostgreSQL with the same schema
`data_to_rds` creates, then runs the real handler against it — production
credentials are never involved.

---

## Documentation

Per-function detail lives in the directory READMEs and the wiki:

- **[climate_net_api/README.md](climate_net_api/README.md)** — setup, API contract, response limits, local testing
- **[data_to_rds/README.md](data_to_rds/README.md)** — IoT Core ingestion setup

**[Wiki](https://github.com/ClimateNetTumoLabs/lambda-functions/wiki)**

| Page                                                                                                                     | Covers                                           |
| :----------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------- |
| [ClimateNet Data API](https://github.com/ClimateNetTumoLabs/lambda-functions/wiki/ClimateNet-Data-API)                   | `climate_net_api` — full setup and API reference |
| [Certificate & Mail Automations](https://github.com/ClimateNetTumoLabs/lambda-functions/wiki/Certificate-Automations)    | `certificate_auto_gen` and `mail_service`        |
| [Cognito Authentication](https://github.com/ClimateNetTumoLabs/lambda-functions/wiki/Cognito-Authentication)             | Both Cognito triggers and the sign-up flow       |
| [Creating AWS Lambda Function](https://github.com/ClimateNetTumoLabs/lambda-functions/wiki/Creating-AWS-Lambda-function) | Generic packaging and upload walkthrough         |
| [Creating AWS API Gateway](https://github.com/ClimateNetTumoLabs/lambda-functions/wiki/Creating-AWS-API-Gateway)         | Creating an HTTP API and wiring a route          |

---

## Repository Conventions

- One directory per Lambda; the handler is always `lambda_function.lambda_handler`.
- `config.py`, `venv/`, `lambda_function.zip` and `__pycache__/` are gitignored — secrets and build artefacts stay out of the repository.
- Database tables are one per device, named `deviceN`, created on demand by the ingestion Lambdas.
