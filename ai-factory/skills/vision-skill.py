#!/usr/bin/env python3
"""
============================================
AI FACTORY - Vision Skill
============================================
Analyse d'images via LLaVA/Ollama.
Reconnaissance de contenu, visages, style,
et scoring visuel automatisé.

Usage:
    python3 vision-skill.py analyse photo.jpg
    python3 vision-skill.py batch ./images/
    python3 vision-skill.py watch ./dossier-surveille/
    python3 vision-skill.py compare image1.jpg image2.jpg

Prérequis: Ollama avec modèle LLaVA chargé
    docker compose exec ollama ollama pull llava:7b
============================================
"""

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ============================================
# CONFIGURATION
# ============================================
OLLAMA_API = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
VISION_MODEL = os.getenv("VISION_MODEL", "llava:7b")
SCORE_MODEL = os.getenv("SCORE_MODEL", "llava:7b")

# Extensions d'images supportées
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"}


class Colors:
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'


def log(msg: str, color: str = Colors.GREEN):
    print(f"{color}[{datetime.now().strftime('%H:%M:%S')}]{Colors.NC} {msg}")


# ============================================
# MOTEUR DE VISION
# ============================================
class VisionEngine:
    """Interface avec LLaVA via Ollama pour l'analyse d'images."""

    def __init__(self, model: str = VISION_MODEL):
        self.model = model
        self.api_url = f"{OLLAMA_API}/api/generate"

    def _image_to_base64(self, image_path: str) -> str:
        """Convertit une image en base64."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def ask(self, image_path: str, prompt: str, temperature: float = 0.3) -> str:
        """
        Pose une question sur une image via LLaVA.

        Args:
            image_path: Chemin de l'image
            prompt: Question à poser sur l'image
            temperature: Créativité de la réponse (0.0 - 1.0)

        Returns:
            str: Réponse du modèle
        """
        import httpx
        
        image_b64 = self._image_to_base64(image_path)
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 1024
            },
            "images": [image_b64]
        }
        
        try:
            with httpx.Client(timeout=120) as client:
                r = client.post(self.api_url, json=payload)
                if r.status_code == 200:
                    return r.json().get("response", "")
                else:
                    log(f"⚠️ Erreur API: {r.status_code}", Colors.YELLOW)
                    return ""
        except Exception as e:
            log(f"❌ Erreur: {e}", Colors.RED)
            return ""

    def describe(self, image_path: str) -> dict:
        """Description complète d'une image."""
        prompt = """Décris cette image en détail. Inclus:
1. Le sujet principal
2. Les couleurs dominantes
3. Le style visuel (professionnel, amateur, artistique)
4. La qualité de l'image (net, flou, bien éclairé)
5. Tout texte visible
Réponds en JSON."""
        
        response = self.ask(image_path, prompt, temperature=0.2)
        
        # Essayer d'extraire le JSON
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        
        return {
            "description": response[:500],
            "format": "texte"
        }

    def score_aesthetic(self, image_path: str) -> dict:
        """
        Note l'esthétique d'une image sur 10.
        Utile pour trier des photos (Instagram, etc.).
        """
        prompt = """Analyse cette image et note-la sur une échelle de 1 à 10 selon:
- Qualité visuelle générale (netteté, éclairage, composition)
- Style et esthétique
- Attrait visuel

Réponds UNIQUEMENT au format JSON:
{
    "score": 7.5,
    "quality": 8,
    "style": 7,
    "composition": 7.5,
    "lighting": 8,
    "details": "Belle composition, couleurs harmonieuses, léger flou d'arrière-plan",
    "tags": ["portrait", "professionnel", "bien éclairé"]
}"""
        
        response = self.ask(image_path, prompt, temperature=0.2)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        
        return {"score": 5.0, "details": response[:200]}

    def detect_faces(self, image_path: str) -> list:
        """Détecte et analyse les visages dans une image."""
        prompt = """Analyse cette image et liste TOUS les visages visibles.
Pour chaque visage, indique:
- Nombre approximatif de personnes
- Expression dominante (souriant, sérieux, etc.)
- Qualité de la photo pour un portrait

Réponds UNIQUEMENT au format JSON:
{
    "face_count": 2,
    "faces": [
        {"expression": "souriant", "position": "centre", "quality": "bonne"},
        {"expression": "neutre", "position": "gauche", "quality": "moyenne"}
    ],
    "best_quality": "centre"
}"""
        
        response = self.ask(image_path, prompt, temperature=0.2)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        
        return {"face_count": 0, "faces": []}

    def classify(self, image_path: str, categories: list = None) -> dict:
        """
        Classifie une image dans des catégories.

        Args:
            image_path: Chemin de l'image
            categories: Liste de catégories possibles
        """
        cats = categories or [
            "portrait", "paysage", "produit", "événement",
            "selfie", "art", "document", "mème", "autre"
        ]
        
        prompt = f"""Classifie cette image dans l'une de ces catégories: {', '.join(cats)}.
Réponds UNIQUEMENT au format JSON:
{{
    "category": "portrait",
    "confidence": 0.85,
    "subcategory": "portrait professionnel",
    "tags": ["tag1", "tag2"],
    "has_text": false,
    "has_logo": false
}}"""
        
        response = self.ask(image_path, prompt, temperature=0.1)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass
        
        return {"category": "inconnu", "confidence": 0}


