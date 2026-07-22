#!/usr/bin/env python3
"""
============================================
AI FACTORY - Smart Router
============================================
Chat unique qui choisit automatiquement le
meilleur modèle pour chaque requête.

Architecture :
  Requête → Classifieur (phi4-mini / 1s) 
         → Routage vers le meilleur modèle
         → Réponse streamée

Modèles disponibles :
  💻 qwen2.5-coder:7b   → Code, debug, architecture
  ⚡ phi4-mini:3.8b      → Raisonnement rapide
  🎯 gemma4:4b          → Général polyvalent
  💬 llama3.2:3b         → Chat, créativité
  🧠 deepseek-r1:7b     → Problèmes complexes
============================================
"""

import json
import os
import httpx
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="AI Factory - Smart Router")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "phi4-mini:3.8b")

# ============================================
# Configuration du routage intelligent
# Chaque modèle avec ses spécialités
# ============================================
MODEL_ROUTES = {
    "💻 qwen2.5-coder:7b": {
        "keywords": ["code", "programmation", "python", "javascript", "react", "docker", "git", 
                    "bug", "débug", "algorithme", "fonction", "api", "backend", "frontend",
                    "html", "css", "typescript", "node", "sql", "base de données"],
        "priority": 1,
        "strength": "code"
    },
    "⚡ phi4-mini:3.8b": {
        "keywords": ["raisonne", "logique", "analyse", "math", "équation", "calcul",
                    "scientifique", "physique", "explique", "pourquoi", "comment",
                    "problème", "solution", "prouve", "démontre"],
        "priority": 2,
        "strength": "reasoning"
    },
    "🧠 deepseek-r1:7b": {
        "keywords": ["stratégie", "architecture", "plan", "conception", "design pattern",
                    "complexe", "système", "optimisation", "performance", "sécurité",
                    "réfléchis", "analyse approfondie", "comparaison"],
        "priority": 3,
        "strength": "deep"
    },
    "🎯 gemma4:4b": {
        "keywords": ["traduis", "résume", "explique simplement", "vulgarise",
                    "conseil", "recommandation", "comparatif", "avis",
                    "général", "culture", "histoire", "géographie"],
        "priority": 4,
        "strength": "general"
    },
    "💬 llama3.2:3b": {
        "keywords": ["écris", "rédige", "poème", "histoire", "créatif",
                    "blague", "humour", "inspiration", "idée", "brainstorming",
                    "conversation", "discussion", "avis personnel"],
        "priority": 5,
        "strength": "creative"
    }
}

