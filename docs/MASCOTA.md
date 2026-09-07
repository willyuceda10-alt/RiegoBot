# Mascota del recolector

En Windows, instala las dependencias de `requirements.txt` en un Python con Tkinter. Desde la carpeta del proyecto, ejecuta `scripts/START_MASCOT.ps1 -PythonPath .\.venv\Scripts\python.exe`, o `.\.venv\Scripts\python.exe -m dreamreader.mascot`. La [guía para otra laptop](CONTINUAR_EN_OTRA_LAPTOP.md) explica cómo crear ese entorno.

La mascota actual es un personaje de estilo anime sentado frente a una PC, con la identidad de Camposol, respiración, parpadeo y gestos suaves de lectura y escritura. Un pensamiento sobre su cabeza muestra el estado del recolector: ámbar en espera, verde con conexión confirmada recientemente y rojo ante un fallo. Consulta los [detalles del diseño y movimiento](MASCOTA_PC.md).

Arrástrala para moverla y haz clic para desplegar sus controles en la misma ventana transparente. Inicia pausada: no transmite datos al abrirse.

- **Iniciar:** repite la lectura con `supabase.intervalSeconds` (mínimo 30 segundos).
- **Pausar:** termina el ciclo en curso y suspende los siguientes.
- **Sincronizar:** ejecuta un ciclo sin activar la repetición.
- **Ajustes:** permite editar carpeta Dream, URL de Supabase, ID e intervalo sin salir de la mascota. Guarda en `config/config.local.json`. Los cambios se leen en el siguiente ciclo. El token puede introducirse en un campo oculto y se conserva solo durante esta sesión; no se escribe al archivo. También admite `RIEGOBOT_COLLECTOR_TOKEN` del entorno de Windows.
- **Actividad:** muestra los últimos 10 KB de `runtime/mascot.log` dentro de la mascota. Pulsa de nuevo para actualizar.
- **Ocultar / Escape / clic en el personaje:** repliega los controles y deja solo la mascota. La sincronización automática continúa si estaba activa.
- **Salir:** espera a que termine el ciclo para cerrar.

El indicador informa del resultado del recolector, no del funcionamiento físico de Dream o las válvulas. La última sincronización mostrada corresponde a esta sesión. Los lotes pendientes se consultan en la cola SQLite persistente.

Usa la mascota como alternativa al recolector programado: no ejecutes ambos a la vez. No cambia ni instala tareas de Windows automáticamente. Requiere la misma configuración de Dream, ACE y credenciales que el recolector de consola.
