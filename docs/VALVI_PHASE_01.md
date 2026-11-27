# Valvi — Fase 01: configuración multi-origen

## Objetivo

Introducir una configuración por instalación, independiente del usuario y del
nombre de las carpetas. Sin IA. Sin exploración automática de redes. El
validador no abre bases MDB, no envía mensajes y no inicia el monitoreo.

## Uso en Windows (Python 3.11+)

Desde la raíz del repositorio, crear el directorio de configuración privado:

    New-Item -ItemType Directory -Force "$env:LOCALAPPDATA\Valvi"
    Copy-Item config/valvi.sources.example.json "$env:LOCALAPPDATA\Valvi\sources.json"

Editar únicamente el archivo privado con rutas exactas autorizadas por TI.
Los ejemplos están deshabilitados. No incluir IP reales ni credenciales en Git.
El archivo privado no se crea automáticamente ni se sobrescribe por Valvi.

    python -m valvi validate-config
    python -m unittest discover -s tests -p test_valvi_sources.py -v

El resumen muestra la validez sintáctica de la configuración, no el acceso
efectivo ni la actualidad de los datos. El intervalo de 30 segundos es una
propuesta configurable; no garantiza latencia de la fuente.

## Integración pendiente

El ZIP 2.0.3-alpha contiene extractores PowerShell ampliados, pero no incluye
el módulo Python que ejecuta el comando realtime. Se conserva el lector
existente hasta revisar diferencias y comprobar su comportamiento autorizado.
No se importan configuraciones operativas ni datos del ZIP a este repositorio
público. Antes de activar el monitoreo: validar unidades, permisos, frescura,
integridad y rendimiento con pruebas autorizadas. Luego agregar almacenamiento
local, reglas deterministas, reportes y WhatsApp mediante menús predefinidos.
