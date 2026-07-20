#!/bin/bash
# ============================================
# AkyelIA - Script de démarrage (Production)
# ============================================
# Utilisation: ./start.sh
# ============================================

set -e

echo "======================================"
echo "  AkyelIA - Assistant Multi-LLM"
echo "======================================"

# Vérifier les dépendances
if ! command -v python3 &> /dev/null; then
    echo "[ERREUR] Python 3 n'est pas installé"
    exit 1
fi

# Installer les dépendances si nécessaire
if [ ! -d "venv" ]; then
    echo "[INFO] Création de l'environnement virtuel..."
    python3 -m venv venv
fi
source venv/bin/activate

echo "[INFO] Installation des dépendances..."
pip install -q -r requirements.txt

# Créer les dossiers de données
mkdir -p data

# Démarrer le serveur
echo "[OK] Démarrage d'AkyelIA sur http://0.0.0.0:${PORT:-7777}"
echo "[INFO] Providers: DeepSeek, OpenAI, Claude, Gemini, Groq, Kimi, Mistral, Perplexity, xAI, OpenRouter, Together, Ollama"
echo ""

gunicorn app:app \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT:-7777} \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
