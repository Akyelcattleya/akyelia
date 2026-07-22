#!/usr/bin/env python3
"""
============================================
AI FACTORY - Marketing Agent
============================================
Agence de marketing automatisée.
Stratégie, création de contenu, SEO/GEO,
réseaux sociaux, campagnes — le tout piloté
par IA sur ton VPS.

Ce module remplace une agence marketing complète.

Usage:
    python3 marketing-agent.py strategy "Mon produit X pour client Y"
    python3 marketing-agent.py content "Article sur le thème Z"
    python3 marketing-agent.py social "LinkedIn post sur mon nouveau service"
    python3 marketing-agent.py seo "Analyse le SEO de mon site"
    python3 marketing-agent.py geo "Optimise mon site pour les LLM"
    python3 marketing-agent.py campaign --budget 500 --target "PME tech"
    python3 marketing-agent.py dashboard
============================================
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ============================================
# CONFIGURATION
# ============================================
BASE_DIR = Path(__file__).parent.parent  # ai-factory/
WORKSPACE_DIR = BASE_DIR / "workspace"
DATA_DIR = BASE_DIR / "data"
OLLAMA_API = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:14b")
CONTENT_DIR = WORKSPACE_DIR / "content"
CAMPAIGNS_DIR = WORKSPACE_DIR / "campaigns"

CONTENT_DIR.mkdir(parents=True, exist_ok=True)
CAMPAIGNS_DIR.mkdir(parents=True, exist_ok=True)


class Colors:
    GREEN = '\033[0;32m'; YELLOW = '\033[1;33m'
    RED = '\033[0;31m'; BLUE = '\033[0;34m'; CYAN = '\033[0;36m'
    BOLD = '\033[1m'; NC = '\033[0m'


def log(msg, color=Colors.GREEN):
    print(f"{color}[{datetime.now().strftime('%H:%M:%S')}]{Colors.NC} {msg}")


# ============================================
# MOTEUR DE GÉNÉRATION
# ============================================
class LLM:
    """Interface avec Ollama pour la génération."""

    def ask(self, prompt: str, system: str = None, 
            temperature: float = 0.7, max_tokens: int = 4096) -> str:
        import httpx
        
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens}
        }
        if system:
            payload["system"] = system
        
        try:
            with httpx.Client(timeout=180) as client:
                r = client.post(f"{OLLAMA_API}/api/generate", json=payload)
                return r.json().get("response", "") if r.status_code == 200 else ""
        except Exception as e:
            log(f"❌ Erreur LLM: {e}", Colors.RED)
            return ""

    def generate_json(self, prompt: str, system: str = None,
                      temperature: float = 0.3) -> dict:
        """Génère une réponse JSON structurée."""
        response = self.ask(prompt, system, temperature)
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        return {"response": response[:200]}


# ============================================
# MODULE STRATÉGIE
# ============================================
class StrategyEngine:
    """Analyse de marché et stratégie marketing."""

    def __init__(self):
        self.llm = LLM()

    def analyze_market(self, product: str, audience: str = None) -> dict:
        """Analyse de marché complète."""
        log(f"📊 Analyse de marché pour: {product}")
        
        prompt = f"""Analyse le marché pour ce produit/service:
Produit: {product}
Cible: {audience or 'Grand public'}

