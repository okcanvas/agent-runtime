# ADR-002: Isolate External Reference Source

## Status
Accepted.

## Decision
Store supplied repositories under immutable `reference/upstream/` and exclude them from imports, formatting, tests, coverage, and packaging logic that targets our implementation.

## Rationale
Mixing reference source with our runtime would obscure ownership, produce namespace collisions, inflate validation, and allow accidental upstream modification.
