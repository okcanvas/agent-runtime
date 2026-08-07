# STEP091C Implementation Failure Log

## 1. Local blob adapter dropped media type before record creation

The first adapter implementation deleted both unused parameters, then attempted to return `media_type`. Focused execution failed before Artifact creation. The adapter now discards only `artifact_type`, and a direct round-trip test protects the contract.

## 2. Application layer imported a concrete storage adapter

Optional fallback construction caused Application -> Adapter dependency-direction violations. The fallback was removed. Bootstrap now constructs and injects one `ArtifactService`; Application code depends only on the application Artifact boundary.

## 3. Historical tests treated `storage_path` as a host Path

The compatibility field now contains an opaque storage reference. Tests were migrated to `ArtifactService` and explicit local test helpers. Product API responses continue to omit the storage reference.

## 4. Automated test edit inserted `artifact_service` into `create_app` calls

A broad textual edit added an unsupported argument using an undefined local ProductStore. These insertions were removed; `create_app` owns its Artifact composition through StorageTopology.

## 5. STEP081 evidence generator required an unavailable STEP080A baseline tree

Only the current physical module manifest needed regeneration. The historical source inventory and relocation identities remain STEP081D. The physical module manifest was regenerated from current canonical modules while preserving the historical identity contract.

## 6. Monolithic STEP091C acceptance exceeded the external command window

The same focused command passed 88/88 directly. A bounded supplied-focused-evidence option was added; the acceptance runner validates the supplied state and exit code and still executes all other gates itself. Windows launchers continue to run the complete path without supplied evidence.

## 7. Current HANDOFF omitted a retained Skill identifier

Full partition 09 correctly detected that the new current HANDOFF no longer mentioned the retained `document-review-v1` Product Skill. No Skill implementation had been removed. The current HANDOFF now preserves the retained Skill and Connector capability identifiers so historical product-contract tests and ZIP-only continuation remain accurate.

## 8. Current HANDOFF omitted retained Tool and Groupware deployment identifiers

Full partition 11 correctly detected that the new current HANDOFF preserved the Skill name but omitted retained Product Tool names and exact external Groupware Connector/Example identifiers required for ZIP-only continuation. No runtime capability was removed. The HANDOFF now preserves `local_text_fingerprint`, `local_text_metrics`, `project_readonly_inspect`, `sandbox_project_readonly_inspect`, `reference-catalog`, `external-connector-service`, `okcanvas-connectors/groupware-mcp-server`, `EXAMPLE_TEMPLATE_ONLY`, and `okcanvas-connector-examples/groupware/groupware-api-fake`, and the retained issue identifier `OR-ISSUE-091`.
