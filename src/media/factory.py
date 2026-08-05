import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from logger_config import get_logger
from .media_client import MediaClient

logger = get_logger(__name__)

def load_yaml(filename: str) -> Dict[str, Any]:
    workspace_dir = Path(__file__).resolve().parents[2]
    path = workspace_dir / "config" / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def get_media_client() -> Optional[MediaClient]:
    api_config = load_yaml("api.yaml")
    media_config = load_yaml("media.yaml")
    
    server_type = os.environ.get("MEDIA_SERVER_TYPE")
    if not server_type:
        server_type = api_config.get("active_engines", {}).get("media", "diffusers")
    server_type = server_type.lower()
    
    server_config = media_config.get(server_type, {})

    logger.info("Creating media client for server type: %s", server_type)

    if server_type == "diffusers":
        return MediaClient(server_config)
    if server_type == "none":
        return None

    raise ValueError(f"Unsupported media server type: {server_type}")
