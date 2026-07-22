#!/usr/bin/env python3
"""
============================================
AI FACTORY - Self-Healing Module
============================================
Module d'auto-guérison pour les bots.
Détecte les blocages (403, 429, captcha),
analyse la cause, ajuste les paramètres,
et redémarre automatiquement.

Usage:
    python3 self-healing.py monitor bot-mon-instagram
    python3 self-healing.py heal bot-mon-linkedin
    python3 self-healing.py status
    python3 self-healing.py analyze --logs ./workspace/bot/logs/

Prérequis: Docker, les bots doivent être nommés bot-xxxx
============================================
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ============================================
# CONFIGURATION
# ============================================
BASE_DIR = Path(__file__).parent.parent
WORKSPACE_DIR = BASE_DIR / "workspace"
LOGS_DIR = BASE_DIR / "data" / "logs"
OLLAMA_API = os.getenv("OLLAMA_API_URL", "http://localhost:11434")

# Stratégies de contournement
HEALING_STRATEGIES = [
    {
        "name": "Changer User-Agent",
        "action": "rotate_user_agent",
        "params": {"user_agent": "rotate"}
    },
    {
        "name": "Modifier Viewport",
        "action": "change_viewport",
        "params": {"width": 1440, "height": 900}
    },
    {
        "name": "Changer Locale",
        "action": "change_locale",
        "params": {"locale": "en-US"}
    },
    {
        "name": "Rotation Proxy",
        "action": "rotate_proxy",
        "params": {"proxy": "next_in_chain"}
    },
    {
        "name": "Augmenter délais",
        "action": "increase_delays",
        "params": {"min_delay": 5, "max_delay": 15}
    },
    {
        "name": "Réduire actions/heure",
        "action": "reduce_rate",
        "params": {"max_per_hour": 5}
    },
    {
        "name": "Pause étendue",
        "action": "extended_cooldown",
        "params": {"cooldown_minutes": 60}
    },
    {
        "name": "Nouvelle session",
        "action": "fresh_session",
        "params": {"clear_cookies": True}
    },
]


class Colors:
    GREEN = '\033[0;32m'; YELLOW = '\033[1;33m'
    RED = '\033[0;31m'; BLUE = '\033[0;34m'; CYAN = '\033[0;36m'
    BOLD = '\033[1m'; NC = '\033[0m'


def log(msg, color=Colors.GREEN):
    print(f"{color}[{datetime.now().strftime('%H:%M:%S')}]{Colors.NC} {msg}")


# ============================================
# DÉTECTEUR DE BLOCAGE
# ============================================
class BlockDetector:
    """Analyse les logs pour détecter les blocages."""

    BLOCK_PATTERNS = [
        (r"(403|Forbidden)", "HTTP 403 - Accès refusé"),
        (r"(429|Too Many Requests)", "Rate limit - Trop de requêtes"),
        (r"(captcha|recaptcha|challenge)", "Captcha détecté"),
        (r"(blocked|block|banned|suspend)", "Compte bloqué/banni"),
        (r"(timeout|timed out|ETIMEDOUT)", "Timeout de connexion"),
        (r"(Cloudflare|cf-|cloudflare)", "Protection Cloudflare"),
        (r"(login|sign in|authenticate)", "Redirigé vers page de login"),
        (r"(error|exception|traceback)", "Erreur Python non gérée"),
        (r"(502|503|504)", "Erreur serveur (502/503/504)"),
        (r"(rate limit|too fast)", "Rate limit détecté"),
        (r"(your account has been|temporary restricted)", "Restriction de compte"),
        (r"(IP.*block|blocked.*IP)", "IP bloquée"),
    ]

    @staticmethod
    def scan_logs(bot_name: str, lines: int = 200) -> list:
        """Scanne les logs Docker d'un bot."""
        issues = []
        
        try:
            result = subprocess.run(
                ["docker", "logs", f"bot-{bot_name}", "--tail", str(lines)],
                capture_output=True, text=True, timeout=10
            )
            log_content = result.stdout + result.stderr
        except Exception:
            log_content = ""
        
        # Scanner les logs du workspace
        for d in WORKSPACE_DIR.iterdir():
            if d.is_dir() and bot_name in d.name:
                for log_file in d.rglob("*.log"):
                    if log_file.exists():
                        log_content += log_file.read_text(errors="ignore")
        
        # Analyser les patterns
        for pattern, description in BlockDetector.BLOCK_PATTERNS:
            matches = re.findall(pattern, log_content, re.IGNORECASE)
            if matches:
                issues.append({
                    "type": description,
                    "pattern": pattern,
                    "count": len(matches),
                    "severity": "high" if any(w in description.lower() 
                        for w in ["bloqué", "banni", "captcha", "403", "429"]) else "medium"
                })
        
        return issues

    @staticmethod
    def check_health(bot_name: str) -> dict:
        """Vérifie l'état de santé d'un bot."""
        status = {
            "name": bot_name,
            "running": False,
            "issues": [],
            "last_restart": None,
            "uptime": None,
            "healthy": True
        }
        
        # Vérifier si le conteneur tourne
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name=bot-{bot_name}",
                 "--format", "{{.Status}}\t{{.CreatedAt}}"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                parts = result.stdout.strip().split("\t")
                status["running"] = "Up" in parts[0]
                status["uptime"] = parts[0][:50] if parts else None
        except Exception:
            pass
        
        # Scanner les issues
        status["issues"] = BlockDetector.scan_logs(bot_name)
        status["healthy"] = len([i for i in status["issues"] if i["severity"] == "high"]) == 0
        
        return status


