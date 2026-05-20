# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/).

## [0.0.4] — 2026-05-20

### Añadido
- **Panel de control manual** (`Ctrl+M` o "Control manual…" en la toolbar):
  jog X/Y con flechas del teclado, paso configurable (0.1/1/5/10 mm),
  pen up/down, ir a Home, ir a tintero seleccionado, probar ritual de
  recarga sin pintar, apagar/encender motores.
- **Selector de modelo de plotter** en la toolbar: 6 modelos
  (NextDraw 8511/1117/2234, AxiDraw V3/XLX/A3). Cambia los límites
  visuales del lienzo dinámicamente.
- **Dimensiones físicas en cm** mostradas tras cargar un SVG.
- **8 nuevos tests** del ManualControlWorker (jog, home, dip test, pen,
  motors). Total: 28 tests verdes.

### Cambiado
- Nombre del color por defecto: ahora "Único (nombre-del-archivo)" en
  lugar del antiestético "Color por defecto (sin stroke en SVG)".
- Color hex por defecto cambiado de #000000 a #222222 (más visible en
  el preview sin ser negro puro).

### Por hacer (v0.0.5)
- Cambio masivo a cm en toda la UI (calibración, recarga, etc.)
- Validación visual "¿cabe en la cama?" con preview a escala real
- Selector de escala/encaje (50%, 100%, ajustar a cama)
- Selector de orientación A1/A3 (apaisado/vertical)
- Soporte de **estación de agua** (acuarela): cada color con water_station opcional
- Preferencias persistentes (QSettings)

## [0.0.3] — 2026-05-20

### Añadido
- Diálogo de edición manual de tinteros (icono ✎ en el panel).
- Diagnóstico explícito cuando una sesión iría sin pintar nada.
- Fallback de color por defecto cuando el SVG no tiene strokes.

### Cambiado
- Ya no se descarta `stroke="black"` como color válido.
- Fuentes monospace explícitas (`Menlo`, `Courier New`) para evitar
  warning de Qt sobre fuente `Monospace` inexistente.

## [0.0.2] — 2026-05-20

### Añadido
- GUI funcional con PySide6 (ventana principal del primer mockup).
- `ui/canvas_view.py`, `ui/main_window.py`, `ui/inkwell_panel.py`.
- `hardware/nextdraw_controller.py` real envolviendo el SDK.
- Punto de entrada `python -m brushplotter [--hardware]`.

## [0.0.1] — 2026-05-20

### Añadido
- Núcleo, simulador, worker, CLI legacy. 19 tests verdes.
