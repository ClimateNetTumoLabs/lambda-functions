#!/bin/bash
set -e  # Exit on any error

# Check if Python 3 is installed
if ! command -v python3 &>/dev/null; then
    echo "Python3 is not installed. Exiting."
    exit 1
fi

# Create and activate the virtual environment
python3 -m venv venv
source venv/bin/activate

# Get the first Python version directory inside venv
PYTHON_VERSION=$(ls ./venv/lib | grep python | head -n 1)
export PYTHON_VERSION

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Deactivate virtual environment
deactivate

# Package the Lambda function
cd venv/lib/"$PYTHON_VERSION"/site-packages || exit
zip -r9 "${OLDPWD}"/lambda_function.zip .
cd "$OLDPWD" || exit
zip -g lambda_function.zip lambda_function.py
zip -g lambda_function.zip config.py

