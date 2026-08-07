# WORKSPACE-ISSUE-030 — Short Organization expressions bypassed the read boundary

## Status

`FIX_IMPLEMENTED_LOCAL_DETERMINISTIC_ACCEPTED_WINDOWS_PENDING`

## Found in

`WORKSPACE_STEP007R1` / Runtime `STEP088R1`

## Evidence

The existing Organization Context child already owned employee, department, position, product, client, project, system, capability and term reads. The external Connector already resolved names, aliases, codes and ambiguity. However, the global Product router admitted Organization Context only when a fixed lexicon term was present.

The following inputs selected the general answer path before correction:

```text
김민수 정보
김선임 연락처
과장들 목록
플랫폼팀 직원
한빛 담당자
PI 뜻
VOC 의미
```

The failure occurred before Agent or MCP execution.

## Root cause

The router had no bounded short-read expression contract. Dynamic organization names cannot be copied into a static lexicon, and the existing Root/Child Agent contract intentionally forbids adding Product Skills to this delegation boundary.

## Correction

Runtime STEP089 adds four strict Product-owned short-read patterns and a structured request hint:

```text
<target> 정보
<target> 연락처
<target> 직책
<position>들 목록
```

The hint carries target expression, requested fields, entity type hints and preferred operation. It is explicitly not entity evidence. Existing Root/Child Agent IDs, empty Skill arrays, MCP ownership, Tool allowlist and ambiguity policy remain unchanged.

## Recurrence gate

- Positive and negative routing tests execute before model submission.
- Root and Child `skills` must remain empty.
- A request hint may never establish entity existence or resolve ambiguity.
- The external Tool result remains authoritative.
