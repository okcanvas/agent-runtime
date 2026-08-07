# OKCanvas Agent Runtime 아키텍처 헌법

## 문서 정체성

```text
Constitution ID: OKCANVAS_AGENT_RUNTIME_CLIENT_TRANSPORT_AGENT_ARCHITECTURE_CONSTITUTION
Version: 1.0.0
Authority: RATIFIED_ARCHITECTURE_CONSTITUTION
Source baseline: STEP080_PRODUCT_OWNED_CAPABILITY_TOPOLOGY_AND_TOOL_DISCOVERY_FOUNDATION / 2.60.0
Product source movement: BLOCKED until STEP080 Windows live 62/62
Constitution SHA-256: 262b1db8549d7de5baf09307336b3ad5da07b7397f70cc2d6f5a1374eeb08bfa
```

본 헌법은 프로젝트 구조의 권장안이 아니라 이후 모든 구현 STEP을 구속하는 규범이다. 본문, machine-readable manifest, 추적표, migration map, Gate catalog, amendment protocol과 해시 고정 원본 감사 자료는 하나의 불가분 문서 집합이다.

## 규범 용어

- **MUST / SHALL**: 반드시 지켜야 한다.
- **MUST NOT / SHALL NOT**: 절대 금지한다.
- **MAY**: 상위 조항과 Gate를 위반하지 않는 범위에서 허용한다.
- **Compatibility facade**: 기존 import path를 유지하면서 canonical implementation을 re-export하는 임시 경계다.
- **Canonical Product Event**: durable persistence와 sequence identity를 가진 유일한 event truth다.

## 최상위 구조

```text
Client
  ↕ REST / persisted SSE / optional WebSocket
Transport adapters
  ↓
Application command/query/event-subscription ports
  ↓
Agent Runtime / Domain
  ↓
Adapters (OpenAI / SQLite / Docker / Storage / MCP / Codex)
```

## 헌법 조항

### governance

#### GOV-001 — 헌법의 최고 우선순위

**MUST**

본 문서와 해시 고정 부속서는 OKCanvas Agent Runtime의 프로젝트 구조, 책임 경계, 의존 방향, Client/Transport/Agent 관계에 대한 최상위 규범이다. 하위 설계서, STEP 계획, 코드 주석, 디렉터리 관행이 충돌하면 본 헌법이 우선한다.

#### GOV-002 — 적용 범위

**MUST**

본 헌법은 저장소 전체의 Python Runtime, clients, protocols, transports, application services, agent runtime, capabilities, domain, adapters, bootstrap, tests, scripts, specs, docs, fixtures, launchers, reference 및 packaging에 적용한다.

#### GOV-003 — 추측 금지

**MUST**

모든 구조 변경 판단은 실제 코드, AST import graph, route inventory, path coupling, packaging configuration, tests 및 acceptance evidence를 근거로 해야 하며 디렉터리 이름이나 예상만으로 결정해서는 안 된다.

#### GOV-004 — 단일 진실 원천

**MUST**

규범 본문, machine-readable manifest, traceability matrix, migration map, gate catalog 및 amendment log는 하나의 불가분 헌법 묶음이다. 어느 하나라도 누락되면 헌법 적용과 STEP 종료를 허용하지 않는다.

#### GOV-005 — 조항 ID 의무

**MUST** · Gates: GATE-TRACEABILITY-COMPLETE

모든 구조 관련 Issue, STEP 계획, 코드 변경, 테스트, acceptance 및 Handoff는 적용하거나 변경하는 헌법 조항 ID를 명시해야 한다.

#### GOV-006 — 기준선 gate

**MUST**

STEP080 Windows live acceptance 62/62가 폐쇄되기 전에는 product source의 물리 이동을 공식 기준선으로 승격해서는 안 된다. 헌법 문서의 제정과 검증 도구 준비는 허용한다.

#### GOV-007 — 작업 중 발견사항 기록

**MUST**

실제 실패, 구조 결함, 경계 위반, 검증 결함, 환경 blocker 및 반복 가능한 near-miss는 별도 Issue 문서와 재발 방지 Gate 없이 닫을 수 없다.

#### GOV-008 — 부분 완료 금지

**MUST** · Gates: GATE-CLAUSE-COVERAGE-100

