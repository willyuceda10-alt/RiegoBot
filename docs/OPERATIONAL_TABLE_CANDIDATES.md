# Operational Table Candidates

| Area | Database / Table | Relevant fields | Example observed | Scope | Classification | Confidence | Notes |
|---|---|---|---|---|---|---|---|
| DreamStatus | TGDReports.mdb / ReportsRT | Dream, RepDate, RepTime, RepCode, RepCodeStr, State | Dream 13, `Valvula se abrio`, State 0 | Shared, Dream-scoped by column | CANDIDATE | 0.45 | Event/report evidence, not proven general health. |
| Programs | TGDStatistics.mdb / Programs | Unit, ProgName, ProgNameStr, StartCond, StopCond | Unit 11; names may be empty | Shared; relation Unit-to-Dream unconfirmed | CANDIDATE | 0.40 | Configuration-like fields; active execution is not evidenced. |
| Valves | Dream*_1.mdb / TactName10 | Valve, Name | Common schema across detected Dreams | Dream-specific | CANDIDATE | 0.50 | Naming table only; no open/closed signal observed. |
| WaterMeters | TGDStatistics.mdb / Water_Meters and LastWM | Dream, WM_Number, WM_GType, ValueA | Dream 11, subtype 22, numeric reading | Shared, Dream-scoped | PROBABLE | 0.65 | Join hypothesis is evidence-backed but not yet validated exhaustively. |
| Flow | TGDStatistics.mdb / RTWMFlow | Dream, DateA, TimeA, ValueA | Dream 11, subtype 54, ValueA 0 | Shared, Dream-scoped | CANDIDATE | 0.55 | Table name suggests flow; units and subtype meanings unknown. |
| Alarms | TGDReports.mdb / ReportsRT | RepCode, RepCodeStr, RepFail | `Caudal Bajo %`, RepFail true | Shared, Dream-scoped | CANDIDATE | 0.55 | Event may be alarm, workflow report, or historical event. |
| Fertigation | TGDStatistics.mdb / RTFert, RTFertFlow | Dream, DateF, TimeF, ValueF | Dream 11 numeric records | Shared, Dream-scoped | CANDIDATE | 0.50 | Current versus historical role is not confirmed. |
| Accumulations | TGDStatistics.mdb / LastAccum, RTAccum, DailyAccum | Dream, WAccum_Vol, WAccum_Time | Dream 13, WAccum_Vol 76466.75 | Shared, Dream-scoped | CANDIDATE | 0.55 | Scope per line/tact is visible; units require confirmation. |
