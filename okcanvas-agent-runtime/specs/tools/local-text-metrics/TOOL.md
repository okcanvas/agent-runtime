# `local_text_metrics`

An approval-required, deterministic local Function Tool. It accepts only an opaque Runtime-generated
`execution_id`, reads the already-authorized request through the product execution context, and
returns SHA-256, UTF-8 bytes, character, word, and line counts. It has no filesystem, network,
shell, or mutation capability. The SDK `RunState` approval interruption remains authoritative.
