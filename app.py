"""
AkyelIA - Assistant de Codage Multi-LLM
"""
import json
import os
import uuid
import shutil
import subprocess
import base64
import mimetypes
from pathlib import Path
from datetime import datetime

import httpx
import asyncio
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import config
from llm_providers import get_provider, get_available_providers
from db import Database, IS_POSTGRES, init_database

app = FastAPI(title="AkyelIA", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

API_KEYS_PATH = BASE_DIR / config.api_keys_file
SKILLS_DIR = BASE_DIR / "skills"
SKILLS_DIR.mkdir(exist_ok=True)
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# Types de fichiers reconnus
TEXT_EXTENSIONS = {".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss", ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".sh", ".bat", ".ps1", ".sql", ".r", ".go", ".rs", ".java", ".cpp", ".c", ".h", ".hpp", ".swift", ".kt", ".rb", ".php", ".pl", ".lua", ".dart", ".scala", ".clj", ".ex", ".exs", ".vue", ".svelte", ".astro", ".csv", ".env"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico"}
CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".scss", ".json", ".xml", ".yaml", ".yml", ".sql", ".sh", ".bat", ".go", ".rs", ".java", ".cpp", ".c", ".h", ".swift", ".kt", ".rb", ".php", ".lua", ".dart", ".vue", ".svelte", ".astro"}


# ============================================
# DATABASE - Utilise db.py (SQLite local / PostgreSQL sur Render)
# ============================================


# ============================================
# API KEYS
# ============================================
def load_api_keys() -> dict:
    if API_KEYS_PATH.exists():
        try:
            return json.loads(API_KEYS_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_api_keys(keys: dict):
    API_KEYS_PATH.write_text(json.dumps(keys, indent=2))
    for k, v in keys.items():
        if v:
            os.environ[k] = v


# ============================================
# SKILLS HELPERS
# ============================================
def extract_readme_text(repo_path: Path) -> str:
    """Extract description from README."""
    for name in ["README.md", "README.txt", "README", "readme.md"]:
        readme = repo_path / name
        if readme.exists():
            text = readme.read_text(encoding="utf-8", errors="ignore")
            # Extract first paragraph (up to 300 chars)
            lines = text.split("\n")
            desc_lines = []
            for line in lines:
                if line.startswith("#"):
                    continue
                if line.strip():
                    desc_lines.append(line.strip())
                    if len(" ".join(desc_lines)) > 300:
                        break
            return " ".join(desc_lines)[:300]
    return "Skill installe avec succes. Consulte le README pour plus de details."


def get_repo_author(repo_url: str) -> str:
    """Extract author/owner from GitHub URL."""
    url = repo_url.rstrip("/").replace(".git", "")
    if "github.com" in url:
        parts = url.split("github.com/")[-1].split("/")
        return parts[0] if len(parts) > 0 else ""
    return ""


def get_repo_full_name(repo_url: str) -> str:
    """Extract owner/repo from GitHub URL."""
    url = repo_url.rstrip("/").replace(".git", "")
    if "github.com" in url:
        return url.split("github.com/")[-1]
    return url.split("/")[-1] if "/" in url else url


# ============================================
# OMNIROUTE AUTO-START
# ============================================
OMNIROUTE_URL = "http://localhost:20128"

async def ensure_omniroute():
    """Verifie si OmniRoute tourne, sinon le demarre."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OMNIROUTE_URL}/v1/models")
            if r.status_code == 200:
                print(f"[OK] OmniRoute deja en ligne sur {OMNIROUTE_URL}")
                return
    except Exception:
        pass
    
    # OmniRoute ne repond pas, on le lance
    print("[INFO] Demarrage d'OmniRoute...")
    try:
        process = await asyncio.create_subprocess_shell(
            "npx omniroute serve --port 20128 --daemon",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.sleep(5)
        print(f"[OK] OmniRoute lance sur {OMNIROUTE_URL}")
    except Exception as e:
        print(f"[WARN] Impossible de demarrer OmniRoute: {e}")
        print("[WARN] Lance-le manuellement : npx omniroute serve")


# ============================================
# FREE-FIRST ROUTING - Cascade multi-providers 100% gratuite
# ============================================
# Stratégie : essayer les modèles gratuits d'abord, les quasi-gratuits ensuite,
# et les payants en TOUT dernier recours. Les tokens sont précieux !

# 🆓 FREE_MODEL_CHAIN : Modèles open-source/rate-limités connus pour être gratuits
# Ces modèles sont accessibles via OpenRouter sans carte bancaire
FREE_MODEL_CHAIN = [
    # 🥇 TIER 1 - Gratuits 100% (même sans crédit OpenRouter)
    "google/gemini-2.0-flash",                    # 🆓 Gemini Flash - rapide, polyvalent
    "google/gemini-2.0-flash-lite",               # 🆓 Gemini Flash Lite - ultra léger
    "meta-llama/llama-3.3-70b-instruct",          # 🆓 Llama 3.3 70B - excellent raisonnement
    "mistralai/mistral-small-24b-instruct-2501",   # 🆓 Mistral Small - nouveau gratuit
    # 🥈 TIER 2 - Quasi gratuits (quelques centimes pour 1M tokens)
    "deepseek/deepseek-chat",                      # 💰 DeepSeek V3 - $0.014/M tokens (quasi rien)
    "qwen/qwen-2.5-72b-instruct",                  # 💰 Qwen 2.5 - excellent rapport qualité/prix
    # 🥉 TIER 3 - Fallback gratuits supplémentaires
    "microsoft/phi-4-mini-instruct",
    "qwen/qwen-2.5-coder-32b-instruct",
]

# 💎 PAID_MODEL_CHAIN : Modèles payants (dernier recours)
PAID_MODEL_CHAIN = [
    "anthropic/claude-sonnet-4",    # 💎 Claude - seulement si nécessaire
    "openai/gpt-4o",               # 💎 GPT-4o - seulement si nécessaire
]

# SMART_MODEL_CHAIN : Chaîne de fallback par provider
# Chaque provider a sa propre liste de modèles du + gratuit/rapide au + payant/puissant
SMART_MODEL_CHAIN = {
    "openrouter": FREE_MODEL_CHAIN + PAID_MODEL_CHAIN,
    "omniroute": [
        # ⚠️ OmniRoute nécessite un serveur local - indisponible sur Render
        "auto/best-free",
        "auto/coding:free",
        "auto/smart",
    ],
    "deepseek": [
        "deepseek-chat",              # 🧠 DeepSeek - excellent code, quasi gratuit
        "deepseek-reasoner",
    ],
}

# FREE_FALLBACK : Modèle de dernier recours si tout échoue
DEFAULT_FALLBACK = "google/gemini-2.0-flash"


# ============================================
# PYDANTIC MODELS
# ============================================
class ChatRequest(BaseModel):
    message: str
    provider: str = "openrouter"
    model: str | None = None
    conversation_id: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: str = "Tu es Akyel AI, un assistant de codage stratégique orchestré par un routage intelligent. Tu utilises automatiquement le meilleur modèle disponible pour chaque tâche (code, raisonnement, créativité). Tu aides les utilisateurs à coder avec des explications claires et précises. Tu réponds en français."
    smart_mode: bool = False
    files: list[dict] = []  # Fichiers attachés: [{id, name, type, content?, path?}]

class SaveKeysRequest(BaseModel):
    keys: dict[str, str]

class InstallSkillRequest(BaseModel):
    repo_url: str

class AgentCreate(BaseModel):
    name: str
    description: str = ""
    system_prompt: str = ""
    provider: str = "openrouter"
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    icon: str = "🤖"
    color: str = "#7c3aed"

class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    icon: str | None = None
    color: str | None = None

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    language: str = "python"
    icon: str = "📁"

class ProjectFileSave(BaseModel):
    path: str
    content: str = ""
    language: str = ""


# ============================================
# ROUTES
# ============================================
@app.on_event("startup")
async def startup():
    await init_database()
    # Demarrage automatique d'OmniRoute si c'est le provider par defaut
    if config.default_provider == "omniroute":
        asyncio.create_task(ensure_omniroute())


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = static_dir / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>AkyelIA - Interface non trouvée</h1>")


# ========== PROVIDERS ==========
@app.get("/api/config")
async def app_config():
    """Return app configuration."""
    return {
        "default_provider": config.default_provider,
        "app_name": "Akyel AI",
        "version": "2.0.0",
    }


@app.get("/api/models")
async def list_models():
    providers = get_available_providers()
    saved_keys = load_api_keys()
    for name, p in config.providers.items():
        if name in providers:
            env_val = os.getenv(p.api_key_env, "") or saved_keys.get(p.api_key_env, "")
            providers[name]["has_key"] = bool(env_val)
            providers[name]["available"] = providers[name]["available"] or bool(env_val)
            providers[name]["setup_url"] = p.setup_url
            providers[name]["api_key_env"] = p.api_key_env
            providers[name]["requires_key"] = p.requires_key
    return {"providers": providers}


# ========== CHAT ==========
@app.post("/api/chat")
async def chat(request: ChatRequest):
    provider_name = request.provider
    if provider_name not in config.providers:
        raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' introuvable")

    provider = get_provider(provider_name)
    if provider is None:
        raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' non disponible")

    if not provider.is_available:
        saved_keys = load_api_keys()
        env_key = saved_keys.get(config.providers[provider_name].api_key_env, "")
        if env_key:
            provider.api_key = env_key
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{provider.config.display_name}' n'est pas configuré. Va dans Paramètres > Clés API."
            )

    conv_id = request.conversation_id or str(uuid.uuid4())
    db = await Database.open()
    
    # Setup DB : créer/charger conversation, message utilisateur
    try:
        cursor = await db.execute("SELECT id FROM conversations WHERE id = ?", (conv_id,))
        existing = await cursor.fetchone()
        if not existing:
            await db.execute(
                "INSERT INTO conversations (id, provider, model) VALUES (?, ?, ?)",
                (conv_id, provider_name, request.model or provider.config.default_model)
            )
            await db.commit()

        cursor = await db.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id", (conv_id,)
        )
        rows = await cursor.fetchall()
        history = [{"role": row["role"], "content": row["content"]} for row in rows]

        # Si des fichiers sont attachés, construire le message enrichi
        user_content = build_user_message(request.message, request.files) if request.files else request.message
        
        messages = [{"role": "system", "content": request.system_prompt}]
        messages.extend(history[-config.max_history:])
        messages.append({"role": "user", "content": user_content})
        
        # Sauvegarder le message original (sans le contenu des fichiers pour la lisibilité)
        display_content = request.message
        if request.files:
            file_names = [f.get("name", "fichier") for f in request.files]
            display_content += f"\n[📎 Fichiers: {', '.join(file_names)}]"
        
        await db.execute(
            "INSERT INTO messages (conversation_id, role, content, provider, model) VALUES (?, ?, ?, ?, ?)",
            (conv_id, "user", display_content, provider_name, request.model)
        )

        if not history:
            title = request.message[:50] + ("..." if len(request.message) > 50 else "")
            await db.execute(
                "UPDATE conversations SET title = ?, provider = ?, model = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (title, provider_name, request.model or provider.config.default_model, conv_id)
            )
        else:
            await db.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conv_id,))
        await db.commit()
    except Exception:
        await db.close()
        raise
    
    # ===== FREE-FIRST ROUTING : cascade gratuite puis payante =====
    models_to_try = []
    # Si le provider a une chaîne SMART_MODEL_CHAIN, on l'utilise
    # (cela active le free-first routing pour openrouter + tous les autres)
    chain = SMART_MODEL_CHAIN.get(provider_name, None)
    if chain:
        models_to_try = list(chain)
        # Si l'utilisateur a demandé un modèle spécifique, le mettre en premier
        if request.model and request.model not in models_to_try:
            models_to_try.insert(0, request.model)
        # Si smart_mode est activé, ajouter les modèles payants à la fin
        if request.smart_mode:
            for m in PAID_MODEL_CHAIN:
                if m not in models_to_try:
                    models_to_try.append(m)
        # Message informatif sur le mode Free-First
        free_count = sum(1 for m in models_to_try if 'free' in m or 'flash' in m.lower() or 'gemini' in m.lower())
        print(f"[FREE-FIRST] {provider_name}: {len(models_to_try)} modeles, {free_count} gratuits en tete")
    else:
        # Pas de chaîne définie pour ce provider → utiliser le modèle par défaut
        models_to_try = [request.model or provider.config.default_model]
    
    async def generate():
        last_error = None
        try:
            for model_idx, try_model in enumerate(models_to_try):
                try:
                    full_response = ""
                    model_used = try_model
                    
                    if len(models_to_try) > 1:
                        if model_idx == 0:
                            yield f"data: {json.dumps({'info': f'⚡ Routage vers le meilleur modèle...', 'conversation_id': conv_id})}\n\n"
                        elif model_idx == 1:
                            yield f"data: {json.dumps({'info': f'🔄 Fallback vers modèle secondaire...', 'conversation_id': conv_id})}\n\n"
                        else:
                            yield f"data: {json.dumps({'info': f'🔄 Tentative {model_idx+1}/{len(models_to_try)}...', 'conversation_id': conv_id})}\n\n"
                    
                    async for chunk in provider.chat_stream(
                        messages=messages, model=try_model,
                        temperature=request.temperature, max_tokens=request.max_tokens,
                    ):
                        full_response += chunk
                        yield f"data: {json.dumps({'content': chunk, 'conversation_id': conv_id, 'model_used': model_used})}\n\n"
                    
                    # Si réponse vide et qu'on a d'autres modèles à essayer, fallback
                    if not full_response.strip() and model_idx < len(models_to_try) - 1:
                        last_error = "Réponse vide"
                        yield f"data: {json.dumps({'info': f'⚠️ {try_model} a retourné une réponse vide... Passage au suivant'})}\n\n"
                        continue
                    
                    # Succès ! Sauvegarder avec la connexion db
                    await db.execute(
                        "INSERT INTO messages (conversation_id, role, content, provider, model) VALUES (?, ?, ?, ?, ?)",
                        (conv_id, "assistant", full_response, provider_name, model_used)
                    )
                    await db.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conv_id,))
                    if not history and full_response[:20]:
                        await db.execute(
                            "UPDATE conversations SET title = ? WHERE id = ? AND title = 'Nouvelle conversation'",
                            ("Discussion code", conv_id)
                        )
                    if model_used != (request.model or provider.config.default_model):
                        await db.execute(
                            "UPDATE conversations SET model = ? WHERE id = ?",
                            (model_used, conv_id)
                        )
                    await db.commit()
                    
                    yield f"data: {json.dumps({'done': True, 'conversation_id': conv_id, 'model_used': model_used})}\n\n"
                    return
                    
                except Exception as e:
                    last_error = str(e)
                    if model_idx < len(models_to_try) - 1:
                        yield f"data: {json.dumps({'info': f'⚠️ {try_model} indisponible: {last_error[:50]}... Passage au suivant'})}\n\n"
                        continue
            
            yield f"data: {json.dumps({'error': f'Tous les modèles ont échoué. Dernière erreur: {last_error[:200]}', 'conversation_id': conv_id})}\n\n"
        finally:
            await db.close()
    
    return StreamingResponse(generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


# ========== CONVERSATIONS ==========
@app.get("/api/conversations")
async def list_conversations():
    db = await Database.open()
    try:
        cursor = await db.execute(
            "SELECT id, title, provider, model, created_at, updated_at "
            "FROM conversations ORDER BY updated_at DESC LIMIT 50"
        )
        return {"conversations": [dict(r) for r in await cursor.fetchall()]}
    finally:
        await db.close()


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    db = await Database.open()
    try:
        cursor = await db.execute(
            "SELECT id, title, provider, model, created_at, updated_at FROM conversations WHERE id = ?", (conv_id,)
        )
        conv = await cursor.fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation introuvable")
        cursor = await db.execute(
            "SELECT role, content, provider, model, created_at FROM messages WHERE conversation_id = ? ORDER BY id", (conv_id,)
        )
        return {"conversation": dict(conv), "messages": [dict(m) for m in await cursor.fetchall()]}
    finally:
        await db.close()


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    db = await Database.open()
    try:
        await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
        await db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


@app.post("/api/conversations/clear")
async def clear_conversation(request: Request):
    data = await request.json()
    conv_id = data.get("conversation_id")
    if conv_id:
        db = await Database.open()
        try:
            await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            await db.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conv_id,))
            await db.commit()
        finally:
            await db.close()
    return {"status": "ok"}


@app.put("/api/conversations/{conv_id}/title")
async def update_conversation_title(conv_id: str, request: Request):
    data = await request.json()
    title = data.get("title", "")
    db = await Database.open()
    try:
        await db.execute("UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (title, conv_id))
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


# ========== API KEYS ==========
@app.get("/api/settings/keys")
async def get_api_keys():
    saved = load_api_keys()
    result = {}
    for name, p in config.providers.items():
        env_val = os.getenv(p.api_key_env, "") or saved.get(p.api_key_env, "")
        result[p.api_key_env] = {
            "has_key": bool(env_val), "key_name": p.api_key_env,
            "masked_key": env_val[:8] + "..." + env_val[-4:] if len(env_val) > 12 else "",
        }
    return {"keys": result}


@app.post("/api/settings/keys")
async def save_api_keys_endpoint(request: SaveKeysRequest):
    existing = load_api_keys()
    existing.update(request.keys)
    save_api_keys(existing)
    return {"status": "ok", "saved": list(request.keys.keys())}


# ========== SKILLS ==========

# Cloner un repo GitHub en skill (helper)
async def _clone_and_install(repo_url: str, db) -> dict | str:
    """Clone a repo and return skill info or error message."""
    repo_full = get_repo_full_name(repo_url)
    author = get_repo_author(repo_url)
    skill_name = repo_full.split("/")[-1] if "/" in repo_full else repo_full
    
    # Check if already installed
    cursor = await db.execute("SELECT id FROM skills WHERE repo_url = ? OR name = ?", (repo_url, skill_name))
    existing = await cursor.fetchone()
    if existing:
        return f"Déjà installé: {skill_name}"
    
    repo_path = SKILLS_DIR / skill_name
    if repo_path.exists():
        shutil.rmtree(repo_path)
    
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(repo_path)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            return f"Erreur git {skill_name}: {result.stderr[:100]}"
    except subprocess.TimeoutExpired:
        return f"Timeout: {skill_name}"
    except Exception as e:
        return f"Erreur: {skill_name} - {str(e)[:100]}"
    
    description = extract_readme_text(repo_path)
    
    await db.execute(
        "INSERT INTO skills (name, repo_url, description, author, skill_path, repo_full_name) VALUES (?, ?, ?, ?, ?, ?)",
        (skill_name, repo_url, description, author, str(repo_path), repo_full)
    )
    await db.commit()
    return {"name": skill_name, "description": description[:100]}


@app.post("/api/skills/install-trending")
async def install_trending():
    """Install all trending AI repos as skills."""
    db = await Database.open()
    results = {"success": [], "skipped": [], "errors": []}
    try:
        for repo_url in TRENDING_AI_REPOS:
            result = await _clone_and_install(repo_url, db)
            if isinstance(result, dict):
                results["success"].append(result)
            elif result.startswith("Déjà"):
                results["skipped"].append(result)
            else:
                results["errors"].append(result)
    finally:
        await db.close()
    return results


@app.post("/api/skills/install-multiple")
async def install_multiple(request: Request):
    """Install multiple repos from a list of URLs."""
    data = await request.json()
    urls = data.get("urls", [])
    if not urls:
        raise HTTPException(status_code=400, detail="Liste d'URLs requise")
    if len(urls) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 repos à la fois")
    
    db = await Database.open()
    results = {"success": [], "skipped": [], "errors": []}
    try:
        for repo_url in urls:
            result = await _clone_and_install(repo_url, db)
            if isinstance(result, dict):
                results["success"].append(result)
            elif result.startswith("Déjà"):
                results["skipped"].append(result)
            else:
                results["errors"].append(result)
    finally:
        await db.close()
    return results
@app.get("/api/skills")
async def list_skills():
    """List all installed skills."""
    db = await Database.open()
    try:
        cursor = await db.execute(
            "SELECT id, name, repo_url, description, author, installed_at, enabled, skill_path, repo_full_name "
            "FROM skills ORDER BY installed_at DESC"
        )
        skills = [dict(r) for r in await cursor.fetchall()]
        # Check which repos still exist on disk
        for s in skills:
            repo_path = Path(s["skill_path"])
            s["on_disk"] = repo_path.exists()
            s["file_count"] = len(list(repo_path.rglob("*"))) if repo_path.exists() else 0
        return {"skills": skills}
    finally:
        await db.close()


@app.post("/api/skills/install")
async def install_skill(request: InstallSkillRequest):
    """Install a skill from a GitHub repo."""
    repo_url = request.repo_url.strip()
    if not repo_url:
        raise HTTPException(status_code=400, detail="URL du repo requis")

    # Validate URL
    if not repo_url.startswith(("https://github.com/", "http://github.com/", "git@github.com:")):
        raise HTTPException(status_code=400, detail="Seules les URLs GitHub sont supportées")

    repo_full = get_repo_full_name(repo_url)
    author = get_repo_author(repo_url)
    skill_name = repo_full.split("/")[-1] if "/" in repo_full else repo_full

    # Check if already installed
    db = await Database.open()
    try:
        cursor = await db.execute("SELECT id FROM skills WHERE repo_url = ? OR name = ?", (repo_url, skill_name))
        existing = await cursor.fetchone()
        if existing:
            raise HTTPException(status_code=400, detail=f"Le skill '{skill_name}' est déjà installé")

        # Clone the repo
        repo_path = SKILLS_DIR / skill_name
        if repo_path.exists():
            shutil.rmtree(repo_path)

        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(repo_path)],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode != 0:
                raise HTTPException(status_code=400, detail=f"Erreur git: {result.stderr[:200]}")
        except FileNotFoundError:
            raise HTTPException(status_code=400, detail="Git n'est pas installé sur ce serveur")
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=400, detail="Timeout: le clone a pris trop de temps")

        # Extract description
        description = extract_readme_text(repo_path)

        # Find skill files
        skill_files = []
        for f in repo_path.rglob("*"):
            if f.is_file() and f.suffix in [".md", ".yaml", ".yml", ".json", ".txt", ".py", ".js", ".sh"]:
                skill_files.append(str(f.relative_to(repo_path)))

        await db.execute(
            "INSERT INTO skills (name, repo_url, description, author, skill_path, repo_full_name) VALUES (?, ?, ?, ?, ?, ?)",
            (skill_name, repo_url, description, author, str(repo_path), repo_full)
        )
        await db.commit()

        return {
            "status": "ok",
            "skill": {
                "name": skill_name,
                "repo_url": repo_url,
                "author": author,
                "description": description[:150] + ("..." if len(description) > 150 else ""),
                "files": skill_files[:20],
                "total_files": len(skill_files),
            }
        }
    finally:
        await db.close()


@app.post("/api/skills/scan")
async def scan_skills():
    """Scan local skills directory and sync with database."""
    db = await Database.open()
    try:
        # Get existing skills
        cursor = await db.execute("SELECT id, name, skill_path FROM skills")
        existing = {row["name"]: dict(row) for row in await cursor.fetchall()}

        # Scan disk
        if not SKILLS_DIR.exists():
            return {"skills": [], "removed": [], "added": []}

        on_disk = set()
        for item in SKILLS_DIR.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                name = item.name
                on_disk.add(name)
                if name not in existing:
                    # New skill found on disk, add to DB
                    desc = extract_readme_text(item)
                    author = ""
                    readme = item / "README.md"
                    if readme.exists():
                        for line in readme.read_text().split("\n"):
                            if line.startswith("#") and " " in line:
                                name_in_readme = line.replace("#", "").strip()
                                break
                    await db.execute(
                        "INSERT INTO skills (name, repo_url, description, author, skill_path) VALUES (?, ?, ?, ?, ?)",
                        (name, f"https://github.com/local/{name}", desc, author, str(item))
                    )

        # Mark removed skills
        removed = []
        for name, skill in existing.items():
            if name not in on_disk:
                await db.execute("DELETE FROM skills WHERE id = ?", (skill["id"],))
                removed.append(name)

        await db.commit()

        cursor = await db.execute(
            "SELECT id, name, repo_url, description, author, installed_at, enabled, skill_path, repo_full_name "
            "FROM skills ORDER BY installed_at DESC"
        )
        return {"skills": [dict(r) for r in await cursor.fetchall()], "removed": removed}
    finally:
        await db.close()


@app.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: int):
    """Delete a skill."""
    db = await Database.open()
    try:
        cursor = await db.execute("SELECT id, skill_path FROM skills WHERE id = ?", (skill_id,))
        skill = await cursor.fetchone()
        if not skill:
            raise HTTPException(status_code=404, detail="Skill introuvable")

        # Remove from disk
        repo_path = Path(skill["skill_path"])
        if repo_path.exists():
            shutil.rmtree(repo_path)

        await db.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


@app.put("/api/skills/{skill_id}/toggle")
async def toggle_skill(skill_id: int):
    """Toggle a skill's enabled status."""
    db = await Database.open()
    try:
        cursor = await db.execute("SELECT id, enabled, name FROM skills WHERE id = ?", (skill_id,))
        skill = await cursor.fetchone()
        if not skill:
            raise HTTPException(status_code=404, detail="Skill introuvable")

        new_enabled = 0 if skill["enabled"] else 1
        await db.execute("UPDATE skills SET enabled = ? WHERE id = ?", (new_enabled, skill_id))
        await db.commit()
        return {"status": "ok", "enabled": bool(new_enabled), "name": skill["name"]}
    finally:
        await db.close()


@app.get("/api/skills/{skill_id}/explore")
async def explore_skill(skill_id: int):
    """Explore a skill's files and content."""
    db = await Database.open()
    try:
        cursor = await db.execute("SELECT name, skill_path, description FROM skills WHERE id = ?", (skill_id,))
        skill = await cursor.fetchone()
        if not skill:
            raise HTTPException(status_code=404, detail="Skill introuvable")

        repo_path = Path(skill["skill_path"])
        if not repo_path.exists():
            return {"name": skill["name"], "description": skill["description"], "files": [], "error": "Dossier supprimé"}

        files = []
        for f in sorted(repo_path.rglob("*")):
            if f.is_file() and f.name not in [".gitkeep"]:
                rel = str(f.relative_to(repo_path))
                size = f.stat().st_size
                # Read first 500 chars of text files
                preview = ""
                if f.suffix in [".md", ".txt", ".py", ".js", ".yaml", ".yml", ".json", ".sh", ".toml", ".cfg", ".ini"]:
                    try:
                        preview = f.read_text(encoding="utf-8", errors="ignore")[:500]
                    except:
                        pass
                files.append({"path": rel, "size": size, "preview": preview})

        return {"name": skill["name"], "description": skill["description"], "files": files}
    finally:
        await db.close()


# ========== MARKETPLACE ==========
# Liste des meilleurs repos AI/ML tendances à installer en masse
TRENDING_AI_REPOS = [
    "https://github.com/unclecode/crawl4ai",
    "https://github.com/trekhleb/javascript-algorithms",
    "https://github.com/TheAlgorithms/Python",
    "https://github.com/ollama/ollama-python",
    "https://github.com/huggingface/transformers",
    "https://github.com/langchain-ai/langchain",
    "https://github.com/crewAIInc/crewAI",
    "https://github.com/fastai/fastai",
    "https://github.com/vllm-project/vllm",
    "https://github.com/ggerganov/llama.cpp",
    "https://github.com/nomic-ai/gpt4all",
    "https://github.com/imartinez/privateGPT",
    "https://github.com/open-webui/open-webui",
    "https://github.com/OpenInterpreter/open-interpreter",
    "https://github.com/lm-sys/FastChat",
    "https://github.com/microsoft/autogen",
    "https://github.com/plandex-ai/plandex",
    "https://github.com/stanfordnlp/dspy",
    "https://github.com/unslothai/unsloth",
    "https://github.com/mozilla/readability",
    "https://github.com/yt-dlp/yt-dlp",
    "https://github.com/mckaywrigley/chatbot-ui",
    "https://github.com/nicegui/nicegui",
    "https://github.com/donnemartin/system-design-primer",
    "https://github.com/public-apis/public-apis",
    "https://github.com/f/awesome-chatgpt-prompts",
    "https://github.com/e2b-dev/awesome-ai-agents",
    "https://github.com/comfyanonymous/ComfyUI",
    "https://github.com/AUTOMATIC1111/stable-diffusion-webui",
    "https://github.com/kyutai-labs/moshi",
    "https://github.com/gradio-app/gradio",
    "https://github.com/streamlit/streamlit",
    "https://github.com/scikit-learn/scikit-learn",
    "https://github.com/hwchase17/langchain-hub",
    "https://github.com/WeChat-ai-lab/WeChat-Article-Exporter",
    "https://github.com/truewindllm/finetuning",
    "https://github.com/levihsu/OOTDiffusion",
    "https://github.com/meta-llama/llama-models",
    "https://github.com/mistralai/mistral-inference",
    "https://github.com/deepseek-ai/DeepSeek-V3",
]

FEATURED_REPOS = [
    {"name": "crawl4ai", "full_name": "unclecode/crawl4ai", "url": "https://github.com/unclecode/crawl4ai",
     "description": "🔥🕷️ Crawl4AI: Open-source LLM-friendly web crawler & scraper",
     "topics": ["web-scraping", "crawler", "ai", "llm"], "stars": 30000},
    {"name": "javascript-algorithms", "full_name": "trekhleb/javascript-algorithms",
     "url": "https://github.com/trekhleb/javascript-algorithms",
     "description": "📝 Algorithms and data structures implemented in JavaScript",
     "topics": ["algorithms", "javascript", "education"], "stars": 190000},
    {"name": "Python", "full_name": "TheAlgorithms/Python",
     "url": "https://github.com/TheAlgorithms/Python",
     "description": "All Algorithms implemented in Python",
     "topics": ["python", "algorithms", "education"], "stars": 200000},
    {"name": "ollama-python", "full_name": "ollama/ollama-python",
     "url": "https://github.com/ollama/ollama-python",
     "description": "Ollama Python library for local LLM inference",
     "topics": ["ollama", "python", "llm", "local-ai"], "stars": 6000},
    {"name": "transformers", "full_name": "huggingface/transformers",
     "url": "https://github.com/huggingface/transformers",
     "description": "🤗 Transformers: State-of-the-art Machine Learning for Pytorch, TensorFlow, and JAX",
     "topics": ["nlp", "transformers", "deep-learning", "huggingface"], "stars": 140000},
    {"name": "fastapi", "full_name": "fastapi/fastapi",
     "url": "https://github.com/fastapi/fastapi",
     "description": "FastAPI framework, high performance, easy to learn, fast to code, ready for production",
     "topics": ["fastapi", "python", "api", "async"], "stars": 82000},
    {"name": "langchain", "full_name": "langchain-ai/langchain",
     "url": "https://github.com/langchain-ai/langchain",
     "description": "🦜🔗 Build context-aware reasoning applications",
     "topics": ["llm", "ai", "python", "langchain"], "stars": 100000},
    {"name": "awesome-python", "full_name": "vinta/awesome-python",
     "url": "https://github.com/vinta/awesome-python",
     "description": "A curated list of awesome Python frameworks, libraries and software",
     "topics": ["awesome-list", "python", "resources"], "stars": 240000},
    {"name": "crewAI", "full_name": "crewAIInc/crewAI",
     "url": "https://github.com/crewAIInc/crewAI",
     "description": "Framework for orchestrating role-playing, autonomous AI agents",
     "topics": ["ai-agents", "llm", "python", "multi-agent"], "stars": 28000},
    {"name": "scikit-learn", "full_name": "scikit-learn/scikit-learn",
     "url": "https://github.com/scikit-learn/scikit-learn",
     "description": "scikit-learn: machine learning in Python",
     "topics": ["machine-learning", "python", "data-science"], "stars": 62000},
]


@app.get("/api/marketplace/featured")
async def marketplace_featured():
    """Get featured/popular repositories."""
    # Check installed skills to mark them
    db = await Database.open()
    try:
        cursor = await db.execute("SELECT repo_full_name, name FROM skills")
        installed = {row["repo_full_name"]: row["name"] for row in await cursor.fetchall()}
    finally:
        await db.close()

    repos = []
    for r in FEATURED_REPOS:
        repos.append({
            **r,
            "installed": r["full_name"] in installed,
            "installed_name": installed.get(r["full_name"]),
        })
    for r in repos:
        r["source"] = "Recommande"
    return {"repos": repos, "source": "curated"}


@app.get("/api/marketplace/search")
async def marketplace_search(q: str = ""):
    """Search GitHub for repositories."""
    if not q or len(q.strip()) < 2:
        return {"repos": [], "error": "Requete trop courte (min 2 caracteres)"}

    query = q.strip()
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": 15}
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "AkyelIA/2.0"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params=params, headers=headers)
            if r.status_code == 403:
                return {"repos": [], "error": "Limite de requêtes GitHub dépassée. Réessaie dans 1 heure."}
            if r.status_code != 200:
                return {"repos": [], "error": f"Erreur GitHub API: {r.status_code}"}

            data = r.json()
            items = data.get("items", [])[:15]

            # Check which are already installed
            db = await Database.open()
            try:
                cursor = await db.execute("SELECT repo_full_name FROM skills")
                installed = {row["repo_full_name"] for row in await cursor.fetchall()}
            finally:
                await db.close()

            repos = []
            for item in items:
                full_name = item.get("full_name", "")
                repos.append({
                    "name": item.get("name", ""),
                    "full_name": full_name,
                    "url": item.get("html_url", ""),
                    "description": item.get("description", "") or "",
                    "topics": item.get("topics", [])[:5],
                    "stars": item.get("stargazers_count", 0),
                    "language": item.get("language", ""),
                    "installed": full_name in installed,
                })
            for r in repos:
                r["source"] = "GitHub"
            return {"repos": repos, "source": "github"}
    except httpx.TimeoutException:
        return {"repos": [], "error": "La requête a pris trop de temps. Réessaie."}
    except Exception as e:
        return {"repos": [], "error": f"Erreur: {str(e)[:100]}"}


@app.get("/api/marketplace/trending")
async def marketplace_trending():
    """Get trending Python/AI repositories from GitHub."""
    url = "https://api.github.com/search/repositories"
    params = {"q": "stars:>1000 pushed:>2025-01-01", "sort": "stars", "order": "desc", "per_page": 10}
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "AkyelIA/2.0"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params=params, headers=headers)
            if r.status_code != 200:
                return {"repos": [], "error": f"Erreur: {r.status_code}"}

            data = r.json()
            items = data.get("items", [])[:10]

            db = await Database.open()
            try:
                cursor = await db.execute("SELECT repo_full_name FROM skills")
                installed = {row["repo_full_name"] for row in await cursor.fetchall()}
            finally:
                await db.close()

            repos = []
            for item in items:
                full_name = item.get("full_name", "")
                repos.append({
                    "name": item.get("name", ""),
                    "full_name": full_name,
                    "url": item.get("html_url", ""),
                    "description": item.get("description", "") or "",
                    "topics": item.get("topics", [])[:5],
                    "stars": item.get("stargazers_count", 0),
                    "language": item.get("language", ""),
                    "installed": full_name in installed,
                })
            for r in repos:
                r["source"] = "Tendances"
            return {"repos": repos, "source": "github-trending"}
    except Exception as e:
        return {"repos": [], "error": str(e)[:100]}