Génère une analyse complète en JSON:
{{
    "product": "{product}",
    "market_analysis": {{
        "trends": ["Tendance 1", "Tendance 2"],
        "opportunities": ["Opportunité 1", "Opportunité 2"],
        "threats": ["Menace 1", "Menace 2"]
    }},
    "target_audience": {{
        "primary": "Cible principale",
        "demographics": ["Âge", "Sexe", "Localisation"],
        "pain_points": ["Problème 1", "Problème 2"],
        "aspirations": ["Objectif 1", "Objectif 2"]
    }},
    "competitors": [
        {{"name": "Concurrent A", "strengths": ["Force 1"], "weaknesses": ["Faiblesse 1"]}}
    ],
    "positioning": "Positionnement stratégique recommandé",
    "unique_selling_points": ["USP 1", "USP 2", "USP 3"],
    "recommended_channels": ["LinkedIn", "Instagram", "Blog"],
    "budget_allocation": {{"content": 40, "ads": 30, "seo": 20, "tools": 10}},
    "estimated_timeline": "3 mois pour résultats visibles"
}}"""
        
        result = self.llm.generate_json(prompt, temperature=0.4)
        self._save_analysis(product, result)
        return result

    def create_strategy(self, product: str, goal: str = "notoriété",
                        budget: str = "1000€/mois") -> dict:
        """Crée une stratégie marketing complète."""
        log(f"🎯 Création de stratégie pour: {product}")
        
        prompt = f"""Crée une stratégie marketing complète:
Produit: {product}
Objectif: {goal}
Budget: {budget}

Réponds en JSON avec:
- objectives (3 objectifs SMART)
- channels (canaux à utiliser avec priorité)
- content_plan (plan de contenu sur 30 jours)
- kpis (indicateurs de performance)
- timeline (calendrier sur 3 mois)
- budget_breakdown (répartition détaillée)
- success_metrics (métriques de succès)"""
        
        result = self.llm.generate_json(prompt, temperature=0.5)
        return result

    def _save_analysis(self, product: str, analysis: dict):
        """Sauvegarde l'analyse."""
        filename = re.sub(r'[^a-z0-9]', '_', product.lower())[:30]
        filepath = CONTENT_DIR / f"strategy-{filename}.json"
        filepath.write_text(json.dumps(analysis, indent=2, ensure_ascii=False))
        log(f"💾 Analyse sauvegardée: {filepath.name}")


