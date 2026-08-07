# STEP081 root package and architecture restructuring — code audit

## Audited baseline

The immutable STEP080A ZIP was re-extracted and hashed before comparison. The product baseline inventory contains 3,224 packaged files and is bound to ZIP SHA-256 `11a554e6a0fda3e728002ce915e9b3729622928919f30c5d30390814d2d29702`.

## Source relocation audit

```text
legacy source root: src/okcanvas_agent_runtime
legacy first-level entries: 65
legacy Python files: 262
legacy resource files: 10
registered Python relocations: 262
registered resource relocations: 10
missing relocations: 0
legacy source root present: false
```

`governance/`, which was absent from the stale STEP080 migration map, is included in the current inventory and relocation manifest.

## Current module audit

```text
canonical Python modules: 323
compatibility aliases: 301
alias target failures: 0
AST failures: 0
missing internal imports: 0
import cycles: 0
eager import cycles: 0
dependency-direction violations: 0
```

The dependency scan evaluates actual AST imports and executable package initialization. It rejects Client→Runtime, Protocol→Runtime, Transport→Adapter/Agent/Domain/Client/Bootstrap, Application→concrete Adapter/Transport, Agent→Transport framework, Adapter→Transport, and Bootstrap-owned route bodies.

## Runtime composition audit

Executable FastAPI composition produces 86 HTTP method/path records:

```text
Admin /v1 routes: 48
Service routes: 33
Console/Runner/health routes: 5
method/path duplicates: 0
WebSocket routes: 0
```

Transport modules contain no direct ProductStore, SQLite, Coordinator, attachment/snapshot store or concrete authority access. SSE encodes the Application subscription port. Concrete composition is located under `okcanvas_agent_runtime/bootstrap/application.py`.

## Compatibility audit

`okcanvas_agent_runtime/compatibility/import_aliases.py` and its manifest provide 301 lazy aliases. Old and new import paths resolve to the same exported objects. Historical source-inspection tests use `LegacySourceContract`, which resolves one legacy logical component to one or more canonical sources/resources without recreating the removed `src` tree.

## Package-data audit

The constitution resources and Client Console/Runner static assets are owned by canonical packages and included in wheel/package validation. The exact wheel payload contains 334 expected files with zero missing, extra or SHA-mismatched entries.

## Validation audit

The bounded Python runner enumerates every `tests/test_*.py` file and stores per-chunk JUnit counts and logs. Current and Fresh-ZIP runs each completed 12/12 chunks and 900/900 tests with zero failures, errors, skips or timeouts. Node, Reference, direct-import, npm-pack, compile/import and installation checks are separately evidenced.

## Known external boundary

Linux lacks the real `hatchling>=1.27` backend and uses a non-packaged test-only PEP 517 shim solely to validate installable wheel/editable contents. Real Hatchling and actual OpenAI/MCP dependencies remain part of the Windows live contract. No shim is included in the Product ZIP.
