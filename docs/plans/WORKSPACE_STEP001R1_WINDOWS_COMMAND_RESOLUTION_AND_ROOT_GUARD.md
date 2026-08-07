# WORKSPACE STEP001R1 — Windows command resolution and root guard

## Scope

Correct only the Workspace management layer discovered by the user's real Windows run. Preserve Runtime,
Product CLI, Connector, and Example product source bytes.

## Corrections

1. Resolve Node.js command entrypoints before subprocess execution.
2. Execute Windows `.cmd`/`.bat` launchers through the command shell.
3. Reject Workspace setup or acceptance from a product project root.
4. Replace the Connector-owned optional integration runner with a Workspace-owned cross-project E2E runner
   for Workspace acceptance, while preserving the accepted Connector bytes.
5. Return structured failure evidence instead of an uncaught `FileNotFoundError`.

## Packaging closure

Workspace acceptance JSON is mutable execution evidence and is excluded from source packaging. Final Fresh validation requires a byte-identical deterministic repack.
