"""Enhanced settings loader supporting default YAML, local YAML, and .env with environment override.

Behavior:
- Load default settings from config/default_settings.yaml (if present in repository).
- Then load config/settings.yaml if exists (local overrides).
- Finally, environment variables override any loaded values. Environment variable names are the
  uppercase form of the Pydantic field names (e.g., ASSISTANT_NAME).

This design gives users the flexibility to configure via files during installation and override
safely with environment variables for secrets or runtime changes.
"""
from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Dict, Any

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    assistant_name: str = Field("Jarvis", description="Assistant display name and wake-word")
    wake_word: str = Field("jarvis", description="Wake word (lowercase)")
    ai_provider: str = Field("gemini", description="Default AI provider id")
    default_voice: str = Field("en-US-JennyNeural", description="Default TTS voice")
    log_level: str | None = Field(None, description="Override log level e.g. DEBUG")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
            if not isinstance(data, dict):
                return {}
            return data
    except Exception:
        # If YAML is invalid, ignore and return empty to avoid crashing startup
        return {}


def load_settings() -> Settings:
    repo_root = Path(__file__).resolve().parents[1]
    default_path = repo_root / "config" / "default_settings.yaml"
    local_path = repo_root / "config" / "settings.yaml"

    config: Dict[str, Any] = {}
    config.update(_load_yaml_file(default_path))
    config.update(_load_yaml_file(local_path))

    # Environment overrides: look for env vars matching upper(field_name)
    env_overrides: Dict[str, Any] = {}
    for field in Settings.model_fields.keys():
        env_key = field.upper()
        if env_key in os.environ:
            env_overrides[field] = os.environ[env_key]

    # Merge with env taking precedence over YAML
    merged = {**config, **env_overrides}
    return Settings(**merged)
