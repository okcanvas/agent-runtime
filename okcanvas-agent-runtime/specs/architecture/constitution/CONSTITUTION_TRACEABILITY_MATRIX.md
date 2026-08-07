# 헌법 조항 구현 추적표

Constitution SHA-256: `262b1db8549d7de5baf09307336b3ad5da07b7397f70cc2d6f5a1374eeb08bfa`

이 표의 빈 구현·테스트·증거 필드는 해당 조항의 구현 STEP에서 반드시 채워야 한다. `OPEN` 조항이 하나라도 있으면 해당 Wave는 종료할 수 없다.

| Clause | Title | Wave | Status | Required Gates |
|---|---|---:|---|---|
| GOV-001 | 헌법의 최고 우선순위 |  | CONTINUOUS |  |
| GOV-002 | 적용 범위 |  | CONTINUOUS |  |
| GOV-003 | 추측 금지 |  | CONTINUOUS |  |
| GOV-004 | 단일 진실 원천 |  | CONTINUOUS |  |
| GOV-005 | 조항 ID 의무 |  | CONTINUOUS | GATE-TRACEABILITY-COMPLETE |
| GOV-006 | 기준선 gate |  | CONTINUOUS |  |
| GOV-007 | 작업 중 발견사항 기록 |  | CONTINUOUS |  |
| GOV-008 | 부분 완료 금지 |  | CONTINUOUS | GATE-CLAUSE-COVERAGE-100 |
| GOV-009 | 행동 보존 원칙 |  | CONTINUOUS |  |
| GOV-010 | 헌법 개정 절차 |  | CONTINUOUS | GATE-AMENDMENT-VALID |
| ARC-001 | 최상위 시스템 축 |  | CONTINUOUS |  |
| ARC-002 | Transport 비권위성 |  | CONTINUOUS |  |
| ARC-003 | Product Event 권위 |  | CONTINUOUS |  |
| ARC-004 | 단방향 의존 |  | CONTINUOUS |  |
| ARC-005 | 기능과 배치의 일치 |  | CONTINUOUS |  |
| LAY-001 | Root Python package | 1 | CONTINUOUS |  |
| LAY-002 | 중복 package 금지 | 1 | CONTINUOUS |  |
| LAY-003 | Link 의존 금지 | 1 | CONTINUOUS |  |
| LAY-004 | Path SOT | 1 | CONTINUOUS | GATE-NO-HARDCODED-OLD-PACKAGE-PATH |
| LAY-005 | Target top-level directories | 1 | CONTINUOUS |  |
| LAY-006 | Runtime package canonical zones | 1 | CONTINUOUS | GATE-NO-UNCLASSIFIED-TOPLEVEL-PACKAGE |
| LAY-007 | 빈 placeholder 금지 | 1 | CONTINUOUS |  |
| LAY-008 | 대형 모듈 분해 우선 | 3 | CONTINUOUS |  |
| LAY-009 | RuntimeInfo 분리 | 2 | CONTINUOUS |  |
| LAY-010 | Vertical 격리 | 1 | CONTINUOUS |  |
| LAY-011 | Interface asset 격리 | 2 | CONTINUOUS |  |
| LAY-012 | Hatch package 제한 | 1 | CONTINUOUS | GATE-WHEEL-CONTENTS-EXACT |
| DEP-001 | Clients 의존 | 2 | CONTINUOUS | GATE-CLIENT-NO-SERVER-IMPORT |
| DEP-002 | Protocols 독립 | 2 | CONTINUOUS | GATE-PROTOCOLS-RUNTIME-INDEPENDENT |
| DEP-003 | Transport 의존 | 2 | CONTINUOUS | GATE-TRANSPORT-IMPORT-DIRECTION |
| DEP-004 | Application 의존 | 3 | CONTINUOUS | GATE-APPLICATION-NO-CONCRETE-ADAPTER |
| DEP-005 | Agent 의존 | 5 | CONTINUOUS | GATE-AGENT-NO-TRANSPORT-FRAMEWORK |
| DEP-006 | Capabilities 의존 | 5 | CONTINUOUS |  |
| DEP-007 | Domain 의존 | 3 | CONTINUOUS | GATE-DOMAIN-ISOLATION |
| DEP-008 | Adapters 의존 | 3 | CONTINUOUS |  |
| DEP-009 | Bootstrap 예외 | 2 | CONTINUOUS | GATE-BOOTSTRAP-WIRING-ONLY |
| DEP-010 | Service/Admin transport 독립 | 2 | CONTINUOUS | GATE-SERVICE-NO-CONTROL-API-IMPORT |
| DEP-011 | Transport-store 직접 접근 금지 | 3 | CONTINUOUS | GATE-TRANSPORT-NO-STORE-COORDINATOR |
| DEP-012 | 순환 의존 금지 |  | CONTINUOUS | GATE-MODULE-CYCLES-ZERO |
| CLI-001 | 제품 Client 위치 | 2 | CONTINUOUS |  |
| CLI-002 | 개발 Client 분리 | 2 | CONTINUOUS |  |
| CLI-003 | Service API 전용 | 2 | CONTINUOUS | GATE-PRODUCT-CLIENT-SERVICE-API-ONLY |
| CLI-004 | Server resource 비접근 |  | CONTINUOUS |  |
| CLI-005 | Credential 분리 |  | CONTINUOUS | GATE-CLIENT-CREDENTIAL-BOUNDARY |
| CLI-006 | Protocol-generated types | 2 | CONTINUOUS |  |
| PRO-001 | Protocol SOT | 2 | CONTINUOUS |  |
| PRO-002 | Versioning |  | CONTINUOUS |  |
| PRO-003 | Transport-neutral DTO | 2 | CONTINUOUS |  |
| PRO-004 | Canonical event identity | 4 | CONTINUOUS |  |
| PRO-005 | Ephemeral 구분 |  | CONTINUOUS |  |
| TRA-001 | Transport 역할 |  | CONTINUOUS |  |
| TRA-002 | Transport business logic 금지 | 3 | CONTINUOUS | GATE-TRANSPORT-NO-BUSINESS-LOGIC |
| TRA-003 | Service prefix |  | CONTINUOUS |  |
| TRA-004 | Admin prefix 목표 | 2 | CONTINUOUS |  |
| TRA-005 | Use case 재사용 | 3 | CONTINUOUS | GATE-DUPLICATE-USE-CASE-REMOVED |
| TRA-006 | Composition root 분리 | 2 | CONTINUOUS |  |
| REST-001 | REST 책임 |  | CONTINUOUS |  |
| REST-002 | Idempotency |  | CONTINUOUS |  |
| REST-003 | Audit 우선 명령 |  | CONTINUOUS |  |
| REST-004 | Store projection 금지 | 3 | CONTINUOUS |  |
| SSE-001 | Persisted SSE 권위 |  | CONTINUOUS |  |
| SSE-002 | Replay |  | CONTINUOUS |  |
| SSE-003 | Restart recovery |  | CONTINUOUS |  |
| SSE-004 | Subscription port | 3 | CONTINUOUS | GATE-SSE-SUBSCRIPTION-PORT |
| SSE-005 | WebSocket 독립 |  | CONTINUOUS |  |
| SSE-006 | Sequence 보존 | 4 | CONTINUOUS |  |
| WS-001 | 선택적 adapter | 4 | CONTINUOUS |  |
| WS-002 | 새 권한 경로 금지 | 4 | CONTINUOUS | GATE-WEBSOCKET-NO-AUTHORITY-ESCALATION |
| WS-003 | 연결 인증 | 4 | CONTINUOUS |  |
| WS-004 | Idempotent command | 4 | CONTINUOUS |  |
| WS-005 | Persist-before-broadcast | 4 | CONTINUOUS |  |
| WS-006 | Recovery path | 4 | CONTINUOUS |  |
| WS-007 | Ephemeral telemetry | 4 | CONTINUOUS |  |
| WS-008 | 비활성 기본값 | 4 | CONTINUOUS |  |
| APP-001 | Application use cases |  | CONTINUOUS |  |
| APP-002 | Transaction orchestration |  | CONTINUOUS |  |
| APP-003 | Authorization intent |  | CONTINUOUS |  |
| APP-004 | Port 우선 | 3 | CONTINUOUS |  |
| APP-005 | Transport 중복 제거 | 3 | CONTINUOUS |  |
| AGT-001 | Agent transport 독립 |  | CONTINUOUS |  |
| AGT-002 | Agent state write |  | CONTINUOUS |  |
| AGT-003 | Agent topology |  | CONTINUOUS |  |
| CAP-001 | Capability 통합 위치 | 5 | CONTINUOUS |  |
| CAP-002 | Tool subtype |  | CONTINUOUS |  |
| CAP-003 | Skill 구분 |  | CONTINUOUS |  |
| CAP-004 | Sub-agent 구분 |  | CONTINUOUS |  |
| CAP-005 | MCP 계층 |  | CONTINUOUS |  |
| CAP-006 | 구조와 권한 분리 |  | CONTINUOUS |  |
| DOM-001 | Domain framework 독립 |  | CONTINUOUS |  |
| DOM-002 | Event 불변성 |  | CONTINUOUS |  |
| ADP-001 | OpenAI adapter | 5 | CONTINUOUS |  |
| ADP-002 | Persistence adapter | 5 | CONTINUOUS |  |
| ADP-003 | Sandbox adapter | 5 | CONTINUOUS |  |
| ADP-004 | Storage adapter | 5 | CONTINUOUS |  |
| ADP-005 | MCP/Codex adapter | 5 | CONTINUOUS |  |
| BOOT-001 | 유일한 wiring 위치 |  | CONTINUOUS |  |
| BOOT-002 | Route 비소유 |  | CONTINUOUS | GATE-BOOTSTRAP-WIRING-ONLY |
| SEC-001 | Tenant/principal 일관성 |  | CONTINUOUS |  |
| SEC-002 | Secret 비저장 |  | CONTINUOUS |  |
| SEC-003 | Transport privilege parity |  | CONTINUOUS |  |
| CMP-001 | Compatibility facade | 2 | CONTINUOUS | GATE-COMPAT-SYMBOL-IDENTITY |
| CMP-002 | Import equivalence | 2 | CONTINUOUS |  |
| CMP-003 | Deprecation inventory | 2 | CONTINUOUS |  |
| CMP-004 | Major removal gate | 5 | CONTINUOUS |  |
| CMP-005 | Root launcher 호환 | 1 | CONTINUOUS |  |
| CMP-006 | Launcher registry | 1 | CONTINUOUS | GATE-LAUNCHER-REGISTRY-COMPLETE |
| HIS-001 | 보호 경로 |  | CONTINUOUS |  |
| HIS-002 | 원본 증거 보존 |  | CONTINUOUS |  |
| HIS-003 | Index 우선 |  | CONTINUOUS |  |
| HIS-004 | Reference 불변성 |  | CONTINUOUS | GATE-REFERENCE-INTEGRITY |
| TST-001 | Test inventory | 1 | CONTINUOUS |  |
| TST-002 | Test 이동 전제 | 1 | CONTINUOUS |  |
| TST-003 | Acceptance registry | 1 | CONTINUOUS |  |
| TST-004 | 전체 회귀 |  | CONTINUOUS |  |
| TST-005 | Windows live |  | CONTINUOUS |  |
| TST-006 | Fresh ZIP |  | CONTINUOUS |  |
| TST-007 | Wheel/editable install | 1 | CONTINUOUS | GATE-WHEEL-CONTENTS-EXACT, GATE-EDITABLE-INSTALL |
| TST-008 | Path coupling zero | 1 | CONTINUOUS | GATE-NO-HARDCODED-OLD-PACKAGE-PATH |
| MIG-001 | One-shot 금지 |  | CONTINUOUS |  |
| MIG-002 | Wave 0 | 0 | CONTINUOUS |  |
| MIG-003 | Wave 1 | 1 | CONTINUOUS |  |
| MIG-004 | Wave 2 | 2 | CONTINUOUS |  |
| MIG-005 | Wave 3 | 3 | CONTINUOUS |  |
| MIG-006 | Wave 4 | 4 | CONTINUOUS |  |
| MIG-007 | Wave 5 | 5 | CONTINUOUS |  |
| MIG-008 | 64 package map 의무 |  | CONTINUOUS | GATE-MIGRATION-MAP-COMPLETE |
| MIG-009 | 하위 단계 독립 검증 |  | CONTINUOUS |  |
