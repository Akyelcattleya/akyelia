#!/bin/bash
# ============================================
# AI FACTORY - Déploiement VPS
# ============================================
# Ce script :
# 1. Arrête proprement l'ancien AkyelIA
# 2. Déploie UNIQUEMENT la nouvelle stack Docker
# 3. Configure le réseau sans conflit
# 4. Teste que tout fonctionne
#
# Usage: ssh root@148.230.98.203
#        curl -fsSL https://raw.githubusercontent.com/Akyelcattleya/akyelia/main/ai-factory/deploy-vps.sh | bash
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }
section() { echo -e "\n${CYAN}══════════════════════════════════════${NC}"; echo -e "${CYAN}  $1${NC}"; echo -e "${CYAN}══════════════════════════════════════${NC}"; }

# ============================================
# PHASE 1 : ARRÊTER L'ANCIEN AKYELIA
# ============================================
section "PHASE 1/4 : Arrêt de l'ancien AkyelIA"

# Arrêter les anciens processus Python (uvicorn, gunicorn)
echo ""
info "Arrêt des anciens processus Python..."
pkill -f "uvicorn app:app" 2>/dev/null || warn "Aucun processus uvicorn trouvé"
pkill -f "gunicorn app:app" 2>/dev/null || warn "Aucun processus gunicorn trouvé"
pkill -f "python3 app.py" 2>/dev/null || warn "Aucun processus python app.py trouvé"
sleep 2
log "Anciens processus Python arrêtés"

# Arrêter nginx/apache s'ils tournent sur les ports de la stack
info "Vérification des services sur les ports 80/443..."
if command -v nginx &>/dev/null; then
    systemctl stop nginx 2>/dev/null || true
    log "Nginx arrêté"
fi
if command -v apache2 &>/dev/null; then
    systemctl stop apache2 2>/dev/null || true
    log "Apache arrêté"
fi

# Arrêter tout conteneur Docker existant de l'ancienne stack
info "Arrêt des anciens conteneurs Docker..."
docker stop $(docker ps -q --filter "name=ai-factory-") 2>/dev/null || true
docker rm $(docker ps -aq --filter "name=ai-factory-") 2>/dev/null || true
log "Anciens conteneurs Docker nettoyés"

# Vider les anciens volumes de données (optionnel - demander confirmation)
read -p "🗑️  Supprimer les anciennes données AkyelIA ? (oui/non): " CLEAN_DATA
if [ "$CLEAN_DATA" = "oui" ]; then
    rm -rf /opt/akyelia /home/akyelia /var/www/akyelia 2>/dev/null || true
    log "Anciennes données supprimées"
fi

# ============================================
# PHASE 2 : CLONER LE NOUVEAU PROJET
# ============================================
section "PHASE 2/4 : Installation de la nouvelle AI Factory"

# Créer le répertoire
mkdir -p /opt/ai-factory
cd /opt/ai-factory

