# Researcher Quickstart

Run examples with the pinned package root:

```powershell
.\.venv\Scripts\python.exe 05_ACCESS_TOOLS\BASIC_EXAMPLES\inspect_sources.py .
```

The readers require only the Python standard library. Optional Kloppy loading was
not available because PyPI was unreachable during acquisition; exact source formats
and reproducible equivalent parsers are supplied here.

Start with `MATCH_INVENTORY.csv`, then use the source-specific reader. Do not infer
continuous H/A/D/X truth from StatsBomb or Wyscout events.