# ============================================
# ANALYSEUR DE CAUSE
# ============================================
class CauseAnalyzer:
    """Analyse la cause d'un blocage avec l'IA."""

    @staticmethod
    def analyze(issues: list, logs_sample: str) -> dict:
        """Analyse la cause probable du blocage."""
        
        # Déductions basées sur les patterns
        causes = []
        recommendations = []
        
        issue_types = [i["type"] for i in issues]
        
        if any("403" in t for t in issue_types):
            causes.append("IP bloquée ou User-Agent détecté")
            recommendations.append("→ Changer de proxy et modifier le User-Agent")
            recommendations.append("→ Augmenter les délais entre les actions")
        
        if any("429" in t for t in issue_types):
            causes.append("Trop de requêtes en peu de temps")
            recommendations.append("→ Réduire les actions par heure de 50%")
            recommendations.append("→ Ajouter une rotation de proxies")
        
        if any("Captcha" in t for t in issue_types):
            causes.append("Comportement robotique détecté")
            recommendations.append("→ Ralentir les interactions")
            recommendations.append("→ Ajouter des mouvements de souris aléatoires")
            recommendations.append("→ Utiliser un proxy résidentiel")
        
        if any("Timeout" in t for t in issue_types):
            causes.append("Connexion instable ou proxy lent")
            recommendations.append("→ Changer de proxy")
            recommendations.append("→ Augmenter les timeouts")
        
        if any("Cloudflare" in t for t in issue_types):
            causes.append("Protection anti-bot Cloudflare activée")
            recommendations.append("→ Utiliser un navigateur avec vraie empreinte")
            recommendations.append("→ Proxy résidentiel recommandé")
        
        if not causes:
            causes.append("Cause inconnue — rotation complète recommandée")
            recommendations = HEALING_STRATEGIES[:4]
        
        return {
            "causes": causes,
            "recommendations": recommendations,
            "severity": "high" if len([i for i in issues if i["severity"] == "high"]) > 0 else "medium",
            "strategy_index": 0  # Prochaine stratégie à essayer
        }


