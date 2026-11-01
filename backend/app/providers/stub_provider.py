from .base import BaseLLMProvider


class StubProvider(BaseLLMProvider):
    """Not a model. Answers RAG prompts by echoing the retrieved context so the
    pipeline runs end to end without keys (evals, tests, load tests). Other prompts
    (query rewrite, expansion) raise, and the pipeline falls back to its non-LLM path."""

    async def generate(self, messages):
        if messages[0]["role"] != "system":
            raise RuntimeError("stub provider only answers RAG prompts")
        context = messages[-1]["content"].split("CONTEXT:", 1)[-1].split("\n---\n", 1)[0]
        return context.strip()

    async def stream(self, messages):
        yield await self.generate(messages)

    def get_token_count(self, text: str) -> int:
        return len(text) // 4

    def __str__(self):
        return "stub"
