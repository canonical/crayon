"""The eval kit's one model transport: OpenRouter chat completions over urllib.

Dev-time evaluation material, never imported by the tool. One call shape for
every lane: messages in, one normalised assistant turn out. A lane never touches
HTTP, and the offline ``StubProvider`` stands in for the network in the gate.

A normalised turn is a plain dict::

    {"content": str, "tool_calls": [{"id", "name", "arguments"}],
     "finish_reason": str, "usage": {"prompt_tokens", "completion_tokens",
     "cost"}, "served_by": str}

Two guards live here and nowhere else:

- ``Budget``: before every paid call, the call's largest possible cost is
  reserved (``max_cost``: its request bytes as prompt tokens and its
  ``max_tokens`` as completion tokens, at the roster's price), and the call is
  refused if the reservation would pass the run's cap or the model's cap. After
  the call the reservation is settled at what the call was charged. Calls in
  flight therefore never spend past a cap. A paid response is charged before
  its body is read (``charged_cost``), so a body the kit cannot read is still
  on the cap and, through its ``ProviderError``, on a record. A call whose
  answer is lost after its request was sent whole is charged its reservation
  and never retried, because a retry could bill it twice. A run that reaches its
  cap stops with ``BudgetExceeded``, which carries the cost of the case's calls
  already paid, so the case's record keeps it.
- Retries: each with backoff, on a retry status (``RETRY_STATUSES``), whether
  it comes as an ``HTTPError`` or in an API error body, and on a ``URLError``
  from the opener, which urllib raises before the request is sent whole. Every
  other failure is a ``ProviderError`` the runner reports as a run-level error,
  never as a failed case.

There is no response cache: every answer a result records is a new
observation of the model.
"""

import contextlib
import fcntl
import http.client
import json
import math
import os
import threading
import time
import urllib.error
import urllib.request

API_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_ENV = "OPENROUTER_API_KEY"
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}


class ProviderError(Exception):
    """A call that could not produce a turn: a run-level error, not a failure.

    ``cost`` is money spent on calls whose turns reach no record because of this
    error, 0.0 unless a paid call came before it: each caller that holds paid
    turns adds theirs before it lets the error go on, so a record's cost still
    adds up to what was spent. An ``AnswerLost`` carries the reservation
    ``complete`` charged for an answer lost after its request was sent whole.
    """

    cost = 0.0


class AnswerLost(ProviderError):
    """A call whose request was sent whole and whose answer was lost.

    No status line came back, or the body was lost while it was read. The provider
    held the whole request, so the call may have run and be billed: ``complete``
    charges it its reservation, on the cap and on this error, and it is never
    retried, because a retry could bill it again with nothing charged.
    """


class BudgetExceeded(Exception):
    """The run's spend cap is reached; nothing further may be called.

    ``cost`` is money spent on calls whose turns reach no record because the stop
    came mid-case, 0.0 unless a paid call in the same case came before it. Each
    caller that holds paid turns adds theirs before it lets the stop go on, as for
    ``ProviderError.cost``, so the runner records a case that ran as stopped with
    what it paid.
    """

    cost = 0.0


def carry_cost(exc, cost):
    """``exc`` carrying ``cost``: the one place an escaping exception picks up the
    cost its caller holds, so a record's cost adds up to what was spent.

    A ``ProviderError`` or a ``BudgetExceeded`` is returned with ``cost`` added to
    its own. Any other exception is wrapped in a new ``ProviderError`` reading
    ``run error: <Type>: <message>``, caused by the original and carrying ``cost``,
    so the runner records it as the case's run-level error with what was paid.
    """
    if isinstance(exc, (ProviderError, BudgetExceeded)):
        exc.cost += cost
        return exc
    wrapped = ProviderError("run error: %s: %s" % (type(exc).__name__, exc))
    wrapped.__cause__ = exc
    wrapped.cost = cost
    return wrapped