STEP 종료 시 계획된 조항 중 미구현, 미검증, 미문서화 항목이 하나라도 있으면 상태를 PASSED 또는 ACCEPTED로 선언해서는 안 된다.

#### GOV-009 — 행동 보존 원칙

**MUST**

구조 재정렬 STEP은 명시적으로 선택한 기능 변경을 제외하고 Runtime behavior, API semantics, event truth, security, ownership, model/Tool 권한 및 persisted identity를 변경해서는 안 된다.

#### GOV-010 — 헌법 개정 절차

**MUST** · Gates: GATE-AMENDMENT-VALID

헌법 조항 변경은 amendment 문서, 영향 분석, 이전/신규 조항 diff, migration plan, 자동 Gate 수정, 전체 회귀 및 Windows live acceptance를 거쳐야 한다. 묵시적 개정은 금지한다.

### architecture

#### ARC-001 — 최상위 시스템 축

**MUST**

제품 구조는 Client ↔ REST/persisted SSE/optional WebSocket ↔ Transport ↔ Application ports ↔ Agent Runtime/Domain ↔ Adapters의 방향을 따른다.

#### ARC-002 — Transport 비권위성

**MUST**

REST, SSE, WebSocket transport는 Product state의 권위 원천이 아니며 상태 변경과 조회는 Application port를 통해 수행한다.

#### ARC-003 — Product Event 권위

**MUST**

지속 가능한 Product Event ledger만 canonical event truth이며 raw model/SDK stream, WebSocket frame, console log 또는 in-memory callback은 이를 대체할 수 없다.

#### ARC-004 — 단방향 의존

**MUST**

상위 interface/transport가 하위 application/domain port를 호출하고 concrete adapter는 port를 구현한다. 하위 계층이 상위 transport/framework를 import해서는 안 된다.

#### ARC-005 — 기능과 배치의 일치

**MUST**

논리 capability topology와 물리 디렉터리 구조는 서로 모순되어서는 안 되며 tools, skills, sub-agents, MCP, guardrails, workspace 및 model capability는 agent/capabilities 하위에서 일관되게 표현한다.

### layout

#### LAY-001 — Root Python package

**MUST** · Wave 1

Python package의 물리 경로는 저장소 루트의 okcanvas_agent_runtime/이어야 하며 src/okcanvas_agent_runtime/를 최종 구조로 유지하지 않는다. Public import 이름 okcanvas_agent_runtime.*은 변경하지 않는다.

#### LAY-002 — 중복 package 금지

**MUST** · Wave 1

root package와 src package를 동시에 유지하거나 양쪽을 PYTHONPATH에 넣어서는 안 된다.

#### LAY-003 — Link 의존 금지

**MUST** · Wave 1

Windows junction, symbolic link 또는 filesystem alias를 package 이동의 호환 수단으로 사용해서는 안 된다.

#### LAY-004 — Path SOT

**MUST** · Wave 1 · Gates: GATE-NO-HARDCODED-OLD-PACKAGE-PATH

PROJECT_ROOT, PACKAGE_ROOT, CLIENTS_ROOT, PROTOCOLS_ROOT, SCRIPTS_ROOT, TESTS_ROOT, SPECS_ROOT, DOCS_ROOT, REFERENCE_ROOT, FIXTURES_ROOT를 단일 path resolver가 제공해야 한다.

#### LAY-005 — Target top-level directories

**MUST** · Wave 1

저장소 최상위는 okcanvas_agent_runtime/, clients/, protocols/, tests/, scripts/, specs/, docs/, reference/, fixtures/ 및 명시적으로 등록된 packaging/launcher 파일로 구성한다.

#### LAY-006 — Runtime package canonical zones

**MUST** · Wave 1 · Gates: GATE-NO-UNCLASSIFIED-TOPLEVEL-PACKAGE

okcanvas_agent_runtime 내부 canonical zone은 bootstrap, core, domain, application, agent, transport, adapters, compatibility로 제한한다.

#### LAY-007 — 빈 placeholder 금지

**MUST** · Wave 1

구현과 re-export가 없는 api, policy, tools 같은 aspirational placeholder package를 두어서는 안 된다. 실제 경계 또는 compatibility facade가 아니면 제거한다.

#### LAY-008 — 대형 모듈 분해 우선

**MUST** · Wave 3

