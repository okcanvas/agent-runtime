# STEP068 — Bounded Local PDF and Image Input Foundation

- Version: `2.48.0`
- STEP: `STEP068_BOUNDED_LOCAL_PDF_AND_IMAGE_INPUT_FOUNDATION`
- State before Windows rerun: `IMPLEMENTED_DETERMINISTIC_ACCEPTED_WINDOWS_RERUN_PENDING`

## Objective

Add one Product-owned, bounded local attachment ingress for one isolated Agent without introducing
OpenAI File/Vector Store lifecycle or changing existing text-only Agents.

## Exact scope

- one text instruction;
- zero or one local attachment, with the local-document Agent requiring exactly one;
- PDF, PNG or JPEG only;
- exact magic/signature and structural validation;
- encrypted upload slot and submission-bound attachment storage;
- SDK `input_file` or `input_image` data URL constructed only in memory;
- metadata-only Product Event and Artifact evidence;
- `gpt-4.1` as the immutable V1 multimodal model allowlist.

## Explicit exclusions

- File Search, Vector Store and OpenAI Files API;
- remote URLs or provider file IDs;
- multiple attachments;
- Office, ZIP, audio, video and animated PNG;
- Session, Function Tool, MCP, Handoff, Agent-as-Tool or orchestration composition;
- binary output and raw attachment download API.

## Safety contract

The upload endpoint accepts a bounded raw request body and a filename header. The claimed content
type is not trusted. The Product validates bytes, encrypts them with a key derived from the external
protected-payload root key under a separate HKDF domain, converts the one-time upload slot into a
submission-bound encrypted record, and deletes it under the existing protected-payload retention
lifecycle. Raw bytes do not enter SQLite, Events or Artifacts.

## Acceptance

Run `sh_run_step068_acceptance.cmd`. Deterministic acceptance performs no model or external network
call. Provider-live multimodal acceptance remains a separate state.
