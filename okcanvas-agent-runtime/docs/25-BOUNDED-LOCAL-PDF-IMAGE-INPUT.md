# Bounded Local PDF and Image Input

## Purpose

STEP068 adds one isolated document-review path for a local PDF, PNG or JPEG. The attachment is
validated from its bytes, encrypted in a Product-owned attachment store, bound to one governed
submission and decrypted only in process memory when the accepted SDK input is constructed.

This is direct multimodal input. It does not use OpenAI Files, File Search or Vector Stores.

## Required server configuration

The existing governed-run keys remain required:

- `OKCANVAS_ADMIN_KEY`;
- `OKCANVAS_RUN_SUBMITTER_KEY`;
- `OKCANVAS_PROTECTED_PAYLOAD_KEY`.

The attachment store derives a separate authenticated encryption subkey from the protected-payload
root key by a fixed HKDF domain. No additional attachment key is accepted from HTTP.

The selected model must be exactly `gpt-4.1` for `local-document-review-agent`.

## Supported input

One request contains:

- one non-empty text instruction;
- exactly one local PDF, PNG or JPEG;
- no Session, MCP, Hosted Tool, Function Tool, Handoff, Agent-as-Tool, orchestration, Guardrail or
  workspace composition.

The immutable policy is `specs/attachments/policies/local-pdf-image-v1.json`. The implementation
validates the file signature and bounded PDF/image structure instead of trusting the filename or
HTTP Content-Type.

## Upload

Upload raw bytes to the local Control API. Both authentication headers are required.

```cmd
curl.exe -sS -X POST "http://127.0.0.1:8088/v1/local-attachments" ^
  -H "X-OKCanvas-Admin-Key: %OKCANVAS_ADMIN_KEY%" ^
  -H "X-OKCanvas-Run-Submitter-Key: %OKCANVAS_RUN_SUBMITTER_KEY%" ^
  -H "X-OKCanvas-Attachment-Filename: document.pdf" ^
  --data-binary "@D:\documents\document.pdf"
```

The response contains a one-time identifier such as:

```json
{
  "attachment_id": "attachment_slot_0123456789abcdef0123456789abcdef",
  "state": "UPLOADED",
  "filename": "document.pdf",
  "media_type": "application/pdf",
  "input_kind": "input_file",
  "content_sha256": "...",
  "byte_length": 12345,
  "page_count": 4,
  "width": null,
  "height": null,
  "expires_at": "...",
  "raw_bytes_persisted_in_events": false,
  "raw_bytes_persisted_in_artifacts": false
}
```

The upload slot expires and can be consumed only once.

## Governed preflight

Pass the returned `attachment_id` to the existing governed preflight endpoint. Use a fresh
idempotency key of at least 16 characters.

```cmd
curl.exe -sS -X POST "http://127.0.0.1:8088/v1/run-submissions/preflight" ^
  -H "Content-Type: application/json" ^
  -H "X-OKCanvas-Admin-Key: %OKCANVAS_ADMIN_KEY%" ^
  -H "X-OKCanvas-Run-Submitter-Key: %OKCANVAS_RUN_SUBMITTER_KEY%" ^
  -d "{\"agent_definition_id\":\"local-document-review-agent\",\"input\":\"Review this document and return the required structured findings.\",\"model\":\"gpt-4.1\",\"attachment_id\":\"attachment_slot_0123456789abcdef0123456789abcdef\",\"idempotency_key\":\"document-review-0001\"}"
```

Preflight binds the validated attachment metadata to the immutable request fingerprint and moves the
encrypted bytes from the expiring upload slot to a submission-bound attachment record. It performs
no model call.

Confirm the returned submission through the existing governed confirmation flow described in
`docs/16-PROTECTED-PAYLOAD-AND-GOVERNED-RUN.md`.

## SDK input

Only `local-document-review-agent` receives typed multimodal input. The installed SDK receives:

```text
user message 1: input_file or input_image data URL built in memory
user message 2: input_text instruction
```

All existing text-only Agents continue to receive a plain string. The data URL and raw bytes are not
written to Product Events or Artifacts.

## Evidence and cleanup

A successful execution creates the normal `agent.final-output` Artifact and a separate
`agent.local-attachment-evidence` Artifact containing only bounded metadata:

- validated filename and media type;
- SHA-256 and byte length;
- PDF page count or image dimensions;
- SDK input kind;
- explicit raw-byte persistence flags set to false.

Successful protected-payload cleanup deletes the submission-bound attachment. Failed/cancelled and
unconfirmed submissions follow the existing governed retention lifecycle, and attachment cleanup is
coupled to protected-payload cleanup.

## Explicit non-scope

- remote file or image URLs;
- OpenAI Files and provider file IDs;
- File Search and Vector Stores;
- multiple attachments;
- Office, ZIP, audio or video;
- encrypted PDFs and animated PNG;
- binary Tool output or Image Generation;
- Session/MCP/orchestration composition.
