#!/usr/bin/env python3
"""
============================================
AI FACTORY - MCP Server
============================================
Model Context Protocol Server.
Pont entre l'IA et les outils externes :
bases de données, APIs, système de fichiers,
exécution de code, recherche web.

L'IA peut ainsi "voir" et "agir" sur le monde réel.

Usage:
    python3 mcp-server.py                      # Mode serveur (port 8766)
    python3 mcp-server.py --tools               # Lister les outils disponibles
    python3 mcp-server.py --call search "query" # Tester un outil
    python3 mcp-server.py --interactive         # Mode test interactif

Documentation MCP: https://modelcontextprotocol.io
============================================
"""

import argparse
import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

# ============================================
# CONFIGURATION
# ============================================
BASE_DIR = Path(__file__).parent.parent  # ai-factory/
WORKSPACE_DIR = BASE_DIR / "workspace"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
OLLAMA_API = os.getenv("OLLAMA_API_URL", "http://localhost:11434")

LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Port du serveur MCP
MCP_PORT = int(os.getenv("MCP_PORT", "8766"))


class Colors:
    GREEN = '\033[0;32m'; YELLOW = '\033[1;33m'
    RED = '\033[0;31m'; BLUE = '\033[0;34m'; CYAN = '\033[0;36m'
    BOLD = '\033[1m'; NC = '\033[0m'


def log(msg, color=Colors.GREEN):
    print(f"{color}[MCP][{datetime.now().strftime('%H:%M:%S')}]{Colors.NC} {msg}")


# ============================================
# SYSTÈME D'OUTILS MCP
# ============================================
class MCPTool:
    """Un outil que l'IA peut utiliser via MCP."""

    def __init__(self, name: str, description: str, 
                 handler: Callable, parameters: dict,
                 category: str = "general"):
        self.name = name
        self.description = description
        self.handler = handler
        self.parameters = parameters
        self.category = category

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": self.parameters,
            "input_schema": {
                "type": "object",
                "properties": self.parameters,
                "required": [k for k, v in self.parameters.items() 
                           if v.get("required", False)]
            }
        }


