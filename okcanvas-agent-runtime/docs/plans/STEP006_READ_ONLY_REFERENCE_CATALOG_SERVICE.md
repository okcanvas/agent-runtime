# STEP006_READ_ONLY_REFERENCE_CATALOG_SERVICE

## Objective

Turn the supplied immutable `/reference` source into a bounded, hash-verified local application service that can be used repeatedly by later Agent, Tool, MCP, streaming, and UI work without treating the source tree as an unrestricted filesystem.

## Reference code inspected

The design started from `reference/CODE_MAP.md` and `reference/MANIFEST.json`, then inspected the smallest applicable upstream paths:

- `reference/upstream/openai-agents-python-0.19.0/src/agents/sandbox/workspace_paths.py`
  - **ADAPT**: normalize a requested path under one declared root and reject paths outside the root.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/sandbox/session/archive_extraction.py`
  - **ADAPT**: reject symbolic-link escape and unsafe path components before file access.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/sandbox/util/token_truncation.py`
  - **ADAPT**: place hard bounds on returned content rather than exposing unbounded files.
- `reference/upstream/openai-agents-python-0.19.0/src/agents/sandbox/`
  - **REJECT for this STEP**: do not instantiate a Sandbox runtime merely to read local immutable source. The catalog has no command execution or write capability.
- `reference/upstream/openai-agents-streaming-api/src/api/utils/agent_router.py`
  - **DEFER**: no HTTP or SSE adapter until the persisted event contract is exposed in STEP008.

The upstream code supplies path and output-safety mechanisms, not the OKCanvas product contract. Manifest identities, immutable tree verification, code-map-first lookup, canonical Run events, and query-redaction are product-owned behavior.

## Scope

- load and validate `reference/MANIFEST.json` and `reference/CODE_MAP.md`;
- expose manifest descriptors;
- verify selected tree SHA-256, file count, byte count, and absence of symbolic links before access;
- code-map-first bounded UTF-8 text search;
- exact bounded line-range reads;
- return reference identity, classification, version, relative path, line/range, byte length and file SHA-256;
- reject absolute paths, drive-qualified paths, traversal, symbolic links, missing files, binary files and unbounded requests;
- optional STEP005 product-store adapter for `reference.search.completed` and `reference.file.read` events;
- CLI commands for list, verify, search and read;
- deterministic local acceptance using the actual supplied reference.

## Non-scope

- embeddings, vector database or semantic RAG;
- MCP server/client;
- HTTP, SSE or UI;
- model or Codex call;
- general project-source search;
- reference mutation, import or execution;
- persistence of raw search queries.

## Contracts

- executable implementation: `src/okcanvas_agent_runtime/reference_catalog/`;
- declarative policy: `specs/tools/reference-search/`;
- canonical event source: `reference`;
- search hard limit: 100 matches;
- default searched file limit: 1 MiB per file;
- default exact read limit: 400 lines and 2 MiB;
- paths are POSIX relative to the selected manifest root only;
- every served search/read verifies the selected immutable tree first;
- search event persistence stores only query SHA-256, not query text.

## Acceptance criteria

1. all four manifest roots verify against tree SHA, file count and byte count;
2. `RunState` lookup returns the CODE_MAP entry for `src/agents/run_state.py` before broad matches;
3. exact line read returns numbered text and matching file SHA;
4. absolute, traversal, drive-qualified and symbolic paths fail closed;
5. altered reference content fails integrity verification before search/read;
6. result, file-size and line-range limits are enforced;
7. reference search/read can append canonical Run events to the STEP005 store;
8. the raw search query is absent from persisted event payloads;
9. before/after full reference verification is identical;
10. full regressions and packaged-ZIP verification pass.

## Failure and recovery

- no partial catalog state is persisted;
- integrity mismatch blocks the operation and identifies the affected reference;
- no auto-repair or manifest rewrite is attempted;
- callers must restore the immutable reference ZIP or stop using the affected source;
- product-store event failure propagates and does not convert the access into recorded success.
