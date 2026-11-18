# Sandbox

Prototypes of new commands, to test in Rhino 8 before they join the plug-in.

1. Run a prototype with `_RunPythonScript` (or open it in `_ScriptEditor`).
   Start it with `#! python3` and with the development bootstrap below, so the
   shared library in `../src` is reloaded at every run.
2. Once approved, move it to `commands/`, replacing the bootstrap with the
   guarded import used by the other commands.

```python
import os
import sys

_SRC = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
for _name in [m for m in sys.modules if m.split(".")[0] == "pocketknife"]:
    del sys.modules[_name]
```
