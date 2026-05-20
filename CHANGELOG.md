# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/).

## [0.0.5] — 2026-05-20

### Añadido
- **Panel de configuración de salida** (pestaña "Salida" en el panel
  izquierdo): selector de modelo de plotter + orientación
  (apaisado/vertical), tamaño de la cama en cm, escala con presets
  (25 / 50 / 100% / Ajustar) + slider continuo (1-400%) + numérico.
- **Indicador visual de encaje**: badge verde "Cabe en la cama",
  amarillo "Cabe justo" si queda <1 cm de margen, rojo "No cabe:
  excede N cm" cuando se sale. Bloquea el inicio de la sesión si no
  cabe.
- **Centrado automático** del dibujo en la cama (toggle), o posición
  manual en cm cuando se desactiva.
- **Detección de dimensiones nativas del SVG** (atributos width/height
  con soporte de mm/cm/in/pt/px). Si no las tiene, usa el bounding box
  asumiendo 96 DPI.
- Catálogo `hardware/paper_sizes.py` con A0-A5, Carta, Tabloide, Legal
  + clase `Orientation`.
- Módulo `core/units.py` que centraliza todas las conversiones
  (cm/mm/in) y el formato de presentación.
- Módulo `core/canvas_layout.py` con la lógica de encaje + función
  `fit_to_bed_scale` para "Ajustar".
- **13 nuevos tests** del módulo de layout (encaje, escala, centrado,
  overflow, mensajes). Total: 41 tests verdes.

### Cambiado
- El panel izquierdo ahora tiene **pestañas**: "Salida" (configuración
  de cama y escala) y "Material y tinteros" (lo que había antes).
- "Recarga cada" ahora se muestra en cm (antes pulgadas).
- El selector de modelo de plotter sale de la barra superior y va al
  panel de salida, donde encaja mejor con orientación y tamaño.

### Por hacer (v0.0.6)
- Estación de agua para acuarela (modelo + ritual + preview)
- Preferencias persistentes (QSettings)
- Mejoras visuales del preview: regla, cotas, indicador de margen

## [0.0.4] — 2026-05-20
[…]