class Budget:
    """A spend cap in USD, with a per-scope cap (one per model).

    ``reserve`` holds a call's largest possible cost before the call is sent and
    refuses it if that would pass a cap; ``settle`` replaces the reservation with
    what the call was charged. ``spent`` counts settled charges only.
    """

    def __init__(self, cap_usd, scope_cap_usd=None):
        self.cap = float(cap_usd)
        self.scope_cap = None if scope_cap_usd is None else float(scope_cap_usd)
        self.spent = 0.0
        self.by_scope = {}
        self.held = 0.0
        self.held_by_scope = {}
        self._lock = threading.Lock()

    def reserve(self, amount, scope=None):
        amount = float(amount or 0.0)
        with self._lock:
            if self.spent + self.held + amount > self.cap:
                raise BudgetExceeded("spend cap reached: $%.4f spent and $%.4f in flight of "
                                     "$%.2f" % (self.spent, self.held, self.cap))
            if scope is not None and self.scope_cap is not None:
                used = self.by_scope.get(scope, 0.0) + self.held_by_scope.get(scope, 0.0)
                if used + amount > self.scope_cap:
                    raise BudgetExceeded("%s reached its cap: $%.4f of $%.2f"
                                         % (scope, used, self.scope_cap))
            self.held += amount
            if scope is not None:
                self.held_by_scope[scope] = self.held_by_scope.get(scope, 0.0) + amount
        return amount

    def settle(self, reserved, cost, scope=None):
        cost = float(cost or 0.0)
        with self._lock:
            self.held -= reserved
            self.spent += cost
            if scope is not None:
                self.held_by_scope[scope] = self.held_by_scope.get(scope, 0.0) - reserved
                self.by_scope[scope] = self.by_scope.get(scope, 0.0) + cost


