#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║           AI FACTORY - SMART ROUTER v2.0 (MUSK MODE)       ║
║  Le chat unique qui choisit le meilleur modèle pour toi    ║
║  Analyse → Route → Génère → Livre en moins d'1 seconde    ║
╚══════════════════════════════════════════════════════════════╝
"""

import os, json, asyncio, re, time, html
from urllib.parse import quote
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# ============================================
# CONFIGURATION
# ============================================
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "phi4-mini:3.8b")
PORT = int(os.getenv("PORT", "8765"))
WEB_SEARCH_ENABLED = True

# Tous les modèles disponibles avec leurs specs
MODELS = {
    "qwen2.5-coder:7b": {
        "name": "Qwen 2.5 Coder 7B",
        "emoji": "💻",
        "color": "#3b82f6",
        "specialty": "Code & Programmation",
        "speed": "Moyen",
        "size": "4.7GB",
        "best_for": ["code", "programmation", "python", "javascript", "algorithme", "debug", "api", "script", "sql", "react", "docker", "git", "terminal", "function", "classe", "bug", "compiler", "framework"],
        "quality": 9
    },
    "phi4-mini:3.8b": {
        "name": "Phi-4 Mini 3.8B",
        "emoji": "⚡",
        "color": "#a855f7",
        "specialty": "Raisonnement & Logique",
        "speed": "Très rapide",
        "size": "2.5GB",
        "best_for": ["raisonnement", "logique", "math", "science", "analyse", "réflexion", "puzzle", "calcul", "problème", "stratégie", "planification", "décision"],
        "quality": 8
    },
    "qwen3.5:4b": {
        "name": "Qwen 3.5 4B",
        "emoji": "🧠",
        "color": "#06b6d4",
        "specialty": "Polyvalent & Général",
        "speed": "Rapide",
        "size": "3.4GB",
        "best_for": ["général", "conseil", "explication", "résumé", "traduction", "rédaction", "email", "lettre", "article", "blog", "documentation", "rapport"],
        "quality": 8
    },
    "llama3.2:3b": {
        "name": "Llama 3.2 3B",
        "emoji": "🦙",
        "color": "#22c55e",
        "specialty": "Chat & Créativité",
        "speed": "Très rapide",
        "size": "2GB",
        "best_for": ["chat", "conversation", "créatif", "histoire", "poème", "blague", "idée", "brainstorming", "écriture", "storytelling", "humour", "philosophie"],
        "quality": 7
    },
    "gemma2:2b": {
        "name": "Gemma 2 2B",
        "emoji": "🌐",
        "color": "#ec4899",
        "specialty": "Multilingue & Traduction",
        "speed": "Ultra rapide",
        "size": "1.5GB",
        "best_for": ["traduction", "multilingue", "anglais", "français", "espagnol", "grammaire", "orthographe", "vocabulaire", "langue"],
        "quality": 7
    },
    "deepseek-r1:7b": {
        "name": "DeepSeek R1 7B",
        "emoji": "🔬",
        "color": "#f59e0b",
        "specialty": "Recherche & Deep Dive",
        "speed": "Lent",
        "size": "4.5GB",
        "best_for": ["recherche", "deep", "technique", "avancé", "analyse approfondie", "thèse", "académique", "complexe", "scientifique"],
        "quality": 10
    },
    "nomic-embed-text": {
        "name": "Nomic Embed Text",
        "emoji": "📐",
        "color": "#6366f1",
        "specialty": "Embeddings & RAG",
        "speed": "Instantané",
        "size": "0.3GB",
        "best_for": ["embedding", "vecteur", "recherche sémantique", "similarité"],
        "quality": 7
    }
}

app = FastAPI(title="AI Factory Smart Router")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Cache pour les modèles disponibles sur Ollama
available_models_cache = []
cache_time = 0

async def get_available_models():
    global available_models_cache, cache_time
    now = time.time()
    if now - cache_time < 30 and available_models_cache:
        return available_models_cache
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            if r.status_code == 200:
                data = r.json()
                available = [m["name"] for m in data.get("models", [])]
                available_models_cache = available
                cache_time = now
                return available
    except:
        pass
    return available_models_cache

async def analyze_query(query: str) -> dict:
    """Analyse la requête pour déterminer le meilleur modèle"""
    q = query.lower()
    
    scores = {}
    for model_id, info in MODELS.items():
        score = 0
        for kw in info["best_for"]:
            if kw in q:
                score += 2
        # Bonus pour la longueur
        if len(query) > 200 and model_id == "deepseek-r1:7b":
            score += 3
        if len(query) < 100 and model_id in ["phi4-mini:3.8b", "llama3.2:3b"]:
            score += 1
        # Code-related keywords
        code_words = ["code", "python", "javascript", "function", "api", "bug", "git", "docker", "html", "css", "react", "sql"]
        if any(w in q for w in code_words):
            if model_id == "qwen2.5-coder:7b":
                score += 5
        # Deep/reasoning
        if any(w in q for w in ["pourquoi", "comment", "explique", "analyse", "compare", "différence"]):
            if model_id == "phi4-mini:3.8b":
                score += 3
            if model_id == "deepseek-r1:7b":
                score += 2
        scores[model_id] = score
    
    # Sélectionner le meilleur modèle disponible
    available = await get_available_models()
    best = max(scores, key=scores.get)
    
    # Si le modèle choisi n'est pas disponible, prendre le meilleur dispo
    if best not in available and best != "nomic-embed-text":
        for model_id in sorted(scores, key=scores.get, reverse=True):
            if model_id in available:
                best = model_id
                break
    
    return {
        "model": best,
        "model_info": MODELS.get(best, {}),
        "confidence": min(100, scores.get(best, 0) * 10 + 50),
        "all_scores": {m: s for m, s in sorted(scores.items(), key=lambda x: x[1], reverse=True)}
    }

async def web_search(query: str) -> str:
    """Cherche sur le web via DuckDuckGo"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = "https://lite.duckduckgo.com/lite/"
            r = await client.post(url, data={"q": query}, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                import re
                results = re.findall(r'<a[^>]*class="[^"]*result-link[^"]*"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', r.text)
                snippets = re.findall(r'<td[^>]*class="[^"]*result-snippet[^"]*"[^>]*>(.*?)</td>', r.text, re.DOTALL)
                output = ""
                for i, (url, title) in enumerate(results[:5]):
                    snippet = snippets[i] if i < len(snippets) else ""
                    snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                    output += f"{i+1}. {title}\n   URL: {url}\n   {snippet}\n\n"
                return output.strip() or ""
    except:
        return ""
    return ""

async def generate_response(query: str, model: str, search: bool = False):
    """Génère la réponse via Ollama"""
    context = ""
    if search or any(w in query.lower() for w in ["actualité", "dernières", "news", "aujourd"hui", "2026", "2025", "récent", "prix", "météo", "cours", "google", "recherche web", "internet", "va en ligne"]):
        context = await web_search(query)
    
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            if context:
                prompt = f"""Tu es un assistant IA expert avec accès Internet. 
Utilise les résultats de recherche web ci-dessous pour répondre à la question.

🌐 RÉSULTATS DE RECHERCHE WEB :
{context}

📝 QUESTION: {query}

Réponds de façon claire et complète, en citant tes sources si possible."""
            else:
                prompt = f"""Tu es un assistant IA expert, utile et précis. 
Réponds à la question suivante de façon claire, structurée et complète.

Question: {query}

Réponse:"""
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "num_ctx": 4096
                }
            }
            async with client.stream("POST", f"{OLLAMA_URL}/api/generate", json=payload, timeout=120) as resp:
                async for line in resp.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                            if data.get("done"):
                                break
                        except:
                            continue
    except Exception as e:
        yield f"\n\n❌ Erreur: {str(e)}"

# ============================================
# PAGE HTML PRINCIPALE - Interface Musk-level
# ============================================

HTML_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Factory — Smart Router</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0a0a0f;--bg2:#12121a;--bg3:#1a1a2e;--card:#1e1e32;--border:#2a2a4a;--text:#e8e8f0;--text2:#9090b0;--accent:#6c5ce7;--accent2:#a855f7;--gradient:linear-gradient(135deg,#6c5ce7,#a855f7,#3b82f6);--success:#22c55e;--warning:#f59e0b;--error:#ef4444}
html{scroll-behavior:smooth}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;overflow-x:hidden}
body::before{content:'';position:fixed;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(circle at 30% 20%,rgba(108,92,231,0.08) 0%,transparent 50%),radial-gradient(circle at 70% 80%,rgba(168,85,247,0.05) 0%,transparent 50%);pointer-events:none;z-index:0}
/* PARTICULES */
#particles{position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;overflow:hidden}
.particle{position:absolute;width:3px;height:3px;background:rgba(108,92,231,0.4);border-radius:50%;animation:float linear infinite}
@keyframes float{0%{transform:translateY(100vh) rotate(0deg);opacity:0}10%{opacity:1}90%{opacity:1}100%{transform:translateY(-10vh) rotate(720deg);opacity:0}}
/* HEADER */
.header{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(10,10,15,0.85);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);padding:0 2rem;height:64px;display:flex;align-items:center;justify-content:space-between}
.logo{display:flex;align-items:center;gap:12px;font-size:1.2rem;font-weight:800;background:var(--gradient);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.logo-icon{width:36px;height:36px;border-radius:10px;background:var(--gradient);display:flex;align-items:center;justify-content:center;font-size:1.2rem;-webkit-text-fill-color:white}
.header-right{display:flex;align-items:center;gap:16px}
.model-badge{background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:6px 12px;font-size:0.75rem;display:flex;align-items:center;gap:6px}
.model-badge .dot{width:6px;height:6px;border-radius:50%;background:var(--success);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
.model-count{color:var(--text2);font-size:0.7rem}
/* CHAT CONTAINER */
.chat-container{position:relative;z-index:1;max-width:860px;margin:0 auto;padding-top:88px;padding-bottom:120px}
/* WELCOME */
.welcome{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:60vh;text-align:center;padding:2rem}
.welcome-badge{display:inline-flex;align-items:center;gap:8px;background:rgba(108,92,231,0.15);border:1px solid rgba(108,92,231,0.3);border-radius:100px;padding:6px 16px;font-size:0.8rem;color:var(--accent);margin-bottom:2rem}
.welcome h1{font-size:3.5rem;font-weight:900;line-height:1.1;margin-bottom:1rem;background:var(--gradient);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.welcome p{font-size:1.15rem;color:var(--text2);max-width:500px;line-height:1.6;margin-bottom:2.5rem}
.model-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;width:100%;max-width:700px;margin-bottom:2.5rem}
.model-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px;text-align:left;transition:all 0.3s;cursor:default}
.model-card:hover{transform:translateY(-2px);border-color:var(--accent);box-shadow:0 8px 30px rgba(108,92,231,0.15)}
.model-card .icon{font-size:1.5rem;margin-bottom:4px}
.model-card .name{font-weight:600;font-size:0.85rem;margin-bottom:2px}
.model-card .spec{font-size:0.7rem;color:var(--text2)}
.model-card .bar{height:3px;border-radius:3px;margin-top:6px;transition:width 1s}
.start-btn{display:inline-flex;align-items:center;gap:10px;background:var(--gradient);border:none;border-radius:100px;padding:14px 32px;font-size:1rem;font-weight:600;color:white;cursor:pointer;transition:all 0.3s;font-family:'Inter',sans-serif}
.start-btn:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(108,92,231,0.3)}
/* MESSAGES */
.messages{display:flex;flex-direction:column;gap:16px;padding:1rem 1.5rem}
.msg{display:flex;gap:12px;max-width:85%;animation:msgIn 0.3s ease}
@keyframes msgIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.msg.user{flex-direction:row-reverse;align-self:flex-end}
.msg.assistant{align-self:flex-start}
.msg-avatar{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;flex-shrink:0}
.msg.user .msg-avatar{background:var(--gradient);color:white}
.msg.assistant .msg-avatar{background:var(--bg3);border:1px solid var(--border)}
.msg-content{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:14px 18px;font-size:0.92rem;line-height:1.6}
.msg.user .msg-content{background:rgba(108,92,231,0.15);border-color:rgba(108,92,231,0.3)}
.model-tag{display:inline-flex;align-items:center;gap:4px;font-size:0.7rem;padding:3px 8px;border-radius:6px;margin-bottom:8px;font-weight:500}
.model-tag .emoji{font-size:0.8rem}
.thinking{display:none;align-items:center;gap:12px;padding:1rem 1.5rem;animation:msgIn 0.3s ease}
.thinking.active{display:flex}
.thinking-bar{flex:1;height:3px;background:var(--bg3);border-radius:3px;overflow:hidden;position:relative}
.thinking-bar::after{content:'';position:absolute;top:0;left:-30%;width:30%;height:100%;background:var(--gradient);border-radius:3px;animation:barMove 1.5s ease infinite}
@keyframes barMove{0%{left:-30%}100%{left:130%}}
.thinking-text{font-size:0.85rem;color:var(--text2);white-space:nowrap}
/* INPUT */
.input-bar{position:fixed;bottom:0;left:0;right:0;z-index:100;background:linear-gradient(180deg,transparent,rgba(10,10,15,0.95) 20%);padding:1.5rem 2rem 1.5rem}
.input-inner{max-width:860px;margin:0 auto;display:flex;gap:8px;background:var(--bg2);border:1px solid var(--border);border-radius:16px;padding:6px;transition:all 0.3s}
.input-inner:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px rgba(108,92,231,0.15)}
.input-inner textarea{flex:1;background:transparent;border:none;outline:none;color:var(--text);font-family:'Inter',sans-serif;font-size:0.95rem;padding:10px 12px;resize:none;min-height:24px;max-height:120px;line-height:1.5}
.input-inner textarea::placeholder{color:var(--text2)}
.input-inner button{width:44px;height:44px;border-radius:12px;border:none;background:var(--gradient);color:white;font-size:1.2rem;cursor:pointer;transition:all 0.3s;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.input-inner button:hover{transform:scale(1.05);box-shadow:0 4px 20px rgba(108,92,231,0.3)}
.input-inner button:disabled{opacity:0.4;cursor:not-allowed;transform:none}
/* MODEL SELECTOR */
.model-selector{position:relative}
.model-select-btn{display:flex;align-items:center;gap:6px;background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:8px 12px;font-size:0.8rem;color:var(--text);cursor:pointer;transition:all 0.2s;font-family:'Inter',sans-serif}
.model-select-btn:hover{border-color:var(--accent)}
.model-dropdown{position:absolute;bottom:100%;left:0;margin-bottom:8px;background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:6px;width:280px;display:none;z-index:50;max-height:300px;overflow-y:auto}
.model-dropdown.show{display:block}
.model-option{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:8px;cursor:pointer;transition:all 0.2s;font-size:0.85rem}
.model-option:hover{background:var(--bg3)}
.model-option.active{background:rgba(108,92,231,0.15);border:1px solid rgba(108,92,231,0.3)}
.model-option .mo-icon{font-size:1.1rem}
.model-option .mo-name{font-weight:500}
.model-option .mo-spec{font-size:0.7rem;color:var(--text2);margin-top:1px}
.model-option .mo-check{display:none;margin-left:auto;color:var(--accent)}
.model-option.active .mo-check{display:block}
/* SCROLLBAR */
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--text2)}
/* RESPONSIVE */
@media(max-width:600px){
  .header{padding:0 1rem}
  .welcome h1{font-size:2rem}
  .model-grid{grid-template-columns:repeat(2,1fr)}
  .msg{max-width:95%}
  .input-bar{padding:1rem}
}
</style>
</head>
<body>
<div id="particles"></div>

