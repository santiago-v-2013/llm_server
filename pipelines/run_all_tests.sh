#!/bin/bash

# Pipeline para ejecutar toda la suite de pruebas End-to-End

set -e # Detener el script si alguna prueba falla

# Determinar el directorio base del proyecto
WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="$WORKSPACE_DIR/test"

echo "=================================================="
echo "🚀 INICIANDO PIPELINE DE PRUEBAS COMPLETO"
echo "=================================================="

cd "$WORKSPACE_DIR"

# Asegurarse de que el entorno esté limpio
if [ -d "$WORKSPACE_DIR/config_backup" ]; then
    echo "⚠️ Restaurando backups huérfanos de pruebas anteriores..."
    cp -r "$WORKSPACE_DIR"/config_backup/* "$WORKSPACE_DIR"/config/
    rm -rf "$WORKSPACE_DIR/config_backup"
fi

# Buscar todos los scripts de prueba que empiecen con "test_" y ejecutarlos
TEST_FILES=$(ls "$TEST_DIR"/test_*.py | sort)

TOTAL_TESTS=$(echo "$TEST_FILES" | wc -w)
CURRENT_TEST=1

for test_file in $TEST_FILES; do
    filename=$(basename "$test_file")
    echo ""
    echo "▶️ Ejecutando prueba ($CURRENT_TEST/$TOTAL_TESTS): $filename"
    
    # Ejecutar la prueba
    # Usamos PYTHONPATH para que los scripts encuentren base_runner
    PYTHONPATH="$TEST_DIR" python "$test_file"
    
    # Verificar el código de salida
    if [ $? -eq 0 ]; then
        echo "✅ $filename completado exitosamente."
    else
        echo "❌ $filename FALLÓ. Deteniendo el pipeline."
        exit 1
    fi
    
    CURRENT_TEST=$((CURRENT_TEST + 1))
done

echo ""
echo "=================================================="
echo "🎉 PIPELINE COMPLETADO EXITOSAMENTE (100% PASS) 🎉"
echo "=================================================="
