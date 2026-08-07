from __future__ import annotations

import argparse
import base64
import importlib.metadata
import json
import os
import sqlite3
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from okcanvas_agent_runtime.support.acceptance import AcceptanceWorkspace
from okcanvas_agent_runtime.core.contracts import AgentStatus, CodingAgentResult
from okcanvas_agent_runtime.agent.definitions import AgentDefinitionCatalog
from okcanvas_agent_runtime.control_api import create_app
from okcanvas_agent_runtime.adapters.reference_catalog import ReferenceCatalogService
from okcanvas_agent_runtime.adapters.streaming import InMemoryNativeSDKStreamBroker

ADMIN_KEY = "step044-local-admin-key"
SUBMITTER_KEY = "step044-run-submitter-key"
PAYLOAD_KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
ADMIN_HEADERS = {"X-OKCanvas-Admin-Key": ADMIN_KEY}
SUBMIT_HEADERS = {**ADMIN_HEADERS, "X-OKCanvas-Run-Submitter-Key": SUBMITTER_KEY}
HIDDEN_API_KEY = "step044-hidden-api-key"
RAW_SENTINELS = {
    "clean": "step044 safe request sentinel",
    "input": "BLOCK_INPUT step044 protected input sentinel",
    "output": "step044 request output guardrail sentinel",
    "tool_input": "step044 protected tool input sentinel",
    "tool_output": "step044 protected tool output sentinel",
}


def _usage(input_tokens: int, output_tokens: int):
    return SimpleNamespace(
        requests=1 if input_tokens or output_tokens else 0,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
        output_tokens_details=SimpleNamespace(reasoning_tokens=0),
    )


