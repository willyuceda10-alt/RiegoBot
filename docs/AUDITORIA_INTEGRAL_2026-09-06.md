# Auditoría integral de RiegoBot — 6 de septiembre de 2026

## Resultado y alcance

Se corrigieron fallos reproducibles de seguridad, fiabilidad, rendimiento y accesibilidad en la mascota, el recolector Python/ACE, el panel React y las funciones/RPC de Supabase. Se conserva el personaje pequeño trabajando en una PC y una sola interfaz de control. Esta revisión habilita seguir con el piloto local; **no certifica que el sistema esté listo para producción**.

La revisión combina inspección de código, regresiones automatizadas, pruebas con Auth/Postgres/API locales, lectura de copias MDB y revisión visual del panel. No se enviaron mensajes reales de WhatsApp ni se desplegaron cambios en el proyecto Supabase de producción. Las migraciones 007, 008 y 009 se aplicaron únicamente a Supabase local.

## Seguridad y fiabilidad: hallazgos corregidos

| Prioridad | Problema comprobado | Corrección y evidencia |
|---|---|---|
| Alta | Una URL como `http://127.0.0.1:80@host-remoto` superaba la comprobación por prefijo y podía recibir el token. | `ingest_endpoint` valida esquema, host, puerto, usuario, ruta, fragmento y query. Solo acepta HTTPS o HTTP de IP loopback literal. Ajustes usa el mismo validador. Prueba de regresión. |
| Alta | Las redirecciones HTTP podían llevar la credencial a otro destino. | Se rechazan redirecciones y el token se adjunta como cabecera no redirigible. Un servidor local de prueba confirma que el destino redirigido no recibe solicitudes. |
| Alta | Un operador podía usar el simulador para actuar como un supervisor sobre incidencias de la base local. | Simulación reservada a administradores, además del modo de simulación existente. Prueba contra usuarios reales temporales de Supabase local. |
| Alta | Webhook, ingest, API y fotos podían reservar memoria antes de comprobar el tamaño real. | Lectura por streaming con límites de bytes y cancelación. Límites: webhook 1 MB, ingest 4 MiB, API 15 MiB, fotos 10 MiB; descarga de fotos con timeout. Prueba de stream sin Content-Length confiable. |
| Alta | PowerShell podía bloquearse por stderr lleno o por no terminar y heredaba credenciales innecesarias. | Ambos pipes se drenan en paralelo, con buffers limitados, plazo de extracción y entorno mínimo sin token del recolector. Pruebas de stderr, timeout y fila inválida. |
| Media | Un envío aceptado por Meta con JSON truncado podía reintentarse y duplicar el mensaje. | Resultado `uncertain` para reconciliación, sin reenvío automático. Prueba con respuesta Meta simulada; no se transmitió ningún mensaje. |
| Media | Un lote antiguo podía disparar una alerta aunque ya existiera una lectura normal más reciente. | RPC comprueba la revisión vigente y antigüedad dentro de la transacción. Regresión SQL. |
| Media | Reintentar el mensaje que originó un soporte podía crear otro caso después de cerrar el anterior. | Identidad durable mensaje→incidencia y exclusión transaccional. Regresión SQL antes y después del cierre. |
| Media | Al cambiar sesión/sitio podían reaparecer datos o credenciales por respuestas pendientes. | Generaciones de solicitud invalidan resultados tras logout/cambio de ámbito, incluso al reingresar con el mismo usuario. Prueba asíncrona. |
| Media | Dos recolectores podían leer/enviar simultáneamente desde mascota y tarea programada. | Bloqueo del sistema operativo compartido por ciclo. Prueba de exclusión y liberación. |
| Media | La cola no tenía topes y cada envío cargaba todos los lotes en RAM. | Límites de lotes, bytes pendientes y páginas SQLite; lectura de un lote por vez. La capacidad y `seen` comparten una transacción: si falla, revierte. |
| Media | Los lotes del recolector podían superar el límite nuevo de ingest y quedar en reintento permanente. | División a máximo 3 MiB de JSON UTF-8 y 250 filas por lote, incluyendo el sobre. Cinco pruebas de división, fila excesiva y rollback por capacidad. |
| Media | PENDIENTES omitía casos antiguos autorizados si había 50 casos recientes ajenos. | SQL autoriza antes de LIMIT 15; cubre asignación directa, solicitante de soporte y política. Regresión con 60 casos recientes ajenos y tres antiguos accesibles. |
| Media | La mascota podía quedar ocupada para siempre si fallaba la creación del log o la terminación del proceso. | Evento final garantizado, watchdog del ciclo y limpieza con espera acotada. Pruebas de archivo/directorio inválido, taskkill ausente y timeout. Si no se confirma cierre del árbol, se pausa el automático. |
| Baja | Conexiones de lectura SQLite se dejaban al recolector de basura. | Cierre explícito y consulta cada cinco segundos; timeout de bloqueo de 25 ms. Prueba de cierre y frecuencia. |
| Baja | El log crecía entre ciclos sin rotación. | Se conserva un respaldo al superar 2 MiB antes del siguiente ciclo; el visor lee como máximo 10.000 bytes. No es un tope absoluto durante un ciclo. |

