import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from logger_config import get_logger
from .vision_client import VisionClient

logger = get_logger(__name__)

def load_yaml(filename: str) -> Dict[str, Any]:
    workspace_dir = Path(__file__).resolve().parents[2]
    path = workspace_dir / "config" / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def get_vision_client() -> Optional[VisionClient]:
    api_config = load_yaml("api.yaml")
    vis_config = load_yaml("vision.yaml")
    
    server_type = os.environ.get("VISION_SERVER_TYPE")
    if not server_type:
        server_type = api_config.get("active_engines", {}).get("vision", "huggingface")
    server_type = server_type.lower()
    
    server_config = vis_config.get(server_type, {})

    logger.info("Creating vision client for server type: %s", server_type)

    if server_type == "huggingface":
        return VisionClient(server_config)
    if server_type == "none":
        return None

    raise ValueError(f"Unsupported vision server type: {server_type}")