1,000 LOC 이상 또는 여러 책임을 가진 모듈은 단순 이동하지 말고 route/resource, transaction aggregate, adapter family 또는 feature record 기준으로 분해한다.

#### LAY-009 — RuntimeInfo 분리

**MUST** · Wave 2

786개 필드의 RuntimeInfo 구현은 immutable feature-group record와 assembler로 분리하고 기존 okcanvas_agent_runtime.model은 major-version 제거 전 compatibility facade로 유지한다.

#### LAY-010 — Vertical 격리

**MUST** · Wave 1

store replenishment와 commerce snapshot ingress 등 비즈니스 특화 코드는 verticals/ 또는 명시된 domain vertical에 위치하고 generic core contract가 vertical limit module을 직접 import하지 않도록 한다.

#### LAY-011 — Interface asset 격리

**MUST** · Wave 2

Operations Console, Interactive Runner 등 UI/static assets는 client 또는 transport/admin interface 영역에 위치하며 generic Agent Runtime implementation과 혼합하지 않는다.

#### LAY-012 — Hatch package 제한

**MUST** · Wave 1 · Gates: GATE-WHEEL-CONTENTS-EXACT

flat layout에서도 build backend는 packages=["okcanvas_agent_runtime"]와 같이 배포 package를 명시하여 clients, protocols, tests, docs, reference가 wheel에 암묵적으로 포함되지 않게 한다.

### dependency

#### DEP-001 — Clients 의존

**MUST** · Wave 2 · Gates: GATE-CLIENT-NO-SERVER-IMPORT

clients는 protocols와 생성된 client SDK만 의존하며 server Python package를 import하지 않는다.

#### DEP-002 — Protocols 독립

**MUST** · Wave 2 · Gates: GATE-PROTOCOLS-RUNTIME-INDEPENDENT

protocols는 Runtime implementation, FastAPI, SQLite, OpenAI SDK, Docker 및 filesystem adapter를 import하지 않는다.

#### DEP-003 — Transport 의존

**MUST** · Wave 2 · Gates: GATE-TRANSPORT-IMPORT-DIRECTION

transport는 application, protocols, core만 의존한다.

#### DEP-004 — Application 의존

**MUST** · Wave 3 · Gates: GATE-APPLICATION-NO-CONCRETE-ADAPTER

application은 agent, domain, core 및 추상 port만 의존하고 concrete SQLite/OpenAI/Docker implementation을 import하지 않는다.

#### DEP-005 — Agent 의존

**MUST** · Wave 5 · Gates: GATE-AGENT-NO-TRANSPORT-FRAMEWORK

agent는 capabilities, domain, core 및 추상 port만 의존하고 FastAPI/httpx/WebSocket framework를 import하지 않는다.

#### DEP-006 — Capabilities 의존

**MUST** · Wave 5

capabilities는 domain과 core만 의존하고 transport 및 concrete infrastructure를 직접 소유하지 않는다.

#### DEP-007 — Domain 의존

**MUST** · Wave 3 · Gates: GATE-DOMAIN-ISOLATION

domain은 core 외의 상위 계층을 import하지 않는다.

#### DEP-008 — Adapters 의존

**MUST** · Wave 3

adapters는 application/agent/capability port와 domain/core contract를 구현할 수 있으나 transport route를 import하지 않는다.

#### DEP-009 — Bootstrap 예외

**MUST** · Wave 2 · Gates: GATE-BOOTSTRAP-WIRING-ONLY

bootstrap만 모든 concrete component를 import하고 wiring할 수 있으며 route body 또는 business use case를 소유하지 않는다.

#### DEP-010 — Service/Admin transport 독립

**MUST** · Wave 2 · Gates: GATE-SERVICE-NO-CONTROL-API-IMPORT

service transport는 admin/control transport implementation을 import하지 않고 양쪽은 transport-neutral protocol DTO, errors 및 application use case를 공유한다.

#### DEP-011 — Transport-store 직접 접근 금지

**MUST** · Wave 3 · Gates: GATE-TRANSPORT-NO-STORE-COORDINATOR

REST/SSE/WebSocket route는 ProductStore, ownership store, attachment/snapshot store, submission store, SQLite connection 또는 execution coordinator를 직접 호출하지 않는다.

#### DEP-012 — 순환 의존 금지

**MUST** · Gates: GATE-MODULE-CYCLES-ZERO

