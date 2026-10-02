import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv

BASE_DIR: Path = Path(__file__).resolve().parent.parent
ENV_FILE: Path = BASE_DIR / ".env"
ENV_FILE.exists() and load_dotenv(dotenv_path=ENV_FILE)


class Settings:
    APP_NAME: str = "Semantic Fashion Recommendation System"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # API keys / external services
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://fashion_rec:dev_password@localhost:5432/fashion_rec",
    )


settings = Settings()