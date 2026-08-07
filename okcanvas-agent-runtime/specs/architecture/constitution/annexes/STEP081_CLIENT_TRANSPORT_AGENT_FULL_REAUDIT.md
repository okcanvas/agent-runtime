# STEP081 Client ↔ REST/SSE/WebSocket ↔ Agent 전수 재검토

## 기준선

- STEP: `STEP080_PRODUCT_OWNED_CAPABILITY_TOPOLOGY_AND_TOOL_DISCOVERY_FOUNDATION`
- Version: `2.60.0`
- 검토 방식: STEP080 최종 ZIP의 실제 Python/TypeScript/HTML/문서/pyproject/Acceptance 경로를 AST 및 문자열 전수 분석
- 소스 변경: 없음

## 최종 판단

```text
Client <-- REST / persisted SSE / optional WebSocket --> Transport
                                                       |
                                                       v
                                                Application ports
                                                       |
                                                       v
                                              Agent runtime / Domain
                                                       |
                                                       v
                                                  Adapters
```

이 축을 프로젝트 최상위 헌법으로 고정해야 한다.

현재 구조는 제품 기능은 동작하지만 Transport가 Application boundary를 충분히 형성하지 못했고, Client 구현과 서버 구현도 물리적으로 분리되지 않았다. WebSocket은 현재 없으며, 추가하더라도 새로운 실행 권한이 아니라 Application command/event port의 선택적 adapter가 되어야 한다.

## `src/okcanvas_agent_runtime` → `okcanvas_agent_runtime` 판단

**권고: 저장소 루트의 `okcanvas_agent_runtime/`로 이동한다.**

근거:

1. Python import 경로는 이미 모두 `okcanvas_agent_runtime.*`이므로 public import 이름은 바뀌지 않는다.
2. `pyproject.toml`은 Hatch package 경로를 명시하므로 `packages = ["okcanvas_agent_runtime"]`로 제한할 수 있다.
3. 이 저장소는 단일 라이브러리보다 Agent server + clients + protocols를 함께 소유하는 제품 monorepo이다. 루트 package가 `clients/`와 `protocols/`의 형제인 구조가 책임을 더 명확히 드러낸다.
4. disposable copy에서 package를 루트로 이동한 뒤 compileall, package import, Control API factory import, capability foundation resolve가 통과했고 4개 테스트 파일 22개가 모두 통과했다.

```text
Flat-layout probe: 22/22 PASS
Capability topologies: 27
```

그러나 현재 물리 경로 결합은 크다.

```text
src/okcanvas_agent_runtime literal: 111 files / 399 matches
ROOT / "src" 계열: 92 files / 99 matches
PYTHONPATH/pytest src 계약: 9 files / 9 matches
```

실행 경로 기준 주요 결합:

```text
scripts: 37 files / 199 literal matches
tests:   37 files / 114 literal matches
```

따라서 symlink, junction 또는 `src`와 root의 package 복제는 금지한다. 먼저 단일 `PROJECT_ROOT`/`PACKAGE_ROOT` resolver를 만들고 scripts/tests의 물리 경로 하드코딩을 제거한 다음 한 번에 이동해야 한다.

## 현재 Client/Transport 사실

```text
Control/Admin REST routes: 53
Service REST routes:       33
중복 route shape:          21
WebSocket routes:          0
```

현재 제품 transport:

- Service REST: 구현됨
- Service persisted SSE: 구현됨
- Admin persisted SSE: 구현됨
- Admin native SDK ephemeral SSE: 구현됨
- Client-facing WebSocket: 없음
- OpenAI Responses provider WebSocket: 명시적으로 비활성화됨; 이는 Client WebSocket과 다른 개념이다.

현재 실제 service products:

```text
agent-cli: README only
agent-web: README only
agent-desktop: README only
```

현재 구현된 Client는 개발/수용용이다.

- `clients/okcanvas-agent-cli`: admin/submitter Control API 사용
- `okcanvas_agent_runtime.tui_client`: admin Control API 사용
- `okcanvas_agent_runtime.approval_operator`: admin/submitter Control API 사용
- `operations_console`, `interactive_runner`: 서버 package 내부 정적 UI

즉 현재는 목표 `Client → /v1/service` 제품 구조가 아직 완성되지 않았다.

## 확인된 경계 위반

### 1. Service transport가 Admin transport를 import한다

`service_clients/routes.py`는 다음을 import한다.

```text
okcanvas_agent_runtime.control_api.contracts
okcanvas_agent_runtime.control_api.errors
okcanvas_agent_runtime.control_api.mappers
okcanvas_agent_runtime.control_api.sse
```

Public Service API가 Admin API 구현에 종속되어 있다. 공용 protocol DTO와 transport-neutral error mapping을 분리해야 한다.

### 2. Transport가 Store/Coordinator를 직접 조작한다

`build_service_client_router()`는 store, ownership, attachment store, project snapshot store, submission store, coordinator를 직접 전달받고 route 함수에서 직접 호출한다.

예:

- ownership 등록/검증/해제
- encrypted attachment/snapshot slot 생성·삭제
- submission store 조회
- ProductStore Run/Event/Artifact 조회
- coordinator cancel 호출

이는 REST adapter가 application use case를 우회하는 구조다.

### 3. SSE가 ProductStore를 직접 polling한다

`control_api/sse.py:persisted_event_stream()`은 `ProductStore.list_events()`와 `get_run()`을 직접 호출한다. SSE는 `RunEventSubscription` application port만 호출해야 한다.

### 4. Composition root와 route container가 결합되어 있다

`control_api/app.py`는 약 1716 lines이며 FastAPI 생성, 모든 concrete adapter 생성, service router wiring, admin route 53개를 동시에 소유한다.

