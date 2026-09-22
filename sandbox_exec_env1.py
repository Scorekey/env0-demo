#!/usr/bin/env python3
"""★★THE VENDORED RUNNER — code execution inside a mount namespace. v2.3, 24 August 2026.

★★★WHY THE AUDIT-HOOK APPROACH ENDED HERE. Three rounds patched a CPython audit hook and three
re-audits re-broke it: `/proc` on the allowlist, unguarded directory listing, an undeleted sandbox,
and finally **a hardlink of the key file into the agent's own folder, with the inherited PWD
handing over the grader path** — all 35 of t8's keys read from a live t1 conversation. Ruled:
enumerating dangerous calls against an agent that runs arbitrary code is unwinnable. **Isolation
moves down a layer.**

THE PROPERTY THIS FILE PROVIDES, and it is a property of the FILESYSTEM rather than of a list of
blocked calls:

    THE AGENT'S CODE-EXECUTION ENVIRONMENT CONTAINS ONLY ITS OWN SANDBOX AND THE PUBLIC DATA.
    The key file is not there. No other paper is there. The grader source is not there.
    There is nothing to hardlink to, and no path worth leaking.

Every attempt to reach out now fails with **FileNotFoundError, not PermissionError** — the
difference matters, and it is the whole point: a blocked path still exists and the next round finds
another spelling of it; a path that does not exist has no other spelling.

HOW
  * `unshare --mount --pid --fork` gives the child its own mount and PID namespaces, so the binds
    below are invisible to the host and `/proc` shows only the child's own namespace. ★The PID
    namespace is not decoration: without it `/proc/1/root` and `/proc/<ppid>/root` are the REAL
    root, which is the same escape by another name.
  * a jail skeleton is built per call: `work/` is the conversation's sandbox; `/usr`, `/lib`,
    `/lib64`, `/bin` are bound READ-ONLY so the interpreter runs; `/dev/null` and `/dev/urandom`
    are bound as files; nothing else exists.
  * `chroot` into it, `cwd=/work`, and a CLEAN ENVIRONMENT - no inherited `PWD`, no paths, nothing
    that names the grader tree. The inherited environment was half of the exfiltration chain.
  * the audit hook stays INSIDE as defence in depth, now also refusing `os.link`, `os.rename` and
    `os.replace`. ★It is no longer the boundary; it is a second line behind one.

★IF NAMESPACES ARE UNAVAILABLE this module REFUSES TO RUN CODE rather than silently degrading to
the hook-only shape that three audits defeated. The ruled alternative is (c): run the
agent-execution phase with the grader tree and every other paper physically absent, restoring them
only for the separate scoring phase. A runner that cannot isolate must not quietly measure anyway.

★★SHARED: ENV0 and ENV1 both vendor this file. ENV0's harness has the identical hole and inherits
this fix rather than building its own. The region hash below is written into every RUN.json.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ── the guard that still runs INSIDE the jail ─────────────────────────────────────────────────
GUARD = '''import sys as _s, os as _o
_ROOT = _o.path.abspath({root!r})
_OK = (_ROOT, "/usr", "/lib", "/lib64", "/bin", "/etc/localtime", "/dev/urandom", "/dev/null",
       _s.prefix, _s.base_prefix, _o.path.dirname(_o.__file__))
_NEVER = ("/proc", "/sys")


def _outside(p):
    try: q = _o.path.realpath(_o.path.abspath(str(p)))
    except Exception: return None
    if any(q == x or q.startswith(x + "/") for x in _NEVER): return q
    return None if any(q == x or q.startswith(x + "/") for x in _OK) else q


def _hook(ev, a):
    if ev in ("open", "os.open"):
        p = _outside(a[0] if a else "")
        if p: raise PermissionError("outside your working folder: " + p)
    if ev in ("os.listdir", "os.scandir", "os.walk", "glob.glob", "glob.glob/2",
              "pathlib.Path.glob", "os.chdir"):
        p = _outside(a[0] if a else _ROOT)
        if p: raise PermissionError("outside your working folder: " + p)
    # ★v2.3: LINKING IS A READ IN DISGUISE. The exfiltration that ended the hook-only approach was
    # `os.link(<key file>, './k')` - the bytes never pass through `open` at all, they are given a
    # second name inside a folder the agent already owns. Blocked here as defence in depth; the
    # isolation is what actually removes the target.
    if ev in ("os.link", "os.symlink", "os.rename", "os.replace"):
        for x in (a or ())[:2]:
            p = _outside(x)
            if p: raise PermissionError("outside your working folder: " + p)
    if ev in ("os.system", "subprocess.Popen", "os.exec", "os.spawn", "shutil.copyfile"):
        raise PermissionError("subprocesses are not available")
_s.addaudithook(_hook)
del _hook
'''

#: the bind set. READ-ONLY, and short on purpose: everything not named here simply is not there.
RO_BINDS = ("/usr", "/lib", "/lib64", "/bin")
DEV_BINDS = ("/dev/null", "/dev/urandom")
ETC_FILES = ("/etc/ld.so.cache", "/etc/localtime")

_JAIL_SH = r"""set -e
J="$1"; PY="$2"; SCRIPT="$3"; CHROOT="$5"
mount --bind "$4" "$J/work"
for d in {ro}; do [ -d "$d" ] && mount --bind "$d" "$J$d" && mount -o remount,bind,ro "$J$d"; done
for f in {dev}; do [ -e "$f" ] && : > "$J$f" 2>/dev/null; [ -e "$f" ] && mount --bind "$f" "$J$f"; done
for f in {etc}; do [ -f "$f" ] && : > "$J$f" 2>/dev/null && mount --bind "$f" "$J$f"; done
# ★cwd is /work, not /. `chroot` leaves the cwd at the new root, and a candidate whose relative
# paths resolve against / would see the jail skeleton instead of its own folder.
exec "$CHROOT" "$J" /bin/sh -c 'cd /work && exec "$0" "$@"' "$PY" "$SCRIPT"
"""


def namespaces_available():
    """-> (ok, why). Measured, never assumed: the check RUNS a namespace and a bind mount."""
    if not shutil.which("unshare"):
        return False, "`unshare` is not on PATH"
    if not (shutil.which("chroot") or Path("/usr/sbin/chroot").exists()):
        return False, "`chroot` is not available"
    try:
        r = subprocess.run(["unshare", "--mount", "--pid", "--fork", "sh", "-c",
                            "mkdir -p /tmp/.nsprobe && mount --bind /tmp /tmp/.nsprobe "
                            "&& echo NSOK"],
                           capture_output=True, text=True, timeout=30)
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, e)
    if "NSOK" in r.stdout:
        return True, ""
    return False, (r.stderr.strip()[:120] or "the namespace probe printed no NSOK")


def _real_python():
    """the interpreter's REAL path - `/usr/bin/python3` is a symlink chain through /etc, and
    /etc is not in the jail, so the symlink resolves to nothing inside it."""
    return os.path.realpath(sys.executable or "/usr/bin/python3")


def run_code(sandbox: Path, code: str, timeout=120, guard=True):
    """Run `code` with ONLY `sandbox` and the runtime visible. -> combined output.

    ★`guard=False` runs WITHOUT the inner audit hook, and exists for exactly one caller:
    `probe_exfiltration_env1.py`, which must measure THE ISOLATION ALONE. With the hook in place
    every attempt fails with PermissionError - the hook catches it first - and the probe would
    then be re-testing the layer three audits already defeated while the layer we now rely on went
    unexercised. ★It is never used by the harness; a run with `guard=False` is a measurement of
    the boundary, not a delivery of a paper."""
    ok, why = namespaces_available()
    if not ok:
        raise RuntimeError(
            "REFUSING TO RUN CANDIDATE CODE: mount namespaces are unavailable (%s). This runner "
            "will not fall back to the audit-hook-only shape that three independent audits "
            "defeated. The ruled alternative is to run the agent-execution phase with the grader "
            "tree and every other paper physically absent." % why)

    sandbox = Path(sandbox).resolve()
    jail = Path(tempfile.mkdtemp(prefix="env1_jail_"))
    try:
        py = _real_python()
        for d in ("work", "proc", "dev", "etc", "code") + tuple(x.lstrip("/") for x in RO_BINDS):
            (jail / d).mkdir(parents=True, exist_ok=True)
        # the script lives in the jail but OUTSIDE `work`, so it is not in the agent's own folder
        (jail / "code" / "run.py").write_text(
            (GUARD.format(root="/work") + "\n" if guard else "") + code, encoding="utf-8")
        sh = _JAIL_SH.format(ro=" ".join(RO_BINDS), dev=" ".join(DEV_BINDS),
                             etc=" ".join(ETC_FILES))
        cmd = ["unshare", "--mount", "--pid", "--fork",
               "--mount-proc=%s" % (jail / "proc"),
               "sh", "-c", sh + "\n", "sh", str(jail), py, "/code/run.py", str(sandbox),
               # ★absolute, because the jail's PATH is not the host's and `chroot` lives in /usr/sbin
               (shutil.which("chroot") or "/usr/sbin/chroot")]
        # ★A CLEAN ENVIRONMENT. The inherited `PWD` was half the exfiltration chain: it named the
        # grader tree to code that had no other way to learn the path.
        env = {"PATH": "/usr/bin:/bin", "HOME": "/work", "LC_ALL": "C.UTF-8",
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"}
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env,
                           cwd="/")
        out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
        return out[:24000] if out.strip() else "(no output)"
    finally:
        shutil.rmtree(jail, ignore_errors=True)


def region_hash():
    """md5 of THIS FILE - the whole module is the vendored region, so there is no marker to drift
    away from and no way to vendor half of it."""
    return hashlib.md5(Path(__file__).read_bytes()).hexdigest()


PROVENANCE = ("vendored runner v2.3, 24 Aug 2026: mount+PID namespace and chroot, only the "
              "conversation's own sandbox and the runtime are present; clean env; audit hook "
              "retained as defence in depth with os.link/rename/replace added. Shared by ENV0 "
              "and ENV1; both re-vendor from this file.")

if __name__ == "__main__":
    ok, why = namespaces_available()
    print("namespaces available: %s%s" % (ok, "" if ok else "  (%s)" % why))
    print("region hash: %s" % region_hash())
    print(PROVENANCE)
