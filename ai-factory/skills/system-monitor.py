#!/usr/bin/env python3
"""
============================================
AI FACTORY - System Monitor
============================================
Dashboard CLI pour surveiller l'état de santé
de tous les services, bots, et ressources.

Usage:
    python3 system-monitor.py          # Dashboard en temps réel
    python3 system-monitor.py --status  # État des services
    python3 system-monitor.py --logs    # Dernières erreurs
    python3 system-monitor.py --bots    # Bots actifs
    python3 system-monitor.py --check   # Health check complet
============================================
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ============================================
# CONFIGURATION
# ============================================
BASE_DIR = Path(__file__).parent.parent  # ai-factory/
DATA_DIR = BASE_DIR / "data"
REGISTRY_FILE = BASE_DIR / "registry" / "skills-registry.yaml"
WORKSPACE_DIR = BASE_DIR / "workspace"

# Services Docker de la stack
CORE_SERVICES = {
    "openhands": {"port": 3000, "desc": "🧠 Agent Architecte"},
    "ollama": {"port": 11434, "desc": "🧠 Moteur LLM"},
    "qdrant": {"port": 6333, "desc": "💾 Base vectorielle"},
    "open-webui": {"port": 3001, "desc": "💬 Interface chat"},
    "n8n": {"port": 5678, "desc": "⚡ Workflow orchestrator"},
    "browserless": {"port": 3002, "desc": "🌐 Navigateur headless"},
    "caddy": {"port": 80, "desc": "🔒 Reverse proxy"},
}


class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'
    CLEAR = '\033[2J\033[H'


def print_banner():
    print(f"""{Colors.CYAN}
╔═══════════════════════════════════════╗
║        AI FACTORY - MONITOR          ║
║     Tableau de bord de l'usine       ║
╚═══════════════════════════════════════╝{Colors.NC}
""")


# ============================================
# CHECKS
# ============================================
class HealthChecker:
    """Vérifie l'état de tous les composants."""

    @staticmethod
    def check_docker() -> bool:
        """Vérifie si Docker est disponible."""
        try:
            result = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def check_docker_compose() -> bool:
        """Vérifie si docker compose est disponible."""
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def get_compose_services() -> list:
        """Liste les services du docker-compose."""
        try:
            result = subprocess.run(
                ["docker", "compose", "ps", "--format", "json"],
                capture_output=True, text=True, timeout=10,
                cwd=str(BASE_DIR)
            )
            if result.returncode == 0 and result.stdout.strip():
                services = []
                for line in result.stdout.strip().split("\n"):
                    try:
                        services.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
                return services
        except Exception:
            pass
        return []

    @staticmethod
    def check_http(port: int, path: str = "/") -> tuple:
        """Vérifie si un service HTTP répond."""
        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                 f"http://localhost:{port}{path}", "--max-time", "3"],
                capture_output=True, text=True, timeout=5
            )
            code = result.stdout.strip()
            return (code == "200" or code == "302" or code == "401", code)
        except Exception:
            return (False, "N/A")

    @staticmethod
    def check_ollama_models() -> list:
        """Liste les modèles Ollama disponibles."""
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:11434/api/tags"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    @staticmethod
    def get_docker_stats() -> dict:
        """Récupère les stats Docker (CPU, RAM, etc.)."""
        try:
            result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format",
                 "{{.Name}}\t{{.CPUPerc}}\t{{.MemPerc}}\t{{.MemUsage}}"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                stats = {}
                for line in result.stdout.strip().split("\n"):
                    parts = line.split("\t")
                    if len(parts) >= 4:
                        stats[parts[0]] = {
                            "cpu": parts[1],
                            "mem_perc": parts[2],
                            "mem_usage": parts[3]
                        }
                return stats
        except Exception:
            pass
        return {}

    @staticmethod
    def check_qdrant_collections() -> list:
        """Liste les collections Qdrant."""
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:6333/collections"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                return list(data.get("result", {}).get("collections", {}).keys())
        except Exception:
            pass
        return []


