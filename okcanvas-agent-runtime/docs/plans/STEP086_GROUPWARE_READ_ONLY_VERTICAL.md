# STEP086 — Groupware Read-only Vertical

## Identity

```text
STEP086_GROUPWARE_READ_ONLY_VERTICAL
version 2.66.0
parent STEP085 / 2.65.0 Windows deterministic accepted 12/12
rollback STEP081D / 2.61.4 Windows live 80/80
```

## Objective

Add the first named Groupware read vertical on the STEP085 delegated-identity and multi-MCP
foundation without inventing a real organization endpoint or enabling any write.

## Implemented

- `groupware-read-agent` on the existing Generic Product execution plane;
- V3 `groupware-read` remote MCP definition;
- tenant/principal/roles delegated from authenticated Service identity;
- exact allowlist: `search_notices`, `search_mail`, `list_calendar_events`;
- dynamic routing readiness from endpoint, credential reference, environment secret, identity, and
  role state;
- Groupware reads route to the Agent only when all readiness gates pass;
- writes, Sessions, Tool Search, programmatic Tool calling, and durable automation remain disabled.

## Default fail-closed state

The committed endpoint is `groupware.example.invalid` and no secret value is present. The
credential reference stores only the environment-variable name. Therefore the default Product
Configuration Pack reports `NOT_CONFIGURED` and does not submit a model run for Groupware reads.

## Operator activation boundary

An operator must replace the V3 URL template with a real organization-owned HTTPS endpoint and set
`OKCANVAS_GROUPWARE_READ_BEARER`. The Runtime then binds the authenticated tenant/principal/roles
and uses the existing protected-payload V6 restoration path.

## Next step

No STEP087 scope was supplied by the user. RuntimeInfo therefore records `UNSELECTED_PENDING_USER_SELECTION`
rather than guessing.

## Deterministic closure

```text
Groupware read-only validation: 30/30 PASS
STEP085 Multi-MCP retained projection: 19/19 PASS
STEP084 Organization Context retained projection: 17/17 PASS
Architecture: 40/40 PASS
Execution plane: 13/13 PASS
Distribution: 14/14 PASS
Launcher registry: 7/7 PASS
Integrated acceptance: 14/14 PASS
Python: 235 files, 962/962 PASS
Node: 14/14 PASS
Reference: 4/4 PASS
Installation: 16/16 PASS; wheel payload 350
Windows subprocess portability: 10/10 PASS
Constitution Compliance: 16/16 PASS
Changed-file SOT: 1,535/1,535 exact before final documentation closure
```

The changed-file total is regenerated after all final handoff and packaging scripts are committed.
Final Fresh ZIP and artifact hashes are external immutable evidence because an archive cannot contain
its own final hash without changing that hash.
## Final Fresh recurrence correction — OR-ISSUE-091

The first immutable Fresh ZIP regression found that a late `HANDOFF.md` rewrite had again omitted `document-review-v1`, recurring OR-ISSUE-067 after the source regression. STEP086 now preserves the exact Product Skill, four Function Tool and `reference-catalog` identities in HANDOFF; the extracted-ZIP final validator independently checks them. Full source regression, Compliance, packaging and Fresh regression must be rerun after this correction.

