# Construcción y distribución

El proyecto utiliza `pyproject.toml`, estructura `src/` y puntos de entrada instalables según las [guías de Python Packaging](https://packaging.python.org/en/latest/guides/distributing-packages-using-setuptools/).

## Preparar una entrega

1. Ajustar la versión en `pyproject.toml` y `src/windows_computer_use/__init__.py`, y actualizar `CHANGELOG.md`.
2. Instalar `.[dev]` en un entorno virtual.
3. Ejecutar Ruff, pytest y `scripts/smoke_check.py`.
4. Ejecutar `python scripts/build_release.py` con ese Python.
5. Probar la instalación del wheel recibido desde una carpeta diferente de la del proyecto.

El constructor produce en `dist/`:

- `windows_computer_use_mcp-VERSION-py3-none-any.whl`: paquete instalable con pip, para Windows.
- `windows_computer_use_mcp-VERSION.tar.gz`: distribución fuente generada por el backend de empaquetado.
- `windows-computer-use-mcp-VERSION-source.zip`: proyecto para extraer, revisar e instalar, con documentación, pruebas y ejemplos.
- `SHA256SUMS.txt`: huellas de los tres archivos de esa versión.

El wheel contiene Python puro; la clasificación de plataforma del proyecto indica Windows y las herramientas usan APIs de Windows. No es compatible con Linux/macOS aunque su nombre de wheel no tenga un ABI nativo.

El ZIP usa una lista explícita de archivos y carpetas. No se empaquetan `.local/`, imágenes de referencia, archivos de estado, configuraciones del usuario, entornos virtuales, cachés ni otras versiones de `dist/`. El constructor revisa también el wheel y el tar.gz para detectar archivos locales indebidos.

## Instalación del receptor

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .\windows_computer_use_mcp-0.2.3-py3-none-any.whl
```

Después se configura el cliente con el Python de ese entorno y los argumentos `-m windows_computer_use`. Ver `examples/mcp_config.json`. No se modifica automáticamente la configuración global de Antigravity.

Para instalar el ZIP fuente, extraerlo, abrir PowerShell en su carpeta y ejecutar los mismos pasos usando `pip install .`.

## Datos de ejecución y actualización

El estado está en `%LOCALAPPDATA%/WindowsComputerUseMCP/overlay_status.json`. Es un dato de ejecución, no un archivo distribuible. `WINDOWS_COMPUTER_USE_STATE_DIR` permite un directorio alternativo, útil para pruebas o instancias aisladas. Utilizar una sola instancia por escritorio en uso normal.

Al reorganizar esta copia de desarrollo, se preservó el estado antiguo en la carpeta de usuario y se guardó un respaldo en `.local/backups/`. Las capturas previas quedaron en `.local/reference-captures/`. Estos archivos permanecen locales.

Para actualizar un entorno instalado, reconectar el cliente después de instalar la versión nueva con pip. El lanzador de compatibilidad permite conservar las configuraciones existentes que apuntan al archivo de la raíz.
