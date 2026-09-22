#!/usr/bin/env python3
"""ENV0 DEMO — SUBMIT THE THREE ANSWERS TO THE SCORER.

    export SCOREKEY_TOKEN=<your token>
    python submit_demo.py --answers runs/<name> --url https://scorekey-env0.fly.dev

For each of T3, T4 and full-chain-from-T1, in that order: reads <answers>/<task>.json, CHECKS it,
POSTs it to <url>/score/<task> with the token in the X-ENV0-Key header, prints the response as it
comes back, and saves it beside the answer as <task>.response.json.

★THE CHECK COMES FIRST, BECAUSE EVERY SUBMISSION SPENDS ONE OF FIVE. The scorer counts every
submission it takes, scored or rejected, against the token's cap of five per task. So a file that
is not one JSON object with a "commitments" list -- empty, text, truncated, a turn-cap run with no
answer -- is refused HERE and never sent.

Exit status: 0 all sent and answered; 1 one or more answers refused before sending, or a
transport error; 3 HTTP 401 (unknown token: stops at once, nothing further is sent).
Standard library only. The token is read from SCOREKEY_TOKEN and from nowhere else; it is never
written or printed.
"""
import argparse, json, os, sys, urllib.error, urllib.request
from pathlib import Path

TASKS = ["T3", "T4", "full-chain-from-T1"]
TOKEN_ENV = "SCOREKEY_TOKEN"


def check(path):
    """-> (body_bytes, None) if the file may be sent, else (None, reason)."""
    if not path.is_file():
        return None, "no such file"
    raw = path.read_bytes()
    if not raw.strip():
        return None, "the file is empty (the run produced no answer for this paper)"
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        return None, "not JSON (%s)" % str(e)[:120]
    if not isinstance(obj, dict):
        return None, "the JSON is a %s, not one object" % type(obj).__name__
    if not isinstance(obj.get("commitments"), list):
        return None, 'the object has no "commitments" list'
    return raw, None


def main():
    ap = argparse.ArgumentParser(description="Submit the three ENV0 demo answers to the scorer.")
    ap.add_argument("--answers", required=True, help="the --out directory of run_demo.py")
    ap.add_argument("--url", required=True, help="the scorer, e.g. https://scorekey-env0.fly.dev")
    A = ap.parse_args()
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        raise SystemExit("★REFUSED: %s is not set. The scorer token is read from that environment "
                         "variable and from nowhere else." % TOKEN_ENV)
    base = A.url.rstrip("/")
    d = Path(A.answers)
    status = 0
    for task in TASKS:
        f = d / ("%s.json" % task)
        body, why = check(f)
        if body is None:
            print("%-19s NOT SENT — %s: %s" % (task, f, why), flush=True)
            status = 1
            continue
        req = urllib.request.Request(base + "/score/" + task, data=body, method="POST",
                                     headers={"X-ENV0-Key": token,
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                code, text = r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            code, text = e.code, e.read().decode("utf-8", "replace")
        except Exception as e:
            print("%-19s TRANSPORT ERROR — %s: %s" % (task, type(e).__name__, e), flush=True)
            status = 1
            continue
        print("%-19s HTTP %d  %s" % (task, code, text.strip()), flush=True)
        (d / ("%s.response.json" % task)).write_text(text, encoding="utf-8")
        if code == 401:
            print("★the scorer does not know this token; nothing further is sent", flush=True)
            sys.exit(3)
        if code != 200:
            status = 1
    sys.exit(status)


if __name__ == "__main__":
    main()
