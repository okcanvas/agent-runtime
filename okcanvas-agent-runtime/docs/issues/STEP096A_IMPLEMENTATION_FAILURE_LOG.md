# STEP096A Implementation Failure Log

## Scope

Failures and rejected approaches observed while implementing `STEP096A_GROUNDED_LLM_INTERPRETATION_CONTEXT_SHADOW_FOUNDATION`.

## F-096A-001 — Test asserted source formatting rather than behavior

The first focused test assumed a one-line source formatting shape for Root instruction construction and failed although Product behavior was correct.

Correction: test contract/behavior instead of incidental formatting.

Recurrence rule: do not convert source-layout preferences into Product contract tests.

## F-096A-002 — Historical focused tests are not a clean current SOT

A selected broader regression run produced 62 PASS / 7 FAIL before the successor identity was finalized. Six failures were inherited stale STEP/version/legacy-session-root assertions. One STEP087 fake Session object implemented only `sdk_session()` and not the formal `SessionRuntimePort.get_context_focus()` contract exposed by the new hint path.

Correction: do not weaken Product interfaces to satisfy partial historical fakes. STEP096A uses a current focused matrix and records broader historical debt separately.

## F-096A-003 — SOT hint JSON was initially placed in system instructions

Initial implementation appended projected Organization SOT text to Root system instructions. Retained SDK inspection showed this grants untrusted external strings excessive prompt authority.

Correction: use `call_model_input_filter` and inject the projected hint as turn-local user-role context data. Root instructions explicitly state that hint strings are data, never instructions.

Recurrence rule: external/SOT text used for interpretation must not be promoted to system-instruction authority.

## F-096A-004 — Two hint-search revisions were incorrectly collapsed

Initial code selected `max(entity_revision, term_revision)`, which could hide that two independent searches observed different catalog revisions.

Correction: preserve entity and term revisions separately, expose a consistency bit, and emit a global revision only when observed revisions agree.

Recurrence rule: never synthesize one snapshot identity from independent reads that did not prove a common snapshot.

## F-096A-005 — Static validator import root was wrong under direct script execution

The first validator run failed with `ModuleNotFoundError: scripts` because Python placed the Runtime `scripts/` directory, not the Runtime root, first on `sys.path`.

Correction: insert Runtime root explicitly before importing the parent STEP validator.

## F-096A-006 — Static validator produced two false negatives

The first semantic gate treated a network safety `.endswith(".invalid")` check as a forbidden language suffix router and assumed a source syntax shape for the nested route-v3 public dictionary.

Correction: narrow static assertions to actual interpretation-layer semantics and observable route contract.

## F-096A-007 — Hint profile is not live-configured yet

The new `organization-context-interpretation-hints` profile intentionally retains an `.invalid` URL in the packaged baseline. Existing live bootstrap patches only the execution Organization MCP profile.

Consequence: STEP096A deterministic acceptance may return `UNAVAILABLE` hints unless a future Live harness explicitly configures the hint profile. No Live acceptance is claimed in this wave.

Recurrence rule: future STEP096A/096B Live setup must configure and prove the hint profile independently rather than silently sharing mutable execution-profile state.

## F-096A-008 — New acceptance runner was missing from canonical launcher registry

After Product and focused acceptance passed, `validate_acceptance_launcher_registry.py` failed because `run_step096a_acceptance.py` and its Windows launcher had not been registered and STEP094R2 was still classified CURRENT.

Correction: demote STEP094R2 acceptance records to HISTORICAL, register STEP096A script/launcher as the exact CURRENT deterministic pair, and retain the fail-closed launcher registry gate in Workspace packaging.

Recurrence rule: every new `run_step*_acceptance.py` and `sh_run_step*_acceptance.cmd` must update the canonical launcher registry in the same wave.

## F-096A-009 — Current physical module manifest and RuntimeInfo count lagged STEP096A source

After launcher-registry repair, the STEP081 architecture gate passed 38/40. STEP096A intentionally added new canonical modules and RuntimeInfo fields, while the current physical module manifest and `EXPECTED_RUNTIME_INFO_FIELDS` still represented the parent tree.

Correction: preserve the historical STEP081 source/relocation baseline, regenerate only `STEP081_PHYSICAL_RELOCATION_MANIFEST.json` from the current canonical modules, and set the current expected RuntimeInfo field count to the observed 1042.

Recurrence rule: any Product Python/module or RuntimeInfo surface change must refresh the current physical manifest and architecture expected count before packaging; historical source/relocation evidence is not rewritten.

## F-096A-010 — Workspace static validator initially mutated Runtime architecture evidence

The first Workspace R11 validator invoked `validate_architecture_constitution.py` with its default output path. That validator correctly includes a fresh `validated_at`, so the call rewrote `docs/evidence/ARCHITECTURE_CONSTITUTION_VALIDATION.json` and made the just-generated Runtime parent manifest drift.

Correction: Workspace validation now sends that validator output to `/tmp` and treats the result as transient validation evidence. The packaged Runtime evidence file is not mutated by the Workspace static gate.

Recurrence rule: a static manifest-verification gate must not invoke nested validators that rewrite packaged files unless their output is explicitly redirected outside the source tree.

## F-096A-011 — Fresh-validation result summarizer assumed one output shape

The Fresh gates and deterministic repack completed successfully, but the final console summarizer assumed `focused_pytest` was always an object. The STEP096A runner stdout intentionally exposes it as a summary string, while the persisted acceptance evidence uses an object, causing the summarizer to raise `AttributeError` after validation work had finished.

Correction: inspect each validator result according to its declared output contract and avoid a polymorphic convenience accessor in the final release check.

Recurrence rule: release tooling must not infer one JSON shape across independent validators merely because field names overlap.

## F-096A-012 — Fresh package contained a secret-shaped historical test sentinel

The final Fresh secret scan found one `sk-...` shaped literal in `tests/test_sqlite_product_store.py`. Code inspection proved it was a fixed negative-test sentinel used to verify raw input/API-key text is not persisted, not a live credential.

Correction: rename the sentinel to a clearly non-secret-shaped value while retaining the same persistence-negative assertion, run the focused test, and add secret-like literal scanning to the R11 Workspace static gate.

Recurrence rule: tests and documentation must not use credential-shaped literals when a non-secret sentinel can prove the same contract.

