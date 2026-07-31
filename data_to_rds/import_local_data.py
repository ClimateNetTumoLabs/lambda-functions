#!/usr/bin/env python3
"""
Emergency direct import of a station's local_data.json into RDS.

Bypasses MQTT, IoT Core and the Lambda entirely - for when a buffer file has been
rescued off a device by hand and has to be loaded straight into the database.

It reuses the Lambda's own add_message(), so duplicate-skipping, column handling
and value formatting are identical to the normal path. That makes it safe to run
more than once: timestamps already in the table are skipped, never re-inserted.
It is also resumable - each batch commits, so an interrupted run can simply be
started again.

Usage:
    python3 import_local_data.py <device> <path-to-json> [--dry-run]

Example:
    python3 import_local_data.py device54 ~/Desktop/local_data.json --dry-run
    python3 import_local_data.py device54 ~/Desktop/local_data.json

Needs psycopg2 and a filled-in config.py in this directory:
    pip3 install psycopg2-binary
"""

import json
import sys

from lambda_function import add_message, connect_to_db, create_table, existing_times

BATCH = 500


def load_records(path):
    with open(path) as f:
        records = json.load(f)

    if not isinstance(records, list):
        sys.exit(f"{path} is not a JSON list of records")

    missing = sum(1 for r in records if not r.get("time"))
    if missing:
        sys.exit(f"{missing} records have no 'time' - refusing to import, they cannot be deduplicated")

    return records


def dry_run(device, records, connection):
    """Report what would happen without writing anything."""
    already = set()

    with connection.cursor() as cursor:
        for i in range(0, len(records), BATCH):
            times = [r["time"] for r in records[i:i + BATCH]]
            already |= existing_times(device, times, cursor)

    print(f"records in file:       {len(records)}")
    print(f"already in {device}:   {len(already)}")
    print(f"would be inserted:     {len(records) - len(already)}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2:
        sys.exit(__doc__)

    device, path = args
    records = load_records(path)
    print(f"Loaded {len(records)} records from {path}")

    connection = connect_to_db()

    try:
        create_table(device=device, connection=connection)

        if "--dry-run" in sys.argv:
            dry_run(device, records, connection)
            return

        inserted = 0
        for i in range(0, len(records), BATCH):
            inserted += add_message(device=device, data=records[i:i + BATCH], connection=connection)
            done = min(i + BATCH, len(records))
            print(f"  {done}/{len(records)} processed, {inserted} inserted")

        print(f"\nDone. {inserted} new rows, {len(records) - inserted} already present.")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
