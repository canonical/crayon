"""promptfoo assertion: grade one case's trace with the case's own checks.

Dev-time evaluation material. The checks are ``grade.KINDS``, the same code the
offline self-tests hold every case's known-good and known-bad replies to, so
one rule has one grader. The trace comes from the provider's metadata
(``pf_provider.call_api``). A check that cannot be evaluated is reported with
the ``GRADE ERROR`` prefix, which ``run.py`` counts as a run-level error, never
as a failed case.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import grade  # noqa: E402
import lanes  # noqa: E402

GRADE_ERROR = "GRADE ERROR"


def get_assert(output, context):
    variables = context.get("vars") or {}
    case = lanes.case_by_id(variables["lane"], variables["case_id"])
    response = context.get("providerResponse") or {}
    trace = (response.get("metadata") or {}).get("trace")
    if trace is None:
        return {"pass": False, "score": 0.0,
                "reason": "%s: the provider returned no trace" % GRADE_ERROR}
    try:
        graded = grade.grade(case["assert"], trace)
    except grade.GradeError as exc:
        return {"pass": False, "score": 0.0, "reason": "%s: %s" % (GRADE_ERROR, exc)}
    failed = ["%s: %s" % (item["kind"], item["feedback"])
              for item in graded["results"] if not item["pass"]]
    return {
        "pass": graded["passed"],
        "score": graded["score"],
        "reason": "; ".join(failed) or "every check passed",
        "componentResults": [
            {"pass": item["pass"], "score": item["score"],
             "reason": "%s: %s" % (item["kind"], item["feedback"])}
            for item in graded["results"]
        ],
    }
