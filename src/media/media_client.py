"""Client for interacting with the local Media server (Diffusers)."""

from typing import Any, Dict, List, Optional
import httpx
from logger_config import get_logger

logger = get_logger(__name__)

class MediaClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 5001)
        self.base_url = f"http://{self.host}:{self.port}"

    async def generate_media(self, prompt: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        logger.info("Sending media generation request")
        
        payload = {}
        if prompt:
            payload["prompt"] = prompt
        
        if "options" in self.config:
            payload.update(self.config["options"])
            
        payload.update(kwargs)

        async with httpx.AsyncClient(timeout=600.0) as client:
            response = await client.post(f"{self.base_url}/generate", json=payload)
            if response.status_code != 200:
                raise Exception(f"Media server error: {response.text}")
            
        return response.json().get("data", [])
