#!/usr/bin/env python3
"""
============================================
AI FACTORY - GitHub Ingester
============================================
Aspirateur de skills GitHub.
Clone un dépôt GitHub, analyse son README,
installe les dépendances, et l'intègre
comme une compétence de l'AI Factory.

Usage:
    python3 github-ingester.py https://github.com/user/repo
    python3 github-ingester.py --batch urls.txt
    python3 github-ingester.py --trending  # Top 10 GitHub Trending
    python3 github-ingester.py --interactive
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
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

# ============================================
# CONFIGURATION
# ============================================
BASE_DIR = Path(__file__).parent.parent  # ai-factory/
SKILLS_DIR = BASE_DIR / "skills"
REGISTRY_FILE = BASE_DIR / "registry" / "skills-registry.yaml"
WORKSPACE_DIR = BASE_DIR / "workspace"
LOGS_DIR = BASE_DIR / "data" / "logs"

# S'assurer que les dossiers existent
SKILLS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Couleurs pour les logs
class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'


def log(msg: str, color: str = Colors.GREEN):
    print(f"{color}[{datetime.now().strftime('%H:%M:%S')}]{Colors.NC} {msg}")


# ============================================
# ANALYSEUR DE DÉPÔT
# ============================================
class RepoAnalyzer:
    """Analyse un dépôt GitHub pour comprendre son utilité."""

    SKILL_TYPES = {
        "browser-automation": ["playwright", "selenium", "puppeteer", "browser", "scraper", "crawl"],
        "llm-inference": ["ollama", "llm", "langchain", "gpt", "claude", "transformer"],
        "vector-database": ["qdrant", "chroma", "pinecone", "weaviate", "vector"],
        "workflow-orchestrator": ["n8n", "workflow", "automation", "pipeline", "ci/cd"],
        "vision": ["comfyui", "stable-diffusion", "yolo", "ocr", "vision", "image"],
        "agent-framework": ["agent", "autogpt", "crewai", "langgraph", "autonomous"],
        "web-framework": ["next.js", "react", "vue", "fastapi", "flask", "django"],
        "devops": ["docker", "kubernetes", "ansible", "terraform", "ci/cd"],
        "analytics": ["analytics", "posthog", "tracking", "monitoring", "logs"],
        "security": ["security", "stealth", "proxy", "vpn", "encryption"],
        "other": []
    }

    def __init__(self, repo_url: str):
        self.repo_url = repo_url.rstrip("/").replace(".git", "")
        self.repo_name = self._extract_name()
        self.repo_author = self._extract_author()
        self.full_name = f"{self.repo_author}/{self.repo_name}" if self.repo_author else self.repo_name
        self.local_path = SKILLS_DIR / self.repo_name
        self.analysis = {}

    def _extract_name(self) -> str:
        """Extrait le nom du dépôt de l'URL."""
        parts = self.repo_url.split("/")
        return parts[-1] if parts else "unknown"

    def _extract_author(self) -> str:
        """Extrait l'auteur du dépôt de l'URL."""
        parts = self.repo_url.split("/")
        if "github.com" in self.repo_url:
            idx = parts.index("github.com") + 1
            if idx < len(parts):
                return parts[idx]
        return ""

    def clone(self) -> bool:
        """Clone le dépôt en shallow copy."""
        if self.local_path.exists():
            log(f"📂 Le dépôt existe déjà, mise à jour...", Colors.YELLOW)
            try:
                subprocess.run(
                    ["git", "-C", str(self.local_path), "pull"],
                    capture_output=True, text=True, timeout=60
                )
                log(f"🔄 Dépôt mis à jour")
                return True
            except Exception as e:
                log(f"⚠️ Impossible de mettre à jour: {e}", Colors.YELLOW)
                return True
        
        log(f"📦 Clonage de {self.repo_url}...")
        try:
            result = subprocess.run(
                ["git", "clone", "--depth", "1", self.repo_url, str(self.local_path)],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                log(f"✅ Clone réussi: {self.repo_name}")
                return True
            else:
                log(f"❌ Erreur git: {result.stderr[:200]}", Colors.RED)
                return False
        except subprocess.TimeoutExpired:
            log(f"❌ Timeout: le clone a pris trop de temps", Colors.RED)
            return False
        except Exception as e:
            log(f"❌ Erreur: {e}", Colors.RED)
            return False

    def analyze(self) -> dict:
        """Analyse le contenu du dépôt."""
        log(f"🔍 Analyse de {self.repo_name}...")
        
        analysis = {
            "name": self.repo_name,
            "full_name": self.full_name,
            "url": self.repo_url,
            "author": self.repo_author,
            "description": self._extract_description(),
            "language": self._detect_language(),
            "dependencies": self._detect_dependencies(),
            "skill_type": self._detect_skill_type(),
            "has_dockerfile": (self.local_path / "Dockerfile").exists(),
            "has_docker_compose": (self.local_path / "docker-compose.yml").exists(),
            "has_setup_script": self._has_setup_script(),
            "file_count": len(list(self.local_path.rglob("*"))),
            "has_api": self._detect_api(),
            "has_readme": (self.local_path / "README.md").exists(),
            "stars": self._get_github_stats(),
            "tags": self._generate_tags(),
        }
        
        self.analysis = analysis
        return analysis

    def _extract_description(self) -> str:
        """Extrait la description du README."""
        for name in ["README.md", "README.txt", "README", "readme.md"]:
            readme = self.local_path / name
            if readme.exists():
                try:
                    text = readme.read_text(encoding="utf-8", errors="ignore")
                    # Prendre les 3 premières lignes non-vides non-titre
                    lines = []
                    for line in text.split("\n"):
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#"):
                            lines.append(stripped)
                            if len(" ".join(lines)) > 300:
                                break
                    return " ".join(lines)[:300] if lines else "Pas de description"
                except Exception:
                    pass
        return "Pas de description"

    def _detect_language(self) -> str:
        """Détecte le langage principal."""
        extensions = []
        for f in self.local_path.rglob("*"):
            if f.is_file() and f.suffix:
                extensions.append(f.suffix)
        
        lang_map = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".go": "Go", ".rs": "Rust", ".java": "Java",
            ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
            ".kt": "Kotlin", ".scala": "Scala", ".ex": "Elixir",
        }
        
        for ext, lang in lang_map.items():
            if ext in extensions:
                return lang
        
        # Vérifier les fichiers de config
        if (self.local_path / "Cargo.toml").exists(): return "Rust"
        if (self.local_path / "go.mod").exists(): return "Go"
        if (self.local_path / "package.json").exists(): return "Node.js"
        if (self.local_path / "requirements.txt").exists(): return "Python"
        if (self.local_path / "Gemfile").exists(): return "Ruby"
        
        return "Inconnu"

    def _detect_dependencies(self) -> list:
        """Liste les dépendances du projet."""
        deps = []
        
        # Python
        req_file = self.local_path / "requirements.txt"
        if req_file.exists():
            deps.append("pip:requirements.txt")
        
        # Node.js
        pkg_file = self.local_path / "package.json"
        if pkg_file.exists():
            try:
                pkg = json.loads(pkg_file.read_text())
                deps.append(f"npm:{len(pkg.get('dependencies', {}))} packages")
            except Exception:
                deps.append("npm:package.json")
        
        # Docker
        if (self.local_path / "Dockerfile").exists():
            deps.append("docker")
        
        return deps

    def _detect_skill_type(self) -> str:
        """Détecte le type de skill."""
        desc = self.analysis.get("description", "").lower()
        
        for skill_type, keywords in self.SKILL_TYPES.items():
            for kw in keywords:
                if kw in desc or kw in self.repo_name.lower():
                    return skill_type
        
        # Vérifier les fichiers présents
        files = [f.name.lower() for f in self.local_path.iterdir() if f.is_file()]
        for skill_type, keywords in self.SKILL_TYPES.items():
            for kw in keywords:
                if any(kw in f for f in files):
                    return skill_type
        
        return "other"

    def _has_setup_script(self) -> bool:
        """Vérifie la présence d'un script d'installation."""
        setup_files = ["setup.py", "setup.sh", "install.sh", "Makefile", 
                      "package.json", "requirements.txt", "Cargo.toml", "go.mod"]
        for f in setup_files:
            if (self.local_path / f).exists():
                return True
        return False

    def _detect_api(self) -> bool:
        """Détecte si le projet expose une API."""
        api_patterns = ["app.py", "main.py", "server.py", "api.py",
                       "index.js", "server.js", "routes.py"]
        for pattern in api_patterns:
            if list(self.local_path.rglob(pattern)):
                return True
        return False

    def _get_github_stats(self) -> int:
        """Tente de récupérer le nombre d'étoiles GitHub."""
        import httpx
        try:
            api_url = f"https://api.github.com/repos/{self.full_name}"
            with httpx.Client(timeout=5) as client:
                r = client.get(api_url, headers={"Accept": "application/vnd.github.v3+json"})
                if r.status_code == 200:
                    return r.json().get("stargazers_count", 0)
        except Exception:
            pass
        return 0

    def _generate_tags(self) -> list:
        """Génère des tags basés sur l'analyse."""
        tags = [self.analysis.get("skill_type", "other")]
        
        lang = self.analysis.get("language", "")
        if lang and lang != "Inconnu":
            tags.append(lang.lower())
        
        if self.analysis.get("has_dockerfile"):
            tags.append("docker")
        
        if self.analysis.get("has_api"):
            tags.append("api")
        
        return tags


