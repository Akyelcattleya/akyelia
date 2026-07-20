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

# Pre-cache OmniRoute globally (install au build, pas au run)
RUN npm install -g omniroute@latest

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for persistence
RUN mkdir -p /data

# Port for AkyelIA (Render attribue dynamiquement)
ENV PORT=10000
ENV DB_PATH=/data/akyelia.db
ENV API_KEYS_FILE=/data/api_keys.json
ENV OMNIROUTE_URL=http://localhost:20128/v1

EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:$PORT/')" || exit 1

# Start OmniRoute en arrière-plan puis AkyelIA
CMD ["sh", "-c", "\
    npx omniroute serve --port 20128 --daemon 2>/dev/null & \
    echo '[OK] OmniRoute demarre sur localhost:20128'; \
    sleep 3; \
    python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000} --workers 2 --timeout-keep-alive 120 --forwarded-allow-ips '*' \
"]
