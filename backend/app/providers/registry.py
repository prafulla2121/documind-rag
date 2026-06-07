from .base import ModelConfig
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider

PROVIDER_CATALOG = {
    "openai": {
        "label": "OpenAI",
        "models": [
            "gpt-4o",                     # Best for RAG
            "gpt-4o-mini",                # Cheap & Fast
            "o1-preview",                 # Reasoning
            "o1-mini",                    # Fast Reasoning
            "gpt-4-turbo",
            "gpt-3.5-turbo"
        ],
        "key_required": True,
        "key_url": "https://platform.openai.com/api-keys",
    },
    "anthropic": {
        "label": "Anthropic (Claude)",
        "models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
        "key_required": True,
        "key_url": "https://console.anthropic.com/settings/keys",
    },
    "gemini": {
        "label": "Google Gemini (Free Tier Available)",
        "models": [
            "gemini-2.5-flash",           # Requested specific version
            "gemini-2.0-flash-exp",       # FREE - Best current free model
            "gemini-1.5-flash",           # FREE - Fast and reliable
            "gemini-1.5-pro",             # Paid - Most capable
            "gemini-1.5-flash-8b",        # FREE - Ultra fast
            "gemini-ultra",               # Paid
        ],
        "key_required": True,
        "key_url": "https://aistudio.google.com/app/apikey",
        "free_models": ["gemini-2.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-flash-8b"],
    },
    "groq": {
        "label": "Groq (Blazing Fast - Free Tier)",
        "models": [
            "llama-3.3-70b-versatile",    # Latest Llama
            "mixtral-8x7b-32768",         # Strong MoE
            "gemma2-9b-it",               # Google's open model
            "llama-3.1-8b-instant",       # Fastest
        ],
        "key_required": True,
        "key_url": "https://console.groq.com/keys",
        "free_models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it", "llama-3.1-8b-instant"],
    },
    "ollama": {
        "label": "Ollama (Local & Free)",
        "models": [
            "deepseek-r1:7b",             # NEW - Reasoning model
            "deepseek-r1:14b",
            "llama3.2:3b",                # Latest Llama
            "llama3.1:8b",
            "mistral",
            "phi3:mini",
        ],
        "key_required": False,
        "key_url": "https://ollama.com",
    },
    "custom": {
        "label": "Custom OpenAI-Compatible",
        "models": [],   
        "key_required": True,
        "key_url": "",
    },
}

def get_llm_provider(config: ModelConfig):
    provider_map = {
        "openai": OpenAIProvider,
        "groq": OpenAIProvider,       
        "mistral": OpenAIProvider,    
        "custom": OpenAIProvider,     
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
        "ollama": OllamaProvider,
    }

    if config.provider == "groq" and not config.api_base_url:
        config.api_base_url = "https://api.groq.com/openai/v1"
    elif config.provider == "mistral" and not config.api_base_url:
        config.api_base_url = "https://api.mistral.ai/v1"

    cls = provider_map.get(config.provider)
    if not cls:
        raise ValueError(f"Unsupported provider: {config.provider}")
    return cls(config)