def _install_fake_agents():
    counters = {
        "run": 0,
        "run_streamed": 0,
        "model_calls": 0,
        "tool_executions": {"guardrail-tool-input-agent": 0, "guardrail-tool-output-agent": 0},
        "guardrail_runs": {"INPUT": 0, "OUTPUT": 0, "TOOL_INPUT": 0, "TOOL_OUTPUT": 0},
    }
    previous_agents = sys.modules.get("agents")
    previous_decorators = sys.modules.get("agents.decorators")
    previous_version = importlib.metadata.version
    fake_agents = types.ModuleType("agents")
    fake_agents.__file__ = "/fake/site-packages/agents/__init__.py"
    fake_decorators = types.ModuleType("agents.decorators")

    class FakeGuardrailFunctionOutput:
        def __init__(self, *, output_info, tripwire_triggered):
            self.output_info = output_info
            self.tripwire_triggered = tripwire_triggered

    class FakeToolGuardrailFunctionOutput:
        def __init__(self, output_info=None, behavior=None):
            self.output_info = output_info
            self.behavior = behavior or {"type": "allow"}

        @classmethod
        def raise_exception(cls, output_info=None):
            return cls(output_info=output_info, behavior={"type": "raise_exception"})

    class FakeInputGuardrail:
        def __init__(self, fn, name, run_in_parallel):
            self.fn = fn; self.name = name; self.run_in_parallel = run_in_parallel
        def get_name(self): return self.name
        async def run(self, context, agent, value):
            counters["guardrail_runs"]["INPUT"] += 1
            return await self.fn(context, agent, value)

    class FakeOutputGuardrail:
        def __init__(self, fn, name): self.fn = fn; self.name = name
        def get_name(self): return self.name
        async def run(self, context, agent, value):
            counters["guardrail_runs"]["OUTPUT"] += 1
            return await self.fn(context, agent, value)

    class FakeToolGuardrail:
        def __init__(self, fn, name, kind): self.fn = fn; self.name = name; self.kind = kind
        def get_name(self): return self.name
        async def run(self, data):
            counters["guardrail_runs"][self.kind] += 1
            result = self.fn(data)
            if hasattr(result, "__await__"):
                result = await result
            return result

    def input_guardrail(func=None, *, name=None, run_in_parallel=True):
        def decorate(fn): return FakeInputGuardrail(fn, name or fn.__name__, run_in_parallel)
        return decorate(func) if func is not None else decorate

    def output_guardrail(func=None, *, name=None):
        def decorate(fn): return FakeOutputGuardrail(fn, name or fn.__name__)
        return decorate(func) if func is not None else decorate

    def tool_input_guardrail(func=None, *, name=None):
        def decorate(fn): return FakeToolGuardrail(fn, name or fn.__name__, "TOOL_INPUT")
        return decorate(func) if func is not None else decorate

    def tool_output_guardrail(func=None, *, name=None):
        def decorate(fn): return FakeToolGuardrail(fn, name or fn.__name__, "TOOL_OUTPUT")
        return decorate(func) if func is not None else decorate

    class FakeException(Exception):
        def __init__(self, *args):
            super().__init__(*args); self.run_data = None

    class InputGuardrailTripwireTriggered(FakeException):
        def __init__(self, result): super().__init__("input guardrail"); self.guardrail_result = result
    class OutputGuardrailTripwireTriggered(FakeException):
        def __init__(self, result): super().__init__("output guardrail"); self.guardrail_result = result
    class ToolInputGuardrailTripwireTriggered(FakeException):
        def __init__(self, guardrail, output): super().__init__("tool input guardrail"); self.guardrail=guardrail; self.output=output
    class ToolOutputGuardrailTripwireTriggered(FakeException):
        def __init__(self, guardrail, output): super().__init__("tool output guardrail"); self.guardrail=guardrail; self.output=output

    class FakeToolContext:
        def __init__(self, *, context, tool_name, tool_call_id, tool_arguments):
            self.context=context; self.tool_name=tool_name; self.tool_call_id=tool_call_id; self.tool_arguments=tool_arguments
        @classmethod
        def __class_getitem__(cls, item): return cls

    class FakeFunctionTool:
        def __init__(self, fn, name):
            self.fn=fn; self.name=name; self.tool_input_guardrails=[]; self.tool_output_guardrails=[]
            self._tool_origin=None

    def function_tool(**kwargs):
        def decorate(fn): return FakeFunctionTool(fn, kwargs.get("name_override") or fn.__name__)
        return decorate

    class FakeAgent:
        def __init__(self, **kwargs):
            for k,v in kwargs.items(): setattr(self,k,v)
    class FakeRunConfig:
        def __init__(self, **kwargs): self.values=kwargs
    class FakeRunHooks: pass
    class FakeModelSettings:
        def __init__(self, **kwargs): self.values=kwargs

    def _attach_run_data(exc, usage):
        exc.run_data = SimpleNamespace(context_wrapper=SimpleNamespace(usage=usage))
        return exc

    class FakeStreamingResult:
        def __init__(self, agent, request, kwargs):
            self.agent=agent; self.request=request; self.kwargs=kwargs
            self.last_response_id=None; self._output=None
            self.context_wrapper=SimpleNamespace(usage=_usage(0,0))

        async def stream_events(self):
            hooks=self.kwargs["hooks"]
            for guardrail in getattr(self.agent,"input_guardrails",[]):
                result=await guardrail.run(SimpleNamespace(),self.agent,self.request)
                if result.tripwire_triggered:
                    raise _attach_run_data(InputGuardrailTripwireTriggered(SimpleNamespace(guardrail=guardrail,output=result)), _usage(0,0))
            await hooks.on_agent_start(SimpleNamespace(),self.agent)
            await hooks.on_llm_start(SimpleNamespace(),self.agent,self.agent.instructions,[{"role":"user"}])
            counters["model_calls"] += 1
            agent_id = {
                "OKCanvas Guardrail Language Agent":"guardrail-language-agent",
                "OKCanvas Tool Input Guardrail Agent":"guardrail-tool-input-agent",
                "OKCanvas Tool Output Guardrail Agent":"guardrail-tool-output-agent",
            }[self.agent.name]
            if agent_id == "guardrail-language-agent":
                summary = "BLOCK_OUTPUT" if "output guardrail" in self.request else "Guardrail pass path is safe."
                usage=_usage(11,3)
                self._output=CodingAgentResult(status=AgentStatus.PASS,summary=summary,findings=[],unverified=[])
                self.context_wrapper=SimpleNamespace(usage=usage)
                response=SimpleNamespace(response_id=f"resp-{agent_id}",request_id="req-step044",output=[1])
                self.last_response_id=response.response_id
                await hooks.on_llm_end(SimpleNamespace(),self.agent,response)
                for guardrail in getattr(self.agent,"output_guardrails",[]):
                    result=await guardrail.run(SimpleNamespace(),self.agent,self._output)
                    if result.tripwire_triggered:
                        raise _attach_run_data(OutputGuardrailTripwireTriggered(SimpleNamespace(guardrail=guardrail,output=result)),usage)
                await hooks.on_agent_end(SimpleNamespace(),self.agent,self._output)
                yield SimpleNamespace(type="agent_updated_stream_event",new_agent=self.agent)
                yield SimpleNamespace(type="raw_response_event",data=SimpleNamespace(type="response.output_text.delta",delta=summary))
                return

            usage=_usage(13,2)
            self.context_wrapper=SimpleNamespace(usage=usage)
            response=SimpleNamespace(response_id=f"resp-{agent_id}",request_id="req-step044-tool",output=[1])
            self.last_response_id=response.response_id
            await hooks.on_llm_end(SimpleNamespace(),self.agent,response)
            tool=self.agent.tools[0]
            execution_id=self.kwargs["context"]["execution_id"]
            tool_context=FakeToolContext(context=self.kwargs["context"],tool_name=tool.name,tool_call_id="call-step044",tool_arguments=json.dumps({"execution_id":execution_id}))
            for guardrail in tool.tool_input_guardrails:
                output=await guardrail.run(SimpleNamespace(context=tool_context,agent=self.agent))
                if output.behavior["type"] == "raise_exception":
                    raise _attach_run_data(ToolInputGuardrailTripwireTriggered(guardrail,output),usage)
            await hooks.on_tool_start(tool_context,self.agent,tool)
            result=await tool.fn(tool_context,execution_id)
            counters["tool_executions"][agent_id] += 1
            for guardrail in tool.tool_output_guardrails:
                output=await guardrail.run(SimpleNamespace(context=tool_context,agent=self.agent,output=result))
                if output.behavior["type"] == "raise_exception":
                    raise _attach_run_data(ToolOutputGuardrailTripwireTriggered(guardrail,output),usage)
            await hooks.on_tool_end(tool_context,self.agent,tool,result)
            raise AssertionError("Guardrail Tool fixture must trip")

        def final_output_as(self, output_type, raise_if_incorrect_type=False):
            assert raise_if_incorrect_type is True and self._output is not None
            return self._output

    class FakeRunner:
        @classmethod
        async def run(cls,*args,**kwargs): counters["run"]+=1; raise AssertionError("STEP044 must use run_streamed")
        @classmethod
        def run_streamed(cls,agent,request,**kwargs): counters["run_streamed"]+=1; return FakeStreamingResult(agent,request,kwargs)

    class _Step052FakeModelRetrySettings:
        def __init__(self, **kwargs):
            self.max_retries = kwargs.get("max_retries")
            self.policy = kwargs.get("policy")

    class _Step052FakeRetryPolicies:
        @staticmethod
        def never():
            return lambda _context: False

    fake_agents.Agent=FakeAgent; fake_agents.ModelSettings=FakeModelSettings; fake_agents.ModelRetrySettings=_Step052FakeModelRetrySettings; fake_agents.retry_policies=_Step052FakeRetryPolicies(); fake_agents.RunConfig=FakeRunConfig; fake_agents.RunHooks=FakeRunHooks
    fake_agents.Runner=FakeRunner; fake_agents.ModelSettings=FakeModelSettings
    fake_tool_context=types.ModuleType("agents.tool_context"); fake_tool_context.ToolContext=FakeToolContext
    fake_agents.function_tool=function_tool
    fake_agents.GuardrailFunctionOutput=FakeGuardrailFunctionOutput
    fake_agents.ToolGuardrailFunctionOutput=FakeToolGuardrailFunctionOutput
    fake_agents.InputGuardrailTripwireTriggered=InputGuardrailTripwireTriggered
    fake_agents.OutputGuardrailTripwireTriggered=OutputGuardrailTripwireTriggered
    fake_agents.ToolInputGuardrailTripwireTriggered=ToolInputGuardrailTripwireTriggered
    fake_agents.ToolOutputGuardrailTripwireTriggered=ToolOutputGuardrailTripwireTriggered
    fake_agents.gen_trace_id=lambda:"trace-step044"
    fake_agents.set_default_openai_key=lambda value:None
    fake_decorators.input_guardrail=input_guardrail; fake_decorators.output_guardrail=output_guardrail
    fake_decorators.tool_input_guardrail=tool_input_guardrail; fake_decorators.tool_output_guardrail=tool_output_guardrail
    previous_tool_context=sys.modules.get("agents.tool_context")
    sys.modules["agents"]=fake_agents; sys.modules["agents.tool_context"]=fake_tool_context; sys.modules["agents.decorators"]=fake_decorators
    importlib.metadata.version=lambda name:"0.19.0" if name=="openai-agents" else previous_version(name)
    return counters,previous_version,previous_agents,previous_decorators,previous_tool_context


