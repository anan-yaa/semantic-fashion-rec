
from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

    app_name: str = Field(default="Semantic Fashion Recommendation System")
    debug: bool = Field(default=False)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    log_level: str = Field(default="INFO")

    # Database
    database_url: str = Field(
        default="postgresql+psycopg://fashion_rec:dev_password@localhost:5432/fashion_rec"
    )

    # Load the embedding and LLM models in the background at startup
    warm_up_models_on_startup: bool = Field(default=True)

    # Embeddings
    embedding_model: str = Field(default="intfloat/multilingual-e5-base")
    embedding_dim: int = Field(default=768)  # multilingual-e5-base dimension
    embedding_batch_size: int = Field(default=64)

    # API keys / external services
    openai_api_key: str | None = Field(default=None)
    gemini_api_key: str | None = Field(default=None)

    # LLM query understanding
    query_understanding_enabled: bool = Field(default=True)
    # How long allowed filter values (read from the catalogue) are cached before re-reading
    catalogue_facets_cache_seconds: int = Field(default=300)
    llm_provider: str = Field(default="ollama")  # "gemini" or "ollama"
    gemini_model: str = Field(default="gemini-3.5-flash-lite")
    ollama_model: str = Field(default="gemma3:1b")
    # For English-only models (e.g. tinyllama): skip the LLM for non-Latin-script
    # queries instead of letting it mistranslate them
    llm_skip_non_latin_queries: bool = Field(default=False)
    ollama_base_url: str = Field(default="http://localhost:11434")
    # Request-path timeout: TinyLlama 1.1B is fast (~2-3s on GTX 1650)
    llm_query_understanding_timeout_seconds: float = Field(default=8.0)
    llm_query_understanding_max_retries: int = Field(default=0)
    # Circuit breaker: after this many consecutive timeouts/connection errors,
    # skip the LLM for the cooldown instead of waiting for it on every search
    llm_circuit_failure_threshold: int = Field(default=3)
    llm_circuit_cooldown_seconds: float = Field(default=30.0)
    # Eval-path timeout: looser budget for offline evaluation (can retry, want complete coverage)
    llm_query_understanding_eval_timeout_seconds: float = Field(default=15.0)
    llm_query_understanding_eval_max_retries: int = Field(default=1)

    # Rate limiting for POST /search (each search can trigger an LLM call)
    rate_limit_enabled: bool = Field(default=True)
    search_rate_limit_per_minute: float = Field(default=30.0, gt=0)
    search_rate_limit_burst: int = Field(default=10, ge=1)
    feedback_rate_limit_per_minute: float = Field(default=120.0, gt=0)
    feedback_rate_limit_burst: int = Field(default=30, ge=1)
    # Only enable behind a reverse proxy that sets X-Forwarded-For; otherwise
    # clients could send the header themselves to dodge the limit.
    trust_proxy_headers: bool = Field(default=False)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")


settings = Settings()