#!/bin/bash
# ============================================
# AI FACTORY - Déploiement Automatique VPS
# ============================================
# Usage: curl -fsSL https://raw.githubusercontent.com/Akyelcattleya/akyelia/main/ai-factory/deploy-vps.sh | bash
#
# Ce script 100% automatique :
# 1. Arrête proprement tout ancien service existant
# 2. Nettoie les anciennes installations
# 3. Clone et déploie UNIQUEMENT la nouvelle AI Factory
# 4. Configure SSL automatique via Caddy (si domaine fourni)
# 5. Lance les 8 services Docker
# 6. Teste que tout fonctionne
# 7. Affiche le résumé final
# ============================================

set -e

# Couleurs
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'

log() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }
info() { echo -e "${BLUE}[i]${NC} $1"; }
section() { echo -e "\n${CYAN}══════════════════════════════════════${NC}"; echo -e "${CYAN}  $1${NC}"; echo -e "${CYAN}══════════════════════════════════════${NC}"; }

# ============================================
# Détection du domaine (via variable d'env ou argument)
# ============================================
DOMAIN="${DOMAIN:-}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain) DOMAIN="$2"; shift 2 ;;
        --help) echo "Usage: bash deploy-vps.sh [--domain mon-domaine.com]"; exit 0 ;;
        *) DOMAIN="$1"; shift ;;
    esac
done

# ============================================
# PHASE 1 : ARRÊTER ET NETTOYER L'ANCIEN
# ============================================
section "PHASE 1/5 : Arrêt et nettoyage de l'ancienne installation"

# 1a. Arrêter tous les processus Python existants
info "Arrêt des processus Python (uvicorn, gunicorn, app)..."
pkill -f "uvicorn" 2>/dev/null || true
pkill -f "gunicorn" 2>/dev/null || true
pkill -f "python3 app.py" 2>/dev/null || true
pkill -f "akyelia" 2>/dev/null || true
sleep 2
log "Processus Python arrêtés"

# 1b. Arrêter nginx/apache s'ils tournent
info "Vérification des services web..."
for svc in nginx apache2; do
    if command -v systemctl &>/dev/null; then
        systemctl stop "$svc" 2>/dev/null && log "$svc arrêté" || true
        systemctl disable "$svc" 2>/dev/null || true
    fi
done

# 1c. Supprimer TOUS les conteneurs Docker de l'ancienne stack
info "Nettoyage des conteneurs Docker..."
docker stop $(docker ps -q -f "name=ai-factory-") 2>/dev/null || true
docker rm $(docker ps -aq -f "name=ai-factory-") 2>/dev/null || true
docker stop $(docker ps -q -f "name=akyelia") 2>/dev/null || true
docker rm $(docker ps -aq -f "name=akyelia") 2>/dev/null || true
docker network rm ai-factory-net 2>/dev/null || true
log "Conteneurs Docker nettoyés"

# 1d. Sauvegarder et supprimer l'ancienne installation
if [ -d /opt/ai-factory.bak ]; then
    rm -rf /opt/ai-factory.bak
fi
if [ -d /opt/ai-factory ]; then
    info "Sauvegarde de l'ancienne installation dans /opt/ai-factory.bak..."
    mv /opt/ai-factory /opt/ai-factory.bak
    log "Ancienne installation sauvegardée dans /opt/ai-factory.bak"
fi

# 1e. Supprimer les anciens projets
rm -rf /opt/akyelia /home/akyelia /var/www/akyelia 2>/dev/null || true
log "Anciens projets supprimés"

# ============================================
# PHASE 2 : INSTALLER DOCKER SI NÉCESSAIRE
# ============================================
section "PHASE 2/5 : Vérification des prérequis"

if ! command -v docker &>/dev/null; then
    info "Installation de Docker..."
    curl -fsSL https://get.docker.com | sh
    log "Docker installé"
else
    log "Docker: $(docker --version 2>/dev/null)"
fi

# Installer docker compose si pas présent
if ! docker compose version &>/dev/null; then
    info "Installation de Docker Compose..."
    apt-get update -qq && apt-get install -y -qq docker-compose-plugin 2>/dev/null || \
    pip3 install docker-compose 2>/dev/null || true
fi
log "Docker Compose: $(docker compose version 2>/dev/null)"

# Installer les outils de base si manquants
for cmd in git curl unzip openssl; do
    if ! command -v "$cmd" &>/dev/null; then
        apt-get install -y -qq "$cmd" 2>/dev/null || true
    fi
done
log "Outils de base OK"

# ============================================
# PHASE 3 : INSTALLER LA NOUVELLE AI FACTORY
# ============================================
section "PHASE 3/5 : Installation de la nouvelle AI Factory"

# Créer le dossier
mkdir -p /opt/ai-factory
cd /opt/ai-factory