Archivos principales: `dreamreader/collector.py`, `mascot.py`, `mascot_view.py`; `supabase/functions/_shared/common.ts`, `_shared/worker.ts`; `core/request-scope.ts`; migraciones `202609060007`–`202609060009`.

## Diseño y accesibilidad

| Antes | Después |
|---|---|
| Apertura compacta solo mediante ratón. | Botón nativo con nombre/estado, Enter/Espacio, foco al abrir y retorno con Escape. El personaje continúa siendo arrastrable. |
| Un error podía verse como una pausa normal al minimizar. | Etiquetas compactas “Configurar” o “Revisar error”, además del estado completo del panel. |
| Controles y campos podían quedar fuera de la pantalla con DPI alto. | Panel desplazable completo, ancho calculado a partir de fuente, botones apilados y scroll al campo enfocado. Prueba con escalado equivalente al 200% y texto grande. |
| Movimiento perpetuo sin ajuste independiente. | “Reducir movimiento” persistente; no cambia la programación del recolector. También hay “Texto grande”, “Siempre visible” y barra de título para Alt+Tab. |
| Ventana sin ruta clara para recuperarla. | Volver a ejecutar el lanzador abre los controles de la instancia existente mediante un comando local limitado a mostrar la ventana. `START_MASCOT.ps1 -Controls` abre directamente los controles. |
| Texto secundario de mascota 4,41–4,48:1; foco 1,45:1. | Texto secundario más oscuro y contorno de foco de dos píxeles; color de texto explícito al pulsar botones. |
| Metadatos del panel web entre 2,94 y 4,10:1. | Los 22 elementos de la muestra revisada alcanzan al menos 5,75:1. Es una muestra del panel de incidencias, no una certificación de todos los estados. |
| Cerrar sesión desaparecía en móvil. | Acción disponible en pantalla estrecha; filtros se apilan. Vista de 390×844 sin desbordamiento horizontal de página. Las tablas y navegación pueden desplazarse dentro de su contenedor. |
| API caída aparentaba cero incidencias. | Indicadores “—”, error en español y aviso de carga fallida. Si hay datos anteriores, se conservan con aviso de actualización no confirmada. |
| Logo deformado en el pequeño sello de la mesa. | Logo proporcional y original conservado. La marca legible permanece en la cabecera del panel; el sello pequeño es decorativo. |

Se comprobó en el navegador que Shift+Tab permanece dentro del detalle y Escape devuelve el foco al caso. Las pruebas Tk despachan Enter/Escape sobre una ventana de prueba mapeada con opacidad cero y verifican foco, campos y geometría; no equivalen a una prueba con una persona usando lector de pantalla.

