# WORKSPACE-ISSUE-055 — Groupware STEP002 parent file manifests retained STEP001R1 hashes

## Observation

During R10D final package validation, both current Groupware parent-project manifests failed byte-identity checks even though the Groupware Connector and Example project trees were byte-identical between R10C and R10D.

The stale manifests declared:

- Connector: `CONNECTOR_STEP001R1_ASYNC_TEST_RUNNER_DEPENDENCY_CLOSURE` / `0.1.1`
- Example: `EXAMPLE_STEP001R1_TYPESCRIPT_BUILD_DEPENDENCY_CLOSURE` / `0.1.1`

while the actual current projects are:

- Connector: `CONNECTOR_STEP002_STABLE_ORGANIZATION_CONTEXT_REFERENCE_FILTER` / `0.2.0`
- Example: `EXAMPLE_STEP002_GROUPWARE_STABLE_CONTEXT_REFERENCE_FIXTURE` / `0.2.0`

The Connector tree had 31 files and the Example tree had 19 files in both R10C and R10D, with zero R10C→R10D byte changes. The stale manifests had 14 Connector hash mismatches and 10 Example hash mismatches.

## Root cause

STEP094 changed the Groupware Connector and Example to their STEP002 stable-context-reference contracts, but the workspace current parent-file manifests were not regenerated at that boundary. The separately retained `accepted-parent-artifacts.json` continues to represent the historical Windows-accepted STEP001R1 artifacts and is intentionally unchanged.

## Correction

R10D regenerates only the two **current source inventory manifests** from the actual STEP002 project trees and records the STEP002 identities. Historical accepted artifact records and historical STEP001R1 evidence remain unchanged.

## Recurrence prevention

Current parent-project manifests must be validated against `snapshot_files()` whenever a sibling project's current source is changed. Historical accepted-artifact metadata must never be used as a substitute for current source inventory, and current source manifests must never be kept stale merely to preserve historical acceptance identity.
