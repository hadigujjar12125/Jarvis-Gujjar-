"""Provider-specific exceptions."""
from __future__ import annotations

from jarvis.utils.exceptions import JarvisError


class AIProviderError(JarvisError):
    """Base exception for AI providers."""


class ProviderUnavailable(AIProviderError):
    """Raised when a provider cannot be reached or is not configured."""


class ProviderTimeout(AIProviderError):
    """Raised when a provider request times out."""
