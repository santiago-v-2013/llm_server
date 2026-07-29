"""Ollama-specific LLM client implementation."""

from typing import Any, Dict, List

import requests

from logger_config import get_logger
from llm_server.base import LLMClientBase, LLMMessage

logger = get_logger(__name__)


class OllamaClient(LLMClientBase):
    """Client for interacting with a local Ollama server."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 11434)
        self.model = config.get("model", "tinyllama")
        self.base_url = f"http://{self.host}:{self.port}"

    def chat(self, messages: List[LLMMessage], **kwargs) -> str:
        """Call the Ollama /api/chat endpoint."""
        logger.info("Sending chat request to Ollama model '%s'", self.model)
        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "stream": False,
        }
        payload.update(kwargs)

        response = requests.post(f"{self.base_url}/api/chat", json=payload)
        response.raise_for_status()
        logger.info("Received response from Ollama.")
        return response.json()["message"]["content"]

    def generate(self, prompt: str, **kwargs) -> str:
        """Call the Ollama /api/generate endpoint."""
        logger.info("Sending generate request to Ollama model '%s'", self.model)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        payload.update(kwargs)

        response = requests.post(f"{self.base_url}/api/generate", json=payload)
        response.raise_for_status()
        logger.info("Received response from Ollama.")
        return response.json()["response"]