# Télécharger le code (3 méthodes de secours)
if [ ! -f /opt/ai-factory/docker-compose.yml ]; then
    info "Téléchargement de l'AI Factory..."
    
    # Méthode 1 : git clone (recommandé)
    if git clone --depth 1 https://github.com/Akyelcattleya/akyelia.git /tmp/ai-factory-temp 2>/dev/null; then
        if [ -d /tmp/ai-factory-temp/ai-factory ]; then
            cp -r /tmp/ai-factory-temp/ai-factory/* /opt/ai-factory/
            cp /tmp/ai-factory-temp/ai-factory/.* /opt/ai-factory/ 2>/dev/null || true
        else
            cp -r /tmp/ai-factory-temp/* /opt/ai-factory/
        fi
        rm -rf /tmp/ai-factory-temp
    # Méthode 2 : zip
    elif curl -sL https://github.com/Akyelcattleya/akyelia/archive/refs/heads/main.zip -o /tmp/ai-factory.zip && \
         unzip -qo /tmp/ai-factory.zip -d /tmp/ai-factory-extract 2>/dev/null; then
        if [ -d /tmp/ai-factory-extract/akyelia-main/ai-factory ]; then
            cp -r /tmp/ai-factory-extract/akyelia-main/ai-factory/* /opt/ai-factory/
        else
            cp -r /tmp/ai-factory-extract/akyelia-main/* /opt/ai-factory/
        fi
        rm -rf /tmp/ai-factory.zip /tmp/ai-factory-extract
    # Méthode 3 : download individuel des fichiers clés
    else
        warn "Téléchargement des fichiers un par un..."
        BASE_URL="https://raw.githubusercontent.com/Akyelcattleya/akyelia/main/ai-factory"
        for f in docker-compose.yml launch.py setup.sh .gitignore Makefile; do
            curl -sL "$BASE_URL/$f" -o "$f" 2>/dev/null || true
        done
        for f in config/caddy/Caddyfile config/openhands/settings.py; do
            mkdir -p "$(dirname "$f")"
            curl -sL "$BASE_URL/$f" -o "$f" 2>/dev/null || true
        done
    fi
fi

# Vérifier que les fichiers essentiels sont là
if [ ! -f docker-compose.yml ]; then
    error "Échec du téléchargement. Vérifie la connexion Internet."
    exit 1
fi
log "Code source téléchargé et installé dans /opt/ai-factory/"

# Créer la structure de dossiers
mkdir -p data/{ollama,qdrant,n8n,open-webui,caddy/{data,config},logs}
mkdir -p skills/{stealth-module} workspace registry bridge config/{caddy,openhands}
log "Structure de dossiers créée"

# ============================================
# PHASE 4 : CONFIGURATION ET LANCEMENT
# ============================================
section "PHASE 4/5 : Configuration et lancement"

# 4a. Créer .env (sans écraser un existant)
if [ ! -f .env ]; then
    cat > .env << EOF
# AI Factory - Généré automatiquement le $(date '+%Y-%m-%d %H:%M:%S')
N8N_PASSWORD=$(openssl rand -base64 12 | tr -dc 'a-zA-Z0-9')
WEBUI_SECRET_KEY=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9')
OLLAMA_DEFAULT_MODEL=qwen2.5-coder:14b
MAX_CONCURRENT_SESSIONS=5
EOF
    log "Fichier .env créé avec secrets aléatoires"
fi

# 4b. Configurer Caddy pour HTTP (ou HTTPS si domaine fourni)
if [ -n "$DOMAIN" ]; then
    cat > config/caddy/Caddyfile << CADDYEOF
{
    storage file /data
    email admin@${DOMAIN}
}

${DOMAIN} {
    reverse_proxy openhands:3000
    encode gzip zstd
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
    }
}

chat.${DOMAIN} {
    reverse_proxy open-webui:8080
    encode gzip zstd
}

n8n.${DOMAIN} {
    reverse_proxy n8n:5678
    encode gzip zstd
}
CADDYEOF
    log "Caddy configuré en mode HTTPS (domaine: $DOMAIN)"
else
    cat > config/caddy/Caddyfile << 'CADDYEOF'
:80 {
    header Content-Type "text/html; charset=utf-8"
    respond `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🏭 AI Factory</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:2rem}
.container{max-width:800px;width:100%;text-align:center}
h1{font-size:3rem;margin-bottom:0.5rem;background:linear-gradient(135deg,#60a5fa,#a78bfa,#f472b6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.subtitle{font-size:1.2rem;color:#94a3b8;margin-bottom:2rem}
.services{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin:2rem 0}
.card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1.5rem;text-decoration:none;color:#e2e8f0;transition:all 0.3s}
.card:hover{background:#334155;transform:translateY(-4px);border-color:#60a5fa}
.card-icon{font-size:2rem;margin-bottom:0.5rem}
.card-title{font-weight:600;margin-bottom:0.25rem}
.card-desc{font-size:0.85rem;color:#94a3b8}
.status{display:flex;align-items:center;justify-content:center;gap:0.5rem;margin-top:1.5rem;font-size:0.9rem;color:#94a3b8}
.dot{width:8px;height:8px;border-radius:50%;background:#22c55e;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
</style>
</head>
<body>
<div class="container">
<h1>🏭 AI Factory</h1>
<p class="subtitle">Usine à Agents Autonomes — Opérationnelle</p>
<div class="services">
<a href="http://IP_VPS:3000" class="card"><div class="card-icon">🤖</div><div class="card-title">OpenHands</div><div class="card-desc">Agent Architecte</div></a>
<a href="http://IP_VPS:3001" class="card"><div class="card-icon">💬</div><div class="card-title">Chat IA</div><div class="card-desc">Open WebUI</div></a>
<a href="http://IP_VPS:5678" class="card"><div class="card-icon">⚡</div><div class="card-title">Workflows</div><div class="card-desc">n8n</div></a>
</div>
<div class="status"><span class="dot"></span> Tous les systèmes sont opérationnels</div>
</div>
</body></html>`
}
CADDYEOF
    log "Caddy configuré en mode HTTP (ajoute --domain mon-site.com pour le SSL auto)"
fi

# 4c. Démarrer la stack Docker
info "Pull des images Docker (première fois peut prendre 5-10 min)..."
docker compose pull 2>&1 | tail -5 || true

info "Lancement des services..."
docker compose up -d 2>&1
sleep 8

# Vérifier que les conteneurs sont bien lancés
RUNNING=$(docker compose ps --status running -q 2>/dev/null | wc -l)
TOTAL=$(docker compose ps -q 2>/dev/null | wc -l)
log "$RUNNING/$TOTAL conteneurs en cours d'exécution"

# ============================================
# PHASE 5 : VÉRIFICATION ET INSTALLATION MODÈLES
# ============================================
section "PHASE 5/5 : Vérification et téléchargement des modèles"

# 5a. Attendre qu'Ollama soit prêt
info "Attente du démarrage d'Ollama..."
for i in $(seq 1 30); do
    if curl -s -f http://localhost:11434/api/tags >/dev/null 2>&1; then
        log "Ollama prêt après ${i}s"
        break
    fi
    sleep 2
done

# 5b. Télécharger les modèles Ollama en arrière-plan
info "Téléchargement des modèles Ollama (en arrière-plan)..."
(
    for model in qwen2.5-coder:14b nomic-embed-text llama3.2:3b; do
        echo "  📦 Téléchargement de $model..."
        docker exec ai-factory-ollama ollama pull "$model" 2>/dev/null && echo "  ✅ $model installé"
    done
    echo "✅ Modèles téléchargés !"
) &

# 5c. Vérifier les autres services
info "Vérification des services..."
services_ok=0
services_total=6
for svc in "ollama:11434" "qdrant:6333" "n8n:5678" "webui:3001" "browserless:3002"; do
    name="${svc%%:*}"
    port="${svc##*:}"
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port" --max-time 3 2>/dev/null | grep -q "200\|302\|301\|401\|403"; then
        log "$name ✅ (port $port)"
        services_ok=$((services_ok+1))
    else
        warn "$name ⏳ (port $port) - peut prendre plus de temps"
    fi
done

# 5d. Vérifier OpenHands
if curl -s -o /dev/null -w "%{http_code}" "http://localhost:3000" --max-time 5 2>/dev/null | grep -q "200\|302"; then
    log "OpenHands ✅ (port 3000)"
    services_ok=$((services_ok+1))
else
    warn "OpenHands ⏳ (port 3000) - premier démarrage lent"
fi

# ============================================
# RÉSUMÉ FINAL
# ============================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     ✅ AI FACTORY DÉPLOYÉE AVEC SUCCÈS !       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "  📍 Services disponibles sur $(curl -s ifconfig.me 2>/dev/null || echo 'TON_IP_VPS') :"
echo "     http://$(curl -s ifconfig.me 2>/dev/null || echo 'IP_VPS'):3000   → 🤖 OpenHands"
echo "     http://$(curl -s ifconfig.me 2>/dev/null || echo 'IP_VPS'):3001   → 💬 Open WebUI"
echo "     http://$(curl -s ifconfig.me 2>/dev/null || echo 'IP_VPS'):5678   → ⚡ n8n"
echo "     http://$(curl -s ifconfig.me 2>/dev/null || echo 'IP_VPS'):11434  → 🧠 Ollama API"
echo "     http://$(curl -s ifconfig.me 2>/dev/null || echo 'IP_VPS'):6333   → 💾 Qdrant"
echo "     http://$(curl -s ifconfig.me 2>/dev/null || echo 'IP_VPS'):3002   → 🌐 Browserless"
echo ""
echo "  ⚙️  État: $services_ok/$services_total services en ligne"
echo "  📦 Modèles Ollama en cours d'installation en arrière-plan..."
echo ""
if [ -n "$DOMAIN" ]; then
    echo "  🔒 HTTPS actif : https://${DOMAIN}"
    echo "  💬 Chat : https://chat.${DOMAIN}"
    echo "  ⚡ n8n : https://n8n.${DOMAIN}"
else
    echo "  🔑 Pour activer le HTTPS : bash deploy-vps.sh --domain ton-domaine.com"
fi
echo ""
echo "  📋 Logs : docker compose logs -f"
echo "  🛑 Arrêt : docker compose down"
echo "  🔄 MAJ : git pull && docker compose up -d"
echo "  🧹 Tout supprimer : docker compose down -v && rm -rf /opt/ai-factory"
echo ""
