# 🦊 AkyelIA - Assistant de Codage Multi-LLM

**12 fournisseurs d'IA** dans une interface magnifique : DeepSeek, OpenAI, Claude, Gemini, Groq, Kimi, Mistral, Perplexity, xAI, OpenRouter, Together AI & Ollama.

---

## 🚀 Déploiement sur Render.com (Gratuit)

### 1️⃣ Créer un dépôt GitHub

```bash
# Depuis le dossier freebuff/
git init
git add .
git commit -m "Premier commit - AkyelIA"
```

Puis crée un nouveau repo sur **github.com** et pousse le code :
```bash
git remote add origin https://github.com/TON-COMPTE/akyelia.git
git branch -M main
git push -u origin main
```

### 2️⃣ Connecter à Render

1. Va sur **https://render.com** et connecte-toi (compte gratuit)
2. Clique sur **"New +" > "Blueprint"**
3. Connecte ton dépôt GitHub
4. Render détecte automatiquement `render.yaml`
5. Ajoute tes **clés API** dans l'onglet "Environment" (optionnel au début)

### 3️⃣ Variables d'environnement

Dans le dashboard Render, ajoute tes clés API :

| Variable | Où l'obtenir | Prix |
|---|---|---|
| `DEEPSEEK_API_KEY` | https://platform.deepseek.com/api_keys | Gratuit |
| `GEMINI_API_KEY` | https://aistudio.google.com/app/apikey | **Gratuit** |
| `GROQ_API_KEY` | https://console.groq.com/keys | **Gratuit** |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys | Payant |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys | Payant |
| `KIMI_API_KEY` | https://platform.moonshot.cn/console/api-keys | Gratuit |
| `MISTRAL_API_KEY` | https://console.mistral.ai/api-keys/ | Gratuit |

### 4️⃣ C'est en ligne ! 🎉

Render te donne une URL du style : `https://akyelia.onrender.com`

---

## ⚠️ Important : Données sur Render Gratuit

Le plan gratuit de Render utilise un **système de fichiers éphémère**. Cela signifie :
- Les conversations sont **perdues** au redémarrage (~15 min d'inactivité)
- Pour un usage sérieux, passe au plan **Starter** (7$/mois) et ajoute un **Disk** (0,10$/GB)

---

## 🐳 Alternative : Docker

```bash
docker build -t akyelia .
docker run -p 7777:7777 -e DEEPSEEK_API_KEY=ta_cle akyelia
```

---

## 📁 Structure du projet

```
freebuff/
├── app.py              # Backend FastAPI
├── config.py           # Configuration des 12 providers
├── llm_providers.py    # Intégrations LLM
├── requirements.txt    # Dépendances
├── render.yaml         # Config Render.com
├── Dockerfile          # Déploiement Docker
├── start.sh            # Script de démarrage
├── .env.example        # Exemple de clés API
├── .gitignore
└── static/
    └── index.html      # Interface utilisateur
```
