# Componentes y recursos externos

## Herramientas reutilizadas desde GitHub

| Componente | Uso en este proyecto | Fuente |
| --- | --- | --- |
| pywinauto 0.6.9 | UI Automation: etiquetas, identificadores y patrón Invoke de controles | https://github.com/pywinauto/pywinauto |
| python-mss | Captura de escritorio por monitor y región | https://github.com/BoboTiG/python-mss |
| PyAutoGUI | Entradas de ratón y teclado y parada de emergencia | https://github.com/asweigart/pyautogui |
| resvg-py 0.5 | Renderizado de los SVG originales a la resolución de pantalla | https://github.com/baseplate-admin/resvg-py |

Las bibliotecas se instalan como dependencias de Python, con sus propios avisos y licencias. No se copia un servidor MCP externo completo ni se necesita ejecutar scripts descargados desde una rama de GitHub.

`inspect_window` ejecuta pywinauto/UIA en un proceso separado y limita la espera a 8 segundos. Entrega un snapshot con identificadores válidos durante 30 segundos. `invoke_control` consume ese snapshot una sola vez y comprueba identidad, etiqueta, visibilidad y disponibilidad del control. Las aplicaciones que no exponen UIA o Invoke siguen utilizando `read_screen` y coordenadas.

## Identidad visual

Los SVG fueron obtenidos de las fuentes oficiales el 6 de noviembre de 2026, conservando los originales:

- Antigravity, icono a color: https://antigravity.google/assets/image/brand/antigravity-icon__full-color.svg
- Antigravity, icono blanco: https://antigravity.google/assets/image/brand/antigravity-icon__white.svg
- Gemini, icono de la aplicación: https://www.gstatic.com/lamda/images/gemini_sparkle_aurora_33f86dc0c0257da337c63.svg
- Catálogo oficial de Antigravity: https://antigravity.google/press
- Aplicación oficial de Gemini: https://gemini.google.com/

Los nombres y logos pertenecen a Google. Las fuentes también se registran en `src/windows_computer_use/assets/sources.json`. Estos recursos se incluyen en wheel, sdist y ZIP, para que el indicador funcione sin descargarlos durante el uso.
