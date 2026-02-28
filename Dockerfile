FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files first for layer caching
COPY pyproject.toml ./
COPY uv.lock* ./

# Install dependencies
RUN uv sync --no-dev

# Copy application code
COPY agent/ ./agent/
COPY api/ ./api/
COPY static/ ./static/

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