# ============================================
# WEB SEARCH
# ============================================
@app.post("/api/web-search")
async def web_search_endpoint(request: Request):
    """Search the web and return results."""
    data = await request.json()
    query = data.get("query", "").strip()
    if not query or len(query) < 3:
        raise HTTPException(status_code=400, detail="Requête trop courte")

    search_url = "https://api.duckduckgo.com/"
    params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(search_url, params=params, headers=headers)
            if r.status_code == 200:
                data = r.json()
                results = []
                abstract = data.get("AbstractText", "")
                if abstract:
                    results.append({
                        "title": data.get("Heading", "Résultat"),
                        "snippet": abstract,
                        "url": data.get("AbstractURL", ""),
                    })
                related = data.get("RelatedTopics", [])[:5]
                for topic in related:
                    if "Text" in topic:
                        results.append({
                            "title": topic.get("Text", "")[:80],
                            "snippet": topic.get("Text", ""),
                            "url": topic.get("FirstURL", ""),
                        })
                    elif "Topics" in topic:
                        for sub in topic["Topics"][:3]:
                            results.append({
                                "title": sub.get("Text", "")[:80],
                                "snippet": sub.get("Text", ""),
                                "url": sub.get("FirstURL", ""),
                            })
                return {"results": results[:8]}
        return {"results": []}
    except Exception as e:
        return {"results": [], "error": str(e)[:100]}


