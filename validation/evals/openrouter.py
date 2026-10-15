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

- ``Budget``: checked before every paid call, and charged only where
  ``complete`` charges a call. A body ``_post`` returns is charged
  ``charged_cost`` before ``normalise`` reads its shape, so a JSON body the kit
  cannot read as a turn is still spend on the cap and, through its
  ``ProviderError``, on a record (24-33, WR-19 of the review at 802e0e3). A
  call whose answer is lost after its request was sent whole, before its status
  line or while its body is read, is charged ``lost_answer_cost``, an estimate,
  on the cap and on its ``AnswerLost`` (24-36, WR-24 and WR-25 of the review at
  5fdfe1b; 24-38, CR-13 of the review at fe0d6a0). Three answered arms are
  charged nothing, each a ``ProviderError`` with ``cost`` 0.0 or a retry: a
  non-2xx status (``HTTPError``), a 2xx body that is not JSON, and an API error
  body (``error`` with no ``choices``). A 2xx body nested too deeply for
  ``json.loads`` is charged nothing either: it leaves ``_post`` as a
  ``RecursionError`` (IN-22 of the review at fe0d6a0). A run that reaches its
  cap stops with ``BudgetExceeded``. With ``N`` calls in flight, what the cap
  is charged overshoots it by at most the ``N - 1`` calls already sent when the
  cap was crossed, so the cap is set with that headroom in mind; the uncharged
  arms are outside that bound. A stop that comes mid-case carries the cost of
  the case's calls already paid (``BudgetExceeded.cost``), so the case's record
  keeps it.
- The cache: keyed on the exact request body, so any change to the skill text,
  the case, the tools or the model parameters is a miss. Lanes that act on a
  real sandbox pass ``cache=False``. An empty turn is never written to it
  (``empty_turn``), so no later run can replay one. An unparsable judge reply
  is dropped from it (``OpenRouter.forget``) and the retried reply that is
  graded is kept (``OpenRouter.remember``), so a cached verdict is always one
  that was graded. A cache entry that cannot be written or dropped is a
  ``ProviderError``, so the runner records the case as a run-level error
  rather than stopping the sweep. An entry is written whole or not at all (a
  temporary file, then ``os.replace``). An entry that is not a whole turn
  (string ``content``, a list of ``tool_calls`` objects with string ``id``,
  ``name`` and ``arguments``, a ``usage`` with numeric token counts), or that
  holds an empty one, is a miss: the call is made and its turn replaces the
  entry, so a bad entry costs one call, not the sweep (24-27, WR-12). So is one
  whose ``served_by`` or ``finish_reason`` is not a string (24-30, WR-14 of the
  review at 1ba4892), or whose token count is not an integer below the cap that
  ``normalise`` also reads (24-33, WR-20 of the review at 802e0e3). A paid call
  whose entry cannot be written raises with its cost (``ProviderError.cost``),
  so the record still counts what was spent.
- Retries: each with backoff, on a retry status (``RETRY_STATUSES``), whether
  it comes as an ``HTTPError`` or in an API error body, and on a ``URLError``
  from the opener, which urllib raises when the connection or the send fails,
  before the request is sent whole. Any other failure from the opener, and any
  failure while an answer is read, comes after the request was sent whole: the
  provider holds it and may run and bill it, so it is an ``AnswerLost`` charged
  ``lost_answer_cost`` and never retried, because a retry could bill the call
  again with nothing charged. So a timeout or a reset after the whole send ends
  its case as a run-level error (24-36, WR-24 and WR-25 of the review at
  5fdfe1b; 24-38, CR-13 of the review at fe0d6a0). Every other failure is a
  ``ProviderError`` the runner reports as a run-level error, never as a failed
  case.
