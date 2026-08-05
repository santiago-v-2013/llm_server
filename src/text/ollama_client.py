"""Ollama-specific LLM client implementation."""

from typing import Any, Dict, List

import httpx

from logger_config import get_logger
from .base import LLMClientBase, LLMMessage

logger = get_logger(__name__)


class OllamaClient(LLMClientBase):
    """Client for interacting with a local Ollama server."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 11434)
        self.model = config.get("model", "llama3")
        self.base_url = f"http://{self.host}:{self.port}"
        
    async def _pull_model(self):
        """Descarga el modelo automáticamente usando la API de Ollama."""
        logger.info("Descargando modelo '%s' en Ollama. Esto puede tardar varios minutos dependiendo de tu conexión...", self.model)
        # El timeout=None es necesario porque descargar gigabytes puede tardar bastante
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model, "stream": False}
            )
            response.raise_for_status()
        logger.info("✅ Modelo '%s' descargado y listo para usar.", self.model)

    async def chat(self, messages: List[LLMMessage], **kwargs) -> str:
        """Call the Ollama /api/chat endpoint."""
        logger.info("Sending chat request to Ollama model '%s'", self.model)
        formatted_messages = []
        for message in messages:
            if isinstance(message.content, str):
                formatted_messages.append({"role": message.role, "content": message.content})
            elif isinstance(message.content, list):
                text_content = ""
                images = []
                for part in message.content:
                    if part.get("type") == "text":
                        text_content += part.get("text", "") + "\n"
                    elif part.get("type") == "image_url":
                        url = part.get("image_url", {}).get("url", "")
                        if url.startswith("data:image"):
                            images.append(url.split(",")[-1])
                
                msg_dict: Dict[str, Any] = {"role": message.role, "content": text_content.strip()}
                
                # Sanitización de Modalidad para Ollama:
                # Protegemos al LLM no enviándole la llave "images" si sabemos que no es un VLM.
                supports_vision = self.config.get("supports_vision", False)
                if images and supports_vision:
                    msg_dict["images"] = images
                elif images:
                    logger.warning("Sanitizando petición: El modelo '%s' no está configurado para visión. Ignorando imagen.", self.model)
                    
                formatted_messages.append(msg_dict)

        payload = {
            "model": self.model,
            "messages": formatted_messages,
            "stream": False,
        }
        
        # Merge common options with specific options
        common = self.config.get("common_options", {})
        specific = self.config.get("options", {})
        merged_opts = {**common, **specific}
        
        # Translate generic standard to Ollama specific
        if "max_tokens" in merged_opts:
            merged_opts["num_predict"] = merged_opts.pop("max_tokens")
            
        if merged_opts:
            payload["options"] = merged_opts

        payload.update(kwargs)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            
            # Si el modelo no existe (404), intentamos descargarlo automáticamente y reintentamos
            if response.status_code == 404:
                logger.warning("Modelo '%s' no encontrado localmente. Iniciando auto-descarga...", self.model)
                await self._pull_model()
                logger.info("Reintentando la petición de chat...")
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
                
            response.raise_for_status()
        
        logger.info("Received response from Ollama.")
        return response.json()["message"]["content"]

    async def generate(self, prompt: str, **kwargs) -> str:
        """Call the Ollama /api/generate endpoint."""
        logger.info("Sending generate request to Ollama model '%s'", self.model)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        
        common = self.config.get("common_options", {})
        specific = self.config.get("options", {})
        merged_opts = {**common, **specific}
        
        if "max_tokens" in merged_opts:
            merged_opts["num_predict"] = merged_opts.pop("max_tokens")
            
        if merged_opts:
            payload["options"] = merged_opts

        payload.update(kwargs)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self.base_url}/api/generate", json=payload)
            
            # Si el modelo no existe (404), intentamos descargarlo automáticamente y reintentamos
            if response.status_code == 404:
                logger.warning("Modelo '%s' no encontrado localmente. Iniciando auto-descarga...", self.model)
                await self._pull_model()
                logger.info("Reintentando la petición de generación...")
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                
            response.raise_for_status()
            
        logger.info("Received response from Ollama.")
        return response.json()["response"]
