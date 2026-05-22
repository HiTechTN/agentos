from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # General
    log_level: str = "INFO"
    project_id: str = "demo-project"
    environment: str = "development"
    version: str = "5.0.0"

    # LLM - OpenRouter
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Agent models (configurable per agent)
    dev_agent_model: str = "anthropic/claude-sonnet-20241022"
    content_agent_model: str = "openai/gpt-4o-2024-11-20"
    marketing_agent_model: str = "anthropic/claude-sonnet-20241022"
    commerce_agent_model: str = "openai/gpt-4o-2024-11-20"

    # Multi-model routing (per task type)
    model_for_code: str = "anthropic/claude-sonnet-20241022"
    model_for_content: str = "openai/gpt-4o-2024-11-20"
    model_for_analysis: str = "mistralai/mixtral-8x22b-instruct"
    model_for_commerce: str = "openai/gpt-4o-2024-11-20"
    model_for_default: str = "openai/gpt-4o-2024-11-20"

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
    database_url: str | None = None

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
    redis_url: str | None = None

    @property
    def resolved_redis_url(self) -> str:
        if self.redis_url:
            return self.redis_url
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"

    # TTL
    llm_cache_enabled: bool = True
    llm_cache_ttl: int = 60
    session_cache_ttl: int = 3600
    project_cache_ttl: int = 86400

    # JWT Authentication
    jwt_secret: SecretStr = SecretStr("agentos-jwt-secret-change-in-prod")
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Rate Limiting
    rate_limit_default: str = "100/minute"
    rate_limit_run: str = "10/minute"
    rate_limit_plan: str = "20/minute"
    rate_limit_verify: str = "30/minute"

    # NextAuth
    nextauth_secret: str = "agentos-nextauth-secret-change-in-prod"
    nextauth_url: str = "http://localhost:3000"

    # OAuth2 provider keys
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

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

    # OpenTelemetry
    otlp_endpoint: str = "http://jaeger:4318"
    otlp_enabled: bool = False
    service_name: str = "agentos"

    # MinIO / S3
    s3_endpoint: str = "http://minio:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "agentos"

    # Notifications
    slack_webhook_url: str = ""
    notification_email_from: str = "agentos@localhost"
    notification_smtp_host: str = "mailhog"
    notification_smtp_port: int = 1025

    # Scheduler
    scheduler_enabled: bool = True
    scheduler_check_interval: int = 60

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "protected_namespaces": ("settings_",),
    }


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
