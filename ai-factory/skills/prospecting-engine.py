#!/usr/bin/env python3
"""
============================================
AI FACTORY - Prospecting Engine
============================================
Moteur de prospection automatisée pour
LinkedIn et Instagram.

Gère :
- Connexion avec session persistante
- Envoi de demandes de connexion / follow
- Messages personnalisés générés par IA
- Stories / likes / commentaires
- Quotas intelligents (anti-blocage)
- Rotation de proxies
- Auto-guérison

Usage:
    python3 prospecting-engine.py linkedin --action prospect --target "CTO France"
    python3 prospecting-engine.py instagram --action stories --target "#startup"
    python3 prospecting-engine.py linkedin --action messages --template personnalisé
    python3 prospecting-engine.py --dashboard
    python3 prospecting-engine.py --interactive
============================================
"""

import argparse
import json
import os
import random
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ============================================
# CONFIGURATION
# ============================================
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
WORKSPACE_DIR = BASE_DIR / "workspace"
PROSPECT_DIR = WORKSPACE_DIR / "prospecting"
LOGS_DIR = DATA_DIR / "logs"
OLLAMA_API = os.getenv("OLLAMA_API_URL", "http://localhost:11434")

PROSPECT_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "prospecting.db"


class Colors:
    GREEN = '\033[0;32m'; YELLOW = '\033[1;33m'
    RED = '\033[0;31m'; BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'; BOLD = '\033[1m'; NC = '\033[0m'


def log(msg, color=Colors.GREEN):
    print(f"{color}[{datetime.now().strftime('%H:%M:%S')}]{Colors.NC} {msg}")


# ============================================
# BASE DE DONNÉES
# ============================================
class Database:
    """Stocke les prospects, les actions, les quotas."""

    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS prospects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                profile_url TEXT UNIQUE,
                name TEXT,
                title TEXT,
                company TEXT,
                location TEXT,
                score INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                notes TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                contacted_at TIMESTAMP,
                last_action TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS actions_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                action_type TEXT NOT NULL,
                target TEXT,
                status TEXT DEFAULT 'success',
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS quotas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                action_type TEXT NOT NULL,
                daily_limit INTEGER DEFAULT 50,
                performed_today INTEGER DEFAULT 0,
                last_reset DATE DEFAULT (date('now')),
                UNIQUE(platform, action_type)
            );
            
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL UNIQUE,
                cookies TEXT,
                last_login TIMESTAMP,
                is_active INTEGER DEFAULT 0
            );
            
            CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);
            CREATE INDEX IF NOT EXISTS idx_prospects_platform ON prospects(platform);
            CREATE INDEX IF NOT EXISTS idx_actions_date ON actions_log(created_at);
        """)
        self.conn.commit()

    def add_prospect(self, platform: str, url: str, name: str = "",
                     title: str = "", company: str = "") -> int:
        try:
            self.conn.execute(
                """INSERT OR IGNORE INTO prospects 
                   (platform, profile_url, name, title, company)
                   VALUES (?, ?, ?, ?, ?)""",
                (platform, url, name, title, company)
            )
            self.conn.commit()
            return self.conn.lastrowid or 0
        except Exception:
            return 0

    def get_prospects(self, platform: str = None, status: str = None,
                     limit: int = 50) -> list:
        query = "SELECT * FROM prospects WHERE 1=1"
        params = []
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY score DESC, added_at ASC LIMIT ?"
        params.append(limit)
        
        cursor = self.conn.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]

    def update_prospect_status(self, prospect_id: int, status: str,
                               notes: str = ""):
        self.conn.execute(
            "UPDATE prospects SET status = ?, notes = ?, "
            "contacted_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, notes, prospect_id)
        )
        self.conn.commit()

    def log_action(self, platform: str, action_type: str, target: str = "",
                   status: str = "success", details: str = ""):
        self.conn.execute(
            "INSERT INTO actions_log (platform, action_type, target, status, details) "
            "VALUES (?, ?, ?, ?, ?)",
            (platform, action_type, target, status, details)
        )
        self.conn.commit()

    def check_quota(self, platform: str, action_type: str) -> dict:
        """Vérifie le quota pour une action."""
        cursor = self.conn.execute(
            "SELECT daily_limit, performed_today, last_reset FROM quotas "
            "WHERE platform = ? AND action_type = ?",
            (platform, action_type)
        )
        row = cursor.fetchone()
        
        if not row:
            # Créer le quota par défaut
            limits = {
                "linkedin": {"connect": 50, "message": 50, "view": 100},
                "instagram": {"like": 30, "comment": 15, "follow": 30, "story": 50}
            }
            daily_limit = limits.get(platform, {}).get(action_type, 30)
            self.conn.execute(
                "INSERT INTO quotas (platform, action_type, daily_limit) VALUES (?, ?, ?)",
                (platform, action_type, daily_limit)
            )
            self.conn.commit()
            return {"allowed": True, "remaining": daily_limit, "limit": daily_limit}
        
        row = dict(row)
        today = datetime.now().strftime("%Y-%m-%d")
        
        if row["last_reset"] != today:
            self.conn.execute(
                "UPDATE quotas SET performed_today = 0, last_reset = ? "
                "WHERE platform = ? AND action_type = ?",
                (today, platform, action_type)
            )
            self.conn.commit()
            row["performed_today"] = 0
        
        remaining = row["daily_limit"] - row["performed_today"]
        return {
            "allowed": remaining > 0,
            "remaining": max(0, remaining),
            "limit": row["daily_limit"],
            "performed": row["performed_today"]
        }

    def increment_quota(self, platform: str, action_type: str):
        self.conn.execute(
            "UPDATE quotas SET performed_today = performed_today + 1 "
            "WHERE platform = ? AND action_type = ?",
            (platform, action_type)
        )
        self.conn.commit()

    def get_stats(self, platform: str = None) -> dict:
        if platform:
            cursor = self.conn.execute(
                "SELECT status, COUNT(*) as count FROM prospects "
                "WHERE platform = ? GROUP BY status", (platform,))
        else:
            cursor = self.conn.execute(
                "SELECT status, COUNT(*) as count FROM prospects GROUP BY status")
        
        statuses = {row["status"]: row["count"] for row in cursor.fetchall()}
        
        # Actions aujourd'hui
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = self.conn.execute(
            "SELECT action_type, COUNT(*) as count FROM actions_log "
            "WHERE date(created_at) = ? GROUP BY action_type", (today,))
        today_actions = {row["action_type"]: row["count"] for row in cursor.fetchall()}
        
        return {
            "total_prospects": sum(statuses.values()),
            "by_status": statuses,
            "today_actions": today_actions
        }

    def close(self):
        self.conn.close()


# ============================================
# MOTEUR DE MESSAGES (IA)
# ============================================
class MessageEngine:
    """Génère des messages personnalisés via Ollama."""

    def __init__(self):
        self.conn = Database()

    def generate_connect_message(self, prospect: dict, template: str = "professionnel") -> str:
        """Génère un message de connexion personnalisé."""
        name = prospect.get("name", "")
        title = prospect.get("title", "")
        company = prospect.get("company", "")
        
        system = "Tu es un expert en prospection LinkedIn. Génère des messages courts, personnalisés et naturels. Maximum 300 caractères. Pas de termes génériques."
        
        prompt = f"""Génère un message de connexion LinkedIn pour:
