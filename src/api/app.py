import os
import sys
from pathlib import Path
import asyncio
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from pydantic import BaseModel, ValidationError
from typing import List, Optional, Union, Any

# Asegurar que python encuentre los paquetes dentro de src/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from text import get_client, LLMMessage
from media import get_media_client
from vision import get_vision_client
from auth.key_manager import validate_key
from logger_config import get_logger

logger = get_logger(__name__)

# -----------------------------------------------------------------------------
# Global Application State
# -----------------------------------------------------------------------------
# Initialize the clients ONCE at startup
llm_client = get_client()
media_client = get_media_client()
vision_client = get_vision_client()

app = Flask(__name__)
# 1. Reverse Proxy Fix (para que el Rate Limiter lea la IP real detrás de Nginx/LoadBalancers)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
# 2. Payload Limit (Defensa DoS: Máximo 50MB por petición para evitar desbordamiento de RAM por Base64 gigante)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# -----------------------------------------------------------------------------
# Security & Rate Limiting
# -----------------------------------------------------------------------------
# Load rate limit from environment
RATE_LIMIT = os.environ.get("RATE_LIMIT", "15 per minute")

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[RATE_LIMIT],
    storage_uri="memory://"
)

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify(create_error("RATE_LIMIT_EXCEEDED", f"Rate limit exceeded: {e.description}")), 429

@app.before_request
def require_api_key():
    # Permitir peticiones CORS pre-flight sin llave
    if request.method == 'OPTIONS':
        return
        
    client_key = request.headers.get("X-API-KEY")
    
    # Also support Standard Bearer Token authorization
    if not client_key:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            client_key = auth_header.split(" ")[1]
            
    if not client_key or not validate_key(client_key):
        return jsonify(create_error("UNAUTHORIZED", "Invalid or missing API Key. Use X-API-KEY or Authorization: Bearer header.")), 401

# -----------------------------------------------------------------------------
# Pydantic Schemas for Validation (Boundary Validation)
# -----------------------------------------------------------------------------
class ImageUrl(BaseModel):
    url: str

class ContentPart(BaseModel):
    type: str
    text: Optional[str] = None
    image_url: Optional[ImageUrl] = None

class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[ContentPart]]

class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

class BatchChatCompletionRequest(BaseModel):
    requests: List[ChatCompletionRequest]

class MediaGenerationRequest(BaseModel):
    prompt: Optional[str] = ""
    image_b64: Optional[str] = None
    num_inference_steps: Optional[int] = 25
    num_frames: Optional[int] = 16
    audio_length_in_s: Optional[float] = 5.0
    strength: Optional[float] = 0.75

class VisionRequest(BaseModel):
    image_base64: str
    prompt: Optional[str] = ""

def create_error(code: str, message: str, details: Any = None):
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details
        }
    }

# -----------------------------------------------------------------------------
# API Routes
# -----------------------------------------------------------------------------
@app.route('/v1/models', methods=['GET'])
def list_models():
    models = []
    if llm_client is not None:
        models.append({"id": getattr(llm_client, "model", "llm-unknown"), "object": "model", "type": "llm"})
    if media_client is not None:
        models.append({"id": getattr(media_client, "model", "media-unknown"), "object": "model", "type": "media"})
    if vision_client is not None:
        models.append({"id": getattr(vision_client, "model", "vision-unknown"), "object": "model", "type": "vision"})
        
    return jsonify({
        "data": models,
        "object": "list"
    }), 200

@app.route('/v1/chat/completions', methods=['POST'])
async def chat_completions():
    try:
        # 1. Validate Input at Boundary
        data = request.get_json()
        if not data:
            return jsonify(create_error("INVALID_JSON", "Request body must be valid JSON")), 400
        
        req_data = ChatCompletionRequest(**data)
    except ValidationError as e:
        return jsonify(create_error("VALIDATION_ERROR", "Invalid payload", e.errors())), 422
    except Exception as e:
        return jsonify(create_error("BAD_REQUEST", str(e))), 400

    if llm_client is None:
        return jsonify(create_error("SERVICE_UNAVAILABLE", "LLM engine is disabled in api.yaml")), 503

    try:
        # 2. Map to internal format
        internal_messages = []
        for msg in req_data.messages:
            if isinstance(msg.content, str):
                internal_messages.append(LLMMessage(role=msg.role, content=msg.content))
            else:
                # Store it as raw list of dicts for the client to handle multimodal
                internal_messages.append(LLMMessage(role=msg.role, content=[part.model_dump() for part in msg.content]))
        
        # Bloqueo estricto: El usuario NO puede elegir el modelo.
        # Siempre usamos el modelo configurado en el YAML por el administrador.
        kwargs = {}
        if req_data.temperature is not None:
            kwargs['temperature'] = req_data.temperature
        if req_data.max_tokens is not None:
            kwargs['max_tokens'] = req_data.max_tokens

        response_text = await llm_client.chat(internal_messages, **kwargs)
        
        # 4. Return OpenAI compatible response
        return jsonify({
            "id": "chatcmpl-local",
            "object": "chat.completion",
            "model": llm_client.model, # Obligamos a que la respuesta muestre el modelo real usado
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }]
        }), 200

    except Exception as e:
        logger.error("Internal Server Error: %s", str(e), exc_info=True)
        return jsonify(create_error("INTERNAL_SERVER_ERROR", "An unexpected error occurred.")), 500

