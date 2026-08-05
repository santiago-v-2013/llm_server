import os
import base64
from io import BytesIO
from PIL import Image
from flask import Flask, request, jsonify
import torch
from transformers import pipeline
import sys
from pathlib import Path

workspace_dir = Path(__file__).resolve().parents[1]
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from src.logger_config import get_logger

logger = get_logger(__name__)

app = Flask(__name__)

model_id = os.environ.get("VISION_MODEL_ID", "IDEA-Research/grounding-dino-base")
task = os.environ.get("VISION_TASK", "zero-shot-object-detection")
device = 0 if torch.cuda.is_available() else -1

logger.info("🚀 Cargando modelo de Visión Genérico (%s): %s en dispositivo %s...", task, model_id, device)

try:
    vision_pipe = pipeline(task=task, model=model_id, device=device)
    logger.info("✅ Modelo de visión cargado correctamente.")
except Exception as e:
    logger.error("❌ Error cargando el modelo de visión: %s", e)
    vision_pipe = None

@app.route("/analyze", methods=["POST"])
def analyze():
    if vision_pipe is None:
        return jsonify({"error": "El modelo no está disponible."}), 500

    data = request.get_json()
    if not data or "image_base64" not in data:
        return jsonify({"error": "Se requiere 'image_base64'."}), 400

    prompt = data.get("prompt", "")
    
    b64 = data.get("image_base64", "")
    if b64.startswith("data:image"):
        b64 = b64.split(",")[-1]

    try:
        image_data = base64.b64decode(b64)
        image = Image.open(BytesIO(image_data)).convert("RGB")
    except Exception as e:
        return jsonify({"error": f"Imposible procesar la imagen base64. {str(e)}"}), 400

    try:
        
        # Build kwargs for pipeline dynamically based on task
        kwargs = {}
        
        if task in ["zero-shot-object-detection", "zero-shot-image-classification"]:
            if not prompt:
                return jsonify({"error": f"La tarea '{task}' requiere un 'prompt' (separado por comas para múltiples etiquetas)."}), 400
            # Hugging Face pipeline uses 'candidate_labels' as a list of strings
            kwargs["candidate_labels"] = [p.strip() for p in prompt.split(",") if p.strip()]
            
        # Run inference
        results = vision_pipe(image, **kwargs)
        
        # HF Pipelines usually return a list of dicts. If it's a single dict, wrap it.
        if isinstance(results, dict):
            results = [results]
            
        # Format results (convert PIL Image masks to base64 if segmentation)
        formatted_results = []
        for res in results:
            formatted_res = {}
            for k, v in res.items():
                if isinstance(v, Image.Image): 
                    buf = BytesIO()
                    v.save(buf, format="PNG")
                    formatted_res[k] = base64.b64encode(buf.getvalue()).decode("utf-8")
                else:
                    formatted_res[k] = v
            formatted_results.append(formatted_res)
            
        return jsonify({"results": formatted_results})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=False)
