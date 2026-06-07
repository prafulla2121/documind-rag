import asyncio
import google.generativeai as genai
from .base import BaseLLMProvider, ModelConfig
from typing import AsyncGenerator, List, Dict

class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini provider using google-generativeai.
    Supports all models including free-tier: gemini-2.0-flash-exp, gemini-1.5-flash, gemini-1.5-flash-8b
    """
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        genai.configure(api_key=config.api_key)
        self.model = genai.GenerativeModel(config.model_name)

    def _build_contents(self, messages: List[Dict[str, str]]) -> str:
        """Flatten message history into a single prompt string."""
        parts = []
        for m in messages:
            role = m["role"].upper() if m["role"] != "assistant" else "MODEL"
            parts.append(f"{role}: {m['content']}")
        return "\n\n".join(parts)

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        prompt = self._build_contents(messages)
        response = await asyncio.to_thread(
            self.model.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_tokens,
            ),
        )
        return response.text

    async def stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        prompt = self._build_contents(messages)
        stream = await asyncio.to_thread(
            self.model.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_tokens,
            ),
            stream=True,
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text

    def get_token_count(self, text: str) -> int:
        # Approximation (Gemini counts differently per model)
        return len(text) // 4
