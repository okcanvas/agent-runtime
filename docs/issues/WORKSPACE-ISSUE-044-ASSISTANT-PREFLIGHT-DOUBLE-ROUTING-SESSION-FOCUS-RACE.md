# WORKSPACE-ISSUE-044 — Assistant preflight double routing could diverge Session focus

```text
Status: FIX_IMPLEMENTED_TEST_EXECUTION_DEFERRED_BY_USER
First fixed in Workspace: WORKSPACE_STEP008R4R8_RUNTIME_STEP092_SESSION_CONTEXTUAL_FOLLOW_UP_AND_STABLE_ENTITY_FOCUS
Runtime: STEP092_SESSION_CONTEXTUAL_FOLLOW_UP_AND_STABLE_ENTITY_FOCUS / 2.76.0
```

## Source defect

Both Service and Admin Assistant preflight paths first called the public route method and then independently invoked `OrganizationAssistantRoutingService.route()` again before building the admitted model request.

Before Session stable focus this was redundant. With STEP092 it becomes a correctness race: another committed Turn can change the Session focus between the two reads. The public route could therefore describe one stable entity while the immutable model routing context is built from another focus snapshot.

Admin preflight also wrapped only the default/session Agent IDs with the Product routing context, while Service already included the Organization Context root/read Agent IDs. STEP092 GET result fencing requires that immutable request hint.

## Correction

- Service preflight resolves ownership, Session focus and routing once through `_assistant_route_decision()`.
- Admin preflight does the same through its own `_assistant_route_decision()`.
- The returned `AssistantRouteResponse` and admitted model request are built from the same decision.
- Admin immutable routing-context wrapping is aligned with the Organization Context root/read Agent IDs used by Service.

## Recurrence guard

The STEP092 deterministic source contract now requires exactly one preflight route-decision call per surface and checks Admin/Service Organization Context wrapping parity. Runtime behavior tests remain unexecuted under the user-directed MinIO test hold, so this issue is not CLOSED yet.
