import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path

from okcanvas_agent_runtime.adapters.evidence import JsonlEventJournal


@dataclass(frozen=True)
class FakeThreadStarted:
    thread_id: str
    type: str = field(default="thread.started", init=False)

    def as_dict(self):
        return {"thread_id": self.thread_id, "type": self.type}


class FakePayload:
    def __init__(self, event):
        self.event = event


def test_jsonl_journal_records_sequence_thread_and_hash(tmp_path: Path) -> None:
    journal = JsonlEventJournal(tmp_path / "events.jsonl")
    asyncio.run(journal.record_codex_payload(FakePayload(FakeThreadStarted("thread_1"))))
    journal.append(event_type="turn.completed", payload={"usage": {"output_tokens": 3}})
    rows = [json.loads(line) for line in journal.path.read_text().splitlines()]
    assert [row["sequence"] for row in rows] == [1, 2]
    assert rows[0]["thread_id"] == "thread_1"
    assert journal.thread_id == "thread_1"
    assert journal.event_types == {"thread.started", "turn.completed"}
    assert len(journal.sha256()) == 64
