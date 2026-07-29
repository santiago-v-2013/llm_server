"""Example script to query a configured local LLM server.

The script reads config/llm_client.yaml to determine which server to use
(Ollama or vLLM) and routes the request through the appropriate translator.
"""

import os
import sys

# Add the src directory to the Python path
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WORKSPACE_DIR, "src"))

from logger_config import get_logger
from llm_server.base import LLMMessage
from llm_server.factory import get_client

logger = get_logger(__name__)


def main() -> None:
    client = get_client()

    messages = [
        LLMMessage(
            role="system",
            content="Eres un asistente útil y conciso.",
        ),
        LLMMessage(
            role="user",
            content="Escribe un haiku sobre la inteligencia artificial.",
        ),
    ]

    logger.info("Using server: %s", type(client).__name__)
    logger.info("Sending chat request...")
    response = client.chat(messages)
    print("\nResponse:")
    print(response)


if __name__ == "__main__":
    main()