# ============================================
# EXPORT CONVERSATION
# ============================================
@app.get("/api/conversations/{conv_id}/export")
async def export_conversation(conv_id: str, fmt: str = "markdown"):
    db = await Database.open()
    try:
        cursor = await db.execute("SELECT id, title, provider, model FROM conversations WHERE id = ?", (conv_id,))
        conv = await cursor.fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation introuvable")
        cursor = await db.execute("SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id", (conv_id,))
        messages = await cursor.fetchall()

        if fmt == "markdown":
            lines = [f"# {conv['title']}\n", f"Provider: {conv['provider']} | Modèle: {conv['model']}\n", "---\n"]
            for m in messages:
                role = "👤 **Vous**" if m["role"] == "user" else "🤖 **AkyelIA**"
                lines.append(f"\n### {role}\n{m['content']}\n")
            content = "\n".join(lines)
            return StreamingResponse(
                iter([content]),
                media_type="text/markdown",
                headers={"Content-Disposition": f'attachment; filename="{conv["title"]}.md"'}
            )
        elif fmt == "json":
            return {
                "conversation": dict(conv),
                "messages": [dict(m) for m in messages]
            }
        raise HTTPException(status_code=400, detail="Format non supporté")
    finally:
        await db.close()


# ============================================
# AGENTS API
# ============================================
@app.get("/api/agents")
async def list_agents():
    db = await Database.open()
    try:
        cursor = await db.execute("SELECT * FROM agents ORDER BY updated_at DESC")
        agents = [dict(r) for r in await cursor.fetchall()]
        return {"agents": agents}
    finally:
        await db.close()


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    db = await Database.open()
    try:
        cursor = await db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        agent = await cursor.fetchone()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent introuvable")
        return dict(agent)
    finally:
        await db.close()


