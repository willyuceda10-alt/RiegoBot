# RiegoBot 2 · Operación y despliegue

## Alcance implementado
Panel React: incidencias, responsables, reglas por clase con cadena de escalamiento, asignación, evidencias, subsanación, aprobación, reapertura, respuesta al usuario, conversaciones, equipos/colectores y métricas.
Backend Supabase: ingesta autenticada, Postgres con RLS, cola persistente, transiciones atómicas, recordatorios/escalamiento y webhook firmado para WhatsApp.
Lector Python + PowerShell/ACE, exclusivamente de lectura, con outbox SQLite local y reintentos.

Las consultas disponibles son estado de sincronización, eventos, caudal, medidores, fertilización, programas, catálogos y observaciones del día. Se interpretan frases y comandos definidos; no se integra todavía un proveedor de LLM ni se permite SQL libre.
El chatbot no inventa riegos activos, salud del controlador, unidades ni totales de consumo no validados. Presenta observaciones y su fecha. Para información física validada se debe configurar el mapping correspondiente; la fuente de válvulas activas sigue pendiente de validación en Dream.

## Desarrollo local
Requisitos: Node 22+, Python 3.11+, Docker Desktop y PowerShell para MDB.
```powershell
npm ci
npx supabase start
node scripts/local-demo.mjs
npx supabase functions serve --env-file supabase/functions/.env.local
# En otra terminal:
npm run dev -- --port 5178
```
Panel: http://127.0.0.1:5178. Studio: http://127.0.0.1:55323.
Usuario de demostración únicamente local: operacion@riegobot.local.
Contraseña local: RiegoBot-Local-2026!
La preparación local comprueba la URL 127.0.0.1 y no aprovisiona usuarios en producción. Los teléfonos y casos de demostración están marcados como prueba.
DRY_RUN=true guarda respuestas simuladas; no llama a Meta.
El panel permite simular mensajes de contactos autorizados desde Conversaciones.

## Pruebas
```powershell
npm test
npm run build
python -m unittest discover -s tests -p 'test_*.py'
npm run test:db
npx deno check --config supabase/functions/deno.json supabase/functions/api/index.ts supabase/functions/ingest/index.ts supabase/functions/worker/index.ts supabase/functions/whatsapp-webhook/index.ts
node tests/api-integration.mjs
```
La prueba API requiere entorno local preparado y funciones sirviendo. Crea casos exclusivamente locales. Las pruebas SQL usan una transacción que revierte sus datos.
CI ejecuta pruebas de dominio, Python, compilación, tipos y ciclo SQL/RLS.

## Configuración del proyecto remoto
Proyecto acordado: zdgfjepoptlwjaoxvuju.
1. Autenticarse con npx supabase login.
2. Revisar el esquema remoto antes de aplicar migraciones. Nunca resetear una base remota.
3. Preparar supabase/functions/.env.production.local desde .env.example; usar secretos propios y DRY_RUN=true.
4. Ejecutar scripts/DEPLOY_SUPABASE.ps1. Las funciones verifican su propia autenticación: usuario Supabase para API, credencial de colector para ingesta, HMAC Meta para webhook y secreto para worker.
5. Crear/asignar el usuario administrador con scripts/BOOTSTRAP_SITE.mjs usando variables de entorno locales SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY y ADMIN_EMAIL. El script invita por correo si el usuario no existe; ejecutarlo solo para el destinatario autorizado. Configurar URLs de Auth del frontend.
6. Guardar en Vault riegobot_worker_url y riegobot_worker_secret; ejecutar scripts/CONFIGURE_DISPATCH.sql.
7. Configurar VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY en el frontend. Nunca utilizar service_role en el navegador.
8. Compilar npm run build; dist es la aplicación estática. La publicación del frontend debe hacerse en un host HTTPS autorizado; Supabase es el backend, no un hosting estático automático del panel.

No se han aplicado estas migraciones al proyecto remoto sin una sesión Supabase autorizada. La URL del proyecto por sí sola no otorga credenciales de despliegue.

## Incorporar el PC de Dream
1. Instalar Python y un proveedor Access compatible. La muestra se leyó con ACE 16.0 en Windows.
2. pip install -r requirements.txt
3. Copiar config/config.local.example.json a config/config.local.json.
4. Panel → Equipos: crear colector y copiar su UUID. Guardar el token en RIEGOBOT_COLLECTOR_TOKEN en el entorno del usuario del PC, no en Git.
5. Configurar ruta real de Dream, URL Supabase, zona horaria y Dreams habilitados.
6. Carga inicial: python -m dreamreader.collector --once --since 2026-08-01
7. Ejecución continua: python -m dreamreader.collector
8. Opcional: scripts/INSTALL_COLLECTOR.ps1 registra inicio al entrar el usuario en Windows. Si se requiere ejecución sin sesión iniciada, TI debe instalarlo con una cuenta de servicio y condiciones de arranque apropiadas.

