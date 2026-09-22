#!/usr/bin/env python3
"""ENV0 DEMO — THE REFERENCE RUNNER. Runs a model on the three demo papers exactly as the campaign did.

    python run_demo.py --packet . --model <name> --out runs/<name> [--transport chat|responses|anthropic]

WHAT THIS IS. The ENV0 campaign harness (`run_env0_campaign.py`, md5 da47a0e373b9494233aa4f28ab9ac8fa),
cut down to the three papers in this packet and to the packet alone. What it keeps, unchanged:

  * the SYSTEM message and the menu introduction, byte for byte;
  * the four tools and the tool loop, a fenced region re-hashed at start-up and refused unless it is
    39504313a53c61b7a559002738ea9303 -- the same region, and the same hash, as the campaign's;
  * one conversation per paper: [system, user = the paper, user = the menu], then the tool loop;
  * tool results truncated to 24000 characters; the turn cap (default 120, the campaign's setting);
  * `run_python` executed by `sandbox_exec_env1.py` (md5 7802cb28466280e9a84a8e651b6d88cd, vendored
    unchanged, asserted at start-up): a mount and PID namespace, chrooted, holding only this paper's
    sandbox and the runtime;
  * retries on TRANSPORT errors only (HTTP 408/409/429/5xx, socket errors); no prompt is ever
    adjusted; no sampling or reasoning parameter is sent;
  * the campaign's 4xx rule, on every transport: a conversation the provider refuses with an HTTP
    4xx is re-run ONCE as a fresh conversation in a fresh sandbox; the first attempt is kept as
    <paper>__attempt1; a second 4xx stands as no submission.

TRANSPORT. `--transport chat` (default) speaks /v1/chat/completions. `--transport responses` speaks
/v1/responses through the campaign's adapter, ported unchanged in behaviour: the model's own prior
output items (reasoning included) are carried forward and each tool result goes back as a
function_call_output. `--transport anthropic` speaks the Anthropic Messages API through the adapter
claude-fable-5-1's campaign rows were produced with, ported unchanged in behaviour: top-level
system prompt, tools as {name, description, input_schema}, tool results as tool_result blocks, the
model's own content blocks replayed verbatim, max_tokens at the model's documented maximum, prompt
caching on; a timed-out call stops rather than retries, and an empty assistant turn is re-requested
once, identically. `--transport chat` also re-requests an empty turn once, as gemini-3.8-flash's
harness did; `--transport responses` does neither, as the gpt harnesses did. The gpt-5.6 models refuse function tools on chat completions, and the campaign
ran them over responses; README.md lists which transport each model ran on.

WHAT IT REFUSES, rather than degrading:
  * a Linux host without mount namespaces (the runner must be able to isolate);
  * a missing SCOREKEY_MODEL_KEY (the API key comes from that environment variable and nowhere else;
    it is held in memory, sent in the request's auth header, and never written or logged);
  * a claude- model on a non-anthropic transport, or the reverse (as the campaign refused);
  * a packet whose MD5SUMS.txt does not check, or an MD5SUMS.txt that is not the one shipped;
  * a sandbox holding anything other than exactly one paper, and that paper this conversation's.

WHAT IT WRITES
  <out>/T3.json, T4.json, full-chain-from-T1.json   the submit_answer body of each paper, exactly
  <out>/RUN.json                                    model, endpoint host, transport, the three md5s,
                                                    turns, finished_by and token usage per paper
  <out>/raw/<task>/turn_NN.json, <out>/transcripts/<task>.jsonl   every response body and the turn log
"""
import argparse, copy, datetime, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
import urllib.request, urllib.error, urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True

#: the three papers of the demo packet, in campaign order, and nothing else
TASKS = ["T3", "T4", "full-chain-from-T1"]
CHAIN = ["full-chain-from-T1"]


def is_chain(station):
    return station in CHAIN


def bundle_name(station):
    """The bundle directory this conversation is delivered from."""
    return ("bundle_chain_%s" % station) if is_chain(station) else ("bundle_%s" % station)


def paper_name(station):
    """The paper file inside that bundle."""
    return ("chain_%s.md" % station) if is_chain(station) else ("prompt_env0_%s.md" % station)


API_CHAT = "https://api.openai.com/v1/chat/completions"
API_RESPONSES = "https://api.openai.com/v1/responses"
API_ANTHROPIC = "https://api.anthropic.com/v1/messages"
KEY_ENV = "SCOREKEY_MODEL_KEY"

ENV1_LOOP_MD5 = "39504313a53c61b7a559002738ea9303"
ISO_RUNNER_MD5 = "7802cb28466280e9a84a8e651b6d88cd"
CAMPAIGN_HARNESS_MD5 = "da47a0e373b9494233aa4f28ab9ac8fa"
#: the packet's own manifest, as shipped with demo packet build 3
PACKET_MANIFEST_MD5 = "7cff531e5873643c67280f6a6a227763"
PACKET_FILES = 64

SYSTEM = ("You are a data analyst staffed on a client module. Your working folder is the "
          "current directory. Read the files you need, write and run Python to compute "
          "figures, and finish by calling submit_answer exactly once with the JSON object "
          "for this task.")

MENU_INTRO = "The published menu referred to in the instructions, menu_env0.json, in full:"


