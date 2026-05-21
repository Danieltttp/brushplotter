# Changelog

## [0.0.8] — 2026-05-21  (empaquetado para distribución macOS)

### Añadido
- **`brushplotter.spec`**: configuración de PyInstaller para generar el
  bundle `.app` de macOS con:
  - Bundle identifier `com.danielgarciaandujar.brushplotter`.
  - Versión, copyright, NSHumanReadableCopyright.
  - Tipo de documento asociado: SVG.
  - `Info.plist` con declaración de uso de Apple Events y `LSMinimumSystemVersion`.
  - Hidden imports declarados: PySide6.QtCore/QtGui/QtWidgets, svgpathtools,
    vpype, shapely, nextdraw.
  - Exclusiones: módulos pesados de PySide6 que no usamos
    (QtNetwork, QtWebEngineCore, QtMultimedia, etc.) para reducir tamaño.
- **`scripts/build_macos.sh`**: script de build automatizado. Limpia,
  compila, opcionalmente genera DMG distribuible.
- **`scripts/make_icns.sh`**: convierte un PNG 1024×1024 en un `.icns`
  multi-resolución usando las herramientas nativas (`sips`, `iconutil`).
- **`resources/brushplotter.svg` y `.png`**: icono base sobrio del
  proyecto (pincelada azul + tierra sobre lienzo, gota de agua).
  Reemplazable por uno propio.
- **`docs/PACKAGING_MACOS.md`**: guía completa de empaquetado y
  distribución, incluyendo:
  - Build sin firma de Apple Developer (con instrucciones para el usuario
    final de "click derecho → Abrir").
  - Build con firma (codesign + notarización) para usuarios con cuenta.
  - Troubleshooting de problemas comunes (ModuleNotFoundError, bundle
    enorme, permisos USB, app dañada por xattr).
  - Tabla de tamaños aproximados.

### Cómo construir tu .app
```bash
source .venv/bin/activate
bash scripts/build_macos.sh --dmg
# Genera dist/brushplotter.app + dist/brushplotter-0.0.8.dmg
```

### Tamaño del bundle resultante
~240 MB (.app), ~150 MB (.dmg comprimido). Normal para PySide6 + vpype.

## [0.0.7] — 2026-05-21
- Preferencias persistentes (QSettings) — plotter, material, calibración,
  ventana, última carpeta. 58 tests verdes.

## [0.0.6.4] — 2026-05-21
- Botón de configurar agua en fila propia.

## [0.0.6.3] — 2026-05-21
- Replicar layout del item de tintero en estación de agua.

## [0.0.6.2] — 2026-05-21
- Fix botón agua, "+ Añadir tintero", material aplica al session.

## [0.0.6.1] — 2026-05-21
- Dos rituales de agua independientes (rápido y profundo).

## [0.0.6] — 2026-05-21
- Estación de agua compartida con ritual de limpieza.

## [0.0.5.1] — 2026-05-20
- Proyección por viewBox; rotación del dibujo.

## [0.0.5] — 2026-05-20
- Panel de configuración de salida con escala, encaje, orientación.

## [0.0.4] — 2026-05-20
- Control manual del cabezal.

## [0.0.3] — 2026-05-20
- Edición manual de tinteros.

## [0.0.2] — 2026-05-20
- GUI inicial con PySide6.

## [0.0.1] — 2026-05-20
- Núcleo, simulador, worker, CLI legacy.
