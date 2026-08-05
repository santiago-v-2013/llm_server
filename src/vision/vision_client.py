"""Client for interacting with the local generic Vision server."""

from typing import Any, Dict, List
import httpx
from logger_config import get_logger

logger = get_logger(__name__)

class VisionClient:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 5002)
        self.base_url = f"http://{self.host}:{self.port}"

    async def analyze_image(self, image_base64: str, prompt: str = "", **kwargs) -> List[Dict[str, Any]]:
        logger.info("Sending vision analysis request")
        
        payload = {
            "image_base64": image_base64,
            "prompt": prompt,
        }
        
        if "options" in self.config:
            payload.update(self.config["options"])
            
        payload.update(kwargs)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self.base_url}/analyze", json=payload)
            if response.status_code != 200:
                raise Exception(f"Vision server error: {response.text}")
            
        return response.json().get("results", [])
