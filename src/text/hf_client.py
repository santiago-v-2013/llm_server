"""HuggingFace-specific LLM client implementation."""

from typing import Any, Dict, List
import httpx
from src.logger_config import get_logger
from .base import LLMClientBase, LLMMessage

logger = get_logger(__name__)

class HFClient(LLMClientBase):
    """Client for interacting with a local HuggingFace Text API server."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 8000)
        self.model = config.get("model", "HuggingFaceTB/SmolLM-135M-Instruct")
        self.base_url = f"http://{self.host}:{self.port}/v1"

    async def chat(self, messages: List[LLMMessage], **kwargs) -> str:
        """Call the HuggingFace /v1/chat/completions endpoint."""
        logger.info("Sending chat request to HuggingFace model API")
        formatted_messages = []
        for message in messages:
            formatted_messages.append({"role": message.role, "content": message.content})

        payload = {
            "messages": formatted_messages,
        }
        
        common = self.config.get("common_options", {})
        specific = self.config.get("options", {})
        payload.update({**common, **specific})
        payload.update(kwargs)

        # Disable timeout for LLMs since generating max_tokens can take several minutes on local GPUs
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload)
            if response.status_code >= 400:
                logger.error(f"HTTP Error {response.status_code}: {response.text}")
            response.raise_for_status()
            
        logger.info("Received response from HuggingFace API.")
        return response.json()["choices"][0]["message"]["content"]

    async def generate(self, prompt: str, **kwargs) -> str:
        """Send a completion-style request and return the generated text.
        HuggingFace local API serves chat/completions natively, so we wrap the prompt in a user message.
        """
        message = LLMMessage(role="user", content=prompt)
        return await self.chat([message], **kwargs)
