#!/usr/bin/env python3
"""
============================================
AI FACTORY - Bot Generator
============================================
Générateur de bots automatiques.
Donne une instruction en français, il crée le bot.

Usage:
    python3 bot-generator.py --target linkedin --action prospect
    python3 bot-generator.py --target instagram --action "like stories & comment"
    python3 bot-generator.py --interactive   # Mode dialogue

Prérequis: Ollama doit tourner (docker compose up -d ollama)
============================================
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

# ============================================
# CONFIGURATION
# ============================================
BASE_DIR = Path(__file__).parent.parent  # ai-factory/
SKILLS_DIR = BASE_DIR / "skills"
WORKSPACE_DIR = BASE_DIR / "workspace"
STEALTH_TEMPLATE = SKILLS_DIR / "stealth-module" / "template.py"
REGISTRY_FILE = BASE_DIR / "registry" / "skills-registry.yaml"
OLLAMA_API = os.getenv("OLLAMA_API_URL", "http://localhost:11434")

# S'assurer que les dossiers existent
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================
# MOTEUR LLM - Dialogue avec Ollama
# ============================================
class LLMEngine:
    """Interface avec Ollama pour la génération de code."""

    def __init__(self, model: str = "qwen2.5-coder:14b"):
        self.model = model
        self.api_url = f"{OLLAMA_API}/api/generate"

    def ask(self, prompt: str, system: str = None) -> str:
        """Envoie un prompt à Ollama et retourne la réponse."""
        import httpx
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 4096
            }
        }
        
        if system:
            payload["system"] = system
        
        try:
            with httpx.Client(timeout=120) as client:
                r = client.post(self.api_url, json=payload)
                if r.status_code == 200:
                    return r.json().get("response", "")
                else:
                    print(f"⚠️ Erreur API Ollama: {r.status_code}")
                    return ""
        except Exception as e:
            print(f"❌ Impossible de contacter Ollama: {e}")
            print("   Vérifie que le conteneur tourne: docker compose ps")
            return ""

    def generate_code(self, instruction: str, context: str = "") -> dict:
        """Génère le code d'un bot à partir d'une instruction."""
        system_prompt = """Tu es un expert en génération de bots d'automatisation.
Tu génères du code Python utilisant Playwright pour l'automatisation web.
Tu respectes les meilleures pratiques anti-détection : délais aléatoires,
mouvements de souris réalistes, gestion des sessions, rotation de proxies.

Règles :
- Utilise uniquement Playwright (pas Selenium)
- Inclus des délais humains aléatoires
- Gère les erreurs et les timeouts
- Limite les actions par heure (anti-blocage)
- Ajoute un système de logging
- Le bot doit être résilient aux changements de l'interface cible

Format de réponse : 
```python
[code complet du bot]
```
```json
{
  "name": "nom-du-bot",
  "description": "description",
  "platform": "linkedin|instagram|etc",
  "actions": ["action1", "action2"],
  "config": {"max_per_hour": 10, "min_delay": 2}
}
```"""
        
        user_prompt = f"""Génère un bot pour automatiser la tâche suivante :
        
Instruction: {instruction}

Contexte additionnel:
{context}

Utilise le template de base avec Playwright. Assure-toi que le bot :
1. Se connecte à la plateforme cible
2. Effectue les actions demandées
3. Respecte les limites pour ne pas être détecté
4. Sauvegarde les sessions"""
        
        response = self.ask(user_prompt, system_prompt)
        return self._parse_response(response, instruction)

    def _parse_response(self, response: str, instruction: str) -> dict:
        """Extrait le code et la config de la réponse de l'IA."""
        result = {
            "code": "",
            "config": {
                "name": self._generate_name(instruction),
                "description": instruction[:100],
                "platform": "generic",
                "actions": [],
                "max_per_hour": 10,
                "min_delay": 2
            },
            "success": False
        }
        
        # Extraire le code Python
        code_match = re.search(r'```python\n(.*?)\n```', response, re.DOTALL)
        if code_match:
            result["code"] = code_match.group(1).strip()
        
        # Extraire la config JSON
        json_match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
        if json_match:
            try:
                config = json.loads(json_match.group(1))
                result["config"].update(config)
            except json.JSONDecodeError:
                pass
        
        # Fallback : si pas de code trouvé, utiliser le template
        if not result["code"]:
            result["code"] = self._generate_fallback_code(instruction)
            result["success"] = False
            print("⚠️ L'IA n'a pas généré de code, utilisation du template générique")
        else:
            result["success"] = True
        
        return result

    def _generate_name(self, instruction: str) -> str:
        """Génère un nom de bot à partir de l'instruction."""
        words = instruction.lower().split()[:4]
        name = "-".join(words)
        name = re.sub(r'[^a-z0-9-]', '', name)
        return name or "custom-bot"

    def _generate_fallback_code(self, instruction: str) -> str:
        """Génère un code de fallback basique."""
        # Lire le template existant
        if STEALTH_TEMPLATE.exists():
            code = STEALTH_TEMPLATE.read_text()
            # Adapter la config
            code = code.replace(
                '"target_url": os.getenv("BOT_TARGET_URL", "https://exemple.com")',
                f'"target_url": os.getenv("BOT_TARGET_URL", "https://github.com")'
            )
            return code
        return ""