class MCPServer:
    """
    Serveur MCP qui expose des outils à l'IA.
    L'IA peut appeler ces outils pour interagir avec le monde réel.
    """

    def __init__(self):
        self.tools: dict[str, MCPTool] = {}
        self.call_history = []
        self._register_all_tools()

    # ==========================================
    # ENREGISTREMENT DES OUTILS
    # ==========================================
    def _register_all_tools(self):
        """Enregistre tous les outils disponibles."""

        # --- Outils Fichiers ---
        self._register(MCPTool(
            "read_file", "Lire le contenu d'un fichier",
            self._tool_read_file,
            {"path": {"type": "string", "description": "Chemin du fichier", "required": True}}
        ))
        
        self._register(MCPTool(
            "write_file", "Écrire du contenu dans un fichier",
            self._tool_write_file,
            {"path": {"type": "string", "description": "Chemin du fichier", "required": True},
             "content": {"type": "string", "description": "Contenu à écrire", "required": True}}
        ))
        
        self._register(MCPTool(
            "list_files", "Lister les fichiers d'un dossier",
            self._tool_list_files,
            {"path": {"type": "string", "description": "Chemin du dossier", "required": False, "default": "."},
             "pattern": {"type": "string", "description": "Filtre glob (ex: *.py)", "required": False}}
        ))
        
        self._register(MCPTool(
            "search_files", "Rechercher du texte dans les fichiers",
            self._tool_search_files,
            {"pattern": {"type": "string", "description": "Texte à rechercher", "required": True},
             "path": {"type": "string", "description": "Dossier de recherche", "required": False}}
        ))

        # --- Outils Exécution ---
        self._register(MCPTool(
            "run_command", "Exécuter une commande shell",
            self._tool_run_command,
            {"command": {"type": "string", "description": "Commande à exécuter", "required": True},
             "timeout": {"type": "number", "description": "Timeout en secondes", "required": False}}
        ))
        
        self._register(MCPTool(
            "run_python", "Exécuter du code Python",
            self._tool_run_python,
            {"code": {"type": "string", "description": "Code Python à exécuter", "required": True},
             "timeout": {"type": "number", "description": "Timeout en secondes", "required": False}}
        ))

        # --- Outils Base de données ---
        self._register(MCPTool(
            "query_database", "Exécuter une requête SQL sur la base locale",
            self._tool_query_database,
            {"query": {"type": "string", "description": "Requête SQL", "required": True}}
        ))
        
        self._register(MCPTool(
            "qdrant_search", "Rechercher des vecteurs similaires dans Qdrant",
            self._tool_qdrant_search,
            {"collection": {"type": "string", "description": "Collection Qdrant", "required": True},
             "query": {"type": "string", "description": "Texte de recherche", "required": True},
             "limit": {"type": "number", "description": "Nombre de résultats", "required": False}}
        ))

        # --- Outils Web ---
        self._register(MCPTool(
            "web_search", "Rechercher sur le web via DuckDuckGo",
            self._tool_web_search,
            {"query": {"type": "string", "description": "Requête de recherche", "required": True},
             "max_results": {"type": "number", "description": "Nombre max de résultats", "required": False}}
        ))
        
        self._register(MCPTool(
            "web_fetch", "Récupérer le contenu d'une URL",
            self._tool_web_fetch,
            {"url": {"type": "string", "description": "URL à récupérer", "required": True},
             "max_chars": {"type": "number", "description": "Max caractères", "required": False}}
        ))

        # --- Outils Docker ---
        self._register(MCPTool(
            "docker_ps", "Lister les conteneurs Docker",
            self._tool_docker_ps,
            {}
        ))
        
        self._register(MCPTool(
            "docker_logs", "Récupérer les logs d'un conteneur",
            self._tool_docker_logs,
            {"container": {"type": "string", "description": "Nom du conteneur", "required": True},
             "lines": {"type": "number", "description": "Nombre de lignes", "required": False}}
        ))

        # --- Outils Ollama ---
        self._register(MCPTool(
            "ollama_list", "Lister les modèles Ollama disponibles",
            self._tool_ollama_list,
            {}
        ))
        
        self._register(MCPTool(
            "ollama_generate", "Générer du texte avec Ollama",
            self._tool_ollama_generate,
            {"prompt": {"type": "string", "description": "Prompt à envoyer", "required": True},
             "model": {"type": "string", "description": "Modèle (défaut: qwen2.5-coder:14b)", "required": False},
             "temperature": {"type": "number", "description": "Température (0-1)", "required": False}}
        ))

        # --- Outils API ---
        self._register(MCPTool(
            "http_request", "Effectuer une requête HTTP",
            self._tool_http_request,
            {"url": {"type": "string", "description": "URL de la requête", "required": True},
             "method": {"type": "string", "description": "Méthode HTTP (GET/POST/PUT/DELETE)", "required": False},
             "headers": {"type": "object", "description": "En-têtes HTTP", "required": False},
             "body": {"type": "string", "description": "Corps de la requête", "required": False}}
        ))

        # --- Outils Système ---
        self._register(MCPTool(
            "system_info", "Informations sur le système (RAM, CPU, disque)",
            self._tool_system_info,
            {}
        ))
        
        self._register(MCPTool(
            "get_time", "Obtenir la date et l'heure actuelles",
            self._tool_get_time,
            {}
        ))

        # --- Outils AI Factory ---
        self._register(MCPTool(
            "factory_status", "État de l'AI Factory (services, bots, skills)",
            self._tool_factory_status,
            {}
        ))
        
        self._register(MCPTool(
            "list_skills", "Lister les skills installés",
            self._tool_list_skills,
            {}
        ))

    def _register(self, tool: MCPTool):
        self.tools[tool.name] = tool

    # ==========================================
    # IMPLÉMENTATIONS DES OUTILS
    # ==========================================

    # --- Fichiers ---
    async def _tool_read_file(self, params: dict) -> dict:
        path = params["path"]
        p = Path(path)
        if not p.exists():
            return {"error": f"Fichier introuvable: {path}"}
        if p.stat().st_size > 100_000:
            return {"error": "Fichier trop volumineux (max 100KB)"}
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            return {"content": content, "size": len(content), "path": path}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_write_file(self, params: dict) -> dict:
        path = params["path"]
        content = params["content"]
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            p.write_text(content, encoding="utf-8")
            return {"success": True, "path": path, "size": len(content)}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_list_files(self, params: dict) -> dict:
        path = params.get("path", ".")
        pattern = params.get("pattern")
        p = Path(path)
        if not p.exists():
            return {"error": f"Dossier introuvable: {path}"}
        
        files = []
        if pattern:
            iterator = p.rglob(pattern)
        else:
            iterator = p.iterdir()
        
        for f in sorted(iterator):
            if f.is_file():
                files.append({
                    "name": f.name,
                    "path": str(f),
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                })
        
        return {"files": files, "total": len(files), "directory": str(p)}

    async def _tool_search_files(self, params: dict) -> dict:
        pattern = params["pattern"]
        path = params.get("path", str(BASE_DIR))
        try:
            result = subprocess.run(
                ["grep", "-rn", "--include=*.py", "--include=*.md", 
                 "--include=*.js", "--include=*.html", "--include=*.yml",
                 "--include=*.yaml", "--include=*.json",
                 "-l", pattern, path],
                capture_output=True, text=True, timeout=30
            )
            files = [f for f in result.stdout.strip().split("\n") if f]
            return {"files": files[:50], "total": len(files), "pattern": pattern}
        except Exception as e:
            return {"error": str(e)}

    # --- Exécution ---
    async def _tool_run_command(self, params: dict) -> dict:
        command = params["command"]
        timeout = params.get("timeout", 30)
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, 
                timeout=timeout
            )
            return {
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-1000:],
                "return_code": result.returncode,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {"error": "Commande expirée", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    async def _tool_run_python(self, params: dict) -> dict:
        code = params["code"]
        timeout = params.get("timeout", 15)
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                f.flush()
                result = subprocess.run(
                    ["python3", f.name],
                    capture_output=True, text=True, timeout=timeout
                )
                Path(f.name).unlink(missing_ok=True)
                return {
                    "stdout": result.stdout[-2000:],
                    "stderr": result.stderr[-1000:],
                    "return_code": result.returncode,
                    "success": result.returncode == 0
                }
        except subprocess.TimeoutExpired:
            return {"error": "Code expiré", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    # --- Base de données ---
    async def _tool_query_database(self, params: dict) -> dict:
        query = params["query"]
        db_path = BASE_DIR / "data" / "factory.db"
        
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query)
            
            if query.strip().upper().startswith("SELECT"):
                rows = [dict(row) for row in cursor.fetchall()]
                conn.close()
                return {"rows": rows, "count": len(rows), "query": query}
            else:
                conn.commit()
                changes = conn.total_changes
                conn.close()
                return {"success": True, "changes": changes}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_qdrant_search(self, params: dict) -> dict:
        import httpx
        collection = params["collection"]
        query = params["query"]
        limit = params.get("limit", 10)
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"http://localhost:6333/collections/{collection}/points/search",
                    json={"vector": [0.0] * 384, "limit": limit, "with_payload": True}
                )
                if r.status_code == 200:
                    data = r.json()
                    return {"results": data.get("result", []), "collection": collection}
                return {"error": f"Qdrant: {r.status_code}"}
        except Exception as e:
            return {"error": f"Qdrant indisponible: {e}"}

    # --- Web ---
    async def _tool_web_search(self, params: dict) -> dict:
        import httpx
        query = params["query"]
        max_results = params.get("max_results", 5)
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": 1}
                )
                if r.status_code == 200:
                    data = r.json()
                    results = []
                    abstract = data.get("AbstractText", "")
                    if abstract:
                        results.append({
                            "title": data.get("Heading", "Résultat"),
                            "snippet": abstract[:300],
                            "url": data.get("AbstractURL", "")
                        })
                    related = data.get("RelatedTopics", [])[:max_results]
                    for topic in related:
                        if "Text" in topic:
                            results.append({
                                "title": topic.get("Text", "")[:80],
                                "snippet": topic.get("Text", "")[:300],
                                "url": topic.get("FirstURL", "")
                            })
                    return {"results": results[:max_results], "query": query}
                return {"error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_web_fetch(self, params: dict) -> dict:
        import httpx
        url = params["url"]
        max_chars = params.get("max_chars", 5000)
        
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    # Extraction simple du texte
                    import re
                    text = r.text
                    # Enlever les balises HTML
                    text = re.sub(r'<[^>]+>', ' ', text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    return {
                        "content": text[:max_chars],
                        "url": url,
                        "status": r.status_code,
                        "headers": dict(r.headers)
                    }
                return {"error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    # --- Docker ---
    async def _tool_docker_ps(self, params: dict) -> dict:
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", 
                 '{{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Ports}}'],
                capture_output=True, text=True, timeout=10
            )
            containers = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split("\t")
                    containers.append({
                        "name": parts[0],
                        "status": parts[1] if len(parts) > 1 else "",
                        "image": parts[2] if len(parts) > 2 else "",
                        "ports": parts[3] if len(parts) > 3 else ""
                    })
            return {"containers": containers, "total": len(containers)}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_docker_logs(self, params: dict) -> dict:
        container = params["container"]
        lines = params.get("lines", 50)
        try:
            result = subprocess.run(
                ["docker", "logs", container, "--tail", str(lines)],
                capture_output=True, text=True, timeout=10
            )
            return {"logs": result.stdout[-3000:], "container": container}
        except Exception as e:
            return {"error": str(e)}

    # --- Ollama ---
    async def _tool_ollama_list(self, params: dict) -> dict:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{OLLAMA_API}/api/tags")
                if r.status_code == 200:
                    models = [{"name": m["name"], "size": f"{m.get('size', 0)/1e9:.1f}GB"} 
                            for m in r.json().get("models", [])]
                    return {"models": models, "total": len(models)}
                return {"error": "Ollama indisponible"}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_ollama_generate(self, params: dict) -> dict:
        import httpx
        prompt = params["prompt"]
        model = params.get("model", "qwen2.5-coder:14b")
        temperature = params.get("temperature", 0.7)
        
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(f"{OLLAMA_API}/api/generate", json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": temperature, "num_predict": 4096}
                })
                if r.status_code == 200:
                    return {"response": r.json().get("response", ""), "model": model}
                return {"error": f"Ollama: {r.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    # --- HTTP ---
    async def _tool_http_request(self, params: dict) -> dict:
        import httpx
        url = params["url"]
        method = params.get("method", "GET").upper()
        headers = params.get("headers", {})
        body = params.get("body")
        
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                if method == "GET":
                    r = await client.get(url, headers=headers)
                elif method == "POST":
                    r = await client.post(url, headers=headers, content=body)
                elif method == "PUT":
                    r = await client.put(url, headers=headers, content=body)
                elif method == "DELETE":
                    r = await client.delete(url, headers=headers)
                else:
                    return {"error": f"Méthode non supportée: {method}"}
                
                return {
                    "status": r.status_code,
                    "headers": dict(r.headers),
                    "body": r.text[:5000],
                    "url": str(r.url)
                }
        except Exception as e:
            return {"error": str(e)}

    # --- Système ---
    async def _tool_system_info(self, params: dict) -> dict:
        info = {
            "platform": sys.platform,
            "python_version": sys.version,
            "timestamp": datetime.now().isoformat()
        }
        try:
            result = subprocess.run(
                ["free", "-h"], capture_output=True, text=True, timeout=5
            )
            info["memory"] = result.stdout.strip()
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["df", "-h", "/"], capture_output=True, text=True, timeout=5
            )
            info["disk"] = result.stdout.strip()
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["nproc"], capture_output=True, text=True, timeout=5
            )
            info["cpu_cores"] = result.stdout.strip()
        except Exception:
            pass
        return info

    async def _tool_get_time(self, params: dict) -> dict:
        return {
            "datetime": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
            "timezone": time.tzname
        }

    # --- AI Factory ---
    async def _tool_factory_status(self, params: dict) -> dict:
        # Vérifier les services Docker
        import httpx
        services = {}
        
        checks = {
            "ollama": ("http://localhost:11434/api/tags", "🧠 LLM"),
            "qdrant": ("http://localhost:6333/healthz", "💾 Vector DB"),
            "open-webui": ("http://localhost:3001", "💬 Chat UI"),
            "n8n": ("http://localhost:5678", "⚡ Workflows"),
            "browserless": ("http://localhost:3002", "🌐 Browser"),
        }
        
        for name, (url, desc) in checks.items():
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    r = await client.get(url)
                    services[name] = {"alive": r.status_code < 500, "description": desc}
            except Exception:
                services[name] = {"alive": False, "description": desc}
        
        # Compter les skills
        skills_count = 0
        registry_file = BASE_DIR / "registry" / "skills-registry.yaml"
        if registry_file.exists():
            try:
                import yaml
                with open(registry_file) as f:
                    registry = yaml.safe_load(f) or {}
                    skills_count = len(registry.get("skills", []))
            except Exception:
                pass
        
        return {
            "services": services,
            "skills_count": skills_count,
            "status": "operational" if any(s["alive"] for s in services.values()) else "offline"
        }

    async def _tool_list_skills(self, params: dict) -> dict:
        registry_file = BASE_DIR / "registry" / "skills-registry.yaml"
        if not registry_file.exists():
            return {"skills": [], "total": 0}
        
        try:
            import yaml
            with open(registry_file) as f:
                registry = yaml.safe_load(f) or {}
            
            skills = registry.get("skills", [])
            pending = registry.get("pending", [])
            
            return {
                "skills": [{"name": s["name"], "type": s.get("type", "N/A"),
                           "description": s.get("description", "")[:100],
                           "enabled": s.get("enabled", True)} for s in skills],
                "pending": [{"name": p.get("name", ""), "url": p.get("url", "")} for p in pending],
                "total": len(skills),
                "pending_count": len(pending)
            }
        except Exception as e:
            return {"error": str(e)}

    # ==========================================
    # POINT D'ENTRÉE PRINCIPAL
    # ==========================================
    async def call_tool(self, tool_name: str, params: dict) -> dict:
        """Appelle un outil et retourne le résultat."""
        if tool_name not in self.tools:
            return {"error": f"Outil inconnu: {tool_name}. Disponibles: {list(self.tools.keys())}"}
        
        log(f"🔧 Appel outil: {tool_name}", Colors.BLUE)
        
        try:
            result = await self.tools[tool_name].handler(params)
            
            # Enregistrer dans l'historique
            self.call_history.append({
                "tool": tool_name,
                "params": params,
                "result_preview": str(result)[:200],
                "timestamp": datetime.now().isoformat()
            })
            
            return result
        except Exception as e:
            log(f"❌ Erreur outil {tool_name}: {e}", Colors.RED)
            return {"error": str(e)}

    def list_tools(self, category: str = None) -> list:
        """Liste les outils disponibles, optionnellement filtrés par catégorie."""
        if category:
            return [t.to_dict() for t in self.tools.values() if t.category == category]
        return [t.to_dict() for t in self.tools.values()]

    def get_tool(self, name: str) -> Optional[dict]:
        if name in self.tools:
            return self.tools[name].to_dict()
        return None


