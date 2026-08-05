import os
import sys
import yaml
import subprocess
import signal
import time
import atexit
import socket
from pathlib import Path

# Fix module imports for direct execution
workspace_dir = Path(__file__).resolve().parents[1]
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from src.logger_config import get_logger

logger = get_logger(__name__)

# Load configs
workspace_dir = Path(__file__).resolve().parents[1]

def load_yaml(filename):
    path = workspace_dir / "config" / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def wait_for_port(port, host="127.0.0.1", timeout=120):
    logger.info(f"⏳ Esperando al puerto {port}...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, port)) == 0:
                logger.info(f"✅ Puerto {port} listo.")
                return True
        time.sleep(1)
    logger.error(f"❌ Timeout esperando al puerto {port}")
    return False

from typing import List
processes: List[subprocess.Popen] = []

def cleanup():
    logger.info("🛑 Apagando el ecosistema de servidores y liberando puertos...")
    for p in processes:
        if p.poll() is None: # Si sigue vivo
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill() # Forzar si no cierra

# Garantiza la limpieza sin importar si fue error, crasheo de python o salida normal
atexit.register(cleanup)

def signal_handler(signum, frame):
    # Esto disparará atexit limpiamente
    sys.exit(0)

# Interceptar Ctrl+C y señales del sistema para apagar todo limpiamente
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    api_config = load_yaml("api.yaml")
    llm_config = load_yaml("llm.yaml")
    media_config = load_yaml("media.yaml")
    vision_config = load_yaml("vision.yaml")
    
    gunicorn_path = os.path.join(os.path.dirname(sys.executable), "gunicorn")
    
    active_engines = api_config.get("active_engines", {})
    server_type = active_engines.get("llm", "ollama")
    media_server_type = active_engines.get("media", "diffusers")
    vision_server_type = active_engines.get("vision", "huggingface")
    
    # ==========================================
    # 1. Start LLM Engine
    # ==========================================
    if server_type == "ollama":
        logger.info("🚀 Iniciando motor Ollama en segundo plano...")
        env = os.environ.copy()
        engine_cfg = llm_config.get("ollama", {}).get("engine_config", {})
        if "visible_devices" in engine_cfg:
            env["CUDA_VISIBLE_DEVICES"] = str(engine_cfg["visible_devices"])
        if "keep_alive" in engine_cfg:
            env["OLLAMA_KEEP_ALIVE"] = str(engine_cfg["keep_alive"])
            
        p = subprocess.Popen(["ollama", "serve"], env=env)
        processes.append(p)
        
    elif server_type == "huggingface":
        logger.info("🚀 Iniciando motor HuggingFace (Text/VLM) en segundo plano...")
        hf_cfg = llm_config.get("huggingface", {})
        model = hf_cfg.get("model", "HuggingFaceTB/SmolLM-135M-Instruct")
        task = hf_cfg.get("task", "text-generation")
        port = hf_cfg.get("port", 8000)
        
        env = os.environ.copy()
        env["LLM_MODEL_ID"] = model
        env["LLM_TASK"] = task
        env["PORT"] = str(port)
        
        # Visible devices
        engine_cfg = hf_cfg.get("engine_config", {})
        if "visible_devices" in engine_cfg:
            env["CUDA_VISIBLE_DEVICES"] = str(engine_cfg["visible_devices"])
            
        p = subprocess.Popen([gunicorn_path, "-w", "1", "--threads", "4", "--bind", f"127.0.0.1:{port}", "--timeout", "300", "scripts.run_hf_text_server:app"], env=env)
        processes.append(p)
    elif server_type != "none":
        logger.warning(f"⚠️ Tipo de servidor LLM no soportado o no configurado: {server_type}")
    
    # Esperar a que el motor LLM inicialice
    if server_type != "none" and 'port' in locals():
        wait_for_port(port)
    
    # ==========================================
    # 2. Start Media Engine
    # ==========================================
    if media_server_type == "diffusers":
        logger.info("🚀 Iniciando motor Multimedia (Diffusers) en segundo plano...")
        env = os.environ.copy()
        diff_cfg = media_config.get("diffusers", {})
        model = diff_cfg.get("model", "runwayml/stable-diffusion-v1-5")
        task = diff_cfg.get("task", "text-to-image")
        port = diff_cfg.get("port", 5001)
        
        env["MEDIA_MODEL_ID"] = model
        env["MEDIA_TASK"] = task
        env["PORT"] = str(port)
        p = subprocess.Popen([gunicorn_path, "-w", "1", "--threads", "4", "--bind", f"127.0.0.1:{port}", "--timeout", "600", "scripts.run_media_server:app"], env=env)
        processes.append(p)
    elif media_server_type != "none":
        logger.warning(f"⚠️ Tipo de servidor de multimedia no configurado: {media_server_type}")
    
    # Esperar a que el motor multimedia inicialice
    if media_server_type != "none":
        wait_for_port(port)
    
    # ==========================================
    # 2.5 Start Vision Engine
    # ==========================================
    if vision_server_type == "huggingface":
        logger.info("🚀 Iniciando motor de Visión Computacional (HuggingFace) en segundo plano...")
        env = os.environ.copy()
        vis_cfg = vision_config.get("huggingface", {})
        model = vis_cfg.get("model", "IDEA-Research/grounding-dino-base")
        task = vis_cfg.get("task", "zero-shot-object-detection")
        port = vis_cfg.get("port", 5002)
        
        env["VISION_MODEL_ID"] = model
        env["VISION_TASK"] = task
        env["PORT"] = str(port)
        p = subprocess.Popen([gunicorn_path, "-w", "1", "--threads", "4", "--bind", f"127.0.0.1:{port}", "--timeout", "120", "scripts.run_vision_server:app"], env=env)
        processes.append(p)
    elif vision_server_type != "none":
        logger.warning(f"⚠️ Tipo de servidor de visión no configurado: {vision_server_type}")
    
    # Esperar a que el motor visión inicialice
    if vision_server_type != "none":
        wait_for_port(port)
    
    # ==========================================
    # 3. Start API Server (Gunicorn)
    # ==========================================
    logger.info("🚀 Iniciando Flask API Server (Gunicorn)...")
    srv_cfg = api_config.get("server", {})
    host = srv_cfg.get("host", "0.0.0.0")
    port = str(srv_cfg.get("port", 5000))
    workers = str(srv_cfg.get("workers", 4))
    threads = str(srv_cfg.get("threads", 8))
    
    p = subprocess.Popen([gunicorn_path, "-w", workers, "--threads", threads, "--bind", f"{host}:{port}", "src.api.app:app"])
    processes.append(p)
    
    logger.info("✅ ¡Ecosistema completo corriendo! (Presiona Ctrl+C para apagar todos los servicios)")
    
    # Wait for processes indefinitely
    try:
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        pass # Se maneja mediante atexit automáticamente

if __name__ == "__main__":
    main()
