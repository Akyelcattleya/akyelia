# ============================================
# Akyel AI - Dockerfile (Python seulement)
# ============================================
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl git \
    && rm -rf /var/lib/apt/lists/*

# Copier les dépendances Python pour le cache Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le code
COPY . .

# Dossier persistant
RUN mkdir -p /data

ENV PORT=10000
ENV DB_PATH=/data/akyelia.db
ENV API_KEYS_FILE=/data/api_keys.json

EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:$PORT/')" || exit 1

# Lancement direct de l'app Python
CMD python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000} --workers 2 --timeout-keep-alive 120 --forwarded-allow-ips '*'