Python internal module cycle count는 0을 유지한다.

### clients

#### CLI-001 — 제품 Client 위치

**MUST** · Wave 2

제품 Client는 clients/cli, clients/web, clients/desktop에 위치한다.

#### CLI-002 — 개발 Client 분리

**MUST** · Wave 2

dev-cli, dev-console, acceptance runner, operator utility는 제품 Client와 별도 디렉터리와 credential policy를 갖는다.

#### CLI-003 — Service API 전용

**MUST** · Wave 2 · Gates: GATE-PRODUCT-CLIENT-SERVICE-API-ONLY

제품 Client는 /v1/service 및 공개 protocol만 사용하고 /v1/admin 또는 Control API를 정상 제품 기능에 사용하지 않는다.

#### CLI-004 — Server resource 비접근

**MUST**

Client는 SQLite, workspace, encrypted slot, provider key, Docker socket 및 server filesystem에 접근하지 않는다.

#### CLI-005 — Credential 분리

**MUST** · Gates: GATE-CLIENT-CREDENTIAL-BOUNDARY

제품 Client에 admin key, submitter key 또는 provider API key를 제공하지 않는다.

#### CLI-006 — Protocol-generated types

**MUST** · Wave 2

Client request/response/event 타입은 protocols의 versioned schema에서 생성하거나 검증한다.

### protocols

#### PRO-001 — Protocol SOT

**MUST** · Wave 2

REST OpenAPI, Product Event schema, SSE frame/replay, WebSocket command/event envelope는 protocols/가 단일 진실 원천이다.

#### PRO-002 — Versioning

**MUST**

모든 공개 protocol은 schema_version과 backward compatibility policy를 가진다.

#### PRO-003 — Transport-neutral DTO

**MUST** · Wave 2

Admin과 Service transport가 공유하는 DTO, error code, cursor 및 event identity는 control_api 구현이 아니라 protocols/common contract에 위치한다.

#### PRO-004 — Canonical event identity

**MUST** · Wave 4

REST Event 조회, SSE frame, WebSocket persisted event frame은 동일한 run_id/event_id/sequence/schema_version을 사용한다.

#### PRO-005 — Ephemeral 구분

**MUST**

raw model token delta, SDK lifecycle delta 및 non-persisted progress는 EPHEMERAL_TELEMETRY로 명시하고 canonical Product Event schema와 혼합하지 않는다.

### transport

#### TRA-001 — Transport 역할

**MUST**

Transport는 인증/인가 adapter, request validation, protocol mapping, application command/query 호출, status/error projection만 수행한다.

#### TRA-002 — Transport business logic 금지

**MUST** · Wave 3 · Gates: GATE-TRANSPORT-NO-BUSINESS-LOGIC

Transport route에서 ownership transfer, transaction orchestration, encrypted slot lifecycle, Task/Run creation 또는 model execution policy를 직접 구현하지 않는다.

#### TRA-003 — Service prefix

**MUST**

공개 Service API prefix는 /v1/service를 유지한다.

#### TRA-004 — Admin prefix 목표

**MUST** · Wave 2

Admin API는 /v1/admin으로 명확히 분리하며 native SDK stream은 ADMIN_DIAGNOSTIC_ONLY_NOT_SERVICE_CONTRACT로 유지한다.

#### TRA-005 — Use case 재사용

**MUST** · Wave 3 · Gates: GATE-DUPLICATE-USE-CASE-REMOVED

Admin과 Service는 authorization과 response projection은 달라도 동일 application command/query use case를 사용한다.

#### TRA-006 — Composition root 분리

**MUST** · Wave 2

FastAPI app 생성과 concrete wiring은 bootstrap/application.py 등 composition root에 위치하고  route 모듈은 wiring을 수행하지 않는다.

### rest

#### REST-001 — REST 책임

**MUST**

REST는 command, query, upload, idempotency, confirmation, approval, cancel, artifact retrieval 및 auditable lifecycle 변경의 authoritative protocol이다.

#### REST-002 — Idempotency

**MUST**

모든 재시도 가능한 state-changing Service REST command는 명시적 idempotency key 및 replay contract를 가진다.

#### REST-003 — Audit 우선 명령

**MUST**

Approval decision, destructive delete, retention override 및 credential-sensitive operation은 REST-first auditable command로 유지한다.

