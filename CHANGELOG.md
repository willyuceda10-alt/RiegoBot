# Changelog

## 1.3.0-alpha

Initial independent multi-Dream discovery architecture. Adds configuration, inventory, shared-database candidates, provider probing, read-only schema discovery, schema comparison, logs, performance records, validation, and packaging.

## 1.3.1-alpha

Adds normalized extraction framework, mapping evidence documentation, shared database relationship analysis, and a clearly labelled candidate DreamStatus observation derived from the latest ReportsRT event per Dream. Candidate mappings remain disabled by default.

## 1.3.2-alpha

Adds the first portable Python control-plane skeleton, Water_Meters/LastWM contract analysis, generic database-adapter interface, and migration documentation while preserving the tested PowerShell MDB bridge.

## 1.3.3-alpha

Adds portable multiuser session contexts, unique session IDs, per-site/per-collector output and log paths, Python discovery artifacts, doctor command, portability audit, and multiuser collision testing for shared-folder execution.

## 1.3.4-alpha

Adds Python orchestration of the existing read-only PowerShell MDB bridge through the extract command. The launcher now accepts discovery, doctor, and extract while keeping MDB access on the previously tested Jet/ACE path.

## 1.3.5-alpha

Adds evidence-backed latest raw RTWMFlow observations per water meter. Flow values remain explicitly unscaled and unit-unresolved. Adds a candidate LastAccum mapping without enabling accumulation extraction by default.

## 1.3.6-alpha

Adds a consolidated `romeo_snapshot.json/csv` built from validated WaterMeters and latest raw FlowObservations. Snapshot values remain raw and flow units stay explicitly unresolved. Runtime config version is aligned with the executable version.

## 1.3.7-alpha

Adds an explicit `extract-candidates` mode for read-only investigation of candidate mappings. LastAccum can now be exported as raw accumulation observations with unresolved volume/time units. Normal `extract` keeps candidate mappings disabled.

## 1.3.8-alpha

Adds per-Romeo summaries for candidate LastAccum observations, including record count, latest timestamp, and raw min/max ranges. Units remain unresolved and candidate-only. Adds a one-click updater-and-candidate-test launcher for the local Windows workflow.

## 1.3.9-alpha

Moves automated schema comparison summaries out of tracked documentation and into each runtime session. The updater also cleans the legacy generated change in `docs/DREAM_SCHEMA_COMPARISON.md` before pulling, keeping shared-folder Git worktrees clean.

## 1.4.0-alpha

Introduces the first RiegoBot query layer over normalized DreamReader session outputs. Adds `python -m dreamreader romeo <id>` and `CONSULTAR_ROMEO.bat`, which read the latest valid normalized session without reopening Dream MDB files. Flow and accumulation units remain explicitly unresolved, and candidate status observations remain labelled as candidate data.

## 1.4.1-alpha

Adds freshness-aware Romeo summaries. RiegoBot now reports the latest normalized data timestamp, age in hours, FRESH/STALE status using a 24-hour safety threshold, and counts non-zero raw flow observations without interpreting them as confirmed irrigation. The summary explicitly blocks claims of current irrigation while units/semantics remain unresolved or data is stale.

## 1.4.2-alpha

Corrects freshness calculations for Dream timestamps that do not include timezone information. Site timezone is now explicitly configurable and defaults to `America/Lima` in the pilot configuration, so Romeo summaries preserve local Dream time instead of assuming UTC.

## 1.4.3-alpha

Adds an operator-friendly RiegoBot response layer. The new `romeo-message` command and `PREGUNTAR_RIEGOBOT.bat` summarize freshness, meter counts, and non-zero raw flow observations in Spanish while preserving safety guards: stale data cannot be presented as current irrigation, and unresolved flow units are never converted into physical caudal claims.

## 1.4.4-alpha

Adds a local natural-language command parser for operator questions. RiegoBot can now identify Romeo/Dream/controlador numbers from phrases such as `que pasa con el Romeo 11`, `estado Dream 13`, `caudal del controlador 17`, and classify basic intents (status, flow, irrigation, alarm) without external AI services. The new `RIEGOBOT_PREGUNTA.bat` provides a one-click interactive test.