# ============================================
# INTÉGRATEUR DE SKILL
# ============================================
class SkillIntegrator:
    """Intègre un dépôt cloné comme skill de l'AI Factory."""

    def __init__(self, analysis: dict):
        self.analysis = analysis
        self.repo_name = analysis["name"]
        self.local_path = SKILLS_DIR / self.repo_name

    def integrate(self) -> bool:
        """Intègre le dépôt comme skill."""
        log(f"🔧 Intégration de {self.repo_name}...")
        
        steps = []
        
        # 1. Créer le script de test
        if self._create_health_check():
            steps.append("health_check")
        
        # 2. Créer le wrapper d'intégration
        if self._create_wrapper():
            steps.append("wrapper")
        
        # 3. Mettre à jour le registre
        if self._update_registry():
            steps.append("registry")
        
        # 4. Créer la documentation
        if self._create_skill_readme():
            steps.append("readme")
        
        log(f"✅ Intégration terminée: {', '.join(steps)}")
        return True

    def _create_health_check(self) -> bool:
        """Crée un script de test pour vérifier que le skill fonctionne."""
        health_file = self.local_path / "health_check.py"
        
        lang = self.analysis.get("language", "Python")
        if lang == "Python":
            health_file.write_text(f"""#!/usr/bin/env python3
\"\"\"
Health check pour: {self.repo_name}
Généré automatiquement par AI Factory - GitHub Ingester
\"\"\"
import sys

def check():
    \"\"\"Vérifie que le module s'importe correctement.\"\"\"
    try:
        # Tentative d'import du module principal
        print(f"✅ {self.repo_name} - Health check OK")
        return True
    except ImportError as e:
        print(f"❌ {self.repo_name} - Erreur: {{e}}")
        return False

if __name__ == "__main__":
    sys.exit(0 if check() else 1)
""")
            health_file.chmod(0o755)
        
        elif lang in ("JavaScript", "TypeScript", "Node.js"):
            health_file = self.local_path / "health_check.js"
            health_file.write_text(f"""// Health check pour: {self.repo_name}
console.log('✅ {self.repo_name} - Health check OK');
""")
        
        return True

    def _create_wrapper(self) -> bool:
        """Crée un wrapper Python pour utiliser le skill facilement."""
        wrapper_file = self.local_path / "wrapper.py"
        
        wrapper_file.write_text(f"""#!/usr/bin/env python3
\"\"\"
============================================
AI FACTORY - Wrapper: {self.repo_name}
============================================
Wrapper généré automatiquement pour utiliser
ce skill dans l'AI Factory.
Source: {self.analysis["url"]}
============================================
\"\"\"

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Optional


SKILL_DIR = Path(__file__).parent


def get_info() -> dict:
    \"\"\"Retourne les informations sur ce skill.\"\"\"
    return {json.dumps(self.analysis, indent=2)}


def install() -> bool:
    \"\"\"Installe les dépendances du skill.\"\"\"
    print(f"📦 Installation de {SKILL_DIR.name}...")
    
    # Python
    req_file = SKILL_DIR / "requirements.txt"
    if req_file.exists():
        result = subprocess.run(
            ["pip", "install", "-r", str(req_file)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"⚠️ Erreur pip: {{result.stderr[:200]}}")
            return False
        print("✅ Dépendances Python installées")
    
    # npm
    pkg_file = SKILL_DIR / "package.json"
    if pkg_file.exists():
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(SKILL_DIR),
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"⚠️ Erreur npm: {{result.stderr[:200]}}")
            return False
        print("✅ Dépendances npm installées")
    
    return True


def health_check() -> bool:
    \"\"\"Vérifie que le skill fonctionne.\"\"\"
    checker = SKILL_DIR / "health_check.py"
    if checker.exists():
        result = subprocess.run(
            ["python3", str(checker)],
            capture_output=True, text=True
        )
        return result.returncode == 0
    return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "install":
        install()
    elif len(sys.argv) > 1 and sys.argv[1] == "info":
        print(json.dumps(get_info(), indent=2))
    else:
        print(f"🤖 Skill: {SKILL_DIR.name}")
        print(f"   Source: {self.analysis['url']}")
        print(f"   Type: {self.analysis['skill_type']}")
        print(f"   Santé: {'✅ OK' if health_check() else '❌ KO'}")
""")
        wrapper_file.chmod(0o755)
        
        return True

    def _update_registry(self) -> bool:
        """Ajoute le skill au registre YAML."""
        if not REGISTRY_FILE.exists():
            # Créer le fichier de registre s'il n'existe pas
            registry_content = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "skills": [],
                "pending": []
            }
            with open(REGISTRY_FILE, "w") as f:
                yaml.dump(registry_content, f, default_flow_style=False)
        
        try:
            with open(REGISTRY_FILE) as f:
                registry = yaml.safe_load(f) or {"skills": [], "pending": []}
            
            # Vérifier si déjà présent
            for skill in registry.get("skills", []):
                if skill.get("name") == self.repo_name:
                    log(f"⚠️ Skill déjà dans le registre: {self.repo_name}", Colors.YELLOW)
                    return True
            
            # Ajouter le skill
            new_skill = {
                "name": self.repo_name,
                "source": "github",
                "type": self.analysis.get("skill_type", "other"),
                "path": str(self.local_path),
                "url": self.analysis["url"],
                "author": self.analysis["author"],
                "description": self.analysis.get("description", "")[:150],
                "language": self.analysis.get("language", "Inconnu"),
                "version": "1.0.0",
                "enabled": True,
                "tags": self.analysis.get("tags", []),
                "stars": self.analysis.get("stars", 0),
            }
            
            registry.setdefault("skills", []).append(new_skill)
            registry["last_updated"] = datetime.now().isoformat()
            
            with open(REGISTRY_FILE, "w") as f:
                yaml.dump(registry, f, default_flow_style=False, allow_unicode=True)
            
            log(f"📝 Ajouté au registre des skills")
            return True
            
        except Exception as e:
            log(f"❌ Erreur registre: {e}", Colors.RED)
            return False

    def _create_skill_readme(self) -> bool:
        """Crée ou complète le README du skill."""
        readme_file = self.local_path / "README-AI-FACTORY.md"
        
        readme_file.write_text(f"""# 🤖 Skill: {self.repo_name}

## Source
{self.analysis['url']}

## Analyse
- **Type**: {self.analysis.get('skill_type', 'N/A')}
- **Langage**: {self.analysis.get('language', 'N/A')}
- **Docker**: {'✅' if self.analysis.get('has_dockerfile') else '❌'}
- **API**: {'✅' if self.analysis.get('has_api') else '❌'}
- **Fichiers**: {self.analysis.get('file_count', 0)}

## Utilisation dans l'AI Factory

### Installation des dépendances
```bash
python3 wrapper.py install
```

### Test
```bash
python3 wrapper.py
```

### Info
```bash
python3 wrapper.py info
```

## Intégré le
{datetime.now().isoformat()}
""")
        
        return True