#### REST-004 — Store projection 금지

**MUST** · Wave 3

REST handler는 persistence row를 직접 JSON으로 노출하지 않고 application result를 protocol DTO로 projection한다.

### sse

#### SSE-001 — Persisted SSE 권위

**MUST**

persisted SSE는 canonical Product Run Event의 authoritative one-way streaming projection이다.

#### SSE-002 — Replay

**MUST**

SSE는 Last-Event-ID 또는 cursor replay를 지원한다.

#### SSE-003 — Restart recovery

**MUST**

SSE는 process restart 이후 persisted Product Event에서 복구 가능해야 한다.

#### SSE-004 — Subscription port

**MUST** · Wave 3 · Gates: GATE-SSE-SUBSCRIPTION-PORT

SSE adapter는 ProductStore를 직접 polling하지 않고 application RunEventSubscription port만 호출한다.

#### SSE-005 — WebSocket 독립

**MUST**

WebSocket 도입 여부와 무관하게 SSE fallback과 replay는 항상 사용 가능해야 한다.

#### SSE-006 — Sequence 보존

**MUST** · Wave 4

SSE event id와 sequence는 REST Event 조회 및 WebSocket persisted event와 동일해야 한다.

### websocket

#### WS-001 — 선택적 adapter

**MUST** · Wave 4

Client-facing WebSocket은 optional low-latency bidirectional adapter이며 기본 제품 실행의 필수 조건이 아니다.

#### WS-002 — 새 권한 경로 금지

**MUST** · Wave 4 · Gates: GATE-WEBSOCKET-NO-AUTHORITY-ESCALATION

WebSocket은 REST와 다른 model, Tool, Store, filesystem 또는 approval 권한 경로를 만들지 않는다.

#### WS-003 — 연결 인증

**MUST** · Wave 4

WebSocket 연결 시 인증하고 모든 메시지에서 tenant/principal authorization을 다시 검증한다.

#### WS-004 — Idempotent command

**MUST** · Wave 4

state-changing WebSocket message는 idempotency key를 필수로 하고 동일 application command를 호출한다.

#### WS-005 — Persist-before-broadcast

**MUST** · Wave 4

Product Event는 durable store에 commit된 뒤 WebSocket으로 broadcast한다.

#### WS-006 — Recovery path

**MUST** · Wave 4

WebSocket reconnect recovery는 REST/SSE cursor를 사용하며 WebSocket 자체를 durable ledger로 취급하지 않는다.

#### WS-007 — Ephemeral telemetry

**MUST** · Wave 4

raw model/SDK delta를 전달할 경우 EPHEMERAL_TELEMETRY로 표시하고 replay, completion 및 audit truth에 사용하지 않는다.

#### WS-008 — 비활성 기본값

**MUST** · Wave 4

WebSocket foundation은 disabled-by-default로 도입하고 SSE fallback과 reconnect semantics가 자동 검증되기 전 활성화하지 않는다.

### application

#### APP-001 — Application use cases

**MUST**

Application은 submissions, runs, sessions, approvals, artifacts, attachments, snapshots, event subscription 및 lifecycle use case를 소유한다.

#### APP-002 — Transaction orchestration

**MUST**

원자적 ownership transfer, encrypted ingress lifecycle, submission confirmation 및 Task/Run creation transaction은 Application service가 port를 통해 orchestration한다.

#### APP-003 — Authorization intent

**MUST**

Application은 tenant/principal authorization intent를 받되 HTTP header, WebSocket object 또는 FastAPI dependency를 직접 알지 않는다.

#### APP-004 — Port 우선

**MUST** · Wave 3

Persistence, model gateway, sandbox, storage, event publisher 및 clock은 추상 port로 주입한다.

#### APP-005 — Transport 중복 제거

**MUST** · Wave 3

21개 중복 Admin/Service route shape는 공통 application use case로 수렴시킨다.

### agent

#### AGT-001 — Agent transport 독립

**MUST**

Agent runtime은 REST, SSE, WebSocket, FastAPI, HTTP request 또는 client credential을 알지 않는다.

#### AGT-002 — Agent state write

**MUST**

Agent 실행 결과와 lifecycle state는 application/domain port를 통해 기록한다.

#### AGT-003 — Agent topology

**MUST**

