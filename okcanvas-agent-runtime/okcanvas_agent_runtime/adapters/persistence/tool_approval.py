from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from okcanvas_agent_runtime.application.approvals.errors import ToolApprovalIntegrityError, ToolApprovalNotFound, ToolApprovalStateError
from okcanvas_agent_runtime.application.approvals.models import ToolApprovalDecision, ToolApprovalRecord, ToolApprovalState

_SCHEMA = """
CREATE TABLE IF NOT EXISTS governed_tool_approval (
  approval_id TEXT PRIMARY KEY,
  submission_id TEXT NOT NULL UNIQUE,
  task_id TEXT NOT NULL UNIQUE,
  run_id TEXT NOT NULL UNIQUE,
  session_id TEXT,
  session_item_count_before INTEGER,
  state TEXT NOT NULL,
  decision TEXT,
  tool_name TEXT NOT NULL,
  tool_call_id_sha256 TEXT NOT NULL,
  arguments_sha256 TEXT NOT NULL,
  run_state_ref TEXT NOT NULL UNIQUE,
  run_state_sha256 TEXT NOT NULL,
  run_state_byte_length INTEGER NOT NULL,
  run_state_key_id TEXT NOT NULL,
  trace_id TEXT,
  response_id TEXT,
  tool_execution_count INTEGER NOT NULL DEFAULT 0,
  resume_generation INTEGER NOT NULL DEFAULT 0,
  resume_token_sha256 TEXT,
  created_at TEXT NOT NULL,
  decided_at TEXT,
  completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_governed_tool_approval_state
ON governed_tool_approval(state, created_at);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _canonical(payload: dict[str, Any]) -> tuple[str, str]:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


class SQLiteToolApprovalStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=15, isolation_level=None, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as c:
            c.executescript(_SCHEMA)
            columns = {str(row["name"]) for row in c.execute("PRAGMA table_info(governed_tool_approval)").fetchall()}
            if "resume_generation" not in columns:
                c.execute("ALTER TABLE governed_tool_approval ADD COLUMN resume_generation INTEGER NOT NULL DEFAULT 0")
            if "resume_token_sha256" not in columns:
                c.execute("ALTER TABLE governed_tool_approval ADD COLUMN resume_token_sha256 TEXT")
            if "session_id" not in columns:
                c.execute("ALTER TABLE governed_tool_approval ADD COLUMN session_id TEXT")
            if "session_item_count_before" not in columns:
                c.execute("ALTER TABLE governed_tool_approval ADD COLUMN session_item_count_before INTEGER")

    def get(self, approval_id: str) -> ToolApprovalRecord:
        with self._connection() as c:
            row = c.execute("SELECT * FROM governed_tool_approval WHERE approval_id=?", (approval_id,)).fetchone()
        if row is None:
            raise ToolApprovalNotFound(f"Tool approval not found: {approval_id}")
        return self._from_row(row)

    def find_by_submission(self, submission_id: str) -> ToolApprovalRecord | None:
        with self._connection() as c:
            row = c.execute("SELECT * FROM governed_tool_approval WHERE submission_id=?", (submission_id,)).fetchone()
        return self._from_row(row) if row else None

    def list(
        self,
        *,
        state: ToolApprovalState | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ToolApprovalRecord], int]:
        if limit < 1 or limit > 200:
            raise ValueError("Tool approval limit must be between 1 and 200")
        if offset < 0:
            raise ValueError("Tool approval offset must be non-negative")
        where = ""
        params: list[Any] = []
        if state is not None:
            where = " WHERE state=?"
            params.append(state.value)
        with self._connection() as c:
            total = int(
                c.execute(
                    f"SELECT COUNT(*) FROM governed_tool_approval{where}",
                    tuple(params),
                ).fetchone()[0]
            )
            rows = c.execute(
                f"SELECT * FROM governed_tool_approval{where} "
                "ORDER BY created_at DESC, approval_id DESC LIMIT ? OFFSET ?",
                tuple([*params, limit, offset]),
            ).fetchall()
        return [self._from_row(row) for row in rows], total

    def state_counts(self) -> dict[str, int]:
        counts = {state.value: 0 for state in ToolApprovalState}
        with self._connection() as c:
            rows = c.execute(
                "SELECT state, COUNT(*) AS count FROM governed_tool_approval GROUP BY state"
            ).fetchall()
        for row in rows:
            counts[str(row["state"])] = int(row["count"])
        return counts

    def create_pending(
        self, *, approval_id: str, submission_id: str, task_id: str, run_id: str,
        tool_name: str, tool_call_id_sha256: str, arguments_sha256: str,
        run_state_ref: str, run_state_sha256: str, run_state_byte_length: int,
        run_state_key_id: str, trace_id: str | None, response_id: str | None,
        session_id: str | None = None, session_item_count_before: int | None = None,
    ) -> ToolApprovalRecord:
        with self._connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                existing = c.execute("SELECT * FROM governed_tool_approval WHERE submission_id=?", (submission_id,)).fetchone()
                if existing:
                    c.commit(); return self._from_row(existing)
                s = c.execute("SELECT state, task_id, run_id FROM run_submission_preflight WHERE submission_id=?", (submission_id,)).fetchone()
                t = c.execute("SELECT status FROM task WHERE task_id=?", (task_id,)).fetchone()
                r = c.execute("SELECT status FROM run WHERE run_id=?", (run_id,)).fetchone()
                if not s or s["task_id"] != task_id or s["run_id"] != run_id:
                    raise ToolApprovalIntegrityError("Submission binding does not match approval")
                if s["state"] != "EXECUTION_STARTED" or not t or t["status"] != "RUNNING" or not r or r["status"] != "RUNNING":
                    raise ToolApprovalStateError("Run is not in an interruptible running state")
                now = _now()
                c.execute("""INSERT INTO governed_tool_approval(
                  approval_id,submission_id,task_id,run_id,session_id,session_item_count_before,state,decision,tool_name,
                  tool_call_id_sha256,arguments_sha256,run_state_ref,run_state_sha256,
                  run_state_byte_length,run_state_key_id,trace_id,response_id,created_at)
                  VALUES(?,?,?,?,?,?,?,NULL,?,?,?,?,?,?,?,?,?,?)""",
                  (approval_id,submission_id,task_id,run_id,session_id,session_item_count_before,ToolApprovalState.PENDING.value,tool_name,
                   tool_call_id_sha256,arguments_sha256,run_state_ref,run_state_sha256,
                   run_state_byte_length,run_state_key_id,trace_id,response_id,now))
                c.execute("UPDATE task SET status='WAITING_APPROVAL', updated_at=? WHERE task_id=?", (now,task_id))
                c.execute("UPDATE run SET status='INTERRUPTED' WHERE run_id=?", (run_id,))
                c.execute("""UPDATE run_submission_preflight SET state='WAITING_APPROVAL',
                  claim_owner_id=NULL,claim_token_sha256=NULL,claim_acquired_at=NULL,claim_expires_at=NULL
                  WHERE submission_id=?""", (submission_id,))
                self._event(c,run_id,"tool.approval.requested",{
                    "approval_id":approval_id,"tool_name":tool_name,"arguments_persisted":False,
                    "tool_call_id_persisted":False,"run_state_encrypted":True,
                },"okcanvas-tool-approval-requested-v1")
                self._event(c,run_id,"run.interrupted",{"reason":"tool-approval","approval_id":approval_id},"okcanvas-run-interrupted-v1")
                row=c.execute("SELECT * FROM governed_tool_approval WHERE approval_id=?",(approval_id,)).fetchone()
                c.commit()
            except Exception:
                c.rollback(); raise
        return self._from_row(row)

    def claim_decision(self, approval_id: str, decision: ToolApprovalDecision) -> tuple[ToolApprovalRecord,bool,str | None]:
        with self._connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                row=c.execute("SELECT * FROM governed_tool_approval WHERE approval_id=?",(approval_id,)).fetchone()
                if row is None: raise ToolApprovalNotFound(f"Tool approval not found: {approval_id}")
                state=ToolApprovalState(row["state"])
                if state in {ToolApprovalState.SUCCEEDED,ToolApprovalState.REJECTED,ToolApprovalState.FAILED}:
                    if row["decision"] and row["decision"] != decision.value:
                        raise ToolApprovalStateError("Tool approval already has the opposite terminal decision")
                    c.commit(); return self._from_row(row),True,None
                if state is not ToolApprovalState.PENDING:
                    raise ToolApprovalStateError("Tool approval decision is already in progress")
                import secrets
                now=_now(); target=ToolApprovalState.APPROVING if decision is ToolApprovalDecision.APPROVE else ToolApprovalState.REJECTING
                token=secrets.token_urlsafe(32)
                token_sha=hashlib.sha256(token.encode("utf-8")).hexdigest()
                generation=int(row["resume_generation"] or 0)+1
                c.execute("UPDATE governed_tool_approval SET state=?,decision=?,decided_at=?,resume_generation=?,resume_token_sha256=? WHERE approval_id=?",
                          (target.value,decision.value,now,generation,token_sha,approval_id))
                task_update = c.execute(
                    "UPDATE task SET status='RUNNING',updated_at=? WHERE task_id=? AND status='WAITING_APPROVAL'",
                    (now, row["task_id"]),
                )
                run_update = c.execute(
                    "UPDATE run SET status='RUNNING' WHERE run_id=? AND status='INTERRUPTED'",
                    (row["run_id"],),
                )
                submission_update = c.execute(
                    "UPDATE run_submission_preflight SET state='APPROVAL_RESUMING' "
                    "WHERE submission_id=? AND state='WAITING_APPROVAL'",
                    (row["submission_id"],),
                )
                if task_update.rowcount != 1 or run_update.rowcount != 1 or submission_update.rowcount != 1:
                    raise ToolApprovalStateError(
                        "Product Task, Run, and Submission are not in the resumable approval state"
                    )
                self._event(c,row["run_id"],"tool.approval.decided",{
                    "approval_id":approval_id,"decision":decision.value,"tool_name":row["tool_name"]
                },"okcanvas-tool-approval-decided-v1")
                self._event(c,row["run_id"],"run.resumed",{"approval_id":approval_id},"okcanvas-run-resumed-v1")
                updated=c.execute("SELECT * FROM governed_tool_approval WHERE approval_id=?",(approval_id,)).fetchone()
                c.commit()
            except Exception:
                c.rollback(); raise
        return self._from_row(updated),False,token

    def begin_tool_execution(self, approval_id: str, *, resume_token: str) -> bool:
        token_sha = hashlib.sha256(resume_token.encode("utf-8")).hexdigest()
        with self._connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                row=c.execute("SELECT * FROM governed_tool_approval WHERE approval_id=?",(approval_id,)).fetchone()
                if row is None: raise ToolApprovalNotFound(f"Tool approval not found: {approval_id}")
                if row["state"] != ToolApprovalState.APPROVING.value or row["decision"] != ToolApprovalDecision.APPROVE.value:
                    c.commit(); return False
                if row["resume_token_sha256"] != token_sha or int(row["tool_execution_count"] or 0) != 0:
                    c.commit(); return False
                c.execute("UPDATE governed_tool_approval SET tool_execution_count=1,resume_token_sha256=NULL WHERE approval_id=?",(approval_id,))
                c.commit(); return True
            except Exception:
                c.rollback(); raise

    def finish(self, approval_id: str, *, state: ToolApprovalState, tool_execution_count: int) -> ToolApprovalRecord:
        if state not in {ToolApprovalState.SUCCEEDED,ToolApprovalState.REJECTED,ToolApprovalState.FAILED}:
            raise ValueError("finish requires a terminal approval state")
        with self._connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                row=c.execute("SELECT * FROM governed_tool_approval WHERE approval_id=?",(approval_id,)).fetchone()
                if row is None: raise ToolApprovalNotFound(f"Tool approval not found: {approval_id}")
                now=_now()
                current_count=int(row["tool_execution_count"] or 0)
                if tool_execution_count != current_count:
                    raise ToolApprovalIntegrityError("Tool execution count does not match the persisted generation fence")
                c.execute("UPDATE governed_tool_approval SET state=?,completed_at=?,resume_token_sha256=NULL WHERE approval_id=?",
                          (state.value,now,approval_id))
                updated=c.execute("SELECT * FROM governed_tool_approval WHERE approval_id=?",(approval_id,)).fetchone()
                c.commit()
            except Exception:
                c.rollback(); raise
        return self._from_row(updated)

    def _event(self,c:sqlite3.Connection,run_id:str,event_type:str,payload:dict[str,Any],schema:str)->None:
        encoded,digest=_canonical(payload)
        seq=int(c.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM run_event WHERE run_id=?",(run_id,)).fetchone()[0])
        c.execute("INSERT INTO run_event(run_id,sequence,event_type,source,occurred_at,payload_schema_version,payload_sha256,payload_json) VALUES(?,?,?,?,?,?,?,?)",
                  (run_id,seq,event_type,"operator",_now(),schema,digest,encoded))

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ToolApprovalRecord:
        return ToolApprovalRecord(
            approval_id=row["approval_id"],submission_id=row["submission_id"],task_id=row["task_id"],run_id=row["run_id"],
            session_id=(str(row["session_id"]) if "session_id" in row.keys() and row["session_id"] else None),
            session_item_count_before=(int(row["session_item_count_before"]) if "session_item_count_before" in row.keys() and row["session_item_count_before"] is not None else None),
            state=ToolApprovalState(row["state"]),decision=ToolApprovalDecision(row["decision"]) if row["decision"] else None,
            tool_name=row["tool_name"],tool_call_id_sha256=row["tool_call_id_sha256"],arguments_sha256=row["arguments_sha256"],
            run_state_ref=row["run_state_ref"],run_state_sha256=row["run_state_sha256"],run_state_byte_length=int(row["run_state_byte_length"]),
            run_state_key_id=row["run_state_key_id"],trace_id=row["trace_id"],response_id=row["response_id"],
            tool_execution_count=int(row["tool_execution_count"]),created_at=row["created_at"],decided_at=row["decided_at"],completed_at=row["completed_at"])
