# ============================================
# Akyel AI + OmniRoute - Dockerfile
# ============================================
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies + Node.js for OmniRoute
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22.x (required for OmniRoute)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g npm@latest

# Pre-cache OmniRoute globalement (installe au build, disponible au run)
RUN npm install -g omniroute@latest

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
ENV OMNIROUTE_URL=http://localhost:20128/v1

EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:$PORT/')" || exit 1

# Script de demarrage : lance OmniRoute, attend qu'il soit pret, puis lance AkyelIA
CMD ["sh", "-c", "\
    echo '[OK] Demarrage OmniRoute...'; \
    omniroute serve --port 20128 & \
    OMNI_PID=$!; \
    echo '[OK] Attente OmniRoute (PID: '$OMNI_PID')...'; \
    for i in $(seq 1 15); do \
        if curl -s http://localhost:20128/v1/models > /dev/null 2>&1; then \
            echo '[OK] OmniRoute pret !'; \
            break; \
        fi; \
        echo '  Tentative '$i'/15...'; \
        sleep 2; \
    done; \
    echo '[OK] Demarrage AkyelIA...'; \
    python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000} --workers 2 --timeout-keep-alive 120 --forwarded-allow-ips '*' \
"]
