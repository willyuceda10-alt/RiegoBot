# RiegoBot · Semilla Lab

Plataforma de consulta de Dream y gestión de incidencias por WhatsApp con Supabase.

## Componentes
- Recolector local Python + PowerShell/ACE, de solo lectura, con cola persistente.
- Postgres/RLS, ingesta, reglas, incidencias, fotos privadas, escalamiento y trabajos durables.
- Webhook de WhatsApp con firma HMAC y simulación sin número real.
- Panel React para operación, configuración, evidencias, soporte y métricas.

## Empezar en local
```powershell
npm ci
npx supabase start
node scripts/local-demo.mjs
npx supabase functions serve --env-file supabase/functions/.env.local
# Otra terminal
npm run dev -- --port 5178
```

Panel: http://127.0.0.1:5178. Las credenciales y pasos de producción están en [Operación Supabase](docs/OPERACION_SUPABASE.md).

Proyecto remoto previsto: `zdgfjepoptlwjaoxvuju`. Se requiere autenticar la CLI para desplegar. WhatsApp real necesita número Business API y secretos; mientras tanto usar DRY_RUN=true.

## Verificación
```powershell
npm test
npm run build
python -m unittest discover -s tests -p 'test_*.py'
npm run test:db
node tests/api-integration.mjs
```
Las pruebas de API necesitan el entorno local y las funciones en ejecución. CI verifica también los tipos de Edge Functions.

## Alcance de los datos
Hay consultas de eventos, caudal, medidores, fertilización, programas, catálogo y observaciones diarias. Los campos físicos requieren mappings validados. No se infiere estado actual de válvulas, salud del controlador ni ausencia de alarmas a partir de un histórico.
El lector no escribe MDB ni controla Dream. Los scripts V1.3 se conservan como herramientas de inventario; el recolector continuo se ejecuta con `python -m dreamreader.collector`.