class FileBudget(object):
    """``Budget`` shared by several processes through one JSON file under a lock.

    promptfoo runs the provider in parallel worker processes; each opens the
    run's ledger with this class, so the run's cap and each model's cap hold
    across all of them. Once a reservation is refused, the ledger records the
    stop and every later reservation is refused too.
    """

    def __init__(self, path, cap_usd=None, scope_cap_usd=None):
        self.path = str(path)
        if cap_usd is not None:
            with self._locked() as state:
                state.setdefault("cap", float(cap_usd))
                state.setdefault("scope_cap", None if scope_cap_usd is None
                                 else float(scope_cap_usd))

    @contextlib.contextmanager
    def _locked(self):
        with open(self.path + ".lock", "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                try:
                    with open(self.path, encoding="utf-8") as handle:
                        state = json.load(handle)
                except (OSError, ValueError):
                    state = {}
                for key in ("spent", "held"):
                    state.setdefault(key, 0.0)
                for key in ("by_scope", "held_by_scope"):
                    state.setdefault(key, {})
                try:
                    yield state
                finally:
                    # Written even when the block raised: a refused reservation
                    # records the stop every other process must see.
                    tmp = self.path + ".tmp"
                    with open(tmp, "w", encoding="utf-8") as handle:
                        json.dump(state, handle, sort_keys=True)
                    os.replace(tmp, self.path)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def state(self):
        with self._locked() as state:
            return dict(state)

    @property
    def spent(self):
        return self.state()["spent"]

    @property
    def cap(self):
        return self.state()["cap"]

    def reserve(self, amount, scope=None):
        amount = float(amount or 0.0)
        with self._locked() as state:
            if state.get("stopped"):
                raise BudgetExceeded(state["stopped"])
            cap, scope_cap = state["cap"], state.get("scope_cap")
            reason = None
            if state["spent"] + state["held"] + amount > cap:
                reason = "spend cap reached: $%.4f spent and $%.4f in flight of $%.2f" % (
                    state["spent"], state["held"], cap)
            elif scope is not None and scope_cap is not None:
                used = state["by_scope"].get(scope, 0.0) + state["held_by_scope"].get(scope, 0.0)
                if used + amount > scope_cap:
                    reason = "%s reached its cap: $%.4f of $%.2f" % (scope, used, scope_cap)
            if reason:
                state["stopped"] = reason
                raise BudgetExceeded(reason)
            state["held"] += amount
            if scope is not None:
                state["held_by_scope"][scope] = state["held_by_scope"].get(scope, 0.0) + amount
        return amount

    def settle(self, reserved, cost, scope=None):
        cost = float(cost or 0.0)
        with self._locked() as state:
            state["held"] -= reserved
            state["spent"] += cost
            if scope is not None:
                state["held_by_scope"][scope] = state["held_by_scope"].get(scope, 0.0) - reserved
                state["by_scope"][scope] = state["by_scope"].get(scope, 0.0) + cost


def _cache_marked(message):
    """``message`` with its text as one content part carrying a cache breakpoint."""
    content = message.get("content")
    if isinstance(content, str) and content:
        return dict(message, content=[{"type": "text", "text": content,
                                       "cache_control": {"type": "ephemeral"}}])
    return message


def request_body(spec, messages, tools=None):
    """The exact JSON body sent for ``spec``.

    Models run with their default sampling, as authors run them: no
    ``temperature`` is sent. ``reasoning.exclude`` keeps a reasoning model's
    trace out of ``content``, so a text assertion never grades the model's
    scratch work. ``usage.include`` asks OpenRouter to report the call's real
    cost. A model with ``prompt_cache`` gets two cache breakpoints: the system
    prompt (the same for every case) and the last user message (the same for
    every turn of an episode and every repeat of a case).
    """
    if spec.get("prompt_cache"):
        messages = list(messages)
        users = [i for i, m in enumerate(messages) if m.get("role") == "user"]
        for index in ([0] if messages and messages[0].get("role") == "system" else []) + users[-1:]:
            messages[index] = _cache_marked(messages[index])
    body = {
        "model": spec["id"],
        "messages": messages,
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


def estimate_cost(spec, usage):
    """Fallback when a response carries no ``usage.cost``: the roster's price."""
    price = spec.get("price_per_mtok")
    if not price:
        return 0.0
    return (
        usage.get("prompt_tokens", 0) * price[0]
        + usage.get("completion_tokens", 0) * price[1]
    ) / 1e6


def max_cost(spec, body):
    """The most one call can cost: what ``Budget.reserve`` holds before it is sent.

    The request's UTF-8 byte count as prompt tokens and its ``max_tokens`` as
    completion tokens, at the roster's price (``estimate_cost``). It overstates
    the call, the safe direction for a cap: a byte-level tokenizer makes no more
    tokens than bytes, and the completion is capped at ``max_tokens``.
    """
    return estimate_cost(spec, {"prompt_tokens": len(json.dumps(body).encode("utf-8")),
                                "completion_tokens": body.get("max_tokens", 0)})


#: A readable token count is an ``int`` below this: no real call reports a
#: quadrillion tokens, and a count this large in a body is a sign it is not one
#: the provider sent.
_TOKEN_CAP = 10 ** 15


def _token_count(value):
    """``value`` when it reads as a token count, else None: the one definition.

    An ``int`` that is not a ``bool`` and lies in ``[0, _TOKEN_CAP)``.
    ``normalise`` and ``charged_cost`` both use it.
    """
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < _TOKEN_CAP:
        return value
    return None


def _cost_value(value):
    """``value`` as a float when it reads as a cost, else None.

    A number that is not a ``bool``, finite and not negative; an ``int`` too large
    for a float is not one.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        cost = float(value)
    except OverflowError:
        return None
    return cost if math.isfinite(cost) and cost >= 0 else None


def charged_cost(payload, spec):
    """What one paid response body is charged: never raises, whatever its shape.

    A paid call is charged before its body is read, so a body the kit cannot
    read is still spend on the cap and on a record. The charge is the body's
    ``usage.cost`` when that reads as a cost, else ``estimate_cost`` over the
    token counts that read as counts (one that does not counts 0), which is 0.0
    for a model with no listed price.
    """
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        usage = {}
    cost = _cost_value(usage.get("cost"))
    if cost is not None:
        return cost
    return estimate_cost(spec, dict((key, _token_count(usage.get(key)) or 0)
                                    for key in ("prompt_tokens", "completion_tokens")))


def _shaped(value, kind, where):
    """``value`` when it is null or a ``kind``, else a ``malformed response`` error."""
    if value is not None and not isinstance(value, kind):
        raise ProviderError("malformed response: %s is %s, not %s"
                            % (where, type(value).__name__, kind.__name__))
    return value


def normalise(payload, spec):
    """One OpenRouter response body -> one normalised turn.

    Every field is read as the type the turn states, or the body is a
    ``ProviderError`` starting ``malformed response``: the body and each choice
    objects, ``choices`` a non-empty list; ``message``, a call's ``function`` and
    ``usage`` objects; ``content``, ``finish_reason``, ``provider`` and a call's
    ``id``, ``name`` and ``arguments`` strings; ``tool_calls`` a list of objects;
    each token count read by ``_token_count`` and ``cost`` by ``_cost_value``. A
    null takes its default. So nothing past the transport meets a shape it cannot
    read, and the error reaches the runner as the case's run-level error, after
    ``complete`` charged the call.
    """
    if not isinstance(payload, dict):
        raise ProviderError("malformed response: the body is %s, not an object"
                            % type(payload).__name__)
    if "error" in payload and not payload.get("choices"):
        err = payload["error"] or {}
        raise ProviderError(
            "API error %s: %s" % (err.get("code"), err.get("message"))
        )
    choices = _shaped(payload.get("choices"), list, "choices")
    if not choices:
        raise ProviderError("malformed response: no choices[0].message")
    for index, item in enumerate(choices):
        _shaped(item, dict, "choices[%d]" % index)
    choice = choices[0]
    message = _shaped(choice.get("message"), dict, "choices[0].message") or {}
    calls = []
    for call in _shaped(message.get("tool_calls"), list, "message.tool_calls") or []:
        where = "tool_calls[%d]" % len(calls)
        _shaped(call, dict, where)
        function = _shaped(call.get("function"), dict, where + ".function") or {}
        calls.append(
            {
                "id": _shaped(call.get("id"), str, where + ".id") or "call_%d" % len(calls),
                "name": _shaped(function.get("name"), str, where + ".name") or "",
                "arguments": _shaped(function.get("arguments"), str,
                                     where + ".arguments") or "{}",
            }
        )
    raw_usage = _shaped(payload.get("usage"), dict, "usage") or {}
    usage = {}
    for key in ("prompt_tokens", "completion_tokens"):
        count = raw_usage.get(key)
        if count is not None and _token_count(count) is None:
            raise ProviderError("malformed response: usage.%s is %r, not a token count"
                                % (key, count))
        usage[key] = count or 0
    if raw_usage.get("cost") is not None and _cost_value(raw_usage["cost"]) is None:
        raise ProviderError("malformed response: usage.cost is %r, not a cost"
                            % (raw_usage["cost"],))
    usage["cost"] = charged_cost(payload, spec)
    return {
        "content": _shaped(message.get("content"), str, "message.content") or "",
        "tool_calls": calls,
        "finish_reason": _shaped(choice.get("finish_reason"), str,
                                 "choices[0].finish_reason") or "",
        "usage": usage,
        "served_by": _shaped(payload.get("provider"), str, "provider") or "",
    }


def empty_turn(turn):
    """True when a turn holds no answer: no visible content and no tool call.

    The one definition of an empty answer: ``retry_empty_turn`` re-sends one,
    and ``grade.turn_error`` reports one that is still empty after its retry as
    a run-level error.
    """
    return not (turn.get("content") or "").strip() and not turn.get("tool_calls")


def retry_empty_turn(provider, turn, spec, messages, tools=None, scope=None):
    """``(turn, retries)``: an empty ``turn`` re-sent once.

    The retry is a real call, so the budget reserves and charges it like any
    other. The discarded turn's usage is folded into the turn kept, so a record's
    cost and tokens still add up to what was spent. Whatever the retry returns
    is kept: still empty, it is the runner's run-level error.
    """
    if not empty_turn(turn):
        return turn, 0
    try:
        again = provider.complete(spec, messages, tools=tools, scope=scope)
    except Exception as exc:
        # The discarded empty turn was paid for; the error or the stop carries it on.
        raise carry_cost(exc, turn["usage"].get("cost", 0.0))
    usage = dict((key, value + turn["usage"].get(key, 0))
                 for key, value in again["usage"].items())
    return dict(again, usage=usage), 1


class OpenRouter:
    """The paid transport. Reads the key from the environment, never a file."""

    def __init__(self, budget, api_key=None, retries=4, backoff=5.0, timeout=180,
                 sleep=time.sleep, opener=None):
        self.key = api_key or os.environ.get(KEY_ENV, "")
        if not self.key:
            raise ProviderError("%s is not set" % KEY_ENV)
        self.budget = budget
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        self.sleep = sleep
        self.opener = opener or urllib.request.urlopen

    def complete(self, spec, messages, tools=None, scope=None):
        body = request_body(spec, messages, tools)
        reserved = self.budget.reserve(max_cost(spec, body), scope)
        try:
            payload = self._post(body)
        except AnswerLost as exc:
            # The request was sent whole and may be billed, but its answer was
            # lost: it is charged its reservation and never retried.
            self.budget.settle(reserved, reserved, scope)
            exc.cost += reserved
            raise
        except BaseException:
            # Refused or failed before any answer: nothing was billed.
            self.budget.settle(reserved, 0.0, scope)
            raise
        # The call is paid: it is charged before its body is read, so a body that
        # cannot be read is still on the cap and, through the error, on a record.
        cost = charged_cost(payload, spec)
        self.budget.settle(reserved, cost, scope)
        try:
            return normalise(payload, spec)
        except ProviderError as exc:
            exc.cost += cost
            raise

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
                    "X-Title": "crayon evals",
                },
            )
            # The open half: urllib sends the whole request, then waits here for the
            # status line and headers. Only a URLError is retried, because urllib
            # raises it when the connection or the send fails, so the provider never
            # held the whole request. Any other failure here comes after the whole
            # send and may be billed, so it is an AnswerLost: never retried.
            try:
                response = self.opener(request, timeout=self.timeout)
            except urllib.error.HTTPError as exc:
                last = "HTTP %d: %s" % (exc.code, _read_error(exc))
                if exc.code in RETRY_STATUSES:
                    continue
                raise ProviderError(last)
            except urllib.error.URLError as exc:
                last = "transport: %s" % exc
                continue
            except (OSError, http.client.HTTPException) as exc:
                raise AnswerLost("transport: the answer was lost after the request was sent"
                                 " (%s: %s)" % (type(exc).__name__, exc))
            # The read half: the call was answered, so a failure here lost an answer
            # that may be billed; it is never retried.
            try:
                with response:
                    raw = response.read()
            except (OSError, http.client.HTTPException) as exc:
                raise AnswerLost("transport: the answer was lost while it was read (%s: %s)"
                                 % (type(exc).__name__, exc))
            try:
                payload = json.loads(raw.decode("utf-8"))
            except ValueError as exc:
                raise ProviderError("response is not JSON: %s" % exc)
            error = payload.get("error") if isinstance(payload, dict) else None
            if error and not payload.get("choices"):
                # An error body of any shape is a ProviderError: a bare one is its
                # message, and only an integer code in the retry statuses is retried.
                if not isinstance(error, dict):
                    error = {"message": error}
                code = error.get("code")
                last = "API error %s: %s" % (code, error.get("message"))
                if (isinstance(code, int) and not isinstance(code, bool)
                        and code in RETRY_STATUSES):
                    continue
                raise ProviderError(last)
            return payload
        raise ProviderError("gave up after %d attempt(s): %s" % (self.retries + 1, last))


def _read_error(exc):
    try:
        return exc.read().decode("utf-8", "replace")[:300]
    except Exception:  # an unreadable error body still names its status
        return "(no body)"


def scripted(replies):
    """A stub responder that gives ``replies`` in order, then repeats the last."""
    replies = list(replies)
    state = {"next": 0}

    def respond(spec, messages, tools):
        reply = replies[min(state["next"], len(replies) - 1)]
        state["next"] += 1
        return reply

    return respond


class StubProvider:
    """The offline transport: every turn comes from ``responder``, cost zero.

    ``responder(spec, messages, tools)`` returns either a string (the content)
    or a partial turn dict (``content`` and/or ``tool_calls``). The gate's
    self-tests and ``run.py --dry-run`` use it, so neither needs the network.
    """

    #: Its turns are fixed by the test that wrote them, never chosen by a model,
    #: so lane B may run their commands on the host (``sandbox.HostRunner``).
    replays = True

    def __init__(self, responder=None):
        self.responder = responder or (lambda spec, messages, tools: "none")
        self.calls = []

    def complete(self, spec, messages, tools=None, scope=None):
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
            "served_by": "stub",
        }