**Pendiente:** validar NVDA en Windows y percepción real a distintas resoluciones/DPI. Tk y el dibujo Canvas no proporcionan automáticamente toda la semántica accesible. Los criterios de contraste y pausa se usaron como referencia de [WCAG 2.1](https://www.w3.org/TR/WCAG21/) y [movimiento automático](https://www.w3.org/WAI/WCAG21/Understanding/pause-stop-hide.html), sin afirmar conformidad completa de una aplicación nativa.

## Rendimiento medido

| Medición local | Antes | Después | Alcance |
|---|---:|---:|---|
| Preparación inicial de las cuatro poses | 1.725 ms | 12,1 ms | Primera carga del atlas; no representa el arranque completo de Windows/Python. Mediana de cargas posteriores con caché de sprites vaciada: 3,59 ms. |
| 10.000 llamadas de dibujo sin cambios relevantes | 1.240,32 ms | 16,04 ms | Microbenchmark Tk con ventana oculta, misma máquina. Se reutilizan imágenes e items. No es una medición de CPU/GPU durante una jornada. |
| Consulta de cola en la mascota | Cada segundo | Cada cinco segundos | Una conexión de lectura breve, cerrada explícitamente. |
| Extracción sobre diez copias MDB | — | 44.202 registros en 16,0 s | SHA-256 idénticos antes/después. Sin envío a nube. |
| Bundle web | — | 444,21 kB JS / 127,08 kB gzip | Build local; CSS 7,75 kB / 2,46 kB gzip. |

El atlas preparado ocupa 152.359 bytes y contiene cuatro poses de 136×178 px. `scripts/prepare_companion.py` permite regenerarlo; el procesamiento costoso ocurre al preparar el recurso, no al abrir la mascota. Se conserva el archivo de arte original. La comparación de las cuatro poses fue idéntica fuera de la región del logo proporcional.

Se añadieron índices de pendientes/leases, recordatorios/escalamientos y búsquedas de historial, mensajes y telemetría. No se atribuye un porcentaje de mejora de PostgreSQL sin un dataset de carga representativo.

## Límites operativos y trabajo pendiente

| Prioridad | Pendiente | Motivo y siguiente validación |
|---|---|---|
| Alta antes de producción | Actualizar el Python del PC. | La prueba usa Python 3.12.10. Existen correcciones de seguridad posteriores, incluidas HTTP/SSL. [Python 3.12.13](https://www.python.org/downloads/release/python-31213/) documenta varias; 3.12.10 fue el último instalador binario regular de esa rama. TI debe proporcionar un runtime mantenido y volver a validar ACE/Tk/Pillow; esta revisión no cambia la instalación global. |
| Alta antes de operación prolongada | Retención de `seen` en SQLite e históricos en Supabase. | `seen` conserva revisiones incluso tras enviarlas. Al alcanzar el tope detiene nuevas capturas. Se necesita fecha/confirmación por revisión, purga solo de confirmadas fuera de la ventana de relectura, archivo y aviso de capacidad. No borrar outbox.sqlite para liberar espacio con pendientes. VACUUM no elimina claves vivas. |
| Alta antes de producción | Validar escala/unidades y significado de campos Dream con operación. | No inferir válvulas abiertas o estados físicos usando solo catálogos. Verificar reglas con datos y umbrales aprobados por campo. |
| Alta antes de producción | WhatsApp Business y configuración Supabase real. | Falta número/provisión Meta, plantillas, secretos, despliegue y verificación de RLS/Storage/cron en el entorno destino. Probar fotos, reintentos ambiguos y toda la cadena de escalamiento con destinatarios de prueba. |
| Media | Dimensionar ingest y worker bajo carga. | Evaluación de coincidencias mediante RPC secuenciales y worker de diez trabajos por pasada. Medir llegada de datos, demora P95, cola, saturación y recuperación tras desconexión antes de aumentar concurrencia. |
| Media | Ensayo de operación de 24–72 horas. | Falta medir memoria/CPU/handles, cortes de red, suspensión de Windows, espacio en disco, fallos ACE y recuperación de los lotes pendientes. Los microbenchmarks no sustituyen este ensayo. |
| Media | Auditoría de infraestructura local y producción. | No se comprobó endurecimiento del sistema operativo, permisos efectivos/BitLocker, copia y restauración, red, dependencias ACE ni configuración externa de Meta. |
| Media | Prueba asistida de accesibilidad. | NVDA, navegación por teclado física, contraste en todos los formularios/estados y percepción del movimiento. |

Valores por defecto del recolector, configurables bajo `supabase`: `maxPendingBatches=2000`, `maxPendingBytes=134217728`, `maxDatabaseBytes=536870912`, `extractionTimeoutSeconds=900` (máximo 3600). El tope SQLite corresponde a páginas de base; archivos WAL/temporales y archivos ya mayores requieren supervisión adicional. Cada pasada de envío admite hasta 20 lotes o un presupuesto de 60 segundos. El timeout de socket no es una garantía absoluta frente a un servidor que envíe cabeceras muy lentamente; la mascota añade watchdog al proceso completo. El CLI independiente no posee ese watchdog padre.

Cuando se alcanza capacidad, se revierte la nueva escritura y se conserva la cola comprometida. Los datos todavía no capturados dependen de cuánto historial conserve Dream. No hay eliminación silenciosa de pendientes.

## Verificación y reproducibilidad

- 28 pruebas Python: 21 del recolector y 7 de la mascota. Incluyen pruebas con servidores locales y Tk; no acceden a Dream real ni a nube.
- 7 pruebas TypeScript de dominio y ámbito de sesión.
- 3 pruebas Deno: firma HMAC, lectura limitada y envío ambiguo.
- SQL: ciclo, fotos, escalamiento, aprobación, deduplicación, muestras atrasadas, replay de soporte, casos antiguos autorizados y RLS.
- API con Auth local: aislamiento de sitios, restricciones de escritura, protección del hash del recolector, prohibición de aprobación y simulación a operador.
- Build React/TypeScript, tipos de cuatro funciones y revisión de espacios/diff.
- `npm audit`: cero avisos conocidos en las 188 dependencias reportadas, incluyendo desarrollo. `pip-audit`: cero avisos para Pillow 12.3.0 y tzdata 2026.3; versiones ahora fijadas en requirements.txt.

Los escaneos de dependencias consultan vulnerabilidades conocidas. No cubren todos los errores propios, el runtime Python ni infraestructura; [pip-audit](https://github.com/pypa/pip-audit) describe ese alcance. No se afirma ausencia de vulnerabilidades.

Comandos principales, desde la raíz del repositorio:

```text
python -m unittest discover -s tests -p "test_*.py" -v
npm test
npm run build
npm run test:db
node tests/api-security.mjs
deno test --allow-env --config supabase/functions/deno.json tests/signature.test.ts tests/backend-security.test.ts
deno check --config supabase/functions/deno.json supabase/functions/api/index.ts supabase/functions/ingest/index.ts supabase/functions/worker/index.ts supabase/functions/whatsapp-webhook/index.ts
npm audit
```

SQL/API requieren Supabase local y configuración local de prueba. El CI incluye las pruebas Deno nuevas y ejecuta Tk mediante Xvfb en Linux. La verificación local de Windows no implica que el CI remoto ya haya terminado.
