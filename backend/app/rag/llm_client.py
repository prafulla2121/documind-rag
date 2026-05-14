"""
Ollama LLM Client — async HTTP client for local LLM inference.
Supports both sync response and streaming for real-time frontend.
"""
import httpx
from typing import AsyncGenerator
import logging
import json

logger = logging.getLogger(__name__)


class OllamaClient:

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self.base_url = base_url
        self.model = model

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1,
    ) -> str:
        """Non-streaming generation — returns full response."""
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": system_prompt,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "top_p": 0.9,
                            "num_ctx": 4096,
                        },
                    },
                )
                response.raise_for_status()
                return response.json().get("response", "")
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama. Is it running?")
            return "I'm sorry, I cannot process your request right now. The LLM service is unavailable. Please ensure Ollama is running."
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return f"An error occurred while generating a response: {str(e)}"

    async def stream_generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1,
    ) -> AsyncGenerator[str, None]:
        """Streaming generation — yields tokens as they arrive."""
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": system_prompt,
                        "stream": True,
                        "options": {
                            "temperature": temperature,
                            "top_p": 0.9,
                            "num_ctx": 4096,
                        },
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if not data.get("done"):
                                    yield data.get("response", "")
                            except json.JSONDecodeError:
                                continue
        except httpx.ConnectError:
            yield "Error: Cannot connect to Ollama. Please ensure it is running on " + self.base_url
        except Exception as e:
            yield f"Error: {str(e)}"

    async def health_check(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "").split(":")[0] for m in models]
                    return self.model.split(":")[0] in model_names
                return False
        except Exception:
            return False
