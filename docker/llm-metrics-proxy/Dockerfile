FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY docker/llm-metrics-proxy/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY llm_usage_telemetry /app/llm_usage_telemetry
COPY scripts/model_usage_report.py /app/scripts/model_usage_report.py

EXPOSE 8080

CMD ["uvicorn", "llm_usage_telemetry.app:app", "--host", "0.0.0.0", "--port", "8080"]
