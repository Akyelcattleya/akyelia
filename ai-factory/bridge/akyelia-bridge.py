#!/usr/bin/env python3
"""
============================================
AI FACTORY - AkyelIA Bridge
============================================
Pont entre l'interface AkyelIA existante
et l'AI Factory (services Docker).

Ce module peut :
1. Être importé par app.py pour ajouter des endpoints API
2. Être lancé comme microservice standalone (port 8765)

Usage:
    python3 akyelia-bridge.py          # Mode microservice
    python3 akyelia-bridge.py --check  # Vérifier la connexion
============================================
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ============================================
# CONFIGURATION
# ============================================
BASE_DIR = Path(__file__).parent.parent  # ai-factory/
FACTORY_DIR = BASE_DIR
DOCKER_COMPOSE_DIR = BASE_DIR

# Services à monitorer
FACTORY_SERVICES = {
    "openhands": {"port": 3000, "desc": "🧠 Agent Architecte OpenHands"},
    "ollama": {"port": 11434, "desc": "🧠 Moteur LLM Ollama"},
    "qdrant": {"port": 6333, "desc": "💾 Base vectorielle Qdrant"},
    "open-webui": {"port": 3001, "desc": "💬 Interface Open WebUI"},
    "n8n": {"port": 5678, "desc": "⚡ Orchestrateur n8n"},
    "browserless": {"port": 3002, "desc": "🌐 Navigateur Browserless"},
}

# Chemin vers AkyelIA (projet parent)
AKYELIA_DIR = BASE_DIR.parent


class AkyeliaBridge:
    """
    Pont entre AkyelIA et l'AI Factory.
    Traduit les appels API AkyelIA en actions Docker.
    """

    @staticmethod
    def factory_status() -> dict:
        """Retourne l'état complet de l'AI Factory."""
        result = {
            "factory_name": "AI Factory",
            "status": "unknown",
            "services": {},
            "models": [],
            "bots": [],
            "skills_count": 0,
            "uptime": None,
            "last_check": datetime.now().isoformat()
        }
        
        # Vérifier chaque service
        all_ok = True
        for name, info in FACTORY_SERVICES.items():
            service_status = AkyeliaBridge._check_service(name, info["port"])
            result["services"][name] = service_status
            if not service_status.get("alive", False):
                all_ok = False
        
        # Modèles Ollama
        models = AkyeliaBridge._get_ollama_models()
        result["models"] = models
        
        # Bots détectés
        bots = AkyeliaBridge._detect_bots()
        result["bots"] = bots
        
        # Skills
        result["skills_count"] = AkyeliaBridge._count_skills()
        
        # Statut global
        all_online = all(s.get("alive", False) for s in result["services"].values())
        any_online = any(s.get("alive", False) for s in result["services"].values())
        
        if all_online and models:
            result["status"] = "operational"
        elif any_online:
            result["status"] = "partial"
        else:
            result["status"] = "offline"
        
        return result

    @staticmethod
    def _check_service(name: str, port: int) -> dict:
        """Vérifie si un service Docker répond."""
        status = {
            "name": name,
            "port": port,
            "alive": False,
            "http_code": None,
            "container": None
        }
        
        # Vérifier le conteneur Docker
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name=ai-factory-{name}",
                 "--format", "{{.Status}}"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                status["container"] = result.stdout.strip()[:50]
                status["alive"] = "Up" in result.stdout
        except Exception:
            pass
        
        # Vérifier la réponse HTTP
        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 f"http://localhost:{port}", "--max-time", "3"],
                capture_output=True, text=True, timeout=5
            )
            status["http_code"] = result.stdout.strip()
            if not status["alive"] and result.stdout.strip() not in ("000", ""):
                status["alive"] = True
        except Exception:
            status["http_code"] = "N/A"
        
        return status

    @staticmethod
    def _get_ollama_models() -> list:
        """Récupère la liste des modèles Ollama."""
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:11434/api/tags"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                return [{
                    "name": m["name"],
                    "size": f"{m.get('size', 0) / 1e9:.1f}GB",
                    "modified": m.get("modified_at", "")[:10]
                } for m in data.get("models", [])]
        except Exception:
            pass
        return []

    @staticmethod
    def _detect_bots() -> list:
        """Détecte les bots actifs (Docker + workspace)."""
        bots = []
        
        # Bots Docker
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=bot-",
                 "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        bots.append({
                            "name": parts[0].replace("bot-", ""),
                            "status": parts[1][:30],
                            "type": "docker",
                            "image": parts[2] if len(parts) > 2 else ""
                        })
        except Exception:
            pass
        
        # Bots dans workspace/
        workspace_dir = FACTORY_DIR / "workspace"
        if workspace_dir.exists():
            for d in workspace_dir.iterdir():
                if d.is_dir() and (d / "main.py").exists():
                    # Éviter les doublons
                    if not any(b["name"] == d.name for b in bots):
                        bots.append({
                            "name": d.name,
                            "status": "stopped" if not any(
                                b["name"] == d.name for b in bots
                            ) else "running",
                            "type": "workspace",
                            "path": str(d)
                        })
        
        return bots

    @staticmethod
    def _count_skills() -> int:
        """Compte les skills installées."""
        registry_file = FACTORY_DIR / "registry" / "skills-registry.yaml"
        if registry_file.exists():
            try:
                import yaml
                with open(registry_file) as f:
                    registry = yaml.safe_load(f) or {}
                return len(registry.get("skills", []))
            except Exception:
                pass
        return 0

    @staticmethod
    def execute_action(action: str, params: dict = None) -> dict:
        """
        Exécute une action sur l'AI Factory.
        Appelé par les endpoints API d'AkyelIA.
        
        Actions disponibles:
        - "deploy_bot": Lance un bot dans Docker
        - "stop_bot": Arrête un bot
        - "restart_service": Redémarre un service Docker
        - "start_service": Démarre un service Docker
        - "factory_status": État de l'usine
        - "create_bot": Génère un nouveau bot
        """
        params = params or {}
        
        actions = {
            "factory_status": lambda: {
                "status": "ok",
                "data": AkyeliaBridge.factory_status()
            },
            
            "restart_service": lambda: AkyeliaBridge._docker_action(
                "restart", params.get("service", "")
            ),
            
            "start_service": lambda: AkyeliaBridge._docker_action(
                "start", params.get("service", "")
            ),
            
            "stop_service": lambda: AkyeliaBridge._docker_action(
                "stop", params.get("service", "")
            ),
            
            "deploy_bot": lambda: AkyeliaBridge._deploy_bot(
                params.get("bot_name", ""),
                params.get("bot_dir", "")
            ),
            
            "stop_bot": lambda: AkyeliaBridge._stop_bot(
                params.get("bot_name", "")
            ),
            
            "factory_logs": lambda: AkyeliaBridge._get_logs(
                params.get("service", "all"),
                int(params.get("lines", 50))
            ),
        }
        
        handler = actions.get(action)
        if handler:
            return handler()
        
        return {"status": "error", "message": f"Action inconnue: {action}"}

    @staticmethod
    def _docker_action(action: str, service: str) -> dict:
        """Exécute une action Docker compose."""
        if not service:
            return {"status": "error", "message": "Service requis"}
        
        try:
            result = subprocess.run(
                ["docker", "compose", action, f"ai-factory-{service}"],
                capture_output=True, text=True, timeout=30,
                cwd=str(DOCKER_COMPOSE_DIR)
            )
            
            if result.returncode == 0:
                return {
                    "status": "ok",
                    "action": action,
                    "service": service,
                    "message": f"✅ {action} réussi pour {service}"
                }
            else:
                return {
                    "status": "error",
                    "action": action,
                    "service": service,
                    "message": f"❌ {result.stderr[:200]}"
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def _deploy_bot(bot_name: str, bot_dir: str) -> dict:
        """Déploie un bot dans Docker."""
        if not bot_name or not bot_dir:
            return {"status": "error", "message": "bot_name et bot_dir requis"}
        
        bot_path = Path(bot_dir)
        if not bot_path.exists():
            return {"status": "error", "message": f"Dossier introuvable: {bot_dir}"}
        
        try:
            # Construction
            build = subprocess.run(
                ["docker", "build", "-t", f"ai-factory-bot-{bot_name}", "."],
                capture_output=True, text=True, timeout=120,
                cwd=str(bot_path)
            )
            if build.returncode != 0:
                return {"status": "error", "message": f"Build échoué: {build.stderr[:200]}"}
            
            # Lancement
            run = subprocess.run([
                "docker", "run", "-d",
                "--name", f"bot-{bot_name}",
                "--restart", "unless-stopped",
                "--network", "ai-factory-net",
                f"ai-factory-bot-{bot_name}"
            ], capture_output=True, text=True, timeout=30)
            
            if run.returncode == 0:
                return {
                    "status": "ok",
                    "bot_name": bot_name,
                    "container_id": run.stdout.strip()[:12],
                    "message": f"✅ Bot {bot_name} déployé!"
                }
            else:
                return {"status": "error", "message": run.stderr[:200]}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def _stop_bot(bot_name: str) -> dict:
        """Arrête un bot Docker."""
        if not bot_name:
            return {"status": "error", "message": "bot_name requis"}
        
        try:
            subprocess.run(
                ["docker", "stop", f"bot-{bot_name}"],
                capture_output=True, text=True, timeout=10
            )
            subprocess.run(
                ["docker", "rm", f"bot-{bot_name}"],
                capture_output=True, text=True, timeout=10
            )
            return {"status": "ok", "message": f"🛑 Bot {bot_name} arrêté"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def _get_logs(service: str = "all", lines: int = 50) -> dict:
        """Récupère les logs d'un service."""
        try:
            if service == "all":
                cmd = ["docker", "compose", "logs", "--tail", str(lines)]
            else:
                cmd = ["docker", "logs", "--tail", str(lines), f"ai-factory-{service}"]
            
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10,
                cwd=str(DOCKER_COMPOSE_DIR)
            )
            
            return {
                "status": "ok",
                "service": service,
                "logs": result.stdout[-5000:] if result.stdout else "Aucun log"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


# ============================================
# ENDPOINTS API (pour intégration dans app.py)
# ============================================

def register_endpoints(app):
    """
    Enregistre les endpoints AI Factory dans une app FastAPI.
    
    Usage dans app.py:
        from ai-factory.bridge.akyelia-bridge import register_endpoints
        register_endpoints(app)
    
    Ajoute les routes:
    - GET  /api/factory/status
    - POST /api/factory/action
    - GET  /api/factory/bots
    - GET  /api/factory/services
    """
    from fastapi import HTTPException
    
    @app.get("/api/factory/status")
    async def get_factory_status():
        """État complet de l'AI Factory."""
        return AkyeliaBridge.factory_status()
    
    @app.get("/api/factory/services")
    async def get_factory_services():
        """Liste des services avec leur état."""
        status = AkyeliaBridge.factory_status()
        return {
            "services": status["services"],
            "models": status["models"],
            "bots": status["bots"],
            "skills_count": status["skills_count"],
            "status": status["status"]
        }
    
    @app.get("/api/factory/bots")
    async def get_factory_bots():
        """Liste des bots actifs et disponibles."""
        bots = AkyeliaBridge._detect_bots()
        return {"bots": bots, "total": len(bots)}
    
    @app.post("/api/factory/action")
    async def execute_factory_action(request: dict):
        """
        Exécute une action sur l'AI Factory.
        
        Body:
            action: str (deploy_bot, stop_bot, restart_service, etc.)
            params: dict (optionnel)
        """
        action = request.get("action")
        params = request.get("params", {})
        
        if not action:
            raise HTTPException(status_code=400, detail="action requis")
        
        result = AkyeliaBridge.execute_action(action, params)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        return result
    
    @app.post("/api/factory/ingest-skill")
    async def ingest_skill(request: dict):
        """Ingère un dépôt GitHub comme skill."""
        repo_url = request.get("url")
        if not repo_url:
            raise HTTPException(status_code=400, detail="URL du dépôt requis")
        
        # Importer et lancer l'ingester
        sys.path.insert(0, str(FACTORY_DIR / "skills"))
        try:
            from github_ingester import GitHubIngester
            ingester = GitHubIngester()
            result = ingester.ingest(repo_url)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


# ============================================
# MODE MICROSERVICE STANDALONE
# ============================================
def run_microservice(port: int = 8765):
    """Lance le bridge comme microservice indépendant."""
    from fastapi import FastAPI, HTTPException
    import uvicorn
    
    app = FastAPI(
        title="AI Factory Bridge",
        description="Pont API entre AkyelIA et l'AI Factory",
        version="1.0.0"
    )
    
    # Enregistrer les endpoints
    register_endpoints(app)
    
    # Route racine
    @app.get("/")
    async def root():
        return {
            "service": "AI Factory Bridge",
            "version": "1.0.0",
            "status": AkyeliaBridge.factory_status()["status"],
            "endpoints": [
                "GET  /api/factory/status",
                "GET  /api/factory/services",
                "GET  /api/factory/bots",
                "POST /api/factory/action",
                "POST /api/factory/ingest-skill",
            ]
        }
    
    @app.get("/health")
    async def health():
        return {"status": "ok", "timestamp": datetime.now().isoformat()}
    
    print(f"""
╔═══════════════════════════════════════╗
║    🔌 AI FACTORY BRIDGE              ║
║    Pont AkyelIA ↔ Docker Stack       ║
╠═══════════════════════════════════════╣
║  Serveur: http://0.0.0.0:{port:<5}            ║
║  Statut: {AkyeliaBridge.factory_status()['status']:10}             ║
╚═══════════════════════════════════════╝
""")
    
    uvicorn.run(app, host="0.0.0.0", port=port)


# ============================================
# CLI
# ============================================
def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="AI FACTORY - AkyelIA Bridge"
    )
    
    parser.add_argument("--port", "-p", type=int, default=8765,
                       help="Port du microservice (défaut: 8765)")
    parser.add_argument("--check", "-c", action="store_true",
                       help="Vérifier la connexion à l'AI Factory")
    parser.add_argument("--status", "-s", action="store_true",
                       help="Afficher l'état de l'usine")
    
    args = parser.parse_args()
    
    if args.check:
        print("🔍 Vérification de la connexion...")
        status = AkyeliaBridge.factory_status()
        print(f"\nStatut: {status['status']}")
        for name, info in status["services"].items():
            alive = "✅" if info.get("alive") else "❌"
            print(f"  {alive} {name}: port={info['port']} code={info.get('http_code', 'N/A')}")
        print(f"\nModèles: {len(status['models'])}")
        print(f"Bots: {len(status['bots'])}")
        print(f"Skills: {status['skills_count']}")
        return
    
    if args.status:
        status = AkyeliaBridge.factory_status()
        print(json.dumps(status, indent=2))
        return
    
    # Mode microservice
    run_microservice(args.port)


if __name__ == "__main__":
    main()
