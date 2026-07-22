#!/usr/bin/env python3
"""
============================================
AI FACTORY - Launch Orchestrator
============================================
Point d'entrée unique pour toute l'AI Factory.
Une seule commande pour tout lancer, tout arrêter,
tout surveiller.

Usage:
    python3 launch.py                    # Menu interactif
    python3 launch.py start              # Tout démarrer
    python3 launch.py stop               # Tout arrêter
    python3 launch.py status             # État complet
    python3 launch.py logs               # Logs en direct
    python3 launch.py models             # Installer les modèles
    python3 launch.py bot "description"  # Créer un bot
    python3 launch.py skill "URL"        # Ingérer un skill
    python3 launch.py update             # Mettre à jour tout le code
    python3 launch.py doctor             # Diagnostiquer et réparer
============================================
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
VERSION = "1.0.0"


class Colors:
    BOLD = '\033[1m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'


def log(msg, color=Colors.GREEN):
    print(f"{color}[LAUNCH]{Colors.NC} {msg}")


def banner():
    print(f"""{Colors.CYAN}
╔══════════════════════════════════════════════════════╗
║                                                     ║
║     █████╗ ██╗    ███████╗ █████╗  ██████╗████████╗ ║
║    ██╔══██╗██║    ██╔════╝██╔══██╗██╔════╝╚══██╔══╝ ║
║    ███████║██║    █████╗  ███████║██║        ██║    ║
║    ██╔══██║██║    ██╔══╝  ██╔══██║██║        ██║    ║
║    ██║  ██║██║    ██║     ██║  ██║╚██████╗   ██║    ║
║    ╚═╝  ╚═╝╚═╝    ╚═╝     ╚═╝  ╚═╝ ╚═════╝   ╚═╝    ║
║                                                     ║
║        🏭 AI FACTORY - Orchestrateur v{VERSION}         ║
║        Votre usine à agents autonomes               ║
╚══════════════════════════════════════════════════════╝{Colors.NC}
""")


# ============================================
# COMMANDES SYSTÈME
# ============================================

def cmd_docker_compose(action: str, service: str = "") -> bool:
    """Exécute une commande docker compose."""
    cmd = ["docker", "compose", action]
    if service:
        cmd.append(f"ai-factory-{service}")
    
    try:
        result = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True)
        if result.returncode != 0:
            if "No such service" not in result.stderr:
                log(f"⚠️ {result.stderr[:200]}", Colors.YELLOW)
        return result.returncode == 0
    except FileNotFoundError:
        log("❌ Docker n'est pas installé !", Colors.RED)
        return False


def cmd_docker_bot(action: str, bot_name: str) -> bool:
    """Actions sur les bots Docker."""
    try:
        subprocess.run(["docker", action, f"bot-{bot_name}"],
                      capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def check_command(cmd: str) -> bool:
    """Vérifie si une commande est disponible."""
    return shutil.which(cmd) is not None


# ============================================
# FONCTIONS PRINCIPALES
# ============================================

def start(services: str = "all"):
    """Démarre tous les services de l'AI Factory."""
    banner()
    log("🚀 Démarrage de l'AI Factory...", Colors.CYAN)
    
    # 1. Vérifier Docker
    if not check_command("docker"):
        log("❌ Docker n'est pas installé !", Colors.RED)
        log("   → curl -fsSL https://get.docker.com | sh")
        return False
    
    # 2. Créer la structure
    for d in ["data/ollama", "data/qdrant", "data/n8n", "data/open-webui",
              "data/caddy/data", "data/caddy/config", "data/logs",
              "skills", "workspace", "registry", "config/caddy", "config/openhands"]:
        (BASE_DIR / d).mkdir(parents=True, exist_ok=True)
    
    # 3. Configurer .env si nécessaire
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        template = BASE_DIR / "ai-factory.env.template"
        if template.exists():
            shutil.copy(template, env_file)
            log("📝 .env créé depuis le template (modifie les mots de passe !)", Colors.YELLOW)
    
    # 4. Lancer la stack Docker
    log("🐳 Lancement des conteneurs Docker...")
    if services == "all":
        success = cmd_docker_compose("up", "-d")
    else:
        success = cmd_docker_compose("up", "-d") and cmd_docker_compose("start", services)
    
    if success:
        log("✅ Stack Docker démarrée !", Colors.GREEN)
    else:
        log("⚠️某些 services ont peut-être échoué. Vérifie avec 'status'.", Colors.YELLOW)
    
    # 5. Attendre que les services soient prêts
    log("⏳ Attente du démarrage des services...")
    time.sleep(10)
    
    # 6. Vérifier les services
    status()
    
    # 7. Suggérer les prochaines étapes
    print(f"""
{Colors.CYAN}═══════════════════════════════════════{Colors.NC}
{Colors.GREEN}  ✅ AI FACTORY OPÉRATIONNELLE !{Colors.NC}
{Colors.CYAN}═══════════════════════════════════════{Colors.NC}

  📍 OpenHands:     http://localhost:3000
  📍 Open WebUI:    http://localhost:3001
  📍 Ollama API:    http://localhost:11434
  📍 Qdrant:       http://localhost:6333
  📍 n8n:          http://localhost:5678
  📍 MCP Server:   http://localhost:8766

{Colors.YELLOW}  Prochaines étapes:{Colors.NC}
  • Installer les modèles :  python3 launch.py models
  • Créer un bot :           python3 launch.py bot "ma description"
  • Dashboard web :          python3 launch.py dashboard
  • Voir les logs :          python3 launch.py logs
""")
    return True


