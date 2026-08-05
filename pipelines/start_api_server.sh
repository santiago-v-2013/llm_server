#!/bin/bash
# Script para iniciar el servidor API en modo Producción (Alta Concurrencia)
# Utiliza Gunicorn en lugar del servidor de desarrollo de Flask.

# Asegurarse de estar en la raíz del proyecto (para que scripts.run_api_server sea encontrado)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

# Cargar el archivo .env si existe
if [ -f .env ]; then
    # Exportar las variables saltándose los comentarios
    export $(grep -v '^#' .env | xargs)
fi

# Si se definió un entorno conda en el .env, activarlo
if [ -n "$CONDA_ENV" ]; then
    echo "🐍 Activando entorno conda: $CONDA_ENV"
    eval "$(conda shell.bash hook)"
    conda activate "$CONDA_ENV"
fi

echo "🚀 Iniciando servidor API LLM en modo Producción..."
echo "Configuración: 4 Workers, 8 Threads por Worker"
echo "Escuchando en: http://0.0.0.0:5000"

# Ejecutar el Orquestador que prende motores y API automáticamente
python scripts/orchestrator.py
