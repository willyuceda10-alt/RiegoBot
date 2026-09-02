# Flow Contract

`TGDStatistics.mdb.RTWMFlow` has Dream-scoped rows keyed by `(Dream, ObjSubType, ObjNum)` and timestamped `ValueA`. All 21,735 observed rows join to `Water_Meters` using the same candidate key; none is unmatched. Counts by group include Dream 11/22 (5,556), Dream 11/54 (6,482), Dream 11/58 (3,241), Dream 13/22 (4,620), Dream 13/58 (462), and Dream 17/22 (1,374).

Observed `ValueA` ranges are 0-120 for Dream 11 group 22, 0-360 for Dream 13 group 22, and 0-288 for Dream 17 group 22. Groups 54 and 58 are zero in the sampled aggregate. The table name is evidence for a flow candidate, but no unit, scale, frequency, or instantaneous-versus-derived semantic is documented. No normalized Flow entity is emitted.