def stop(services: str = "all"):
    """Arrête tous les services."""
    log("🛑 Arrêt de l'AI Factory...", Colors.YELLOW)
    
    if services == "all":
        cmd_docker_compose("down")
        log("✅ Tous les services arrêtés", Colors.GREEN)
    else:
        cmd_docker_compose("stop", services)
        log(f"✅ Service {services} arrêté", Colors.GREEN)


def status():
    """Affiche l'état de tous les services."""
    import httpx
    
    print(f"\n{Colors.BOLD}📊 ÉTAT DES SERVICES{Colors.NC}")
    print("-" * 60)
    
    services = {
        "🧠 Ollama": ("http://localhost:11434/api/tags", True),
        "💾 Qdrant": ("http://localhost:6333/healthz", False),
        "🧠 OpenHands": ("http://localhost:3000/api/health", True),
        "💬 Open WebUI": ("http://localhost:3001", True),
        "⚡ n8n": ("http://localhost:5678", True),
        "🌐 Browserless": ("http://localhost:3002/health", False),
        "🔌 MCP Server": ("http://localhost:8766", True),
    }
    
    all_ok = True
    for name, (url, check_json) in services.items():
        status_text = f"{Colors.RED}❌ Hors ligne{Colors.NC}"
        try:
            r = httpx.get(url, timeout=3)
            if r.status_code < 500:
                status_text = f"{Colors.GREEN}✅ En ligne{Colors.NC}"
            else:
                all_ok = False
                status_text = f"{Colors.YELLOW}⚠️  Anormal ({r.status_code}){Colors.NC}"
        except Exception:
            all_ok = False
            status_text = f"{Colors.RED}❌ Hors ligne{Colors.NC}"
        
        print(f"  {name:20} {status_text}")
    
    # Bots Docker
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=bot-", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5
        )
        bots = [b for b in result.stdout.strip().split("\n") if b]
        if bots:
            print(f"\n{Colors.BOLD}🤖 BOTS ACTIFS{Colors.NC}")
            for bot in bots:
                print(f"  🤖 {bot}")
    except Exception:
        pass
    
    # Stats
    print(f"\n{Colors.BOLD}📈 STATISTIQUES{Colors.NC}")
    skills_dir = BASE_DIR / "skills"
    py_files = len(list(skills_dir.rglob("*.py"))) if skills_dir.exists() else 0
    workspace_files = len(list((BASE_DIR / "workspace").rglob("*"))) if (BASE_DIR / "workspace").exists() else 0
    print(f"  📦 Skills disponibles: {py_files}")
    print(f"  📁 Projets workspace:   {workspace_files}")
    
    print(f"\n{Colors.CYAN}  python3 launch.py logs   → Voir les logs{Colors.NC}")
    print(f"{Colors.CYAN}  python3 launch.py doctor → Diagnostiquer{Colors.NC}")
    print()
    
    return all_ok


