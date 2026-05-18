from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict
from pydantic import BaseModel

class ModelConfig(BaseModel):
    provider: str          # "openai" | "anthropic" | "gemini" | "groq" | "mistral" | "ollama" | "custom"
    model_name: str        # "gpt-4o" | "claude-3-5-sonnet-20241022" | etc.
    api_key: str           # User-provided API key
    api_base_url: str = "" # For custom endpoints
    temperature: float = 0.1
    max_tokens: int = 2048
    context_window: int = 128000

class BaseLLMProvider(ABC):
    def __init__(self, config: ModelConfig):
        self.config = config

    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """Single-shot generation"""
        pass

    @abstractmethod
    async def stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Streaming token generation"""
        pass

    @abstractmethod
    def get_token_count(self, text: str) -> int:
        """Estimate token count"""
        pass