<!-- HEADER -->
<header class="header">
  <div class="logo">
    <div class="logo-icon">⚡</div>
    AI Factory Router
  </div>
  <div class="header-right">
    <div class="model-badge">
      <span class="dot"></span>
      <span id="statusText">Connecté</span>
      <span class="model-count" id="modelCount">0 modèles</span>
    </div>
  </div>
</header>

<!-- CHAT -->
<div class="chat-container">
  <div id="welcome" class="welcome">
    <div class="welcome-badge">🧠 Multi-Model AI Router</div>
    <h1>Pose ta question<br>Je choisis le meilleur modèle</h1>
    <p>Analyse intelligente de ta requête pour sélectionner automatiquement l'IA la plus performante — code, raisonnement, créativité, traduction.</p>
    <div class="model-grid" id="modelGrid"></div>
    <button class="start-btn" onclick="document.getElementById('chatInput').focus()">
      ✨ Commencer à discuter
    </button>
  </div>
  <div id="messages" class="messages" style="display:none"></div>
  <div id="thinking" class="thinking">
    <div class="thinking-bar"></div>
    <span class="thinking-text" id="thinkingText">Réflexion en cours...</span>
  </div>
</div>

<!-- INPUT -->
<div class="input-bar">
  <div class="input-inner">
    <div class="model-selector">
      <button class="model-select-btn" id="modelSelectBtn" onclick="toggleModelDropdown()">
        <span>⚡</span>
        <span id="selectedModelName">Auto</span>
        <span style="font-size:0.6rem">▼</span>
      </button>
      <div class="model-dropdown" id="modelDropdown">
        <div class="model-option active" data-model="auto" onclick="selectModel('auto',this)">
          <span class="mo-icon">🤖</span>
          <div><div class="mo-name">Auto (Recommandé)</div><div class="mo-spec">Choisit le meilleur modèle</div></div>
          <span class="mo-check">✓</span>
        </div>
      </div>
    </div>
    <textarea id="chatInput" placeholder="Pose ta question... (Ex: 'Crée un site web avec React' ou 'Explique la théorie de la relativité')" rows="1" onkeydown="handleKey(event)"></textarea>
    <button id="sendBtn" onclick="sendMessage()">➤</button>
  </div>
