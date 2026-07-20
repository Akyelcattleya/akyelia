#!/bin/bash
# =============================================
# Akyel AI + OmniRoute - Startup Script
# Lance les deux services automatiquement
# Utilisation : bash start_all.sh
# =============================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════════════╗"
echo "║     Akyel AI - Smart Multi-LLM Assistant     ║"
echo "║     demarrage des services...                ║"
echo "╚══════════════════════════════════════════════╝"

# Configuration
OMNIROUTE_PORT=20128
AKYEL_PORT=${PORT:-7777}

# 1. Kill any existing processes
echo ""
echo " [1/3] Arret des anciens processus..."
pkill -f "omniroute serve" 2>/dev/null
pkill -f "python app.py" 2>/dev/null
pkill -f "uvicorn" 2>/dev/null
sleep 2
echo "   ✓ Anciens processus arretes"

# 2. Start OmniRoute (smart router for 99+ LLMs)
echo ""
echo " [2/3] Demarrage d'OmniRoute (routeur intelligent)..."
npx omniroute serve --port $OMNIROUTE_PORT --daemon 2>/dev/null
if [ $? -eq 0 ]; then
    echo "   ✓ OmniRoute pret sur http://localhost:$OMNIROUTE_PORT"
    echo "   ✓ Dashboard : http://localhost:$OMNIROUTE_PORT/dashboard"
else
    echo "   ⚠ OmniRoute deja en cours ou erreur"
    # Verifier s'il tourne deja
    curl -s http://localhost:$OMNIROUTE_PORT/v1/models > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "   ✓ OmniRoute deja en ligne"
    fi
fi
sleep 2

# 3. Start Akyel AI
echo ""
echo " [3/3] Demarrage d'Akyel AI..."
# Clear Python cache
rm -rf __pycache__ 2>/dev/null
python app.py &
sleep 3

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     ✅ TOUT EST PRET !                       ║"
echo "║                                              ║"
echo "║     🌐 Akyel AI  : http://localhost:7777     ║"
echo "║     🌐 OmniRoute : http://localhost:20128     ║"
echo "║                                              ║"
echo "║     ⚡ Smart Routing: ACTIF                  ║"
echo "║     🧠 99+ modeles disponibles               ║"
echo "║                                              ║"
echo "║     Pour arreter : pkill -f 'python app.py'  ║"
echo "╚══════════════════════════════════════════════╝"
