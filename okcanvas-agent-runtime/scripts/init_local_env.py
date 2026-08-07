from __future__ import annotations

import argparse
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from okcanvas_agent_runtime.adapters.storage.protected_payload import generate_protected_payload_key


def initialize(*, force: bool = False) -> Path:
    template = ROOT / ".env.local.example"
    target = ROOT / ".env.local"
    if not template.is_file():
        raise RuntimeError("Canonical .env.local.example is missing")
    if target.exists() and not force:
        raise RuntimeError(".env.local already exists; use --force only when replacement is intentional")
    text = template.read_text(encoding="utf-8")
    replacements = {
        "replace-with-at-least-16-random-characters": secrets.token_urlsafe(32),
        "replace-with-a-distinct-at-least-16-character-key": secrets.token_urlsafe(32),
        "replace-with-generated-32-byte-urlsafe-base64-key": generate_protected_payload_key(),
    }
    for placeholder, value in replacements.items():
        if placeholder not in text:
            raise RuntimeError(f"Required placeholder is missing: {placeholder}")
        text = text.replace(placeholder, value, 1)
    target.write_text(text, encoding="utf-8", newline="\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        target = initialize(force=args.force)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 2
    print(f"[OK] Created {target.name} with distinct local authority keys and a 32-byte payload key.")
    print("[NEXT] Set OPENAI_API_KEY and OKCANVAS_AGENT_MODEL in .env.local, then run sh_run_api.cmd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