def _restore(previous_version,previous_agents,previous_decorators,previous_tool_context):
    importlib.metadata.version=previous_version
    if previous_agents is None: sys.modules.pop("agents",None)
    else: sys.modules["agents"]=previous_agents
    if previous_decorators is None: sys.modules.pop("agents.decorators",None)
    else: sys.modules["agents.decorators"]=previous_decorators
    if previous_tool_context is None: sys.modules.pop("agents.tool_context",None)
    else: sys.modules["agents.tool_context"]=previous_tool_context


def _wait_terminal(client,run_id):
    deadline=time.monotonic()+8
    while time.monotonic()<deadline:
        body=client.get(f"/v1/runs/{run_id}",headers=ADMIN_HEADERS).json()
        if body.get("status") in {"SUCCEEDED","FAILED","CANCELLED"}: return body
        time.sleep(.02)
    raise RuntimeError("STEP044 Run did not terminate")


def _execute(client,agent_id,request,key):
    pre=client.post("/v1/run-submissions/preflight",headers=SUBMIT_HEADERS,json={"agent_definition_id":agent_id,"input":request,"model":"deterministic-step044-model","idempotency_key":key}).json()
    confirm=client.post(f"/v1/run-submissions/{pre['submission_id']}/confirm",headers=SUBMIT_HEADERS,json={"confirmation":pre["confirmation_challenge"]}).json()
    terminal=_wait_terminal(client,confirm["run_id"])
    events=client.get(f"/v1/runs/{confirm['run_id']}/events",headers=ADMIN_HEADERS).json()["events"]
    invocations=client.get(f"/v1/runs/{confirm['run_id']}/invocations",headers=ADMIN_HEADERS).json()["invocations"]
    submission=client.get(f"/v1/run-submissions/{pre['submission_id']}",headers=ADMIN_HEADERS).json()
    return {"preflight":pre,"confirm":confirm,"terminal":terminal,"events":events,"invocations":invocations,"submission":submission}


