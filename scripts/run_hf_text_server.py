import os
import torch
from flask import Flask, request, jsonify
from transformers import pipeline
import sys
import yaml
from pathlib import Path

workspace_dir = Path(__file__).resolve().parents[1]
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

config_path = workspace_dir / "config" / "llm.yaml"
try:
    with open(config_path, "r", encoding="utf-8") as f:
        llm_config = yaml.safe_load(f) or {}
except Exception:
    llm_config = {}

common_options = llm_config.get("common_options", {})
default_max_tokens = common_options.get("max_tokens", 512)
default_temperature = common_options.get("temperature", 0.7)

from src.logger_config import get_logger

logger = get_logger(__name__)

app = Flask(__name__)

model_id = os.environ.get("LLM_MODEL_ID", "HuggingFaceTB/SmolLM-135M-Instruct")
task = os.environ.get("LLM_TASK", "text-generation")
device = "cuda" if torch.cuda.is_available() else "cpu"

logger.info(f"🚀 Cargando modelo de Texto (HuggingFace {task}): {model_id} en {device}...")

try:
    pipe = pipeline(
        task, 
        model=model_id, 
        device_map="auto" if device == "cuda" else None,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        trust_remote_code=True
    )

    # Parches para modelos VLM pequeños (como tiny-llava)
    if "image-text-to-text" in getattr(pipe, "task", ""):
        if getattr(pipe, "processor", None) is not None:
            if getattr(pipe.processor, "patch_size", None) is None:
                pipe.processor.patch_size = 14
                pipe.processor.vision_feature_select_strategy = "full"
            if getattr(pipe.processor, "chat_template", None) is None:
                chat_temp = "{% for message in messages %}{% if message['role'] == 'user' %}USER: {% for content in message['content'] %}{% if content['type'] == 'image' %}<image>\n{% else %}{{ content['text'] }}{% endif %}{% endfor %}\n{% elif message['role'] == 'assistant' %}ASSISTANT: {{ message['content'] }}\n{% endif %}{% endfor %}ASSISTANT: "
                pipe.tokenizer.chat_template = chat_temp
                pipe.processor.chat_template = chat_temp

    logger.info("✅ Modelo de texto cargado correctamente.")
except Exception as e:
    logger.error(f"❌ Error cargando el modelo de texto: {e}")
    pipe = None

@app.route("/v1/models", methods=["GET"])
def get_models():
    return jsonify({
        "data": [{"id": model_id, "object": "model"}],
        "object": "list"
    })

@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    if pipe is None:
        return jsonify({"error": "Model not loaded"}), 500

    data = request.get_json()
    messages = data.get("messages", [])
    
    try:
        # Sanitización de Modalidad:
        # Si el motor fue configurado exclusivamente para texto ("text-generation"),
        # extirpamos silenciosamente cualquier imagen del payload para evitar crasheos.
        is_text_only = (task == "text-generation")
        sanitized_messages = []
        
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                if is_text_only:
                    # Extraer únicamente las porciones de texto
                    text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
                    content = " ".join(text_parts).strip()
                else:
                    # Convertir formato OpenAI al formato Transformers (image-text-to-text pipeline)
                    new_content = []
                    for c in content:
                        if c.get("type") == "image_url":
                            new_content.append({
                                "type": "image",
                                "url": c.get("image_url", {}).get("url", "")
                            })
                        else:
                            new_content.append(c)
                    content = new_content
            
            sanitized_messages.append({
                "role": msg.get("role", "user"),
                "content": content
            })
            
        messages = sanitized_messages

        # Verificar si el modelo tiene soporte oficial para formato chat (Instruct)
        has_chat_template = hasattr(pipe.tokenizer, "chat_template") and pipe.tokenizer.chat_template is not None
        
        # Configurar parámetros de generación basados en el request (o valores por defecto del config)
        temp = data.get("temperature")
        if temp is None:
            temp = default_temperature
        temp = float(temp)
        
        max_tokens = data.get("max_tokens")
        if max_tokens is None:
            max_tokens = default_max_tokens
            
        do_sample = temp > 0.0
        gen_kwargs = {
            "max_new_tokens": max_tokens,
            "return_full_text": False,
            "do_sample": do_sample
        }
        if do_sample:
            gen_kwargs["temperature"] = temp
        
        if has_chat_template:
            # Modelo Instruct: El tokenizador sabe cómo estructurar los turnos de diálogo
            outputs = pipe(messages, **gen_kwargs)
        else:
            # Modelo Base: No sabe qué es un 'user' o un 'assistant'. 
            # Tenemos que aplanar la conversación manualmente a un solo string.
            prompt_str = ""
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, list): # Si trae formato complejo, extraer texto
                    content = " ".join([c.get("text", "") for c in content if c.get("type") == "text"])
                
                role = msg.get("role", "user")
                if role == "system":
                    prompt_str += f"{content}\n\n"
                elif role == "user":
                    prompt_str += f"User: {content}\n"
                elif role == "assistant":
                    prompt_str += f"Assistant: {content}\n"
            
            prompt_str += "Assistant:" # Trigger para que empiece a escribir
            outputs = pipe(prompt_str, **gen_kwargs)
        
        if isinstance(outputs, list) and len(outputs) > 0:
            gen_text = outputs[0].get("generated_text", "")
            if isinstance(gen_text, list):
                response_text = gen_text[-1]["content"]
            else:
                response_text = gen_text
        else:
            response_text = str(outputs)

        return jsonify({
            "model": model_id,
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": response_text
                }
            }]
        })
    except Exception as e:
        import traceback
        logger.error(f"Internal error processing request: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
