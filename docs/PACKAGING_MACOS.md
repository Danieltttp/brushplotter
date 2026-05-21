# Guía de empaquetado y distribución (macOS)

Cómo convertir el código de brushplotter en una aplicación `.app` que se
puede arrastrar a /Applications y distribuir a otros artistas.

## Resumen rápido

```bash
# Una sola línea:
source .venv/bin/activate
bash scripts/build_macos.sh --dmg
```

Esto genera:
- `dist/brushplotter.app` — bundle macOS, ejecutable con doble clic.
- `dist/brushplotter-0.0.8.dmg` — instalador distribuible.

## Requisitos previos

- macOS (no se puede compilar para Mac desde Linux/Windows).
- Python 3.12 instalado.
- Un venv con todas las dependencias del proyecto:
  ```bash
  source .venv/bin/activate
  pip install -r requirements.txt   # o instalar manualmente
  pip install https://software-download.bantamtools.com/nd/api/nextdraw_api.zip
  ```
- (Opcional, para mejor DMG) `brew install create-dmg`.

## Personalizar el icono

El icono por defecto es funcional pero sobrio. Para reemplazarlo:

1. Diseña tu icono como **PNG cuadrado de 1024×1024** (puede ser RGBA con
   transparencia). Sustituye `resources/brushplotter.png`.
2. Borra el `.icns` previo si existía: `rm resources/brushplotter.icns`.
3. Vuelve a lanzar `build_macos.sh` — regenerará el `.icns` desde tu PNG.

Si tienes Inkscape, también puedes editar `resources/brushplotter.svg` y
re-exportar a PNG 1024×1024 antes de compilar.

## Distribución sin firma de Apple Developer

Si **no** tienes una cuenta de Apple Developer (~99€/año), el bundle no
estará firmado. Esto **no impide distribuirlo**, pero:

- macOS marcará la app como "no identificada" la primera vez.
- El usuario verá un mensaje al intentar abrirla: "no se puede abrir
  porque proviene de un desarrollador no identificado".
- **Solución para el usuario final**: click derecho sobre el `.app` →
  "Abrir" → confirmar en el diálogo. Solo la primera vez.

Recomendación práctica: incluye estas instrucciones en el DMG con un
README.

## Distribución con firma de Apple Developer

Si tienes cuenta de Apple Developer, puedes firmar y notarizar el bundle
para que se abra sin avisos. Pasos resumidos:

```bash
# 1. Encontrar tu identidad de firma
security find-identity -v -p codesigning

# 2. Firmar el bundle (después de build)
codesign --deep --force --options runtime \
    --entitlements resources/entitlements.plist \
    --sign "Developer ID Application: Tu Nombre (TEAMID)" \
    dist/brushplotter.app

# 3. Notarizar
xcrun notarytool submit dist/brushplotter-0.0.8.dmg \
    --apple-id tu-email@example.com \
    --team-id TEAMID \
    --password "app-specific-password" \
    --wait

# 4. Sellar la notarización en el DMG
xcrun stapler staple dist/brushplotter-0.0.8.dmg
```

## Problemas frecuentes

### "ModuleNotFoundError: No module named 'X'" al arrancar la app

PyInstaller no detectó esa dependencia. Añádela a `hiddenimports` en
`brushplotter.spec` y recompila.

### El bundle es enorme (>500 MB)

Probable: vpype está arrastrando dependencias científicas pesadas. Opciones:

1. **Excluir explícitamente** módulos no usados en `brushplotter.spec`,
   sección `excludes=[]`.
2. **Distribuir sin vpype** (que el usuario lo instale aparte), removiendo
   la dependencia y haciendo el aplanado externamente con CLI.
3. Aceptarlo: 200-300 MB es normal para una app PySide6 con vpype.

### El plotter no se conecta dentro de la app

macOS necesita permitir el acceso al puerto USB serial. La primera vez:

1. Conecta el plotter al Mac.
2. Lanza la app y prueba a abrir Control Manual.
3. macOS pedirá autorización para acceder a "dispositivo USB". Acepta.
4. Si no aparece el diálogo: **Preferencias del Sistema → Privacidad y
   seguridad → Apps con acceso a dispositivos USB**. Añade brushplotter
   manualmente.

### "App is damaged, can't be opened" al recibir el DMG

Esto pasa cuando el sistema operativo del usuario marca como "cuarentena"
una app no firmada descargada de internet. Solución para el usuario:

```bash
xattr -cr /Applications/brushplotter.app
```

Después se abre normalmente. Esto está documentado por Apple y es esperable
en software no firmado.

## Tamaño aproximado del bundle

| Componente | Tamaño |
|---|---|
| Python embebido | ~30 MB |
| PySide6 (Qt6) | ~80 MB |
| svgpathtools + numpy | ~40 MB |
| vpype + shapely | ~80 MB |
| Resto | ~10 MB |
| **Total `.app`** | **~240 MB** |
| **Total `.dmg` (comprimido)** | **~150 MB** |

## Builds reproducibles

Para builds estables y reproducibles entre versiones:

```bash
# Congela tus dependencias exactas
pip freeze > requirements-frozen.txt

# Usa esa misma versión en todos los builds futuros
pip install -r requirements-frozen.txt
```

Esto incluye PySide6, PyInstaller y todas las dependencias indirectas,
así que un futuro `bash scripts/build_macos.sh` da exactamente el mismo
binario.
