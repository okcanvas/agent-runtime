# Read-only Reference Catalog

## Purpose

`/reference` is an active implementation answer key. The catalog provides a safe product boundary over it without turning the directory into a writable workspace, imported dependency, or unrestricted RAG corpus.

## Operations

```text
reference-list
reference-verify
reference-search
reference-read
```

Search uses `CODE_MAP.md` first. Matching mapped files are scanned before the remaining verified source tree. Results always contain immutable source identity and file SHA-256.

## Security model

- only roots declared by `MANIFEST.json` exist to the service;
- every access verifies the selected tree hash, file count, byte count and symlink absence;
- only POSIX relative paths are accepted;
- absolute, Windows-drive, backslash, traversal and symlink paths are rejected;
- reads are UTF-8 text only and bounded by file size and line count;
- no method can write, import, execute, install or fetch reference code.

## Evidence model

When attached to a STEP005 Run, the service appends:

- `reference.search.completed` with query SHA-256 and result counts;
- `reference.file.read` with reference ID, path, exact range and file SHA-256.

The raw query and file contents are not written to the Run event payload. A caller may separately store a selected result as an Artifact when a durable review output is required.
