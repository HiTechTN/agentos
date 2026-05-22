import hashlib
import json

import httpx
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
    _llm_cache: dict[str, LLMResponse] = {}

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

    def _cache_key(self, model: str, messages: list[dict], temperature: float) -> str:
        raw = json.dumps([model, messages, temperature], sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        if self.settings.llm_cache_enabled and not tools:
            ck = self._cache_key(model, messages, temperature)
            if ck in self._llm_cache:
                cached = self._llm_cache[ck]
                logger.log_action("llm_client", "cache_hit", "completed", details={"model": model})
                return cached

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
            result = LLMResponse(content=content, model=model, provider="openrouter")
            if self.settings.llm_cache_enabled and not tools:
                self._llm_cache[ck] = result
            return result
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
            return LLMResponse(
                content=content, model=ollama_model, provider="ollama", degraded=True
            )
        except Exception as e:
            raise LLMUnavailableError(
                f"OpenRouter and Ollama unavailable. OpenRouter: failed, Ollama: {e}"
            ) from e

    async def chat_with_model_selection(
        self,
        task_type: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model = self._select_model(task_type)
        return await self.chat(model, messages, tools, temperature, max_tokens)

    def _select_model(self, task_type: str) -> str:
        routing = {
            "code": self.settings.model_for_code,
            "content": self.settings.model_for_content,
            "analysis": self.settings.model_for_analysis,
            "commerce": self.settings.model_for_commerce,
            "write": self.settings.model_for_content,
            "image": self.settings.model_for_content,
            "analyze": self.settings.model_for_analysis,
            "segment": self.settings.model_for_analysis,
            "catalog": self.settings.model_for_commerce,
            "pricing": self.settings.model_for_analysis,
            "faq": self.settings.model_for_content,
        }
        return routing.get(task_type, self.settings.model_for_default)

    async def complete(
        self,
        model: object,
        system: str,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        full_messages = [{"role": "system", "content": system}] + messages
        return await self.chat(
            self.settings.model_for_default,
            full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def clear_cache(self):
        self._llm_cache.clear()
        logger.log_action("llm_client", "cache_cleared", "completed")


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
            logger.log_error(
                "embedding_client", "embed_fallback", "All embedding providers unavailable"
            )
            return [0.0] * 768
