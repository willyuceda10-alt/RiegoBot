# Mascota del recolector

En Windows con Python y Tkinter, ejecuta `scripts/START_MASCOT.ps1`, o `python -m dreamreader.mascot` desde la carpeta del proyecto.

La mascota es un robot de riego flotante con casco, visor, brazos y boquilla, construido con una malla 3D iluminada. Usa verdes, amarillo solar y dorado inspirados en Camposol; tiene respiración, parpadeo y mirada que sigue al cursor. Arrástrala para moverla y haz clic para desplegar sus controles en la misma ventana transparente. No hay una ventana de controles separada. Inicia pausada: no transmite datos al abrirse.

- **Iniciar:** repite la lectura con `supabase.intervalSeconds` (mínimo 30 segundos).
- **Pausar:** termina el ciclo en curso y suspende los siguientes.
- **Sincronizar:** ejecuta un ciclo sin activar la repetición.
- **Ajustes:** permite editar carpeta Dream, URL de Supabase, ID e intervalo sin salir de la mascota. Guarda en `config/config.local.json`. Los cambios se leen en el siguiente ciclo. El token puede introducirse en un campo oculto y se conserva solo durante esta sesión; no se escribe al archivo. También admite `RIEGOBOT_COLLECTOR_TOKEN` del entorno de Windows.
- **Actividad:** muestra los últimos 10 KB de `runtime/mascot.log` dentro de la mascota. Pulsa de nuevo para actualizar.
- **Ocultar / Escape / clic en el personaje:** repliega los controles y deja solo la mascota. La sincronización automática continúa si estaba activa.
- **Salir:** espera a que termine el ciclo para cerrar.

El indicador informa del resultado del recolector, no del funcionamiento físico de Dream o las válvulas. La última sincronización mostrada corresponde a esta sesión. Los lotes pendientes se consultan en la cola SQLite persistente.

Usa la mascota como alternativa al recolector programado: no ejecutes ambos a la vez. No cambia ni instala tareas de Windows automáticamente. Requiere la misma configuración de Dream, ACE y credenciales que el recolector de consola.
