export type JsonObject = Record<string, unknown>;

export interface AgentDefinition extends JsonObject {
  agent_id: string;
  version: string;
  name: string;
  output_contract: string;
  tools: string[];
  tool_capabilities: JsonObject[];
  mcp_servers: string[];
  handoffs: string[];
  agent_tools: string[];
  orchestration_children: string[];
  guardrails: string[];
  workspace_access: string;
  session_mode: string;
}

export interface ProductSession extends JsonObject {
  session_id: string;
  state: string;
  agent_definition_id: string;
  agent_definition_version: string;
  runtime_binding_sha256: string;
  history_encryption_key_id: string | null;
  active_run_id: string | null;
  turn_count: number;
  item_count: number;
  created_at: string;
  updated_at: string;
  cleared_at: string | null;
}

export interface RunEvent extends JsonObject {
  run_id: string;
  sequence: number;
  event_type: string;
  payload: JsonObject;
}

export interface RunSnapshot extends JsonObject {
  run_id: string;
  status: string;
  total_tokens: number;
}

export interface Artifact extends JsonObject {
  artifact_id: string;
  sha256: string;
  verified_at: string | null;
  content: JsonObject;
}

export interface RunOutcome {
  agent: AgentDefinition;
  preflight: JsonObject;
  confirmed: JsonObject;
  events: RunEvent[];
  run: RunSnapshot;
  invocations: JsonObject[];
  artifact: Artifact;
  evaluation?: JsonObject;
}

export interface ConversationEntry {
  role: "user" | "agent";
  text: string;
  runId?: string;
}

export interface ExecutionObserver {
  onPreflight?(preflight: JsonObject, agent: AgentDefinition, model: string | undefined): void | Promise<void>;
  onConfirmed?(confirmed: JsonObject): void | Promise<void>;
  onEvent?(event: RunEvent): void | Promise<void>;
}

export interface CliOptions {
  baseUrl?: string;
  agentId?: string;
  sessionId?: string;
  model?: string;
  evaluationCaseId?: string;
  envFile?: string;
  scriptFile?: string;
  assumeYes: boolean;
  noColor: boolean;
  debug: boolean;
}
