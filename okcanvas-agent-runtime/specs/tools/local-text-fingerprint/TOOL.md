# `local_text_fingerprint`

A deterministic, read-only local Function Tool. It accepts only an opaque Runtime-generated
`execution_id`, reads the already-authorized request from the in-memory execution context, and
returns SHA-256 plus bounded character/UTF-8 byte counts. It has no filesystem, network, shell, or
mutation capability and never persists raw Tool arguments or results in canonical Events.
