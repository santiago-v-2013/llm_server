"""Base classes for LLM server clients."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class LLMMessage:
    """Represents a single message in a chat conversation."""

    role: str
    content: str


class LLMClientBase(ABC):
    """Abstract base class for LLM server clients.

    Concrete implementations must translate the unified chat/generate calls
    into the specific API format expected by each server.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    def chat(self, messages: List[LLMMessage], **kwargs) -> str:
        """Send a chat-style request and return the generated text."""
        raise NotImplementedError

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Send a completion-style request and return the generated text."""
        raise NotImplementedError