# ============================================
# API SERVER (FastAPI)
# ============================================
def run_api_server(port: int = MCP_PORT):
    """Lance le serveur API MCP."""
    from fastapi import FastAPI, HTTPException
    import uvicorn
    
    app = FastAPI(title="AI Factory - MCP Server", version="1.0.0")
    mcp = MCPServer()
    
    @app.get("/")
    async def root():
        return {
            "service": "AI Factory MCP Server",
            "version": "1.0.0",
            "tools_count": len(mcp.tools),
            "tools": list(mcp.tools.keys())
        }
    
    @app.get("/tools")
    async def list_tools(category: str = None):
        return {"tools": mcp.list_tools(category), "total": len(mcp.tools)}
    
    @app.get("/tools/{tool_name}")
    async def get_tool(tool_name: str):
        tool = mcp.get_tool(tool_name)
        if not tool:
            raise HTTPException(404, f"Outil '{tool_name}' introuvable")
        return tool
    
    @app.post("/tools/{tool_name}/call")
    async def call_tool(tool_name: str, params: dict = {}):
        result = await mcp.call_tool(tool_name, params)
        return result
    
    @app.get("/history")
    async def get_history(limit: int = 20):
        return {"calls": mcp.call_history[-limit:], "total": len(mcp.call_history)}
    
    print(f"""
╔═══════════════════════════════════════╗
║   🔌 AI FACTORY - MCP Server        ║
║   {len(mcp.tools)} outils disponibles          ║
╚═══════════════════════════════════════╝
""")
    print(f"📡 API: http://localhost:{port}")
    print(f"📋 Outils: {', '.join(mcp.tools.keys())}")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=port)


