# RiegoBot / DreamReader 1.3.3-alpha

DreamReader es el núcleo técnico de RiegoBot para descubrir y leer múltiples controladores Dream en modo solo lectura.

## Arquitectura

Un Collector administra N Dreams.

- `CollectorId`: identifica la instalación del lector.
- `SiteId`: identifica la sede o fundo.
- `DreamKey`: identidad estable `${SiteId}-DREAM-${DreamId}`.

Agregar un nuevo archivo `Dream21_1.mdb` no requiere modificar lógica: si no está configurado aparecerá como `DISCOVERED`.

## Carpeta compartida

El proyecto está diseñado para ejecutarse desde:

```
\\SERVIDOR\RiegoBot\
```

o desde una unidad mapeada como:

```
Z:\RiegoBot\
```

No se requieren rutas del perfil del usuario. La raíz se obtiene desde los propios archivos del proyecto.

Permisos mínimos:

- Lectura sobre código y MDB.
- Escritura sobre `output/` y `logs/`.
- No requiere permisos de administrador.

Cada ejecución genera un `SessionId` único con fecha, host, usuario y sufijo aleatorio. Las salidas se separan así:

```
output/
  SITE01/
    COLLECTOR-LOCAL-01/
      <SessionId>/
```

y los logs:

```
logs/
  SITE01/
    COLLECTOR-LOCAL-01/
      DreamReader_<SessionId>.log
```

Esto evita que dos usuarios sobrescriban la misma sesión.

## Python

Se requiere Python 3.11 o posterior para el nuevo control plane.

Ejecutar:

```text
EJECUTAR_DREAMREADER.cmd
```

El launcher utiliza `pushd`, por lo que también funciona desde rutas UNC.

También puede ejecutarse:

```bash
python -m dreamreader doctor
python -m dreamreader discovery
python -m dreamreader extract
```

`doctor` valida la base portable. `discovery` crea una sesión e inventario. `extract` todavía mantiene el acceso MDB productivo en el puente PowerShell probado.

## Configuración

`config/config.json` contiene configuración compartida.

Opcionalmente puede existir:

```
config/config.local.json
```

para ajustes locales. Este archivo no se versiona.

## MDB y solo lectura

La ruta MDB estable continúa en PowerShell/OLE DB durante la migración.

Proveedores contemplados:

- Microsoft.Jet.OLEDB.4.0
- Microsoft.ACE.OLEDB.16.0
- Microsoft.ACE.OLEDB.12.0

Las conexiones usan `Mode=Read`.

No se implementa escritura en MDB ni acciones de control sobre Dream.

## Validación

Ejecutar:

```powershell
.\scripts\TEST_READONLY.ps1
.\scripts\TEST_PORTABILITY.ps1
.\scripts\TEST_MULTIUSER.ps1
.\scripts\VALIDAR_V1_3.ps1
```

## Estado actual

1.3.3-alpha incluye:

- discovery multi-Dream;
- mappings con evidencia;
- DreamStatus candidato;
- contrato Water_Meters + LastWM;
- base Python portable;
- SessionId multiusuario;
- outputs separados por sede/collector/sesión;
- pruebas de portabilidad.

Todavía no incluye:

- polling productivo;
- API central;
- Azure;
- WhatsApp;
- Windows Service;
- comandos sobre válvulas o programas.
