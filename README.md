# 🧠 Framework Universal de Microservicios de IA

Este proyecto es un **Framework de Orquestación Asíncrona de Inteligencia Artificial**, diseñado para unificar modelos masivos de lenguaje (LLMs), visión computacional analítica y generación multimedia bajo una única y robusta API RESTful. Su diseño prioriza la modularidad, la seguridad, la escalabilidad Multi-GPU y la eficiencia en producción.

---

## ✨ Características Principales (Novedades)

* 🛡️ **Seguridad:** Sistema de autenticación de claves criptográficas almacenadas en hashes (SHA-256) dentro de SQLite (`config/auth.db`). Las contraseñas de los usuarios jamás se exponen.
* 🚦 **Defensa Anti-DoS y Rate Limiting:** Implementado con `Flask-Limiter` en memoria y límite de payloads (50MB máximo) para prevenir cuelgues por desbordamiento (OOM). Soporta Reverse Proxies (`ProxyFix`) correctamente.
* 🚀 **Topología de Red Blindada:** Los motores internos de IA (Visión, Multimedia, LLM) escuchan estrictamente en `127.0.0.1`, siendo accesibles únicamente a través de las rutas sanitizadas de la puerta de enlace (`app.py`).
* ⏳ **Escaneo de Puertos Inteligente:** Eliminados los *sleeps* obsoletos. El sistema usa un *pinging dinámico* a nivel de *socket* para inicializar la API exactamente en el milisegundo en el que los modelos pesados terminan de cargar en la GPU.
* 🖥️ **Escalabilidad Multi-GPU (Out-of-the-Box):** Soporte automático de fragmentación de modelos (`device_map="auto"`) para LLMs grandes usando `accelerate`, y balanceo de carga para Generación de Imágenes mediante el despliegue de múltiples *workers* de Gunicorn asignados a distintas GPUs vía `CUDA_VISIBLE_DEVICES`.

---

## 🏗️ Arquitectura del Sistema

La arquitectura está basada en microservicios internos administrados por un proceso padre (El Orquestador). Se divide en cuatro grandes pilares:

### 1. El Orquestador (`scripts/orchestrator.py`)
Es el corazón del ecosistema. Su responsabilidad no es procesar IA, sino administrar procesos.
- Lee los archivos de configuración `.yaml`.
- Determina qué motores encender o apagar según las instrucciones del usuario.
- Levanta servidores internos `Gunicorn` súper rápidos.
- **Sistema Failsafe (Anti-colapso)**: Utiliza el módulo `atexit` para garantizar que, sin importar cómo se cierre el sistema (Ctrl+C, crash de Python), todos los subprocesos mueran ordenadamente, liberando los puertos y la VRAM de la máquina.

### 2. El API Gateway (`src/api/app.py`)
Es la puerta de enlace orientada al cliente, construida con Flask Asíncrono y servida para producción vía **Gunicorn**.
- **Autenticación Multi-Usuario:** Intercepta todas las peticiones requiriendo cabeceras `X-API-KEY` o `Authorization: Bearer`.
- **Validación Estricta**: Usa `Pydantic` para validar esquemas de entrada. 
- **Estandarización REST Pura**: Rutas diseñadas bajo el esquema estándar de recursos (sustantivos):
  - `POST /v1/chat/completions` (Compatible con OpenAI API)
  - `POST /v1/chat/completions/batch`
  - `POST /v1/media/generations`
  - `POST /v1/vision/analyses`

### 3. Motores de Inferencia (Los Cerebros)
El código de los motores está estrictamente separado por su naturaleza funcional en `scripts/run_*`:
* **Módulo de Texto (`src/text`)**: Especialista en lenguaje natural. Soporta **Ollama** o **HuggingFace Pipeline nativa** (`run_hf_text_server.py`).
* **Módulo Multimedia (`src/media`)**: Especialista en crear contenido generativo (Píxeles y Audio). Impulsado por `diffusers` (`run_media_server.py`).
* **Módulo de Visión (`src/vision`)**: Especialista en entendimiento y análisis visual (Detección Zero-Shot, Segmentación, OCR) (`run_vision_server.py`).

### 4. Sistema de Configuración (`config/`)
La lógica de negocio está totalmente separada de la configuración.
- `api.yaml`: Permite encender o apagar motores (ej. `none`).
- `llm.yaml`, `media.yaml`, `vision.yaml`: Parámetros específicos de cada motor (ej. modelo exacto de HuggingFace, puertos internos).

---

## 🎯 Tareas Soportadas (Tasks)

El framework es agnóstico y permite configurar las tareas directamente en los archivos `.yaml` (`config/llm.yaml`, `config/media.yaml`, `config/vision.yaml`).

**Para Modelos de Texto (`llm.yaml`):**
* `text-generation`: Generación de lenguaje natural estándar (Llama, Mistral).
* `image-text-to-text`: Para Modelos de Visión-Lenguaje (VLMs como LLaVA).

**Para Modelos Multimedia (`media.yaml`):**
* `text-to-image`: Generación de imágenes (ej. Stable Diffusion).
* `image-to-image`: Modificación de imágenes base.
* `text-to-video`: Generación de video desde cero.
* `image-to-video`: Animación de imágenes (ej. Stable Video Diffusion).
* `text-to-audio`: Efectos de sonido o música (ej. AudioLDM).

**Para Modelos de Visión (`vision.yaml`):**
*Soporta nativamente los pipelines de HuggingFace transformers, incluyendo:*
* `zero-shot-object-detection`: Detección de objetos con texto libre (GroundingDINO).
* `object-detection`: Detección con bounding boxes pre-entrenados.
* `image-classification`: Clasificación tradicional (ResNet).
* `zero-shot-image-classification`: Clasificación dinámica sin entrenamiento (CLIP).
* `image-segmentation`: Máscaras de píxeles exactas (DETR, Mask2Former).
* `depth-estimation`: Mapas de profundidad 3D.

---

## 🚀 Cómo Empezar (Setup Rápido)

1. **Instalar Dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Crear tu Llave de Acceso (API Key):**
   Tu servidor ahora está protegido. Debes crear una llave antes de encenderlo:
   ```bash
   python scripts/manage_keys.py create "admin"
   ```
   *(Copia la llave secreta generada en pantalla, empezará con `sk-...`)*

3. **Arrancar el Servidor:**
   ```bash
   python scripts/orchestrator.py
   ```

4. **Hacer tu Primera Petición:**
   ```bash
   curl -X POST http://localhost:5000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -H "X-API-KEY: sk-tu_llave_secreta" \
     -d '{"messages": [{"role": "user", "content": "Hola mundo"}]}'
   ```

---

## 🔐 Gestión de Accesos y Usuarios

El sistema incluye una herramienta CLI nativa para administrar de forma segura quién puede usar tu infraestructura de Inteligencia Artificial:

- **Listar Usuarios Activos:**
  ```bash
  python scripts/manage_keys.py list
  ```
- **Revocar (Banear) Acceso:**
  ```bash
  python scripts/manage_keys.py revoke "admin"
  ```

---

## 🛠️ Escalabilidad Continua (Patrón Factory)

El código interno usa intensivamente el patrón de diseño `Factory` (Fábrica) en `src/`. Esto significa que el orquestador maestro y el API Gateway están **completamente desacoplados** del motor real de inferencia subyacente. 
Si el día de mañana deseas integrar un nuevo framework (ej. vLLM, TensorRT, o Groq API), simplemente creas un nuevo cliente bajo la fábrica (ej. `vllm_client.py`) sin tocar ni una sola ruta de `app.py`. El servidor es agnóstico y a prueba de obsolescencia futura.