## 1.4.5-alpha

Adds intent-specific operator responses. Alarm questions no longer reuse flow/status wording: RiegoBot now states explicitly that the alarm source is unresolved and refuses to infer alarms from flow. Flow and irrigation questions also receive dedicated responses with freshness and semantic safety guards.

## 1.4.6-alpha

Adds a dedicated one-click data refresh workflow. `REFRESCAR_DATOS_RIEGOBOT.bat` runs a fresh read-only normalized extraction so RiegoBot queries stop reusing stale session data after Dream MDB files are updated. A combined `REFRESCAR_Y_PREGUNTAR.bat` is included for local development testing.

## 1.5.0-alpha

Introduces the first continuous read-only collector mode. `python -m dreamreader realtime` polls Dream sources automatically (30 seconds by default), produces fresh normalized sessions without operator refresh, and writes an atomic collector health/status file. Includes one-click launchers for realtime collector and collector status. Manual refresh remains diagnostic only.

## 1.5.1-alpha

Hardens the continuous collector for 24/7 operation. Adds a singleton PID lock to prevent duplicate collectors, direct query lookup through `runtime/collector_status.json`, and automatic session retention (120 sessions by default) so 30-second polling does not grow the output tree indefinitely. Runtime state is now ignored by Git.

## 1.5.2-alpha

Adds Windows autostart support for the realtime collector without GitHub Actions. A single visible launcher, CONFIGURAR_AUTOINICIO_RIEGOBOT.bat, can install, inspect, or remove a per-user Windows logon scheduled task. The task runs the collector hidden through PowerShell and preserves the singleton lock.

## 1.5.3-alpha

Adds read-only operational-event investigation for candidate extraction. When `extract-candidates` is used, DreamReader now exports up to 100 recent `TGDReports.mdb/ReportsRT` rows per Romeo with raw report code/text, failure/state fields, and `Repid1/Repid2/Repid2Name`. Realtime production remains unchanged with candidate mappings disabled. This evidence is intended to validate alarms and active-valve semantics before any operational claim is enabled.

## 1.5.4-alpha

Adds automatic summarization of candidate operational events. `EJECUTAR_ANALISIS_CANDIDATOS.cmd` now performs the candidate extraction and immediately prints grouped evidence by Romeo, report text/code, RepFail, State, and recent raw IDs. This keeps investigation concise while preserving raw semantics and avoiding premature alarm/valve interpretation.

## 1.5.5-alpha

Builds a candidate operational-state layer from recent ReportsRT evidence. Report codes 29/30 are treated only as observed OPEN/CLOSED transitions, keyed by raw Repid2/Repid2Name, while RepFail=true rows are collected as recent failure events. The output explicitly forbids claiming current valve state or active alarms until transition completeness and alarm lifecycle semantics are validated.

## 1.5.6-alpha

Fixes the Windows DreamReader launcher whitelist so the new `candidate-operational-state` command can run from `EJECUTAR_ANALISIS_CANDIDATOS.cmd`. No extraction semantics changed.

## 1.5.7-alpha

Adds read-only ReportsRT coverage diagnostics. Candidate extraction now groups the full ReportsRT table by raw Dream value, reports event counts and latest timestamps, and exposes a reportsrt-coverage summary before event/state analysis. This determines whether Romeos 13/17 are absent from TGDReports.mdb or merely missing from the recent-event sample.

## 1.5.8-alpha

Adds a generic read-only Dream coverage scanner across all detected shared MDB databases. Candidate analysis now identifies every table with a Dream column and groups row counts by Dream value, allowing the current data sources for Romeos 11/13/17 to be located without relying on stale documentation or hardcoded assumptions.

## 1.5.9-alpha

Adds read-only investigation of TGDReports.mdb/Reports for all configured Romeos. The candidate analyzer compares recent historical report codes, valve open/close transitions (29/30), failure flags, IDs, and timestamps for Romeos 11/13/17 while keeping Reports distinct from ReportsRT and making no realtime-state claim.
