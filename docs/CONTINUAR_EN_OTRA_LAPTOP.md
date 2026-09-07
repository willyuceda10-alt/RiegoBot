# Continuar RiegoBot desde otra laptop

El desarrollo del chatbot, panel, Supabase, recolector y mascota está en `codex/chatbot-incidencias-supabase`. Clona esa rama para recibir todos estos cambios.

## 1. Preparar la laptop

- Git y acceso a este repositorio con tu cuenta de GitHub.
- Node.js 22 con npm para el panel y las herramientas de Supabase.
- Python 3.12 o posterior con Tkinter para el recolector y la mascota. Usa una versión con sus actualizaciones de seguridad.
- Docker Desktop en ejecución para la base de datos y las funciones locales.
- Windows con PowerShell y un proveedor Microsoft Access/ACE compatible para leer archivos MDB reales de Dream. La demostración del panel no necesita Dream ni ACE.

## 2. Descargar el código e instalar dependencias

Abre PowerShell en la carpeta donde guardarás el proyecto:

```powershell
git clone --branch codex/chatbot-incidencias-supabase https://github.com/willyuceda10-alt/RiegoBot.git
cd RiegoBot
npm ci
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -c "import tkinter, PIL; print('Entorno de mascota preparado')"
```

Si tu instalación no tiene el comando `py`, utiliza `python -m venv .venv` después de comprobar su versión con `python --version`.

Todos los comandos siguientes se ejecutan desde la carpeta `RiegoBot`. No hace falta activar el entorno virtual: se usa su ejecutable directamente.

## 3. Levantar el panel con datos de demostración

En una terminal, con Docker Desktop iniciado:

```powershell
npx supabase start
node scripts/local-demo.mjs
npx supabase functions serve --env-file supabase/functions/.env.local
```

La primera ejecución descarga las imágenes de Supabase y puede tardar varios minutos. El script de demostración prepara usuarios, datos y configuración para el Supabase local; las funciones permanecen en ejecución en esa terminal.

En una segunda terminal:

```powershell
npm run dev -- --port 5178
```

Abre el panel en <http://127.0.0.1:5178> e ingresa con el usuario de demostración local:

- Correo: `operacion@riegobot.local`
- Contraseña: `RiegoBot-Local-2026!`

Supabase local usa <http://127.0.0.1:55321>; su interfaz Studio está en <http://127.0.0.1:55323>. La demostración usa `DRY_RUN=true`, por lo que las notificaciones de WhatsApp se simulan.

## 4. Abrir la mascota

En otra terminal:

```powershell
.\scripts\START_MASCOT.ps1 -PythonPath .\.venv\Scripts\python.exe -Controls
```

Si la política de PowerShell impide ejecutar scripts, puedes abrirla directamente con Python:

```powershell
.\.venv\Scripts\python.exe -m dreamreader.mascot --controls
```

La mascota abre pausada. Puedes desarrollar su interfaz sin tener Dream o un token de recolector. Para leer datos reales, configura en sus ajustes la carpeta Dream de esa laptop, la URL de Supabase, el ID de recolector registrado en el panel y su token. Consulta [Mascota del recolector](MASCOTA.md) y [Operación Supabase](OPERACION_SUPABASE.md).

## 5. Configuración que se prepara en cada equipo

Git incluye código, ilustraciones, logo, pruebas y migraciones. Los archivos `.env.local`, `supabase/functions/.env.local` y `runtime/local-session.json` se generan al ejecutar la demostración local.

La configuración privada `config/config.local.json`, los tokens, los archivos MDB de Dream y la cola de lecturas pendientes no se suben al repositorio. Configura las rutas y credenciales en la nueva laptop. Si vas a sustituir la PC que recoge datos reales, termina o transfiere de forma controlada su cola pendiente antes de apagar ese recolector; no ejecutes dos recolectores con la misma identidad.

El proyecto remoto previsto es `zdgfjepoptlwjaoxvuju`. Clonar el código no copia una base de datos ni despliega cambios allí. Su configuración y despliegue se explican en [Operación Supabase](OPERACION_SUPABASE.md). El envío real por WhatsApp sigue pendiente de configurar un número Business API y sus credenciales.

## 6. Verificar y continuar el desarrollo

```powershell
npm test
npm run build
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
```

Las pruebas de base de datos y API requieren también el entorno local anterior; consulta [Operación Supabase](OPERACION_SUPABASE.md#pruebas).

Antes de continuar una sesión de trabajo, guarda tus cambios y actualiza la rama:

```powershell
git status
git pull --ff-only
```

Cuando termines, revisa y publica tus cambios en esta misma rama:

```powershell
git diff
git add <archivos-que-modificaste>
git commit -m "Describe el cambio realizado"
git push
```

Sustituye `<archivos-que-modificaste>` por los archivos revisados. En la otra laptop, `git pull --ff-only` recuperará esos cambios una vez que su carpeta de trabajo esté limpia.
