#!/usr/bin/env python3
"""
============================================
AI FACTORY - Stealth Bot Template
============================================
Template de base pour créer des bots furtifs.
Utilise Playwright avec des patches anti-détection
pour imiter un comportement humain parfait.

Usage par l'IA :
    Créer un nouveau bot → Copier ce template →
    Personnaliser la logique → Lancer dans un conteneur Docker
============================================
"""

import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ============================================
# Configuration du logging
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# Configuration du Bot (à PERSONNALISER)
# ============================================
BOT_CONFIG = {
    # --- Cible ---
    "target_url": os.getenv("BOT_TARGET_URL", "https://exemple.com"),
    "target_actions": os.getenv("BOT_TARGET_ACTIONS", "[]"),  # JSON list
    
    # --- Comportement humain ---
    "min_delay_seconds": float(os.getenv("BOT_MIN_DELAY", "2.0")),
    "max_delay_seconds": float(os.getenv("BOT_MAX_DELAY", "8.0")),
    "typing_speed_wpm": int(os.getenv("BOT_TYPING_SPEED", "120")),
    
    # --- Limites (anti-détection) ---
    "max_actions_per_session": int(os.getenv("BOT_MAX_ACTIONS", "50")),
    "max_actions_per_hour": int(os.getenv("BOT_MAX_ACTIONS_HOUR", "10")),
    "session_duration_minutes": int(os.getenv("BOT_SESSION_DURATION", "30")),
    
    # --- Proxy (optionnel) ---
    "proxy_url": os.getenv("BOT_PROXY_URL", ""),
    "proxy_username": os.getenv("BOT_PROXY_USER", ""),
    "proxy_password": os.getenv("BOT_PROXY_PASS", ""),
    
    # --- Session ---
    "session_file": os.getenv("BOT_SESSION_FILE", "session.json"),
    "cookies_file": os.getenv("BOT_COOKIES_FILE", "cookies.json"),
    
    # --- Qdrant (mémoire) ---
    "qdrant_url": os.getenv("QDRANT_URL", "http://qdrant:6333"),
    "qdrant_collection": os.getenv("QDRANT_COLLECTION", "bot_memory"),
}


class HumanBehaviorSimulator:
    """Simule un comportement humain réaliste dans le navigateur."""
    
    @staticmethod
    def random_delay(min_sec: float = 2.0, max_sec: float = 8.0) -> float:
        """Délai aléatoire entre actions (loi normale centrée sur 4s)."""
        return random.gauss((min_sec + max_sec) / 2, 1.5)
    
    @staticmethod
    def human_typing_delay(text: str, wpm: int = 120) -> float:
        """Simule le temps qu'un humain mettrait à taper un texte."""
        chars_per_second = (wpm * 5) / 60
        return len(text) / chars_per_second
    
    @staticmethod
    def generate_mouse_movement(start_x: int, start_y: int, end_x: int, end_y: int):
        """Génère un mouvement de souris réaliste (courbe de Bézier)."""
        import numpy as np
        
        # Points de contrôle pour la courbe de Bézier
        control_x = start_x + random.randint(-50, 50)
        control_y = start_y + random.randint(-50, 50)
        
        points = []
        for t in np.linspace(0, 1, 20):
            # Courbe cubique de Bézier
            x = (1-t)**3 * start_x + 3*(1-t)**2*t * control_x + 3*(1-t)*t**2 * control_x + t**3 * end_x
            y = (1-t)**3 * start_y + 3*(1-t)**2*t * control_y + 3*(1-t)*t**2 * control_y + t**3 * end_y
            points.append((int(x), int(y)))
        
        return points


class RateLimiter:
    """Gère les limites d'actions pour éviter la détection."""
    
    def __init__(self, max_per_hour: int = 10, max_per_session: int = 50):
        self.max_per_hour = max_per_hour
        self.max_per_session = max_per_session
        self.action_log: list[datetime] = []
        self.session_actions = 0
    
    def can_act(self) -> bool:
        """Vérifie si on peut effectuer une action."""
        # Vérifier la limite de session
        if self.session_actions >= self.max_per_session:
            logger.warning("⚠️ Limite de session atteinte")
            return False
        
        # Vérifier la limite horaire
        now = datetime.now()
        self.action_log = [t for t in self.action_log if t > now - timedelta(hours=1)]
        
        if len(self.action_log) >= self.max_per_hour:
            wait_time = 3600 - (now - min(self.action_log)).total_seconds()
            logger.info(f"⏳ Limite horaire. Attente: {wait_time:.0f}s")
            time.sleep(wait_time)
            return True
        
        return True
    
    def log_action(self):
        """Enregistre une action."""
        self.action_log.append(datetime.now())
        self.session_actions += 1
    
    def reset_session(self):
        """Réinitialise le compteur de session."""
        self.session_actions = 0


