import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from logger_config import get_logger
from .base import LLMClientBase
from .ollama_client import OllamaClient
from .hf_client import HFClient

logger = get_logger(__name__)

def load_yaml(filename: str) -> Dict[str, Any]:
    workspace_dir = Path(__file__).resolve().parents[2]
    path = workspace_dir / "config" / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def get_client() -> Optional[LLMClientBase]:
    api_config = load_yaml("api.yaml")
    llm_config = load_yaml("llm.yaml")
    
    server_type = os.environ.get("LLM_SERVER_TYPE")
    if not server_type:
        server_type = api_config.get("active_engines", {}).get("llm", "ollama")
    server_type = server_type.lower()
    
    server_config = llm_config.get(server_type, {})
    server_config["common_options"] = llm_config.get("common_options", {})

    logger.info("Creating text client for server type: %s", server_type)

    if server_type == "ollama":
        return OllamaClient(server_config)
    if server_type == "huggingface":
        return HFClient(server_config)
    if server_type == "none":
        return None

    raise ValueError(f"Unsupported server type: {server_type}")
