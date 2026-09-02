# Water Meter Contract

## Tables and fields

`TGDStatistics.mdb.Water_Meters` has `Dream`, `WM_Ind`, `WM_GType`, `WM_Number`, `WM_Ratio`, and `WM_SName`. `TGDStatistics.mdb.LastWM` has `Dream`, `ObjSubType`, `ObjNum`, `DateA`, `TimeA`, and `ValueA`.

## Observed relationship

The candidate natural key is `(Dream, WM_GType, WM_Number)` on `Water_Meters` and `(Dream, ObjSubType, ObjNum)` on `LastWM`.

| Check | Observed result |
|---|---:|
| Definition rows | 47 |
| Last-reading rows | 47 |
| Duplicate composite keys on either side | 0 |
| Inner-join matches | 47 |
| Unmatched definitions | 0 |
| Unmatched readings | 0 |

The observed cardinality is 1:1 for the inspected snapshot. Dream 11 has groups 22, 54, and 58; Dream 13 has 22 and 58; Dream 17 has 22. `WM_SName` was empty in the sampled definitions, so no meter name is emitted. `WM_Ratio` is retained as raw metadata only.

`Water_Meters` is PROBABLE catalog/configuration data and `LastWM` is PROBABLE last-reading data. `ValueA` is preserved as `RawValue`; its unit, whether it is an accumulated total, and the meanings of the group codes are unresolved. The relationship is not promoted to CONFIRMED until those semantics are independently documented or verified.
