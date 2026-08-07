# CLI-ISSUE-002 — Forbidden-token gate scanned its own declaration

## Failure

The Product CLI foundation declared exact forbidden administrator paths and headers in `src`, while
the recurrence test scanned all `src` text for those same tokens. The gate therefore rejected its own
policy declaration instead of detecting executable use.

## Correction

Keep executable Product CLI source free of forbidden administrator identifiers. Construct the exact
forbidden tokens only inside the test using split literals so the gate cannot self-match.

## Recurrence gate

`npm test` must pass while scanning only Product CLI `src`, and adding any complete forbidden token to
`src` must make the test fail.
