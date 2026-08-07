# MCP Access Configuration

The Product Configuration Pack stores credential references and environment-variable names only.
It never stores secret values. STEP086 declares one `groupware-read-credential` reference, but the
committed Groupware endpoint remains `.invalid` and the secret value is absent, so the default
deployment is `NOT_CONFIGURED`.
