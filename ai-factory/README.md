# 🏭 AI Factory - L'Usine à Agents Autonomes

> **Transforme ton VPS en une plateforme d'IA souveraine, gratuite et illimitée.**

AI Factory est une stack Docker complète qui te permet d'héberger ta propre **infrastructure d'IA de code** : agents autonomes, bots furtifs, génération de contenu, automatisation marketing, et bien plus — le tout sur ton propre VPS, sans aucune limite de requêtes.

---

## 🎯 Architecture

```
┌─────────────────────────────────────────────────────┐
│                   CADDY (Reverse Proxy)             │
│              SSL automatique via Let's Encrypt       │
├────────┬────────┬────────┬────────┬────────┬────────┤
│ Agent  │ Chat   │ Moteur │ Mémoire│ Workf- │ Navig. │
│ Archi. │ Interf.│ LLM    │ Vector │ lows   │ Headl. │
│OpenHands│WebUI  │Ollama  │Qdrant  │ n8n    │Browser │
│ :3000  │ :3001  │:11434  │:6333   │:5678   │ :3002  │
├────────┴────────┴────────┴────────┴────────┴────────┤
│                  DOCKER NETWORK                     │
│               ai-factory-net (bridge)               │
├─────────────────────────────────────────────────────┤
│              VOLUMES PERSISTANTS (./data/)          │
│   ollama/  qdrant/  n8n/  open-webui/  caddy/      │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Installation Express

```bash
# 1. Connecte-toi à ton VPS
ssh root@ton-vps

# 2. Clone le projet (ou copie le dossier ai-factory/ sur le VPS)
cd /opt
git clone https://github.com/Akyelcattleya/akyelia.git
cd akyelia/ai-factory

# 3. Lance l'installation automatique
chmod +x setup.sh
./setup.sh
```

### Installation Manuelle (si tu préfères)

```bash
# 1. Prérequis : Docker
curl -fsSL https://get.docker.com | sh

# 2. Crée les dossiers
mkdir -p data/{ollama,qdrant,n8n,open-webui,caddy/{data,config},logs}
mkdir -p skills workspace registry config/{caddy,openhands}

# 3. Copie la configuration
cp ai-factory.env.template .env
nano .env  # Modifie les mots de passe et domaines

# 4. Lance la stack
docker compose up -d
```

---

## 🌐 Accès aux Services

| Service | URL | Description |
|---------|-----|-------------|
| **OpenHands** | `http://IP_VPS:3000` | Agent architecte - code et déploie automagiquement |
| **Open WebUI** | `http://IP_VPS:3001` | Interface ChatGPT-like connectée à ton Ollama |
| **Browserless** | `http://IP_VPS:3002` | Service de navigateur headless pour tes bots |
| **Ollama API** | `http://IP_VPS:11434` | API des modèles LLM locaux |
| **Qdrant** | `http://IP_VPS:6333` | Dashboard de la base vectorielle |
| **n8n** | `http://IP_VPS:5678` | Orchestrateur de workflows visuel |
| **Caddy** | `http://IP_VPS:80/443` | Reverse proxy avec SSL automatique |

> **Avec un domaine** : configure les sous-domaines dans `config/caddy/Caddyfile`
> puis Caddy générera automatiquement les certificats SSL.

---

## 🧠 Premiers Pas avec l'IA

### 1. Télécharger un modèle de code

```bash
docker compose exec ollama ollama pull qwen2.5-coder:14b
```

### 2. Tester l'API Ollama

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5-coder:14b",
  "prompt": "Écris une fonction Python qui vérifie si un nombre est premier",
  "stream": false
}'
```

### 3. Connecter OpenHands à Ollama

1. Accède à `http://IP_VPS:3000`
2. Dans les paramètres, configure :
   - **Provider** : OpenAI Compatible
   - **Base URL** : `http://ollama:11434/v1`
   - **Model** : `qwen2.5-coder:14b`
3. Sauvegarde et commence à coder !

### 4. Donner son premier ordre à OpenHands

```text
Tu es l'Architecte de l'AI Factory. Crée un bot de prospection LinkedIn
qui utilise le template dans /skills/stealth-module/.
Configure-le pour envoyer 10 invitations par jour avec des messages
personnalisés, en respectant les limites de LinkedIn.
```

---

## 🛠️ Ajouter des Skills (Compétences)

### Depuis OpenHands (recommandé)

```text
OpenHands, intègre ce projet comme une skill :
https://github.com/Atrox/playwright-stealth

Clone-le dans /skills/, analyse le README,
et ajoute-le au registry.
```

