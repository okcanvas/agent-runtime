# OR-ISSUE-096 — Historical output-contract count blocked later accepted contracts

## State

CLOSED_BY_STEP089

## Evidence

The immutable STEP007R1 source already contained eight registered output contracts, including the later accepted `OrganizationContextReadResult`, while the retained STEP032 regression asserted that the entire current registry must contain exactly seven entries.

A full Runtime test partition therefore failed even though no STEP089 change added an output contract.

## Root cause

The STEP032 regression mixed two different responsibilities:

- proving that the two STEP032-owned contracts remain registered, and
- freezing the total size of a registry that later accepted steps are allowed to extend.

The second assertion was not a valid historical invariant.

## Correction

- STEP032 now asserts only that `CodingAgentResult` and `StoreReplenishmentReviewResult` remain present.
- STEP089 owns an exact current-baseline inventory assertion for all eight accepted contracts.

## Recurrence gate

Historical step tests may assert ownership and retained presence, but only the current baseline test may assert the complete current registry inventory.
