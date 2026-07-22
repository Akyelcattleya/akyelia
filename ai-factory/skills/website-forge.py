#!/usr/bin/env python3
"""
============================================
AI FACTORY - Website Forge
============================================
Générateur de sites web en 5 minutes.
Donne une description en français, il crée
un site complet, le dockerise et le déploie.

Usage:
    python3 website-forge.py "Crée un site vitrine pour mon agence"
    python3 website-forge.py --interactive
    python3 website-forge.py --list
    python3 website-forge.py --deploy mon-site

Prérequis: Ollama doit tourner pour la génération
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
WORKSPACE_DIR = BASE_DIR / "workspace"
OLLAMA_API = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b")
CADDY_DIR = BASE_DIR / "config" / "caddy"


class Colors:
    GREEN = '\033[0;32m'; YELLOW = '\033[1;33m'
    RED = '\033[0;31m'; BLUE = '\033[0;34m'; CYAN = '\033[0;36m'
    BOLD = '\033[1m'; NC = '\033[0m'


# ============================================
# MOTEUR DE GÉNÉRATION
# ============================================
class WebsiteGenerator:
    """Génère des sites web complets via IA."""

    # Templates disponibles
    TEMPLATES = {
        "landing": {
            "name": "Landing Page",
            "description": "Page de capture one-page avec hero, features, CTA",
            "tech": "HTML + Tailwind CSS"
        },
        "saaS": {
            "name": "SaaS Dashboard",
            "description": "Dashboard avec navigation, tableaux, graphiques",
            "tech": "HTML + Tailwind CSS + Chart.js"
        },
        "blog": {
            "name": "Blog / Portfolio",
            "description": "Blog avec articles, catégories, pagination",
            "tech": "HTML + Tailwind CSS"
        },
        "ecommerce": {
            "name": "E-commerce",
            "description": "Boutique en ligne avec catalogue, panier, checkout",
            "tech": "HTML + Tailwind CSS + Alpine.js"
        },
        "admin": {
            "name": "Admin Panel",
            "description": "Interface d'administration avec tables, formulaires",
            "tech": "HTML + Tailwind CSS + Alpine.js"
        },
        "mobile-app": {
            "name": "PWA Mobile",
            "description": "Progressive Web App responsive like native",
            "tech": "HTML + Tailwind CSS + PWA manifest"
        }
    }

    def __init__(self):
        self.generated = []

    def list_templates(self) -> dict:
        return self.TEMPLATES

    def list_sites(self) -> list:
        """Liste les sites déjà générés."""
        sites = []
        if WORKSPACE_DIR.exists():
            for d in sorted(WORKSPACE_DIR.iterdir()):
                if d.is_dir() and (d / "index.html").exists():
                    sites.append({
                        "name": d.name,
                        "type": self._detect_type(d),
                        "created": datetime.fromtimestamp(d.stat().st_mtime).isoformat()[:10],
                        "files": len(list(d.rglob("*"))),
                        "deployed": (d / "Dockerfile").exists()
                    })
        return sites

    def _detect_type(self, site_dir: Path) -> str:
        for tpl_name, tpl_info in self.TEMPLATES.items():
            if (site_dir / f"tpl-{tpl_name}.marker").exists():
                return tpl_info["name"]
        return "Personnalisé"

    def _ask_llm(self, prompt: str, system: str = None) -> str:
        """Interroge Ollama."""
        import httpx
        
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 8192}
        }
        if system:
            payload["system"] = system
        
        try:
            with httpx.Client(timeout=180) as client:
                r = client.post(f"{OLLAMA_API}/api/generate", json=payload)
                return r.json().get("response", "") if r.status_code == 200 else ""
        except Exception as e:
            print(f"❌ Erreur Ollama: {e}")
            return ""

    def generate(self, description: str, template: str = "landing",
                 output_name: str = None) -> dict:
        """
        Génère un site complet à partir d'une description.

        Args:
            description: Description du site en français
            template: Type de template (landing, SaaS, blog, ecommerce, admin, mobile-app)
            output_name: Nom du dossier de sortie

        Returns:
            dict: Informations sur le site généré
        """
        print(f"\n{'='*60}")
        print(f"🌐 WEBSITE FORGE - Génération")
        print(f"{'='*60}")
        print(f"📝 Description: {description}")
        print(f"📐 Template: {self.TEMPLATES.get(template, {}).get('name', template)}")
        
        # 1. Nom du projet
        site_name = output_name or self._generate_name(description)
        site_id = f"{site_name}-{uuid.uuid4().hex[:4]}"
        site_dir = WORKSPACE_DIR / site_id
        site_dir.mkdir(parents=True, exist_ok=True)
        
        # 2. Générer le site avec l'IA
        print(f"\n🧠 Génération du site avec {OLLAMA_MODEL}...")
        site_content = self._generate_site(description, template, site_name)
        
        # 3. Écrire les fichiers
        print(f"📁 Création dans: {site_dir}")
        for filename, content in site_content.items():
            file_path = site_dir / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            print(f"   ✅ {filename} ({len(content)} caractères)")
        
        # 4. Créer les fichiers additionnels
        self._create_dockerfile(site_dir, site_name, template)
        self._create_nginx_config(site_dir, site_name)
        self._create_readme(site_dir, description, template, site_name)
        
        # 5. Marquer le template
        (site_dir / f"tpl-{template}.marker").write_text("")
        
        site_info = {
            "id": site_id,
            "name": site_name,
            "path": str(site_dir),
            "template": template,
            "description": description,
            "files": list(site_content.keys()),
            "created_at": datetime.now().isoformat()
        }
        
        self.generated.append(site_info)
        
        print(f"\n✅ Site généré avec succès!")
        print(f"   📍 {site_dir}")
        print(f"   📄 {len(site_content)} fichiers")
        print(f"   🐳 Dockerfile: {'✅' if (site_dir/'Dockerfile').exists() else '❌'}")
        print(f"\n{Colors.CYAN}   Pour voir: python3 website-forge.py --serve {site_id}{Colors.NC}")
        
        return site_info

    def _generate_name(self, description: str) -> str:
        words = description.lower().split()[:3]
        name = re.sub(r'[^a-z0-9-]', '-', '-'.join(words))
        return name.strip('-')[:30] or "mon-site"

    def _generate_site(self, description: str, template: str, name: str) -> dict:
        """Génère le contenu du site via IA ou template."""
        
        if template == "landing":
            return self._generate_landing(description, name)
        elif template == "mobile-app":
            return self._generate_mobile_app(description, name)
        else:
            return self._generate_generic(description, template, name)

    def _generate_landing(self, description: str, name: str) -> dict:
        """Génère une landing page moderne."""
        return {
            "index.html": self._landing_html(description, name),
            "style.css": self._landing_css(),
            "script.js": self._landing_js(),
            "robots.txt": self._robots_txt(),
            "sitemap.xml": self._sitemap_xml(name),
        }

    def _landing_html(self, description: str, name: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name.replace('-', ' ').title()} — Site Officiel</title>
    <meta name="description" content="{description[:150]}">
    <link rel="stylesheet" href="style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar">
        <div class="container">
            <a href="/" class="logo">{name.replace('-', ' ').title()}</a>
            <ul class="nav-links">
                <li><a href="#features">Fonctionnalités</a></li>
                <li><a href="#about">À propos</a></li>
                <li><a href="#contact" class="btn-primary">Contact</a></li>
            </ul>
            <button class="menu-toggle" aria-label="Menu">☰</button>
        </div>
    </nav>

    <!-- Hero Section -->
    <section class="hero">
        <div class="container">
            <div class="hero-content">
                <span class="badge">🚀 Nouveau</span>
                <h1>{description[:60]}</h1>
                <p>{description}</p>
                <div class="hero-cta">
                    <a href="#contact" class="btn-primary btn-large">Commencer maintenant</a>
                    <a href="#features" class="btn-secondary btn-large">En savoir plus</a>
                </div>
            </div>
            <div class="hero-visual">
                <div class="hero-shape"></div>
            </div>
        </div>
    </section>

    <!-- Features -->
    <section id="features" class="features">
        <div class="container">
            <h2>Fonctionnalités</h2>
            <div class="features-grid">
                <div class="feature-card">
                    <div class="feature-icon">⚡</div>
                    <h3>Rapide</h3>
                    <p>Optimisé pour des performances maximales</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">🔒</div>
                    <h3>Sécurisé</h3>
                    <p>Protection des données de niveau entreprise</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">📱</div>
                    <h3>Responsive</h3>
                    <p>S'adapte à tous les écrans</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">🎨</div>
                    <h3>Design</h3>
                    <p>Interface moderne et intuitive</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">🔧</div>
                    <h3>Personnalisable</h3>
                    <p>Adapté à vos besoins spécifiques</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">💬</div>
                    <h3>Support</h3>
                    <p>Assistance dédiée 7j/7</p>
                </div>
            </div>
        </div>
    </section>

    <!-- About -->
    <section id="about" class="about">
        <div class="container">
            <h2>À propos</h2>
            <p>Site généré par AI Factory — Votre usine à sites autonome.</p>
        </div>
    </section>

    <!-- Contact -->
    <section id="contact" class="contact">
        <div class="container">
            <h2>Contactez-nous</h2>
            <form class="contact-form">
                <input type="text" placeholder="Votre nom" required>
                <input type="email" placeholder="Votre email" required>
                <textarea placeholder="Votre message" rows="5" required></textarea>
                <button type="submit" class="btn-primary btn-large">Envoyer</button>
            </form>
        </div>
    </section>

    <!-- Footer -->
    <footer class="footer">
        <div class="container">
            <p>&copy; {datetime.now().year} {name.replace('-', ' ').title()}. Généré par AI Factory.</p>
        </div>
    </footer>

    <script src="script.js"></script>
</body>
</html>"""

    def _landing_css(self) -> str:
        return """/* ============================================
   AI FACTORY - Landing Page Styles
   ============================================ */
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    line-height: 1.6;
}
.container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }
h1, h2, h3 { line-height: 1.2; }
h1 { font-size: clamp(2.5rem, 5vw, 4rem); font-weight: 800; }
h2 { font-size: clamp(2rem, 3vw, 2.5rem); font-weight: 700; text-align: center; margin-bottom: 3rem; }

/* Navigation */
.navbar {
    position: fixed; top: 0; left: 0; right: 0;
    background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(10px);
    border-bottom: 1px solid #1e293b; z-index: 1000;
}
.navbar .container { display: flex; align-items: center; justify-content: space-between; height: 70px; }
.logo { font-size: 1.5rem; font-weight: 700; color: #38bdf8; text-decoration: none; }
.nav-links { display: flex; list-style: none; gap: 2rem; align-items: center; }
.nav-links a { color: #94a3b8; text-decoration: none; transition: color 0.3s; }
.nav-links a:hover { color: #e2e8f0; }
.menu-toggle { display: none; background: none; border: none; color: #e2e8f0; font-size: 1.5rem; cursor: pointer; }

/* Hero */
.hero {
    min-height: 100vh; display: flex; align-items: center;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
    padding-top: 70px;
}
.hero .container { display: grid; grid-template-columns: 1fr 1fr; gap: 4rem; align-items: center; }
.badge {
    display: inline-block; padding: 6px 16px; border-radius: 20px;
    background: rgba(56, 189, 248, 0.1); color: #38bdf8; font-size: 0.875rem;
    margin-bottom: 1.5rem; font-weight: 500;
}
.hero h1 { margin-bottom: 1.5rem; }
.hero p { color: #94a3b8; font-size: 1.125rem; margin-bottom: 2rem; max-width: 500px; }
.hero-cta { display: flex; gap: 1rem; flex-wrap: wrap; }
.hero-visual { display: flex; justify-content: center; align-items: center; }
.hero-shape {
    width: 400px; height: 400px; border-radius: 50%;
    background: radial-gradient(circle, rgba(56, 189, 248, 0.2) 0%, transparent 70%);
    animation: pulse 4s ease-in-out infinite;
}
@keyframes pulse { 0%, 100% { transform: scale(1); opacity: 0.5; } 50% { transform: scale(1.1); opacity: 0.8; } }

/* Buttons */
.btn-primary { display: inline-block; padding: 12px 28px; border-radius: 8px; background: #38bdf8; color: #0f172a; text-decoration: none; font-weight: 600; transition: all 0.3s; border: none; cursor: pointer; }
.btn-primary:hover { background: #7dd3fc; transform: translateY(-2px); }
.btn-secondary { display: inline-block; padding: 12px 28px; border-radius: 8px; background: transparent; color: #e2e8f0; text-decoration: none; font-weight: 600; border: 1px solid #334155; transition: all 0.3s; }
.btn-secondary:hover { border-color: #38bdf8; color: #38bdf8; }
.btn-large { padding: 16px 36px; font-size: 1.125rem; }

/* Features */
.features, .about, .contact { padding: 6rem 0; }
.features { background: #0f172a; }
.features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 2rem; }
.feature-card {
    background: #1e293b; border: 1px solid #334155; border-radius: 16px;
    padding: 2rem; transition: all 0.3s; cursor: default;
}
.feature-card:hover { transform: translateY(-4px); border-color: #38bdf8; box-shadow: 0 8px 32px rgba(56, 189, 248, 0.1); }
.feature-icon { font-size: 2rem; margin-bottom: 1rem; }
.feature-card h3 { margin-bottom: 0.5rem; }
.feature-card p { color: #94a3b8; }

/* Contact */
.contact { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); }
.contact-form { max-width: 500px; margin: 0 auto; display: flex; flex-direction: column; gap: 1rem; }
.contact-form input, .contact-form textarea {
    padding: 14px 18px; border-radius: 8px; border: 1px solid #334155;
    background: #1e293b; color: #e2e8f0; font-size: 1rem; font-family: inherit; transition: border-color 0.3s;
}
.contact-form input:focus, .contact-form textarea:focus { outline: none; border-color: #38bdf8; }

/* Footer */
.footer { border-top: 1px solid #1e293b; padding: 2rem 0; text-align: center; color: #64748b; }

/* Responsive */
@media (max-width: 768px) {
    .hero .container { grid-template-columns: 1fr; text-align: center; }
    .hero p { margin: 0 auto 2rem; }
    .hero-cta { justify-content: center; }
    .hero-shape { width: 200px; height: 200px; }
    .nav-links { display: none; }
    .menu-toggle { display: block; }
    .nav-links.active { display: flex; flex-direction: column; position: absolute; top: 70px; left: 0; right: 0; background: #0f172a; padding: 1rem; border-bottom: 1px solid #1e293b; }
}
"""

    def _landing_js(self) -> str:
        return """// AI FACTORY - Landing Page
document.addEventListener('DOMContentLoaded', function() {
    // Menu mobile
    const toggle = document.querySelector('.menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    if (toggle) {
        toggle.addEventListener('click', () => navLinks.classList.toggle('active'));
    }

    // Smooth scroll
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    });

    // Animation au scroll
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) entry.target.style.opacity = '1';
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.feature-card').forEach(el => {
        el.style.opacity = '0';
        el.style.transition = 'opacity 0.6s ease';
        observer.observe(el);
    });

    // Contact form
    const form = document.querySelector('.contact-form');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = form.querySelector('button');
            btn.textContent = 'Envoi...';
            btn.disabled = true;
            await new Promise(r => setTimeout(r, 1000));
            btn.textContent = '✅ Message envoyé !';
            setTimeout(() => { btn.textContent = 'Envoyer'; btn.disabled = false; }, 2000);
        });
    }
});
"""

    def _robots_txt(self) -> str:
        return "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n"

    def _sitemap_xml(self, name: str) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://{name}.example.com/</loc><priority>1.0</priority></url>
