# Architecture Constitution STEP 실행 템플릿

## 1. STEP identity

```text
STEP:
Version:
Source baseline:
Constitution SHA-256: 262b1db8549d7de5baf09307336b3ad5da07b7397f70cc2d6f5a1374eeb08bfa
State: PLANNED
```

## 2. 적용 조항

- [ ] 변경하는 조항 ID를 모두 열거했다.
- [ ] 연속 준수 조항 중 영향을 받는 조항을 모두 열거했다.
- [ ] amendment가 필요한 조항은 별도 amendment 문서를 만들었다.

```text
Applied clauses:
Amended clauses:
Unaffected-but-revalidated clauses:
```

## 3. 코드 근거 사전 감사

- [ ] 실제 파일과 import graph를 확인했다.
- [ ] 현재 경로 소비자 수를 계량했다.
- [ ] route/store/coordinator/framework 의존을 확인했다.
- [ ] public import 및 Windows launcher 소비자를 확인했다.
- [ ] 추측으로 범위를 정하지 않았다.

## 4. 변경 범위

```text
Canonical implementation paths:
Compatibility facade paths:
Client paths:
Protocol paths:
Transport paths:
Application paths:
Agent/capability paths:
Domain paths:
Adapter paths:
Bootstrap paths:
Scripts/tests/specs/docs paths:
```

## 5. 비변경 범위

- [ ] model/Tool authority 변경 없음 또는 명시적 별도 승인.
- [ ] Product Event truth 변경 없음.
- [ ] tenant/principal/ownership 경계 변경 없음.
- [ ] raw secret/workspace persistence 경계 변경 없음.
- [ ] reference/upstream 및 보호 specs/docs 경로 변경 없음.

## 6. Compatibility

- [ ] old import facade 제공.
- [ ] old/new symbol identity test.
- [ ] behavior equivalence test.
- [ ] deprecation inventory 갱신.
- [ ] root launcher compatibility wrapper 유지.

## 7. 자동 Gate

다음 gate는 해당되지 않는다는 코드 근거가 없는 한 모두 실행한다.

- [ ] GATE-CONSTITUTION-BUNDLE-COMPLETE
- [ ] GATE-CLAUSE-COVERAGE-100
- [ ] GATE-TRACEABILITY-COMPLETE
- [ ] GATE-AMENDMENT-VALID
- [ ] GATE-NO-UNCLASSIFIED-TOPLEVEL-PACKAGE
- [ ] GATE-NO-HARDCODED-OLD-PACKAGE-PATH
- [ ] GATE-WHEEL-CONTENTS-EXACT
- [ ] GATE-EDITABLE-INSTALL
- [ ] GATE-CLIENT-NO-SERVER-IMPORT
- [ ] GATE-PROTOCOLS-RUNTIME-INDEPENDENT
- [ ] GATE-TRANSPORT-IMPORT-DIRECTION
- [ ] GATE-APPLICATION-NO-CONCRETE-ADAPTER
- [ ] GATE-AGENT-NO-TRANSPORT-FRAMEWORK
- [ ] GATE-DOMAIN-ISOLATION
- [ ] GATE-SERVICE-NO-CONTROL-API-IMPORT
- [ ] GATE-TRANSPORT-NO-STORE-COORDINATOR
- [ ] GATE-MODULE-CYCLES-ZERO
- [ ] GATE-PRODUCT-CLIENT-SERVICE-API-ONLY
- [ ] GATE-CLIENT-CREDENTIAL-BOUNDARY
- [ ] GATE-TRANSPORT-NO-BUSINESS-LOGIC
- [ ] GATE-DUPLICATE-USE-CASE-REMOVED
- [ ] GATE-BOOTSTRAP-WIRING-ONLY
- [ ] GATE-SSE-SUBSCRIPTION-PORT
- [ ] GATE-WEBSOCKET-NO-AUTHORITY-ESCALATION
- [ ] GATE-COMPAT-SYMBOL-IDENTITY
- [ ] GATE-LAUNCHER-REGISTRY-COMPLETE
- [ ] GATE-REFERENCE-INTEGRITY
- [ ] GATE-MIGRATION-MAP-COMPLETE
- [ ] GATE-FULL-REGRESSION
- [ ] GATE-WINDOWS-LIVE
- [ ] GATE-FRESH-ZIP
- [ ] GATE-ISSUE-REGISTRY-COMPLETE

## 8. 실패 및 Issue 기록

- [ ] 실제 실패/near-miss마다 Issue 문서 작성.
- [ ] exact command와 symptom 기록.
- [ ] code-confirmed root cause 기록.
- [ ] 영향 경로 기록.
- [ ] fix와 recurrence-prevention gate 기록.
- [ ] Issue Registry 갱신.

## 9. 검증 결과

```text
Focused:
Historical:
Full Python:
Node:
Reference:
Direct reference imports:
Wheel/editable install:
Package contents:
Windows live:
Fresh ZIP:
```

## 10. Clause traceability closure

각 적용 조항에 대해 다음을 모두 채운다.

```text
Clause ID:
Implementation files:
Test files:
Acceptance checks:
Evidence files:
Issue IDs:
Status: COMPLETE | OPEN
```

- [ ] OPEN 조항 0.
- [ ] 미등록 변경 파일 0.
- [ ] 미실행 필수 Gate 0.

## 11. Handoff

- [ ] ZIP만으로 다른 대화에서 계속할 수 있다.
- [ ] current baseline과 pending Windows gate가 명확하다.
- [ ] SHA-256과 fresh extraction 결과가 있다.
- [ ] 다음 Wave와 금지 범위가 있다.
