# Researcher Quickstart

Run examples with the pinned package root:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
python 05_ACCESS_TOOLS/BASIC_EXAMPLES/inspect_sources.py .
```

POSIX shells use the same forward-slash path and `PYTHONDONTWRITEBYTECODE=1`.

Reassemble a package from the five verified archives:

```powershell
python tools/cda_v2/reassemble_package.py `
  --archive-root <ARCHIVE_ROOT> `
  --output <EMPTY_OUTPUT>
```

The readers require only the Python standard library. Optional Kloppy loading was
not available because PyPI was unreachable during acquisition; exact source formats
and reproducible equivalent parsers are supplied here.

Start with `MATCH_INVENTORY.csv`, then use the source-specific reader. Do not infer
continuous H/A/D/X truth from StatsBomb or Wyscout events.