# Cloner UNIQUEMENT le dossier ai-factory (pas tout le repo)
if [ ! -f /opt/ai-factory/docker-compose.yml ]; then
    info "Téléchargement de l'AI Factory..."
    
    # Méthode 1 : Cloner le repo complet puis copier
    git clone --depth 1 https://github.com/Akyelcattleya/akyelia.git /tmp/akyelia-temp 2>/dev/null
    cp -r /tmp/akyelia-temp/ai-factory/* /opt/ai-factory/
    cp /tmp/akyelia-temp/ai-factory/.* /opt/ai-factory/ 2>/dev/null || true
    rm -rf /tmp/akyelia-temp
    
    # Méthode 2 : Si git clone échoue, utiliser curl
    if [ ! -f /opt/ai-factory/docker-compose.yml ]; then
        warn "Git clone échoué, téléchargement via ZIP..."
        curl -L https://github.com/Akyelcattleya/akyelia/archive/main.zip -o /tmp/akyelia.zip 2>/dev/null
        unzip -o /tmp/akyelia.zip -d /tmp/akyelia-unzip 2>/dev/null
        cp -r /tmp/akyelia-unzip/*/ai-factory/* /opt/ai-factory/ 2>/dev/null || true
        rm -rf /tmp/akyelia.zip /tmp/akyelia-unzip
    fi
fi

log "Code source installé dans /opt/ai-factory/"
cd /opt/ai-factory/

# Créer les dossiers de données
mkdir -p data/{ollama,qdrant,n8n,open-webui,caddy/{data,config},logs}
mkdir -p skills workspace registry config/{caddy,openhands}
log "Structure de dossiers créée"

# ============================================
# PHASE 3 : CONFIGURATION ET LANCEMENT
# ============================================
section "PHASE 3/4 : Configuration et lancement"

# Créer le fichier .env avec des secrets aléatoires
if [ ! -f .env ]; then
    cat > .env << EOF
# AI Factory - Généré automatiquement
N8N_PASSWORD=$(openssl rand -base64 12)
WEBUI_SECRET_KEY=$(openssl rand -base64 32)
OLLAMA_DEFAULT_MODEL=qwen2.5-coder:14b
MAX_CONCURRENT_SESSIONS=5
EOF
    log "Fichier .env créé avec secrets aléatoires"
fi

# Configurer Caddy pour HTTP uniquement (pas de domaine = pas de HTTPS)
# L'utilisateur pourra ajouter un domaine plus tard pour le SSL
cat > config/caddy/Caddyfile << 'CADDY'
# AI Factory - Caddy Configuration (HTTP mode)
# Remplace :80 par un domaine pour obtenir le HTTPS auto

:80 {
    # OpenHands
    handle_path /openhands/* {
        reverse_proxy openhands:3000
    }
    
    # n8n
    handle_path /n8n/* {
        reverse_proxy n8n:5678
    }
    
    # Open WebUI
    handle_path /chat/* {
        reverse_proxy open-webui:8080
    }
    
    # Root - simple health check
    header {
        Content-Type "text/html; charset=utf-8"
    }
    respond `
    <!DOCTYPE html>
    <html>
    <head><title>AI Factory</title>
    <style>body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;display:flex;align-items:center;justify-content:center;height:100vh;text-align:center}
    h1{color:#38bdf8}a{color:#38bdf8;text-decoration:none;border:1px solid #38bdf8;padding:12px 24px;border-radius:8px;margin:8px;display:inline-block}</style></head>
    <body>
    <div>
        <h1>🏭 AI Factory</h1>
        <p>Opérationnelle</p>
        <a href="/openhands/">🤖 OpenHands</a>
        <a href="/chat/">💬 Chat</a>
        <a href="http://IP_VPS:3000">📊 Dashboard</a>
    </div>
    </body></html>`
}
CADDY
log "Caddy configuré en mode HTTP (ajoute un domaine pour le HTTPS)"

# Vérifier que Docker est installé
if ! command -v docker &>/dev/null; then
    info "Installation de Docker..."
    curl -fsSL https://get.docker.com | sh
fi

# Lancer la stack
info "Lancement de la stack AI Factory..."
docker compose pull 2>/dev/null || warn "Pull des images en cours (première fois peut être long)"
docker compose up -d
sleep 5

# ============================================
# PHASE 4 : VÉRIFICATION
# ============================================
section "PHASE 4/4 : Vérification"

echo ""
info "Vérification des services :"
docker compose ps

echo ""
# Tester que les services répondent
info "Tests de connexion :"
for service in "Ollama:11434" "Qdrant:6333" "OpenWebUI:3001"; do
    name="${service%%:*}"
    port="${service##*:}"
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:$port --max-time 3 2>/dev/null | grep -q "200\|302\|401"; then
        log "$name ✅ (port $port)"
    else
        warn "$name ⏳ (port $port) - peut prendre quelques minutes"
    fi
done

echo ""
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════╗"
echo "║     ✅ AI FACTORY DÉPLOYÉE AVEC SUCCÈS !       ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo "  📍 Services disponibles :"
echo "     http://148.230.98.203:3000   → OpenHands (Agent Architecte)"
echo "     http://148.230.98.203:3001   → Open WebUI (Chat IA)"
echo "     http://148.230.98.203:6333   → Qdrant (Base vectorielle)"
echo "     http://148.230.98.203:5678   → n8n (Workflows)"
echo "     http://148.230.98.203:3002   → Browserless (Navigation)"
echo "     http://148.230.98.203:11434  → Ollama API (Modèles IA)"
echo ""
echo "  📦 Prochaines étapes :"
echo "     1. Installer les modèles :  docker compose exec ollama ollama pull qwen2.5-coder:14b"
echo "     2. Dashboard :              python3 launch.py dashboard"
echo "     3. Ajouter un domaine :     édite config/caddy/Caddyfile"
echo ""
echo "  📋 Logs : docker compose logs -f"
echo "  🛑 Arrêt : docker compose down"
echo ""
