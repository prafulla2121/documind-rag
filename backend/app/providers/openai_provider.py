from openai import AsyncOpenAI
from .base import BaseLLMProvider, ModelConfig
from typing import AsyncGenerator, List, Dict

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.api_base_url or "https://api.openai.com/v1"
        )

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        response = await self.client.chat.completions.create(
            model=self.config.model_name,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return response.choices[0].message.content

    async def stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        async with self.client.chat.completions.stream(
            model=self.config.model_name,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        ) as stream:
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

    def get_token_count(self, text: str) -> int:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(self.config.model_name)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
