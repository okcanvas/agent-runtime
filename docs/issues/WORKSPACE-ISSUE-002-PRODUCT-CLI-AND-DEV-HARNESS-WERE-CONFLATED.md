# WORKSPACE-ISSUE-002 — Product CLI and development harness were conflated

## Failure

The existing `okcanvas-agent-runtime/clients/cli` is an administrator/development acceptance harness,
but its generic name made it easy to mistake it for the Product Service CLI.

## Correction

Keep the accepted harness unchanged inside Runtime and create the sibling `okcanvas-agent-cli` product
boundary. The sibling project is foundation-only in WORKSPACE STEP001 and may use only `/v1/service/**`
with external Bearer identity when implemented.

## Recurrence gates

- Product CLI sources must not contain `/v1/run-submissions`, `/v1/agent-definitions`, Admin-Key, or Run-Submitter-Key.
- Product CLI must not import Runtime or Connector source modules.
- Foundation state must not claim request execution before it exists.