# ============================================
# GUÉRISSEUR
# ============================================
class Healer:
    """Applique les stratégies de guérison."""

    def __init__(self):
        self.healing_history = defaultdict(list)
        self.state_file = BASE_DIR / "data" / "healing-state.json"
        self._load_state()

    def _load_state(self):
        if self.state_file.exists():
            try:
                self.healing_history = defaultdict(
                    list, json.loads(self.state_file.read_text())
                )
            except Exception:
                pass

    def _save_state(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(
            {k: v for k, v in self.healing_history.items()}, indent=2
        ))

    def get_strategy(self, bot_name: str) -> Optional[dict]:
        """Récupère la prochaine stratégie à essayer."""
        history = self.healing_history.get(bot_name, [])
        last_index = history[-1]["strategy_index"] if history else -1
        next_index = (last_index + 1) % len(HEALING_STRATEGIES)
        
        if next_index < len(HEALING_STRATEGIES):
            return {**HEALING_STRATEGIES[next_index], "index": next_index}
        return None

    def apply_strategy(self, bot_name: str, strategy: dict) -> bool:
        """Applique une stratégie de guérison."""
        log(f"🔧 Application de: {strategy['name']}", Colors.YELLOW)
        
        action = strategy["action"]
        params = strategy["params"]
        success = False
        
        try:
            if action == "increase_delays":
                # Augmenter les délais via variables d'env
                subprocess.run([
                    "docker", "update", f"bot-{bot_name}",
                    "--env", f"BOT_MIN_DELAY={params['min_delay']}",
                    "--env", f"BOT_MAX_DELAY={params['max_delay']}"
                ], capture_output=True, timeout=10)
                success = True
            
            elif action == "reduce_rate":
                subprocess.run([
                    "docker", "update", f"bot-{bot_name}",
                    "--env", f"BOT_MAX_ACTIONS_HOUR={params['max_per_hour']}"
                ], capture_output=True, timeout=10)
                success = True
            
            elif action == "extended_cooldown":
                log(f"⏸️ Pause de {params['cooldown_minutes']} minutes...", Colors.YELLOW)
                subprocess.run(["docker", "stop", f"bot-{bot_name}"], capture_output=True, timeout=10)
                time.sleep(params["cooldown_minutes"] * 60)
                subprocess.run(["docker", "start", f"bot-{bot_name}"], capture_output=True, timeout=10)
                success = True
            
            elif action == "fresh_session":
                subprocess.run(["docker", "restart", f"bot-{bot_name}"], capture_output=True, timeout=10)
                success = True
            
            elif action == "rotate_proxy":
                log(f"🔄 Rotation de proxy...", Colors.BLUE)
                subprocess.run(["docker", "restart", f"bot-{bot_name}"], capture_output=True, timeout=10)
                success = True
            
            else:
                # Par défaut: redémarrer
                subprocess.run(["docker", "restart", f"bot-{bot_name}"], capture_output=True, timeout=10)
                success = True
            
            # Enregistrer
            self.healing_history[bot_name].append({
                "timestamp": datetime.now().isoformat(),
                "strategy": strategy["name"],
                "strategy_index": strategy.get("index", 0),
                "success": success
            })
            self._save_state()
            
            return success
            
        except Exception as e:
            log(f"❌ Erreur lors de l'application: {e}", Colors.RED)
            return False

    def heal(self, bot_name: str) -> bool:
        """Tente de guérir un bot."""
        log(f"\n{'='*50}")
        log(f"🩺 AUTO-GUÉRISON: {bot_name}")
        log(f"{'='*50}")
        
        # 1. Diagnostiquer
        detector = BlockDetector()
        status = detector.check_health(bot_name)
        
        if not status["running"]:
            log(f"❌ Le bot {bot_name} n'est pas en cours d'exécution", Colors.RED)
            # Essayer de le démarrer
            try:
                subprocess.run(["docker", "start", f"bot-{bot_name}"], capture_output=True, timeout=10)
                log(f"✅ Bot {bot_name} démarré", Colors.GREEN)
                return True
            except Exception as e:
                log(f"❌ Impossible de démarrer: {e}", Colors.RED)
                return False
        
        if status["healthy"] and status["running"]:
            log(f"✅ {bot_name} semble en bonne santé", Colors.GREEN)
            return True
        
        # 2. Analyser les issues
        if status["issues"]:
            log(f"⚠️ Problèmes détectés ({len(status['issues'])}):", Colors.YELLOW)
            for issue in status["issues"]:
                sev = "🔴" if issue["severity"] == "high" else "🟡"
                log(f"   {sev} {issue['type']} (x{issue['count']})", Colors.YELLOW)
        
        # 3. Obtenir la stratégie
        strategy = self.get_strategy(bot_name)
        if not strategy:
            log(f"❌ Plus de stratégies disponibles pour {bot_name}", Colors.RED)
            return False
        
        log(f"\n🎯 Stratégie #{strategy['index'] + 1}: {strategy['name']}")
        
        # 4. Appliquer
        success = self.apply_strategy(bot_name, strategy)
        
        # 5. Attendre et vérifier
        if success:
            time.sleep(5)
            new_status = detector.check_health(bot_name)
            if new_status["healthy"]:
                log(f"\n✅ Guérison réussie pour {bot_name} !", Colors.GREEN)
            else:
                log(f"\n⚠️ Guérison partielle, tentative suivante...", Colors.YELLOW)
        
        return success

    def monitor(self, bot_name: str, interval: int = 30):
        """Surveille un bot et le guérit automatiquement."""
        log(f"👁️ Surveillance de {bot_name} (intervalle: {interval}s)")
        
        try:
            while True:
                detector = BlockDetector()
                status = detector.check_health(bot_name)
                
                if not status["healthy"]:
                    log(f"🚨 Problème détecté sur {bot_name} !", Colors.RED)
                    self.heal(bot_name)
                else:
                    log(f"✅ {bot_name} — OK", Colors.GREEN)
                
                time.sleep(interval)
        except KeyboardInterrupt:
            log(f"👋 Surveillance arrêtée")

    def show_status(self):
        """Affiche l'état de tous les bots."""
        print(f"\n{Colors.BOLD}🩺 Rapport d'auto-guérison{Colors.NC}")
        print(f"{'='*60}")
        
        # Lister les bots Docker
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", "name=bot-",
                 "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True, text=True, timeout=5
            )
            
            if result.stdout.strip():
                print(f"\n{Colors.BOLD}Bots Docker:{Colors.NC}")
                for line in result.stdout.strip().split("\n"):
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        name = parts[0].replace("bot-", "")
                        running = "🟢" if "Up" in parts[1] else "🔴"
                        print(f"   {running} {name:30} {parts[1][:40]}")
                        
                        # Vérifications
                        issues = BlockDetector.scan_logs(name)
                        if issues:
                            for i in issues[:2]:
                                print(f"      ⚠️  {i['type']}")
            else:
                print(f"\n   {Colors.YELLOW}Aucun bot Docker actif{Colors.NC}")
                
        except Exception as e:
            log(f"❌ Erreur: {e}", Colors.RED)
        
        # Historique des guérisons
        if self.healing_history:
            print(f"\n{Colors.BOLD}Historique des guérisons:{Colors.NC}")
            for bot_name, entries in self.healing_history.items():
                success_rate = sum(1 for e in entries if e["success"]) / len(entries) * 100
                print(f"   🤖 {bot_name}: {len(entries)} tentatives, {success_rate:.0f}% succès")
                
                # Dernière tentative
                last = entries[-1]
                print(f"      Dernière: {last['strategy']} → {'✅' if last['success'] else '❌'}")


