# Valve Mapping Analysis

All detected Dream-specific MDB files expose `TactName10(Valve, Name, Reserved1, Reserved2)`. This is a common naming structure and preserves DreamKey through the file identity. It does not contain an observed open/closed or active field, so no ActiveValves mapping is created.

`ReportsRT` contains event text such as `Valvula se abrio`, but linking that event to a stable valve identifier requires documentation for `Repid1`, `Repid2`, and `Repid2Name`. That is the next experiment before creating an active-valve extractor.
