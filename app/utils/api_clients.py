import json
import httpx
from typing import Any
from openai import AsyncOpenAI

from app.config.settings import get_settings
from app.utils.logging import get_logger

logger = get_logger("api_clients")


class LLMResponse:
    def __init__(self, content: str, model: str, provider: str, degraded: bool = False):
        self.content = content
        self.model = model
        self.provider = provider
        self.degraded = degraded


class LLMUnavailableError(Exception):
    pass


class LLMClient:
    def __init__(self):
        self.settings = get_settings()
        self._openai_client: AsyncOpenAI | None = None

    def _get_openai_client(self) -> AsyncOpenAI:
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(
                api_key=self.settings.openrouter_api_key,
                base_url=self.settings.openrouter_base_url,
            )
        return self._openai_client

    async def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        try:
            client = self._get_openai_client()
            kwargs = dict(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if tools:
                kwargs["tools"] = tools
            response = await client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            return LLMResponse(content=content, model=model, provider="openrouter")
        except Exception as e:
            logger.log_warn("llm_client", "openrouter_fallback", f"OpenRouter failed: {e}")
            return await self._fallback_ollama(model, messages, tools, temperature, max_tokens)

    async def _fallback_ollama(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        try:
            ollama_model = self.settings.ollama_fallback_model
            ollama_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
            payload = dict(model=ollama_model, messages=ollama_messages, stream=False)
            if temperature:
                payload["options"] = {"temperature": temperature}

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.settings.ollama_base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")

            return LLMResponse(content=content, model=ollama_model, provider="ollama", degraded=True)
        except Exception as e:
            raise LLMUnavailableError(
                f"OpenRouter and Ollama unavailable. OpenRouter: failed, Ollama: {e}"
            ) from e


class EmbeddingClient:
    def __init__(self):
        self.settings = get_settings()
        self._openai_client: AsyncOpenAI | None = None

    def _get_openai_client(self) -> AsyncOpenAI:
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(
                api_key=self.settings.openrouter_api_key,
                base_url="https://api.openai.com/v1",
            )
        return self._openai_client

    async def embed(self, text: str) -> list[float]:
        try:
            client = self._get_openai_client()
            response = await client.embeddings.create(
                model=self.settings.openai_embedding_model,
                input=text,
                dimensions=self.settings.openai_embedding_dimensions,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.log_warn("embedding_client", "openai_fallback", f"OpenAI embedding failed: {e}")
            return await self._fallback_ollama_embed(text)

    async def _fallback_ollama_embed(self, text: str) -> list[float]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.settings.ollama_base_url}/api/embeddings",
                    json={"model": self.settings.ollama_embedding_model, "prompt": text},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("embedding", [0.0] * 768)
        except Exception:
            logger.log_error("embedding_client", "embed_fallback", "All embedding providers unavailable")
            return [0.0] * 768