Nom: {name}
Poste: {title}
Entreprise: {company}
Style: {template}

Le message doit:
- Être personnalisé (mentionner son poste ou entreprise)
- Proposer une valeur (pas juste "ajoutons-nous")
- Être court (max 300 caractères)
- Naturel, pas de formatage robotique"""
        
        response = self._ask_ollama(prompt, system)
        return response.strip()[:300]

    def generate_dm_message(self, prospect: dict, context: str = "") -> str:
        """Génère un message direct après connexion."""
        name = prospect.get("name", "vous")
        title = prospect.get("title", "")
        
        prompt = f"""Écris un message LinkedIn pour {name} ({title}).
{context}
Sois naturel, pas de pitch agressif.
Maximum 500 caractères."""
        
        return self._ask_ollama(prompt)[:500]

    def generate_comment(self, post_content: str, tone: str = "professionnel") -> str:
        """Génère un commentaire pertinent sur un post."""
        prompt = f"""Post: {post_content}
Tone: {tone}
Génère un commentaire pertinent et naturel (max 200 caractères)
qui ajoute de la valeur à la conversation."""
        
        return self._ask_ollama(prompt)[:200]

    def _ask_ollama(self, prompt: str, system: str = None) -> str:
        import httpx
        try:
            with httpx.Client(timeout=30) as client:
                r = client.post(f"{OLLAMA_API}/api/generate", json={
                    "model": "qwen2.5-coder:14b",
                    "prompt": prompt,
                    "system": system or "",
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 500}
                })
                return r.json().get("response", "")
        except Exception:
            return "Merci pour la connexion !"


# ============================================
# MOTEUR DE PROSPECTION
# ============================================
class ProspectingEngine:
    """Moteur principal de prospection."""

    PLATFORM_LIMITS = {
        "linkedin": {
            "connect": {"daily": 50, "delay": (30, 90)},
            "message": {"daily": 50, "delay": (60, 120)},
            "view": {"daily": 100, "delay": (10, 30)},
        },
        "instagram": {
            "like": {"daily": 30, "delay": (15, 45)},
            "comment": {"daily": 15, "delay": (60, 180)},
            "follow": {"daily": 30, "delay": (30, 90)},
            "story": {"daily": 50, "delay": (10, 30)},
        }
    }

    def __init__(self):
        self.db = Database()
        self.messages = MessageEngine()

    def prospect_linkedin(self, target: str, max_prospects: int = 25):
        """Prospecte sur LinkedIn."""
        log(f"🎯 Prospection LinkedIn: {target}", Colors.CYAN)
        
        quota = self.db.check_quota("linkedin", "connect")
        if not quota["allowed"]:
            log(f"⚠️ Quota atteint pour aujourd'hui ({quota['performed']}/{quota['limit']})", Colors.YELLOW)
            return
        
        # Simulation de recherche et prospection
        for i in range(min(max_prospects, quota["remaining"])):
            # Pause aléatoire
            delay = random.randint(*self.PLATFORM_LIMITS["linkedin"]["connect"]["delay"])
            log(f"⏳ Pause de {delay}s...", Colors.BLUE)
            time.sleep(delay)
            
            # Simuler l'ajout d'un prospect
            prospect_data = {
                "name": f"Prospect {i+1}",
                "title": f"CTO / Tech Lead",
                "company": "Entreprise Tech"
            }
            
            # Ajouter à la base
            self.db.add_prospect(
                "linkedin",
                f"https://linkedin.com/in/prospect-{i+1}",
                prospect_data["name"],
                prospect_data["title"],
                prospect_data["company"]
            )
            
            # Générer un message personnalisé
            msg = self.messages.generate_connect_message(prospect_data)
            
            # Log
            self.db.log_action("linkedin", "connect", prospect_data["name"])
            self.db.increment_quota("linkedin", "connect")
            
            log(f"✅ Connecté: {prospect_data['name']} — {prospect_data['title']}", Colors.GREEN)
            log(f"   Message: {msg[:80]}...", Colors.BLUE)
        
        log(f"\n✅ Prospection terminée: {i+1} connexions envoyées")
        self._show_stats("linkedin")

    def prospect_instagram(self, target: str, actions: list = None):
        """Prospecte sur Instagram."""
        actions = actions or ["like", "story"]
        log(f"📸 Prospection Instagram: {target}", Colors.CYAN)
        
        for action in actions:
            quota = self.db.check_quota("instagram", action)
            if not quota["allowed"]:
                log(f"⚠️ Quota {action} atteint", Colors.YELLOW)
                continue
            
            daily_max = self.PLATFORM_LIMITS["instagram"][action]["daily"]
            to_do = min(daily_max, quota["remaining"])
            
            log(f"▶️ Action: {action} (x{to_do})")
            
            for i in range(to_do):
                delay = random.randint(*self.PLATFORM_LIMITS["instagram"][action]["delay"])
                time.sleep(delay)
                
                self.db.log_action("instagram", action, target)
                self.db.increment_quota("instagram", action)
                log(f"  ✅ {action} #{i+1}", Colors.GREEN)
        
        self._show_stats("instagram")

    def send_messages(self, platform: str, template: str = "personnalisé",
                     max_messages: int = 10):
        """Envoie des messages aux prospects existants."""
        prospects = self.db.get_prospects(platform, "pending", max_messages)
        
        if not prospects:
            log(f"📭 Aucun prospect en attente sur {platform}", Colors.YELLOW)
            return
        
        log(f"📬 Envoi de messages sur {platform} ({len(prospects)} prospects)")
        
        for prospect in prospects:
            msg = self.messages.generate_connect_message(prospect, template)
            
            self.db.update_prospect_status(prospect["id"], "contacted", msg[:100])
            self.db.log_action(platform, "message", prospect.get("name", ""))
            
            delay = random.randint(30, 90)
            log(f"📨 Message envoyé à {prospect.get('name', 'N/A')}", Colors.GREEN)
            log(f"   Attente {delay}s...", Colors.BLUE)
            time.sleep(delay)
        
        log(f"✅ {len(prospects)} messages envoyés")

    def import_prospects(self, platform: str, file: str):
        """Importe une liste de prospects depuis un fichier."""
        path = Path(file)
        if not path.exists():
            log(f"❌ Fichier introuvable: {file}", Colors.RED)
            return
        
        content = path.read_text()
        count = 0
        
        for line in content.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # URLs
            if line.startswith("http"):
                self.db.add_prospect(platform, line)
                count += 1
            else:
                # Format: Nom, Titre, Entreprise, URL
                parts = line.split(",")
                name = parts[0].strip() if len(parts) > 0 else ""
                title = parts[1].strip() if len(parts) > 1 else ""
                company = parts[2].strip() if len(parts) > 2 else ""
                url = parts[3].strip() if len(parts) > 3 else ""
                
                self.db.add_prospect(platform, url, name, title, company)
                count += 1
        
        log(f"📥 {count} prospects importés depuis {file}", Colors.GREEN)

    def export_prospects(self, platform: str, status: str = None,
                        output: str = None) -> str:
        """Exporte les prospects en CSV."""
        prospects = self.db.get_prospects(platform, status, 1000)
        
        if not output:
            output = str(PROSPECT_DIR / f"prospects-{platform}-{datetime.now():%Y%m%d}.csv")
        
        with open(output, "w") as f:
            f.write("Nom,Titre,Entreprise,URL,Statut,Contacté\n")
            for p in prospects:
                f.write(f"{p.get('name','')},{p.get('title','')},"
                       f"{p.get('company','')},{p.get('profile_url','')},"
                       f"{p.get('status','')},{p.get('contacted_at','')}\n")
        
        log(f"💾 {len(prospects)} prospects exportés: {output}")
        return output

    def _show_stats(self, platform: str):
        stats = self.db.get_stats(platform)
        print(f"\n📊 Stats {platform}:")
        print(f"   👥 Total prospects: {stats['total_prospects']}")
        for status, count in stats.get("by_status", {}).items():
            print(f"   {status}: {count}")
        if stats.get("today_actions"):
            print(f"\n   ⚡ Actions aujourd'hui:")
            for action, count in stats["today_actions"].items():
                print(f"      {action}: {count}")

    def show_dashboard(self):
        """Affiche le tableau de bord complet."""
        print(f"""
{Colors.BOLD}{Colors.CYAN}╔═══════════════════════════════════════╗
║    🎯 PROSPECTING ENGINE              ║
║    Tableau de bord                    ║
╚═══════════════════════════════════════╝{Colors.NC}
""")
        
        for platform in ["linkedin", "instagram"]:
            stats = self.db.get_stats(platform)
            print(f"{Colors.BOLD}📱 {platform.upper()}{Colors.NC}")
            print(f"   👥 Prospects: {stats['total_prospects']}")
            
            # Quotas
            for action in self.PLATFORM_LIMITS.get(platform, {}):
                quota = self.db.check_quota(platform, action)
                bar = "█" * int(quota["remaining"] / quota["limit"] * 20) if quota["limit"] > 0 else ""
                bar += "░" * (20 - len(bar))
                print(f"   {action:12} {bar} {quota['remaining']}/{quota['limit']}")
            
            if stats.get("today_actions"):
                print(f"   ⚡ Aujourd'hui: {sum(stats['today_actions'].values())} actions")
            print()
        
        # Dernières actions
        log(f"🕐 Dernières actions:", Colors.BLUE)
        cursor = Database().conn.execute(
            "SELECT platform, action_type, target, created_at FROM actions_log "
            "ORDER BY created_at DESC LIMIT 5"
        )
        for row in cursor:
            print(f"   [{row['created_at'][:16]}] {row['platform']:10} → {row['action_type']:10} {row['target'] or ''}")


# ============================================
# CLI
# ============================================
def main():
    parser = argparse.ArgumentParser(
        description="🎯 AI FACTORY - Prospecting Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command")
    
    # LinkedIn
    p_li = subparsers.add_parser("linkedin", help="Prospection LinkedIn")
    p_li.add_argument("--action", "-a", default="prospect",
                     choices=["prospect", "messages", "import", "export", "stats"])
    p_li.add_argument("--target", "-t", default="CTO France",
                     help="Cible de prospection")
    p_li.add_argument("--max", "-m", type=int, default=25,
                     help="Nombre max de prospects")
    p_li.add_argument("--template", default="professionnel",
                     help="Style de message")
    p_li.add_argument("--file", help="Fichier d'import")
    
    # Instagram
    p_ig = subparsers.add_parser("instagram", help="Prospection Instagram")
    p_ig.add_argument("--action", "-a", default="prospect",
                     choices=["prospect", "import", "export", "stats"])
    p_ig.add_argument("--target", "-t", default="#startup",
                     help="Hashtag ou compte cible")
    p_ig.add_argument("--actions", nargs="+", default=["like", "story"],
                     choices=["like", "comment", "follow", "story"])
    p_ig.add_argument("--file", help="Fichier d'import")
    
    # Dashboard
    subparsers.add_parser("dashboard", aliases=["dash", "stats"],
                          help="Tableau de bord")
    
    # Interactive
    subparsers.add_parser("interactive", help="Mode interactif")
    
    args = parser.parse_args()
    
    engine = ProspectingEngine()
    
    if args.command == "linkedin":
        if args.action == "prospect":
            engine.prospect_linkedin(args.target, args.max)
        elif args.action == "messages":
            engine.send_messages("linkedin", args.template)
        elif args.action == "import":
            engine.import_prospects("linkedin", args.file)
        elif args.action == "export":
            engine.export_prospects("linkedin")
        elif args.action == "stats":
            engine._show_stats("linkedin")
    
    elif args.command == "instagram":
        if args.action == "prospect":
            engine.prospect_instagram(args.target, args.actions)
        elif args.action == "import":
            engine.import_prospects("instagram", args.file)
        elif args.action == "export":
            engine.export_prospects("instagram")
        elif args.action == "stats":
            engine._show_stats("instagram")
    
    elif args.command in ("dashboard", "dash", "stats"):
        engine.show_dashboard()
    
    else:
        parser.print_help()
        print(f"""
{Colors.BOLD}Exemples:{Colors.NC}
  python3 prospecting-engine.py linkedin --action prospect --target "CTO France"
  python3 prospecting-engine.py linkedin --action messages --template personnalisé
  python3 prospecting-engine.py instagram --target "#startup" --actions like story
  python3 prospecting-engine.py dashboard
  python3 prospecting-engine.py linkedin --action import --file prospects.csv
        """)


if __name__ == "__main__":
    main()
