import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    cors_origins: tuple[str, ...]
    github_token: str | None
    ollama_base_url: str
    ollama_model: str


settings = Settings(
    cors_origins=tuple(
        origin.strip()
        for origin in os.getenv(
            "BACKEND_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ),
    github_token=os.getenv("GITHUB_TOKEN") or None,
    ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
    ollama_model=os.getenv("OLLAMA_MODEL", "gemma4:12b"),
)
