from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_single_canonical_template_and_initializer() -> None:
    assert (ROOT / ".env.local.example").is_file()
    assert not (ROOT / ".env.example").exists()
    assert not (ROOT / ".env.local.cmd.example").exists()
    source = (ROOT / "scripts" / "init_local_env.py").read_text(encoding="utf-8")
    assert "generate_protected_payload_key" in source
    assert "secrets.token_urlsafe(32)" in source
    assert "OPENAI_API_KEY" in source
    launcher = (ROOT / "sh_init_local_env.cmd").read_text(encoding="utf-8")
    assert '.venv\\Scripts\\python.exe" scripts\\init_local_env.py %*' in launcher
