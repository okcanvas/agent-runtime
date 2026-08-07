from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_architecture_baseline_documents_exist() -> None:
    expected = [
        "docs/06-REFERENCE-ADOPTION-MATRIX.md",
        "docs/07-TARGET-PLATFORM-ARCHITECTURE.md",
        "docs/08-SERVICE-BOUNDARIES.md",
        "docs/09-DELIVERY-ROADMAP.md",
        "docs/decisions/ADR-006-MODULAR-MONOLITH-FIRST.md",
        "docs/decisions/ADR-007-CODEX-OPTIONAL-ADAPTER.md",
        "docs/decisions/ADR-008-PRODUCT-STATE-IS-NOT-SDK-STATE.md",
        "specs/runtime/domain-model.yaml",
        "specs/runtime/canonical-events.yaml",
    ]
    for relative in expected:
        assert (ROOT / relative).is_file(), relative


def test_roadmap_makes_core_store_primary_and_codex_optional() -> None:
    roadmap = (ROOT / "docs/09-DELIVERY-ROADMAP.md").read_text(encoding="utf-8")
    assert "STEP005 — Core Task, Run, Event and Artifact Store" in roadmap
    assert "optional parallel track" in roadmap.lower()
    assert "Codex" in roadmap


def test_product_and_sdk_state_are_separated() -> None:
    architecture = (ROOT / "docs/07-TARGET-PLATFORM-ARCHITECTURE.md").read_text(
        encoding="utf-8"
    )
    for product_state in ("Task", "Run", "Run Event", "Approval", "Artifact", "Validation"):
        assert product_state in architecture
    for adapter_state in ("Session", "RunState", "Trace", "Codex Thread"):
        assert adapter_state in architecture


def test_runtime_specs_are_not_python_packages() -> None:
    runtime_specs = ROOT / "specs/runtime"
    assert runtime_specs.is_dir()
    assert not (runtime_specs / "__init__.py").exists()
