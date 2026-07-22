#!/bin/bash
# ============================================
# ⚡ AI FACTORY — MEGA MISE À JOUR
# Une seule commande pour tout mettre à jour
# ============================================
# Usage: bash <(curl -sL https://raw.githubusercontent.com/Akyelcattleya/akyelia/main/ai-factory/bridge/update-factory.sh)
# ============================================

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
section() { echo -e "\n${CYAN}══════════════════════════════════════${NC}"; echo -e "${CYAN}  $1${NC}"; echo -e "${CYAN}══════════════════════════════════════${NC}"; }

cd /opt/ai-factory

# ============================================
# PHASE 1 : Télécharger les nouveaux fichiers
# ============================================
section "PHASE 1/4 : Téléchargement des nouveaux fichiers"

BASE="https://raw.githubusercontent.com/Akyelcattleya/akyelia/main/ai-factory"
FILES=(
    "bridge/smart-router.py:bridge/smart-router.py"
    "bridge/portal.html:bridge/portal.html"
    "bridge/install-all-models.sh:bridge/install-all-models.sh"
    "config/caddy/Caddyfile:config/caddy/Caddyfile"
    "docker-compose.yml:docker-compose.yml"
)

for file_pair in "${FILES[@]}"; do
    src="${file_pair%%:*}"
    dst="${file_pair##*:}"
    mkdir -p "$(dirname "$dst")"
    echo "  📥 Téléchargement de $dst..."
    curl -sL "$BASE/$src" -o "$dst" && log "$dst mis à jour" || warn "Échec $dst"
done

chmod +x bridge/install-all-models.sh 2>/dev/null || true

# ============================================
# PHASE 2 : Reconstruire et redémarrer le Smart Router
# ============================================
section "PHASE 2/4 : Reconstruction du Smart Router v2.0"

echo "  🏗️  Reconstruction de l'image smart-router..."
docker compose build smart-router 2>&1 | tail -3
echo "  🔄 Redémarrage du smart-router..."
docker compose up -d smart-router --force-recreate 2>&1 | tail -3
log "Smart Router v2.0 déployé sur le port 8765"

# Redémarrer Caddy pour le nouveau portal
echo "  🔄 Redémarrage de Caddy..."
docker compose up -d caddy --force-recreate 2>&1 | tail -3
log "Portail mis à jour sur le port 8080"

# ============================================
# PHASE 3 : Installer TOUS les modèles IA
# ============================================
section "PHASE 3/4 : Installation massive des modèles IA"

# Liste de tous les modèles à installer
ALL_MODELS=(
    "qwen2.5-coder:7b"
    "phi4-mini:3.8b"
    "qwen3.5:4b"
    "deepseek-r1:7b"
    "llama3.2:3b"
    "gemma2:2b"
    "mistral:7b"
    "llava:7b"
    "nomic-embed-text"
    "codegemma:2b"
)

# Vérifier combien de modèles sont déjà installés
echo "  🔍 Vérification des modèles existants..."
ALREADY_INSTALLED=()
TO_INSTALL=()

for model in "${ALL_MODELS[@]}"; do
    if docker compose exec ollama ollama list 2>/dev/null | grep -q "^${model}\b"; then
        ALREADY_INSTALLED+=("$model")
    else
        TO_INSTALL+=("$model")
    fi
done

echo "  ✅ ${#ALREADY_INSTALLED[@]} modèles déjà installés"
echo "  📦 ${#TO_INSTALL[@]} modèles à télécharger"
echo ""

if [ ${#TO_INSTALL[@]} -gt 0 ]; then
    echo "  🚀 Lancement des téléchargements en parallèle..."
    
    # Lancer TOUS les téléchargements d'un coup (Ollama gère la file d'attente)
    for model in "${TO_INSTALL[@]}"; do
        echo "  ⏳ Téléchargement de $model..."
        docker compose exec -d ollama ollama pull "$model" 2>/dev/null || true
    done
    
    echo ""
    echo "  ⏳ Téléchargements en cours (5-20 min selon le nombre de modèles)..."
    echo "  📊 Vérifie avec : docker compose exec ollama ollama list"
else
    echo "  ✅ Tous les modèles sont déjà installés !"
fi

# ============================================
# PHASE 4 : Vérification finale
# ============================================
section "PHASE 4/4 : Vérification finale"

echo "  📊 Statut des services :"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null

echo ""
echo "  📦 Modèles installés :"
docker compose exec ollama ollama list 2>/dev/null || echo "  (téléchargement en cours...)"

echo ""
echo "═══════════════════════════════════════════════════"
echo -e "${GREEN}  ✅ AI FACTORY MISE À JOUR AVEC SUCCÈS !${NC}"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  📍 Accès :"
echo "     http://148.230.98.203:8080  → 🏠 Portail (dashboard onglets)"
echo "     http://148.230.98.203:8765  → 💬 Smart Chat (routage auto)"
echo "     http://148.230.98.203:3000  → 🤖 OpenHands"
echo "     http://148.230.98.203:3001  → 💬 Open WebUI"
echo "     http://148.230.98.203:5678  → ⚡ n8n"
echo ""

# Vérifier que le Smart Router répond
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8765/ --max-time 5 2>/dev/null | grep -q "200"; then
    log "Smart Router ✅ (port 8765)"
else
    warn "Smart Router ⏳ - encore en démarrage..."
fi

# Vérifier le portail
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ --max-time 5 2>/dev/null | grep -q "200"; then
    log "Portail ✅ (port 8080)"
else
    warn "Portail ⏳ - vérifie dans 10s..."
fi

echo ""
echo -e "${GREEN}  🚀 Prêt à coder !${NC}"
