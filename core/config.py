from typing import Optional

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

    # Embeddings
    embedding_model: str = Field(default="intfloat/multilingual-e5-base")
    embedding_dim: int = Field(default=768)  # multilingual-e5-base dimension
    embedding_batch_size: int = Field(default=64)

    # API keys / external services
    openai_api_key: Optional[str] = Field(default=None)
    gemini_api_key: Optional[str] = Field(default=None)

    # LLM query understanding
    query_understanding_enabled: bool = Field(default=True)
    gemini_model: str = Field(default="gemini-3.5-flash-lite")
    # Request-path timeout: tight budget to keep search responsive (no retries, fallback exists)
    llm_query_understanding_timeout_seconds: float = Field(default=2.5)
    llm_query_understanding_max_retries: int = Field(default=0)
    # Eval-path timeout: looser budget for offline evaluation (can retry, want complete coverage)
    llm_query_understanding_eval_timeout_seconds: float = Field(default=15.0)
    llm_query_understanding_eval_max_retries: int = Field(default=1)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")


settings = Settings()