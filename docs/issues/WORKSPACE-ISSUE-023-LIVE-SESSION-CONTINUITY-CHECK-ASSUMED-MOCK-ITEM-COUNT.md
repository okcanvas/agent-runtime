# WORKSPACE-ISSUE-023 — Live Session continuity check assumed mock item count

The deterministic fake SDK stored two Session items per turn, so earlier acceptance asserted `item_count == 4` after two turns. The real OpenAI Agents SDK stores additional model/tool items; the observed Windows Live Session had 8 items after two turns.

STEP004R2 proves `turn_count == 2`, a bounded even item count of at least four, a grounded second answer, and no second-turn child/MCP invocation. It no longer equates a mock storage shape with the real SDK.