@app.post("/api/agents", status_code=201)
async def create_agent(request: AgentCreate):
    agent_id = str(uuid.uuid4())
    db = await Database.open()
    try:
        await db.execute(
            "INSERT INTO agents (id, name, description, system_prompt, provider, model, temperature, max_tokens, icon, color) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (agent_id, request.name, request.description, request.system_prompt, request.provider, request.model, request.temperature, request.max_tokens, request.icon, request.color)
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


@app.put("/api/agents/{agent_id}")
async def update_agent(agent_id: str, request: AgentUpdate):
    db = await Database.open()
    try:
        cursor = await db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Agent introuvable")
        
        updates = {}
        for field in ["name", "description", "system_prompt", "provider", "model", "temperature", "max_tokens", "icon", "color"]:
            val = getattr(request, field, None)
            if val is not None:
                updates[field] = val
        
        if updates:
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [agent_id]
            await db.execute(f"UPDATE agents SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
            await db.commit()
        
        cursor = await db.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    db = await Database.open()
    try:
        await db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


# ============================================
# PROJECTS API
# ============================================
@app.get("/api/projects")
async def list_projects():
    db = await Database.open()
    try:
        cursor = await db.execute(
            "SELECT p.*, (SELECT COUNT(*) FROM project_files WHERE project_id = p.id) as file_count "
            "FROM projects p ORDER BY p.updated_at DESC"
        )
        projects = [dict(r) for r in await cursor.fetchall()]
        return {"projects": projects}
    finally:
        await db.close()


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    db = await Database.open()
    try:
        cursor = await db.execute(
            "SELECT p.*, (SELECT COUNT(*) FROM project_files WHERE project_id = p.id) as file_count "
            "FROM projects p WHERE p.id = ?", (project_id,)
        )
        project = await cursor.fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="Projet introuvable")
        return dict(project)
    finally:
        await db.close()


@app.post("/api/projects", status_code=201)
async def create_project(request: ProjectCreate):
    project_id = str(uuid.uuid4())
    db = await Database.open()
    try:
        await db.execute(
            "INSERT INTO projects (id, name, description, language, icon) VALUES (?, ?, ?, ?, ?)",
            (project_id, request.name, request.description, request.language, request.icon)
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, request: Request):
    data = await request.json()
    db = await Database.open()
    try:
        cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Projet introuvable")
        
        updates = {}
        for field in ["name", "description", "language", "icon"]:
            if field in data:
                updates[field] = data[field]
        
        if updates:
            updates["updated_at"] = datetime.utcnow().isoformat()
            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [project_id]
            await db.execute(f"UPDATE projects SET {set_clause} WHERE id = ?", values)
            await db.commit()
        
        cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    db = await Database.open()
    try:
        await db.execute("DELETE FROM project_files WHERE project_id = ?", (project_id,))
        await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


# ============================================
# PROJECT FILES API
# ============================================
@app.get("/api/projects/{project_id}/files")
async def list_project_files(project_id: str):
    db = await Database.open()
    try:
        cursor = await db.execute(
            "SELECT id, path, language, created_at, updated_at FROM project_files WHERE project_id = ? ORDER BY path",
            (project_id,)
        )
        files = [dict(r) for r in await cursor.fetchall()]
        return {"files": files}
    finally:
        await db.close()


@app.get("/api/projects/{project_id}/files/{file_id}")
async def get_project_file(project_id: str, file_id: int):
    db = await Database.open()
    try:
        cursor = await db.execute(
            "SELECT * FROM project_files WHERE id = ? AND project_id = ?", (file_id, project_id)
        )
        file = await cursor.fetchone()
        if not file:
            raise HTTPException(status_code=404, detail="Fichier introuvable")
        return dict(file)
    finally:
        await db.close()


@app.post("/api/projects/{project_id}/files", status_code=201)
async def create_project_file(project_id: str, request: ProjectFileSave):
    db = await Database.open()
    try:
        # Check project exists
        cursor = await db.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Projet introuvable")
        
        # Check for duplicate path
        cursor = await db.execute(
            "SELECT id FROM project_files WHERE project_id = ? AND path = ?", (project_id, request.path)
        )
        if await cursor.fetchone():
            raise HTTPException(status_code=400, detail="Un fichier existe déjà à ce chemin")
        
        cursor = await db.execute(
            "INSERT INTO project_files (project_id, path, content, language) VALUES (?, ?, ?, ?)",
            (project_id, request.path, request.content, request.language or Path(request.path).suffix.lstrip("."))
        )
        await db.commit()
        await db.execute("UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
        await db.commit()
        
        file_id = db.lastrowid
        cursor = await db.execute("SELECT * FROM project_files WHERE id = ?", (file_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


@app.put("/api/projects/{project_id}/files/{file_id}")
async def update_project_file(project_id: str, file_id: int, request: ProjectFileSave):
    db = await Database.open()
    try:
        cursor = await db.execute(
            "SELECT * FROM project_files WHERE id = ? AND project_id = ?", (file_id, project_id)
        )
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Fichier introuvable")
        
        await db.execute(
            "UPDATE project_files SET content = ?, language = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (request.content, request.language or Path(request.path).suffix.lstrip("."), file_id)
        )
        await db.commit()
        await db.execute("UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
        await db.commit()
        
        cursor = await db.execute("SELECT * FROM project_files WHERE id = ?", (file_id,))
        return dict(await cursor.fetchone())
    finally:
        await db.close()


@app.delete("/api/projects/{project_id}/files/{file_id}")
async def delete_project_file(project_id: str, file_id: int):
    db = await Database.open()
    try:
        await db.execute("DELETE FROM project_files WHERE id = ? AND project_id = ?", (file_id, project_id))
        await db.commit()
        await db.execute("UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
        await db.commit()
        return {"status": "ok"}
    finally:
        await db.close()


# ============================================
# SYSTEM INFO
# ============================================
@app.get("/api/system")
async def system_info():
    """Get system information."""
    import sys
    return {
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "app_version": "2.1.0",
        "app_name": "Akyel AI",
        "uptime": "",  # À améliorer si besoin
        "total_providers": len(config.providers),
    }


# ============================================
# FILE UPLOAD & MANAGEMENT
# ============================================

def get_file_type(filename: str) -> str:
    """Determine file type from extension."""
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in CODE_EXTENSIONS:
        return "code"
    if ext in TEXT_EXTENSIONS:
        return "text"
    return "other"


def read_text_file_content(filepath: Path, max_size: int = 50000) -> str:
    """Read a text file safely."""
    if not filepath.exists() or not filepath.is_file():
        return ""
    if filepath.stat().st_size > max_size:
        return f"[Fichier trop volumineux: {filepath.stat().st_size} octets (max: {max_size})]"
    try:
        return filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        try:
            return filepath.read_text(encoding="latin-1", errors="replace")
        except Exception:
            return ""


@app.post("/api/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    """Upload files to the server."""
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier fourni")
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 fichiers à la fois")
    
    uploaded = []
    for file in files:
        file_id = str(uuid.uuid4())
        original_name = file.filename or "fichier"
        ext = Path(original_name).suffix or ""
        safe_name = f"{file_id}{ext}"
        filepath = UPLOADS_DIR / safe_name
        
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:  # 10 MB max
            continue
        
        filepath.write_bytes(content)
        
        file_type = get_file_type(original_name)
        file_info = {
            "id": file_id,
            "name": original_name,
            "size": len(content),
            "type": file_type,
            "ext": ext,
            "url": f"/api/files/{file_id}{ext}",
        }
        
        # Pour les fichiers texte, lire le contenu directement
        if file_type in ("text", "code"):
            file_info["content"] = read_text_file_content(filepath)
        elif file_type == "image":
            # Convertir en base64 pour prévisualisation
            mime = mimetypes.guess_type(original_name)[0] or "image/png"
            b64 = base64.b64encode(content).decode()
            file_info["preview_url"] = f"data:{mime};base64,{b64}"
        
        uploaded.append(file_info)
    
    return {"files": uploaded}


@app.get("/api/files/{file_id:str}")
async def serve_file(file_id: str):
    """Serve an uploaded file."""
    # Find file by ID (any extension)
    for f in UPLOADS_DIR.iterdir():
        if f.is_file() and f.stem == file_id:
            return FileResponse(str(f))
    raise HTTPException(status_code=404, detail="Fichier introuvable")


@app.post("/api/files/read-local")
async def read_local_file(request: Request):
    """Read a file from a local path (sécurisé)."""
    data = await request.json()
    filepath = data.get("path", "").strip()
    if not filepath:
        raise HTTPException(status_code=400, detail="Chemin requis")
    
    path = Path(filepath).resolve()
    
    # Sécurité: vérifier que le fichier existe et est accessible
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Fichier introuvable: {filepath}")
    if not path.is_file():
        raise HTTPException(status_code=400, detail="Le chemin spécifié n'est pas un fichier")
    
    file_type = get_file_type(path.name)
    max_size = 100000  # 100 KB
    
    if file_type == "image":
        content_bytes = path.read_bytes()
        if len(content_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image trop volumineuse (max 10 MB)")
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        b64 = base64.b64encode(content_bytes).decode()
        return {
            "name": path.name,
            "type": "image",
            "preview_url": f"data:{mime};base64,{b64}",
            "content": f"[Image: {path.name}]",
        }
    elif file_type in ("text", "code"):
        content = read_text_file_content(path, max_size)
        return {
            "name": path.name,
            "type": file_type,
            "content": content,
            "size": path.stat().st_size,
        }
    else:
        return {
            "name": path.name,
            "type": "other",
            "content": f"[Fichier: {path.name} ({path.stat().st_size} octets)]",
            "size": path.stat().st_size,
        }


# ========== Modification du chat pour gérer les fichiers ==========
# Cette fonction prépare le message utilisateur avec les fichiers attachés
def build_user_message(message: str, files: list[dict]) -> str:
    """Build user message content including file contents."""
    if not files:
        return message
    
    parts = [message] if message else []
    
    for f in files:
        name = f.get("name", "fichier")
        ftype = f.get("type", "other")
        content = f.get("content", "")
        
        if ftype == "image":
            parts.append(f"\n[ Image jointe: {name} ]")
        elif ftype == "code":
            ext = Path(name).suffix.lstrip(".") or ""
            if content:
                parts.append(f"\n--- Début du fichier: {name} ---\n```{ext}\n{content}\n```\n--- Fin de {name} ---")
            else:
                parts.append(f"\n[ Fichier: {name} (non lisible) ]")
        elif ftype == "text":
            if content:
                parts.append(f"\n--- Contenu de {name} ---\n{content}\n--- Fin de {name} ---")
            else:
                parts.append(f"\n[ Fichier: {name} ]")
        else:
            parts.append(f"\n[ Fichier joint: {name} ]")
    
    return "\n".join(parts)


if __name__ == "__main__":
    import uvicorn
    print(f"[OK] AkyelIA demarre sur http://{config.host}:{config.port}")
    print(f"[INFO] Providers disponibles : {', '.join(config.providers.keys())}")
    print(f"[INFO] Base de donnees : {config.db_path}")
    print(f"[INFO] Uploads: {UPLOADS_DIR}")
    uvicorn.run(app, host=config.host, port=config.port)
