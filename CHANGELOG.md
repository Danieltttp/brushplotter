# Changelog

## [0.0.5.1] — 2026-05-20  (parche de proyección y rotación)

### Corregido
- **El SVG ahora se proyecta usando su viewBox declarado**, no el
  bounding box de los trazos. Si dibujas en un lienzo A1 con margen
  blanco alrededor, ese margen se respeta. Antes los trazos se
  "encajaban al lienzo de salida" y se ampliaban erróneamente.
- **El toggle Apaisado/Vertical ahora rota el dibujo, no la cama del
  plotter.** La cama del plotter es física y no rota. Si tu NextDraw
  2234 tiene X=86 cm (lado largo) e Y=59 cm (lado corto), siempre será
  así. Lo que rota es el dibujo dentro: si pones un A1 en vertical,
  no cabrá y el indicador se pondrá rojo informativamente.
- **Etiquetas de orientación física en el preview**: "⌂ Home (0,0)" en
  esquina superior izquierda, "X — N cm →" en la parte superior
  derecha, "↓ Y — N cm" en el lateral. Así se ve claro cómo el preview
  mapea al plotter físico sobre tu mesa.

### Detalles técnicos
- Parsing del atributo `viewBox` del SVG en `svg_loader`.
- `CanvasGeometry.rotation_degrees` (0 o 90) aplicado en
  `svg_to_physical`.
- Nuevos métodos `physical_width`, `rotated_physical_width/height`.
- 2 tests nuevos: `test_session_respects_full_canvas_not_bounding_box`
  y `test_session_rotation_90_degrees`. Total: 43 verde.

## [0.0.5] — 2026-05-20

### Añadido
- Panel de configuración de salida con escala, encaje y orientación.
- Indicador visual de encaje (verde / amarillo / rojo).
- Catálogo de tamaños de papel y módulo de layout.
- 13 tests del módulo de layout. Total: 41 verde.

## [0.0.4] — 2026-05-20
- Control manual del cabezal (jog, home, dip test, motors).

## [0.0.3] — 2026-05-20
- Edición manual de tinteros.

## [0.0.2] — 2026-05-20
- GUI inicial con PySide6.

## [0.0.1] — 2026-05-20
- Núcleo, simulador, worker, CLI legacy.
