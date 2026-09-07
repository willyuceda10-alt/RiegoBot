# Mascota del recolector

En Windows con Python y Tkinter, ejecuta `scripts/START_MASCOT.ps1`, o `python -m dreamreader.mascot` desde la carpeta del proyecto.

La mascota es una gota verde flotante. Arrástrala para moverla y haz clic para abrir los controles. Inicia pausada: no transmite datos al abrirse.

- **Iniciar:** repite la lectura con `supabase.intervalSeconds` (mínimo 30 segundos).
- **Pausar:** termina el ciclo en curso y suspende los siguientes.
- **Sincronizar:** ejecuta un ciclo sin activar la repetición.
- **Configuración:** abre `config/config.local.json`. Los cambios se leen en el siguiente ciclo. El token se toma de `RIEGOBOT_COLLECTOR_TOKEN` del entorno de Windows; vuelve a abrir la mascota tras configurarlo.
- **Registro:** abre `runtime/mascot.log`.
- **Salir:** espera a que termine el ciclo para cerrar. Cerrar la ventana de controles solo la oculta.

El indicador informa del resultado del recolector, no del funcionamiento físico de Dream o las válvulas. La última sincronización mostrada corresponde a esta sesión. Los lotes pendientes se consultan en la cola SQLite persistente.

Usa la mascota como alternativa al recolector programado: no ejecutes ambos a la vez. No cambia ni instala tareas de Windows automáticamente. Requiere la misma configuración de Dream, ACE y credenciales que el recolector de consola.
