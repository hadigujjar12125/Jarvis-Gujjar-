"""Runtime settings for JARVIS using Pydantic BaseSettings.

Reads environment variables from a .env file automatically. Keep this file minimal;
more advanced YAML-based configuration loading can be added later.
"""
from __future__ import annotations

from pydantic import BaseSettings, Field
from typing import Optional


class Settings(BaseSettings):
    """Application configuration settings.

    Environment variables are automatically loaded from a `.env` file in the project root.
    """

    assistant_name: str = Field("Jarvis", description="Assistant display name and wake-word")
    wake_word: str = Field("jarvis", description="Wake word (lowercase)")
    ai_provider: str = Field("gemini", description="Default AI provider id")
    default_voice: str = Field("en-US-JennyNeural", description="Default TTS voice")
    log_level: Optional[str] = Field(None, description="Override log level e.g. DEBUG")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def load_settings() -> Settings:
    """Convenience factory to construct Settings.

    Additional loading (from YAML) may be added in future iterations.
    """
    return Settings()
