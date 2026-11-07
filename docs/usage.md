# Windows Computer Use MCP para Antigravity

Control del escritorio de Windows con un indicador discreto y capturas rápidas.

## Indicador de control

- Contorno rojo de 68 píxeles lógicos, que aumenta hasta 100 con el latido, halo y transparencia real por píxel. Puntos suaves aparecen, se desplazan y se difuminan en los bordes. El centro permanece despejado y los clics atraviesan los bordes.
- Barra superior rectangular de 68 píxeles lógicos con el texto **Antigravity is using your computer**, SVG oficial de Antigravity, icono de Gemini, actividad en español y nombre opcional del proyecto.
- Botón **Detener** y atajo **Ctrl+Alt+Esc**. Si termina el proceso del servidor, el indicador también se cierra.
- Bordes en todos los monitores, con coordenadas físicas y compatibilidad con escalado DPI.
- El indicador no solicita foco. En Windows 10 2004 o posterior se solicita su exclusión de las capturas mediante [SetWindowDisplayAffinity](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity).
- Detener bloquea las siguientes acciones, incluidas las capturas y los cambios de foco. Las acciones ya enviadas a Windows pueden terminar. Solo `show_screen_overlay` inicia explícitamente otra sesión.
- PyAutoGUI conserva su parada de emergencia: mover el cursor a una esquina del monitor principal puede interrumpir una acción.

## Instalación y proyectos existentes

Se requiere Windows y Python con Tkinter:

```powershell
python -m pip install -r requirements.txt
python windows_computer_use_mcp.py
```

El servidor utiliza transporte stdio. En la configuración MCP existente de Antigravity, conserva los otros servidores y proyectos y configura este servidor con la ruta absoluta del Python instalado y del archivo `windows_computer_use_mcp.py`. No necesita crear otro proyecto ni abrir otra ventana del editor.

Después de actualizar el código, **reinicia o reconecta este servidor MCP desde Antigravity** para cargar las herramientas nuevas. Un proceso Python que ya estaba iniciado sigue ejecutando el código anterior.

Flujo recomendado para un proyecto ya abierto:

1. Ejecutar `list_open_windows` y localizar la ventana del proyecto.
2. Iniciar `show_screen_overlay(project_name="Mi proyecto")`.
3. Ejecutar `focus_window_by_title(hwnd=...)` con el identificador devuelto. Si un título coincide con varios proyectos, la herramienta devuelve las opciones sin elegir una arbitrariamente.
4. Usar `read_screen` y las herramientas de ratón y teclado.
5. Terminar con `hide_screen_overlay`. Después de una cancelación, esperar una nueva instrucción del usuario antes de iniciar otra sesión.

El nombre del proyecto es una etiqueta de la sesión; no cambia la configuración ni los archivos del proyecto. Las herramientas anteriores mantienen sus nombres y parámetros originales. El estado se guarda en `%LOCALAPPDATA%/WindowsComputerUseMCP/overlay_status.json` y se comparte entre sus clientes: utiliza una sola instancia de este servidor por escritorio. `WINDOWS_COMPUTER_USE_STATE_DIR` permite una carpeta alternativa.

## Lectura de pantalla

`read_screen` entrega una **imagen nativa MCP** y metadatos, evitando enviar la imagen como un bloque de texto base64. La captura reutiliza recursos por hilo, reduce la imagen con interpolación bilineal y no introduce la antigua espera fija de 300 ms al iniciar el indicador.

| Parámetro | Valor predeterminado | Uso |
| --- | --- | --- |
| `max_dimension` | `1600` | Lado máximo de la vista previa. `null` conserva toda la resolución. |
| `quality` | `80` | Calidad JPEG de 40 a 95. |
| `monitor` | `1` | Monitor principal; `0` incluye todo el escritorio. |
| `region` | `null` | Recorte `[left, top, width, height]` en píxeles del escritorio. Útil para leer texto pequeño. |

Para convertir un punto de la vista previa a coordenadas de ratón:

```text
desktop_x = origin_x + preview_x * scale_x
desktop_y = origin_y + preview_y * scale_y
```

Los metadatos incluyen tamaño original, tamaño de vista previa, origen, escalas y `capture_ms` (captura y codificación local; no incluye transporte ni procesamiento del modelo).

`take_screenshot` mantiene la respuesta JSON con `image_base64_jpeg`, `save_path` y el valor predeterminado de 1280 píxeles para clientes existentes. También acepta calidad, monitor y región. Si se proporciona `save_path`, guarda la captura original antes de reducirla.

## Herramientas