@app.route('/v1/chat/completions/batch', methods=['POST'])
async def chat_completions_batch():
    try:
        # 1. Validate Input at Boundary
        data = request.get_json()
        if not data:
            return jsonify(create_error("INVALID_JSON", "Request body must be valid JSON")), 400
        
        batch_req = BatchChatCompletionRequest(**data)
    except ValidationError as e:
        return jsonify(create_error("VALIDATION_ERROR", "Invalid payload", e.errors())), 422
    except Exception as e:
        return jsonify(create_error("BAD_REQUEST", str(e))), 400

    if llm_client is None:
        return jsonify(create_error("SERVICE_UNAVAILABLE", "LLM engine is disabled in api.yaml")), 503

    try:
        # 2. Prepare all coroutines
        coroutines = []
        for req_data in batch_req.requests:
            internal_messages = []
            for msg in req_data.messages:
                if isinstance(msg.content, str):
                    internal_messages.append(LLMMessage(role=msg.role, content=msg.content))
                else:
                    internal_messages.append(LLMMessage(role=msg.role, content=[part.model_dump() for part in msg.content]))
            
            # Bloqueo estricto en batch: Se ignora req_data.model
            kwargs = {}
            if req_data.temperature is not None:
                kwargs['temperature'] = req_data.temperature
            if req_data.max_tokens is not None:
                kwargs['max_tokens'] = req_data.max_tokens
            
            # Append the coroutine to the list without awaiting it yet
            coroutines.append(llm_client.chat(internal_messages, **kwargs))
            
        # 3. Execute all requests concurrently
        responses = await asyncio.gather(*coroutines, return_exceptions=True)
        
        # 4. Format the batch response
        batch_results = []
        for idx, (req_data, response_text) in enumerate(zip(batch_req.requests, responses)):
            if isinstance(response_text, Exception):
                logger.error("Error in batch request %d: %s", idx, str(response_text))
                batch_results.append({
                    "id": f"chatcmpl-local-batch-{idx}",
                    "error": str(response_text)
                })
            else:
                batch_results.append({
                    "id": f"chatcmpl-local-batch-{idx}",
                    "object": "chat.completion",
                    "model": llm_client.model, # Obligamos a usar el modelo del server
                    "choices": [{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": response_text
                        },
                        "finish_reason": "stop"
                    }]
                })
                
        return jsonify({"batch_results": batch_results}), 200

    except Exception as e:
        logger.error("Internal Server Error in Batch: %s", str(e), exc_info=True)
        return jsonify(create_error("INTERNAL_SERVER_ERROR", "An unexpected error occurred during batch processing.")), 500

@app.route('/v1/media/generations', methods=['POST'])
async def generate_media():
    try:
        data = request.get_json()
        if not data:
            return jsonify(create_error("INVALID_JSON", "Request body must be valid JSON")), 400
        
        req_data = MediaGenerationRequest(**data)
    except ValidationError as e:
        return jsonify(create_error("VALIDATION_ERROR", "Invalid payload", e.errors())), 422
    except Exception as e:
        return jsonify(create_error("BAD_REQUEST", str(e))), 400
        
    if media_client is None:
        return jsonify(create_error("SERVICE_UNAVAILABLE", "Media engine is disabled in api.yaml")), 503

    try:
        results = await media_client.generate_media(
            prompt=req_data.prompt,
            image_b64=req_data.image_b64,
            num_inference_steps=req_data.num_inference_steps,
            num_frames=req_data.num_frames,
            audio_length_in_s=req_data.audio_length_in_s,
            strength=req_data.strength
        )
        
        import time
        return jsonify({
            "created": int(time.time()),
            "data": results
        }), 200
        
    except Exception as e:
        logger.error("Internal Server Error in Media Generation: %s", str(e), exc_info=True)
        return jsonify(create_error("INTERNAL_SERVER_ERROR", "An unexpected error occurred during media generation.")), 500

@app.route('/v1/vision/analyses', methods=['POST'])
async def analyze_vision():
    try:
        data = request.get_json()
        if not data:
            return jsonify(create_error("INVALID_JSON", "Request body must be valid JSON")), 400
        
        req_data = VisionRequest(**data)
    except ValidationError as e:
        return jsonify(create_error("VALIDATION_ERROR", "Invalid payload", e.errors())), 422
    except Exception as e:
        return jsonify(create_error("BAD_REQUEST", str(e))), 400
        
    if vision_client is None:
        return jsonify(create_error("SERVICE_UNAVAILABLE", "Vision engine is disabled in api.yaml")), 503

    try:
        results = await vision_client.analyze_image(
            image_base64=req_data.image_base64,
            prompt=req_data.prompt
        )
        
        return jsonify({
            "results": results
        }), 200
        
    except Exception as e:
        logger.error(f"Internal Server Error in Vision Analysis: {e}", exc_info=True)
        return jsonify(create_error("INTERNAL_SERVER_ERROR", "An unexpected error occurred during vision analysis.")), 500

if __name__ == "__main__":
    # Ensure asgiref is installed for async Flask routes
    # NOTA PARA CONCURRENCIA: app.run() es para desarrollo y no maneja alta concurrencia.
    # Para producción (Múltiples requests simultáneos), usar Gunicorn con hilos:
    # gunicorn -w 4 --threads 8 scripts.run_api_server:app
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
