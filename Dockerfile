FROM python:3.11-slim

WORKDIR /app

# Install build dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install locked dependencies (without test tools) and download cmudict data
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev && \
    .venv/bin/python -c "import cmudict; cmudict.dict()"

# Copy application files
COPY app/ ./app/

# Expose default port
EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
