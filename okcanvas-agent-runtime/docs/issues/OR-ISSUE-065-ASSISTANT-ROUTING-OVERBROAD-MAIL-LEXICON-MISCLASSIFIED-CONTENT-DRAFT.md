# OR-ISSUE-065 — Assistant routing overbroad mail lexicon misclassified content drafting

## Symptom

The request `프로젝트 지연 안내 메일 초안 작성해줘` was initially classified as an enterprise transaction draft instead of ordinary content drafting.

## Code-confirmed root cause

The deterministic routing policy treated the generic word `메일` as sufficient evidence of an enterprise-system transaction. It did not distinguish writing mail content from creating or sending a mail object in a connected system.

## Impact

A Tool-free writing request would have been unnecessarily constrained as an unavailable enterprise action, reducing ChatGPT-style usability and producing a false `PROPOSAL_ONLY` response.

## Correction

The routing policy now separates enterprise-system terms from enterprise-transaction terms. Content drafting remains `WRITE_CONTENT`; explicit submit/send/create/update language is required for `DRAFT_ACTION` or `WRITE_ACTION`.

## Recurrence gate

- deterministic request matrix in `tests/test_step083_organization_assistant_main_agent_and_action_routing.py`;
- STEP083 Assistant routing validator route matrix;
- STEP083 integrated acceptance.
