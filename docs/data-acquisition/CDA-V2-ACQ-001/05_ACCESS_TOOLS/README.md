# Access Tools

The maintained reader and example code is committed under
`tools/cda_v2/` in the same branch.

Use:

```powershell
$env:PYTHONPATH = "<REPO_ROOT>"
.\.venv\Scripts\python.exe tools\cda_v2\examples\inspect_sources.py `
  "<CONTROLLED_PACKAGE_ROOT>"
```

Use the reassembled controlled package root, not the Git repository root.

The readers use only the Python standard library. Kloppy was not available
because PyPI was unreachable; the source-specific parsing method is recorded in
the handoff documentation.
