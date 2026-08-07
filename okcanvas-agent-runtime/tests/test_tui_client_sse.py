from __future__ import annotations

from okcanvas_agent_clients.tui import parse_sse_json, parse_sse_lines


def test_sse_parser_ignores_comments_and_preserves_multiline_data() -> None:
    messages = list(
        parse_sse_lines(
            [
                ": heartbeat",
                "",
                "id: 7",
                "event: run.completed",
                'data: {"run_id":"run_1",',
                'data: "sequence":7}',
                "",
            ]
        )
    )
    assert len(messages) == 1
    assert messages[0].event_id == "7"
    assert messages[0].event_type == "run.completed"
    assert messages[0].data == '{"run_id":"run_1",\n"sequence":7}'


def test_sse_json_parser_returns_persisted_event_object() -> None:
    events = list(
        parse_sse_json(
            [
                "id: 1",
                "event: run.created",
                'data: {"run_id":"run_1","sequence":1,"event_type":"run.created"}',
                "",
            ]
        )
    )
    assert events == [
        {"run_id": "run_1", "sequence": 1, "event_type": "run.created"}
    ]
