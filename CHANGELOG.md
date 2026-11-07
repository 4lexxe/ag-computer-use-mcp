# Cambios

## 0.2.3 — 2026-11-07

- Seguimiento de solo lectura del estado de ejecución de Antigravity para cerrar el indicador cuando termina la conversación, sin depender del modelo.
- Hook Stop opcional para clientes que emiten el evento; el IDE dispone del monitor de estado como respaldo.
- Instalador del hook global que conserva las personalizaciones existentes y crea respaldo antes de modificarlas.
- El cierre mantiene las cancelaciones del usuario y no cambia permisos ni prolonga el chat.

## 0.2.2 — 2026-11-07

- Cierre automático del indicador tras 8 segundos sin actividad, aunque el modelo omita `hide_screen_overlay`.
- Las acciones largas mantienen el indicador visible hasta finalizar; la siguiente acción lo vuelve a mostrar.
- La consulta de estado no prolonga la sesión visual; el cierre automático conserva las cancelaciones del usuario.

## 0.2.1 — 2026-11-06

- Rojo más intenso y latido doble que aumenta suavemente el grosor de 68 a 100 píxeles lógicos.
- Franjas de dibujo ampliadas para conservar el halo del contorno y barra desplazada fuera del pulso.
- Grabación de demos con inclusión temporal y explícita del indicador.

## 0.2.0 — 2026-11-06

- Contorno rectangular de 34 píxeles lógicos con halo y transparencia real por píxel, sin recortar las esquinas.
- Partículas en los bordes que aparecen, se desplazan y se difuminan; actualización limitada a franjas estrechas.
- 144 partículas por monitor entre puntos y destellos que se difuminan.
- Barra rectangular con «Antigravity is using your computer», SVG oficiales de Antigravity y Gemini y estados en español.
- Halo transparente del mouse, estela corta, insignia de Antigravity y pulso de clic; el cursor del sistema conserva su forma.
- Mantenimiento periódico de la superposición al cambiar de ventana y al mostrarse la barra de tareas, sin activar el indicador.
- Botón Detener y atajo global Ctrl+Alt+Esc mediante mensajes de Windows; el indicador se cierra si termina su servidor.
- Integración con pywinauto/UIA: inspección de controles e invocación mediante snapshots de un solo uso.
- Estado compartido con bloqueo entre procesos; las actualizaciones de actividad no reactivan una cancelación.
- Comprobación de cancelación durante la escritura por bloques.

## 0.1.0 — 2026-11-04

- Paquete Python con estructura `src/`, comandos instalables y lanzadores compatibles.
- Pruebas, documentación, ejemplos y construcción de releases separados del código.
- Estado de sesión en una carpeta de usuario, fuera de la instalación.
- Contorno rojo translúcido y barra con nombre del proyecto y botón Detener.
- Capturas nativas MCP, recortes por región y metadatos de coordenadas.
- Cancelación persistente y reanudación explícita con mensajes de recuperación.
- Selección de ventanas por identificador y detección de títulos ambiguos.