# ============================================
# TRAITEUR D'IMAGES
# ============================================
class ImageProcessor:
    """Traite des images par lots avec le moteur de vision."""

    def __init__(self):
        self.engine = VisionEngine()
        self.results = []

    def find_images(self, path: str, recursive: bool = True) -> list:
        """Trouve toutes les images dans un dossier."""
        p = Path(path)
        if p.is_file():
            return [p] if p.suffix.lower() in IMAGE_EXTENSIONS else []
        
        pattern = "**/*" if recursive else "*"
        images = []
        for f in p.glob(pattern):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                images.append(f)
        return sorted(images)

    def process_single(self, image_path: str, analyse: str = "full") -> dict:
        """Analyse une seule image."""
        log(f"🔍 Analyse: {Path(image_path).name}")
        
        result = {
            "file": image_path,
            "filename": Path(image_path).name,
            "size": f"{Path(image_path).stat().st_size / 1024:.1f}KB",
            "timestamp": datetime.now().isoformat()
        }
        
        if analyse in ("full", "describe"):
            result["description"] = self.engine.describe(image_path)
        
        if analyse in ("full", "score"):
            result["aesthetic"] = self.engine.score_aesthetic(image_path)
        
        if analyse in ("full", "faces"):
            result["faces"] = self.engine.detect_faces(image_path)
        
        if analyse in ("full", "classify"):
            result["classification"] = self.engine.classify(image_path)
        
        self.results.append(result)
        return result

    def process_batch(self, directory: str, analyse: str = "score") -> list:
        """Analyse toutes les images d'un dossier."""
        images = self.find_images(directory)
        log(f"📂 {len(images)} images trouvées dans {directory}")
        
        results = []
        for i, img in enumerate(images, 1):
            log(f"  [{i}/{len(images)}] {img.name}")
            result = self.process_single(str(img), analyse)
            results.append(result)
            
            # Pause pour ne pas surcharger Ollama
            if i < len(images):
                time.sleep(1)
        
        # Trier par score esthétique
        scored = [r for r in results if "aesthetic" in r]
        scored.sort(key=lambda x: x.get("aesthetic", {}).get("score", 0), reverse=True)
        
        self.results = scored
        return scored

    def watch_directory(self, directory: str, analyse: str = "score"):
        """Surveille un dossier et analyse les nouvelles images."""
        import threading
        
        watched = set()
        log(f"👁️ Surveillance de {directory} (Ctrl+C pour arrêter)")
        
        try:
            while True:
                images = self.find_images(directory)
                
                for img in images:
                    if str(img) not in watched:
                        log(f"🆕 Nouvelle image: {img.name}")
                        result = self.process_single(str(img), analyse)
                        watched.add(str(img))
                        
                        # Afficher le score si disponible
                        if "aesthetic" in result:
                            score = result["aesthetic"].get("score", "N/A")
                            log(f"   Score: {score}/10")
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            log("👋 Arrêt de la surveillance")

    def export_results(self, output: str = "vision-results.json"):
        """Exporte les résultats en JSON."""
        output_path = Path(output)
        output_path.write_text(json.dumps(self.results, indent=2, ensure_ascii=False))
        log(f"💾 Résultats exportés: {output_path}")

    def generate_report(self, output: str = "vision-report.html"):
        """Génère un rapport HTML des analyses."""
        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Rapport Vision - AI Factory</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background: #0f172a; color: #e2e8f0; }}
        h1 {{ color: #38bdf8; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 20px; margin: 15px 0; border: 1px solid #334155; }}
        .score {{ font-size: 2em; font-weight: bold; color: #22c55e; }}
        .tags {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .tag {{ background: #334155; padding: 4px 12px; border-radius: 20px; font-size: 0.8em; }}
        img {{ max-width: 300px; border-radius: 8px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; }}
    </style>
</head>
<body>
    <h1>👁️ Rapport Vision - AI Factory</h1>
    <p>Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
    <p>{len(self.results)} images analysées</p>
    <div class="grid">"""
        
        for r in self.results:
            score = r.get("aesthetic", {}).get("score", "N/A")
            tags = r.get("aesthetic", {}).get("tags", [])
            desc = r.get("description", {}).get("description", "")[:200] if isinstance(r.get("description"), dict) else ""
            
            html += f"""
        <div class="card">
            <h3>{r['filename']}</h3>
            <p class="score">{score}/10</p>
            <div class="tags">{''.join(f'<span class="tag">{t}</span>' for t in tags[:5])}</div>
            <p>{desc}</p>
            <small>{r.get('size', '')}</small>
        </div>"""
        
        html += """
    </div>
</body>
</html>"""
        
        Path(output).write_text(html, encoding="utf-8")
        log(f"📊 Rapport HTML généré: {output}")


# ============================================
# COMPARATEUR D'IMAGES
# ============================================
class ImageComparator:
    """Compare deux images et mesure leur similarité."""

    def __init__(self):
        self.engine = VisionEngine()

    def compare(self, img1: str, img2: str) -> dict:
        """Compare deux images."""
        log(f"🔄 Comparaison: {Path(img1).name} ↔ {Path(img2).name}")
        
        prompt = """Compare ces deux images et évalue leur similarité.
Réponds UNIQUEMENT au format JSON:
{
    "similarity_score": 0.75,
    "same_subject": true,
    "same_style": false,
    "differences": ["L'image 1 est en couleur, l'image 2 est en noir et blanc"],
    "which_is_better": 1,
    "better_reason": "Meilleure composition et éclairage"
}"""
        
        response1 = self.engine.ask(img1, "Décris cette image en 1 phrase.", 0.2)
        response2 = self.engine.ask(img2, "Décris cette image en 1 phrase.", 0.2)
        
        return {
            "image1": Path(img1).name,
            "image2": Path(img2).name,
            "description1": response1[:200],
            "description2": response2[:200],
            "comparison": "Compare les descriptions visuellement"
        }


# ============================================
# CLI
# ============================================
def main():
    parser = argparse.ArgumentParser(
        description="👁️ AI FACTORY - Vision Skill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  python3 vision-skill.py analyse photo.jpg
  python3 vision-skill.py score photo.jpg
  python3 vision-skill.py batch ./images/ --sort
  python3 vision-skill.py watch ./dossier-surveille/
  python3 vision-skill.py compare img1.jpg img2.jpg
  python3 vision-skill.py report ./images/ --output rapport.html
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commande")
    
    # Analyse simple
    p_analyse = subparsers.add_parser("analyse", help="Analyser une image")
    p_analyse.add_argument("image", help="Chemin de l'image")
    p_analyse.add_argument("--prompt", "-p", default=None, help="Question personnalisée")
    
    # Score esthétique
    p_score = subparsers.add_parser("score", help="Noter l'esthétique")
    p_score.add_argument("image", help="Chemin de l'image")
    
    # Batch
    p_batch = subparsers.add_parser("batch", help="Analyser un dossier")
    p_batch.add_argument("directory", help="Dossier d'images")
    p_batch.add_argument("--sort", "-s", action="store_true", help="Trier par score")
    p_batch.add_argument("--output", "-o", default="vision-results.json", help="Fichier de sortie")
    p_batch.add_argument("--analyse", "-a", default="score", 
                        choices=["full", "score", "describe", "faces", "classify"])
    
    # Rapport
    p_report = subparsers.add_parser("report", help="Générer un rapport")
    p_report.add_argument("directory", help="Dossier d'images")
    p_report.add_argument("--output", "-o", default="vision-report.html", help="Fichier HTML")
    
    # Watch
    p_watch = subparsers.add_parser("watch", help="Surveiller un dossier")
    p_watch.add_argument("directory", help="Dossier à surveiller")
    
    # Compare
    p_compare = subparsers.add_parser("compare", help="Comparer deux images")
    p_compare.add_argument("image1", help="Première image")
    p_compare.add_argument("image2", help="Deuxième image")
    
    args = parser.parse_args()
    
    processor = ImageProcessor()
    
    if args.command == "analyse":
        if args.prompt:
            engine = VisionEngine()
            response = engine.ask(args.image, args.prompt)
            print(f"\n{response}")
        else:
            result = processor.process_single(args.image, "full")
            print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == "score":
        engine = VisionEngine()
        score = engine.score_aesthetic(args.image)
        print(f"\n📊 Score esthétique: {score.get('score', 'N/A')}/10")
        print(f"   Qualité: {score.get('quality', 'N/A')}/10")
        print(f"   Style: {score.get('style', 'N/A')}/10")
        print(f"   Composition: {score.get('composition', 'N/A')}/10")
        print(f"   Tags: {', '.join(score.get('tags', []))}")
        print(f"   Détails: {score.get('details', '')[:200]}")
    
    elif args.command == "batch":
        results = processor.process_batch(args.directory, args.analyse)
        processor.export_results(args.output)
        
        print(f"\n📊 Top 5 des meilleurs scores:")
        for i, r in enumerate(results[:5], 1):
            score = r.get("aesthetic", {}).get("score", "N/A")
            print(f"   {i}. {r['filename']:30} → {score}/10")
    
    elif args.command == "report":
        processor.process_batch(args.directory)
        processor.generate_report(args.output)
        print(f"\n✅ Rapport généré: {args.output}")
    
    elif args.command == "watch":
        processor.watch_directory(args.directory)
    
    elif args.command == "compare":
        comparator = ImageComparator()
        result = comparator.compare(args.image1, args.image2)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    else:
        parser.print_help()
        print(f"""
{Colors.BOLD}🔍 Test rapide:{Colors.NC}
  python3 vision-skill.py score photo.jpg
  python3 vision-skill.py batch ./images/ --sort
  python3 vision-skill.py report ./images/ --output rapport.html
        """)


if __name__ == "__main__":
    main()
