# 🚀 Déployer Akyel AI sur Hugging Face Spaces

## Prérequis

- Un compte [Hugging Face](https://huggingface.co/join) (gratuit, pas de carte bleue)
- Des clés API gratuites (DeepSeek, Groq, Gemini)

---

## Étape 1 : Créer un Space

1. Va sur [huggingface.co/spaces](https://huggingface.co/spaces)
2. Clique sur **"Create new Space"**
3. Configure :
   - **Space Name :** `akyel-ai` (ou le nom que tu veux)
   - **License :** MIT
   - **Space SDK :** **Docker**
   - **Space Hardware :** **CPU - Free** (gratuit)
4. Clique **"Create Space"**

---

## Étape 2 : Ajouter tes clés API (Secrets)

Dans ton Space, va dans **Settings → Repository Secrets** et ajoute :

| Secret | Valeur | Où l'obtenir |
|---|---|---|
| `DEFAULT_PROVIDER` | `deepseek` | **IMPORTANT** : changer de `omniroute` à `deepseek` pour le cloud |
| `DEEPSEEK_API_KEY` | `sk-...` | [platform.deepseek.com](https://platform.deepseek.com) - Gratuit |
| `GROQ_API_KEY` | `gsk_...` | [console.groq.com](https://console.groq.com) - Gratuit |
| `GEMINI_API_KEY` | `AIza...` | [aistudio.google.com](https://aistudio.google.com) - Gratuit |
| `NVIDIA_API_KEY` | `nvapi-...` | [build.nvidia.com](https://build.nvidia.com) - Gratuit |

> ⚠️ **IMPORTANT** : Ajoute `DEFAULT_PROVIDER=deepseek` dans les Secrets. Sans ça, le chat essaiera d'utiliser OmniRoute (qui n'existe pas sur HF Spaces) et échouera.

Ajoute au moins **DeepSeek** et **Groq** pour que ça marche tout de suite.

---

## Étape 3 : Déployer le code

### Option A : Via Git (recommandé)

```bash
# Clone ton Space HF
git clone https://huggingface.co/spaces/TON-COMPTE/akyel-ai
cd akyel-ai

# Copie les fichiers de freebuff/
cp -r chemin/vers/freebuff/* .

# Push sur HF
git add .
git commit -m "Deploiement Akyel AI"
git push
```

### Option B : Via upload manuel

1. Dans ton Space, va dans **Files**
2. Glisse-dépose tous les fichiers de `freebuff/`
3. Assure-toi que `Dockerfile` est à la racine

---

## Étape 4 : Ton IA est en ligne ! 🎉

Une fois le build terminé (5-10 min), ton IA sera accessible à :
```
https://TON-COMPTE-akyel-ai.hf.space
```

---

## ⚠️ Important : Différences avec la version locale

| Fonctionnalité | Local | En ligne (HF) |
|---|---|---|
| **OmniRoute** | ✅ Gratuit, 99 modèles | ❌ Non disponible |
| **Clé API DeepSeek** | Optionnel | ✅ Requis |
| **Clé API Groq** | Optionnel | ✅ Recommandé |
| **Clé API Gemini** | Optionnel | ✅ Recommandé |
| **Skills / Repos** | ✅ OK | ⚠️ Git doit être installé |
| **Base de données** | ✅ SQLite locale | ✅ SQLite persistante (/data) |

---

## 💡 Astuces

- **Pour éviter le "sommeil"** : le free tier HF s'endort après 15 min d'inactivité. Mets un uptimerobot.com pour ping toutes les 10 min.
- **Pour activer le GPU** : Settings → Space Hardware → T4 GPU (payant, $0.60/h)
