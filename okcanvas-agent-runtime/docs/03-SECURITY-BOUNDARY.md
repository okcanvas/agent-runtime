# Security Boundary

STEP002 enables only the official experimental Codex integration over an explicitly selected repository.

## Enabled

- model calls after explicit opt-in;
- Codex CLI subprocess after readiness checks;
- read-only sandbox;
- non-mutating command execution inside Codex;
- JSONL event and usage evidence;
- explicit Codex thread continuation;
- explicit confirmation that the workspace is controlled;
- Git repository requirement;
- symbolic-link rejection;
- Evidence and thread files required outside the analyzed workspace;
- minimal subprocess environment allowlist.

## Disabled

- workspace write;
- arbitrary runtime shell Tool;
- web search in Codex;
- general use on untrusted repositories;
- a claim that arbitrary-command network denial is live-proven;
- MCP;
- Git write by the runtime;
- database or external-system access;
- deployment.

The runtime computes the source tree SHA-256 before and after the Codex run. A difference is a hard failure even if the model reports success. `.git` and transient Python cache directories are explicitly excluded from the source snapshot and listed in the evidence.

The Codex subprocess does not inherit the complete Agent process environment. Only a small platform/runtime allowlist is passed, and the Codex API key is added through the inspected SDK option. Other environment secrets are not intentionally propagated. Secrets are not placed in prompts, result envelopes, event metadata, thread state, or ZIP artifacts.

## STEP017 local Run submission boundary

The environment-started Control API disables direct `POST /v1/runs` by default. The read-only admin key remains sufficient only for GET operations and policy inspection. The future governed submit path must establish `LOCAL_RUN_SUBMITTER` authority separately.

The STEP017 preflight ledger stores Agent identity, policy identity, input SHA-256, request fingerprint, idempotency-key SHA-256, execution mode, and confirmation challenge. It stores no raw prompt, raw idempotency key, model output, Tool arguments, API key, or protected payload. Preflight creates no Product Task or Run and invokes no model.

## STEP018 protected payload and governed execution

The raw read-only Run request is encrypted with AES-256-GCM in a product-owned file outside SQLite. The encryption key is supplied through `OKCANVAS_PROTECTED_PAYLOAD_KEY` and is never written to source, payload files, SQLite, canonical Events, or acceptance Evidence. SQLite stores only an opaque reference, encrypted-file SHA-256, byte length, and non-secret key fingerprint.

Governed preflight and confirmation require both the local-admin credential and the distinct `LOCAL_RUN_SUBMITTER` credential. Exact confirmation is followed by policy, Agent definition, model, fingerprint, payload-file, authenticated-decryption, and capability revalidation. Only then may one transaction create the Product Task, Product Run, initial `run.created` Event, and submission binding.

The operations console remains read-only. Local Tools, write MCP, Handoffs, Sessions, Codex write, stale-claim recovery, and payload deletion are not enabled by STEP018.

## STEP019 claim recovery and payload retention

Execution recovery uses a generation-fenced claim. The raw claim token is returned only to the local scheduling path and is never written to SQLite, canonical Events, payload files, or Evidence. SQLite stores the token SHA-256, owner identity, acquisition/expiry timestamps, attempt count, and recovery count. When a stale eligible claim is recovered, a new generation token replaces the old one. An older scheduled task cannot transition the Product Task/Run to `RUNNING`.

Recovery requires both local-admin and distinct Run-submitter authority. It is explicit, bounded, and limited to Task `READY` plus Run `CREATED`. STEP019 does not reclaim or resume an already `RUNNING` Product Run and does not implement distributed worker leases.

Protected-payload retention follows the immutable lifecycle policy. Successful Runs delete the encrypted payload immediately after terminal synchronization. Failed or cancelled Runs retain it for seven days for investigation. Unconfirmed submissions expire after 24 hours. Cleanup is an authenticated explicit operation with a maximum batch of 100. Deletion failure is recorded rather than hidden. The operations console remains read-only.

## STEP020 encrypted SDK RunState and Tool approval

Approval-interrupted Runs keep request text in the existing AES-256-GCM protected payload store. SDK RunState is separately encrypted under `OKCANVAS_RUN_STATE_ROOT`; only its opaque reference, file SHA-256, byte length, and key fingerprint enter SQLite. Raw Tool arguments and call IDs are hashed, not persisted. Approval resume uses a fresh generation token whose SHA-256 is stored. The Tool body must atomically claim persisted execution count `0→1` with that token before accessing the protected request.