모든 Agent 정의는 STEP080 capability topology와 runtime binding identity를 유지한다.

### capabilities

#### CAP-001 — Capability 통합 위치

**MUST** · Wave 5

tools, skills, subagents, MCP, guardrails, workspace 및 model capability는 agent/capabilities 아래 정규화한다.

#### CAP-002 — Tool subtype

**MUST**

Function Tool, hosted Tool, Codex, future Tool Search 및 Programmatic Tool Calling은 명시적 subtype과 activation/loading/caller policy를 가진다.

#### CAP-003 — Skill 구분

**MUST**

Product instruction/static-resource Skill과 SDK Shell/container executable Skill을 동일 contract로 취급하지 않는다.

#### CAP-004 — Sub-agent 구분

**MUST**

handoff, Agent-as-Tool, bounded orchestration child는 subagents 하위의 서로 다른 capability kind로 유지한다.

#### CAP-005 — MCP 계층

**MUST**

MCP definition, client adapter, server implementation 및 Hosted MCP discovery를 구분한다.

#### CAP-006 — 구조와 권한 분리

**MUST**

미래 Tool Search/WebSocket/Code Interpreter 구조를 준비하는 것과 runtime 권한 활성화를 분리하며 structure-only 기능은 fail-closed로 유지한다.

### domain

#### DOM-001 — Domain framework 독립

**MUST**

Task, Run, Event, Artifact, Approval, Session, Attachment, Snapshot 및 ownership domain contract는 web/model/persistence framework에 독립적이어야 한다.

#### DOM-002 — Event 불변성

**MUST**

canonical Product Event identity와 ordering은 transport 변경으로 달라지지 않는다.

### adapters

#### ADP-001 — OpenAI adapter

**MUST** · Wave 5

OpenAI Agents SDK 및 provider-specific mapping은 adapters/openai에 위치한다.

#### ADP-002 — Persistence adapter

**MUST** · Wave 5

SQLite implementation과 migration은 adapters/persistence/sqlite에 위치한다.

#### ADP-003 — Sandbox adapter

**MUST** · Wave 5

Docker Sandbox implementation은 adapters/sandbox/docker에 위치한다.

#### ADP-004 — Storage adapter

**MUST** · Wave 5

AES-GCM ingress slot 및 encrypted payload implementation은 adapters/storage에 위치하고 application port를 구현한다.

#### ADP-005 — MCP/Codex adapter

**MUST** · Wave 5

Concrete MCP transport와 Codex gateway는 adapters/mcp 및 adapters/codex에 위치한다.

### bootstrap

#### BOOT-001 — 유일한 wiring 위치

**MUST**

bootstrap은 configuration을 읽고 concrete adapter와 application/transport를 연결하는 유일한 composition root다.

#### BOOT-002 — Route 비소유

**MUST** · Gates: GATE-BOOTSTRAP-WIRING-ONLY

bootstrap은 HTTP/SSE/WebSocket route body 또는 business validation을 포함하지 않는다.

### security

#### SEC-001 — Tenant/principal 일관성

**MUST**

REST, SSE, WebSocket, Application, ownership 및 persistence 전 구간에서 동일 tenant/principal identity를 사용한다.

#### SEC-002 — Secret 비저장

**MUST**

API key, bearer token, raw archive, raw workspace 및 raw model draft의 기존 비저장 헌법을 구조 변경으로 완화하지 않는다.

#### SEC-003 — Transport privilege parity

**MUST**

WebSocket/SSE/Admin/Service transport 차이가 권한 상승으로 이어져서는 안 된다.

### compatibility

#### CMP-001 — Compatibility facade

**MUST** · Wave 2 · Gates: GATE-COMPAT-SYMBOL-IDENTITY

widely imported 기존 Python path는 canonical implementation 이동 후 bounded re-export facade로 유지한다.

#### CMP-002 — Import equivalence

**MUST** · Wave 2

각 facade는 old/new import의 exported symbol identity 및 behavior equivalence 테스트를 가진다.

#### CMP-003 — Deprecation inventory

**MUST** · Wave 2

compatibility path마다 owner, replacement path, introduction STEP, remaining consumers 및 removal major version을 기록한다.

#### CMP-004 — Major removal gate

**MUST** · Wave 5

old path 삭제는 internal import 0, scripts/tests consumer 0, external compatibility policy, Handoff 고지 및 major-version boundary를 모두 만족해야 한다.

