# RiegoBot / DreamReader 1.3.2-alpha

DreamReader is a read-only discovery and schema inventory tool for multiple Dream MDB instances.

A Collector represents one host or installation. `CollectorId` identifies that collector, `SiteId` identifies the site, and `DreamKey` is the stable identity `${SiteId}-DREAM-${DreamId}`. Adding a site means creating a separate configuration with its own collector and site values.

The discovery module searches `Dream*_1.mdb`, extracts the numeric DreamId, and compares it to `config/config.json`. A configured and enabled instance is `CONFIGURED`; an unconfigured file is `DISCOVERED`; a disabled configured entry is `DISABLED`; a configured file that is absent is `UNKNOWN`. Discovered instances are reported only and are not activated.

Run `EJECUTAR_V1_3.cmd`, or run `scripts/INICIAR_V1_3.ps1` after `scripts/VALIDAR_V1_3.ps1`. Results are stored in a new timestamped `output` session. Package the most recent session with `scripts/EMPAQUETAR_RESULTADOS.ps1`.

`extractionMode` defaults to `DISCOVERY`. `NORMALIZED` only uses evidence-backed mappings. Candidate mappings require the explicit `allowCandidateMappings` switch; their output remains labelled `CANDIDATE` and never represents a confirmed operational state.

This alpha release does not implement realtime polling, WhatsApp, Azure, external APIs, valve control, program changes, MDB writes, or a Windows Service. All connections are opened with `Mode=Read`; schema access uses ADO.NET metadata APIs, and the only query gateway accepts `SELECT` statements.
