"""The eval kit's one model transport: OpenRouter chat completions over urllib.

Dev-time evaluation material, like ``validation/score.py``: stdlib only, never
imported by the tool. One call shape for every lane — messages in, one
normalised assistant turn out — so a lane never touches HTTP, and the offline
``StubProvider`` can stand in for the network in the gate.

A normalised turn is a plain dict::

    {"content": str, "tool_calls": [{"id", "name", "arguments"}],
     "finish_reason": str, "usage": {"prompt_tokens", "completion_tokens",
     "cost"}, "cached": bool, "served_by": str}

Three guards live here and nowhere else:

- ``Budget``: checked before every paid call and charged after it. A run that
  reaches its cap stops with ``BudgetExceeded``. With ``N`` calls in flight the
  overshoot is bounded by the ``N - 1`` calls already sent when the cap was
  crossed, so the cap is set with that headroom in mind.
- The cache: keyed on the exact request body, so any change to the skill text,
  the case, the tools or the model parameters is a miss. Lanes that act on a
  real sandbox pass ``cache=False``.
- Retries: only on 429, 5xx and transport errors, with backoff. Every other
  failure is a ``ProviderError`` the runner reports as a run-level error,
  never as a failed case.
"""

import hashlib
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_ENV = "OPENROUTER_API_KEY"
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}


class ProviderError(Exception):
    """A call that could not produce a turn: a run-level error, not a failure."""


class BudgetExceeded(Exception):
    """The run's spend cap is reached; nothing further may be called."""


class Budget:
    """A spend cap in USD, with optional per-scope sub-caps (one per model)."""

    def __init__(self, cap_usd, scope_cap_usd=None):
        self.cap = float(cap_usd)
        self.scope_cap = None if scope_cap_usd is None else float(scope_cap_usd)
        self.spent = 0.0
        self.by_scope = {}
        self._lock = threading.Lock()

    def check(self, scope=None):
        with self._lock:
            self._check(scope)

    def _check(self, scope):
        if self.spent >= self.cap:
            raise BudgetExceeded(
                "spend cap reached: $%.4f of $%.2f" % (self.spent, self.cap)
            )
        if scope is not None and self.scope_cap is not None:
            used = self.by_scope.get(scope, 0.0)
            if used >= self.scope_cap:
                raise BudgetExceeded(
                    "%s reached its cap: $%.4f of $%.2f"
                    % (scope, used, self.scope_cap)
                )

    def charge(self, cost, scope=None):
        cost = float(cost or 0.0)
        with self._lock:
            self.spent += cost
            if scope is not None:
                self.by_scope[scope] = self.by_scope.get(scope, 0.0) + cost


