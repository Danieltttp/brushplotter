# brushplotter

Aplicación gráfica para pintar con acuarela, acrílico o tinta usando plotters
NextDraw y AxiDraw. Soluciona el problema fundamental del software estándar
(diseñado para rotuladores) introduciendo recarga automática de pintura,
soporte multi-color con pausas para cambio, calibración asistida, y
reanudación robusta tras interrupciones.

**Estado:** pre-alpha (v0.0.1). Núcleo y simulador funcionales. GUI en
desarrollo. Hardware testeado: Bantam Tools NextDraw.

## Por qué existe

El software estándar de los plotters (extensión de Inkscape, CLI de Bantam
Tools) asume flujo de tinta infinito. Con un pincel cargado de pintura, el
plotter dibuja sin parar y el pincel se seca a los pocos centímetros,
arruinando el lienzo.

`brushplotter` intercepta el control de la máquina vía la API Python: calcula
la distancia recorrida en tiempo real, y cuando supera un límite configurable,
detiene el dibujo, va al tintero, simula gestos humanos de recarga (sumergir,
remover, asentar) y vuelve al punto exacto para continuar.

## Arquitectura

```
brushplotter/
├── core/         Lógica pura: SVG, modelo de datos, geometría. Sin Qt, sin hardware.
├── hardware/     Controlador del plotter (real + simulador).
├── workers/      QThread que ejecuta la pintura sin congelar la GUI.
├── ui/           PySide6: ventana principal, calibración, jog.
└── tests/        Tests del core y simulador.
```

Separación estricta de capas: la GUI nunca habla con el hardware directamente,
solo con `workers/` mediante señales Qt. El controlador es una interfaz
abstracta; el simulador permite desarrollo y CI sin plotter físico.

## Instalación

```bash
git clone <repo>
cd brushplotter
pip install -e ".[dev]"
```

Para conectar hardware real, instalar adicionalmente el SDK del plotter:

```bash
# NextDraw (Bantam Tools)
pip install https://software-download.bantamtools.com/nd/api/nextdraw_api.zip

# o AxiDraw clásico
pip install https://cdn.evilmadscientist.com/dl/ad/public/AxiDraw_API.zip
```

## Uso

### Aplicación gráfica (en desarrollo)

```bash
brushplotter
```

### Script legacy (versión corregida del script original)

`scripts/pintar.py` mantiene el flujo CLI de la guía original, con todos
los bugs detectados resueltos. Útil mientras la GUI está en desarrollo.

### Desarrollo sin plotter

```bash
python -m brushplotter.scripts.demo_simulado
```

Demuestra el flujo completo (carga SVG → asigna colores → ejecuta pintura)
sobre el simulador. Ejecuta los tests:

```bash
pytest
```

## Diferencias con el script original

| Aspecto | Script original | brushplotter |
|---|---|---|
| Curvas Bézier | Descartadas silenciosamente | Aplanadas con muestreo |
| Segmentos largos | Pueden exceder MAX_DRAW_DIST | Subdivididos preventivamente |
| Reanudación | Por número de trazo (frágil) | Por estado JSON serializado |
| Multi-color | No soportado | Capas SVG + cambio con pausa |
| Calibración | Manual con regla | Jog interactivo en GUI |
| Errores genéricos | Motores quedan energizados | Apagado de emergencia automático |
| Threading | Bloqueante (`time.sleep`) | QThread + señales |

## Licencia

GPL-3.0-or-later. Pendiente de confirmación por el autor.

## Autoría

Concepto y dirección: Daniel García Andújar.
Desarrollo: Daniel García Andújar con asistencia técnica.
