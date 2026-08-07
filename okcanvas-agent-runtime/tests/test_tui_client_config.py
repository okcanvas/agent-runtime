from __future__ import annotations

import pytest

from okcanvas_agent_clients.tui import TUIClientConfig, TUIClientError


ADMIN = "tui-test-admin-key"
SUBMITTER = "tui-test-submitter-key"


def test_tui_config_accepts_explicit_loopback_and_separate_authorities() -> None:
    config = TUIClientConfig(
        base_url="http://127.0.0.1:8765/",
        admin_key=ADMIN,
        submitter_key=SUBMITTER,
    )
    assert config.base_url == "http://127.0.0.1:8765"
    assert config.admin_key == ADMIN
    assert config.submitter_key == SUBMITTER


@pytest.mark.parametrize(
    ("base_url", "code"),
    [
        ("http://example.com:8765", "TUI_REMOTE_URL_FORBIDDEN"),
        ("file:///tmp/socket", "TUI_BASE_URL_INVALID"),
        ("http://127.0.0.1", "TUI_BASE_URL_INVALID"),
        ("http://user:pass@127.0.0.1:8765", "TUI_BASE_URL_INVALID"),
        ("http://127.0.0.1:8765/control", "TUI_BASE_URL_INVALID"),
    ],
)
def test_tui_config_rejects_non_loopback_or_ambiguous_urls(
    base_url: str,
    code: str,
) -> None:
    with pytest.raises(TUIClientError) as caught:
        TUIClientConfig(
            base_url=base_url,
            admin_key=ADMIN,
            submitter_key=SUBMITTER,
        )
    assert caught.value.code == code


def test_tui_config_requires_separate_authorities() -> None:
    with pytest.raises(TUIClientError) as caught:
        TUIClientConfig(
            base_url="http://localhost:8765",
            admin_key=ADMIN,
            submitter_key=ADMIN,
        )
    assert caught.value.code == "TUI_AUTHORITY_NOT_SEPARATED"
