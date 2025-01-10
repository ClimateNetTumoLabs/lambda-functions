
FROM python:3.10

WORKDIR /app

COPY . .

RUN python3 -m venv venv && \
    . venv/bin/activate && \
    pip install --upgrade pip && \
    pip install -r requirements.txt && \
    deactivate && \
    cd venv/lib/$(ls venv/lib | grep python)/site-packages && \
    zip -r9 /app/lambda_function.zip . && \
    cd /app && \
    zip -g lambda_function.zip lambda_function.py config.py