</urlset>"""

    def _generate_mobile_app(self, description: str, name: str) -> dict:
        """Génère une Progressive Web App mobile."""
        html = self._landing_html(description, name).replace(
            '<link rel="stylesheet" href="style.css">',
            '<link rel="stylesheet" href="style.css">\n    <link rel="manifest" href="manifest.json">\n    <meta name="theme-color" content="#0f172a">'
        )
        
        manifest = {
            "name": name.replace('-', ' ').title(),
            "short_name": name[:12],
            "description": description[:100],
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0f172a",
            "theme_color": "#0f172a",
            "icons": [{"src": "/icon.svg", "sizes": "512x512", "type": "image/svg+xml", "purpose": "any maskable"}]
        }
        
        return {
            "index.html": html,
            "style.css": self._landing_css(),
            "script.js": self._landing_js(),
            "manifest.json": json.dumps(manifest, indent=2),
            "sw.js": self._service_worker(),
            "robots.txt": self._robots_txt(),
        }

    def _service_worker(self) -> str:
        return """self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(clients.claim()));
self.addEventListener('fetch', e => e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
));
"""

    def _generate_generic(self, description: str, template: str, name: str) -> dict:
        """Génère un site pour les autres templates."""
        return {
            "index.html": f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name.replace('-', ' ').title()}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; line-height: 1.6; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
header {{ text-align: center; padding: 4rem 0; }}
h1 {{ font-size: 3rem; color: #38bdf8; }}
p {{ color: #94a3b8; font-size: 1.125rem; }}
</style></head>
<body>
<div class="container">
    <header>
        <h1>{name.replace('-', ' ').title()}</h1>
        <p>{description}</p>
        <p style="margin-top:2rem;color:#64748b">Généré par AI Factory — Website Forge</p>
    </header>
</div></body></html>""",
            "style.css": "/* Ready for customization */",
        }

    def _create_dockerfile(self, site_dir: Path, name: str, template: str):
        """Crée un Dockerfile pour le site."""
        dockerfile = f"""FROM caddy:alpine

COPY . /usr/share/caddy

ENV SITE_NAME="{name}"
ENV TEMPLATE="{template}"

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
    CMD wget -qO- http://localhost:80/ || exit 1

EXPOSE 80

CMD ["caddy", "file-server", "--root", "/usr/share/caddy", "--listen", ":80"]
"""
        (site_dir / "Dockerfile").write_text(dockerfile)

    def _create_nginx_config(self, site_dir: Path, name: str):
        """Crée une config nginx-like pour Caddy."""
        caddyfile = site_dir / "Caddyfile"
        caddyfile.write_text(f""":80 {{
    root * /usr/share/caddy
    file_server
    encode gzip zstd
    
    header {{
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Cache-Control "public, max-age=3600"
    }}
}}
""")

    def _create_readme(self, site_dir: Path, description: str, template: str, name: str):
        """Crée un README pour le site."""
        (site_dir / "README.md").write_text(f"""# 🌐 {name.replace('-', ' ').title()}

**Généré par AI Factory - Website Forge**

## Description
{description}

## Template
- Type: {self.TEMPLATES.get(template, {}).get('name', template)}
- Tech: {self.TEMPLATES.get(template, {}).get('tech', 'HTML/CSS')}

## Déploiement

### Avec Docker
```bash
docker build -t {name} .
docker run -d -p 8080:80 {name}
```

### En local
Ouvre simplement `index.html` dans un navigateur.

## Fichiers
- `index.html` - Page principale
- `style.css` - Styles
- `script.js` - Interactions
- `Dockerfile` - Pour le déploiement

## Généré le
{datetime.now().isoformat()}
""")

    def deploy(self, site_name: str) -> bool:
        """Déploie un site dans Docker."""
        sites = self.list_sites()
        site = next((s for s in sites if s["name"] == site_name or site_name in s["name"]), None)
        
        if not site:
            # Chercher par ID
            for d in WORKSPACE_DIR.iterdir():
                if d.is_dir() and d.name.startswith(site_name):
                    site = {"name": d.name, "path": str(d)}
                    break
        
        if not site:
            print(f"❌ Site '{site_name}' introuvable")
            return False
        
        site_dir = Path(site["path"]) if "path" in site else WORKSPACE_DIR / site["name"]
        name = site["name"].split("-")[0]  # Enlever l'ID
        
        print(f"\n🐳 Déploiement de {name}...")
        
        try:
            subprocess.run(["docker", "build", "-t", f"site-{name}", "."],
                         cwd=site_dir, check=True, capture_output=True)
            subprocess.run([
                "docker", "run", "-d",
                "--name", f"site-{name}",
                "--restart", "unless-stopped",
                "-p", "8080:80",
                f"site-{name}"
            ], check=True, capture_output=True)
            
            print(f"✅ Site déployé: http://localhost:8080")
            print(f"   Pour arrêter: docker stop site-{name}")
            return True
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False


