"""AI chunk types used across the system."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class AIChunk:
    """A chunk of AI-generated content streamed from an AI provider.

    Attributes:
        text: the partial text content
        delta_type: one of 'token', 'finish', 'error', or 'meta'
        role: optional role such as 'assistant' or 'system'
        token_index: optional sequential token index
        metadata: optional provider-specific metadata
        timestamp: time the chunk was created locally
    """

    text: str
    delta_type: str = "token"
    role: Optional[str] = None
    token_index: Optional[int] = None
    metadata: Dict[str, Any] = None
    timestamp: datetime = datetime.utcnow()