#### CMP-005 — Root launcher 호환

**MUST** · Wave 1

기존 root .cmd launcher는 user-facing Windows contract로 유지하고 canonical implementation으로 위임하는 wrapper로 전환한다.

#### CMP-006 — Launcher registry

**MUST** · Wave 1 · Gates: GATE-LAUNCHER-REGISTRY-COMPLETE

새 root launcher와 run_step script는 registry entry, current/history classification 및 command reachability test 없이 추가할 수 없다.

### history

#### HIS-001 — 보호 경로

**MUST**

reference/upstream, specs/agents, specs/mcp, specs/tools, docs/plans, docs/evidence, docs/issues, docs/reference는 일괄 이동하거나 rewrite하지 않는다.

#### HIS-002 — 원본 증거 보존

**MUST**

과거 문서의 당시 경로와 명령은 역사적 사실로 보존한다. 현재 경로로 일괄 치환하지 않는다.

#### HIS-003 — Index 우선

**MUST**

보호 경로에는 이동 대신 index, manifest, compatibility map을 추가한다.

#### HIS-004 — Reference 불변성

**MUST** · Gates: GATE-REFERENCE-INTEGRITY

reference/upstream hash와 direct import 0 계약을 유지한다.

### testing

#### TST-001 — Test inventory

**MUST** · Wave 1

모든 test는 unit, integration, contract, acceptance/current, regression/history, windows 중 하나로 manifest에서 분류한다.

#### TST-002 — Test 이동 전제

**MUST** · Wave 1

exact test path를 사용하는 script가 generated manifest를 사용하기 전에는 tests 물리 이동을 수행하지 않는다.

#### TST-003 — Acceptance registry

**MUST** · Wave 1

모든 current/history acceptance script와 launcher는 machine-readable registry에 등록한다.

#### TST-004 — 전체 회귀

**MUST**

각 구조 변경 STEP은 Python full regression, Node tests, Reference integrity, direct import 0, npm pack, compileall 및 packaging 검증을 수행한다.

#### TST-005 — Windows live

**MUST**

Runtime/launcher/package path에 영향을 주는 STEP은 Windows live acceptance 없이 ACCEPTED로 닫지 않는다.

#### TST-006 — Fresh ZIP

**MUST**

최종 ZIP을 새 디렉터리에 풀어 동일 acceptance와 전체 회귀 또는 byte-identical payload 증명을 수행한다.

#### TST-007 — Wheel/editable install

**MUST** · Wave 1 · Gates: GATE-WHEEL-CONTENTS-EXACT, GATE-EDITABLE-INSTALL

root package 전환 STEP은 fresh venv에서 wheel build/install, editable install, console entrypoint, import 및 package contents를 검증한다.

#### TST-008 — Path coupling zero

**MUST** · Wave 1 · Gates: GATE-NO-HARDCODED-OLD-PACKAGE-PATH

실행 가능한 scripts/tests/config에서 src/okcanvas_agent_runtime 하드코딩이 0이어야 root move를 완료할 수 있다. 역사 문서의 문자열은 예외 inventory로 관리한다.

### migration

#### MIG-001 — One-shot 금지

**MUST**

root move, 64개 package 재배치, transport extraction, application port 도입, WebSocket 활성화 및 Client 구현을 한 STEP에서 동시에 수행하지 않는다.

#### MIG-002 — Wave 0

**MUST** · Wave 0

STEP080 Windows live 62/62를 먼저 폐쇄한다.

#### MIG-003 — Wave 1

**MUST** · Wave 1

헌법/manifest/gate/path resolver/root package move/launcher-test inventory/empty placeholder/vertical low-risk 정리를 수행한다.

#### MIG-004 — Wave 2

**MUST** · Wave 2

Client와 Transport 물리 분리, protocol DTO 추출, composition root 분리, core/capability compatibility facade를 수행한다.

#### MIG-005 — Wave 3

**MUST** · Wave 3

Route direct store access를 application command/query port로 교체하고 SSE subscription port, transaction aggregate, domain/application/infrastructure 분리를 수행한다.

#### MIG-006 — Wave 4

**MUST** · Wave 4

disabled WebSocket protocol/adapter를 추가하고 SSE fallback, auth, idempotency, persist-before-broadcast, reconnect를 증명한 후 별도 activation STEP을 선택한다.

