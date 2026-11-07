# Desarrollo

Trabajar en Windows con Python 3.11 o posterior. Crear un entorno virtual e instalar el proyecto con sus herramientas:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

El código pertenece a `src/windows_computer_use/`; las pruebas a `tests/`. Las dependencias se definen únicamente en `pyproject.toml`. `requirements.txt` conserva compatibilidad con instaladores anteriores y delega en ese archivo.

Antes de entregar un cambio:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/smoke_check.py
```

Las pruebas deben sustituir las acciones de teclado y ratón para no modificar el escritorio. Usar el fixture de estado temporal para no alterar sesiones reales. La prueba MCP crea su propia carpeta temporal y comprueba el protocolo stdio desde otra carpeta de trabajo.

El proceso MCP reserva stdout para el protocolo. Enviar cualquier diagnóstico futuro a stderr o a un registro local; nunca imprimir mensajes sueltos en stdout desde el servidor.

Conservar nombres y parámetros de herramientas existentes. La cancelación permanece detenida hasta una solicitud explícita de continuación. Una importación del paquete no debe iniciar el indicador ni escribir estado.

Para revisar el indicador manualmente, fuera de una sesión de control activa:

```powershell
.\.venv\Scripts\windows-computer-use-preview.exe --preview
```

Pulsar Detener al terminar la revisión. La vista previa comparte el estado de sesión predeterminado; se puede aislar con `WINDOWS_COMPUTER_USE_STATE_DIR`.