def follow_logs(service: str = "all", lines: int = 50):
    """Affiche les logs des services."""
    if service == "all":
        print(f"\n{Colors.BOLD}📋 LOGS DE TOUS LES SERVICES{Colors.NC}\n")
        subprocess.run(
            ["docker", "compose", "logs", "--tail", str(lines)],
            cwd=str(BASE_DIR)
        )
    else:
        print(f"\n{Colors.BOLD}📋 LOGS DE {service}{Colors.NC}\n")
        subprocess.run(
            ["docker", "logs", f"ai-factory-{service}", "--tail", str(lines)],
            cwd=str(BASE_DIR)
        )


def install_models(models: list = None):
    """Télécharge les modèles Ollama recommandés."""
    if models is None:
        models = [
            "qwen2.5-coder:14b",
            "llama3.2:3b",
            "nomic-embed-text",
            "llava:7b",
        ]
    
    banner()
    log("📦 Installation des modèles Ollama...", Colors.CYAN)
    
    for model in models:
        log(f"⏳ Téléchargement de {model}...")
        result = subprocess.run(
            ["docker", "exec", "ai-factory-ollama", "ollama", "pull", model],
            capture_output=True, text=True, timeout=600
        )
        if result.returncode == 0:
            log(f"✅ {model} installé", Colors.GREEN)
        else:
            log(f"❌ {model}: {result.stderr[:100]}", Colors.RED)


def doctor():
    """Diagnostique et répare les problèmes courants."""
    banner()
    log("🔍 Diagnostic de l'AI Factory...", Colors.CYAN)
    
    issues = []
    fixes = []
    
    # 1. Vérifier Docker
    log("🔧 Vérification de Docker...")
    if not check_command("docker"):
        issues.append("Docker n'est pas installé")
        fixes.append("curl -fsSL https://get.docker.com | sh")
    
    # 2. Vérifier docker compose
    if not check_command("docker"):
        issues.append("Docker Compose non trouvé")
    else:
        # 3. Vérifier que le docker-compose.yml existe
        if not (BASE_DIR / "docker-compose.yml").exists():
            issues.append("docker-compose.yml introuvable")
    
    # 4. Vérifier les conteneurs
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=5
        )
        running = result.stdout.strip().split("\n")
        expected = ["ai-factory-ollama", "ai-factory-qdrant",
                    "ai-factory-openhands", "ai-factory-n8n",
                    "ai-factory-browserless"]
        
        for container in expected:
            if container not in running:
                issues.append(f"Conteneur {container} ne tourne pas")
                fixes.append(f"docker compose start {container.replace('ai-factory-', '')}")
    except Exception:
        issues.append("Impossible de lister les conteneurs Docker")
    
    # 5. Vérifier les dossiers
    for d in ["data", "skills", "workspace", "registry", "config"]:
        if not (BASE_DIR / d).exists():
            issues.append(f"Dossier {d}/ manquant")
            fixes.append(f"mkdir -p {d}")
    
    # 6. Vérifier les permissions
    docker_sock = Path("/var/run/docker.sock")
    if not docker_sock.exists():
        issues.append("Socket Docker non accessible")
        fixes.append("Vérifie que Docker tourne et que l'utilisateur a les droits")
    
    # Résumé
    if issues:
        print(f"\n{Colors.YELLOW}⚠️  Problèmes détectés ({len(issues)}):{Colors.NC}")
        for i, issue in enumerate(issues, 1):
            print(f"\n  {i}. {issue}")
            if i - 1 < len(fixes):
                print(f"     🔧 Solution: {fixes[i-1]}")
        
        # Tentative de réparation automatique
        print(f"\n{Colors.CYAN}🔧 Tentative de réparation automatique...{Colors.NC}")
        
        if not check_command("docker"):
            log("❌ Installe Docker manuellement puis relance", Colors.RED)
        else:
            # Recréer les dossiers manquants
            for d in ["data/ollama", "data/qdrant", "data/n8n", "data/open-webui",
                      "data/caddy/data", "data/caddy/config", "data/logs",
                      "skills", "workspace", "registry", "config/caddy", "config/openhands"]:
                (BASE_DIR / d).mkdir(parents=True, exist_ok=True)
            log("✅ Dossiers recréés", Colors.GREEN)
            
            # Tentative de redémarrage
            log("🔄 Redémarrage des services...")
            cmd_docker_compose("up", "-d")
            log("✅ Services redémarrés", Colors.GREEN)
    else:
        print(f"\n{Colors.GREEN}✅ Aucun problème détecté. Tout est opérationnel !{Colors.NC}")
    
    # Afficher les stats
    print(f"\n{Colors.BOLD}📊 SYSTÈME{Colors.NC}")
    try:
        result = subprocess.run(["free", "-h"], capture_output=True, text=True)
        print(f"  {result.stdout.split(chr(10))[1]}")
    except Exception:
        pass
    try:
        result = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
        print(f"  {result.stdout.split(chr(10))[1]}")
    except Exception:
        pass


