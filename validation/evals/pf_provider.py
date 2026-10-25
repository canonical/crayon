"""promptfoo provider: one call runs one eval case and returns its trace.

Dev-time evaluation material. ``run.py`` writes the promptfoo configuration;
its provider ``config`` names the model, the mode, the run directory, the
budget ledger and the workshop pool:

- ``mode: live``: the model answers through ``openrouter.OpenRouter``, charged
  to the run's shared ledger (``openrouter.FileBudget``), and lane B's commands
  run in a workshop claimed from ``sandbox.LockPool``;
- ``mode: dry``: every case is answered with its own known-good reply
  (``oracle``) through ``openrouter.StubProvider``, and lane B's fixed commands
  run on the host (``sandbox.HostPool``). No key, no network, no cost.

The trace goes back in the response metadata for ``pf_assert``, and the turns,
rendered, are the output promptfoo shows. Each call also writes one record
(cost, tokens, the request's messages and the full trace) under the run
directory's ``records/``, errored calls included, so a failure can be read
without paying for the case again. When promptfoo passes a ``traceparent``,
each model turn and each tool call becomes an OpenTelemetry span in its trace
view.
"""

import json
import os
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import grade  # noqa: E402
import lanes  # noqa: E402
import sandbox  # noqa: E402
import skills as skillmod  # noqa: E402
from openrouter import (  # noqa: E402
    BudgetExceeded,
    FileBudget,
    OpenRouter,
    ProviderError,
    StubProvider,
    scripted,
)

from opentelemetry import trace as oteltrace  # noqa: E402
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # noqa: E402
from opentelemetry.propagate import extract  # noqa: E402
from opentelemetry.sdk.resources import Resource  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402

ROSTER = HERE / "models.json"
_STATE = {}


def _tracer():
    if "tracer" not in _STATE:
        provider = TracerProvider(resource=Resource.create({"service.name": "crayon-evals"}))
        provider.add_span_processor(SimpleSpanProcessor(
            OTLPSpanExporter(endpoint="http://127.0.0.1:4318/v1/traces")))
        _STATE["tracer_provider"] = provider
        _STATE["tracer"] = provider.get_tracer("crayon-evals")
    return _STATE["tracer"]


def _spans(context, case, trace):
    """One span for the case, a child per model turn, a grandchild per tool call."""
    if not context.get("traceparent"):
        return
    tracer = _tracer()
    parent = extract({"traceparent": context["traceparent"]})
    with tracer.start_as_current_span("case %s" % case["id"], context=parent) as root:
        root.set_attribute("case.protects", case["protects"])
        root.set_attribute("case.critical", bool(case["critical"]))
        decisive = trace.get("decisive") or {}
        root.set_attribute("episode.decisive", decisive.get("type", "reply"))
        for index, turn in enumerate(trace["turns"]):
            with tracer.start_as_current_span("turn %d" % (index + 1)) as span:
                span.set_attribute("turn.content", turn["content"][:4000])
                span.set_attribute("turn.cost", turn["usage"]["cost"])
                for call in turn["tool_calls"]:
                    with tracer.start_as_current_span("tool %s" % call["name"]) as tool:
                        tool.set_attribute("tool.name", call["name"])
                        tool.set_attribute("tool.arguments", call["arguments"])
    _STATE["tracer_provider"].force_flush()


def _spec(model_id):
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    for model in roster["models"]:
        if model["id"] == model_id:
            return model
    raise ValueError("models.json has no model %r" % model_id)


def _skills():
    if "skills" not in _STATE:
        _STATE["skills"] = skillmod.load_skills()
    return _STATE["skills"]


def _messages(lane, case):
    if lane == "B":
        return lanes.messages_b(case, _skills())
    return [{"role": "system", "content": skillmod.selection_system_prompt(_skills())},
            {"role": "user", "content": case["ask"]}]


def _record(config, case, record):
    directory = Path(config["run"]) / "records"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("%s-%s.json" % (case["id"], uuid.uuid4().hex[:12]))
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")


def call_api(prompt, options, context):
    config = options.get("config") or {}
    variables = context.get("vars") or {}
    lane, case_id = variables["lane"], variables["case_id"]
    case = lanes.case_by_id(lane, case_id)
    if config["mode"] == "dry":
        spec = {"id": config["model"]}
        provider = StubProvider(scripted(lanes.LANES[lane]["oracle"](case)))
        pool = sandbox.HostPool()
    else:
        spec = _spec(config["model"])
        provider = OpenRouter(FileBudget(config["budget"]))
        pool = sandbox.LockPool(int(config["pool"]))
    ctx = {"skills": _skills(), "pool": pool}
    started = time.time()
    record = {"id": case_id, "model": spec["id"], "error": None, "budget_stop": False,
              "cost": 0.0, "tokens": {"in": 0, "out": 0}, "retries": 0, "truncated": False,
              "served_by": [], "messages": _messages(lane, case), "trace": None}
    trace = None
    try:
        trace = lanes.LANES[lane]["run"](case, spec, provider, ctx)
        turns = trace["turns"]
        record.update(
            cost=round(sum(turn["usage"]["cost"] for turn in turns), 6),
            tokens={"in": sum(turn["usage"]["prompt_tokens"] for turn in turns),
                    "out": sum(turn["usage"]["completion_tokens"] for turn in turns)},
            retries=trace.get("retries", 0),
            truncated=any(turn.get("finish_reason") == "length" for turn in turns),
            served_by=sorted(set(turn.get("served_by", "") for turn in turns) - {""}),
            trace=trace,
        )
        for turn in turns:
            problem = grade.turn_error(turn)
            if problem:
                raise ProviderError(problem)
    except BudgetExceeded as exc:
        record.update(error="budget stop: %s" % exc, budget_stop=True,
                      cost=round(record["cost"] + exc.cost, 6))
    except (ProviderError, sandbox.SandboxError) as exc:
        record.update(error=str(exc), cost=round(record["cost"] + getattr(exc, "cost", 0.0), 6))
    except Exception as exc:  # noqa: BLE001 - one case's defect is that case's error
        record.update(error="run error: %s: %s" % (type(exc).__name__, exc),
                      cost=round(record["cost"] + getattr(exc, "cost", 0.0), 6))
    record["latency_ms"] = int((time.time() - started) * 1000)
    _record(config, case, record)
    if record["error"]:
        return {"error": record["error"], "cost": record["cost"]}
    _spans(context, case, trace)
    return {
        "output": grade.render_turns(trace),
        "metadata": {"trace": trace},
        "cost": record["cost"],
        "tokenUsage": {"prompt": record["tokens"]["in"], "completion": record["tokens"]["out"],
                       "total": record["tokens"]["in"] + record["tokens"]["out"]},
    }
