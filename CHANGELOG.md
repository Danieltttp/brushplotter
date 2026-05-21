# Changelog

## [0.0.6.2] — 2026-05-20  (bugfixes UI agua/material/tinteros)

### Corregido
- **Bug del botón ✎ de la estación de agua no visible**: el item se ha
  rediseñado con layout vertical más claro: cabecera con ✎ siempre
  visible (no condicionada a estar calibrada), coordenadas o aviso
  "⚠ Sin posición — pulsa ✎ para configurar" debajo, y dos checkboxes
  abajo. Ahora siempre hay un camino visible para configurar la
  posición.
- **"+ Añadir tintero" no hacía nada**: la señal `add_requested` del
  panel no estaba conectada. Ahora abre el diálogo de edición con un
  tintero placeholder (color gris, nombre "Tintero N") que el usuario
  puede personalizar y guardar.
- **El selector de Material no cambiaba el comportamiento**: ahora
  cambiar el desplegable aplica el perfil completo al session
  (incluidos `uses_water_before_dip` y `uses_water_on_color_change`),
  y refresca los checkboxes del panel de agua. Antes solo actualizaba
  el spinner de recarga y el slider de velocidad.
- **Mutación accidental del perfil global**: `on_start` reasignaba el
  perfil desde `DEFAULT_PROFILES` (referencia compartida), lo cual
  machacaba los cambios del usuario en los checkboxes Y contaminaba
  el diccionario global. Ahora se usan copias (`dataclasses.replace`).
- Al cargar SVG, el perfil del material actualmente seleccionado en
  el combo se aplica a la nueva sesión (antes siempre se quedaba en
  acuarela aunque tuvieras seleccionado otro material).

### Por hacer (v0.0.7)
- Preferencias persistentes (QSettings).

## [0.0.6.1] — 2026-05-20
- Dos rituales de agua independientes (rápido y profundo).

## [0.0.6] — 2026-05-20
- Estación de agua compartida con ritual de limpieza.

## [0.0.5.1] — 2026-05-20
- Proyección por viewBox; rotación del dibujo; etiquetas físicas.

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
