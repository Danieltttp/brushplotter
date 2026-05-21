# Changelog

## [0.0.7] — 2026-05-21  (preferencias persistentes)

### Añadido
- **Módulo `core/preferences.py`**: wrapper tipado sobre `QSettings`.
  Persistencia de todos los ajustes del usuario entre sesiones.
- **Lo que se guarda automáticamente** (sin que tengas que pulsar
  "Guardar"):
  - Modelo de plotter seleccionado.
  - Material activo (Acuarela / Acrílico / Tinta).
  - Velocidad y distancia de recarga (en cm).
  - Posiciones de tinteros (GLOBALES, por nombre del color).
  - Posición de la estación de agua (global).
  - Estado de los dos checkboxes de agua.
  - Geometría de la ventana principal (tamaño + posición).
  - Última carpeta usada en "Abrir SVG".
- **`apply_calibration_to_session`**: cuando cargas un SVG, si algún
  color coincide en nombre con uno calibrado previamente, recupera
  su posición automáticamente. Una vez calibras tu setup físico,
  queda recordado para siempre.
- **Menú "Preferencias > Restablecer preferencias…"**: borra todos los
  ajustes guardados con confirmación previa. Útil si algo se corrompe
  o quieres empezar limpio.
- **10 nuevos tests** del módulo de preferencias (defaults, roundtrip
  de escalares, upsert/recuperación de tinteros, ciclo del agua,
  aplicación a sesión, reset). Total: 58 verde.

### Ubicación de las preferencias
- **macOS**: `~/Library/Preferences/com.danielgarciaandujar.brushplotter.plist`
- **Linux**: `~/.config/Daniel García Andújar/brushplotter.conf`
- **Windows**: registro bajo `HKEY_CURRENT_USER\Software\...`

### Por hacer (v0.0.8)
- Empaquetado .app/.icns para macOS con py2app o briefcase.
- Bundle identifier, icono, permisos USB/serial.

## [0.0.6.4] — 2026-05-21
- Botón de configurar agua en fila propia, garantiza visibilidad.

## [0.0.6.3] — 2026-05-21
- Replicar layout del item de tintero en estación de agua.

## [0.0.6.2] — 2026-05-21
- Fix botón agua, "+ Añadir tintero" conectado, material se aplica al session.

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
