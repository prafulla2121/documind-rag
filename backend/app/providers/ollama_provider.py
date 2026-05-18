import httpx
import json
from .base import BaseLLMProvider, ModelConfig
from typing import AsyncGenerator, List, Dict

class OllamaProvider(BaseLLMProvider):
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.base_url = config.api_base_url or "http://localhost:11434"

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={"model": self.config.model_name, "messages": messages, "stream": False, "options": {"temperature": self.config.temperature}}
            )
            response.raise_for_status()
            return response.json()["message"]["content"]

    async def stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat",
                json={"model": self.config.model_name, "messages": messages, "stream": True, "options": {"temperature": self.config.temperature}}
            ) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if not data.get("done") and data.get("message"):
                                yield data["message"].get("content", "")
                        except Exception:
                            pass

    def get_token_count(self, text: str) -> int:
        return len(text) // 4
