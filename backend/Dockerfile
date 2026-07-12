# Tradzo Backend — Dockerfile for Fly.io deployment
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Port Fly.io will use (matches fly.toml internal_port)
EXPOSE 8080

# Start uvicorn with the Fly PORT env var
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