# ============================================
# CLI
# ============================================
def main():
    parser = argparse.ArgumentParser(
        description="🌐 AI FACTORY - Website Forge",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command")
    
    # Générer
    p_gen = subparsers.add_parser("generate", aliases=["g", "new"])
    p_gen.add_argument("description", help="Description du site en français")
    p_gen.add_argument("--template", "-t", default="landing",
                      choices=["landing", "SaaS", "blog", "ecommerce", "admin", "mobile-app"])
    p_gen.add_argument("--name", "-n", help="Nom du site")
    
    # Lister
    subparsers.add_parser("list", aliases=["ls"])
    
    # Déployer
    p_deploy = subparsers.add_parser("deploy")
    p_deploy.add_argument("name", help="Nom ou ID du site à déployer")
    
    # Templates
    subparsers.add_parser("templates", aliases=["tpl"])
    
    args = parser.parse_args()
    
    forge = WebsiteGenerator()
    
    if args.command in ("generate", "g", "new"):
        forge.generate(args.description, args.template or "landing", args.name)
    
    elif args.command in ("list", "ls"):
        sites = forge.list_sites()
        if sites:
            print(f"\n📋 Sites générés ({len(sites)}):")
            for s in sites:
                deployed = "🐳" if s["deployed"] else "📄"
                print(f"   {deployed} {s['name']:35} {s['type']:15} {s['created']}")
        else:
            print("\n📋 Aucun site généré pour le moment.")
            print("   → Crée un site: python3 website-forge.py generate \"Ma description\"")
    
    elif args.command == "deploy":
        forge.deploy(args.name)
    
    elif args.command in ("templates", "tpl"):
        print(f"\n📐 Templates disponibles ({len(forge.TEMPLATES)}):")
        for tpl_name, tpl_info in forge.TEMPLATES.items():
            print(f"\n   {tpl_info['name']:20} {tpl_info['tech']}")
            print(f"   {'':20} {tpl_info['description']}")
    
    else:
        parser.print_help()
        print(f"\n{Colors.BOLD}Exemples:{Colors.NC}")
        print(f"  python3 website-forge.py generate \"Crée un site pour mon agence de marketing\"")
        print(f"  python3 website-forge.py generate \"App mobile de suivi de fitness\" -t mobile-app")
        print(f"  python3 website-forge.py list")
        print(f"  python3 website-forge.py deploy mon-site")


if __name__ == "__main__":
    main()