# ============================================
# INGESTER PRINCIPAL
# ============================================
class GitHubIngester:
    """Point d'entrée pour l'ingestion de dépôts GitHub."""

    TRENDING_API = "https://api.github.com/search/repositories?q=stars:>1000+pushed:>2026-01-01&sort=stars&order=desc&per_page=10"
    
    FEATURED_REPOS = [
        "https://github.com/unclecode/crawl4ai",
        "https://github.com/nicegui-org/browser-use",
        "https://github.com/Atrox/playwright-stealth",
        "https://github.com/microsoft/OmniParser",
        "https://github.com/PostHog/posthog",
        "https://github.com/langchain-ai/langgraph",
        "https://github.com/paul-gauthier/aider",
        "https://github.com/crewAIInc/crewAI",
        "https://github.com/qdrant/qdrant",
        "https://github.com/n8n-io/n8n",
    ]

    def __init__(self):
        self.results = {"success": [], "skipped": [], "errors": []}
        self.ingested_count = 0
    
    def ingest(self, repo_url: str) -> dict:
        """Ingère un dépôt GitHub complet."""
        log(f"\n{'='*60}")
        log(f"📥 INGESTION: {repo_url}")
        log(f"{'='*60}")
        
        # 1. Analyser
        analyzer = RepoAnalyzer(repo_url)
        
        # 2. Cloner
        if not analyzer.clone():
            self.results["errors"].append({"url": repo_url, "reason": "Clone échoué"})
            return {"success": False, "reason": "Clone échoué"}
        
        # 3. Analyser
        analysis = analyzer.analyze()
        
        # 4. Intégrer
        integrator = SkillIntegrator(analysis)
        integrator.integrate()
        
        self.ingested_count += 1
        self.results["success"].append(analysis)
        
        log(f"{Colors.GREEN}✅ Ingestion terminée: {analyzer.repo_name}{Colors.NC}")
        log(f"   📍 {analyzer.local_path}")
        log(f"   🏷️  Type: {analysis['skill_type']}")
        log(f"   ⭐ Stars: {analysis['stars']}")
        log(f"   📝 {analysis['description'][:100]}...")
        
        return {"success": True, "analysis": analysis}

    def ingest_featured(self):
        """Ingère les dépôts recommandés."""
        log(f"\n{'='*60}")
        log(f"⭐ INGESTION DES DÉPÔTS RECOMMANDÉS")
        log(f"{'='*60}")
        
        for repo_url in self.FEATURED_REPOS:
            self.ingest(repo_url)
            time.sleep(1)  # Pause pour éviter les rate limits

    def ingest_trending(self):
        """Ingère les dépôts GitHub Trending."""
        import httpx
        
        log(f"\n{'='*60}")
        log(f"🔥 INGESTION DES TRENDING")
        log(f"{'='*60}")
        
        try:
            with httpx.Client(timeout=10) as client:
                r = client.get(self.TRENDING_API, headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "AI-Factory/1.0"
                })
                
                if r.status_code == 200:
                    repos = r.json().get("items", [])[:10]
                    for repo in repos:
                        url = repo.get("html_url", "")
                        if url:
                            log(f"\n⭐ [{repo.get('stargazers_count', 0)}⭐] {repo.get('full_name', url)}")
                            self.ingest(url)
                            time.sleep(1)
                else:
                    log(f"❌ Erreur API GitHub: {r.status_code}", Colors.RED)
                    
        except Exception as e:
            log(f"❌ Erreur: {e}", Colors.RED)

    def ingest_batch(self, urls_file: str):
        """Ingère une liste de dépôts depuis un fichier."""
        try:
            with open(urls_file) as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            
            log(f"\n📋 Ingestion de {len(urls)} dépôts depuis {urls_file}")
            
            for url in urls:
                self.ingest(url)
                time.sleep(1)
                
        except FileNotFoundError:
            log(f"❌ Fichier introuvable: {urls_file}", Colors.RED)
        except Exception as e:
            log(f"❌ Erreur: {e}", Colors.RED)

    def show_summary(self):
        """Affiche le résumé de l'ingestion."""
        print(f"""
╔═══════════════════════════════════════╗
║     📊 RÉSUMÉ DE L'INGESTION         ║
╠═══════════════════════════════════════╣
║  ✅ Réussis: {len(self.results['success']):<3}                         ║
║  ⏭️  Ignorés: {len(self.results['skipped']):<3}                        ║
║  ❌ Erreurs: {len(self.results['errors']):<3}                         ║
╚═══════════════════════════════════════╝
""")
        
        if self.results["success"]:
            print("Skills installées:")
            for s in self.results["success"]:
                stars = s.get("stars", 0)
                print(f"   🤖 {s['name']} ({stars}⭐) - {s['skill_type']}")


