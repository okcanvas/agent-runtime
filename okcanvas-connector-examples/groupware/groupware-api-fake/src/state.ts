import type {
  CalendarRecord,
  CapturedRequest,
  FakeClock,
  FaultRule,
  MailRecord,
  NoticeRecord,
} from "./types.js";

export class FakeState {
  clock: FakeClock = { now: "2026-08-04T09:00:00+09:00" };
  notices: NoticeRecord[] = [];
  mail: MailRecord[] = [];
  calendar: CalendarRecord[] = [];
  requests: CapturedRequest[] = [];
  faults: FaultRule[] = [];
  private sequence = 0;

  constructor() {
    this.reset();
  }

  reset(): void {
    this.clock = { now: "2026-08-04T09:00:00+09:00" };
    this.notices = [
      {
        record_id: "notice-001",
        tenant_id: "tenant-a",
        title: "Maintenance notice",
        body: "Service maintenance at 18:00.",
        visible_to_roles: ["agent-user", "employee", "manager", "admin"],
      },
      {
        record_id: "notice-tenant-b-001",
        tenant_id: "tenant-b",
        title: "Tenant B notice",
        body: "Tenant B only.",
        visible_to_roles: ["agent-user", "employee", "manager", "admin"],
      },
    ];
    this.mail = [
      {
        record_id: "mail-001",
        tenant_id: "tenant-a",
        owner_principal_id: "user-001",
        subject: "Project update",
        body: "The project is on track.",
      },
      {
        record_id: "mail-002",
        tenant_id: "tenant-a",
        owner_principal_id: "manager-001",
        subject: "Management update",
        body: "Manager private mail.",
      },
    ];
    this.calendar = [
      {
        record_id: "event-001",
        tenant_id: "tenant-a",
        owner_principal_id: "user-001",
        title: "Weekly review",
        start_at: "2026-08-05T10:00:00+09:00",
        end_at: "2026-08-05T11:00:00+09:00",
      },
      {
        record_id: "event-002",
        tenant_id: "tenant-a",
        owner_principal_id: "manager-001",
        title: "Manager review",
        start_at: "2026-08-05T12:00:00+09:00",
        end_at: "2026-08-05T13:00:00+09:00",
      },
    ];
    this.requests = [];
    this.faults = [];
    this.sequence = 0;
  }

  capture(input: Omit<CapturedRequest, "sequence">): void {
    this.sequence += 1;
    this.requests.push({ sequence: this.sequence, ...input });
  }

  setFault(rule: FaultRule): void {
    this.faults = this.faults.filter((item) => item.operation !== rule.operation);
    if (rule.mode !== "NONE" && rule.remaining > 0) {
      this.faults.push(rule);
    }
  }

  consumeFault(operation: string): FaultRule | undefined {
    const rule = this.faults.find((item) => item.operation === operation && item.remaining > 0);
    if (!rule) return undefined;
    rule.remaining -= 1;
    if (rule.remaining === 0) {
      this.faults = this.faults.filter((item) => item !== rule);
    }
    return { ...rule };
  }
}
