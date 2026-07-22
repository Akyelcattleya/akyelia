# ============================================
# AI FACTORY - Makefile
# ============================================
# Commandes rapides pour l'usine à agents.
#
# Usage:
#   make start      - Démarrer l'usine
#   make stop       - Arrêter l'usine
#   make status     - État des services
#   make logs       - Voir les logs
#   make models     - Installer les modèles
#   make bot        - Créer un bot (DESC="mon bot")
#   make doctor     - Diagnostiquer
#   make update     - Mettre à jour
#   make clean      - Nettoyer
#   make reset      - Réinitialiser complètement
# ============================================

.PHONY: start stop status logs models bot skill doctor update clean reset help

# ─── Variables ───────────────────────────────────
DESC ?= "bot personnalisé"
URL  ?= ""
SVC  ?= "all"

# ─── Commandes ──────────────────────────────────

## 🚀 Démarrer l'usine
start:
	@python3 launch.py start

## 🛑 Arrêter l'usine
stop:
	@python3 launch.py stop

## 📊 État des services
status:
	@python3 launch.py status

## 📋 Voir les logs (SVC=service_name pour filtrer)
logs:
	@python3 launch.py logs --service $(SVC)

## 📦 Installer les modèles Ollama recommandés
models:
	@python3 launch.py models

## 🤖 Créer un bot (DESC="description du bot")
bot:
	@python3 launch.py bot "$(DESC)"

## 📥 Ingérer un skill GitHub (URL="https://github.com/...")
skill:
	@python3 launch.py skill "$(URL)"

## 🔧 Diagnostiquer et réparer
doctor:
	@python3 launch.py doctor

## 🩺 Audit rapide
audit:
	@echo "🔍 Audit du code source..."
	@find . -name "*.py" -type f | while read f; do \
		python3 -c "import py_compile; py_compile.compile('$$f', doraise=True)" 2>&1 && echo "✅ $$f" || echo "❌ $$f"; \
	done
	@echo ""
	@echo "📊 Statistiques:"
	@find . -name "*.py" -type f -exec wc -l {} + | tail -1
	@find . -type f | wc -l | xargs -I{} echo "📁 {} fichiers"

## 🗑️ Nettoyer les caches et données temporaires
clean:
	@echo "🧹 Nettoyage..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Caches nettoyés"

## 🔄 Mettre à jour depuis GitHub
update:
	@python3 launch.py update

## ⚠️  Réinitialisation complète (arrête et supprime les données)
reset:
	@echo "⚠️  RÉINITIALISATION COMPLÈTE"
	@echo "   Arrêt des services..."
	-docker compose down -v 2>/dev/null
	@echo "   Suppression des données..."
	-rm -rf data/* 2>/dev/null
	@echo "   ✅ Réinitialisation terminée"
	@echo "   Relance: make start"

## 🐳 Redémarrer un service spécifique (SVC=service_name)
restart:
	@docker compose restart ai-factory-$(SVC)

## 📱 Dashboard web
dashboard:
	@python3 launch.py dashboard

## ❓ Aide
help:
	@echo ""
	@echo "╔═══════════════════════════════════════╗"
	@echo "║   🏭 AI FACTORY - Aide rapide        ║"
	@echo "╚═══════════════════════════════════════╝"
	@echo ""
	@echo "  $$ make start          Démarrer l'usine"
	@echo "  $$ make stop           Arrêter l'usine"
	@echo "  $$ make status         État des services"
	@echo "  $$ make logs           Voir les logs"
	@echo "  $$ make models         Installer les modèles"
	@echo "  $$ make bot DESC=...   Créer un bot"
	@echo "  $$ make skill URL=...  Ingérer un skill"
	@echo "  $$ make doctor         Diagnostiquer"
	@echo "  $$ make audit          Audit du code"
	@echo "  $$ make clean          Nettoyer les caches"
	@echo "  $$ make update         Mettre à jour"
	@echo "  $$ make reset          Réinitialiser"
	@echo "  $$ make restart SVC=x  Redémarrer un service"
	@echo "  $$ make dashboard       Dashboard web"
	@echo ""
	@echo "  Variables: DESC, URL, SVC"
	@echo "  Ex: make bot DESC=\"bot pour LinkedIn\""
	@echo ""

.DEFAULT_GOAL := help