"""

import hashlib
import http.client
import json
import math
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_ENV = "OPENROUTER_API_KEY"
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}


class ProviderError(Exception):
    """A call that could not produce a turn: a run-level error, not a failure.

    ``cost`` is money spent on calls whose turns reach no record because of this
    error, 0.0 unless a paid call came before it (24-23, WR-02): ``complete``
    sets it when a paid turn's cache entry cannot be written, and each caller
    that holds paid turns adds theirs before it lets the error go on, so a
    record's cost still adds up to what was spent (D-24). An ``AnswerLost``
    carries the estimate ``complete`` charged for an answer lost after its request
    was sent whole (24-36, WR-24 and WR-25 of the review at 5fdfe1b; 24-38, CR-13
    of the review at fe0d6a0).
    """

    cost = 0.0


class AnswerLost(ProviderError):
    """A call whose request was sent whole and whose answer was lost.

    No status line came back, or the body was lost while it was read. The provider
    held the whole request, so the call may have run and be billed: ``complete``
    charges it ``lost_answer_cost``, an estimate, on the cap and on this error, and
    it is never retried, because a retry could bill it again with nothing charged
    (24-36: WR-24 and WR-25 of the review at 5fdfe1b; 24-38: CR-13 of the review at
    fe0d6a0).
    """


class BudgetExceeded(Exception):
    """The run's spend cap is reached; nothing further may be called.

    ``cost`` is money spent on calls whose turns reach no record because the stop
    came mid-case, 0.0 unless a paid call in the same case came before it (24-27,
    WR-11 of the review at aac605a). Each caller that holds paid turns adds theirs
    before it lets the stop go on, as for ``ProviderError.cost``, so the runner
    records a case that ran as stopped with what it paid.
    """

    cost = 0.0


def carry_cost(exc, cost):
    """``exc`` carrying ``cost``: the one place an escaping exception picks up the
    cost its caller holds, so a record's cost adds up to what was spent (D-24;
    24-36: WR-24 of the review at 5fdfe1b).

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


def lost_answer_cost(spec, body):
    """The estimate charged for a call whose answer was lost after its request was sent whole.

    The request's UTF-8 byte count as prompt tokens and its ``max_tokens`` as
    completion tokens, at the roster's price (``estimate_cost``). It is meant to
    overstate the call, the safe direction for a cap: a byte-level tokenizer makes
    no more tokens than bytes, and the completion is capped at ``max_tokens``
    (24-36: WR-25 of the review at 5fdfe1b; 24-38: CR-13 of the review at fe0d6a0).
    """
    return estimate_cost(spec, {"prompt_tokens": len(json.dumps(body).encode("utf-8")),
                                "completion_tokens": body.get("max_tokens", 0)})


#: A readable token count is an ``int`` below this (24-33, WR-20 of the review at
#: 802e0e3): no real call reports a quadrillion tokens, and a count this large
#: in a cache entry or a body is a sign it is not one the provider sent.
_TOKEN_CAP = 10 ** 15


