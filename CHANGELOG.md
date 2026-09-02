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
