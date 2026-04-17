FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# Default internal port (override with BRIDGE_PORT env var)
EXPOSE 5001

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${BRIDGE_PORT:-5001} --workers 2 --timeout 30 app:app"]