### 5. Admin/Service route logic이 중복된다

동일 relative resource shape가 21개다. Authorization과 projection은 달라도 use case는 하나여야 한다.

## 목표 책임 구조

### Clients

- `clients/cli`, `clients/web`, `clients/desktop`
- 서버 Python module import 금지
- SQLite, workspace, encrypted storage, provider key 접근 금지
- `protocols/`에서 생성된 타입과 REST/SSE/WebSocket client만 사용

### Protocols

- REST OpenAPI
- canonical Product Event schemas
- SSE frame/replay contract
- WebSocket command/event envelopes
- Runtime implementation import 없음

### Transport

- authentication/authorization adapter
- request validation
- protocol DTO mapping
- application command/query 호출
- HTTP/SSE/WebSocket status/error projection
- Store, SDK, Docker, workspace 직접 접근 금지

### Application

- submissions, runs, sessions, approvals, artifacts, event subscription use cases
- transaction and authorization intent orchestration
- concrete SQLite/OpenAI/Docker import 금지

### Agent

- Agent definitions, capabilities, execution, orchestration
- REST/SSE/WebSocket/FastAPI/httpx import 금지
- Product state는 port를 통해 기록

### Adapters

- OpenAI Agents SDK
- SQLite
- Docker Sandbox
- encrypted storage
- MCP/Codex
- Application/Agent port 구현

### Bootstrap

- 유일하게 모든 concrete layer를 import하고 wiring
- route 구현을 포함하지 않음

## REST/SSE/WebSocket 역할 분리

### REST

명령, 조회, upload, idempotency, confirmation, approval, cancel, Artifact retrieval의 authoritative protocol이다.

### persisted SSE

canonical Product Run Event의 authoritative streaming projection이다.

- Last-Event-ID/cursor replay
- process restart 후 복구
- Product Event sequence 보존
- WebSocket 유무와 무관하게 항상 사용 가능

### WebSocket

선택적 low-latency bidirectional adapter다.

- 기본 실행에 필수 아님
- 연결 인증 + message별 authorization
- state-changing message는 idempotency key 필수
- Application command로만 진입
- Product Event persist 후 broadcast
- reconnect는 REST/SSE cursor로 복구
- raw SDK/model delta는 명시적 ephemeral telemetry일 뿐 Product Event를 대체하지 않음
- approval/destructive operation은 REST-first audit contract 유지

## 권장 최종 저장소 구조

```text
okcanvas-agent-runtime/
├─ okcanvas_agent_runtime/
│  ├─ bootstrap/
│  ├─ core/
│  ├─ domain/
│  ├─ application/
│  ├─ agent/
│  │  ├─ definitions/
│  │  ├─ runtime/
│  │  ├─ orchestration/
│  │  └─ capabilities/
│  │     ├─ tools/
│  │     ├─ skills/
│  │     ├─ subagents/
│  │     ├─ mcp/
│  │     ├─ guardrails/
│  │     ├─ workspace/
│  │     └─ model/
│  ├─ transport/
│  │  ├─ common/
│  │  ├─ service/
│  │  │  ├─ rest/
│  │  │  ├─ sse/
│  │  │  └─ websocket/
│  │  └─ admin/
│  │     ├─ rest/
│  │     └─ sse/
│  ├─ adapters/
│  │  ├─ openai/
│  │  ├─ persistence/sqlite/
│  │  ├─ sandbox/docker/
│  │  ├─ storage/
│  │  ├─ mcp/
│  │  └─ codex/
│  └─ compatibility/
├─ clients/
│  ├─ cli/
│  ├─ web/
│  ├─ desktop/
│  ├─ dev-cli/
│  └─ dev-console/
├─ protocols/
│  ├─ rest/openapi/
│  ├─ events/
│  ├─ sse/
│  └─ websocket/
├─ tests/
├─ scripts/
├─ specs/
├─ docs/
├─ reference/
└─ fixtures/
```

## 이동 순서

1. STEP080 Windows live 62/62 폐쇄.
2. Layout/dependency manifest와 AST forbidden-import gate 추가.
3. path resolver 도입 후 `src/okcanvas_agent_runtime`를 root `okcanvas_agent_runtime`로 이동.
4. `service_clients`를 `transport/service`로 재명명하고 server-side responsibility를 명확히 함.
5. TUI/operator/console/runner source를 `clients/`로 이동.
6. REST route에서 store/coordinator direct access 제거; application command/query 도입.
7. persisted SSE를 application `RunEventSubscription` port 위로 이동.
8. disabled-by-default WebSocket adapter와 protocol schema 추가.
9. capabilities/domain/adapters 물리 재배치; 기존 Python import는 bounded compatibility facade로 유지.

## 금지사항

- root package와 `src` package 동시 유지
- Windows junction/symlink 의존
- WebSocket에서 직접 model/Tool/Store 호출
- SSE와 WebSocket이 서로 다른 event truth를 가짐
- Product client에 admin key 또는 submitter key 제공
- `/v1/service` route가 `control_api` 구현을 import
- historical evidence 문서를 현재 경로로 일괄 rewrite
- 한 STEP에서 root move, module move, transport extraction, WebSocket 활성화를 모두 수행

## 권장 다음 STEP

STEP080 live 수용 후:

```text
STEP081_ROOT_PACKAGE_AND_CLIENT_TRANSPORT_AGENT_ARCHITECTURE_CONSTITUTION
```

STEP081의 범위는 헌법·gate·root package move까지만으로 제한한다. Transport store 분리와 WebSocket foundation은 후속 STEP으로 나누는 것이 안전하다.
