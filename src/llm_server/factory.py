"""Factory for creating the appropriate LLM client from configuration."""

import os
from typing import Any, Dict

from logger_config import get_logger
from llm_server.base import LLMClientBase
from llm_server.ollama_client import OllamaClient
from llm_server.vllm_client import VLLMClient

logger = get_logger(__name__)


def load_yaml(path: str) -> Dict[str, Any]:
    """Load a simple YAML file with top-level sections into a dictionary.

    This parser supports the structure used by config/llm_client.yaml and does
    not require external YAML libraries.
    """
    config: Dict[str, Any] = {}
    current_section: str | None = None

    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Top-level section (e.g. "ollama:") or top-level key-value
            if not line.startswith(" ") and ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if value == "":
                    # Section header with no value
                    current_section = key
                    config[current_section] = {}
                else:
                    # Top-level scalar key-value (e.g. server_type: "vllm")
                    current_section = None
                    config[key] = value
                continue

            # Key-value inside current section
            if current_section is not None and ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                config[current_section][key] = value

    return config


def get_client(config_path: str = None) -> LLMClientBase:
    """Create an LLM client based on the configuration file.

    Args:
        config_path: Path to the YAML configuration file. If not provided,
            it defaults to config/llm_client.yaml relative to the workspace root.

    Returns:
        An instance of a concrete LLMClientBase implementation.

    Raises:
        ValueError: If the configured server type is not supported.
        FileNotFoundError: If the configuration file does not exist.
    """
    if config_path is None:
        workspace_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        config_path = os.path.join(workspace_dir, "config", "llm_client.yaml")

    logger.info("Loading LLM client configuration from %s", config_path)
    config = load_yaml(config_path)
    server_type = config.get("server_type", "ollama").lower()
    server_config = config.get(server_type, {})

    logger.info("Creating client for server type: %s", server_type)

    if server_type == "ollama":
        return OllamaClient(server_config)
    if server_type == "vllm":
        return VLLMClient(server_config)

    raise ValueError(f"Unsupported server type: {server_type}")
