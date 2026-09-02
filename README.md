# RiegoBot / DreamReader 1.3.4-alpha

DreamReader es el núcleo técnico de RiegoBot para descubrir y leer múltiples controladores Dream en modo solo lectura.

## Arquitectura

Un Collector administra N Dreams.

- `CollectorId`: identifica la instalación del lector.
- `SiteId`: identifica la sede o fundo.
- `DreamKey`: identidad estable `${SiteId}-DREAM-${DreamId}`.

El discovery detecta archivos `Dream*_1.mdb` de forma dinámica y no requiere lógica específica para 11, 13 o 17.

## Ejecución

Con doble clic:

```
EJECUTAR_DREAMREADER.cmd
```

Por defecto ejecuta `discovery`.

También se puede ejecutar:

```
EJECUTAR_DREAMREADER.cmd doctor
EJECUTAR_DREAMREADER.cmd discovery
EJECUTAR_DREAMREADER.cmd extract
```

El comando `extract` usa Python como orquestador y delega la lectura MDB al bridge PowerShell probado en modo solo lectura.

## Carpeta compartida

Compatible con rutas como:

```
\\SERVIDOR\RiegoBot\
```

o:

```
Z:\RiegoBot\
```

El launcher usa `pushd` y no depende del directorio de trabajo actual.

## Configuración local

La ruta de Dream puede ajustarse sin modificar GitHub mediante:

```
config/config.local.json
```

o la variable:

```
RIEGOBOT_DREAM_ROOT
```

El discovery también revisa ubicaciones vecinas comunes como `..\Dream` y `..\Dream_Realtime\Dream`.

## Seguridad

El acceso MDB productivo permanece en PowerShell/OLE DB y usa `Mode=Read`.

No se implementan:

- escrituras MDB;
- cambios de válvulas;
- cambios de programas;
- polling productivo;
- WhatsApp;
- Azure;
- Windows Service.

## Validación

```powershell
.\scripts\TEST_READONLY.ps1
.\scripts\TEST_PORTABILITY.ps1
.\scripts\TEST_MULTIUSER.ps1
.\scripts\RUN_PYTHON_TESTS.ps1
.\scripts\VALIDAR_V1_3.ps1
```

## Estado actual

La versión 1.3.4-alpha ya cubre:

- discovery multi-Dream;
- ejecución portable;
- sesiones multiusuario;
- salida JSON/CSV;
- contratos Water_Meters + LastWM;
- mappings de evidencia;
- bridge PowerShell de solo lectura invocable desde Python.

El siguiente paso es validar `extract` en Windows real contra las MDB y revisar los artefactos normalizados generados.