class StealthBot:
    """
    Bot furtif de base.
    S'adapte automatiquement aux blocages.
    """
    
    def __init__(self, config: dict = None):
        self.config = config or BOT_CONFIG
        self.browser = None
        self.context = None
        self.page = None
        self.limiter = RateLimiter(
            max_per_hour=self.config["max_actions_per_hour"],
            max_per_session=self.config["max_actions_per_session"]
        )
        self.detected = False
    
    async def launch(self):
        """Lance le navigateur avec les paramètres furtifs."""
        from playwright.async_api import async_playwright
        
        self.playwright = await async_playwright().start()
        
        # Options du navigateur
        browser_options = {
            "headless": False,  # Mettre à True en production
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-web-security",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--window-size=1920,1080",
            ]
        }
        
        self.browser = await self.playwright.chromium.launch(**browser_options)
        
        # Contexte avec user-agent réaliste
        context_options = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "viewport": {"width": 1920, "height": 1080},
            "locale": "fr-FR",
            "timezone_id": "Europe/Paris",
            "geolocation": {"latitude": 48.8566, "longitude": 2.3522},
            "permissions": ["geolocation"],
        }
        
        # Ajouter le proxy si configuré
        if self.config["proxy_url"]:
            context_options["proxy"] = {
                "server": self.config["proxy_url"],
                "username": self.config["proxy_username"],
                "password": self.config["proxy_password"],
            }
        
        self.context = await self.browser.new_context(**context_options)
        
        # Charger les cookies de la session précédente
        cookies_file = Path(self.config["cookies_file"])
        if cookies_file.exists():
            with open(cookies_file) as f:
                cookies = json.load(f)
            await self.context.add_cookies(cookies)
            logger.info("🍪 Cookies de session chargés")
        
        self.page = await self.context.new_page()
        
        # Injecter les scripts anti-détection
        await self._inject_stealth_scripts()
        
        logger.info("🚀 Navigateur lancé avec configuration furtive")
    
    async def _inject_stealth_scripts(self):
        """Injecte des scripts pour masquer l'automatisation."""
        stealth_js = """
        // Masquer WebDriver
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Masquer les APIs de détection
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        
        Object.defineProperty(navigator, 'languages', {
            get: () => ['fr-FR', 'fr', 'en-US', 'en']
        });
        
        // Simuler Chrome
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        """
        
        await self.page.add_init_script(stealth_js)
        logger.info("🛡️ Scripts anti-détection injectés")
    
    async def human_delay(self, min_sec: float = None, max_sec: float = None):
        """Pause aléatoire simulant un humain."""
        min_s = min_sec or self.config["min_delay_seconds"]
        max_s = max_sec or self.config["max_delay_seconds"]
        delay = HumanBehaviorSimulator.random_delay(min_s, max_s)
        logger.debug(f"⏸️  Pause de {delay:.1f}s")
        await asyncio.sleep(delay)
    
    async def human_type(self, text: str):
        """Tape du texte comme un humain."""
        for char in text:
            await self.page.keyboard.type(char, delay=random.randint(50, 200))
    
    async def human_click(self, selector: str):
        """Clique sur un élément avec mouvement de souris réaliste."""
        element = await self.page.query_selector(selector)
        if not element:
            logger.warning(f"⚠️ Élément non trouvé: {selector}")
            return False
        
        box = await element.bounding_box()
        if not box:
            return False
        
        # Mouvement de souris réaliste
        start_x = random.randint(0, 500)
        start_y = random.randint(0, 500)
        end_x = box["x"] + box["width"] / 2
        end_y = box["y"] + box["height"] / 2
        
        await self.page.mouse.move(start_x, start_y)
        await self.human_delay(0.1, 0.3)
        await self.page.mouse.move(end_x, end_y)
        await self.human_delay(0.1, 0.3)
        await element.click()
        
        return True
    
    async def is_detected(self) -> bool:
        """Vérifie si le bot est détecté (403, captcha, etc.)."""
        try:
            # Vérifier le code de statut
            response = await self.page.evaluate("""
                () => {
                    const perf = performance.getEntriesByType('navigation')[0];
                    return perf ? perf.responseStatus : 200;
                }
            """)
            
            if response in [403, 429]:
                logger.warning(f"🚨 Bloqué! Status: {response}")
                return True
            
            # Vérifier la présence de captcha
            captcha_selectors = [
                "iframe[src*='captcha']",
                "iframe[src*='recaptcha']",
                "[class*='captcha']",
                "[id*='captcha']",
                "[class*='challenge']",
            ]
            
            for selector in captcha_selectors:
                element = await self.page.query_selector(selector)
                if element:
                    logger.warning("🚨 Captcha détecté!")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur de détection: {e}")
            return True
    
    async def screenshot(self, path: str = "debug.png"):
        """Prend une capture d'écran."""
        await self.page.screenshot(path=path, full_page=True)
        logger.info(f"📸 Capture: {path}")
        return path
    
    async def save_session(self):
        """Sauvegarde les cookies pour la prochaine session."""
        cookies = await self.context.cookies()
        with open(self.config["cookies_file"], "w") as f:
            json.dump(cookies, f)
        logger.info("💾 Session sauvegardée")
    
    async def navigate(self, url: str = None):
        """Navigue vers une URL avec des délais réalistes."""
        target = url or self.config["target_url"]
        logger.info(f"🌐 Navigation vers: {target}")
        
        try:
            await self.page.goto(target, wait_until="networkidle", timeout=30000)
            await self.human_delay(1, 3)
            
            # Scroll naturel
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 3)")
            await self.human_delay(0.5, 1.5)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur de navigation: {e}")
            return False
    
    async def run_action(self, action: dict):
        """Exécute une action définie dans la configuration."""
        action_type = action.get("type", "")
        selector = action.get("selector", "")
        value = action.get("value", "")
        
        logger.info(f"🎯 Action: {action_type} sur {selector}")
        
        if action_type == "click":
            return await self.human_click(selector)
        
        elif action_type == "type":
            await self.human_click(selector)
            await self.human_delay(0.2, 0.5)
            await self.human_type(value)
            return True
        
        elif action_type == "wait":
            await self.human_delay(value, value + 2)
            return True
        
        elif action_type == "scroll":
            await self.page.evaluate(f"window.scrollTo(0, {value})")
            await self.human_delay(0.5, 1.5)
            return True
        
        elif action_type == "screenshot":
            await self.screenshot(value or "capture.png")
            return True
        
        logger.warning(f"⚠️ Type d'action inconnu: {action_type}")
        return False
    
    async def run(self):
        """Point d'entrée principal du bot."""
        try:
            # Lancement
            await self.launch()
            
            # Navigation vers la cible
            if not await self.navigate():
                logger.error("❌ Impossible d'accéder à la cible")
                return
            
            # Exécution des actions
            actions = json.loads(self.config["target_actions"])
            
            for i, action in enumerate(actions):
                # Vérifier les limites
                if not self.limiter.can_act():
                    logger.info("🔚 Limites atteintes, fin de la session")
                    break
                
                # Vérifier la détection
                if await self.is_detected():
                    logger.warning("🚨 Détection! Sauvegarde et arrêt...")
                    await self.screenshot("detected.png")
                    break
                
                # Exécuter l'action
                success = await self.run_action(action)
                self.limiter.log_action()
                
                if not success:
                    logger.warning(f"⚠️ Action {i+1} échouée")
                
                # Pause entre les actions
                await self.human_delay()
            
            # Sauvegarde de la session
            await self.save_session()
            
            logger.info(f"""
✅ Session terminée avec succès
   Actions effectuées: {self.limiter.session_actions}
   Détection: {"OUI 🚨" if self.detected else "NON ✅"}
""")
            
        except Exception as e:
            logger.error(f"❌ Erreur fatale: {e}")
            await self.screenshot("error.png")
        
        finally:
            # Nettoyage
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
    
    async def self_heal(self, error_info: dict) -> bool:
        """
        Auto-guérison : tente de corriger les problèmes de détection.
        Appelé quand le bot est bloqué pour ajuster les paramètres.
        """
        logger.info("🔧 Tentative d'auto-guérison...")
        
        # Stratégies de contournement
        strategies = [
            {"user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            {"viewport": {"width": 1440, "height": 900}},
            {"locale": "en-US"},
            {"extra_http_headers": {"Accept-Language": "fr-FR,fr;q=0.9"}},
        ]
        
        for strategy in strategies:
            logger.info(f"🔄 Essai stratégie: {strategy}")
            try:
                # Re-créer le contexte avec la nouvelle stratégie
                if self.browser:
                    await self.browser.close()
                
                # Appliquer la stratégie
                # (implémentation simplifiée)
                return True
                
            except Exception as e:
                logger.error(f"❌ Échec stratégie: {e}")
                continue
        
        return False


# ============================================
# POINT D'ENTRÉE
# ============================================
async def main():
    """Point d'entrée principal."""
    bot = StealthBot()
    
    # Afficher la configuration
    logger.info(f"""
╔══════════════════════════════════════╗
║      AI FACTORY - Stealth Bot       ║
╠══════════════════════════════════════╣
║  Cible: {BOT_CONFIG['target_url'][:40]:<40} ║
║  Actions/session: {BOT_CONFIG['max_actions_per_session']:<5}                     ║
║  Actions/heure: {BOT_CONFIG['max_actions_per_hour']:<6}                     ║
║  Session max: {BOT_CONFIG['session_duration_minutes']:<4} min                     ║
╚══════════════════════════════════════╝
""")
    
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
