# Data Mapping Evidence

Confidence scale: LOW 0.00-0.39, MEDIUM 0.40-0.69, HIGH 0.70-0.89, VERIFIED 0.90-1.00. `CONFIRMED` is reserved for a relationship directly supported by structure and observed values; it does not claim undocumented business semantics.

| Entity | Database | Table | Column(s) | DreamKey | Evidence observed | Classification | Confidence |
|---|---|---|---|---|---|---|---|
| DreamStatus observation | TGDReports.mdb | ReportsRT | Dream, RepDate, RepTime, RepCode, RepCodeStr, State | Resolved from `Dream` only | Rows observed with `Dream=13`, dated report events such as `Valvula se abrio` and `Caudal Bajo %`. | CANDIDATE | 0.45 |
| Water-meter reading | TGDStatistics.mdb | LastWM | Dream, ObjSubType, ObjNum, DateA, TimeA, ValueA | Resolved from `Dream` only | Rows observed for Dream 11 with timestamped numeric values; table name and fields indicate a last reading. | PROBABLE | 0.65 |
| Water-meter metadata | TGDStatistics.mdb | Water_Meters | Dream, WM_Ind, WM_GType, WM_Number, WM_Ratio | Resolved from `Dream` only | Dream 11 rows show `WM_GType=22` and `WM_Number` values overlapping LastWM subtype/number values. | PROBABLE | 0.65 |
| Accumulation | TGDStatistics.mdb | LastAccum | Dream, Date, Time, WAccum_Vol, WAccum_Time | Resolved from `Dream` only | Dream 13 rows contain timestamped volume/time values. Unit and exact business scope remain unverified. | CANDIDATE | 0.55 |
| Fertigation reading | TGDStatistics.mdb | RTFert / RTFertFlow | Dream, ObjType, ObjSubType, ObjNum, DateF, TimeF, ValueF | Resolved from `Dream` only | Dream 11 rows observed with timestamped numeric values. Object coding is undocumented. | CANDIDATE | 0.50 |

`State` in `ReportsRT` is exported only as `SourceStateRaw`. It is not mapped to a status label. No communication, active-program, active-valve, or active-alarm flag is confirmed in this phase.
