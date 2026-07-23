#!/bin/bash
set -e

# Builds lambda_function.zip for upload to AWS Lambda.
#
# psycopg2-binary ships a compiled extension, so the wheel has to match the
# Lambda runtime rather than the machine running this script. --platform and
# --python-version make pip download the right wheel instead of building one,
# which is why this works on macOS without Docker.

PYTHON_VERSION=${PYTHON_VERSION:-3.13}
# Set to manylinux2014_aarch64 if the function's architecture is arm64.
PLATFORM=${PLATFORM:-manylinux2014_x86_64}
# Invoked as `python3 -m pip` because a bare `pip` is not on PATH on every
# machine. Any Python 3 works here: pip only downloads a prebuilt wheel for the
# target runtime, it does not build or run anything.
PYTHON=${PYTHON:-python3}

if ! command -v "$PYTHON" &>/dev/null; then
    echo "$PYTHON not found. Set PYTHON=/path/to/python3 and retry."
    exit 1
fi

rm -rf package lambda_function.zip
mkdir package

"$PYTHON" -m pip install \
    --platform "$PLATFORM" \
    --python-version "$PYTHON_VERSION" \
    --implementation cp \
    --only-binary=:all: \
    --target package \
    -r requirements.txt

cp lambda_function.py package/
cd package
zip -qr9 ../lambda_function.zip .
cd ..
rm -rf package

echo "Built lambda_function.zip for python${PYTHON_VERSION} / ${PLATFORM}"
unzip -l lambda_function.zip | grep -E "_psycopg|lambda_function.py"
