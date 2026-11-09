# Access Tools

The maintained reader and example code is committed under
`tools/cda_v2/` in the same branch.

Use:

```powershell
$env:PYTHONPATH = "E:\mtah2027-code"
.\.venv\Scripts\python.exe tools\cda_v2\examples\inspect_sources.py `
  "E:\mtah2027-code\outputs\Cross-Match-Open-Data-v2"
```

The readers use only the Python standard library. Kloppy was not available
because PyPI was unreachable; the source-specific parsing method is recorded in
the handoff documentation.