# ============================================
# GÉNÉRATEUR DE BOTS
# ============================================
class BotGenerator:
    """Génère, configure et déploie des bots."""

    def __init__(self, llm: LLMEngine = None):
        self.llm = llm or LLMEngine()
        self.generated_bots = []

    def list_existing_bots(self) -> list:
        """Liste les bots déjà générés dans workspace/."""
        bots = []
        if WORKSPACE_DIR.exists():
            for d in WORKSPACE_DIR.iterdir():
                if d.is_dir() and (d / "main.py").exists():
                    bots.append({
                        "name": d.name,
                        "path": str(d),
                        "created": datetime.fromtimestamp(d.stat().st_mtime).isoformat(),
                        "has_dockerfile": (d / "Dockerfile").exists()
                    })
        return bots

    def generate(self, instruction: str, platform: str = None, 
                 output_dir: str = None) -> dict:
        """
        Génère un bot complet à partir d'une instruction.
        
        Args:
            instruction: Description en français de ce que le bot doit faire
            platform: Plateforme cible (linkedin, instagram, twitter, etc.)
            output_dir: Dossier de sortie (sinon workspace/nom-du-bot/)
        
        Returns:
            dict: Informations sur le bot généré
        """
        print(f"\n{'='*60}")
        print(f"🤖 GÉNÉRATION DE BOT")
        print(f"{'='*60}")
        print(f"📝 Instruction: {instruction}")
        if platform:
            print(f"🎯 Plateforme: {platform}")
        print()
        
        # 1. Analyser la demande avec l'IA
        print("🧠 Analyse de la demande avec l'IA...")
        context = ""
        if platform:
            context = f"Plateforme cible: {platform}"
        
        result = self.llm.generate_code(instruction, context)
        config = result["config"]
        
        # 2. Créer le dossier du bot
        bot_name = config["name"]
        bot_id = f"{bot_name}-{uuid.uuid4().hex[:6]}"
        bot_dir = Path(output_dir or WORKSPACE_DIR) / bot_id
        bot_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. Écrire le code
        print(f"📁 Création du bot dans: {bot_dir}")
        main_file = bot_dir / "main.py"
        main_file.write_text(result["code"])
        
        # 4. Créer le Dockerfile
        dockerfile = self._generate_dockerfile(bot_name, config)
        (bot_dir / "Dockerfile").write_text(dockerfile)
        
        # 5. Créer la configuration
        config_file = bot_dir / "config.json"
        config_file.write_text(json.dumps(config, indent=2))
        
        # 6. Créer les scripts de démarrage
        self._create_run_scripts(bot_dir, bot_name, config)
        
        # 7. Créer le README du bot
        self._create_bot_readme(bot_dir, instruction, config)
        
        # 8. Ajouter au registre
        self._add_to_registry(bot_name, bot_dir, config)
        
        bot_info = {
            "id": bot_id,
            "name": bot_name,
            "path": str(bot_dir),
            "platform": config.get("platform", "generic"),
            "actions": config.get("actions", []),
            "generated_by_ai": result["success"],
            "has_dockerfile": True,
            "created_at": datetime.now().isoformat(),
        }
        
        self.generated_bots.append(bot_info)
        
        print(f"\n✅ Bot généré avec succès!")
        print(f"   📍 Dossier: {bot_dir}")
        print(f"   🏷️  Nom: {bot_name}")
        print(f"   🐳 Dockerfile: {'✅' if (bot_dir/'Dockerfile').exists() else '❌'}")
        print()
        
        return bot_info

    def _generate_dockerfile(self, bot_name: str, config: dict) -> str:
        """Génère un Dockerfile pour le bot."""
        return f"""# ============================================
# AI FACTORY - Bot: {bot_name}
# Généré automatiquement le {datetime.now().isoformat()}
# ============================================
FROM python:3.12-slim

WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \\
    curl gnupg ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

# Installer Playwright et les dépendances
RUN pip install --no-cache-dir playwright playwright-stealth httpx aiofiles

# Installer les navigateurs Playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Copier le code du bot
COPY main.py .
COPY config.json .

# Variables d'environnement
ENV BOT_NAME={bot_name}
ENV BOT_MAX_ACTIONS_HOUR={config.get("max_per_hour", 10)}
ENV BOT_MIN_DELAY={config.get("min_delay", 2)}
ENV BOT_MAX_DELAY=8
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \\
    CMD python3 -c "import json; json.load(open('config.json'))" || exit 1

CMD ["python3", "main.py"]
"""

    def _create_run_scripts(self, bot_dir: Path, bot_name: str, config: dict):
        """Crée les scripts pour lancer/arrêter le bot."""
        
        # Script de lancement
        run_sh = bot_dir / "run.sh"
        run_sh.write_text(f"""#!/bin/bash
# ============================================
# Lancer le bot {bot_name}
# ============================================
set -e

echo "🚀 Démarrage du bot: {bot_name}"

# Vérifier les dépendances
pip install -q playwright playwright-stealth httpx aiofiles
playwright install chromium 2>/dev/null

# Lancer le bot
echo "📡 Connexion à la cible..."
python3 main.py
""")
        run_sh.chmod(0o755)
        
        # Script de lancement via Docker
        run_docker = bot_dir / "run-docker.sh"
        run_docker.write_text(f"""#!/bin/bash
# ============================================
# Lancer le bot {bot_name} dans Docker
# ============================================
set -e

IMAGE_NAME="ai-factory-bot-{bot_name}"

echo "🏗️  Construction de l'image Docker..."
docker build -t $IMAGE_NAME .

echo "🚀 Lancement du conteneur..."
docker run -d \\
    --name bot-{bot_name} \\
    --restart unless-stopped \\
    --network ai-factory-net \\
    -e BOT_PROXY_URL="$BOT_PROXY_URL" \\
    $IMAGE_NAME

echo "✅ Bot {bot_name} lancé!"
echo "   Logs: docker logs -f bot-{bot_name}"
echo "   Arrêt: docker stop bot-{bot_name}"
""")
        run_docker.chmod(0o755)
        
        # Script d'arrêt
        stop_sh = bot_dir / "stop.sh"
        stop_sh.write_text(f"""#!/bin/bash
echo "🛑 Arrêt du bot: {bot_name}"
docker stop bot-{bot_name} 2>/dev/null || true
docker rm bot-{bot_name} 2>/dev/null || true
echo "✅ Bot arrêté"
""")
        stop_sh.chmod(0o755)

    def _create_bot_readme(self, bot_dir: Path, instruction: str, config: dict):
        """Crée la documentation du bot."""
        readme = bot_dir / "README.md"
        readme.write_text(f"""# 🤖 Bot: {config['name']}

## Description
{instruction}

## Configuration
- **Plateforme**: {config.get('platform', 'generic')}
- **Actions**: {', '.join(config.get('actions', []))}
- **Max actions/heure**: {config.get('max_per_hour', 10)}
- **Délai min**: {config.get('min_delay', 2)}s

## Utilisation

### En local
```bash
./run.sh
```

### Dans Docker
```bash
./run-docker.sh
```

### Variables d'environnement
- `BOT_PROXY_URL`: Proxy optionnel
- `BOT_TARGET_URL`: URL cible (si applicable)
- `BOT_MAX_ACTIONS_HOUR`: Actions max par heure
- `BOT_MIN_DELAY`: Délai min entre actions

## Logs
```bash
docker logs -f bot-{config['name']}
```

## Généré le
{datetime.now().isoformat()}
""")

    def _add_to_registry(self, bot_name: str, bot_dir: Path, config: dict):
        """Ajoute le bot au registre des skills."""
        if not REGISTRY_FILE.exists():
            return
        
        try:
            content = REGISTRY_FILE.read_text()
            entry = f"""
  - name: "{bot_name}"
    source: "generated"
    type: "bot"
    path: "{bot_dir}"
    description: "{config.get('description', 'Bot généré automatiquement')}"
    version: "1.0.0"
    enabled: true
    api_endpoint: ""\n"""
            
            # Ajouter avant la section "pending"
            content = content.replace("pending:", f"{entry}\npending:")
            REGISTRY_FILE.write_text(content)
            
        except Exception as e:
            print(f"⚠️ Impossible de mettre à jour le registre: {e}")

    def deploy_docker(self, bot_info: dict) -> bool:
        """
        Déploie un bot généré dans Docker.
        
        Args:
            bot_info: Informations retournées par generate()
        
        Returns:
            bool: True si le déploiement a réussi
        """
        bot_dir = Path(bot_info["path"])
        bot_name = bot_info["name"]
        
        print(f"\n🐳 Déploiement de {bot_name} dans Docker...")
        
        try:
            # Build l'image
            subprocess.run(
                ["docker", "build", "-t", f"ai-factory-bot-{bot_name}", "."],
                cwd=bot_dir,
                check=True,
                capture_output=True
            )
            
            # Lancer le conteneur
            subprocess.run([
                "docker", "run", "-d",
                "--name", f"bot-{bot_name}",
                "--restart", "unless-stopped",
                "--network", "ai-factory-net",
                f"ai-factory-bot-{bot_name}"
            ], check=True, capture_output=True)
            
            print(f"✅ Bot {bot_name} déployé avec succès!")
            print(f"   Logs: docker logs -f bot-{bot_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Erreur de déploiement: {e.stderr.decode() if e.stderr else e}")
            return False
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False


