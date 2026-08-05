import os
import base64
from io import BytesIO
import numpy as np
from flask import Flask, request, jsonify
import torch
import scipy.io.wavfile
import imageio
import sys
from pathlib import Path

workspace_dir = Path(__file__).resolve().parents[1]
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from src.logger_config import get_logger

logger = get_logger(__name__)

app = Flask(__name__)

model_id = os.environ.get("MEDIA_MODEL_ID", "runwayml/stable-diffusion-v1-5")
task = os.environ.get("MEDIA_TASK", "text-to-image")
device = "cuda" if torch.cuda.is_available() else "cpu"

logger.info("🚀 Cargando modelo de Multimedia (%s): %s en %s...", task, model_id, device)

pipe = None
try:
    if task == "text-to-image":
        from diffusers import AutoPipelineForText2Image
        pipe = AutoPipelineForText2Image.from_pretrained(model_id, torch_dtype=torch.float16 if device=="cuda" else torch.float32)
    elif task == "image-to-image":
        from diffusers import AutoPipelineForImage2Image
        pipe = AutoPipelineForImage2Image.from_pretrained(model_id, torch_dtype=torch.float16 if device=="cuda" else torch.float32)
    elif task == "text-to-video":
        from diffusers import DiffusionPipeline, DPMSolverMultistepScheduler
        pipe = DiffusionPipeline.from_pretrained(model_id, torch_dtype=torch.float16 if device=="cuda" else torch.float32)
        if hasattr(pipe, "scheduler") and pipe.scheduler is not None:
            pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config)
    elif task == "image-to-video":
        from diffusers import DiffusionPipeline
        pipe = DiffusionPipeline.from_pretrained(model_id, torch_dtype=torch.float16 if device=="cuda" else torch.float32, variant="fp16" if device=="cuda" else None)
    elif task == "text-to-audio":
        from diffusers import AudioLDMPipeline
        pipe = AudioLDMPipeline.from_pretrained(model_id, torch_dtype=torch.float16 if device=="cuda" else torch.float32)
    else:
        raise ValueError(f"Tarea no soportada: {task}")
        
    if task == "image-to-video" and device == "cuda":
        pipe.enable_model_cpu_offload()
        # pipe.enable_attention_slicing()  # Opcional, reduce VRAM aún más si fuera necesario
    else:
        pipe = pipe.to(device)
    logger.info("✅ Modelo multimedia cargado correctamente.")
except Exception as e:
    logger.error("❌ Error cargando el modelo multimedia: %s", e)

@app.route("/generate", methods=["POST"])
def generate():
    if pipe is None:
        return jsonify({"error": "El modelo no está disponible."}), 500

    data = request.get_json()
    prompt = data.get("prompt")
    image_b64 = data.get("image_b64")
    
    if not prompt and task not in ["image-to-video"]: # Algunos img2vid no ocupan prompt
        return jsonify({"error": "Se requiere un 'prompt'."}), 400

    init_image = None
    if image_b64:
        if image_b64.startswith("data:image"):
            image_b64 = image_b64.split(",")[-1]
            
        try:
            from PIL import Image
            img_data = base64.b64decode(image_b64)
            init_image = Image.open(BytesIO(img_data)).convert("RGB")
        except Exception as e:
            return jsonify({"error": f"Error decodificando la imagen base64 proporcionada. Asegúrese de que sea válida. Detalle: {str(e)}"}), 400

    try:
        if task == "text-to-image":
            result = pipe(prompt, num_inference_steps=data.get("num_inference_steps", 25)).images[0]
            buf = BytesIO()
            result.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return jsonify({"data": [{"b64_json": b64, "mime_type": "image/png"}]})
            
        elif task == "image-to-image":
            if not init_image:
                return jsonify({"error": "Se requiere 'image_b64' para la tarea image-to-image."}), 400
            result = pipe(prompt, image=init_image, num_inference_steps=data.get("num_inference_steps", 25), strength=data.get("strength", 0.75)).images[0]
            buf = BytesIO()
            result.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return jsonify({"data": [{"b64_json": b64, "mime_type": "image/png"}]})
            
        elif task == "text-to-video":
            # Retorna frames (list of PIL.Image)
            result = pipe(prompt, num_inference_steps=data.get("num_inference_steps", 25), num_frames=data.get("num_frames", 16)).frames
            if hasattr(result, "shape") and len(result.shape) == 5:
                result = result[0] # unpacking batch for numpy array
            elif isinstance(result, list) and isinstance(result[0], list):
                result = result[0] # unpacking batch for list
                
            # Escalar a uint8 si es float
            if isinstance(result, np.ndarray) and result.dtype in [np.float32, np.float64]:
                frames_list = [(img * 255).astype(np.uint8) if img.max() <= 1.0 else img.astype(np.uint8) for img in result]
            else:
                frames_list = [np.array(img) for img in result]
                
            buf = BytesIO()
            # Guardar como MP4 usando imageio
            imageio.mimsave(buf, frames_list, format="mp4", fps=8)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return jsonify({"data": [{"b64_json": b64, "mime_type": "video/mp4"}]})
            
        elif task == "image-to-video":
            if not init_image:
                return jsonify({"error": "Se requiere 'image_b64' para image-to-video."}), 400
            
            kwargs = {
                "image": init_image,
                "num_inference_steps": data.get("num_inference_steps", 25),
                "decode_chunk_size": 1,
                "height": data.get("height", 320),
                "width": data.get("width", 512)
            }
            if prompt:
                kwargs["prompt"] = prompt
                
            result = pipe(**kwargs).frames
            if isinstance(result, list) and isinstance(result[0], list):
                result = result[0]
                
            buf = BytesIO()
            imageio.mimsave(buf, [np.array(img) for img in result], format="mp4", fps=data.get("fps", 7))
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return jsonify({"data": [{"b64_json": b64, "mime_type": "video/mp4"}]})
            
        elif task == "text-to-audio":
            audio = pipe(prompt, num_inference_steps=data.get("num_inference_steps", 10), audio_length_in_s=data.get("audio_length_in_s", 5.0)).audios[0]
            buf = BytesIO()
            scipy.io.wavfile.write(buf, rate=16000, data=audio)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return jsonify({"data": [{"b64_json": b64, "mime_type": "audio/wav"}]})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
