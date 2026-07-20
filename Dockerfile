# ============================================
# Akyel AI - Dockerfile (Hugging Face Spaces / Docker)
# ============================================
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY freebuff/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY freebuff/ .

# Create data directory for persistence
RUN mkdir -p /data

# Hugging Face Spaces utilise le port 7860
ENV PORT=7860
ENV DB_PATH=/data/akyelia.db
ENV API_KEYS_FILE=/data/api_keys.json

EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/')" || exit 1

# Start server
CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860} --workers 2 --timeout-keep-alive 120 --forwarded-allow-ips '*'"]