# ============================================
# MODE INTERACTIF
# ============================================
def interactive_mode():
    """Mode dialogue : pose des questions pour créer le bot."""
    print("""
╔═══════════════════════════════════════╗
║   🤖 AI FACTORY - Bot Generator      ║
║   Mode interactif                     ║
║   Décris ce que tu veux automatiser ! ║
╚═══════════════════════════════════════╝
""")
    
    generator = BotGenerator()
    
    while True:
        print("\n---")
        instruction = input("🎯 Que veux-tu automatiser ? (ou 'quit'): ").strip()
        
        if instruction.lower() in ('quit', 'q', 'exit'):
            print("\n👋 À bientôt !")
            break
        
        if not instruction:
            continue
        
        # Demander des précisions
        platform = input("📱 Plateforme cible (linkedin/instagram/twitter/web/entrée): ").strip() or None
        deploy = input("🐳 Déployer dans Docker ? (oui/non): ").strip().lower() in ('oui', 'o', 'yes', 'y', '')
        
        # Générer le bot
        bot_info = generator.generate(instruction, platform)
        
        # Déployer si demandé
        if deploy and bot_info:
            print()
            generator.deploy_docker(bot_info)
        
        print("\n✅ Fait ! Tu peux trouver ton bot dans:", bot_info["path"])