def _token_count(value):
    """``value`` when it reads as a token count, else None: the one definition.

    An ``int`` that is not a ``bool`` and lies in ``[0, _TOKEN_CAP)``. ``normalise``,
    ``charged_cost`` and the cache read (``OpenRouter._cached``) all use it, so a
    count the transport refuses is one the cache misses (24-33, WR-20 of the
    review at 802e0e3).
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
    read is still spend on the cap and on a record (24-33, WR-19 of the review at
    802e0e3). The charge is the body's ``usage.cost`` when that reads as a cost,
    else ``estimate_cost`` over the token counts that read as counts (one that
    does not counts 0), which is 0.0 for a model with no listed price.
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
    ``ProviderError`` starting ``malformed response`` (24-33, WR-18 and WR-19 of
    the review at 802e0e3): the body and each choice objects, ``choices`` a
    non-empty list; ``message``, a call's ``function`` and ``usage`` objects;
    ``content``, ``finish_reason``, ``provider`` and a call's ``id``, ``name`` and
    ``arguments`` strings; ``tool_calls`` a list of objects; each token count read
    by ``_token_count`` and ``cost`` by ``_cost_value``. A null takes its default.
    So nothing past the transport meets a shape it cannot read, and the error
    reaches the runner as the case's run-level error, after ``complete`` charged
    the call.
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
        "cached": False,
        "served_by": _shaped(payload.get("provider"), str, "provider") or "",
    }


def empty_turn(turn):
    """True when a turn holds no answer: no visible content and no tool call.

    The one definition of an empty answer (D-24). The cache will not keep one,
    ``retry_empty_turn`` re-sends one, and ``grade.turn_error`` reports one that
    is still empty after its retry as a run-level error.
    """
    return not (turn.get("content") or "").strip() and not turn.get("tool_calls")


def retry_empty_turn(provider, turn, spec, messages, tools=None, scope=None):
    """``(turn, retries)``: an empty ``turn`` re-sent once, uncached (D-24).

    The retry is a real call, so the budget checks and charges it like any
    other; it passes ``cache=False``, so it can never be answered from the
    cache. The discarded turn's usage is folded into the turn kept, so a
    record's cost and tokens still add up to what was spent. Whatever the
    retry returns is kept: still empty, it is the runner's run-level error.
    """
    if not empty_turn(turn):
        return turn, 0
    try:
        again = provider.complete(spec, messages, tools=tools, cache=False, scope=scope)
    except Exception as exc:
        # The discarded empty turn was paid for; the error or the stop carries it
        # on (24-27, WR-11), and any other exception becomes a ProviderError that
        # does (24-36, WR-24 of the review at 5fdfe1b).
        raise carry_cost(exc, turn["usage"].get("cost", 0.0))
    usage = dict((key, value + turn["usage"].get(key, 0))
                 for key, value in again["usage"].items())
    return dict(again, usage=usage), 1


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
            hit = self._cached(self.cache_dir / ("%s.json" % key))
            if hit is not None:
                return hit
        self.budget.check(scope)
        try:
            payload = self._post(body)
        except AnswerLost as exc:
            # The request was sent whole and the call may be billed, but its answer
            # was lost: it is charged an estimate on the cap and on the error, and
            # never retried (24-36, WR-24 and WR-25 of the review at 5fdfe1b; 24-38,
            # CR-13 of the review at fe0d6a0).
            cost = lost_answer_cost(spec, body)
            self.budget.charge(cost, scope)
            exc.cost += cost
            raise
        # The call is paid: it is charged before its body is read, so a body that
        # cannot be read is still on the cap and, through the error, on a record
        # (24-33, WR-19 of the review at 802e0e3).
        cost = charged_cost(payload, spec)
        self.budget.charge(cost, scope)
        try:
            turn = normalise(payload, spec)
        except ProviderError as exc:
            exc.cost += cost
            raise
        if cache:
            try:
                self.remember(spec, messages, turn, tools=tools)
            except ProviderError as exc:
                # The call is paid and its turn is lost with the error (24-23, WR-02).
                exc.cost += turn["usage"]["cost"]
                raise
        return turn

    @staticmethod
    def _cached(path):
        """The turn cached at ``path``, served free, or None for a miss.

        An entry that cannot be read or is not JSON is a miss (24-23, WR-02), and
        so is one that is not a whole turn (24-27, WR-12 of the review at aac605a):
        an object with a string ``content``, a list ``tool_calls`` whose items are
        objects with string ``id``, ``name`` and ``arguments``, and a ``usage``
        object with ``prompt_tokens`` and ``completion_tokens``, the fields the
        runner, the agent loop and the grader read. Those token counts are integers
        below the cap, read by ``_token_count`` as ``normalise`` reads them (24-33,
        WR-20 of the review at 802e0e3), and ``served_by`` and ``finish_reason``,
        where present, are strings (24-30, WR-14 of the review at 1ba4892): the
        runner sorts the one and sums the other into a summary written as strict
        JSON. An entry holding an empty
        turn (``empty_turn``) is a miss as well, so it is replaced by the first
        answer rather than re-paid as a D-24 retry on every run. On a miss the
        call is made and its turn replaces the entry, so a half-written entry
        costs one call, not the sweep.
        """
        try:
            if not path.is_file():
                return None
            turn = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(turn, dict) or not isinstance(turn.get("content"), str):
            return None
        calls, usage = turn.get("tool_calls"), turn.get("usage")
        if not isinstance(calls, list) or not all(
                isinstance(call, dict)
                and all(isinstance(call.get(key), str) for key in ("id", "name", "arguments"))
                for call in calls):
            return None
        # 24-33, WR-20 (802e0e3): a token count is read as ``normalise`` reads it, an
        # integer below the cap, so a huge, fractional, NaN, Infinity or negative
        # count is a miss, never an ``OverflowError`` on every run.
        if not isinstance(usage, dict) or not all(
                _token_count(usage.get(key)) is not None
                for key in ("prompt_tokens", "completion_tokens")):
            return None
        # 24-30, WR-14 (1ba4892): the runner sets and sorts ``served_by`` and sums
        # the token counts into a summary written as JSON, so a non-string label is
        # a miss, not a sweep crash.
        if not all(isinstance(turn.get(key, ""), str) for key in ("served_by", "finish_reason")):
            return None
        if empty_turn(turn):
            return None
        turn["cached"] = True
        turn["usage"]["cost"] = 0.0
        return turn

    def _cache_path(self, spec, messages, tools=None):
        """The cache entry for this request: the cache dir joined with its key."""
        return self.cache_dir / ("%s.json" % cache_key(request_body(spec, messages, tools)))

    def forget(self, spec, messages, tools=None):
        """Drop the cached turn for this request, if there is one.

        An entry that cannot be dropped is a ``ProviderError`` (24-20, IN-03), so
        the runner records the case as a run-level error and the sweep goes on.
        """
        if self.cache_dir is not None:
            try:
                self._cache_path(spec, messages, tools).unlink(missing_ok=True)
            except OSError as exc:
                raise ProviderError("cache: %s" % exc)

    def remember(self, spec, messages, turn, tools=None):
        """Cache ``turn`` for this request: the cache's one write site.

        An empty turn is never written (``empty_turn``), so no run replays one.
        An entry that cannot be written is a ``ProviderError`` (24-20, IN-03), so
        the runner records the case as a run-level error and the sweep goes on.
        The entry is written whole or not at all (24-23, WR-02): to a temporary
        file beside it, named for this process and thread and never ``*.json``,
        then moved into place; a failed write removes the temporary file.
        """
        if self.cache_dir is None or empty_turn(turn):
            return
        path = self._cache_path(spec, messages, tools)
        tmp = path.with_name("%s.%d.%d.tmp" % (path.stem, os.getpid(), threading.get_ident()))
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(turn, sort_keys=True), encoding="utf-8")
            os.replace(str(tmp), str(path))
        except OSError as exc:
            try:
                tmp.unlink()
            except OSError:
                pass  # never written, or already gone; the first error is the one
            raise ProviderError("cache: %s" % exc)

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
            # held the whole request (24-36, WR-24). Any other failure here comes
            # after the whole send and may be billed, so it is an AnswerLost: never
            # retried, and charged by ``complete`` (24-38, CR-13 of the review at
            # fe0d6a0).
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
            # that may be billed; it is never retried (24-36, WR-25 of the review at
            # 5fdfe1b), and ``complete`` charges it.
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
                # An error body of any shape is a ProviderError (24-36, WR-24 of the
                # review at 5fdfe1b): a bare one is its message, and only an integer
                # code in the retry statuses is retried.
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


class StubProvider:
    """The offline transport: every turn comes from ``responder``, cost zero.

    ``responder(spec, messages, tools)`` returns either a string (the content)
    or a partial turn dict (``content`` and/or ``tool_calls``). The gate's
    self-tests and ``run.py --dry-run`` use it, so neither needs the network.
    """

    #: Its turns are fixed by the test that wrote them, never chosen by a model,
    #: so lane B may run their commands without a jail (``lanes.run_b``).
    replays = True

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