# ============================================
# AFFICHAGE
# ============================================
class Dashboard:
    """Affiche le tableau de bord."""

    def __init__(self):
        self.checker = HealthChecker()

    def show_status(self):
        """Affiche l'état de tous les services."""
        print_banner()
        
        # 1. Docker
        print(f"{Colors.BOLD}🔧 INFRASTRUCTURE{Colors.NC}")
        docker_ok = self.checker.check_docker()
        compose_ok = self.checker.check_docker_compose()
        
        print(f"   Docker:        {'✅ ' + Colors.GREEN if docker_ok else '❌ ' + Colors.RED}"
              f"{'Disponible' if docker_ok else 'Indisponible'}{Colors.NC}")
        print(f"   Docker Compose:{'✅ ' + Colors.GREEN if compose_ok else '❌ ' + Colors.RED}"
              f"{'Disponible' if compose_ok else 'Indisponible'}{Colors.NC}")
        
        if not docker_ok:
            print(f"\n{Colors.RED}⚠️  Docker n'est pas disponible. Vérifie qu'il est installé.{Colors.NC}")
            return
        
        # 2. Services
        print(f"\n{Colors.BOLD}📦 SERVICES{Colors.NC}")
        
        services = self.checker.get_compose_services()
        service_names = {s.get("Name", "").replace("ai-factory-", "") for s in services}
        
        for name, info in CORE_SERVICES.items():
            is_running = f"ai-factory-{name}" in service_names or name in service_names
            state = f"{Colors.GREEN}✅ En ligne{Colors.NC}" if is_running else f"{Colors.RED}❌ Arrêté{Colors.NC}"
            print(f"   {info['desc']:25} {state}")

        # 3. Ollama Models
        print(f"\n{Colors.BOLD}🧠 MODÈLES OLLAMA{Colors.NC}")
        models = self.checker.check_ollama_models()
        if models:
            for model in models:
                print(f"   🤖 {model}")
        else:
            print(f"   {Colors.YELLOW}⚠️  Aucun modèle trouvé (ou Ollama pas encore prêt){Colors.NC}")
        
        # 4. Qdrant Collections
        print(f"\n{Colors.BOLD}💾 COLLECTIONS QDRANT{Colors.NC}")
        collections = self.checker.check_qdrant_collections()
        if collections:
            for col in collections:
                print(f"   📚 {col}")
        else:
            print(f"   {Colors.YELLOW}📚 Aucune collection{Colors.NC}")

        # 5. Bots actifs
        print(f"\n{Colors.BOLD}🤖 BOTS ACTIFS{Colors.NC}")
        self.show_bots()
        
        # 6. Skills
        print(f"\n{Colors.BOLD}🧩 SKILLS INSTALLÉES{Colors.NC}")
        self.show_skills()

    def show_bots(self):
        """Affiche les bots générés."""
        bots = []
        
        # Chercher dans workspace/
        if WORKSPACE_DIR.exists():
            for d in sorted(WORKSPACE_DIR.iterdir()):
                if d.is_dir() and (d / "main.py").exists():
                    created = datetime.fromtimestamp(d.stat().st_mtime)
                    age = (datetime.now() - created).days
                    bots.append({
                        "name": d.name,
                        "age": f"{age}j" if age > 0 else "aujourd'hui",
                        "path": str(d)
                    })
        
        # Chercher dans Docker
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=bot-", "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                for name in result.stdout.strip().split("\n"):
                    if name not in [b["name"] for b in bots]:
                        bots.append({"name": name, "age": "en cours", "path": "docker"})
        except Exception:
            pass
        
        if bots:
            for bot in bots:
                print(f"   🤖 {bot['name']:30} ({bot['age']})")
        else:
            print(f"   {Colors.YELLOW}Aucun bot actif pour le moment{Colors.NC}")
            print(f"   → Crée un bot: python3 skills/bot-generator.py --interactive")

    def show_skills(self):
        """Affiche les skills installées depuis le registre."""
        if not REGISTRY_FILE.exists():
            print(f"   {Colors.YELLOW}Aucun registre de skills trouvé{Colors.NC}")
            print(f"   → Ingère des skills: python3 skills/github-ingester.py --featured")
            return
        
        try:
            import yaml
            with open(REGISTRY_FILE) as f:
                registry = yaml.safe_load(f) or {}
            
            skills = registry.get("skills", [])
            if skills:
                for s in skills[:8]:  # Max 8 pour l'affichage
                    status = "🟢" if s.get("enabled", True) else "🔴"
                    stars = s.get("stars", 0)
                    skill_type = s.get("type", "N/A")
                    print(f"   {status} {s['name']:25} ({stars}⭐) {skill_type}")
                
                if len(skills) > 8:
                    print(f"   {Colors.CYAN}... et {len(skills) - 8} autre(s){Colors.NC}")
            else:
                print(f"   {Colors.YELLOW}Aucune skill installée{Colors.NC}")
                
        except Exception as e:
            print(f"   {Colors.RED}Erreur: {e}{Colors.NC}")

    def show_detailed_check(self):
        """Affiche un health check détaillé de chaque service."""
        print_banner()
        print(f"{Colors.BOLD}🔍 HEALTH CHECK DÉTAILLÉ{Colors.NC}\n")
        
        # Tester chaque service
        print(f"{'Service':25} {'Port':8} {'Status':10} {'HTTP':6}  Notes")
        print("-" * 70)
        
        for name, info in CORE_SERVICES.items():
            port = info["port"]
            http_ok, http_code = self.checker.check_http(port)
            status = f"{Colors.GREEN}OK{Colors.NC}" if http_ok else f"{Colors.RED}KO{Colors.NC}"
            
            notes = ""
            if name == "ollama" and http_ok:
                models = self.checker.check_ollama_models()
                notes = f", {len(models)} modèles" if models else ""
            elif name == "qdrant" and http_ok:
                cols = self.checker.check_qdrant_collections()
                notes = f", {len(cols)} collections" if cols else ""
            
            print(f"  {info['desc']:25} :{port:<5} {status:12} {http_code:<6}{notes}")

    def show_logs(self, lines: int = 20):
        """Affiche les dernières erreurs des logs."""
        print_banner()
        print(f"{Colors.BOLD}📋 DERNIERS LOGS (stack complète){Colors.NC}\n")
        
        try:
            result = subprocess.run(
                ["docker", "compose", "logs", "--tail", str(lines)],
                capture_output=True, text=True, timeout=10,
                cwd=str(BASE_DIR)
            )
            if result.stdout:
                # Filtrer les lignes intéressantes (erreurs, warnings)
                important_lines = []
                for line in result.stdout.split("\n"):
                    if any(word in line.lower() for word in ["error", "warning", "exception", "traceback", "failed"]):
                        important_lines.append(line)
                
                if important_lines:
                    print(f"{Colors.YELLOW}⚠️  Lignes importantes détectées:{Colors.NC}\n")
                    for line in important_lines[-lines:]:
                        print(f"   {line}")
                else:
                    print(f"{Colors.GREEN}Aucune erreur détectée dans les logs récents ✅{Colors.NC}")
            else:
                print(f"{Colors.YELLOW}Aucun log disponible{Colors.NC}")
                
        except Exception as e:
            print(f"{Colors.RED}Erreur: {e}{Colors.NC}")
        
        print(f"\n{Colors.CYAN}Pour voir tous les logs: docker compose logs -f{Colors.NC}")

    def show_resources(self):
        """Affiche l'utilisation des ressources."""
        print_banner()
        print(f"{Colors.BOLD}📊 UTILISATION DES RESSOURCES{Colors.NC}\n")
        
        # Stats Docker
        stats = self.checker.get_docker_stats()
        if stats:
            print(f"{'Conteneur':40} {'CPU':10} {'RAM %':10} {'RAM Usage':15}")
            print("-" * 75)
            for name, s in sorted(stats.items()):
                name_short = name.replace("ai-factory-", "")
                print(f"  {name_short:38} {s['cpu']:10} {s['mem_perc']:10} {s['mem_usage']:15}")
        else:
            print(f"{Colors.YELLOW}Aucune stats disponible{Colors.NC}")
        
        # Espace disque
        print(f"\n{Colors.BOLD}💾 ESPACE DISQUE{Colors.NC}")
        try:
            result = subprocess.run(
                ["du", "-sh", str(DATA_DIR)],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                print(f"   Données: {result.stdout.strip().split()[0]}")
            
            result = subprocess.run(
                ["df", "-h", str(BASE_DIR)],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if len(lines) >= 2:
                    parts = lines[1].split()
                    if len(parts) >= 5:
                        print(f"   Disque: {parts[3]} libre / {parts[1]} total")
        except Exception:
            pass


# ============================================
# MODE EN TEMPS RÉEL
# ============================================
def watch_mode():
    """Mode surveillance en temps réel."""
    dashboard = Dashboard()
    
    try:
        while True:
            os.system("clear" if os.name == "posix" else "cls")
            dashboard.show_status()
            print(f"\n{Colors.CYAN}🔄 Mise à jour toutes les 5s. Ctrl+C pour quitter.{Colors.NC}")
            time.sleep(5)
    except KeyboardInterrupt:
        print(f"\n{Colors.GREEN}👋 À bientôt !{Colors.NC}")


# ============================================
# CLI
# ============================================
def main():
    parser = argparse.ArgumentParser(
        description="AI FACTORY - System Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--status", "-s", action="store_true",
                       help="Afficher l'état des services")
    parser.add_argument("--check", "-c", action="store_true",
                       help="Health check détaillé")
    parser.add_argument("--logs", "-l", action="store_true",
                       help="Afficher les dernières erreurs")
    parser.add_argument("--resources", "-r", action="store_true",
                       help="Afficher l'utilisation des ressources")
    parser.add_argument("--watch", "-w", action="store_true",
                       help="Mode surveillance en temps réel")
    parser.add_argument("--bots", "-b", action="store_true",
                       help="Afficher les bots actifs")
    
    args = parser.parse_args()
    
    dashboard = Dashboard()
    
    if args.check:
        dashboard.show_detailed_check()
    elif args.logs:
        dashboard.show_logs()
    elif args.resources:
        dashboard.show_resources()
    elif args.watch:
        watch_mode()
    elif args.bots:
        dashboard.show_bots()
    else:
        # Mode par défaut : status
        dashboard.show_status()


if __name__ == "__main__":
    main()
