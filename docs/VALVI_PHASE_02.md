# Valvi — Fase 02A: puente de compatibilidad MDB

Primera entrega del puente Python/PowerShell, sin migrar todavía los extractores operativos.
La revisión del ZIP 2.0.3-alpha confirmó que el lector existente depende de Jet/ACE y que
el módulo Python realtime no está incluido. Se conserva ese código sin importarlo aún.

Desde la raíz de Valvi-Dev, con Python 3.11 o posterior:

    python -m unittest discover -s tests -p "test_*.py" -v
    python -m valvi probe-mdb

El segundo comando comprueba los proveedores Jet/ACE visibles para el proceso PowerShell
actual y devuelve arquitectura y nombres de proveedores, no rutas ni información de la red.
Una lista vacía no prueba que no existan proveedores en otra arquitectura de proceso.
El comando respeta la política de ejecución de Windows; si se bloquea, pedir a TI un script
aprobado o firmado. No cambia políticas ni instala controladores.

Opcional: con autorización, usar únicamente una base MDB de ensayo sintética, en un disco
local fijo, con tamaño máximo de 50 MiB. No utilizar una base de producción ni una carpeta
de red. Ejemplo de sintaxis (archivo ficticio):

    python -m valvi probe-mdb --fixture "C:\\ValviTest\\fixture.mdb"

Se crea una copia temporal y se abre con Mode=Read. Solo se devuelve el número de tablas
locales; no hay consultas SQL ni extracción de registros. La copia se elimina al finalizar
normalmente; un cierre forzado puede dejar un directorio ValviFixture_* en TEMP. No usar
archivos confidenciales. No hay publicación automática. Los códigos 0 y 2 distinguen
resultados válidos y errores; una lista vacía de proveedores requiere revisión.

Las pruebas unitarias simulan las respuestas del proceso PowerShell. No sustituyen una
prueba en Windows con Jet/ACE. El tiempo de espera del proceso es de 30 segundos.

Pendiente: validar el puente en Windows, comparar datos de ensayo con contratos de mapeo,
revisar y adaptar los extractores 2.0.3, validar frescura y unidades. El colector continuo,
SQLite, alertas y WhatsApp no están activos. No se ha alterado el lector histórico.
