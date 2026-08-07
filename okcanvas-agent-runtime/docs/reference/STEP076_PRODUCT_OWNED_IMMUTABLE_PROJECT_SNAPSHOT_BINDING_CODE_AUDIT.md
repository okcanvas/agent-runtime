# STEP076 code audit — immutable project snapshot binding

## Audit rule

All conclusions below were obtained from the packaged STEP075G source and the implemented STEP076 source. No runtime behavior is inferred from names alone.

## STEP075G gap, confirmed in source

- STEP075G `control_api/app.py:269,352-354` accepted one `readonly_workspace_root` and passed it to the gateway.
- STEP075G `execution/openai_gateway.py:164-169,981-991` retained and used that one root for the Sandbox Tool.
- STEP075G `control_api/contracts.py:100+` had no `project_snapshot_id` in `GovernedRunPreflightRequest`.
- STEP075G `protected_payload/models.py:10+` and `run_submission/models.py:89+` had no project snapshot binding or ledger identity.
- STEP075G service routes had no `/v1/service/project-snapshots` endpoint or `project-snapshot-slot` ownership type.

This proved that project bytes were outside the governed submission identity.

## Implemented source path

### Validation and manifest

`project_snapshots/validation.py:21-44` normalizes the upload filename and repository-relative POSIX paths. `:56-125` validates archive size/CRC, encryption bit, compression method, symlink mode, duplicate/case-collision, file/count/expanded-byte bounds, reads each file, computes SHA-256, sorts the manifest and derives `snapshot_sha256`.

### Encrypted store

`project_snapshots/store.py:67-154` validates on create, inspect, bind and read. `:184-242` writes an AES-256-GCM envelope with authenticated metadata. `:244-317` strictly verifies envelope identity/AAD, authenticates ciphertext, checks archive SHA/length and revalidates ZIP metadata. `:319-332` validates opaque slot/bound references and rejects symlinked paths.

### Principal-owned service ingress

`service_clients/routes.py:248-276` publishes configured limits and API metadata. `:409-450` implements bounded raw-body upload and registers `project-snapshot-slot` ownership. `:452-488` requires ownership before preflight, passes the slot to the boundary and releases the slot ownership only after successful binding.

### Submission identity

`run_submission/service.py:142-156` requires one snapshot for the Sandbox Agent and rejects it for other Agents. `:289-299` adds compact snapshot identity to the request fingerprint. `:354-383` binds the encrypted slot and includes the binding in protected payload content. `:415-430` writes snapshot/archive hashes and bounded counts into `RunSubmissionDecision`.

`run_submission/store.py` adds the same four fields to the SQLite schema, migration, insert/read and row mapping, so restart does not lose the identity fence.

### Protected payload

`protected_payload/models.py:24-31` adds the compact binding. `protected_payload/store.py:58,156-166,249-308,333-336` introduces content V5 and binds `project_snapshot_sha256` into authenticated additional data while retaining V3/V4 read compatibility.

### Execution fence

`run_submission/execution.py:212-229` authenticates and reads the bound snapshot before scheduling. `:347-361` compares protected-payload identity with the submission ledger. `:269,299` passes the prepared snapshot through existing-execution preparation and guarded execution.

`execution/openai_gateway.py:994-1012` requires an uploaded snapshot or the explicitly retained development root. With a snapshot, it enters `materialize_project_snapshot`, invokes the existing read-only Tool against that temporary root, and exits the context after the call.

`project_snapshots/materialization.py:17-52` creates a per-run directory, checks every path against the manifest, verifies byte length and SHA-256, checks exact manifest coverage and removes the directory in `finally`.

### Evidence and retention

`execution/service.py:1175-1220` registers `agent.project-snapshot-evidence` using only compact metadata from `PreparedProjectSnapshot.to_evidence_dict()`.

`run_submission/lifecycle.py:292-319` resolves the bound snapshot reference from authenticated payload content and deletes it when the protected payload is deleted. Failure retention remains coupled to the existing governed lifecycle policy.

## Security invariants preserved

- Docker image/provider/Sandbox policy hashes are not modified by STEP076.
- Network remains `none`; Shell and Apply Patch remain disabled.
- No host path is mounted into Docker.
- The model cannot choose the ZIP, host path, executable, image or materialization location.
- Raw ZIP/source is not included in Event or snapshot evidence Artifact payloads.
- Selected files are still checked against the existing immutable Sandbox snapshot before evidence is accepted.

## Tests

`tests/test_step076_product_owned_immutable_project_snapshot_binding.py` covers ZIP attack rejection, encrypted tamper detection, temporary cleanup, principal isolation, required binding, upload→execution→Artifact→deletion, and fingerprint differentiation.
