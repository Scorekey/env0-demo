#!/usr/bin/env python3
"""ENV0 DEMO — THE REFERENCE RUNNER. Runs a model on the three demo papers exactly as the campaign did.

    python run_demo.py --packet . --model <name> --out runs/<name> [--transport chat|responses]

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
  * retries on TRANSPORT errors only (HTTP 408/409/429/5xx, socket, timeout); a model answer is
    never re-requested and no prompt is ever adjusted; no sampling or reasoning parameter is sent.

TRANSPORT. `--transport chat` (default) speaks /v1/chat/completions. `--transport responses` speaks
/v1/responses through the campaign's adapter, ported unchanged in behaviour: the model's own prior
output items (reasoning included) are carried forward and each tool result goes back as a
function_call_output. The gpt-5.6 models refuse function tools on chat completions, and the
campaign ran them over responses; README.md lists which transport each model ran on.

WHAT IT REFUSES, rather than degrading:
  * a Linux host without mount namespaces (the runner must be able to isolate);
  * a missing SCOREKEY_MODEL_KEY (the API key comes from that environment variable and nowhere else;
    it is held in memory, sent in an Authorization header, and never written or logged);
  * a packet whose MD5SUMS.txt does not check, or an MD5SUMS.txt that is not the one shipped;
  * a sandbox holding anything other than exactly one paper, and that paper this conversation's.

WHAT IT WRITES
  <out>/T3.json, T4.json, full-chain-from-T1.json   the submit_answer body of each paper, exactly
  <out>/RUN.json                                    model, endpoint host, transport, the three md5s,
                                                    turns, finished_by and token usage per paper
  <out>/raw/<task>/turn_NN.json, <out>/transcripts/<task>.jsonl   every response body and the turn log
"""
import argparse, datetime, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
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
#: Ported from the campaign transport (HC-013), unchanged in behaviour: every outgoing request body
#: is walked BEFORE it is sent. The live key, or a 12-character run of it, anywhere in it is a
#: refusal; so is an Authorization field or a key-shaped string outside the provider's own opaque
#: reasoning blob (`encrypted_content`), where a shape hit is recorded and not refused.
_KEY_RX = [
    ("google_aiza",   re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("google_aq",     re.compile(r"(?<![A-Za-z0-9])AQ\.[A-Za-z0-9_\-]{20,}")),
    ("openai_sk",     re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{20,}")),
    ("bearer_header", re.compile(r"(?i)authorization\"?\s*[:=]\s*\"?bearer\s")),
]


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
            if live_key:
                for probe, label in ((live_key, "THE LIVE KEY"),
                                     (live_key[:12], "the live key's first 12 characters"),
                                     (live_key[-12:], "the live key's last 12 characters")):
                    if len(probe) >= 8 and probe in o:
                        hits.append((label, path or "."))          # never exempt
    walk(obj)
    return hits, noted


def refuse_if_key_shaped(obj, live_key, what, meta=None):
    hits, noted = key_shaped(obj, live_key)
    if noted and meta is not None:
        seen = meta.setdefault("key_shape_noted_in_opaque", [])
        for h in noted:
            if h[1] not in [x["where"] for x in seen]:
                seen.append({"what": h[0], "where": h[1],
                             "ruling": "inside the provider's own encrypted_content: SHAPE hit "
                                       "recorded, not refused. Equality against the live key was "
                                       "applied here too and did not fire."})
    real = [h for h in hits if h[0].startswith("THE LIVE KEY") or h[0].startswith("the live key")]
    if real:
        raise SystemExit(
            "★★KEY-SHAPED BODY REFUSED — %s. THE LIVE KEY (or a 12-character run of it) IS IN THE "
            "OBJECT ABOUT TO LEAVE THIS PROCESS, at %s. Nothing is sent and nothing is logged."
            % (what, "; ".join(x for _, x in real)))
    if hits:
        raise SystemExit(
            "★★KEY-SHAPED BODY REFUSED — %s. A key-shaped string is in the object about to leave "
            "this process: %s. This is a stop, not proof of a leak: look at the named field."
            % (what, "; ".join("%s at %s" % h for h in hits)))


# ── the transport: chat completions, or responses through the campaign's adapter ─────────────
HARD_QUOTA = "generate_requests_per_model_per_day"
RETRY_BUDGET_PER_CALL = 5
RETRYABLE_HTTP = (429, 500, 502, 503, 504, 408, 409, 529)
SAMPLING = ("DEFAULT - no temperature, top_p, seed, reasoning_effort, max_tokens or "
            "response_format is sent by this harness")


def _backoff(i):
    return min(6 * (2 ** i), 60)


class Transport:
    """Speaks chat-completions to the tool loop whatever it speaks to the provider.

    The signature and the return shape are the harness's `post`: (parsed_body, retry_log).
    Ported from the campaign transport with its spend ledger, price table and request banking
    removed; the request it builds, the retries it makes and the translation it does are its own."""

    def __init__(self, url, key, mode, meta):
        self.url, self.key, self.mode, self.meta = url, key, mode, meta
        self.prior = []          # responses mode: the model's own output items, in order

    def reset(self):
        """one conversation per paper: nothing of one paper's output reaches the next"""
        self.prior = []

    def _raw(self, body, station, turn, retries):
        refuse_if_key_shaped(body, self.key, "the outgoing request body", self.meta)
        data = json.dumps(body).encode()
        for i in range(RETRY_BUDGET_PER_CALL):
            req = urllib.request.Request(self.url, data=data, headers={
                "Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
            t0 = time.time()
            try:
                return json.load(urllib.request.urlopen(req, timeout=1800))
            except urllib.error.HTTPError as e:
                msg = e.read().decode("utf-8", "replace")[:600]
                if e.code == 429 and HARD_QUOTA in msg:
                    raise RuntimeError("HTTP 429 DAILY QUOTA (never retried) %s" % msg)
                if e.code not in RETRYABLE_HTTP or i == RETRY_BUDGET_PER_CALL - 1:
                    self.meta["provider_event"] = {
                        "http": e.code, "message_verbatim": msg, "station": station,
                        "turn": turn,
                        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
                    raise RuntimeError("HTTP %s %s" % (e.code, msg))
                retries.append({"station": station, "turn": turn, "attempt": i + 1,
                                "kind": "http", "code": e.code, "sleep_s": _backoff(i),
                                "body_preview": msg[:200], "seconds": round(time.time() - t0, 1),
                                "action": "retry (transport)"})
                print("      retry %d after HTTP %s" % (i + 1, e.code), flush=True)
                time.sleep(_backoff(i))
            except Exception as e:
                if i == RETRY_BUDGET_PER_CALL - 1:
                    self.meta["provider_event"] = {
                        "http": None, "message_verbatim": "%s: %s" % (type(e).__name__, str(e)[:400]),
                        "station": station, "turn": turn,
                        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
                    raise
                retries.append({"station": station, "turn": turn, "attempt": i + 1,
                                "kind": "transport", "sleep_s": _backoff(i),
                                "error": "%s: %s" % (type(e).__name__, str(e)[:200]),
                                "seconds": round(time.time() - t0, 1),
                                "action": "retry (transport)"})
                print("      retry %d after %s" % (i + 1, type(e).__name__), flush=True)
                time.sleep(_backoff(i))
        raise RuntimeError("attempts exhausted")

    # -- responses <-> chat -------------------------------------------------------------------
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

    def post(self, key, url, body, station, turn, tries=5):
        """the signature the tool loop calls; `key` and `url` are ignored, ours are held here.
        Returns (parsed_body, retry_log) exactly as the harness's post does."""
        retries = []
        if self.mode == "responses":
            req = {"model": body["model"], "input": self._to_input(body["messages"]),
                   "tools": [{"type": "function", "name": t["function"]["name"],
                              "description": t["function"]["description"],
                              "parameters": t["function"]["parameters"]} for t in body["tools"]],
                   "tool_choice": "auto"}
        else:
            req = body
        if self.meta.get("request_params") is None:
            self.meta["request_params"] = {
                "model": req["model"], "transport": self.mode, "endpoint": self.url,
                "tools": [t.get("name") or t["function"]["name"] for t in req["tools"]],
                "tool_choice": "auto", "sampling": SAMPLING}
        raw = self._raw(req, station, turn, retries)
        served = raw.get("model")
        if served and served not in self.meta["served_models"]:
            self.meta["served_models"].append(served)
        for fld in ("reasoning", "service_tier"):
            v = raw.get(fld)
            if v and v not in self.meta.setdefault(fld + "_reported", []):
                self.meta[fld + "_reported"].append(v)
        r = self._as_chat(raw) if self.mode == "responses" else raw
        self.meta.setdefault("finish_reasons", []).append(r["choices"][0].get("finish_reason"))
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
    """prompt, cached, completion and reasoning tokens over one conversation, from each turn's usage"""
    t = {"prompt_tokens": 0, "cached_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0,
         "total_tokens": 0, "calls": 0}
    for p in per_turn:
        u = p.get("usage") or {}
        t["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
        t["completion_tokens"] += int(u.get("completion_tokens") or 0)
        t["total_tokens"] += int(u.get("total_tokens") or 0)
        t["cached_tokens"] += int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
        t["reasoning_tokens"] += int((u.get("completion_tokens_details") or {})
                                     .get("reasoning_tokens") or 0)
        t["calls"] += 1
    return t


def main():
    global TRANSPORT
    ap = argparse.ArgumentParser(description="Run a model on the three ENV0 demo papers.")
    ap.add_argument("--packet", required=True, help="the unpacked demo packet (the repository root)")
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--transport", choices=("chat", "responses"), default="chat")
    ap.add_argument("--base-url", dest="base_url", default=None,
                    help="default: the OpenAI endpoint for the chosen transport")
    ap.add_argument("--max-turns", type=int, default=120)
    A = ap.parse_args()
    if A.base_url is None:
        A.base_url = API_RESPONSES if A.transport == "responses" else API_CHAT

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
    meta = {"served_models": []}
    TRANSPORT = Transport(A.base_url, key, A.transport, meta)
    run = {"harness": "run_demo.py",
           "harness_note": "the ENV0 campaign harness (run_env0_campaign.py %s) on the three demo "
                           "papers; one conversation per paper, no carry-over; one attempt per "
                           "paper; retries on transport only" % CAMPAIGN_HARNESS_MD5,
           "model": A.model,
           "base_url_host": urllib.parse.urlsplit(A.base_url).hostname,
           "endpoint_path": urllib.parse.urlsplit(A.base_url).path,
           "transport": A.transport,
           "runner_md5": runner_md5,
           "loop_md5": h, "loop_verified": ok,
           "sandbox_md5": iso_md5, "sandbox_provenance": VENDORED_PROVENANCE,
           "packet_manifest_md5": man_md5, "packet_files_checked": n_checked,
           "system_message": SYSTEM, "menu_intro": MENU_INTRO,
           "max_turns": A.max_turns,
           "sampling": "default - no sampling or reasoning parameter is sent by this harness",
           "papers": {}, "retries": [], "usage_total": {}}
    print("ENV0 DEMO · %s · %s (%s)" % (A.model, run["base_url_host"], A.transport), flush=True)

    work = Path(tempfile.mkdtemp(prefix="env0_demo_"))
    try:
        for n in TASKS:
            root, manifest = compose(A.packet, n, work / ("sandbox_%s" % n), land)
            rawdir = out / "raw" / n
            rawdir.mkdir(parents=True, exist_ok=True)
            TRANSPORT.reset()
            meta["request_params"] = None
            t0, err = time.time(), None
            try:
                with (out / "transcripts" / ("%s.jsonl" % n)).open("w", encoding="utf-8") as log:
                    ans, turns, how, usage, per_turn, rts = run_station(
                        key, A.base_url, A.model, root, n, A.max_turns, log, rawdir)
            except SystemExit:
                raise
            except Exception as e:
                ans, turns, how, usage, per_turn, rts = "", 0, "ERROR", {}, [], []
                err = "%s: %s" % (type(e).__name__, str(e)[:400])
            shutil.rmtree(root, ignore_errors=True)
            secs = round(time.time() - t0, 1)
            (out / ("%s.json" % n)).write_text(ans or "", encoding="utf-8")
            tok = usage_of(per_turn)
            run["retries"] += rts
            run["papers"][n] = {
                "finished_by": how, "turns": turns, "seconds": secs,
                "answer_bytes": len(ans or ""), "answer_md5": hashlib.md5((ans or "").encode("utf-8")).hexdigest(),
                "error": err, "provider_event": meta.pop("provider_event", None),
                "served_model": sorted({p.get("response_model") for p in per_turn
                                        if p.get("response_model")}),
                "usage": tok, "per_turn": per_turn, "n_retries": len(rts),
                "bundle": manifest, "sandbox_check": "exactly one paper, %s" % paper_name(n)}
            for k, v in tok.items():
                run["usage_total"][k] = run["usage_total"].get(k, 0) + v
            print("  %-19s %-14s turns %3d  %6d B  %5.0f s  tokens in/out/reasoning %d/%d/%d  %s"
                  % (n, how, turns, len(ans or ""), secs, tok["prompt_tokens"],
                     tok["completion_tokens"], tok["reasoning_tokens"], err or ""), flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    run["request_params"] = {"model": A.model, "transport": A.transport,
                             "endpoint": A.base_url.split("?")[0],
                             "tools": [t["function"]["name"] for t in TOOLS],
                             "tool_choice": "auto", "sampling": SAMPLING}
    run["served_models"] = meta.get("served_models", [])
    run["reasoning_reported"] = meta.get("reasoning_reported", [])
    run["service_tier_reported"] = meta.get("service_tier_reported", [])
    if meta.get("key_shape_noted_in_opaque"):
        run["key_shape_noted_in_opaque"] = meta["key_shape_noted_in_opaque"]
    run["written_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (out / "RUN.json").write_text(json.dumps(run, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote %s" % out, flush=True)


if __name__ == "__main__":
    main()