def create_bot(description: str, platform: str = "web", deploy: bool = False):
    """Crée un bot via le Bot Generator."""
    log(f"🤖 Création du bot: {description}", Colors.CYAN)
    
    cmd = ["python3", str(BASE_DIR / "skills" / "bot-generator.py"),
           "--target", platform, "--action", description]
    if deploy:
        cmd.append("--deploy")
    
    subprocess.run(cmd)


def ingest_skill(url: str):
    """Ingère un skill GitHub."""
    log(f"📥 Ingestion du skill: {url}", Colors.CYAN)
    
    subprocess.run(
        ["python3", str(BASE_DIR / "skills" / "github-ingester.py"), url]
    )


def update():
    """Met à jour le code depuis GitHub."""
    log("🔄 Mise à jour de l'AI Factory...", Colors.CYAN)
    
    # Vérifier si on est dans un repo Git
    if (BASE_DIR / ".git").exists():
        subprocess.run(["git", "pull"], cwd=str(BASE_DIR))
        log("✅ Code mis à jour", Colors.GREEN)
    else:
        log("⚠️ Pas de dépôt Git détecté", Colors.YELLOW)
        log("   Clone le projet: git clone https://github.com/Akyelcattleya/akyelia.git")


def dashboard():
    """Ouvre le dashboard web ou affiche les instructions."""
    dashboard_path = BASE_DIR / "bridge" / "dashboard.html"
    if dashboard_path.exists():
        print(f"""
{Colors.CYAN}╔═══════════════════════════════════════╗
║    📊 AI FACTORY - DASHBOARD        ║
╚═══════════════════════════════════════╝{Colors.NC}

  Ouvre ce fichier dans ton navigateur :
  
  {Colors.GREEN}file://{dashboard_path.absolute()}{Colors.NC}
  
  Ou si tu as Python http.server :
  {Colors.GREEN}cd ai-factory/bridge && python3 -m http.server 8080{Colors.NC}
  → http://localhost:8080/dashboard.html

  Ou lance AkyelIA Bridge :
  {Colors.GREEN}python3 bridge/akyelia-bridge.py{Colors.NC}
  → http://localhost:8766
""")
    else:
        log("❌ Dashboard introuvable", Colors.RED)


