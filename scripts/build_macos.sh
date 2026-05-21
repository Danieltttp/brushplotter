#!/usr/bin/env bash
# Build script para brushplotter en macOS.
#
# Uso:
#   bash scripts/build_macos.sh         # build normal
#   bash scripts/build_macos.sh --dmg   # build + crear DMG distribuible

set -euo pipefail

# Esta carpeta scripts/ está DENTRO del paquete brushplotter/.
# El PROJECT_ROOT es la carpeta del paquete (un nivel por encima de scripts/).
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# ── Comprobaciones previas ──
if [ -z "${VIRTUAL_ENV:-}" ]; then
    echo "⚠️  No detecto un venv activo."
    echo "Activa primero el entorno: source .venv/bin/activate"
    exit 1
fi

echo "→ Proyecto: $PROJECT_ROOT"
echo "→ Python: $(which python) ($(python --version))"

# ── PyInstaller ──
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "→ Instalando PyInstaller..."
    pip install pyinstaller
fi

# ── Icono ──
ICON_SRC="$PROJECT_ROOT/resources/brushplotter.png"
ICON_DST="$PROJECT_ROOT/resources/brushplotter.icns"
if [ -f "$ICON_SRC" ] && [ ! -f "$ICON_DST" ]; then
    echo "→ Generando icono .icns desde PNG..."
    bash "$PROJECT_ROOT/scripts/make_icns.sh" "$ICON_SRC" "$ICON_DST"
fi

# ── Limpiar builds previos ──
echo "→ Limpiando builds anteriores..."
rm -rf build dist

# ── Ejecutar PyInstaller ──
echo "→ Compilando bundle .app... (puede tardar 2-3 minutos)"
pyinstaller --clean --noconfirm "$PROJECT_ROOT/brushplotter.spec"

# ── Verificar resultado ──
APP_PATH="$PROJECT_ROOT/dist/brushplotter.app"
if [ ! -d "$APP_PATH" ]; then
    echo "❌ Build falló: no existe $APP_PATH"
    exit 1
fi

echo ""
echo "✓ Build completo: $APP_PATH"
echo "  Tamaño: $(du -sh "$APP_PATH" | cut -f1)"
echo ""
echo "Para probarla:"
echo "  open $APP_PATH"

# ── DMG opcional ──
if [ "${1:-}" = "--dmg" ]; then
    DMG_PATH="$PROJECT_ROOT/dist/brushplotter-0.0.8.dmg"
    echo "→ Creando DMG distribuible..."

    if command -v create-dmg >/dev/null 2>&1; then
        create-dmg \
            --volname "brushplotter 0.0.8" \
            --volicon "$ICON_DST" \
            --window-pos 200 120 \
            --window-size 600 400 \
            --icon-size 100 \
            --icon "brushplotter.app" 175 200 \
            --hide-extension "brushplotter.app" \
            --app-drop-link 425 200 \
            "$DMG_PATH" \
            "$APP_PATH" || true
    else
        echo "  (create-dmg no instalado, usando hdiutil)"
        echo "  Consejo: brew install create-dmg para mejor presentación"
        hdiutil create -volname "brushplotter 0.0.8" \
            -srcfolder "$APP_PATH" \
            -ov -format UDZO \
            "$DMG_PATH"
    fi

    if [ -f "$DMG_PATH" ]; then
        echo ""
        echo "✓ DMG creado: $DMG_PATH"
        echo "  Tamaño: $(du -sh "$DMG_PATH" | cut -f1)"
    fi
fi