</div>

<script>
const MODELS = {};
const MSG_HISTORY = [];
let isStreaming = false;

// PARTICULES
function createParticles() {
  const container = document.getElementById('particles');
  for (let i = 0; i < 50; i++) {
    const p = document.createElement('div');
    p.className = 'particle';
    p.style.left = Math.random() * 100 + '%';
    p.style.width = p.style.height = (1 + Math.random() * 3) + 'px';
    p.style.animationDuration = (15 + Math.random() * 25) + 's';
    p.style.animationDelay = -Math.random() * 30 + 's';
    p.style.opacity = 0.1 + Math.random() * 0.4;
    container.appendChild(p);
  }
}
createParticles();

// AUTO-RESIZE TEXTAREA
document.getElementById('chatInput').addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});

// KEY HANDLER
function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

// TOGGLE MODEL DROPDOWN
function toggleModelDropdown() {
  document.getElementById('modelDropdown').classList.toggle('show');
}
document.addEventListener('click', function(e) {
  if (!e.target.closest('.model-selector')) {
    document.getElementById('modelDropdown').classList.remove('show');
  }
});

function selectModel(modelId, el) {
  document.querySelectorAll('.model-option').forEach(o => o.classList.remove('active'));
  if (el) el.classList.add('active');
  const name = modelId === 'auto' ? 'Auto' : (MODELS[modelId]?.name || modelId);
  document.getElementById('selectedModelName').textContent = name;
  document.getElementById('modelDropdown').classList.remove('show');
}

