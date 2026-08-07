# Reference Catalog Tool

Implemented in STEP006 as a local read-only application service and CLI.

The service:

- loads only `reference/MANIFEST.json` declared roots;
- consults `reference/CODE_MAP.md` before broad text scanning;
- verifies the selected immutable tree SHA, file count, byte count, and absence of symbolic links before access;
- accepts only POSIX relative file paths under the selected reference root;
- rejects absolute paths, drive-qualified paths, traversal, symbolic links, missing files, binary reads, oversized reads, and unbounded result requests;
- returns exact reference ID, classification, version, relative path, line number/range, file SHA-256, and bounded text;
- records canonical Run events through an optional STEP005 product-store adapter without storing the raw search query.

It is not an MCP server, HTTP service, embedding index, vector database, or general filesystem browser.