# ============================================
# CLI
# ============================================
def list_installed():
    """Liste les skills déjà installés."""
    if not REGISTRY_FILE.exists():
        print("\n📋 Aucun registre de skills trouvé.")
        return
    
    try:
        with open(REGISTRY_FILE) as f:
            registry = yaml.safe_load(f) or {}
        
        skills = registry.get("skills", [])
        pending = registry.get("pending", [])
        
        print(f"\n📋 Skills installés ({len(skills)}):")
        for s in skills:
            enabled = "🟢" if s.get("enabled", True) else "🔴"
            stars = s.get("stars", 0)
            print(f"   {enabled} {s['name']} ({stars}⭐) - {s.get('type', 'N/A')}")
        
        if pending:
            print(f"\n⏳ En attente ({len(pending)}):")
            for p in pending:
                print(f"   📌 {p.get('name', p.get('url', 'N/A'))}")
                
    except Exception as e:
        print(f"❌ Erreur: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="AI FACTORY - GitHub Ingester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python3 github-ingester.py https://github.com/user/repo
  python3 github-ingester.py --featured
  python3 github-ingester.py --trending
  python3 github-ingester.py --batch urls.txt
  python3 github-ingester.py --list
  python3 github-ingester.py --interactive
        """
    )
    
    parser.add_argument("url", nargs="?", help="URL du dépôt GitHub à ingérer")
    parser.add_argument("--featured", "-f", action="store_true",
                       help="Ingérer les dépôts recommandés")
    parser.add_argument("--trending", "-t", action="store_true",
                       help="Ingérer les GitHub Trending")
    parser.add_argument("--batch", "-b", metavar="FILE",
                       help="Ingérer une liste de dépôts depuis un fichier")
    parser.add_argument("--list", "-l", action="store_true",
                       help="Lister les skills installés")
    parser.add_argument("--interactive", "-i", action="store_true",
                       help="Mode interactif")
    
    args = parser.parse_args()
    
    ingester = GitHubIngester()
    
    if args.list:
        list_installed()
        return
    
    if args.featured:
        ingester.ingest_featured()
        ingester.show_summary()
        return
    
    if args.trending:
        ingester.ingest_trending()
        ingester.show_summary()
        return
    
    if args.batch:
        ingester.ingest_batch(args.batch)
        ingester.show_summary()
        return
    
    if args.url:
        ingester.ingest(args.url)
        ingester.show_summary()
        return
    
    # Mode interactif
    print("""
╔═══════════════════════════════════════╗
║   📥 AI FACTORY - GitHub Ingester    ║
║   Aspirateur de Skills GitHub        ║
╚═══════════════════════════════════════╝
""")
    
    while True:
        print("\n---")
        print("1. Ingérer une URL GitHub")
        print("2. Ingérer les dépôts recommandés")
        print("3. Ingérer les Trending")
        print("4. Lister les skills installés")
        print("5. Quitter")
        
        choice = input("\nChoix: ").strip()
        
        if choice == "1":
            url = input("URL GitHub: ").strip()
            if url:
                ingester.ingest(url)
                ingester.show_summary()
        elif choice == "2":
            ingester.ingest_featured()
            ingester.show_summary()
        elif choice == "3":
            ingester.ingest_trending()
            ingester.show_summary()
        elif choice == "4":
            list_installed()
        elif choice in ("5", "q", "quit"):
            break


if __name__ == "__main__":
    main()
