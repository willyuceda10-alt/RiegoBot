# Python MDB Compatibility

The validated reader uses OLE DB providers in PowerShell: Jet 4.0, ACE 16.0, then ACE 12.0, all with `Mode=Read`. Python 3.11+ is selected for the portable control plane because it can use only the standard library for configuration, discovery, output, and validation.

MDB access is intentionally not migrated in this phase. A future `DatabaseAdapter` interface defines `open_readonly`, `execute_select`, `read_schema`, and `close`. `AceAdapter` may use a tested 64-bit ODBC/OLE DB path; `JetBridgeAdapter` may retain the current PowerShell/VBS bridge for 32-bit Jet installations. Python, driver, and provider bitness must match. A 64-bit Python process cannot assume access to a 32-bit Jet provider.