def interactive_menu():
    """Mode interactif avec menu."""
    banner()
    
    while True:
        print(f"""
{Colors.BOLD}MENU PRINCIPAL{Colors.NC}
{Colors.CYAN}───{Colors.NC}
  1) 🚀  Démarrer l'usine
  2) 🛑  Arrêter l'usine
  3) 📊  État des services
  4) 📋  Voir les logs
  5) 🤖  Créer un bot
  6) 📥  Ingérer un skill GitHub
  7) 📦  Installer les modèles Ollama
  8) 🔧  Diagnostiquer et réparer
  9) 📱  Dashboard web
  10) 🗑️  arrêter et tout nettoyer
  0)  ❌ Quitter
{Colors.CYAN}───{Colors.NC}
""")
        choice = input(f"{Colors.BOLD}Choix: {Colors.NC}").strip()
        
        if choice == "1":
            start()
        elif choice == "2":
            stop()
        elif choice == "3":
            status()
        elif choice == "4":
            s = input("Service (entrée = tous): ").strip()
            follow_logs(s if s else "all")
        elif choice == "5":
            desc = input("Description du bot: ").strip()
            if desc:
                create_bot(desc)
        elif choice == "6":
            url = input("URL GitHub: ").strip()
            if url:
                ingest_skill(url)
        elif choice == "7":
            install_models()
        elif choice == "8":
            doctor()
        elif choice == "9":
            dashboard()
        elif choice == "10":
            confirm = input("⚠️  Tout arrêter et nettoyer ? (oui/non): ").strip()
            if confirm == "oui":
                stop()
                cmd_docker_compose("down", "-v")
                log("🧹 Tout a été nettoyé")
        elif choice in ("0", "q", "quit"):
            print(f"\n{Colors.GREEN}👋 À bientôt !{Colors.NC}")
            break


# ============================================
# CLI
# ============================================
def main():
    parser = argparse.ArgumentParser(
        description="🏭 AI FACTORY - Orchestrateur Global",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("command", nargs="?", default="menu",
                       help="Commande à exécuter")
    parser.add_argument("args", nargs="*", help="Arguments supplémentaires")
    parser.add_argument("--service", "-s", default="all",
                       help="Nom du service (pour start/stop/logs)")
    parser.add_argument("--lines", "-l", type=int, default=50,
                       help="Nombre de lignes de logs")
    parser.add_argument("--deploy", "-d", action="store_true",
                       help="Déployer dans Docker (pour bot)")
    parser.add_argument("--platform", "-p", default="web",
                       help="Plateforme (pour bot)")
    
    args = parser.parse_args()
    
    cmd = args.command.lower()
    
    if cmd in ("start", "up"):
        start(args.service)
    elif cmd in ("stop", "down"):
        stop(args.service)
    elif cmd in ("status", "st", "ps"):
        status()
    elif cmd in ("logs", "log"):
        follow_logs(args.service, args.lines)
    elif cmd in ("models", "model"):
        install_models()
    elif cmd in ("bot", "create"):
        desc = " ".join(args.args) if args.args else "bot personnalisé"
        create_bot(desc, args.platform, args.deploy)
    elif cmd in ("skill", "ingest"):
        url = " ".join(args.args) if args.args else ""
        if url:
            ingest_skill(url)
        else:
            print("Usage: python3 launch.py skill https://github.com/user/repo")
    elif cmd in ("doctor", "diagnostic", "repair", "fix"):
        doctor()
    elif cmd in ("update", "upgrade", "pull"):
        update()
    elif cmd in ("dashboard", "dash", "web"):
        dashboard()
    elif cmd in ("menu", "interactive"):
        interactive_menu()
    else:
        parser.print_help()
        print(f"""
{Colors.BOLD}Commandes disponibles:{Colors.NC}
  start               Démarrer l'AI Factory
  stop                Arrêter l'AI Factory
  status              État des services
  logs                Voir les logs
  models              Installer les modèles Ollama
  bot "description"   Créer un bot
  skill "URL"         Ingérer un skill GitHub
  doctor              Diagnostiquer et réparer
  dashboard           Dashboard web
  update              Mettre à jour depuis GitHub
  menu                Menu interactif
        """)


if __name__ == "__main__":
    main()
