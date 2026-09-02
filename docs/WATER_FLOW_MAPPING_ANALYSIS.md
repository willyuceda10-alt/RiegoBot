# Water and Flow Mapping Analysis

`Water_Meters` includes Dream-scoped metadata: `WM_Ind`, `WM_GType`, `WM_Number`, `WM_Ratio`, and `WM_SName`. `LastWM` includes Dream-scoped, timestamped `ObjSubType`, `ObjNum`, and `ValueA`. In observed Dream 11 samples, `ObjSubType=22` and `ObjNum=1..5` overlap `WM_GType=22` and `WM_Number=1..5`; this is PROBABLE, not confirmed as a join contract.

`RTWMFlow` includes timestamped `ValueA` with Dream identity, but its unit and subtype interpretation are unknown. `LastWM` is treated as a candidate accumulated/latest reading, while `RTWMFlow` is treated as a candidate instantaneous-flow source. No normalized water or flow output is emitted yet.