def _counts(product_db,evaluation_db):
    p=sqlite3.connect(product_db); e=sqlite3.connect(evaluation_db)
    try:
        return {"tasks":p.execute("select count(*) from task").fetchone()[0],"runs":p.execute("select count(*) from run").fetchone()[0],"submissions":p.execute("select count(*) from run_submission_preflight").fetchone()[0],"invocations":p.execute("select count(*) from agent_invocation").fetchone()[0],"events":p.execute("select count(*) from run_event").fetchone()[0],"artifacts":p.execute("select count(*) from artifact").fetchone()[0],"evaluations":e.execute("select count(*) from evaluation_result").fetchone()[0]}
    finally: p.close(); e.close()


def run_acceptance(output:Path)->int:
    refs_before={x.reference_id:x.to_dict() for x in ReferenceCatalogService(ROOT).verify_all()}
    counters,pv,pa,pd,ptc=_install_fake_agents(); old=os.environ.get("OPENAI_API_KEY"); os.environ["OPENAI_API_KEY"]=HIDDEN_API_KEY
    try:
        with AcceptanceWorkspace(step_id="STEP044",output=output) as ws:
            product_db=ws.database_dir/"product.sqlite3"; evaluation_db=ws.database_dir/"evaluation.sqlite3"; payload_root=ws.scratch_dir/"payloads"
            app=create_app(project_root=ROOT,product_db=product_db,artifact_root=ws.artifact_dir,evaluation_db=evaluation_db,admin_key=ADMIN_KEY,run_submitter_key=SUBMITTER_KEY,protected_payload_root=payload_root,protected_payload_key=PAYLOAD_KEY,native_stream_broker=InMemoryNativeSDKStreamBroker())
            with TestClient(app) as client:
                cases={
                    "clean":_execute(client,"guardrail-language-agent",RAW_SENTINELS["clean"],"step044-clean-0001"),
                    "input":_execute(client,"guardrail-language-agent",RAW_SENTINELS["input"],"step044-input-0002"),
                    "output":_execute(client,"guardrail-language-agent",RAW_SENTINELS["output"],"step044-output-0003"),
                    "tool_input":_execute(client,"guardrail-tool-input-agent",RAW_SENTINELS["tool_input"],"step044-tool-input-0004"),
                    "tool_output":_execute(client,"guardrail-tool-output-agent",RAW_SENTINELS["tool_output"],"step044-tool-output-0005"),
                }
                clean=cases["clean"]
                artifact=client.get(f"/v1/runs/{clean['confirm']['run_id']}/artifact",headers=ADMIN_HEADERS).json()
                eval_resp=client.post(f"/v1/runs/{clean['confirm']['run_id']}/evaluations",headers=ADMIN_HEADERS,json={"case_id":"native-guardrail-v1"})
                evaluation=eval_resp.json()
            product_text=product_db.read_bytes().decode("utf-8",errors="ignore"); eval_text=evaluation_db.read_bytes().decode("utf-8",errors="ignore")
            final_counts=_counts(product_db,evaluation_db)
            refs_after={x.reference_id:x.to_dict() for x in ReferenceCatalogService(ROOT).verify_all()}
            def trip(case): return [e for e in case["events"] if e["event_type"]=="guardrail.tripped"]
            expected_codes={"input":"INPUT_GUARDRAIL_TRIPPED","output":"OUTPUT_GUARDRAIL_TRIPPED","tool_input":"TOOL_INPUT_GUARDRAIL_TRIPPED","tool_output":"TOOL_OUTPUT_GUARDRAIL_TRIPPED"}
            checks={
                "guardrail_catalog_exact":len(AgentDefinitionCatalog(ROOT).resolve("guardrail-language-agent").guardrails)==2,
                "native_streaming_runner_used_five_times":counters["run_streamed"]==5 and counters["run"]==0,
                "clean_guardrail_path_succeeded":clean["terminal"].get("status")=="SUCCEEDED" and len(trip(clean))==0,
                "input_tripwire_before_model":cases["input"]["terminal"].get("status")=="FAILED" and counters["model_calls"]==4,
                "output_tripwire_after_model":cases["output"]["terminal"].get("status")=="FAILED",
                "tool_input_tripwire_prevented_execution":counters["tool_executions"]["guardrail-tool-input-agent"]==0,
                "tool_output_tripwire_followed_one_execution":counters["tool_executions"]["guardrail-tool-output-agent"]==1,
                "four_tripwire_error_codes_exact":all(cases[k]["submission"].get("state")=="EXECUTION_FAILED" and any(e["event_type"]=="run.failed" and e["payload"].get("code")==v for e in cases[k]["events"]) for k,v in expected_codes.items()),
                "one_safe_tripwire_event_per_rejection":all(len(trip(cases[k]))==1 for k in expected_codes),
                "tripwire_metadata_safe":all(set(trip(cases[k])[0]["payload"])=={"guardrail_id","guardrail_kind","tool_id","behavior","tripwire_triggered","guarded_content_persisted","output_info_persisted","raw_sdk_error_persisted"} and not trip(cases[k])[0]["payload"]["guarded_content_persisted"] and not trip(cases[k])[0]["payload"]["output_info_persisted"] for k in expected_codes),
                "rejected_runs_created_no_artifact":all(not any(e["event_type"]=="artifact.created" for e in cases[k]["events"]) for k in expected_codes),
                "clean_artifact_verified":artifact.get("artifact_id") and artifact.get("content",{}).get("status")=="PASS",
                "clean_recorded_evaluation_passed":eval_resp.status_code==201 and evaluation.get("state")=="PASSED",
                "all_root_invocations_terminal":all(len(c["invocations"])==1 and c["invocations"][0]["state"] in {"SUCCEEDED","FAILED"} and c["invocations"][0]["workspace_access"]=="none" for c in cases.values()),
                "guardrail_runtime_bound":all(c["preflight"].get("runtime_binding_sha256") for c in cases.values()),
                "pydantic_validation_remains_distinct":all(not any(e["payload"].get("code")=="OUTPUT_CONTRACT_INVALID" for e in c["events"] if e["event_type"]=="run.failed") for c in cases.values()),
                "successful_payload_deleted_failures_retained":clean["submission"].get("payload_retention_state")=="DELETED" and all(cases[k]["submission"].get("payload_retention_state")=="RETAINED" for k in expected_codes),
                "protected_payload_count_exact":len(list(payload_root.glob("payload_*.json")))==4,
                "raw_guarded_content_not_in_product_or_evaluation_db":all(v not in product_text and v not in eval_text for v in RAW_SENTINELS.values()),
                "api_key_not_persisted":HIDDEN_API_KEY not in product_text and HIDDEN_API_KEY not in eval_text,
                "product_counts_exact":final_counts=={"tasks":5,"runs":5,"submissions":5,"invocations":5,"events":48,"artifacts":1,"evaluations":1},
                "references_unchanged":refs_before==refs_after,
                "cleanup_completed":True,
            }
            payload={"schema_version":"okcanvas-step044-acceptance-v1","state":"PASSED" if all(checks.values()) else "FAILED","checks":checks,"gateway_counts":counters,"cases":{k:{"run_id":v["confirm"]["run_id"],"submission_id":v["preflight"]["submission_id"],"status":v["terminal"].get("status"),"event_count":len(v["events"]),"tripwire":trip(v)[0]["payload"] if trip(v) else None} for k,v in cases.items()},"final_counts":final_counts,"artifact_id":artifact.get("artifact_id"),"evaluation_id":evaluation.get("evaluation_id"),"protected_payload_file_count":len(list(payload_root.glob("payload_*.json")))}
            output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            print(json.dumps(payload,ensure_ascii=False,indent=2)); return 0 if payload["state"]=="PASSED" else 1
    finally:
        _restore(pv,pa,pd,ptc)
        if old is None: os.environ.pop("OPENAI_API_KEY",None)
        else: os.environ["OPENAI_API_KEY"]=old


def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--output",type=Path,default=ROOT/"docs/evidence/STEP044_ACCEPTANCE.json"); args=parser.parse_args(); return run_acceptance(args.output)
if __name__=="__main__": raise SystemExit(main())