La cola está en runtime/outbox.sqlite. Cada lote permanece hasta confirmación del servidor. Un corte no elimina lotes pendientes. Los registros históricos se deduplican por contenido y los estados/catálogos/datos diarios tienen identidad estable y revisión.
El escaneo incremental usa ventana retrospectiva configurable, predeterminada de dos días. Correcciones históricas anteriores requieren repetir --since. Dimensionar retención de seen/outbox y telemetría antes de operación prolongada.
Validar bloqueo/concurrencia y carga en la PC real; las pruebas no ejecutaron Dream simultáneamente con el lector.

## Configurar alertas e incidencias
Crear responsables con teléfono internacional sin +, rol y estado activo.
Cada regla define entidad/campo, comparación, valor, Dream opcional, gravedad, frescura y destinatarios por nivel.
Hay tres tipos: evento, umbral y solicitud de soporte. El soporte humano utiliza una regla activa de tipo support, no el primer umbral arbitrario.
El primer vencimiento es ack_minutes; cuando se confirma recepción comienza resolve_minutes. Los niveles siguientes utilizan after_minutes. Los recordatorios utilizan reminder_minutes.
Las reglas se copian en la incidencia al crearla: cambiar una regla afecta casos nuevos; los abiertos conservan su política y trazabilidad.
Los casos abiertos se deduplican por regla/objeto. El reenvío conserva el número. Una observación ya evaluada no vuelve a abrir un caso por un reintento.
La subsanación exige descripción y, si está configurado, foto. La aprobación puede requerir supervisor/jefe/admin. Reconocer no cierra. Un caso cerrado deja de recibir recordatorios.
No hay cierre automático por una lectura normal; el cierre administrativo no certifica la recuperación física de la señal.

Comandos WhatsApp:
- RECIBIDO 123
- ATENDIENDO 123
- CASO 123, luego enviar una foto
- SUBSANAR 123 descripción de la reparación
- APROBAR 123
- REABRIR 123 motivo
- PENDIENTES
- SOPORTE Dream 11 descripción
La foto también puede incluir #123 en su descripción. Si no hay caso seleccionado, se solicita selección y reenvío para evitar adjuntos en la incidencia incorrecta.

## WhatsApp real
Pendiente de número Business API del usuario.
Configurar WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_TOKEN, WHATSAPP_APP_SECRET, WHATSAPP_VERIFY_TOKEN y versión API.
Registrar webhook HTTPS /functions/v1/whatsapp-webhook.
La verificación GET exige token; POST valida X-Hub-Signature-256 y el phone_number_id.
Configurar una plantilla aprobada WHATSAPP_ALERT_TEMPLATE con un parámetro de texto en el cuerpo y su idioma. Se usa para avisos fuera de la ventana de conversación; revisar compatibilidad y límites con la plantilla real.
DRY_RUN=false únicamente después de la prueba con el número autorizado.
No se probó recepción/envío con Meta ni descarga de imágenes reales de WhatsApp porque no existe número configurado.

## Seguridad y recuperación
El usuario interno se autoriza por membership de sitio. Regador consulta/transiciona sus incidencias; supervisores autorizados pueden revisar las del sitio.
Los endpoints administrativos requieren rol admin. Los secretos del colector se guardan hasheados y las claves administrativas no llegan al panel.
Storage es privado; fotos con límite de 10 MB, tipos permitidos y enlaces temporales. La API valida firma de archivo básica; incorporar escaneo de malware según política corporativa antes de ampliar tipos.
La cola reclama trabajos con bloqueo y lease; reintenta rechazos acotadamente. Un envío a Meta de resultado ambiguo queda uncertain y no se reenvía automáticamente para evitar duplicados. Reconciliar con Meta y utilizar retry_delivery solo tras verificar que no salió.
El historial diferencia apertura, recepción, subsanación, aprobación y escalamiento.
No hay control ni escritura en Dream.

## Límites de aceptación del piloto
Falta autenticar/desplegar el proyecto remoto, asociar número Meta, configurar destinatarios reales y validar unidades/estados/umbrales con el operador.
No prometer ahorro de agua ni “sin alarmas” ante falta de datos.
El panel resume las últimas 200 incidencias y 80 mensajes. Las consultas de telemetría devuelven como máximo 1000 observaciones y muestran diez por mensaje. La paginación/históricos exhaustivos puede consumirse en Postgres, pero el chat informa el límite.
La interfaz administrativa requiere una política corporativa para altas, turnos y suplencias; esta versión configura contactos y escalamiento por regla, sin calendario de turnos automático.
