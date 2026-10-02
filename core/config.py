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
    embedding_dim: int = Field(default=384)  # multilingual-e5-small dimension

    # API keys / external services
    openai_api_key: Optional[str] = Field(default=None)
    anthropic_api_key: Optional[str] = Field(default=None)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")


settings = Settings()