# ============================================
# MODULE CONTENU
# ============================================
class ContentEngine:
    """Génération de contenu automatisée."""

    def __init__(self):
        self.llm = LLM()

    def generate_post(self, topic: str, platform: str = "linkedin",
                      tone: str = "professionnel") -> dict:
        """Génère un post pour les réseaux sociaux."""
        log(f"✍️ Génération d'un post {platform} sur: {topic}")
        
        system = f"""Tu es un expert en copywriting pour {platform}.
Style: {tone}
Format adapté à la plateforme.
Inclus des emojis pertinents.
Termine par un call-to-action."""

        prompt = f"""Rédige un post pour {platform} sur le thème: {topic}

Le post doit:
- Accrocher dans les 3 premières lignes
- Apporter de la valeur
- Inclure un CTA
- Être optimisé pour l'algorithme {platform}

Réponds en JSON:
{{
    "platform": "{platform}",
    "topic": "{topic}",
    "hook": "L'accroche principale",
    "body": "Le contenu du post (300-500 caractères)",
    "cta": "Call to action",
    "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"],
    "best_time_to_post": "Meilleur moment pour publier",
    "engagement_tips": ["Astuce 1", "Astuce 2"],
    "visual_suggestion": "Description du visuel recommandé"
}}"""
        
        result = self.llm.generate_json(prompt, system, temperature=0.7)
        self._save_content(result, "post")
        return result

    def generate_article(self, topic: str, audience: str = "professionnels",
                         length: str = "moyen") -> dict:
        """Génère un article de blog complet."""
        log(f"📝 Génération d'article: {topic}")
        
        prompt = f"""Rédige un article de blog complet sur: {topic}
Public: {audience}
Longueur: {length}

Structure:
1. Titre accrocheur (SEO-friendly)
2. Introduction qui capte l'attention
3. 3-5 sections avec sous-titres
4. Conclusion avec CTA
5. Meta description (150 caractères)

Réponds en JSON avec: title, meta_description, introduction, 
sections (tableau), conclusion, cta, tags, estimated_read_time"""
        
        result = self.llm.generate_json(prompt, temperature=0.6)
        self._save_content(result, "article")
        return result

    def generate_ad_copy(self, product: str, platform: str = "meta",
                         goal: str = "conversion") -> dict:
        """Génère des copy pour publicités."""
        log(f"📢 Création de pub {platform} pour: {product}")
        
        prompt = f"""Crée 3 variations de copy publicitaire pour:
Produit: {product}
Plateforme: {platform}
Objectif: {goal}

Réponds en JSON:
{{
    "variations": [
        {{
            "headline": "Titre accrocheur",
            "primary_text": "Corps de l'annonce",
            "cta": "Bouton d'appel à l'action",
            "angle": "Angle marketing utilisé"
        }}
    ],
    "targeting_tips": ["Conseil ciblage 1"],
    "visual_suggestions": ["Description visuel 1"]
}}"""
        
        result = self.llm.generate_json(prompt, temperature=0.8)
        self._save_content(result, "ad")
        return result

    def generate_sequence(self, goal: str, steps: int = 5) -> dict:
        """Génère une séquence de contenu (email, DM, etc.)."""
        log(f"📬 Génération d'une séquence: {goal}")
        
        prompt = f"""Crée une séquence de {steps} messages pour: {goal}

Chaque message doit:
- Avoir un objectif spécifique
- Inclure un CTA
- Progresser dans la relation

Réponds en JSON avec steps (tableau), overall_strategy, timing"""
        
        result = self.llm.generate_json(prompt, temperature=0.6)
        return result

    def _save_content(self, content: dict, content_type: str):
        """Sauvegarde le contenu généré."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{content_type}-{timestamp}.json"
        filepath = CONTENT_DIR / filename
        filepath.write_text(json.dumps(content, indent=2, ensure_ascii=False))
        log(f"💾 Contenu sauvegardé: {filename}")


# ============================================
# MODULE SEO / GEO
# ============================================
class SEOEngine:
    """Optimisation SEO classique et GEO (Generative Engine Optimization)."""

    def __init__(self):
        self.llm = LLM()

    def analyze_seo(self, url: str) -> dict:
        """Analyse SEO d'un site."""
        log(f"🔍 Analyse SEO de: {url}")
        
        prompt = f"""Analyse le SEO de ce site: {url}

Génère un rapport en JSON avec:
- title_optimization (analyse du titre)
- meta_description (analyse et suggestion)
- headings_structure (structure H1/H2/H3)
- keywords (mots-clés principaux et secondaires)
- content_quality (qualité du contenu /10)
- loading_speed_issues (problèmes potentiels)
- mobile_friendliness (adaptation mobile)
- backlink_opportunities (opportunités)
- quick_wins (3 actions rapides)
- priority_actions (5 actions prioritaires)"""
        
        return self.llm.generate_json(prompt, temperature=0.3)

    def optimize_for_llm(self, content: str) -> dict:
        """Optimise du contenu pour les LLM (GEO)."""
        log(f"🤖 Optimisation GEO du contenu")
        
        system = """Tu es un expert en GEO (Generative Engine Optimization).
Tu optimises le contenu pour qu'il soit cité par les LLM 
(ChatGPT, Claude, Gemini, Perplexity, etc.)."""

        prompt = f"""Optimise ce contenu pour les LLM:

{content[:2000]}

Pour être cité par les IA, le contenu doit:
1. Répondre directement aux questions (format Q&A)
2. Inclure des données vérifiables et des chiffres
3. Utiliser un langage clair et structuré
4. Inclure des citations et références
5. Avoir une conclusion actionable

Réponds en JSON:
{{
    "original_score": 5,
    "optimized_version": "Version optimisée du contenu",
    "improvements": ["Amélioration 1", "Amélioration 2"],
    "qa_pairs": [
        {{"question": "Q1", "answer": "A1"}}
    ],
    "structured_data_suggestion": "Schéma JSON-LD recommandé",
    "citation_probability": 7.5,
    "key_changes": ["Changement 1"]
}}"""
        
        return self.llm.generate_json(prompt, system, temperature=0.3)

    def generate_llm_content(self, topic: str, target_keywords: list = None) -> dict:
        """Génère du contenu optimisé pour les LLM."""
        keywords = target_keywords or []
        kw_text = ", ".join(keywords) if keywords else "sujet principal"
        
        log(f"📝 Contenu optimisé GEO: {topic}")
        
        prompt = f"""Génère un article de blog optimisé pour les LLM.
Sujet: {topic}
Mots-clés: {kw_text}

Le contenu doit être structuré pour répondre aux questions 
que les utilisateurs posent aux IA (ChatGPT, Claude, Gemini).

Inclus:
- Une réponse directe à la question principale (featured snippet)
- Des sous-questions/réponses structurées
- Des données chiffrées
- Un schéma FAQ JSON-LD

Réponds en JSON avec le contenu complet et les métadonnées SEO."""

        result = self.llm.generate_json(prompt, temperature=0.4)
        self._save_content(topic, result)
        return result

    def _save_content(self, topic: str, content: dict):
        filename = re.sub(r'[^a-z0-9]', '_', topic.lower())[:30]
        filepath = CONTENT_DIR / f"geo-{filename}.json"
        filepath.write_text(json.dumps(content, indent=2, ensure_ascii=False))


