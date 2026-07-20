"""
AkyelIA - Configuration multi-LLM
Tous les meilleurs modèles du marché !
"""
import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMProviderConfig:
    """Configuration for an LLM provider."""
    name: str
    display_name: str
    api_key_env: str
    base_url: str
    default_model: str
    models: list[str]
    api_type: str  # "openai", "anthropic", "gemini", "ollama"
    requires_key: bool = True
    icon: str = "🤖"
    description: str = ""
    setup_url: str = ""


@dataclass
class Config:
    """Main application configuration."""
    host: str = "0.0.0.0"
    port: int = int(os.getenv("PORT", "7777"))
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    secret_key: str = os.getenv("SECRET_KEY", "akyelia-secret-key")
    default_provider: str = os.getenv("DEFAULT_PROVIDER", "omniroute")
    db_path: str = os.getenv("DB_PATH", "akyelia.db")
    api_keys_file: str = os.getenv("API_KEYS_FILE", "api_keys.json")
    max_history: int = 100

    providers: dict[str, LLMProviderConfig] = field(default_factory=lambda: {
        # 🌟 OmniRoute - Routeur AI 100% gratuit, 85+ modèles (Claude Opus 4.6, GPT-5, Gemini 3 Pro...)
        "omniroute": LLMProviderConfig(
            name="omniroute", display_name="OmniRoute",
            api_key_env="",
            base_url=os.getenv("OMNIROUTE_URL", "http://localhost:20128/v1"),
            default_model="tllm/CLAUDE_4_6_OPUS",    # 🎭 Claude Opus 4.6 = chef d'orchestre
            models=[
                # 🎯 Routing intelligent
                "auto/best-free", "auto/best-coding", "auto/best-reasoning",
                "auto/best-fast", "auto/best-chat", "auto/best-vision",
                "auto/coding:free", "auto/coding:fast", "auto/smart",
                "auto/cheap", "auto/pro-coding", "auto/pro-reasoning",
                # 🤖 Top modèles (via tllm, veo, oc...)
                "tllm/CLAUDE_4_6_OPUS", "tllm/CLAUDE_4_6_SONNET", "tllm/CLAUDE_4_5_HAIKU",
                "tllm/GPT_5", "tllm/GPT_5_4", "tllm/GPT_o4_mini",
                "tllm/gemini_3_pro", "tllm/gemini_2_5_pro", "tllm/gemini_2_0_flash",
                "tllm/deepseek_v4", "tllm/GPT_4o", "tllm/gemini_3_flash",
                # 🆕 Augment models
                "aug/claude-sonnet-4.6", "aug/claude-opus-4.6", "aug/claude-haiku-4.5",
                "aug/gemini-3.1-pro", "aug/gemini-3.0-flash",
                "aug/gpt-5.5-high", "aug/gpt-5.5-medium",
                # 🆓 Free tiers
                "oc/deepseek-v4-flash-free", "oc/minimax-m3-free",
                "oc/ling-2.6-1t-free", "oc/qwen3.6-plus-free",
                # 🖼️ Vision/Génération
                "veo-free/veo", "veo-free/seedance",
            ],
            api_type="openai", requires_key=False, icon="🌟",
            description="GRATUIT ! Routeur 85+ LLMs (Claude 4.6 Opus, GPT-5, Gemini 3 Pro)",
            setup_url="http://localhost:20128/dashboard"
        ),
        # 🟢 NVIDIA NIM - API gratuite pour le développement (Llama, Nemotron, Mistral...)
        "nvidia": LLMProviderConfig(
            name="nvidia", display_name="NVIDIA NIM",
            api_key_env="NVIDIA_API_KEY",
            base_url="https://integrate.api.nvidia.com/v1",
            default_model="meta/llama-3.3-70b-instruct",
            models=[
                "meta/llama-3.3-70b-instruct", "meta/llama-3.1-405b-instruct",
                "meta/llama-3.1-70b-instruct", "meta/llama-3.1-8b-instruct",
                "nvidia/llama-3.3-nemotron-super-49b-v1",
                "nvidia/llama-3.1-nemotron-ultra-253b-v1",
                "nvidia/nemotron-3-ultra-550b-a55b",
                "mistralai/mixtral-8x22b-instruct", "mistralai/mistral-nemotron",
                "deepseek-ai/deepseek-v4-flash", "deepseek-ai/deepseek-v4-pro",
                "qwen/qwq-32b", "qwen/qwen2.5-coder-32b-instruct",
                "qwen/qwen3.5-122b-a10b",
                "microsoft/phi-4-mini-instruct",
                "google/gemma-2-2b-it",
            ],
            api_type="openai", icon="🟢",
            description="GRATUIT pour le dev ! Llama 3.3, Nemotron, Mixtral via NVIDIA NIM",
            setup_url="https://build.nvidia.com/settings/api-keys"
        ),
        # 🧠 DeepSeek - Excellent rapport qualité/prix pour le code
        "deepseek": LLMProviderConfig(
            name="deepseek", display_name="DeepSeek",
            api_key_env="DEEPSEEK_API_KEY",
            base_url="https://api.deepseek.com/v1",
            default_model="deepseek-chat",
            models=["deepseek-chat", "deepseek-reasoner"],
            api_type="openai", icon="🧠",
            description="N°1 rapport qualite/prix. Excellent pour le code",
            setup_url="https://platform.deepseek.com/api_keys"
        ),
        # ✨ OpenAI / ChatGPT - Les plus populaires
        "openai": LLMProviderConfig(
            name="openai", display_name="OpenAI ChatGPT",
            api_key_env="OPENAI_API_KEY",
            base_url="https://api.openai.com/v1",
            default_model="gpt-4o-mini",
            models=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o1-mini", "o3-mini"],
            api_type="openai", icon="✨",
            description="GPT-4o, o1, o3. La reference du marché",
            setup_url="https://platform.openai.com/api-keys"
        ),
        # 🟣 Anthropic Claude - Le meilleur pour le code
        "anthropic": LLMProviderConfig(
            name="anthropic", display_name="Anthropic Claude",
            api_key_env="ANTHROPIC_API_KEY",
            base_url="https://api.anthropic.com/v1",
            default_model="claude-sonnet-4-20250514",
            models=["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-opus-4-20250514"],
            api_type="anthropic", icon="🟣",
            description="Claude Sonnet 4, Opus. Excellent raisonnement",
            setup_url="https://console.anthropic.com/settings/keys"
        ),
        # 🔵 Google Gemini - Le multimodal gratuit
        "google": LLMProviderConfig(
            name="google", display_name="Google Gemini",
            api_key_env="GEMINI_API_KEY",
            base_url="https://generativelanguage.googleapis.com/v1beta",
            default_model="gemini-2.0-flash",
            models=["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-2.5-pro-exp-03-25"],
            api_type="gemini", icon="🔵",
            description="Gratuit ! Multimodal et ultra-rapide",
            setup_url="https://aistudio.google.com/app/apikey"
        ),
        # ⚡ Groq - Inference ultra-rapide, modèles gratuits
        "groq": LLMProviderConfig(
            name="groq", display_name="Groq",
            api_key_env="GROQ_API_KEY",
            base_url="https://api.groq.com/openai/v1",
            default_model="llama-3.3-70b-versatile",
            models=["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768",
                    "deepseek-r1-distill-llama-70b", "gemma2-9b-it", "qwen-2.5-32b"],
            api_type="openai", icon="⚡",
            description="Gratuit ! Inference ultra-rapide (Llama, Mixtral...)",
            setup_url="https://console.groq.com/keys"
        ),
        # 🇨🇳 Kimi / Moonshot (mentionné par l'utilisateur)
        "kimi": LLMProviderConfig(
            name="kimi", display_name="Kimi (Moonshot)",
            api_key_env="KIMI_API_KEY",
            base_url="https://api.moonshot.cn/v1",
            default_model="kimi-k2",
            models=["kimi-k2", "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
            api_type="openai", icon="🇨🇳",
            description="Kimi K2 : top modele chinois, contexte 128k",
            setup_url="https://platform.moonshot.cn/console/api-keys"
        ),
        # 🔮 Mistral AI - Le champion européen
        "mistral": LLMProviderConfig(
            name="mistral", display_name="Mistral AI",
            api_key_env="MISTRAL_API_KEY",
            base_url="https://api.mistral.ai/v1",
            default_model="mistral-large-latest",
            models=["mistral-large-latest", "mistral-small-latest", "codestral-latest", "ministral-8b-latest"],
            api_type="openai", icon="🔮",
            description="Mistral Large, Codestral. L'excellence europeenne",
            setup_url="https://console.mistral.ai/api-keys/"
        ),
        # 🟡 Perplexity AI - Recherche + IA
        "perplexity": LLMProviderConfig(
            name="perplexity", display_name="Perplexity AI",
            api_key_env="PERPLEXITY_API_KEY",
            base_url="https://api.perplexity.ai",
            default_model="sonar-pro",
            models=["sonar-pro", "sonar", "sonar-reasoning-pro", "sonar-reasoning"],
            api_type="openai", icon="🟡",
            description="Sonar Pro : recherche web + raisonnement",
            setup_url="https://www.perplexity.ai/settings/api"
        ),
        # 🎯 xAI / Grok
        "xai": LLMProviderConfig(
            name="xai", display_name="xAI Grok",
            api_key_env="XAI_API_KEY",
            base_url="https://api.x.ai/v1",
            default_model="grok-2-1212",
            models=["grok-2-1212", "grok-2-vision-1212"],
            api_type="openai", icon="🎯",
            description="Grok 2 par xAI (Elon Musk)",
            setup_url="https://console.x.ai"
        ),
        # 🌐 OpenRouter - Passerelle vers 200+ modèles
        "openrouter": LLMProviderConfig(
            name="openrouter", display_name="OpenRouter",
            api_key_env="OPENROUTER_API_KEY",
            base_url="https://openrouter.ai/api/v1",
            default_model="google/gemini-2.0-flash",  # 🆓 Gratuit sur OpenRouter
            models=["google/gemini-2.0-flash",                    # 🆓 Gemini - toujours gratuit
                    "meta-llama/llama-3.3-70b-instruct",         # 🆓 Llama - toujours gratuit
                    "mistralai/mistral-small-24b-instruct-2501",  # 🆓 Mistral - toujours gratuit
                    "deepseek/deepseek-chat",                     # 🆓 DeepSeek - quasi gratuit
                    "anthropic/claude-sonnet-4",
                    "openai/gpt-4o",
                    "qwen/qwen-2.5-72b-instruct"],
            api_type="openai", icon="🌐",
            description="200+ modeles. Une seule clé pour tous les accès",
            setup_url="https://openrouter.ai/keys"
        ),
        # 🤝 Together AI - Modèles open-source
        "together": LLMProviderConfig(
            name="together", display_name="Together AI",
            api_key_env="TOGETHER_API_KEY",
            base_url="https://api.together.xyz/v1",
            default_model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
            models=["meta-llama/Llama-3.3-70B-Instruct-Turbo", "deepseek-ai/DeepSeek-V3",
                    "Qwen/Qwen2.5-72B-Instruct-Turbo", "mistralai/Mixtral-8x22B-Instruct-v0.1"],
            api_type="openai", icon="🤝",
            description="Modeles open-source hebergés",
            setup_url="https://api.together.xyz/settings/api-keys"
        ),
        # 🟠 OpenClaude - Gitlawb Opengateway (via OpenClaude CLI)
        "openclaude": LLMProviderConfig(
            name="openclaude", display_name="OpenClaude Gateway",
            api_key_env="OPENCLAUDE_API_KEY",
            base_url="https://opengateway.gitlawb.com/v1",
            default_model="mimo-v2.5-pro",
            models=["mimo-v2.5-pro", "mimo-v2.0-flash", "google/gemini-3.1-flash-lite-preview",
                    "google/gemini-3.0-flash", "deepseek/deepseek-chat", "qwen/qwen-2.5-72b-instruct"],
            api_type="openai", icon="🟠",
            description="Gateway OpenClaude : Xiaomi MiMo, Gemini, DeepSeek et +",
            setup_url="https://gitlawb.com/opengateway/keys"
        ),
        # 💻 Ollama - Modèles locaux gratuits
        "ollama": LLMProviderConfig(
            name="ollama", display_name="Ollama (Local)",
            api_key_env="",
            base_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            default_model="llama3.2",
            models=["llama3.2", "llama3.1", "deepseek-coder", "codellama", "mistral", "mixtral", "qwen2.5"],
            api_type="ollama", requires_key=False, icon="💻",
            description="Gratuit ! Modeles locaux sur ta machine",
            setup_url="https://ollama.ai/download"
        ),
    })


config = Config()
