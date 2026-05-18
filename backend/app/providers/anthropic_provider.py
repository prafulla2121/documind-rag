import anthropic
from .base import BaseLLMProvider, ModelConfig
from typing import AsyncGenerator, List, Dict

class AnthropicProvider(BaseLLMProvider):
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.client = anthropic.AsyncAnthropic(api_key=config.api_key)

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        system = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)

        response = await self.client.messages.create(
            model=self.config.model_name,
            max_tokens=self.config.max_tokens,
            system=system,
            messages=user_messages,
        )
        return response.content[0].text

    async def stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        system = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)

        async with self.client.messages.stream(
            model=self.config.model_name,
            max_tokens=self.config.max_tokens,
            system=system,
            messages=user_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def get_token_count(self, text: str) -> int:
        return len(text) // 4