#### MIG-007 — Wave 5

**MUST** · Wave 5

capability/domain/adapter 물리 재배치와 compatibility facade 소비자 제거를 수행한다.

#### MIG-008 — 64 package map 의무

**MUST** · Gates: GATE-MIGRATION-MAP-COMPLETE

현재 64개 first-level package의 target path와 status는 해시 고정 migration map을 따르며 새 package가 생기면 map과 헌법 Gate를 동시에 갱신한다.

#### MIG-009 — 하위 단계 독립 검증

**MUST**

각 bounded sub-wave마다 import graph, behavior equivalence, full regression, ZIP 및 필요 시 Windows live를 독립적으로 수행한다.

## 강제 완료 조건

구조 관련 STEP은 다음을 모두 충족해야 종료할 수 있다.

1. 적용 조항 ID 전부 선언.
2. 변경 파일과 조항의 1:N 추적표 작성.
3. 모든 계획 조항의 implementation/test/evidence path 채움.
4. 미완료 조항 0.
5. 실제 실패와 near-miss의 Issue 문서 및 자동 재발 방지 Gate.
6. AST import graph parse 성공 및 cycle 0.
7. 호환 facade symbol identity와 behavior equivalence.
8. Python 전체 회귀, Node, Reference, direct import 0, packaging, fresh ZIP.
9. Runtime/launcher/package path 영향이 있으면 Windows live acceptance.
10. HANDOFF에 기준선, SHA, 남은 wave, deprecated path, 다음 gate를 기록.

## 금지된 일괄 작업

한 STEP에서 root package 이동, 64개 package 재배치, REST refactor, SSE refactor, WebSocket 활성화, Client 구현을 동시에 수행해서는 안 된다.

## 규범 부속서

다음 파일은 본 헌법에 해시로 편입된다. 어느 하나라도 없거나 SHA가 다르면 헌법 bundle 검증은 실패해야 한다.

- `structure_audit`: `STEP081_PROJECT_STRUCTURE_FULL_AUDIT.md` — `45ebb8d9fefec725602cd83cdfe0ec5f9902c386d26143bf12ab1fb71bca0c00`
- `migration_map`: `STEP081_PROJECT_LAYOUT_MIGRATION_MAP.json` — `4274b71e6203638f1908970ef0a7eff07a05660a741be2cf685625e5f860e8e6`
- `import_graph_audit`: `STEP081_IMPORT_GRAPH_AUDIT.json` — `747d3afc4ec503179329ca0be1be812b6b551310b6af09552ab2c3da9f7a0ca5`
- `path_coupling_audit`: `STEP081_PATH_COUPLING_AUDIT.json` — `d569ed8e79661f71a9bd57f61d862a7200543e7a204195fffa4ee7357a16d0a4`
- `boundary_audit`: `STEP081_CLIENT_TRANSPORT_AGENT_BOUNDARY_AUDIT.json` — `402bf3343b1fb238850800f2a00dd53dc554134096205f43c86c5ee78013f5cb`
- `client_transport_reaudit`: `STEP081_CLIENT_TRANSPORT_AGENT_FULL_REAUDIT.md` — `d4b863eba88dbdf8f727e86a287ce12cd644171b839f2aecd8dadea284f66bd0`
- `client_transport_reaudit_json`: `STEP081_CLIENT_TRANSPORT_AGENT_FULL_REAUDIT.json` — `083fd3b2a5398311625cc14f5cc41f0dcf90d59258602cd3581b546d839ea10e`
- `flat_layout_audit`: `STEP081_FLAT_LAYOUT_IMPACT_AUDIT.json` — `b158999a650252558f230657bd5eded65192364e5688467b5f56a019dce8129d`
- `target_architecture_manifest`: `STEP081_TARGET_ARCHITECTURE_MANIFEST.json` — `047b61d2403c577365622baa5c144c3b1fefeaa6dcf64bbe706206549d537f15`

## 현재 수용 상태

```text
STEP079A deterministic: ACCEPTED 29/29
STEP079A Windows live: ACCEPTED 57/57
STEP080 deterministic: ACCEPTED 31/31
STEP080 Windows live: PENDING 62/62
Architecture constitution: RATIFIED
Product source movement: NOT STARTED
```
