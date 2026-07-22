#!/bin/bash
# ============================================
# MEGA INSTALL MODÈLES IA — 100% Gratuit
# Télécharge TOUS les meilleurs modèles open source
# en parallèle pour une puissance maximale
# ============================================

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log() { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
section() { echo -e "\n${CYAN}══════════════════════════════════════${NC}"; echo -e "${CYAN}  $1${NC}"; echo -e "${CYAN}══════════════════════════════════════${NC}"; }

cd /opt/ai-factory

section "🎯 INSTALLATION MASSIVE DES MODÈLES IA"
echo ""

# Vérifier qu'Ollama tourne
if ! docker compose exec ollama ollama list &>/dev/null; then
    echo "❌ Ollama ne répond pas. Démarre les services d'abord avec : docker compose up -d"
    exit 1
fi

# ============================================
# MODÈLES À INSTALLER — TOP 10 pour 8GB RAM
# ============================================
# Format: "nom_modele|Catégorie|Taille|Stars"
MODELS=(
    "qwen2.5-coder:7b|💻 Code Master|4.7GB|⭐ Ultra Populaire"
    "phi4-mini:3.8b|⚡ Fast Reasoning|2.5GB|⭐ Microsoft"
    "qwen3.5:4b|🧠 Polyvalent Pro|3.4GB|⭐ Alibaba"
    "deepseek-r1:7b|🔬 Deep Reasoning|4.5GB|⭐ DeepSeek"
    "llama3.2:3b|🦙 Chat Créatif|2GB|⭐ Meta"
    "gemma2:2b|🌐 Multilingue|1.5GB|⭐ Google"
    "mistral:7b|🌀 Général Expert|4.1GB|⭐ Mistral AI"
    "llava:7b|👁️ Vision AI|4.5GB|⭐ Vision & Images"
    "nomic-embed-text|📐 Embeddings RAG|0.3GB|⭐ Mémoire IA"
    "codegemma:2b|🔧 Code Léger|1.3GB|⭐ Google Code"
)

TOTAL=${#MODELS[@]}
CURRENT=0
SUCCESS=0
FAILED=0

# Afficher ce qui va être installé
echo "📦 MODÈLES À INSTALLER ($TOTAL):"
echo "────────────────────────────────────────────"
for model_info in "${MODELS[@]}"; do
    IFS='|' read -r model_name category size stars <<< "$model_info"
    printf "  %-25s %-18s %s\n" "$model_name" "$size" "$category"
done
echo "────────────────────────────────────────────"
echo ""

# Vérifier combien de place il reste
DF=$(df -BG /opt | tail -1 | awk '{print $4}' | sed 's/G//')
echo "💾 Espace disque disponible: ${DF}GB"
echo ""

# Vérifier combien de modèles sont déjà installés
ALREADY=$(docker compose exec ollama ollama list 2>/dev/null | wc -l)
if [ "$ALREADY" -gt 1 ]; then
    echo "✅ $((ALREADY - 1)) modèle(s) déjà installé(s)"
fi
echo ""

read -p "🚀 Lancer l'installation massive ? (O/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Oo]$ ]] && [[ ! -z $REPLY ]]; then
    echo "Annulé."
    exit 0
fi

echo ""
section "📥 TÉLÉCHARGEMENT EN PARALLÈLE"

# Lancer les installations en parallèle (groupes de 2 pour pas saturer le CPU/RAM)
install_model() {
    local model_info="$1"
    IFS='|' read -r model_name category size stars <<< "$model_info"
    
    # Vérifier si déjà installé
    if docker compose exec ollama ollama list 2>/dev/null | grep -q "^${model_name}\b"; then
        echo "  ✅ $model_name déjà installé — ignoré"
        return 0
    fi
    
    echo "  📥 Installation de $model_name ($size)..."
    if docker compose exec -d ollama ollama pull "$model_name" 2>/dev/null; then
        echo "  ✅ $model_name installé !"
        return 0
    else
        echo "  ⚠️ Échec pour $model_name (peut-être pas de place)"
        return 1
    fi
}

# Groupe 1: Essentiels (larges, à démarrer en premier)
echo ""
echo "╔════════════════════════════════════════════╗"
echo "║  GROUPE 1 — Modèles essentiels (4-5GB)   ║"
echo "╚════════════════════════════════════════════╝"
echo ""

for model_info in "${MODELS[@]:0:4}"; do
    IFS='|' read -r model_name category size stars <<< "$model_info"
    echo "  🚀 Lancement de $model_name..."
    docker compose exec -d ollama ollama pull "$model_name" 2>/dev/null || true
done

echo ""
echo "  ⏳ Téléchargement en cours (5-15 min selon la connexion)..."
echo "  📊 Surveille avec: docker compose exec ollama ollama list"
echo ""

# Groupe 2: Modèles moyens (2-3GB)
echo ""
echo "╔════════════════════════════════════════════╗"
echo "║  GROUPE 2 — Modèles complémentaires       ║"
echo "╚════════════════════════════════════════════╝"
echo ""

sleep 30

for model_info in "${MODELS[@]:4:4}"; do
    IFS='|' read -r model_name category size stars <<< "$model_info"
    echo "  🚀 Lancement de $model_name..."
    docker compose exec -d ollama ollama pull "$model_name" 2>/dev/null || true
done

echo ""
echo "  ⏳ Téléchargement en cours..."
sleep 20

# Groupe 3: Petits modèles (rapides)
echo ""
echo "╔════════════════════════════════════════════╗"
echo "║  GROUPE 3 — Modèles légers (rapides)      ║"
echo "╚════════════════════════════════════════════╝"
echo ""

for model_info in "${MODELS[@]:8}"; do
    IFS='|' read -r model_name category size stars <<< "$model_info"
    echo "  🚀 Lancement de $model_name..."
    docker compose exec -d ollama ollama pull "$model_name" 2>/dev/null || true
done

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ TOUS LES TÉLÉCHARGEMENTS LANCÉS !"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  📊 Vérifie l'avancement avec :"
echo "     docker compose exec ollama ollama list"
echo ""
echo "  🔄 Recharge le Smart Router :"
echo "     http://148.230.98.203:8765"
echo ""

echo "Modèles installés :"
docker compose exec ollama ollama list 2>/dev/null || echo "  (encore en cours...)"
