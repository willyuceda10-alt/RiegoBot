# Shared Database Relationships

| Database | Purpose indicated by structure | Dream relationship | Evidence | Status | Confidence | Useful for realtime | Useful for history |
|---|---|---|---|---|---|---|---|
| TGDStatistics.mdb | Statistics, readings, accumulations, configuration | Many tables include `Dream` with observed values 11, 13, and 17. | `LastWM`, `LastAccum`, `RTWM`, `RTFert`, and `Water_Meters` have `Dream`; sampled rows matched configured identifiers. | CONFIRMED | 0.90 | Candidate, timestamp freshness unverified | Yes, candidate |
| TGDReports.mdb | Reports/events | `ReportsRT.Dream` is populated in observed rows. | Sampled reports for Dream 13 include date/time, code, text, and flags. | CONFIRMED | 0.90 | Candidate, event freshness unverified | Yes, candidate |
| Prog.mdb | Program names | `Unit` is populated; its equivalence to Dream is unproven. | Sample rows with Unit 17 exist. | CANDIDATE | 0.40 | No | Candidate |
| Cont.mdb | Contacts | `System`, `Unit` columns only. | Schema observed; no row relationship sampled. | CANDIDATE | 0.30 | No | Unknown |
| Sat.mdb | Satellites | `System`, `Unit` columns only. | Schema observed; no row relationship sampled. | CANDIDATE | 0.30 | No | Unknown |
| WM.mdb | Water-meter names | `System`, `Unit` columns only. | Sample rows with Unit 11 exist. | CANDIDATE | 0.40 | No | Candidate |
| ans.mdb | Analog sensors/graphs | ASensor has `System`, `Dream`; other tables have Unit. | Schema observed; data relationship not sampled. | CANDIDATE | 0.40 | Candidate | Candidate |

`CONFIRMED` here only confirms that a shared table stores a populated Dream identifier matching configured DreamIds. It does not confirm every field's operational semantics.