# ============================================
# CLI
# ============================================
def main():
    parser = argparse.ArgumentParser(
        description="🩺 AI FACTORY - Self-Healing Module",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command")
    
    p_heal = subparsers.add_parser("heal", help="Guérir un bot")
    p_heal.add_argument("bot_name", help="Nom du bot (sans le prefixe bot-)")
    
    p_monitor = subparsers.add_parser("monitor", help="Surveiller un bot")
    p_monitor.add_argument("bot_name", help="Nom du bot")
    p_monitor.add_argument("--interval", "-i", type=int, default=30,
                          help="Intervalle en secondes")
    
    p_status = subparsers.add_parser("status", aliases=["st"],
                                     help="État de tous les bots")
    
    p_analyze = subparsers.add_parser("analyze", help="Analyser les logs")
    p_analyze.add_argument("--logs", "-l", help="Chemin vers les logs")
    p_analyze.add_argument("--bot", "-b", help="Nom du bot")
    
    args = parser.parse_args()
    
    healer = Healer()
    
    if args.command == "heal":
        healer.heal(args.bot_name)
    
    elif args.command == "monitor":
        healer.monitor(args.bot_name, args.interval)
    
    elif args.command in ("status", "st"):
        healer.show_status()
    
    elif args.command == "analyze":
        if args.bot:
            detector = BlockDetector()
            status = detector.check_health(args.bot)
            print(json.dumps(status, indent=2))
        elif args.logs:
            log_path = Path(args.logs)
            if log_path.exists():
                content = log_path.read_text(errors="ignore")
                issues = BlockDetector.scan_logs("")
                print(f"\nAnalyse de {log_path}:")
                for i in issues:
                    print(f"  {'🔴' if i['severity'] == 'high' else '🟡'} {i['type']}")
            else:
                print(f"❌ Fichier introuvable: {args.logs}")
        else:
            print("Utilise --bot ou --logs")
    
    else:
        parser.print_help()
        print(f"""
{Colors.BOLD}Exemples:{Colors.NC}
  python3 self-healing.py status                # État de tous les bots
  python3 self-healing.py heal mon-bot-linkedin  # Guérir un bot
  python3 self-healing.py monitor mon-bot-insta  # Surveillance automatique
  python3 self-healing.py analyze --bot mon-bot  # Analyser les logs
        """)


if __name__ == "__main__":
    main()
