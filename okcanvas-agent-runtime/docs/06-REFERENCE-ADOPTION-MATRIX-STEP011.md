# Reference Adoption Matrix — STEP011

| Reference path | Decision | Applied boundary |
|---|---|---|
| `openai-cs-agents-demo/python-backend/server.py::_build_agents_list` | ADAPT | Compact public Agent metadata list, backed by immutable definitions rather than in-memory objects |
| `openai-agents-streaming-api/src/api/utils/agent_router.py::get_agent_info` | REJECT | Does not expose instructions, model internals, session DB path or environment configuration |
| `openai-agents-python` | DEFER | No additional SDK feature is required for a read-only product catalog API |

All runtime imports continue to resolve from installed dependencies or project-owned code. `/reference` remains immutable evidence only.