# ============================================
# MODULE CAMPAGNES
# ============================================
class CampaignEngine:
    """Gestion de campagnes marketing."""

    def __init__(self):
        self.llm = LLM()

    def plan_campaign(self, product: str, budget: float = 1000,
                      duration_days: int = 30, target: str = None) -> dict:
        """Planifie une campagne marketing complète."""
        log(f"📋 Planification campagne: {product} ({budget}€)")

        prompt = f"""Planifie une campagne marketing:
Produit: {product}
Budget: {budget}€
Durée: {duration_days} jours
Cible: {target or 'À définir'}

Réponds en JSON avec:
- campaign_name, objective, target_audience
- channels (tableau avec priorité et budget allocation)
- timeline (phase 1/2/3 avec dates et actions)
- content_plan (10 pièces de contenu à créer)
- kpi_targets (objectifs chiffrés)
- budget_distribution (répartition détaillée)
- risk_management (risques et mitigations)
- success_criteria (critères de succès)"""
        
        result = self.llm.generate_json(prompt, temperature=0.5)
        self._save_campaign(product, result)
        return result

    def analyze_performance(self, campaign_data: dict = None) -> dict:
        """Analyse les performances d'une campagne."""
        prompt = f"""Analyse ces données de campagne et recommande des optimisations:
{campaign_data or 'Campagne standard'}

Réponds en JSON avec:
- performance_score, strengths, weaknesses
- optimization_recommendations (5 actions)
- budget_reallocation_suggestions
- a_b_test_ideas (3 idées de tests)"""
        
        return self.llm.generate_json(prompt, temperature=0.4)

    def _save_campaign(self, product: str, campaign: dict):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = re.sub(r'[^a-z0-9]', '_', product.lower())[:20]
        filepath = CAMPAIGNS_DIR / f"campaign-{filename}-{timestamp}.json"
        filepath.write_text(json.dumps(campaign, indent=2, ensure_ascii=False))
        log(f"💾 Campagne sauvegardée: {filepath.name}")


