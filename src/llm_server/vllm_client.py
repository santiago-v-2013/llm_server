"""vLLM-specific LLM client implementation."""

from typing import Any, Dict, List

import requests

from logger_config import get_logger
from llm_server.base import LLMClientBase, LLMMessage

logger = get_logger(__name__)


class VLLMClient(LLMClientBase):
    """Client for interacting with a local vLLM server."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 8000)
        self.model = config.get("model", "meta-llama/Llama-3.1-8B-Instruct")
        self.base_url = f"http://{self.host}:{self.port}/v1"

    def chat(self, messages: List[LLMMessage], **kwargs) -> str:
        """Call the vLLM /v1/chat/completions endpoint."""
        logger.info("Sending chat request to vLLM model '%s'", self.model)
        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
        }
        payload.update(kwargs)

        response = requests.post(f"{self.base_url}/chat/completions", json=payload)
        response.raise_for_status()
        logger.info("Received response from vLLM.")
        return response.json()["choices"][0]["message"]["content"]

    def generate(self, prompt: str, **kwargs) -> str:
        """Call the vLLM /v1/completions endpoint."""
        logger.info("Sending generate request to vLLM model '%s'", self.model)
        payload = {
            "model": self.model,
            "prompt": prompt,
        }
        payload.update(kwargs)

        response = requests.post(f"{self.base_url}/completions", json=payload)
        response.raise_for_status()
        logger.info("Received response from vLLM.")
        return response.json()["choices"][0]["text"]
