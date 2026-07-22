#!/bin/bash
# ============================================
# AI FACTORY - Script d'Installation One-Shot
# ============================================
# Usage: chmod +x setup.sh && ./setup.sh
# Ce script :
#   1. Vérifie les prérequis (Docker, Git)
#   2. Crée la structure de dossiers
#   3. Télécharge les modèles Ollama de base
#   4. Lance la stack complète
#   5. Configure les health checks
# ============================================

set -e

# Couleurs pour les logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

VERSION="1.0.0"

log() {
    echo -e "${GREEN}[✓]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

error() {
    echo -e "${RED}[✗]${NC} $1"
}

info() {
    echo -e "${BLUE}[i]${NC} $1"
}

banner() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}        AI FACTORY - v${VERSION}            ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}   Installation de l'Usine à Agents    ${BLUE}║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
    echo ""
}

# ============================================
# ÉTAPE 0 : Vérification des prérequis
# ============================================
check_prerequisites() {
    info "Vérification des prérequis..."
    
    # Vérifier Docker
    if ! command -v docker &> /dev/null; then
        error "Docker n'est pas installé."
        info "Installation de Docker..."
        curl -fsSL https://get.docker.com | sh
        log "Docker installé"
    else
        log "Docker: $(docker --version)"
    fi
    
    # Vérifier Docker Compose
    if ! docker compose version &> /dev/null; then
        error "Docker Compose n'est pas installé."
        info "Installation de Docker Compose..."
        apt-get update && apt-get install -y docker-compose-plugin
        log "Docker Compose installé"
    else
        log "Docker Compose: $(docker compose version)"
    fi
    
    # Vérifier Git
    if ! command -v git &> /dev/null; then
        warn "Git n'est pas installé. Installation..."
        apt-get update && apt-get install -y git
    else
        log "Git: $(git --version)"
    fi
    
    # Vérifier curl
    if ! command -v curl &> /dev/null; then
        apt-get update && apt-get install -y curl
    fi
}

# ============================================
# ÉTAPE 1 : Création de la structure
# ============================================
create_structure() {
    info "Création de la structure de dossiers..."
    
    mkdir -p \
        ./data/ollama \
        ./data/qdrant \
        ./data/n8n \
        ./data/open-webui \
        ./data/caddy/data \
        ./data/caddy/config \
        ./data/logs \
        ./skills \
        ./workspace \
        ./registry \
        ./config/caddy \
        ./config/openhands
    
    log "Structure créée:"
    echo ""
    echo "  📁 ai-factory/"
    echo "    ├── 📁 data/         (données persistantes)"
    echo "    ├── 📁 skills/       (templates et modules)"
    echo "    ├── 📁 workspace/    (projets générés)"
    echo "    ├── 📁 registry/     (index des compétences)"
    echo "    ├── 📁 config/       (configurations)"
    echo "    └── docker-compose.yml"
    echo ""
}

# ============================================
# ÉTAPE 2 : Configuration du .env
# ============================================
configure_env() {
    if [ ! -f .env ]; then
        info "Création du fichier .env..."
        
        # Générer des secrets aléatoires
        N8N_PASS=$(openssl rand -base64 12)
        WEBUI_KEY=$(openssl rand -base64 32)
        
        cat > .env << EOF
# AI FACTORY - Variables d'Environnement
# Généré automatiquement le $(date)

# --- Sécurité ---
N8N_PASSWORD=${N8N_PASS}
WEBUI_SECRET_KEY=${WEBUI_KEY}

# --- Domaines (modifie avec ton domaine) ---
DOMAIN_MAIN=exemple.com
DOMAIN_OPENHANDS=openhands.exemple.com
DOMAIN_N8N=n8n.exemple.com
DOMAIN_CHAT=chat.exemple.com

# --- Ollama ---
OLLAMA_DEFAULT_MODEL=qwen2.5-coder:14b

# --- Browserless ---
MAX_CONCURRENT_SESSIONS=5
EOF
        
        log "Fichier .env créé avec des secrets aléatoires"
        warn "⚠️  Modifie les domaines dans .env avant de déployer !"
    else
        log "Fichier .env existant, utilisation des valeurs actuelles"
    fi
}