// LOAD MODELS
async function loadModels() {
  try {
    const r = await fetch('/api/models');
    const data = await r.json();
    const grid = document.getElementById('modelGrid');
    const dropdown = document.getElementById('modelDropdown');
    grid.innerHTML = '';
    
    data.models.forEach(m => {
      MODELS[m.id] = m;
      // Card
      const card = document.createElement('div');
      card.className = 'model-card';
      const barColor = m.color || '#6c5ce7';
      card.innerHTML = '<div class="icon">' + (m.emoji || '🧠') + '</div><div class="name">' + m.name + '</div><div class="spec">' + m.specialty + '</div><div class="bar" style="width:0%;background:' + barColor + '"></div>';
      grid.appendChild(card);
      setTimeout(() => { card.querySelector('.bar').style.width = (m.quality * 10) + '%'; }, 200);
      
      // Dropdown option
      const opt = document.createElement('div');
      opt.className = 'model-option';
      opt.dataset.model = m.id;
      opt.onclick = function() { selectModel(m.id, this); };
      opt.innerHTML = '<span class="mo-icon">' + (m.emoji || '🧠') + '</span><div><div class="mo-name">' + m.name + '</div><div class="mo-spec">' + m.specialty + ' · ' + m.size + '</div></div><span class="mo-check">✓</span>';
      dropdown.appendChild(opt);
    });
    
    document.getElementById('modelCount').textContent = data.available + '/' + data.models.length + ' modèles';
  } catch(e) {
    document.getElementById('statusText').textContent = '⚠️ Erreur';
  }
}
loadModels();

