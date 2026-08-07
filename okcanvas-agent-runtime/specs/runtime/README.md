# Runtime Policies

## Immutable OpenAI model route

`model-routing-policy.json` permits exactly one route:

- provider `openai`;
- installed-SDK `OpenAIProvider`;
- Responses API over HTTP;
- official base URL `https://api.openai.com/v1`;
- no provider-prefixed model IDs;
- no fallback;
- no sensitive trace content.

## Immutable zero-retry authority

`model-retry-policy.json` permits exactly one retry policy:

- provider-managed retries `0`;
- Runner-managed retries `0`;
- SDK conversation-locked compatibility retries disabled through the explicit zero retry budget;
- retryable categories empty;
- automatic model fallback remains disabled.

The Product Runtime supplies an `AsyncOpenAI(max_retries=0)` client and explicit SDK
`ModelRetrySettings(max_retries=0, policy=retry_policies.never())`. Changing either policy or the
model-routing/retry implementation changes the Runtime binding and invalidates already prepared
confirmations. This directory does not authorize another provider, endpoint, fallback, or retry.

## OpenAI trace export

`openai-trace-export-policy.json` is the immutable Product policy for SDK trace behavior. V1 requires
SDK tracing and provider trace export to be disabled, sensitive trace data disabled, and the
Product-local generated trace ID retained. The policy and Product implementation SHA are included in
Agent Runtime binding.