# ============================================
# MODULE DASHBOARD & RAPPORTS
# ============================================
class Dashboard:
    """Tableau de bord marketing."""

    @staticmethod
    def show():
        """Affiche le dashboard complet."""
        print(f"""
{Colors.BOLD}{Colors.CYAN}╔═══════════════════════════════════════╗
║    📈 MARKETING AGENT - DASHBOARD  ║
╚═══════════════════════════════════════╝{Colors.NC}
""")
        
        # Contenu généré
        posts = list(CONTENT_DIR.glob("post-*.json"))
        articles = list(CONTENT_DIR.glob("article-*.json"))
        ads = list(CONTENT_DIR.glob("ad-*.json"))
        geo = list(CONTENT_DIR.glob("geo-*.json"))
        strategies = list(CONTENT_DIR.glob("strategy-*.json"))
        
        print(f"{Colors.BOLD}📊 STATISTIQUES{Colors.NC}")
        print(f"   📝 Posts générés:     {len(posts)}")
        print(f"   📄 Articles:          {len(articles)}")
        print(f"   📢 Copies pub:        {len(ads)}")
        print(f"   🤖 Contenu GEO:       {len(geo)}")
        print(f"   🎯 Stratégies:        {len(strategies)}")
        
        # Campagnes
        campaigns = list(CAMPAIGNS_DIR.glob("*.json"))
        print(f"   📋 Campagnes:         {len(campaigns)}")
        
        # Dernières publications
        all_content = list(CONTENT_DIR.glob("*.json"))
        if all_content:
            all_content.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            print(f"\n{Colors.BOLD}🕐 DERNIERS CONTENUS{Colors.NC}")
            for f in all_content[:5]:
                created = datetime.fromtimestamp(f.stat().st_mtime)
                print(f"   📄 {f.stem:45} {created.strftime('%d/%m %H:%M')}")
        
        # Actions rapides
        print(f"\n{Colors.BOLD}⚡ ACTIONS RAPIDES{Colors.NC}")
        print(f"   python3 marketing-agent.py content \"Sujet d'article\"")
        print(f"   python3 marketing-agent.py social \"Post LinkedIn\"")
        print(f"   python3 marketing-agent.py campaign --budget 500")
        print(f"   python3 marketing-agent.py geo \"Optimise mon site\"")

    @staticmethod
    def generate_report(output: str = "marketing-report.html") -> str:
        """Génère un rapport HTML complet."""
        posts = list(CONTENT_DIR.glob("post-*.json"))
        campaigns = list(CAMPAIGNS_DIR.glob("*.json"))
        
        # Préparer les lignes du tableau hors de l'f-string pour éviter les backslashes
        table_rows = ""
        recent_files = sorted(
            list(CONTENT_DIR.glob('*.json')),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:10]
        for f in recent_files:
            date_str = datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m %H:%M")
            table_rows += f'<tr><td>{f.stem}</td><td>{date_str}</td></tr>'
        
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Rapport Marketing - AI Factory</title>
<style>
    body {{ font-family: -apple-system, sans-serif; background: #0f172a; color: #e2e8f0; max-width: 1000px; margin: 0 auto; padding: 20px; }}
    h1, h2 {{ color: #38bdf8; }}
    .card {{ background: #1e293b; border-radius: 12px; padding: 20px; margin: 15px 0; border: 1px solid #334155; }}
    .stat {{ font-size: 2em; font-weight: bold; color: #22c55e; }}
    table {{ width: 100%; border-collapse: collapse; }}
    td, th {{ padding: 10px; text-align: left; border-bottom: 1px solid #334155; }}
</style></head>
<body>
    <h1>📈 Rapport Marketing - AI Factory</h1>
    <p>Généré le {now_str}</p>
    
    <div class="card">
        <h2>📊 Statistiques</h2>
        <table>
            <tr><td>Posts générés</td><td class="stat">{len(posts)}</td></tr>
            <tr><td>Campagnes</td><td class="stat">{len(campaigns)}</td></tr>
        </table>
    </div>
    
    <div class="card">
        <h2>🕐 Derniers contenus</h2>
        <table>
        {table_rows}
        </table>
    </div>
    
    <p style="text-align: center; color: #64748b; margin-top: 40px;">
        Généré par AI Factory - Marketing Agent
    </p>
</body></html>"""
        
        Path(output).write_text(html, encoding="utf-8")
        log(f"📊 Rapport généré: {output}")
        return output


# ============================================
# ORCHESTRATEUR GLOBAL
# ============================================
class MarketingAgent:
    """Point d'entrée unique pour toutes les opérations marketing."""

    def __init__(self):
        self.strategy = StrategyEngine()
        self.content = ContentEngine()
        self.seo = SEOEngine()
        self.campaigns = CampaignEngine()

    def full_audit(self, product: str) -> dict:
        """Audit marketing complet."""
        log(f"\n{'='*60}")
        log(f"📊 AUDIT MARKETING COMPLET: {product}")
        log(f"{'='*60}")
        
        # 1. Analyse du marché
        market = self.strategy.analyze_market(product)
        
        # 2. Stratégie
        strategy = self.strategy.create_strategy(product)
        
        # 3. Contenu initial
        post = self.content.generate_post(
            f"Nous lançons {product}",
            "linkedin", "professionnel"
        )
        
        # 4. Recommandations GEO
        geo = self.seo.optimize_for_llm(
            f"Découvrez {product} - la solution idéale pour..."
        )
        
        # 5. Plan campagne
        campaign = self.campaigns.plan_campaign(product)
        
        return {
            "market_analysis": market,
            "strategy": strategy,
            "sample_content": post,
            "geo_recommendations": geo,
            "campaign_plan": campaign,
            "generated_at": datetime.now().isoformat()
        }


# ============================================
# CLI
# ============================================
def main():
    parser = argparse.ArgumentParser(
        description="📈 AI FACTORY - Marketing Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python3 marketing-agent.py strategy "Mon SaaS de gestion"
  python3 marketing-agent.py content "IA pour les PME"
  python3 marketing-agent.py social "Post sur mon nouveau produit"
  python3 marketing-agent.py ad "Formation en ligne"
  python3 marketing-agent.py seo "https://monsite.com"
  python3 marketing-agent.py geo "Optimise ma page d'accueil"
  python3 marketing-agent.py campaign --budget 1000
  python3 marketing-agent.py dashboard
  python3 marketing-agent.py audit "Mon produit"
        """
    )
    
    subparsers = parser.add_subparsers(dest="command")
    
    # Stratégie
    p_strat = subparsers.add_parser("strategy", help="Analyse de marché et stratégie")
    p_strat.add_argument("product", help="Produit/service à analyser")
    p_strat.add_argument("--goal", default="notoriété", help="Objectif marketing")
    p_strat.add_argument("--budget", default="1000€/mois", help="Budget mensuel")
    
    # Contenu
    p_content = subparsers.add_parser("content", aliases=["article"],
                                       help="Générer un article")
    p_content.add_argument("topic", help="Sujet de l'article")
    p_content.add_argument("--audience", default="professionnels",
                          help="Public cible")
    
    # Post social
    p_social = subparsers.add_parser("social", aliases=["post"],
                                      help="Générer un post social")
    p_social.add_argument("topic", help="Sujet du post")
    p_social.add_argument("--platform", "-p", default="linkedin",
                         choices=["linkedin", "twitter", "instagram", "facebook"])
    p_social.add_argument("--tone", "-t", default="professionnel",
                         choices=["professionnel", "décontracté", "inspirant", "humour"])
    
    # Ad copy
    p_ad = subparsers.add_parser("ad", help="Générer des copies pub")
    p_ad.add_argument("product", help="Produit à promouvoir")
    p_ad.add_argument("--platform", default="meta",
                     choices=["meta", "google", "linkedin", "tiktok"])
    
    # SEO
    p_seo = subparsers.add_parser("seo", help="Analyse SEO")
    p_seo.add_argument("url", help="URL à analyser")
    
    # GEO
    p_geo = subparsers.add_parser("geo", help="Optimisation GEO (LLM)")
    p_geo.add_argument("content", help="Contenu à optimiser")
    
    # Campagne
    p_camp = subparsers.add_parser("campaign", help="Planifier une campagne")
    p_camp.add_argument("product", nargs="?", default="mon produit",
                       help="Produit de la campagne")
    p_camp.add_argument("--budget", type=float, default=1000, help="Budget total")
    p_camp.add_argument("--days", type=int, default=30, help="Durée en jours")
    p_camp.add_argument("--target", help="Cible")
    
    # Dashboard
    subparsers.add_parser("dashboard", aliases=["dash", "report"],
                          help="Afficher le dashboard")
    
    # Audit complet
    p_audit = subparsers.add_parser("audit", help="Audit marketing complet")
    p_audit.add_argument("product", help="Produit à auditer")
    
    args = parser.parse_args()
    
    agent = MarketingAgent()
    
    if args.command in ("strategy",):
        result = agent.strategy.analyze_market(args.product)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command in ("content", "article"):
        result = agent.content.generate_article(args.topic, args.audience)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command in ("social", "post"):
        result = agent.content.generate_post(args.topic, args.platform, args.tone)
        print(f"\n📝 Post {args.platform}:")
        print(f"\n{Colors.BOLD}Accroche:{Colors.NC}")
        print(f"   {result.get('hook', 'N/A')}")
        print(f"\n{Colors.BOLD}Corps:{Colors.NC}")
        print(f"   {result.get('body', 'N/A')[:500]}")
        print(f"\n{Colors.BOLD}CTA:{Colors.NC}")
        print(f"   {result.get('cta', 'N/A')}")
        if result.get('hashtags'):
            print(f"\n🏷️  {' '.join(result['hashtags'])}")
    
    elif args.command in ("ad",):
        result = agent.content.generate_ad_copy(args.product, args.platform)
        print(f"\n📢 3 variations de pub ({args.platform}):")
        for i, v in enumerate(result.get("variations", []), 1):
            print(f"\n{Colors.BOLD}Variation {i}:{Colors.NC}")
            print(f"   Titre: {v.get('headline', 'N/A')}")
            print(f"   Corps: {v.get('primary_text', 'N/A')[:200]}")
            print(f"   CTA: {v.get('cta', 'N/A')}")
    
    elif args.command in ("seo",):
        result = agent.seo.analyze_seo(args.url)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command in ("geo",):
        result = agent.seo.optimize_for_llm(args.content)
        print(f"\n🤖 Optimisation GEO:")
        print(f"   Score original: {result.get('original_score', 'N/A')}/10")
        for imp in result.get("improvements", []):
            print(f"   ✅ {imp}")
    
    elif args.command in ("campaign",):
        result = agent.campaigns.plan_campaign(
            args.product, args.budget, args.days, args.target
        )
        print(f"\n📋 Campagne planifiée:")
        print(f"   Objectif: {result.get('objective', 'N/A')}")
        print(f"   Budget: {result.get('budget_distribution', {})}")
    
    elif args.command in ("dashboard", "dash", "report"):
        Dashboard.show()
        if args.command == "report":
            Dashboard.generate_report()
    
    elif args.command in ("audit",):
        result = agent.full_audit(args.product)
        print(f"\n✅ Audit terminé!")
        print(f"   Voir les fichiers dans: {CONTENT_DIR}")
    
    else:
        parser.print_help()
        print(f"""
{Colors.BOLD}🏁 Pour démarrer rapidement:{Colors.NC}
  python3 marketing-agent.py strategy "Mon produit"          # Analyse marché
  python3 marketing-agent.py social "Nouveau lancement"      # Post LinkedIn
  python3 marketing-agent.py ad "Formation marketing"        # Copies pub
  python3 marketing-agent.py campaign --budget 500           # Plan campagne
  python3 marketing-agent.py dashboard                       # Tableau de bord
  python3 marketing-agent.py audit "Mon SaaS"                # Audit complet
        """)


if __name__ == "__main__":
    main()
