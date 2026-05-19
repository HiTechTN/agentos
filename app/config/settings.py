from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # General
    log_level: str = "INFO"
    project_id: str = "demo-project"
    environment: str = "development"

    # LLM - OpenRouter
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Agent models (configurable per agent)
    dev_agent_model: str = "anthropic/claude-sonnet-20241022"
    content_agent_model: str = "openai/gpt-4o-2024-11-20"
    marketing_agent_model: str = "anthropic/claude-sonnet-20241022"
    commerce_agent_model: str = "openai/gpt-4o-2024-11-20"

    # LLM - Ollama fallback
    ollama_base_url: str = "http://ollama:11434"
    ollama_fallback_model: str = "qwen2.5"

    # Embedding
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 768
    ollama_embedding_model: str = "nomic-embed-text"

    # Database
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "agentos"
    postgres_user: str = "agentos"
    postgres_password: str = ""
    database_url: Optional[str] = None

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_url: Optional[str] = None

    @property
    def resolved_redis_url(self) -> str:
        if self.redis_url:
            return self.redis_url
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"

    # TTL
    llm_cache_ttl: int = 60
    session_cache_ttl: int = 3600
    project_cache_ttl: int = 86400

    # NextAuth
    nextauth_secret: str = "agentos-nextauth-secret-change-in-prod"
    nextauth_url: str = "http://localhost:3000"

    # Stripe
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""

    # GitHub
    github_token: str = ""

    # Replicate
    replicate_api_token: str = ""

    # Sandbox
    sandbox_enabled: bool = True
    sandbox_network: str = "agentos_net"

    # HITL
    hitl_mode: str = "webhook_and_cli"
    hitl_timeout: int = 0

    # API quota per project
    api_quota_per_project: int = 1000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
