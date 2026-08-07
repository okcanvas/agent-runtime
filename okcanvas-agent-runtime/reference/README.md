# External Reference Source

This directory preserves supplied upstream source snapshots for ongoing code inspection.

## Rules

- Read `MANIFEST.json` and `CODE_MAP.md` first.
- Treat `upstream/**` as immutable.
- Do not import it into the runtime.
- Do not run upstream applications as proof of our implementation.
- Cite exact upstream paths in design findings.
- Verify integrity with `python scripts/verify_reference.py`.