// SEND MESSAGE
async function sendMessage() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text || isStreaming) return;
  
  input.value = '';
  input.style.height = 'auto';
  
  // Hide welcome
  document.getElementById('welcome').style.display = 'none';
  const msgContainer = document.getElementById('messages');
  msgContainer.style.display = 'flex';
  
  // Add user message
  addMessage(text, 'user');
  
  // Show thinking
  const thinking = document.getElementById('thinking');
  thinking.classList.add('active');
  document.getElementById('thinkingText').textContent = '🔍 Analyse de la requête...';
  
  isStreaming = true;
  document.getElementById('sendBtn').disabled = true;
  
  try {
    // Analyze
    const selectedBtn = document.querySelector('.model-option.active');
    let modelId = 'auto';
    if (selectedBtn && selectedBtn.dataset.model !== 'auto') {
      modelId = selectedBtn.dataset.model;
    }
    
    if (modelId === 'auto') {
      const analyzeR = await fetch('/api/analyze', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({query: text})
      });
      const analysis = await analyzeR.json();
      modelId = analysis.model;
      document.getElementById('thinkingText').textContent = '🧠 ' + (analysis.model_info?.emoji || '') + ' ' + (analysis.model_info?.name || modelId) + ' · Confiance ' + analysis.confidence + '%';
      await new Promise(r => setTimeout(r, 600));
    } else {
      document.getElementById('thinkingText').textContent = '⚡ Génération en cours...';
    }
    
    // Generate
    document.getElementById('thinkingText').textContent = '✍️ Génération de la réponse...';
    
    const msgDiv = document.createElement('div');
    msgDiv.className = 'msg assistant';
    const avatarColor = MODELS[modelId]?.color || '#6c5ce7';
    msgDiv.innerHTML = '<div class="msg-avatar" style="background:' + avatarColor + '20;border:1px solid ' + avatarColor + '40">' + (MODELS[modelId]?.emoji || '🤖') + '</div><div class="msg-content"><div class="model-tag" style="background:' + avatarColor + '20;color:' + avatarColor + '"><span class="emoji">' + (MODELS[modelId]?.emoji || '🤖') + '</span> ' + (MODELS[modelId]?.name || modelId) + '</div><div class="response-text"></div></div>';
    msgContainer.appendChild(msgDiv);
    
    const respText = msgDiv.querySelector('.response-text');
    
    // Stream response
    const streamR = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({query: text, model: modelId})
    });
    
    const reader = streamR.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});
      
      // Process SSE
      const lines = buffer.split('\\n');
      buffer = lines.pop() || '';
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.text) {
              respText.textContent += data.text;
              msgContainer.scrollTop = msgContainer.scrollHeight;
              window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});
            }
          } catch(e) {}
        }
      }
    }
    
  } catch(e) {
    addMessage('❌ Erreur: ' + e.message, 'assistant');
  }
  
  thinking.classList.remove('active');
  isStreaming = false;
  document.getElementById('sendBtn').disabled = false;
  document.getElementById('chatInput').focus();
}