def request_body(spec, messages, tools=None):
    """The exact JSON body sent for ``spec`` — and the cache key's input.

    ``reasoning.exclude`` keeps a reasoning model's trace out of ``content``,
    so a ``not_prescribed`` assertion never grades the model's scratch work.
    ``usage.include`` asks OpenRouter to report the call's real cost.
    """
    body = {
        "model": spec["id"],
        "messages": messages,
        "temperature": spec.get("temperature", 0.0),
        "max_tokens": spec.get("max_tokens", 2048),
        "reasoning": dict({"exclude": True}, **spec.get("reasoning", {})),
        "usage": {"include": True},
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    if spec.get("provider"):
        body["provider"] = spec["provider"]
    return body


def cache_key(body):
    blob = json.dumps(body, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def estimate_cost(spec, usage):
    """Fallback when a response carries no ``usage.cost``: the roster's price."""
    price = spec.get("price_per_mtok")
    if not price:
        return 0.0
    return (
        usage.get("prompt_tokens", 0) * price[0]
        + usage.get("completion_tokens", 0) * price[1]
    ) / 1e6


def normalise(payload, spec):
    """One OpenRouter response body -> one normalised turn."""
    if "error" in payload and not payload.get("choices"):
        err = payload["error"] or {}
        raise ProviderError(
            "API error %s: %s" % (err.get("code"), err.get("message"))
        )
    try:
        choice = payload["choices"][0]
        message = choice.get("message") or {}
    except (KeyError, IndexError, TypeError):
        raise ProviderError("malformed response: no choices[0].message")
    calls = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        calls.append(
            {
                "id": call.get("id") or "call_%d" % len(calls),
                "name": function.get("name") or "",
                "arguments": function.get("arguments") or "{}",
            }
        )
    raw_usage = payload.get("usage") or {}
    usage = {
        "prompt_tokens": int(raw_usage.get("prompt_tokens") or 0),
        "completion_tokens": int(raw_usage.get("completion_tokens") or 0),
    }
    cost = raw_usage.get("cost")
    usage["cost"] = float(cost) if cost is not None else estimate_cost(spec, usage)
    return {
        "content": message.get("content") or "",
        "tool_calls": calls,
        "finish_reason": choice.get("finish_reason") or "",
        "usage": usage,
        "cached": False,
        "served_by": payload.get("provider") or "",
    }


class OpenRouter:
    """The paid transport. Reads the key from the environment, never a file."""

    def __init__(self, budget, cache_dir=None, api_key=None, retries=4,
                 backoff=5.0, timeout=120, sleep=time.sleep, opener=None):
        self.key = api_key or os.environ.get(KEY_ENV, "")
        if not self.key:
            raise ProviderError("%s is not set" % KEY_ENV)
        self.budget = budget
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        self.sleep = sleep
        self.opener = opener or urllib.request.urlopen

    def complete(self, spec, messages, tools=None, cache=True, scope=None):
        body = request_body(spec, messages, tools)
        key = cache_key(body)
        if cache and self.cache_dir is not None:
            hit = self.cache_dir / ("%s.json" % key)
            if hit.is_file():
                turn = json.loads(hit.read_text(encoding="utf-8"))
                turn["cached"] = True
                turn["usage"]["cost"] = 0.0
                return turn
        self.budget.check(scope)
        payload = self._post(body)
        turn = normalise(payload, spec)
        self.budget.charge(turn["usage"]["cost"], scope)
        if cache and self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / ("%s.json" % key)).write_text(
                json.dumps(turn, sort_keys=True), encoding="utf-8"
            )
        return turn

    def _post(self, body):
        data = json.dumps(body).encode("utf-8")
        last = "no attempt made"
        for attempt in range(self.retries + 1):
            if attempt:
                self.sleep(self.backoff * (2 ** (attempt - 1)))
            request = urllib.request.Request(
                API_URL,
                data=data,
                headers={
                    "Authorization": "Bearer %s" % self.key,
                    "Content-Type": "application/json",
                    "X-Title": "dogen evals",
                },
            )
            try:
                with self.opener(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last = "HTTP %d: %s" % (exc.code, _read_error(exc))
                if exc.code in RETRY_STATUSES:
                    continue
                raise ProviderError(last)
            except (urllib.error.URLError, socket.timeout, ConnectionError) as exc:
                last = "transport: %s" % exc
                continue
            except ValueError as exc:
                raise ProviderError("response is not JSON: %s" % exc)
            error = payload.get("error") if isinstance(payload, dict) else None
            if error and not payload.get("choices"):
                code = error.get("code")
                last = "API error %s: %s" % (code, error.get("message"))
                if code in RETRY_STATUSES:
                    continue
                raise ProviderError(last)
            return payload
        raise ProviderError("gave up after %d attempt(s): %s" % (self.retries + 1, last))


def _read_error(exc):
    try:
        return exc.read().decode("utf-8", "replace")[:300]
    except Exception:  # an unreadable error body still names its status
        return "(no body)"


class StubProvider:
    """The offline transport: every turn comes from ``responder``, cost zero.

    ``responder(spec, messages, tools)`` returns either a string (the content)
    or a partial turn dict (``content`` and/or ``tool_calls``). The gate's
    self-tests and ``run.py --dry-run`` use it, so neither needs the network.
    """

    def __init__(self, responder=None):
        self.responder = responder or (lambda spec, messages, tools: "none")
        self.calls = []

    def complete(self, spec, messages, tools=None, cache=True, scope=None):
        self.calls.append({"model": spec["id"], "messages": messages, "tools": tools})
        reply = self.responder(spec, messages, tools)
        if isinstance(reply, str):
            reply = {"content": reply}
        calls = []
        for index, call in enumerate(reply.get("tool_calls") or []):
            arguments = call.get("arguments", {})
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments)
            calls.append(
                {"id": call.get("id", "stub_%d" % index), "name": call["name"],
                 "arguments": arguments}
            )
        return {
            "content": reply.get("content") or "",
            "tool_calls": calls,
            "finish_reason": "tool_calls" if calls else "stop",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0},
            "cached": False,
            "served_by": "stub",
        }