# ============================================
# CLI
# ============================================
def main():
    parser = argparse.ArgumentParser(
        description="AI FACTORY - Bot Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python3 bot-generator.py --interactive
  python3 bot-generator.py --target linkedin --action "prospecter et envoyer des invitations"
  python3 bot-generator.py --target instagram --action "liker les posts récents" --deploy
  python3 bot-generator.py --list
        """
    )
    
    parser.add_argument("--interactive", "-i", action="store_true",
                       help="Mode interactif")
    parser.add_argument("--target", "-t", 
                       help="Plateforme cible (linkedin, instagram, twitter, web)")
    parser.add_argument("--action", "-a",
                       help="Action à automatiser")
    parser.add_argument("--deploy", "-d", action="store_true",
                       help="Déployer dans Docker après génération")
    parser.add_argument("--list", "-l", action="store_true",
                       help="Lister les bots existants")
    parser.add_argument("--model", "-m", default="qwen2.5-coder:14b",
                       help="Modèle Ollama à utiliser")
    
    args = parser.parse_args()
    
    generator = BotGenerator(LLMEngine(model=args.model))
    
    if args.list:
        bots = generator.list_existing_bots()
        if bots:
            print(f"\n📋 Bots existants ({len(bots)}):")
            for bot in bots:
                print(f"   🤖 {bot['name']} - {bot['created'][:10]}" + 
                      f" {'🐳' if bot['has_dockerfile'] else ''}")
        else:
            print("\n📋 Aucun bot généré pour le moment.")
        return
    
    if args.interactive:
        interactive_mode()
        return
    
    if args.target and args.action:
        instruction = f"{args.action} sur {args.target}"
        bot_info = generator.generate(instruction, args.target)
        
        if args.deploy and bot_info:
            generator.deploy_docker(bot_info)
        return
    
    # Si aucun argument, afficher l'aide
    parser.print_help()


if __name__ == "__main__":
    main()
