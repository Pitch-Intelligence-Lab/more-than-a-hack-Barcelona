from __future__ import annotations

from scripts.audit_independent_validation import _next_link, summarize_entries


def test_next_link_parser_extracts_cursor_url() -> None:
    header = '<https://example.invalid/tree?cursor=abc>; rel="next"'
    assert _next_link(header) == "https://example.invalid/tree?cursor=abc"
    assert _next_link("") is None


def test_summarize_entries_counts_files_not_directories() -> None:
    entries = [
        {"path": "a", "type": "directory", "size": 0},
        {"path": "a/one", "type": "file", "size": 3},
        {"path": "b/two", "type": "file", "size": 5},
    ]
    assert summarize_entries(entries) == {
        "tree_entries": 3,
        "file_entries": 2,
        "tree_bytes": 8,
        "folder_bytes": {"a": 3, "b": 5},
    }