def md5f(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


#: ★THE ISOLATED RUNNER IS CHECKED BEFORE IT IS IMPORTED: the tool loop below imports it, and an
#: import runs code. Absent or altered, nothing runs.
_ISO = HERE / "sandbox_exec_env1.py"
if not _ISO.is_file():
    raise SystemExit("★REFUSED: sandbox_exec_env1.py is not beside run_demo.py. It is the isolated "
                     "runner; without it no candidate code may run.")
if md5f(_ISO) != ISO_RUNNER_MD5:
    raise SystemExit("★REFUSED: sandbox_exec_env1.py has md5 %s, not %s. It is vendored unchanged "
                     "from the campaign; do not edit it." % (md5f(_ISO), ISO_RUNNER_MD5))


# ══════════════════════════════════ ENV1 LOOP BEGIN ══════════════════════════════════
TOOLS = [
 {"type": "function", "function": {
   "name": "list_dir", "description": "List a directory inside your working folder.",
   "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
 {"type": "function", "function": {
   "name": "read_file",
   "description": "Read a UTF-8 text file inside your working folder. Returns at most 400 lines "
                  "from `offset`. Use run_python for gzipped or very large files.",
   "parameters": {"type": "object", "properties": {
     "path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}},
     "required": ["path"]}}},
 {"type": "function", "function": {
   "name": "run_python",
   "description": "Run Python 3 in your working folder and return stdout and stderr. The standard "
                  "library is available, including gzip, csv and json. 120 s limit.",
   "parameters": {"type": "object", "properties": {"code": {"type": "string"}},
                  "required": ["code"]}}},
 {"type": "function", "function": {
   "name": "submit_answer",
   "description": "Submit your final answer for this task and finish. Pass the JSON object as a "
                  "string, in the shape the task's answer template shows.",
   "parameters": {"type": "object", "properties": {"answer_json": {"type": "string"}},
                  "required": ["answer_json"]}}},
]

# ★★★v2.3: THE VENDORED REGION IS NOW ITS OWN FILE, `sandbox_exec_env1.py`, AND IT IS NOT A LIST
# OF BLOCKED CALLS ANY MORE. Three rounds patched an audit hook here and three independent
# re-audits re-broke it - `/proc`, directory listing, an undeleted sandbox, and finally a hardlink
# of the key file into the agent's own folder that read all 35 of t8's keys from a live t1
# conversation. Enumerating dangerous calls against an agent that runs arbitrary code is
# unwinnable, so isolation moved down a layer: the agent's execution environment now CONTAINS only
# its own sandbox and the public data. ★ENV0 vendors the same file.
from sandbox_exec_env1 import run_code as _run_code, region_hash as _region_hash, \
    PROVENANCE as VENDORED_PROVENANCE, namespaces_available as _ns_available

VENDORED_REGION = _region_hash()


def safe(root: Path, p: str):
    q = (root / p).resolve() if not os.path.isabs(p) else Path(p).resolve()
    try: q.relative_to(root.resolve())
    except ValueError: return None
    return q

def tool_call(root: Path, name, args):
    try:
        if name == "list_dir":
            q = safe(root, args.get("path", "."))
            if q is None or not q.exists(): return "no such directory inside your working folder"
            out = []
            for c in sorted(q.iterdir()):
                out.append(("%-44s %s" % (c.name + ("/" if c.is_dir() else ""),
                                          "" if c.is_dir() else "%d B" % c.stat().st_size)))
            return "\n".join(out) or "(empty)"
        if name == "read_file":
            q = safe(root, args.get("path", ""))
            if q is None or not q.is_file(): return "no such file inside your working folder"
            off = int(args.get("offset") or 0); lim = min(int(args.get("limit") or 400), 400)
            try: lines = q.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception as e: return "cannot read as text (%s) - use run_python" % type(e).__name__
            body = "\n".join(lines[off:off + lim])
            return body + ("\n... (%d more lines)" % (len(lines) - off - lim)
                           if len(lines) > off + lim else "")
        if name == "run_python":
            # ★the whole of the isolation lives in the vendored runner. Nothing here decides what
            # a candidate may touch, because deciding that was the losing game.
            return _run_code(root, args.get("code") or "", timeout=120)
    except subprocess.TimeoutExpired:
        return "timed out after 120 s"
    except Exception as e:
        return "%s: %s" % (type(e).__name__, e)
    return "unknown tool"
# ══════════════════════════════════ ENV1 LOOP END ══════════════════════════════════


def loop_provenance():
    """Re-hash the fenced region of THIS file. -> (md5, ok). A drift is campaign-blocking."""
    src = Path(__file__).read_text(encoding="utf-8")
    b = src.index("# " + "\u2550" * 34 + " ENV1 LOOP BEGIN")
    b = src.index("\n", b) + 1
    e = src.index("# " + "\u2550" * 34 + " ENV1 LOOP END")
    region = src[b:e]
    h = hashlib.md5(region.encode("utf-8")).hexdigest()
    return h, h == ENV1_LOOP_MD5


# ── the key guard: nothing that carries the live key leaves this process ─────────────────────
#: Ported from the campaign transport of record for claude-fable-5-1 (run_campaign_env0_v1.py
#: 76312bf5: HC-013 with its build-17 repair), unchanged in behaviour, on every transport. Every
#: outgoing request body is walked BEFORE it is sent. Fatal: the live key, or a 12-character run of
#: its SECRET part (taken after the vendor's public prefix, so `sk-ant-api03` alone can never kill a
#: conversation), an Authorization field, or a key-shaped string. Recorded, not fatal: a shape hit
#: inside the provider's own opaque `encrypted_content`, and a public vendor prefix on its own.
_KEY_RX = [
    ("google_aiza",   re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("google_aq",     re.compile(r"(?<![A-Za-z0-9])AQ\.[A-Za-z0-9_\-]{20,}")),
    ("anthropic_sk",  re.compile(r"(?<![A-Za-z0-9])sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai_sk",     re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{20,}")),
    ("bearer_header", re.compile(r"(?i)authorization\"?\s*[:=]\s*\"?bearer\s")),
]
PUBLIC_KEY_PREFIXES = (
    "sk-ant-api03-", "sk-ant-api-", "sk-ant-",
    "sk-proj-", "sk-svcacct-", "sk-None-", "sk-",
    "AIzaSy", "AIza", "AQ.",
)
_PUBLIC_PREFIXES_LONGEST_FIRST = tuple(sorted(PUBLIC_KEY_PREFIXES, key=len, reverse=True))
MIN_SECRET_FOR_PARTIAL_PROBES = 24


def _secret_key_part(live_key):
    """-> (secret, public_prefix_removed). The remainder is never printed anywhere."""
    k = (live_key or "").strip()
    for pre in _PUBLIC_PREFIXES_LONGEST_FIRST:
        if k.startswith(pre):
            return k[len(pre):], pre
    return k, ""


def key_probe_profile(live_key):
    """What the live-key test actually checks, in words, for RUN.json. No secret material."""
    sec, pre = _secret_key_part(live_key or "")
    partial = len(sec) >= MIN_SECRET_FOR_PARTIAL_PROBES
    return {"public_prefix_removed": pre or None,
            "key_length": len(live_key or "") or None,
            "secret_length_after_prefix": len(sec) or None,
            "probes": (["whole key"] + (["first 12 of the secret", "last 12 of the secret"]
                                        if partial else [])),
            "partial_probes_taken": partial}


def key_shaped(obj, live_key):
    """Walk the object about to leave this process. Returns (hits, noted)."""
    hits, noted = [], []
    OPAQUE = ("encrypted_content",)

    def walk(o, path="", opaque=False):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(k, str) and "authorization" in k.lower():
                    hits.append(("an Authorization field", path + "." + k))
                walk(v, path + "." + str(k), opaque or (k in OPAQUE))
        elif isinstance(o, (list, tuple)):
            for i, v in enumerate(o):
                walk(v, "%s[%d]" % (path, i), opaque)
        elif isinstance(o, str):
            for name, rx in _KEY_RX:
                if rx.search(o):
                    (noted if opaque else hits).append(("a %s-shaped string" % name, path or "."))
            for _pre in _PUBLIC_PREFIXES_LONGEST_FIRST:
                if len(_pre) >= 6 and _pre.rstrip("-") in o:
                    noted.append(("a PUBLIC vendor key prefix (%s) and nothing secret with it"
                                  % _pre.rstrip("-"), path or "."))
                    break
            if live_key:
                _sec, _pre_used = _secret_key_part(live_key)
                _probes = [(live_key, "THE LIVE KEY")]
                if len(_sec) >= MIN_SECRET_FOR_PARTIAL_PROBES:
                    _probes.append((_sec[:12], "the live key's first 12 SECRET characters"))
                    _probes.append((_sec[-12:], "the live key's last 12 SECRET characters"))
                for probe, label in _probes:
                    if len(probe) >= 8 and probe in o:
                        hits.append((label, path or "."))          # never exempt
    walk(obj)
    return hits, noted


def refuse_if_key_shaped(obj, live_key, what, meta=None):
    hits, noted = key_shaped(obj, live_key)
    _pub = [h for h in noted if h[0].startswith("a PUBLIC vendor key prefix")]
    _opq = [h for h in noted if not h[0].startswith("a PUBLIC vendor key prefix")]
    if meta is not None:
        if "key_probe_profile" not in meta:
            meta["key_probe_profile"] = key_probe_profile(live_key)
        if _pub:
            seenp = meta.setdefault("public_key_prefix_seen", [])
            for h in _pub:
                if h[1] not in [x["where"] for x in seenp]:
                    seenp.append({"what": h[0], "where": h[1],
                                  "ruling": "a public vendor prefix on its own is recorded, "
                                            "never fatal"})
        if _opq:
            seen = meta.setdefault("key_shape_noted_in_opaque", [])
            for h in _opq:
                if h[1] not in [x["where"] for x in seen]:
                    seen.append({"what": h[0], "where": h[1],
                                 "ruling": "inside the provider's own encrypted_content: SHAPE "
                                           "hit recorded, not refused. Equality against the live "
                                           "key was applied here too and did not fire."})
    real = [h for h in hits if h[0].startswith("THE LIVE KEY") or h[0].startswith("the live key")]
    if real:
        raise SystemExit(
            "★★KEY-SHAPED BODY REFUSED — %s. THE LIVE KEY, or a 12-character run of its SECRET "
            "material, IS IN THE OBJECT ABOUT TO LEAVE THIS PROCESS: %s. Nothing is sent and "
            "nothing is logged." % (what, "; ".join("%s at %s" % h for h in real)))
    if hits:
        raise SystemExit(
            "★★KEY-SHAPED BODY REFUSED — %s. A key-shaped string is in the object about to leave "
            "this process: %s. This is a stop, not proof of a leak: look at the named field."
            % (what, "; ".join("%s at %s" % h for h in hits)))


# ── the transports ───────────────────────────────────────────────────────────────────────────
#: responses: the campaign transport that produced the gpt-5.6 and gpt-6 rows
#:   (run_campaign_env0_v1.B7.py b2fd302b; astra's B8 819ab817 has the same rule) -- five
#:   attempts, backoff min(6*2^i, 60) s, on HTTP 408/409/429/5xx/529 and on socket errors; a
#:   daily-quota 429 is never retried.
#: chat: the same retry rule, plus one identical re-request of an empty assistant turn (HC-019),
#:   as gemini-3.8-flash's harness had it (build 10, 48a14949).
#: anthropic: the campaign transport that produced the claude-fable-5-1 rows
#:   (run_campaign_env0_v1.py 76312bf5) -- the same retry rule, except that a TIMED-OUT call is
#:   never retried (its build 16): it stops the conversation, because the provider may have
#:   served and billed it; and one identical re-request of an empty assistant turn (its HC-019).
HARD_QUOTA = "generate_requests_per_model_per_day"
REQUEST_TIMEOUT_S = 1800
RETRY_BUDGET_PER_CALL = 5
RETRYABLE_HTTP = (429, 500, 502, 503, 504, 408, 409, 529)
SAMPLING = ("DEFAULT - no temperature, top_p, seed, reasoning_effort, max_tokens or "
            "response_format is sent by this harness")

#: Anthropic REQUIRES max_tokens and has no unset. The campaign sent each model's DOCUMENTED
#: MAXIMUM, so that the cap is the same as no cap, and refused a model whose maximum it did not
#: hold. The same rule here: a Claude model not in this table is refused, never given a guess.
ANTHROPIC_MAX_OUTPUT = {
    "claude-fable-5-1": 128000,             # the campaign's own row, read 2026-09-19
    "claude-sonnet-4-6": 64000,
    "claude-haiku-4-5-20251001": 64000,
    "claude-opus-4-7": 128000,
    "claude-opus-4-6": 128000,
    "claude-sonnet-4-5-20250929": 64000,
    "claude-opus-4-5-20251101": 64000,
    "claude-opus-4-1-20250805": 32000,
}
ANTHROPIC_MAX_OUTPUT_SOURCE = (
    "claude-fable-5-1: platform.claude.com/docs/en/models/overview, read 2026-09-19 by the "
    "campaign ('Max output: 128K tokens'). Every other row: platform.claude.com/docs/en/about-"
    "claude/models/overview, read 2026-09-22 ('Max output' column; 128k read as 128000, 64k as "
    "64000, 32k as 32000).")


def anthropic_max_output(model):
    """The documented maximum for this id, or a refusal. Never a fallback, never a default."""
    v = ANTHROPIC_MAX_OUTPUT.get(model)
    if not v:
        raise SystemExit(
            "★REFUSED: %r has no documented max-output figure in run_demo.py. Anthropic requires "
            "max_tokens, and the campaign sent each model's documented maximum; starting would "
            "mean inventing a cap. Known: %s." % (model, ", ".join(sorted(ANTHROPIC_MAX_OUTPUT))))
    return int(v)


class TimeoutStop(RuntimeError):
    """anthropic transport: a call timed out. Never retried."""


def _is_timeout(e):
    if isinstance(e, TimeoutError):
        return True
    r = getattr(e, "reason", None)
    if isinstance(e, urllib.error.URLError) and isinstance(r, TimeoutError):
        return True
    return isinstance(e, OSError) and "timed out" in str(r if r is not None else e).lower()


def _backoff(i):
    return min(6 * (2 ** i), 60)


def _utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class Transport:
    """Speaks chat-completions to the tool loop whatever it speaks to the provider.

    The signature and the return shape are the harness's `post`: (parsed_body, retry_log).
    Ported from the campaign transports with their spend ledger, price table, tier accounting and
    request banking removed; the request each builds, the retries it makes and the translation
    it does are the campaign's."""

    ANTHROPIC_VERSION = "2023-06-01"
    CACHE_CONTROL = {"type": "ephemeral"}

    def __init__(self, url, key, mode, meta):
        self.url, self.key, self.mode, self.meta = url, key, mode, meta
        self.cache = (mode == "anthropic")
        self.reset()

    def reset(self):
        """one conversation per paper: nothing of one paper's output reaches the next"""
        self.prior = []              # responses: the model's own output items, in order
        self.anthropic_prior = []    # anthropic: the model's own content blocks, per response
        self._hc019_attempt = 0
        self._hc019_first_body = None

    def _raw(self, body, station, turn, retries):
        refuse_if_key_shaped(body, self.key, "the outgoing request body", self.meta)
        data = json.dumps(body).encode()
        for i in range(RETRY_BUDGET_PER_CALL):
            hdrs = ({"x-api-key": self.key, "anthropic-version": self.ANTHROPIC_VERSION,
                     "Content-Type": "application/json"} if self.mode == "anthropic"
                    else {"Authorization": "Bearer " + self.key,
                          "Content-Type": "application/json"})
            req = urllib.request.Request(self.url, data=data, headers=hdrs)
            t0 = time.time()
            try:
                return json.load(urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S))
            except urllib.error.HTTPError as e:
                msg = e.read().decode("utf-8", "replace")[:600]
                if e.code == 429 and HARD_QUOTA in msg:
                    raise RuntimeError("HTTP 429 DAILY QUOTA (never retried) %s" % msg)
                if e.code not in RETRYABLE_HTTP or i == RETRY_BUDGET_PER_CALL - 1:
                    self.meta["provider_event"] = {
                        "http": e.code, "message_verbatim": msg, "station": station,
                        "turn": turn, "utc": _utc()}
                    raise RuntimeError("HTTP %s %s" % (e.code, msg))
                retries.append({"station": station, "turn": turn, "attempt": i + 1,
                                "kind": "http",
                                "retry_class": "rate_limit_429" if e.code == 429 else "http_%d" % e.code,
                                "code": e.code, "sleep_s": _backoff(i),
                                "body_preview": msg[:200], "seconds": round(time.time() - t0, 1),
                                "action": "retry (transport)", "utc": _utc()})
                print("      retry %d after HTTP %s" % (i + 1, e.code), flush=True)
                time.sleep(_backoff(i))
            except Exception as e:
                if self.mode == "anthropic" and _is_timeout(e):
                    ev = {"station": station, "turn": turn, "retry_class": "timeout",
                          "action": "STOP (never retried)",
                          "error": "%s: %s" % (type(e).__name__, str(e)[:200]),
                          "request_timeout_s": REQUEST_TIMEOUT_S,
                          "seconds": round(time.time() - t0, 1), "utc": _utc()}
                    self.meta.setdefault("timeout_stops", []).append(ev)
                    self.meta["provider_event"] = {
                        "http": None, "status": "TIMEOUT_STOP",
                        "message_verbatim": ev["error"], "station": station, "turn": turn,
                        "utc": _utc()}
                    raise TimeoutStop("TIMEOUT STOP — %s turn %s timed out after %.0f s; not "
                                      "retried (the provider may have served and billed it)"
                                      % (station, turn, time.time() - t0))
                if i == RETRY_BUDGET_PER_CALL - 1:
                    self.meta["provider_event"] = {
                        "http": None, "message_verbatim": "%s: %s" % (type(e).__name__, str(e)[:400]),
                        "station": station, "turn": turn, "utc": _utc()}
                    raise
                retries.append({"station": station, "turn": turn, "attempt": i + 1,
                                "kind": "transport", "retry_class": "connection_error",
                                "sleep_s": _backoff(i),
                                "error": "%s: %s" % (type(e).__name__, str(e)[:200]),
                                "seconds": round(time.time() - t0, 1),
                                "action": "retry (transport)", "utc": _utc()})
                print("      retry %d after %s" % (i + 1, type(e).__name__), flush=True)
                time.sleep(_backoff(i))
        raise RuntimeError("attempts exhausted")

    # -- anthropic <-> chat: the campaign's adapter (76312bf5, its build 14) -------------------
    #   the system prompt is a top-level `system` field; tools are {name, description,
    #   input_schema}; a tool call is a `tool_use` block whose `input` is an object; a tool result
    #   goes back as a user message holding a `tool_result` block; max_tokens is required and is
    #   the documented maximum; the model's own prior content blocks (thinking blocks with their
    #   signatures included) are replayed verbatim, and checked against the turn they replace;
    #   prompt caching ON, 5-minute ephemeral TTL, three breakpoints (tools, system, latest user).
    def _to_anthropic(self, body):
        sys_txt, msgs = [], []
        asst_i = 0
        for m in body["messages"]:
            role, content = m.get("role"), m.get("content")
            if role == "system":
                sys_txt.append(content or ""); continue
            if role == "tool":
                msgs.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": m.get("tool_call_id"),
                     "content": str(content or "")}]})
                continue
            if role == "assistant":
                raw = (self.anthropic_prior[asst_i]
                       if asst_i < len(self.anthropic_prior) else None)
                asst_i += 1
                if raw is None:
                    raise SystemExit(
                        "★ASSISTANT TURN %d HAS NO STORED RESPONSE. Rebuilding it from the chat "
                        "shape would silently drop the model's reasoning. Refusing." % (asst_i - 1))
                want = [c.get("id") for c in (m.get("tool_calls") or [])]
                got = [b.get("id") for b in raw if b.get("type") == "tool_use"]
                if want != got:
                    raise SystemExit(
                        "★ASSISTANT TURN %d DOES NOT MATCH THE RESPONSE STORED FOR IT: tool_use "
                        "ids %r in the record against %r in the turn. Refusing."
                        % (asst_i - 1, got, want))
                msgs.append({"role": "assistant", "content": copy.deepcopy(raw)})
                continue
            msgs.append({"role": "user", "content": content or ""})
        sys_joined = "\n\n".join(x for x in sys_txt if x)
        tools = [{"name": x["function"]["name"],
                  "description": x["function"]["description"],
                  "input_schema": x["function"]["parameters"]} for x in body["tools"]]
        mx = anthropic_max_output(body["model"])
        self.meta["anthropic_max_tokens_sent"] = mx
        req = {"model": body["model"], "max_tokens": mx,
               "system": sys_joined, "messages": msgs,
               "tools": tools, "tool_choice": {"type": "auto"}}
        if self.cache:
            req = self._add_cache_control(req)
        #: no temperature, top_p, top_k, thinking block or effort is sent
        return req

    def _add_cache_control(self, req):
        r = json.loads(json.dumps(req))
        if r.get("tools"):
            r["tools"][-1]["cache_control"] = dict(self.CACHE_CONTROL)
        if isinstance(r.get("system"), str):
            r["system"] = [{"type": "text", "text": r["system"],
                            "cache_control": dict(self.CACHE_CONTROL)}]
        for m in reversed(r.get("messages") or []):
            if m.get("role") != "user":
                continue
            if isinstance(m.get("content"), str):
                m["content"] = [{"type": "text", "text": m["content"],
                                 "cache_control": dict(self.CACHE_CONTROL)}]
            elif isinstance(m.get("content"), list) and m["content"]:
                m["content"][-1]["cache_control"] = dict(self.CACHE_CONTROL)
            break
        return r

    def _anthropic_as_chat(self, raw):
        blocks = raw.get("content") or []
        self.anthropic_prior.append(copy.deepcopy(blocks))
        self.meta.setdefault("anthropic_block_types_received", []).append(
            [b.get("type") for b in blocks])
        text = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
        calls = [{"id": b.get("id"), "type": "function",
                  "function": {"name": b.get("name"),
                               "arguments": json.dumps(b.get("input") or {})}}
                 for b in blocks if b.get("type") == "tool_use"]
        u = raw.get("usage") or {}
        cw = u.get("cache_creation") or {}
        return {"id": raw.get("id"), "model": raw.get("model"),
                "choices": [{"index": 0,
                             "finish_reason": "tool_calls" if calls else "stop",
                             "message": {"role": "assistant", "content": text or None,
                                         **({"tool_calls": calls} if calls else {})}}],
                "stop_reason_anthropic": raw.get("stop_reason"),
                "usage": {"prompt_tokens": int(u.get("input_tokens") or 0),
                          "completion_tokens": int(u.get("output_tokens") or 0),
                          "prompt_tokens_details": {
                              "cached_tokens": int(u.get("cache_read_input_tokens") or 0)},
                          "cache_write_5m_tokens": int(cw.get("ephemeral_5m_input_tokens") or 0),
                          "cache_write_1h_tokens": int(cw.get("ephemeral_1h_input_tokens") or 0),
                          "cache_write_unattributed_tokens": (
                              0 if cw else int(u.get("cache_creation_input_tokens") or 0))}}

    # -- responses <-> chat: the campaign's adapter (b2fd302b) ----------------------------------
    def _to_input(self, messages):
        """[system,user,user] verbatim, then the model's OWN prior output items (reasoning
        included), then each tool result as a function_call_output."""
        items = [{"role": m["role"], "content": m["content"]}
                 for m in messages if m.get("role") in ("system", "user")]
        results = {m["tool_call_id"]: m["content"] for m in messages if m.get("role") == "tool"}
        for out_items in self.prior:
            items += out_items
            for o in out_items:
                if o.get("type") == "function_call" and o.get("call_id") in results:
                    items.append({"type": "function_call_output", "call_id": o["call_id"],
                                  "output": results[o["call_id"]]})
        return items

    def _as_chat(self, r):
        out = r.get("output") or []
        self.prior.append(out)
        calls = [{"id": o.get("call_id"), "type": "function",
                  "function": {"name": o.get("name"), "arguments": o.get("arguments") or "{}"}}
                 for o in out if o.get("type") == "function_call"]
        text = "".join(c.get("text") or "" for o in out if o.get("type") == "message"
                       for c in (o.get("content") or []) if c.get("type") == "output_text")
        u = r.get("usage") or {}
        return {"id": r.get("id"), "model": r.get("model"),
                "service_tier": r.get("service_tier"),
                "choices": [{"index": 0, "finish_reason": "tool_calls" if calls else "stop",
                             "message": {"role": "assistant", "content": text or None,
                                         **({"tool_calls": calls} if calls else {})}}],
                "usage": {"prompt_tokens": u.get("input_tokens"),
                          "completion_tokens": u.get("output_tokens"),
                          "total_tokens": u.get("total_tokens"),
                          "prompt_tokens_details": {
                              "cached_tokens": (u.get("input_tokens_details") or {}).get("cached_tokens")},
                          "completion_tokens_details": {
                              "reasoning_tokens": (u.get("output_tokens_details") or {}).get("reasoning_tokens")}}}

    @staticmethod
    def _empty_assistant_turn(r):
        m = ((r.get("choices") or [{}])[0] or {}).get("message") or {}
        return not (m.get("content") or "").strip() and not m.get("tool_calls")

    def post(self, key, url, body, station, turn, tries=5, _hc019_carry=None):
        """the signature the tool loop calls; `key` and `url` are ignored, ours are held here.
        Returns (parsed_body, retry_log) exactly as the harness's post does."""
        retries = list(_hc019_carry or [])
        if self.mode == "responses":
            req = {"model": body["model"], "input": self._to_input(body["messages"]),
                   "tools": [{"type": "function", "name": t["function"]["name"],
                              "description": t["function"]["description"],
                              "parameters": t["function"]["parameters"]} for t in body["tools"]],
                   "tool_choice": "auto"}
        elif self.mode == "anthropic":
            req = self._to_anthropic(body)
        else:
            req = body
        if self.meta.get("request_params") is None:
            self.meta["request_params"] = {
                "model": req["model"], "transport": self.mode, "endpoint": self.url,
                "tools": [t.get("name") or t["function"]["name"] for t in req["tools"]],
                "tool_choice": "auto",
                "tool_format": ("anthropic: {name, description, input_schema}"
                                if self.mode == "anthropic" else
                                "openai responses: {type:function, name, description, parameters}"
                                if self.mode == "responses" else
                                "openai: {type:function, function:{...}}"),
                "prompt_caching": ("ON, 5-minute ephemeral TTL, three breakpoints: the tool "
                                   "prefix, the system prompt and the latest user turn"
                                   if self.mode == "anthropic" else
                                   "not offered by this transport"),
                "max_tokens_sent": (self.meta.get("anthropic_max_tokens_sent")
                                    if self.mode == "anthropic" else None),
                "max_tokens_note": ("the DOCUMENTED MAXIMUM - this API requires the field and has "
                                    "no unset, so the cap is the same as no cap; source: %s"
                                    % ANTHROPIC_MAX_OUTPUT_SOURCE
                                    if self.mode == "anthropic" else "not sent"),
                "sampling": SAMPLING}
        #: HC-019 (anthropic, chat): the re-request must be byte-identical to the first request
        _ser = json.dumps(req, sort_keys=True, ensure_ascii=False)
        if self._hc019_attempt == 1:
            if self._hc019_first_body is None or _ser != self._hc019_first_body:
                raise RuntimeError("★HC-019 REFUSING: the re-request of an empty turn (%s turn %s) "
                                   "is not byte-identical to the first request" % (station, turn))
        else:
            self._hc019_first_body = _ser
        raw = self._raw(req, station, turn, retries)
        served = raw.get("model")
        if served and served not in self.meta["served_models"]:
            self.meta["served_models"].append(served)
        for fld in ("reasoning", "service_tier"):
            v = raw.get(fld)
            if v and v not in self.meta.setdefault(fld + "_reported", []):
                self.meta[fld + "_reported"].append(v)
        r = (self._anthropic_as_chat(raw) if self.mode == "anthropic"
             else self._as_chat(raw) if self.mode == "responses" else raw)
        self.meta.setdefault("finish_reasons", []).append(r["choices"][0].get("finish_reason"))
        #: every call's usage, counted HERE: a conversation that ends in an error still spent
        #: tokens, and an HC-019 re-request is a call of its own
        self.meta.setdefault("call_usage", []).append({"usage": r.get("usage") or {}})
        if "stop_reason_anthropic" in r:
            self.meta.setdefault("stop_reasons_anthropic", []).append(r["stop_reason_anthropic"])
            if r["stop_reason_anthropic"] == "max_tokens":
                self.meta.setdefault("output_cap_calls", []).append({"station": station, "turn": turn})
        #: HC-019, on the anthropic and chat transports as their harnesses of record had it
        #: (fable's 76312bf5, flash's 48a14949); not on responses, whose gpt harnesses did not:
        #: an assistant turn with no content and no tool call is re-requested ONCE, identical
        #: request, no added text; a second empty turn stands and the conversation ends with no
        #: submission. In chat mode the body IS the request and is re-sent unchanged.
        if self.mode in ("anthropic", "chat"):
            ev = {"station": station, "turn": turn,
                  "finish_reason": r["choices"][0].get("finish_reason")}
            if self._hc019_attempt == 0 and self._empty_assistant_turn(r):
                ev["action"] = "RE-REQUESTED ONCE, identical request, no added text (HC-019)"
                self.meta.setdefault("hc019_empty_turns", []).append(ev)
                if self.mode == "anthropic" and self.anthropic_prior:
                    self.anthropic_prior.pop()
                self._hc019_attempt = 1
                try:
                    return self.post(key, url, body, station, turn, tries, _hc019_carry=retries)
                finally:
                    self._hc019_attempt = 0
                    self._hc019_first_body = None
            if self._hc019_attempt == 1 and self._empty_assistant_turn(r):
                ev["action"] = "SECOND empty turn - it stands; no submission"
                self.meta.setdefault("hc019_empty_turns", []).append(ev)
        return r, retries


#: set by main(); the tool loop's run_station calls `post`, as in the campaign harness
TRANSPORT = None


def post(key, url, body, station, turn, tries=5):
    return TRANSPORT.post(key, url, body, station, turn, tries)

# ── the packet, and each paper's sandbox ─────────────────────────────────────────────────────
def check_packet(packet):
    """The packet's own MD5SUMS.txt, as shipped: its md5 first, then every packet file in it.
    -> (checked, manifest_md5). Raises SystemExit on any difference."""
    man = Path(packet) / "MD5SUMS.txt"
    if not man.is_file():
        raise SystemExit("★REFUSED: %s has no MD5SUMS.txt. Point --packet at the unpacked demo "
                         "packet (the repository root)." % packet)
    mm = md5f(man)
    if mm != PACKET_MANIFEST_MD5:
        raise SystemExit("★REFUSED: MD5SUMS.txt has md5 %s, not %s. It is not the manifest the "
                         "packet shipped with." % (mm, PACKET_MANIFEST_MD5))
    rows = []
    for line in man.read_text(encoding="utf-8").splitlines():
        h, rel = line.split("  ", 1)
        if rel.startswith("packet/"):
            rows.append((h, rel[len("packet/"):]))
    bad = []
    for h, rel in rows:
        p = Path(packet) / rel
        if not p.is_file():
            bad.append("missing  %s" % rel)
        elif md5f(p) != h:
            bad.append("differs  %s" % rel)
    if len(rows) != PACKET_FILES or bad:
        raise SystemExit("★REFUSED: the packet does not check against its MD5SUMS.txt "
                         "(%d of %d entries; %d problem(s)):\n  %s"
                         % (len(rows) - len(bad), PACKET_FILES, len(bad), "\n  ".join(bad[:20])))
    return len(rows), mm


def graft(src, dst):
    """Reproduce the packet's landscape inside the sandbox as a real directory tree of COPIES.

    The campaign grafted hardlinks to a read-only master. Here the master is the lab's own
    packet and the sandbox's work folder is writable from inside the jail, so a hardlink would let
    candidate code write through into the packet. Copies carry the same bytes and no such path;
    each copy is checked against the packet manifest before the conversation starts."""
    n = 0
    for r, ds, fs in os.walk(src):
        rel = os.path.relpath(r, src)
        here = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(here, exist_ok=True)
        for f in fs:
            shutil.copyfile(os.path.join(r, f), os.path.join(here, f))
            n += 1
    return n


def one_paper(root, station):
    """THE ONE CHECK THE DEMO NEEDS: exactly one paper in the sandbox, and it is this
    conversation's. -> list of reasons (empty = conforms)."""
    papers = []
    for r, ds, fs in os.walk(root):
        for f in fs:
            if re.fullmatch(r"prompt_env0_.+\.md|chain_.+\.md", f):
                papers.append(os.path.relpath(os.path.join(r, f), root))
    if papers != [paper_name(station)]:
        return ["the sandbox holds %d paper(s) %s; it must hold exactly one, %s"
                % (len(papers), sorted(papers), paper_name(station))]
    return []


def compose(packet, station, where, land_manifest):
    """Build one paper's sandbox and prove it before a request is sent. -> (root, manifest)."""
    root = Path(where)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    bundle = Path(packet) / bundle_name(station)
    manifest = {}
    for f in sorted(os.listdir(bundle)):
        shutil.copy(str(bundle / f), str(root / f))
        manifest[f] = md5f(root / f)
    graft(str(Path(packet) / "landscape"), str(root / "landscape"))
    moved = [rel for rel, h in land_manifest.items() if md5f(root / "landscape" / rel) != h]
    if moved:
        raise SystemExit("★REFUSED: the landscape copied into the %s sandbox differs from the "
                         "packet: %s" % (station, ", ".join(moved)))
    #: presence is not reachability: the candidate's own read_file must reach the landscape
    probe = tool_call(root, "read_file", {"path": "landscape/README.txt", "limit": 1})
    if probe.startswith("no such file"):
        raise SystemExit("★REFUSED: the landscape is not reachable for %s through the candidate's "
                         "own read_file: %r" % (station, probe))
    why = one_paper(str(root), station)
    if why:
        raise SystemExit("★SANDBOX REFUSED for %s: %s" % (station, "; ".join(why)))
    return root, manifest


def run_station(key, url, model, root: Path, station, max_turns, log, rawdir):
    """One conversation. -> (answer_text, turns, how, usage_total, per_turn, retries)."""
    paper = (root / paper_name(station)).read_text(encoding="utf-8")
    menu = (root / "menu_env0.json").read_text(encoding="utf-8")
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": paper},
            {"role": "user", "content": MENU_INTRO + "\n\n" + menu}]
    usage_total, per_turn, retries = {}, [], []
    for turn in range(max_turns):
        body = {"model": model, "messages": msgs, "tools": TOOLS, "tool_choice": "auto"}
        r, rt = post(key, url, body, station, turn)
        retries += rt
        (rawdir / ("turn_%02d.json" % turn)).write_text(
            json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
        m = r["choices"][0]["message"]
        u = r.get("usage") or {}
        for k, v in u.items():
            if isinstance(v, int):
                usage_total[k] = usage_total.get(k, 0) + v
        per_turn.append({"turn": turn, "usage": u, "response_id": r.get("id"),
                         "response_model": r.get("model"),
                         "service_tier": r.get("service_tier"),
                         "finish_reason": r["choices"][0].get("finish_reason")})
        log.write(json.dumps({"turn": turn, "message": m, "usage": u,
                              "response_model": r.get("model")}, default=str) + "\n")
        log.flush()
        msgs.append(m)
        calls = m.get("tool_calls") or []
        if not calls:
            return m.get("content") or "", turn + 1, "text", usage_total, per_turn, retries
        for c in calls:
            fn = c["function"]["name"]
            try:
                a = json.loads(c["function"].get("arguments") or "{}")
            except Exception:
                a = {}
            if fn == "submit_answer":
                return (a.get("answer_json", ""), turn + 1, "submit_answer",
                        usage_total, per_turn, retries)
            res = tool_call(root, fn, a)
            log.write(json.dumps({"turn": turn, "tool": fn, "args_preview": str(a)[:2000],
                                  "result_preview": str(res)[:2000]}) + "\n")
            log.flush()
            msgs.append({"role": "tool", "tool_call_id": c["id"], "content": str(res)[:24000]})
    return "", max_turns, "turn cap", usage_total, per_turn, retries


def usage_of(per_turn):
    """input, cached, cache-write, output and reasoning tokens over one conversation, from each
    turn's usage as the transport reported it"""
    t = {"prompt_tokens": 0, "cached_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0,
         "total_tokens": 0, "cache_write_5m_tokens": 0, "cache_write_1h_tokens": 0,
         "cache_write_unattributed_tokens": 0, "calls": 0}
    for p in per_turn:
        u = p.get("usage") or {}
        t["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
        t["completion_tokens"] += int(u.get("completion_tokens") or 0)
        t["total_tokens"] += int(u.get("total_tokens") or 0)
        t["cached_tokens"] += int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
        t["reasoning_tokens"] += int((u.get("completion_tokens_details") or {})
                                     .get("reasoning_tokens") or 0)
        for k in ("cache_write_5m_tokens", "cache_write_1h_tokens",
                  "cache_write_unattributed_tokens"):
            t[k] += int(u.get(k) or 0)
        t["calls"] += 1
    return t


RETRY_RULE = {
    "chat": "5 attempts, backoff min(6*2^i, 60) s, on HTTP 408/409/429/5xx/529 and socket errors "
            "(timeouts included); a daily-quota 429 is never retried; an empty assistant turn is "
            "re-requested once, identically (HC-019) (flash's campaign harness 48a14949)",
    "responses": "5 attempts, backoff min(6*2^i, 60) s, on HTTP 408/409/429/5xx/529 and socket "
                 "errors (timeouts included); a daily-quota 429 is never retried (campaign "
                 "transport b2fd302b)",
    "anthropic": "5 attempts, backoff min(6*2^i, 60) s, on HTTP 408/409/429/5xx/529 and socket "
                 "errors; a TIMEOUT is never retried and stops the conversation; a daily-quota 429 "
                 "is never retried; an empty assistant turn is re-requested once, identically "
                 "(HC-019) (campaign transport 76312bf5)",
}
FOURXX_RULE = ("an HTTP 4xx refusal is re-run ONCE as a fresh conversation in a fresh sandbox; the "
               "first attempt is kept as <paper>__attempt1; a second 4xx stands as no submission "
               "(the campaign's rule, founder 7 Sep 2026)")


def main():
    global TRANSPORT
    ap = argparse.ArgumentParser(description="Run a model on the three ENV0 demo papers.")
    ap.add_argument("--packet", required=True, help="the unpacked demo packet (the repository root)")
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--transport", choices=("chat", "responses", "anthropic"), default="chat")
    ap.add_argument("--base-url", dest="base_url", default=None,
                    help="default: the provider endpoint for the chosen transport")
    ap.add_argument("--max-turns", type=int, default=120)
    A = ap.parse_args()
    if A.base_url is None:
        A.base_url = {"chat": API_CHAT, "responses": API_RESPONSES,
                      "anthropic": API_ANTHROPIC}[A.transport]

    runner_md5 = md5f(__file__)
    iso_md5 = md5f(_ISO)
    ns_ok, ns_why = _ns_available()
    if not ns_ok:
        raise SystemExit("★REFUSED: mount namespaces are unavailable (%s). The runner isolates the "
                         "model's code in a mount and PID namespace and will not run it any other "
                         "way. Run on Linux as root (a VM or a privileged container)." % ns_why)
    h, ok = loop_provenance()
    if not ok:
        raise SystemExit("★REFUSED: the tool loop has drifted (%s, expected %s). A score "
                         "difference between two models must not be a difference between two "
                         "harnesses." % (h, ENV1_LOOP_MD5))
    #: the transport and the model must agree, both ways (as the campaign refused)
    is_claude = str(A.model).startswith("claude-")
    if A.transport == "anthropic" and not is_claude:
        raise SystemExit("★REFUSED: --transport anthropic with model %r. That transport builds an "
                         "Anthropic request body; it is meaningless for a non-claude id." % A.model)
    if is_claude and A.transport != "anthropic":
        raise SystemExit("★REFUSED: model %r on --transport %s. A Claude model needs "
                         "--transport anthropic: the system prompt, the tool shape, the tool "
                         "results and max_tokens all differ." % (A.model, A.transport))
    if A.transport == "anthropic":
        anthropic_max_output(A.model)            # refuses before any call if the max is unknown
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        raise SystemExit("★REFUSED: %s is not set. The model API key is read from that environment "
                         "variable and from nowhere else." % KEY_ENV)
    n_checked, man_md5 = check_packet(A.packet)
    print("runner %s · loop %s · sandbox %s · namespaces available" % (runner_md5, h, iso_md5),
          flush=True)
    print("packet: MD5SUMS.txt %s, %d of %d files check" % (man_md5, n_checked, PACKET_FILES),
          flush=True)

    land = {}
    for line in (Path(A.packet) / "MD5SUMS.txt").read_text(encoding="utf-8").splitlines():
        hh, rel = line.split("  ", 1)
        if rel.startswith("packet/landscape/"):
            land[rel[len("packet/landscape/"):]] = hh

    out = Path(A.out)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "transcripts").mkdir(parents=True, exist_ok=True)
    run = {"harness": "run_demo.py",
           "harness_note": "the ENV0 campaign harness (run_env0_campaign.py %s) on the three demo "
                           "papers; one conversation per paper, no carry-over; retries on "
                           "transport only; 4xx re-run once" % CAMPAIGN_HARNESS_MD5,
           "model": A.model,
           "base_url_host": urllib.parse.urlsplit(A.base_url).hostname,
           "endpoint_path": urllib.parse.urlsplit(A.base_url).path,
           "transport": A.transport,
           "retry_rule": RETRY_RULE[A.transport],
           "fourxx_rule": FOURXX_RULE,
           "runner_md5": runner_md5,
           "loop_md5": h, "loop_verified": ok,
           "sandbox_md5": iso_md5, "sandbox_provenance": VENDORED_PROVENANCE,
           "packet_manifest_md5": man_md5, "packet_files_checked": n_checked,
           "system_message": SYSTEM, "menu_intro": MENU_INTRO,
           "max_turns": A.max_turns,
           "sampling": "default - no sampling or reasoning parameter is sent by this harness",
           "anthropic_max_tokens": (ANTHROPIC_MAX_OUTPUT.get(A.model)
                                    if A.transport == "anthropic" else None),
           "anthropic_max_tokens_source": (ANTHROPIC_MAX_OUTPUT_SOURCE
                                           if A.transport == "anthropic" else None),
           "papers": {}, "retries": [], "usage_total": {}}
    print("ENV0 DEMO · %s · %s (%s)" % (A.model, run["base_url_host"], A.transport), flush=True)

    served_all, reasoning_all, tier_all = [], [], []
    work = Path(tempfile.mkdtemp(prefix="env0_demo_"))
    try:
        for n in TASKS:
            attempt = 1
            while True:
                root, manifest = compose(A.packet, n, work / ("sandbox_%s" % n), land)
                rawdir = out / "raw" / n
                rawdir.mkdir(parents=True, exist_ok=True)
                meta = {"served_models": [], "request_params": None}
                TRANSPORT = Transport(A.base_url, key, A.transport, meta)
                t0, err, timed_out = time.time(), None, False
                try:
                    with (out / "transcripts" / ("%s.jsonl" % n)).open("w", encoding="utf-8") as log:
                        ans, turns, how, usage, per_turn, rts = run_station(
                            key, A.base_url, A.model, root, n, A.max_turns, log, rawdir)
                except SystemExit:
                    raise
                except TimeoutStop as e:
                    ans, turns, how, usage, per_turn, rts = "", 0, "TIMEOUT STOP", {}, [], []
                    err = "%s: %s" % (type(e).__name__, str(e)[:400])
                    timed_out = True
                except Exception as e:
                    ans, turns, how, usage, per_turn, rts = "", 0, "ERROR", {}, [], []
                    err = "%s: %s" % (type(e).__name__, str(e)[:400])
                shutil.rmtree(root, ignore_errors=True)
                secs = round(time.time() - t0, 1)
                (out / ("%s.json" % n)).write_text(ans or "", encoding="utf-8")
                tok = usage_of(meta.get("call_usage", []))
                pe = meta.get("provider_event")
                for m in meta.get("served_models", []):
                    if m not in served_all:
                        served_all.append(m)
                for v in meta.get("reasoning_reported", []):
                    if v not in reasoning_all:
                        reasoning_all.append(v)
                for v in meta.get("service_tier_reported", []):
                    if v not in tier_all:
                        tier_all.append(v)
                rec = {"attempt": attempt,
                       "finished_by": how, "turns": turns, "seconds": secs,
                       "answer_bytes": len(ans or ""),
                       "answer_md5": hashlib.md5((ans or "").encode("utf-8")).hexdigest(),
                       "error": err, "provider_event": pe, "timeout_stop": timed_out,
                       "served_model": sorted({p.get("response_model") for p in per_turn
                                               if p.get("response_model")}),
                       "usage": tok, "per_turn": per_turn, "retries": rts, "n_retries": len(rts),
                       "request_params": meta.get("request_params"),
                       "key_probe_profile": meta.get("key_probe_profile"),
                       "hc019_empty_turns": meta.get("hc019_empty_turns", []),
                       "timeout_stops": meta.get("timeout_stops", []),
                       "finish_reasons": meta.get("finish_reasons", []),
                       "bundle": manifest, "sandbox_check": "exactly one paper, %s" % paper_name(n)}
                for k in ("stop_reasons_anthropic", "output_cap_calls",
                          "anthropic_block_types_received", "public_key_prefix_seen",
                          "key_shape_noted_in_opaque"):
                    if meta.get(k):
                        rec[k] = meta[k]
                run["papers"][n] = rec
                run["retries"] += rts
                for k, v in tok.items():
                    run["usage_total"][k] = run["usage_total"].get(k, 0) + v
                print("  %-19s %-14s turns %3d  %6d B  %5.0f s  tokens in/cached/out/reasoning "
                      "%d/%d/%d/%d  %s"
                      % (n, how[:14], turns, len(ans or ""), secs, tok["prompt_tokens"],
                         tok["cached_tokens"], tok["completion_tokens"], tok["reasoning_tokens"],
                         err or ""), flush=True)

                #: THE CAMPAIGN'S 4xx RULE. `attempt` is 1 then 2 and never 3.
                http = (pe or {}).get("http")
                is_4xx = isinstance(http, int) and 400 <= http < 500
                if is_4xx and attempt == 1:
                    first = dict(rec)
                    first["superseded_by"] = "attempt 2 (fresh conversation)"
                    src = out / "raw" / n
                    if src.exists():
                        dst = out / "raw" / ("%s__attempt1" % n)
                        shutil.rmtree(dst, ignore_errors=True)
                        src.rename(dst)
                    tsrc = out / "transcripts" / ("%s.jsonl" % n)
                    if tsrc.exists():
                        tsrc.rename(out / "transcripts" / ("%s__attempt1.jsonl" % n))
                    asrc = out / ("%s.json" % n)
                    if asrc.exists():
                        asrc.rename(out / ("%s__attempt1.json" % n))
                    run["papers"]["%s__attempt1" % n] = first
                    print("      ★HTTP %d refusal on attempt 1 — re-run ONCE as a fresh "
                          "conversation; the first is kept as %s__attempt1" % (http, n), flush=True)
                    attempt = 2
                    continue
                if attempt == 2:
                    rec["rerun_of_4xx"] = True
                    rec["first_attempt_record"] = "%s__attempt1" % n
                    if is_4xx:
                        rec["second_refusal_stands"] = True
                        print("      ★second 4xx on the re-run — it stands as no submission",
                              flush=True)
                break
    finally:
        shutil.rmtree(work, ignore_errors=True)

    run["request_params"] = next((p.get("request_params") for p in run["papers"].values()
                                  if p.get("request_params")), None)
    run["served_models"] = served_all
    run["reasoning_reported"] = reasoning_all
    run["service_tier_reported"] = tier_all
    run["written_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (out / "RUN.json").write_text(json.dumps(run, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote %s" % out, flush=True)


if __name__ == "__main__":
    main()
