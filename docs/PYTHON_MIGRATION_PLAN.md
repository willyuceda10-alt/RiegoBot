# Python Migration Plan

| Component | Decision |
|---|---|
| Config, path resolution, session identity, discovery, output, models, mapping resolver | MIGRATE_NOW |
| MDB provider probing and schema/data access | KEEP_POWERSHELL until a matching Python adapter is tested on each target architecture |
| CMD bootstrap and PowerShell validation | KEEP_POWERSHELL during transition |
| Existing VBS V1.2.1 reader | DEPRECATE_LATER; preserve unchanged as compatibility baseline |

The Python module is dependency-free and works from `__file__`-derived project paths, including UNC roots. It does not open MDB files yet; this prevents an untested Python driver from changing the stable read path.
