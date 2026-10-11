FROM python:3.11-slim

WORKDIR /app

# Install build dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY requirements.txt .

# Install dependencies and download cmudict data
RUN pip install --no-cache-dir -r requirements.txt && \
    python -c "import cmudict; cmudict.dict()"

# Copy application files
COPY app/ ./app/

# Expose default port
EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
