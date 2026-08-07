from pathlib import Path


def test_active_reference_use_is_binding_constitution() -> None:
    root = Path(__file__).resolve().parents[1]
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    constitution = (root / "docs" / "00-CONSTITUTION.md").read_text(encoding="utf-8")
    adoption = (root / "docs" / "06-REFERENCE-ADOPTION-MATRIX.md").read_text(encoding="utf-8")

    assert "Actively consult `/reference`" in agents
    assert "implementation answer key, not passive archive material" in agents
    assert "adopted, adapted, deferred, or deliberately rejected" in agents
    assert "must be actively consulted as implementation answer keys" in constitution
    assert "Mandatory reference-use workflow" in adoption
    assert "reference/upstream/**" in adoption