# ============================================
# ÉTAPE 3 : Téléchargement des modèles Ollama
# ============================================
download_models() {
    info "Téléchargement des modèles Ollama..."
    
    # Attendre qu'Ollama soit prêt
    info "Attente du démarrage d'Ollama..."
    sleep 10
    
    # Modèles recommandés
    local MODELS=(
        "qwen2.5-coder:14b"      # Excellent pour le code (14B paramètres)
        "llama3.2:3b"            # Léger et rapide pour les tâches simples
        "nomic-embed-text"       # Pour les embeddings (RAG dans Qdrant)
        "llava:7b"               # Vision - analyse d'images
    )
    
    for model in "${MODELS[@]}"; do
        info "Téléchargement de $model..."
        docker exec ai-factory-ollama ollama pull "$model" || warn "Échec du téléchargement de $model"
    done
    
    log "Modèles téléchargés"
}

# ============================================
# ÉTAPE 4 : Démarrage de la stack
# ============================================
start_stack() {
    info "Démarrage de la stack complète..."
    
    # Démarrer tous les services
    docker compose up -d
    
    log "Stack démarrée !"
    
    # Afficher le statut
    echo ""
    info "Statut des services :"
    docker compose ps
    echo ""
}

# ============================================
# ÉTAPE 5 : Configuration initiale d'OpenHands
# ============================================
setup_openhands() {
    info "Configuration d'OpenHands..."
    
    # Attendre qu'OpenHands soit prêt
    sleep 15
    
    # Vérifier qu'OpenHands répond
    if curl -s -f http://localhost:3000/api/health &> /dev/null; then
        log "✅ OpenHands est opérationnel sur http://localhost:3000"
    else
        warn "⚠️  OpenHands n'est pas encore prêt. Vérifie les logs : docker compose logs openhands"
    fi
}

# ============================================
# ÉTAPE 6 : Test de l'API Ollama
# ============================================
test_ollama() {
    info "Test de l'API Ollama..."
    
    if curl -s http://localhost:11434/api/tags | grep -q "models"; then
        log "✅ Ollama est opérationnel sur http://localhost:11434"
        
        # Lister les modèles disponibles
        echo ""
        info "Modèles disponibles :"
        curl -s http://localhost:11434/api/tags | python3 -m json.tool 2>/dev/null || echo "(affiche avec curl)"
    else
        warn "⚠️  Ollama n'est pas encore prêt"
    fi
}

# ============================================
# ÉTAPE 7 : Test de Qdrant
# ============================================
test_qdrant() {
    info "Test de Qdrant..."
    
    if curl -s -f http://localhost:6333/healthz &> /dev/null; then
        log "✅ Qdrant est opérationnel sur http://localhost:6333"
    else
        warn "⚠️  Qdrant n'est pas encore prêt"
    fi
}

# ============================================
# FIN : Afficher le résumé
# ============================================
show_summary() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}        🎉 AI FACTORY INSTALLÉE !        ${BLUE}║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
    echo ""
    echo "  📍 OpenHands:     http://localhost:3000"
    echo "  📍 Open WebUI:    http://localhost:3001"
    echo "  📍 Browserless:   http://localhost:3002"
    echo "  📍 Ollama API:    http://localhost:11434"
    echo "  📍 Qdrant:       http://localhost:6333"
    echo "  📍 n8n:          http://localhost:5678"
    echo ""
    echo "  🔑 Identifiants n8n: admin / (voir .env)"
    echo ""
    echo -e "  ${YELLOW}Prochaines étapes :${NC}"
    echo "  1. Configure un domaine avec Caddy (édite config/caddy/Caddyfile)"
    echo "  2. Ajoute des modèles : docker compose exec ollama ollama pull qwen2.5-coder:32b"
    echo "  3. Connecte OpenHands à Ollama via l'interface web"
    echo "  4. Commence à créer tes bots !"
    echo ""
    echo -e "  ${GREEN}Pour voir les logs : docker compose logs -f${NC}"
    echo -e "  ${GREEN}Pour arrêter : docker compose down${NC}"
    echo ""
}

# ============================================
# MAIN
# ============================================
main() {
    banner
    
    # Vérifier qu'on est dans le bon dossier
    if [ ! -f docker-compose.yml ]; then
        error "docker-compose.yml introuvable. Exécute ce script depuis le dossier ai-factory/"
        exit 1
    fi
    
    check_prerequisites
    echo ""
    
    create_structure
    echo ""
    
    configure_env
    echo ""
    
    info "Lancement de la stack..."
    start_stack
    echo ""
    
    # Téléchargement des modèles (en arrière-plan)
    download_models &
    
    # Tests de disponibilité
    sleep 10
    setup_openhands
    echo ""
    
    test_ollama
    echo ""
    
    test_qdrant
    echo ""
    
    show_summary
}

main "$@"