# ============================================
# Interface HTML du chat unique
# ============================================
HTML_PAGE = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🧠 AI Factory - Smart Chat</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',sans-serif;background:#0a0b1a;color:#e2e8f0;height:100vh;display:flex;flex-direction:column}
.header{background:rgba(15,17,48,0.9);border-bottom:1px solid rgba(255,255,255,0.1);padding:1rem 2rem;display:flex;align-items:center;justify-content:space-between;backdrop-filter:blur(10px)}
.header h1{font-size:1.1rem;font-weight:600;background:linear-gradient(135deg,#6c5ce7,#00cec9);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.model-badge{font-size:0.75rem;padding:0.25rem 0.75rem;border-radius:20px;background:rgba(108,92,231,0.15);color:#a29bfe;display:none}
.model-badge.visible{display:inline-flex;align-items:center;gap:0.4rem}
.chat-container{flex:1;overflow-y:auto;padding:1.5rem 2rem;display:flex;flex-direction:column;gap:1rem}
.message{max-width:80%;padding:1rem 1.25rem;border-radius:16px;animation:fadeIn 0.3s ease;line-height:1.6;font-size:0.9rem}
.message.user{background:rgba(108,92,231,0.15);align-self:flex-end;border-bottom-right-radius:4px}
.message.assistant{background:rgba(255,255,255,0.05);align-self:flex-start;border-bottom-left-radius:4px;border:1px solid rgba(255,255,255,0.05)}
.message .model-tag{font-size:0.7rem;color:#00cec9;margin-bottom:0.5rem;display:flex;align-items:center;gap:0.4rem}
.message .model-tag.thinking{color:#fdcb6e}
.message .model-tag.code{color:#6c5ce7}
.message .model-tag.creative{color:#fd79a8}
.message .model-tag.reasoning{color:#00cec9}
.typing{display:flex;gap:4px;padding:0.5rem 0}
.typing span{width:8px;height:8px;background:#6c5ce7;border-radius:50%;animation:bounce 1.4s infinite ease-in-out}
.typing span:nth-child(2){animation-delay:0.2s}
.typing span:nth-child(3){animation-delay:0.4s}
@keyframes bounce{0%,80%,100%{transform:scale(0.6)}40%{transform:scale(1)}}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.input-area{background:rgba(15,17,48,0.9);border-top:1px solid rgba(255,255,255,0.1);padding:1rem 2rem}
.input-wrapper{display:flex;gap:0.75rem;align-items:center;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:12px;padding:0.5rem 1rem;transition:border-color 0.3s}
.input-wrapper:focus-within{border-color:#6c5ce7}
.input-wrapper input{flex:1;background:none;border:none;color:#e2e8f0;font-size:0.95rem;outline:none;padding:0.25rem 0;font-family:'Inter',sans-serif}
.input-wrapper input::placeholder{color:#4a5568}
.send-btn{background:#6c5ce7;border:none;color:white;width:36px;height:36px;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.3s;font-size:1.1rem}
.send-btn:hover{background:#5a4bd1;transform:scale(1.05)}
.send-btn:disabled{opacity:0.5;cursor:not-allowed}
.routing-info{font-size:0.75rem;color:#4a5568;text-align:center;padding:0.5rem;display:none}
.routing-info.visible{display:block}
pre{background:rgba(0,0,0,0.3);padding:1rem;border-radius:8px;overflow-x:auto;font-size:0.8rem;margin:0.5rem 0;border:1px solid rgba(255,255,255,0.05)}
code{font-family:'JetBrains Mono',monospace}
</style>
</head>
<body>

<div class="header">
    <h1>🧠 Smart Chat — AI Factory</h1>
    <span class="model-badge" id="modelBadge">🤖 Routage automatique</span>
</div>

<div class="chat-container" id="chatContainer">
    <div class="message assistant" style="align-self:center;max-width:60%;text-align:center;background:rgba(108,92,231,0.05);border-color:rgba(108,92,231,0.1)">
        <div style="font-size:2rem;margin-bottom:0.5rem">🧠</div>
        <div style="font-weight:500;margin-bottom:0.25rem">Smart Chat prêt</div>
        <div style="font-size:0.8rem;color:#8b8fa3">
            Je choisis automatiquement le meilleur modèle pour chaque requête.<br>
            Code → 💻 Qwen · Raisonnement → ⚡ Phi-4 · Général → 🎯 Gemma · Créatif → 💬 Llama
        </div>
    </div>
</div>

<div class="input-area">
    <div class="routing-info" id="routingInfo">🧠 Analyse du message...</div>
    <div class="input-wrapper">
        <input type="text" id="chatInput" placeholder="Pose ta question..." autofocus>
        <button class="send-btn" id="sendBtn" onclick="sendMessage()">➤</button>
    </div>
</div>

<script>
let isProcessing = false;
const chatContainer = document.getElementById('chatContainer');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const modelBadge = document.getElementById('modelBadge');
const routingInfo = document.getElementById('routingInfo');

chatInput.addEventListener('keydown', e => { if(e.key === 'Enter') sendMessage(); });

function addMessage(content, role, model = null) {
    const div = document.createElement('div');
    div.className = `message ${role}`;
    if (model) {
        const modelColors = {coder:'code',phi:'reasoning',deepseek:'thinking',gemma:'general',llama:'creative'};
        const cls = Object.entries(modelColors).find(([k]) => model.includes(k))?.[1] || '';
        div.innerHTML = `<div class="model-tag ${cls}">🎯 ${model}</div><div class="msg-content">${content}</div>`;
    } else {
        div.innerHTML = `<div class="msg-content">${content}</div>`;
    }
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return div;
}

function showTyping() {
    const div = document.createElement('div');
    div.className = 'message assistant';
    div.id = 'typingIndicator';
    div.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function removeTyping() {
    const el = document.getElementById('typingIndicator');
    if(el) el.remove();
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if(!text || isProcessing) return;
    
    chatInput.value = '';
    addMessage(text, 'user');
    showTyping();
    isProcessing = true;
    sendBtn.disabled = true;
    routingInfo.classList.add('visible');
    routingInfo.textContent = '🧠 Analyse du message pour choisir le meilleur modèle...';
    
    try {
        const resp = await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: text})
        });
        
        if(!resp.ok) throw new Error('Erreur serveur');
        
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let fullResponse = '';
        let currentModel = '';
        
        removeTyping();
        
        // Créer le message assistant
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message assistant';
        const modelTag = document.createElement('div');
        modelTag.className = 'model-tag';
        const contentDiv = document.createElement('div');
        contentDiv.className = 'msg-content';
        msgDiv.appendChild(modelTag);
        msgDiv.appendChild(contentDiv);
        chatContainer.appendChild(msgDiv);
        
        while(true) {
            const {done, value} = await reader.read();
            if(done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\\n').filter(l => l.trim());
            
            for(const line of lines) {
                if(line.startsWith('data: ')) {
                    const data = JSON.parse(line.slice(6));
                    if(data.model) {
                        currentModel = data.model;
                        const emoji = data.model.includes('coder') ? '💻' : 
                                     data.model.includes('phi') ? '⚡' :
                                     data.model.includes('deepseek') ? '🧠' :
                                     data.model.includes('gemma') ? '🎯' : '💬';
                        modelTag.innerHTML = `${emoji} ${data.model}`;
                        modelBadge.classList.add('visible');
                        routingInfo.classList.remove('visible');
                    }
                    if(data.content) {
                        fullResponse += data.content;
                        contentDiv.innerHTML = marked(fullResponse);
                        chatContainer.scrollTop = chatContainer.scrollHeight;
                    }
                    if(data.done) {
                        modelTag.innerHTML += ' ✅';
                    }
                }
            }
        }
    } catch(e) {
        removeTyping();
        addMessage('❌ Erreur: ' + e.message, 'assistant');
    }
    
    isProcessing = false;
    sendBtn.disabled = false;
}

function marked(text) {
    return text.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, '<pre><code>$2</code></pre>')
               .replace(/`([^`]+)`/g, '<code>$1</code>')
               .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
               .replace(/\\n/g, '<br>');
}
</script>
</body>
</html>
"""


# ============================================
# ROUTAGE INTELLIGENT
# ============================================
async def classify_intent(message: str) -> str:
    """Utilise un petit modèle pour classifier rapidement l'intention."""
    prompt = f"""Analyse ce message et réponds UNIQUEMENT par le nom du modèle le plus adapté parmi cette liste:
- qwen2.5-coder:7b (pour code, programmation, debug)
- phi4-mini:3.8b (pour analyse rapide, logique, maths, sciences)
- deepseek-r1:7b (pour problèmes complexes, stratégie, architecture)
- gemma4:4b (pour général, traduction, résumé, conseils)
- llama3.2:3b (pour créatif, écriture, humour, discussion)

Message: {message[:300]}
Modèle:"""

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json={
                "model": ROUTER_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 20, "temperature": 0.1}
            })
            if resp.status_code == 200:
                result = resp.json().get("response", "").strip().lower()
                # Trouver le meilleur modèle
                for model in MODEL_ROUTES:
                    if model.split(" ")[-1] in result or model.split("/")[-1].split(":")[0] in result:
                        return model
                # Fallback: keyword matching
                best_model = "🎯 gemma4:4b"
                best_score = 0
                for model, config in MODEL_ROUTES.items():
                    score = sum(1 for kw in config["keywords"] if kw.lower() in message.lower())
                    if score > best_score:
                        best_score = score
                        best_model = model
                return best_model
    except Exception as e:
        print(f"[ROUTER] Classification error: {e}")
    
    # Fallback
    return "🎯 gemma4:4b"


async def stream_model(model_name: str, messages: list):
    """Stream la réponse du modèle choisi."""
    model_id = model_name.split(" ")[-1]
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Récupérer le dernier message utilisateur
            last_msg = messages[-1]["content"] if messages else ""
            
            async with client.stream("POST", f"{OLLAMA_URL}/api/generate", json={
                "model": model_id,
                "prompt": f"Tu es un assistant IA utile, précis et concis. Réponds en français.\n\nUtilisateur: {last_msg}\n\nAssistant:",
                "stream": True,
                "options": {"temperature": 0.7, "num_predict": 2048}
            }) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if data.get("response"):
                                yield f"data: {json.dumps({'content': data['response'], 'model': model_id})}\n\n"
                            if data.get("done"):
                                yield f"data: {json.dumps({'done': True, 'model': model_id})}\n\n"
                                return
                        except json.JSONDecodeError:
                            continue
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


# ============================================
# ROUTES API
# ============================================
@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(HTML_PAGE)

@app.get("/api/models")
async def list_models():
    """Liste les modèles disponibles."""
    models = []
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            if resp.status_code == 200:
                for m in resp.json().get("models", []):
                    models.append(m["name"])
    except Exception:
        pass
    return {"models": models, "router_model": ROUTER_MODEL, "routes": list(MODEL_ROUTES.keys())}

@app.post("/api/chat")
async def chat(request: Request):
    """Point d'entrée unique du chat intelligent."""
    data = await request.json()
    message = data.get("message", "")
    
    if not message:
        return JSONResponse({"error": "Message requis"}, status_code=400)
    
    async def generate():
        # 1. Router le message vers le meilleur modèle
        yield f"data: {json.dumps({'info': '🧠 Analyse...'})}\n\n"
        best_model = await classify_intent(message)
        yield f"data: {json.dumps({'info': f'🎯 Routage vers {best_model}'})}\n\n"
        
        # 2. Stream la réponse
        async for chunk in stream_model(best_model, [{"role": "user", "content": message}]):
            yield chunk
    
    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8765"))
    uvicorn.run(app, host="0.0.0.0", port=port)
