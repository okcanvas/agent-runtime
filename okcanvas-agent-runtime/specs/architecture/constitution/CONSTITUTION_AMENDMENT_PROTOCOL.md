# 아키텍처 헌법 개정 절차

헌법은 코드 변경의 편의를 이유로 묵시적으로 변경할 수 없다.

## 필수 산출물

1. `AMENDMENT-<NNN>-<TITLE>.md`
2. 이전 조항과 새 조항의 exact diff
3. 변경 이유와 실제 코드 증거
4. Client/Protocol/Transport/Application/Agent/Domain/Adapter/Bootstrap 영향 분석
5. Security, persistence, ownership, Event truth, compatibility 영향 분석
6. migration 및 rollback 계획
7. 신규 또는 수정 자동 Gate
8. full regression과 Windows live 결과
9. Constitution manifest, coverage matrix, traceability matrix SHA 갱신
10. Handoff 및 Issue Registry 갱신

## 개정 금지 조건

- 단순 디렉터리 편의를 위한 경계 완화
- Transport에서 Store/SDK/Docker 직접 접근 허용
- WebSocket을 별도 state authority로 인정
- Client의 server Python import 허용
- 역사 증거의 일괄 rewrite
- 기존 compatibility consumer를 확인하지 않은 path 삭제

## 승인 상태

개정은 다음 상태를 순서대로 거친다.

```text
PROPOSED
→ CODE_DERIVED_REVIEWED
→ DETERMINISTIC_ACCEPTED
→ WINDOWS_LIVE_ACCEPTED (해당 시)
→ RATIFIED
```
