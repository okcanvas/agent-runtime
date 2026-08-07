from pathlib import Path

root = Path(__file__).resolve().parents[1]
handoff = root / "HANDOFF.md"
if not handoff.is_file():
    raise SystemExit("HANDOFF.md is missing")
print(handoff)
print("HANDOFF.md is maintained as a reviewed source document; automatic rewriting is intentionally disabled in STEP002.")
