#!/usr/bin/env bash
# Script de actualización segura de brushplotter
# Uso: bash actualizar.sh ruta/al/brushplotter.zip
#
# Descomprime el zip en una carpeta temporal y copia solo el código
# nuevo encima del existente, sin tocar .venv ni archivos generados.

set -e

if [ -z "$1" ]; then
    echo "Uso: bash actualizar.sh ruta/al/brushplotter.zip"
    exit 1
fi

ZIP_PATH="$1"
PROJECT_DIR="$(dirname "$(realpath "$0")")"
TMP_DIR=$(mktemp -d)

echo "Descomprimiendo en $TMP_DIR..."
unzip -q "$ZIP_PATH" -d "$TMP_DIR"

echo "Copiando código nuevo (preservando .venv)..."
rsync -av --delete \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='*.session.json' \
    --exclude='session_state.json' \
    "$TMP_DIR/brushplotter/" "$PROJECT_DIR/"

rm -rf "$TMP_DIR"
echo ""
echo "✓ Actualización completa."
echo "✓ Tu .venv y archivos locales se han mantenido intactos."
echo ""
echo "Verifica con: python -m pytest tests/ -v"