function addMessage(text, role) {
  const container = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  if (role === 'user') {
    div.innerHTML = '<div class="msg-content">' + escapeHtml(text) + '</div><div class="msg-avatar" style="background:var(--gradient);color:white">👤</div>';
  } else {
    div.innerHTML = '<div class="msg-avatar" style="background:var(--bg3);border:1px solid var(--border)">🤖</div><div class="msg-content">' + escapeHtml(text) + '</div>';
  }
  container.appendChild(div);
  window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});
}

function escapeHtml(t) {
  const d = document.createElement('div');
  d.textContent = t;
  return d.innerHTML;
}
</script>
</body>
</html>"""

# ============================================
# ROUTES API
# ============================================

@app.get("/api/models")
async def api_models():
    available = await get_available_models()
    models_list = []
    for mid, info in MODELS.items():
        models_list.append({
            "id": mid,
            "name": info["name"],
            "emoji": info["emoji"],
            "color": info["color"],
            "specialty": info["specialty"],
            "speed": info["speed"],
            "size": info["size"],
            "quality": info["quality"],
            "available": mid in available
        })
    return {"models": models_list, "available": sum(1 for m in models_list if m["available"])}

@app.post("/api/analyze")
async def api_analyze(data: dict):
    query = data.get("query", "")
    result = await analyze_query(query)
    return result

@app.post("/api/chat")
async def api_chat(data: dict, request: Request):
    query = data.get("query", "")
    model = data.get("model", ROUTER_MODEL)
    search = data.get("search", True)
    
    async def stream():
        async for chunk in generate_response(query, model, search=search):
            if chunk:
                yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "data: [DONE]\n\n"
    
    from fastapi.responses import StreamingResponse
    return StreamingResponse(stream(), media_type="text/event-stream")

@app.get("/{path:path}")
async def serve_spa():
    return HTMLResponse(HTML_PAGE)

@app.get("/")
async def root():
    return HTMLResponse(HTML_PAGE)

if __name__ == "__main__":
    import uvicorn
    print(f"\n🚀 AI Factory Smart Router — http://0.0.0.0:{PORT}")
    print(f"   Ollama: {OLLAMA_URL}")
    print(f"   Routeur: {ROUTER_MODEL}")
    print(f"   Modèles: {len(MODELS)}\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