# ============================================
# CLI
# ============================================
def main():
    parser = argparse.ArgumentParser(
        description="🔌 AI FACTORY - MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python3 mcp-server.py                  # Lancer le serveur
  python3 mcp-server.py --tools          # Lister les outils
  python3 mcp-server.py --call read_file '{"path":"README.md"}'
  python3 mcp-server.py --call web_search '{"query":"AI agents 2026"}'
  python3 mcp-server.py --call run_command '{"command":"docker ps"}'
  python3 mcp-server.py --interactive    # Mode dialogue
        """
    )
    
    parser.add_argument("--tools", "-t", action="store_true",
                       help="Lister les outils disponibles")
    parser.add_argument("--call", "-c", nargs=2, metavar=("TOOL", "PARAMS_JSON"),
                       help="Appeler un outil")
    parser.add_argument("--port", "-p", type=int, default=MCP_PORT,
                       help="Port du serveur")
    parser.add_argument("--interactive", "-i", action="store_true",
                       help="Mode interactif")
    
    args = parser.parse_args()
    
    mcp = MCPServer()
    
    if args.tools:
        print(f"\n🔌 Outils MCP disponibles ({len(mcp.tools)}):")
        categories = {}
        for tool in mcp.list_tools():
            categories.setdefault(tool["category"], []).append(tool)
        
        for cat, tools in categories.items():
            print(f"\n{Colors.BOLD}{cat.upper()}{Colors.NC}")
            for t in tools:
                print(f"   🔧 {t['name']:25} {t['description']}")
        
        print(f"\n📡 Serveur: python3 mcp-server.py --port {args.port}")
        return
    
    if args.call:
        import asyncio
        tool_name, params_json = args.call
        try:
            params = json.loads(params_json)
        except json.JSONDecodeError:
            params = {"query": params_json}
        
        result = asyncio.run(mcp.call_tool(tool_name, params))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    
    if args.interactive:
        import asyncio
        print(f"\n🔌 Mode interactif MCP ({len(mcp.tools)} outils)")
        print("   Tape 'quit' pour quitter, 'tools' pour lister\n")
        
        while True:
            cmd = input("mcp> ").strip()
            if cmd.lower() in ("quit", "q", "exit"):
                break
            if cmd.lower() == "tools":
                for t in mcp.list_tools():
                    print(f"   {t['name']:25} {t['description']}")
                continue
            
            parts = cmd.split(maxsplit=1)
            if len(parts) == 2:
                tool_name, params_str = parts
                try:
                    params = json.loads(params_str)
                except json.JSONDecodeError:
                    params = {"query": params_str}
                
                result = asyncio.run(mcp.call_tool(tool_name, params))
                print(json.dumps(result, indent=2, ensure_ascii=False)[:1000])
                print()
            else:
                print("Format: outil params_JSON")
        
        return
    
    # Mode serveur
    run_api_server(args.port)


if __name__ == "__main__":
    main()