- Sesión: `show_screen_overlay`, `resume_screen_control`, `get_control_status`, `hide_screen_overlay`.
- Lectura: `read_screen`, `take_screenshot`, `get_screen_resolution`, `list_open_windows`.
- Ventanas: `focus_window_by_title` (título parcial o `hwnd` exacto).
- Accesibilidad: `inspect_window` y `invoke_control`, mediante pywinauto/UIA. Usar identificadores reales de un snapshot reciente; no inventarlos ni reutilizarlos después de una acción. La ventana debe estar enfocada antes de invocar.
- Ratón: `mouse_move`, `mouse_click`, `mouse_drag`, `mouse_scroll`.
- Teclado: `keyboard_type`, `keyboard_press_key`, `keyboard_hotkey`. La escritura conserva el comportamiento de PyAutoGUI y depende de la distribución del teclado.

### Si aparece `SCREEN_SESSION_STOPPED` o el antiguo `User clicked cancel`

Este mensaje corresponde al estado interno de la sesión MCP. No demuestra que se haya rechazado un diálogo de permisos de Antigravity. No hay que repetir acciones de teclado mientras la sesión siga detenida ni usar la terminal para saltarse la parada.

Cuando el usuario indique «sí», «continúa» o «listo, usa el MCP», llamar primero a `resume_screen_control` y después repetir la acción solicitada. `show_screen_overlay` también reanuda y permite recuperar clientes que todavía no hayan cargado la herramienta nueva. `get_control_status` permite consultar el estado sin reanudarlo. Los permisos propios de Antigravity se gestionan por separado.

## Verificación

```powershell
python -m pip install pytest
python -m pytest -q
```

Las pruebas cubren cancelación persistente, reinicio explícito, estado anterior, coordenadas de regiones y monitores, validación de parámetros, imágenes MCP y títulos de proyectos ambiguos. No envían entradas de ratón o teclado al escritorio.

Vista previa manual (incluye el indicador en las capturas y en el selector de ventanas):

```powershell
python overlay.py --preview
```

## Archivos

- `src/windows_computer_use/overlay.py`: indicador translúcido y botón Detener.
- `src/windows_computer_use/session_state.py`: intercambio atómico del estado.
- `src/windows_computer_use/screen_capture.py`: captura, compresión y coordenadas.
- `src/windows_computer_use/server.py`: servidor y herramientas.
- `tests/`: pruebas de regresión y empaquetado.
- `windows_computer_use_mcp.py` y `overlay.py`: lanzadores de compatibilidad.

## Cierre automático del indicador

El indicador se oculta tras 8 segundos sin actividad de herramientas de pantalla. El plazo empieza cuando termina la última llamada; una acción larga mantiene el indicador visible. Consultar `get_control_status` no prolonga ese plazo. La siguiente acción de pantalla vuelve a mostrarlo, sin reanudar una cancelación del usuario. El servidor MCP sigue conectado para tareas posteriores.

Este cierre por inactividad es un respaldo: no detecta el final del chat de Antigravity. El agente debe llamar a `hide_screen_overlay` antes de su respuesta final, también si la tarea termina con un error. Después de actualizar, reconecta el servidor MCP en Antigravity para cargar el cambio.

## Cierre al terminar la tarea en Antigravity

Instala el hook oficial Stop después de instalar el paquete:

```powershell
.\.venv\Scripts\python.exe -m windows_computer_use.antigravity_hook --install
```

El instalador registra `ag-computer-use-cleanup` en `~/.gemini/config/hooks.json` sin reemplazar otros hooks. Al terminar una tarea completamente inactiva (`fullyIdle`), solicita cerrar el indicador. No detiene el servidor MCP, no reanuda cancelaciones y no cambia los permisos del cliente. El cierre por inactividad sigue como respaldo.

Si configuras `WINDOWS_COMPUTER_USE_STATE_DIR` para el servidor, pasa la misma carpeta al instalador con `--state-dir`. El último evento recibido se registra como metadatos locales en `last_antigravity_stop.json`, sin copiar mensajes ni transcripciones.

Referencia: [Hooks de Antigravity](https://antigravity.google/docs/hooks?tab=ide).

### Integración con el backend del IDE

El indicador consulta únicamente identificador, estado de ejecución y marcas de tiempo de la base local `conversation_summaries.db`, en modo SQLite de solo lectura. No consulta títulos, mensajes, transcripciones ni resultados. Se vincula a una conversación en ejecución y se cierra cuando queda inactiva sin tareas de fondo pendientes. Si hay varias conversaciones en ejecución y no puede determinar el propietario, no elige una al azar y conserva el cierre por inactividad como respaldo.

Se reconocen las carpetas `~/.gemini/antigravity`, `antigravity-ide` y `antigravity-cli`. `WINDOWS_COMPUTER_USE_ANTIGRAVITY_DB` permite indicar una ubicación diferente. Si la versión del cliente cambia el esquema, el cierre por inactividad y el hook Stop siguen disponibles. La integración no modifica archivos del programa ni los datos del backend.

En el IDE probado, el hook global no se ejecutó de forma consistente; el monitor del estado local es la vía de cierre verificada.
