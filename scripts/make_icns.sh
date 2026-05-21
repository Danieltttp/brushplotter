#!/usr/bin/env bash
# Genera un .icns macOS válido desde un PNG cuadrado.
#
# Uso: bash make_icns.sh input.png output.icns
#
# Requiere herramientas nativas de macOS: sips, iconutil.

set -euo pipefail

SRC="${1:-}"
DST="${2:-}"

if [ -z "$SRC" ] || [ -z "$DST" ]; then
    echo "Uso: $0 input.png output.icns"
    exit 1
fi

if [ ! -f "$SRC" ]; then
    echo "❌ No existe $SRC"
    exit 1
fi

ICONSET=$(mktemp -d)
trap "rm -rf $ICONSET" EXIT

# Renombrar a .iconset (requerido por iconutil)
mv "$ICONSET" "${ICONSET}.iconset"
ICONSET="${ICONSET}.iconset"
trap "rm -rf $ICONSET" EXIT

echo "→ Generando tamaños de icono..."
sips -z 16 16     "$SRC" --out "$ICONSET/icon_16x16.png"     >/dev/null
sips -z 32 32     "$SRC" --out "$ICONSET/icon_16x16@2x.png"  >/dev/null
sips -z 32 32     "$SRC" --out "$ICONSET/icon_32x32.png"     >/dev/null
sips -z 64 64     "$SRC" --out "$ICONSET/icon_32x32@2x.png"  >/dev/null
sips -z 128 128   "$SRC" --out "$ICONSET/icon_128x128.png"   >/dev/null
sips -z 256 256   "$SRC" --out "$ICONSET/icon_128x128@2x.png">/dev/null
sips -z 256 256   "$SRC" --out "$ICONSET/icon_256x256.png"   >/dev/null
sips -z 512 512   "$SRC" --out "$ICONSET/icon_256x256@2x.png">/dev/null
sips -z 512 512   "$SRC" --out "$ICONSET/icon_512x512.png"   >/dev/null
sips -z 1024 1024 "$SRC" --out "$ICONSET/icon_512x512@2x.png">/dev/null

echo "→ Compilando .icns..."
iconutil -c icns "$ICONSET" -o "$DST"

echo "✓ Icono generado: $DST"