### Manuellement

```bash
# 1. Clone le dépôt
git clone https://github.com/Atrox/playwright-stealth skills/playwright-stealth

# 2. Ajoute au registre
nano registry/skills-registry.yaml
# Ajoute l'entrée dans la section "skills"
```

---

## 🤖 Créer un Bot Furtif

### Template de base

Le dossier `skills/stealth-module/` contient un template complet de bot furtif.

**Configuration par variables d'environnement :**

```bash
export BOT_TARGET_URL="https://linkedin.com"
export BOT_TARGET_ACTIONS='[{"type":"click","selector":"[aria-label='Se connecter']"}]'
export BOT_MAX_ACTIONS_PER_HOUR=10
export BOT_PROXY_URL="http://mon-proxy:8080"

python3 skills/stealth-module/template.py
```

**Caractéristiques du template :**
- ✅ Anti-détection Playwright
- ✅ Simulation de comportement humain (délais, mouvements de souris)
- ✅ Gestion des limites (quotas horaires)
- ✅ Auto-guérison (détection et contournement de blocages)
- ✅ Sauvegarde de session (cookies persistants)
- ✅ Logging complet

---

## 📋 Variables d'Environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `N8N_PASSWORD` | `changeme123` | Mot de passe pour n8n |
| `WEBUI_SECRET_KEY` | (aléatoire) | Clé secrète pour Open WebUI |
| `OLLAMA_DEFAULT_MODEL` | `qwen2.5-coder:14b` | Modèle chargé au démarrage |
| `MAX_CONCURRENT_SESSIONS` | `5` | Sessions navigateur simultanées |
| `BOT_MIN_DELAY` | `2.0` | Délai minimum entre actions (secondes) |
| `BOT_MAX_DELAY` | `8.0` | Délai maximum entre actions (secondes) |
| `BOT_MAX_ACTIONS_HOUR` | `10` | Actions max par heure (anti-blocage) |

---

## ⚙️ Commandes Utiles

```bash
# Voir les logs de tous les services
docker compose logs -f

# Voir les logs d'un service spécifique
docker compose logs -f openhands

# Arrêter la stack
docker compose down

# Redémarrer un service
docker compose restart ollama

# Télécharger un modèle Ollama
docker compose exec ollama ollama pull deepseek-coder-v2

# Exécuter une commande dans OpenHands
docker compose exec openhands /bin/bash

# Sauvegarder les données
tar -czf backup-ai-factory-$(date +%Y%m%d).tar.gz data/
```

---

## 🔧 Aller Plus Loin

### Ajouter un GPU NVIDIA

Décommente les lignes `deploy:` dans `docker-compose.yml` pour :
- **Ollama** : inférence jusqu'à 10x plus rapide
- **ComfyUI** : génération d'images locale
- **Browserless** : rendu plus fluide

### Sécuriser l'accès

```bash
# Restreindre Ollama à ton IP fixe
sudo ufw allow from TON_IP to any port 11434
sudo ufw deny 11434
```

### Sauvegarde automatique

Ajoute cette ligne à ta crontab (`crontab -e`) :
```bash
0 3 * * * cd /opt/ai-factory && tar -czf /backups/ai-factory-$(date +\%Y\%m\%d).tar.gz data/
```

---

## 🔗 Liens Utiles

| Projet | GitHub | Documentation |
|--------|--------|---------------|
| OpenHands | [all-hands-ai/openhands](https://github.com/all-hands-ai/openhands) | [docs](https://docs.all-hands.dev) |
| Ollama | [ollama/ollama](https://github.com/ollama/ollama) | [docs](https://github.com/ollama/ollama) |
| Qdrant | [qdrant/qdrant](https://github.com/qdrant/qdrant) | [docs](https://qdrant.tech/documentation) |
| n8n | [n8n-io/n8n](https://github.com/n8n-io/n8n) | [docs](https://docs.n8n.io) |
| Open WebUI | [open-webui/open-webui](https://github.com/open-webui/open-webui) | [docs](https://docs.openwebui.com) |
| Caddy | [caddyserver/caddy](https://github.com/caddyserver/caddy) | [docs](https://caddyserver.com/docs) |
| Browserless | [browserless/browserless](https://github.com/browserless/browserless) | [docs](https://docs.browserless.io) |

---

## 📜 License

MIT — Fais ce que tu veux, c'est ton IA, ton VPS, tes règles.
