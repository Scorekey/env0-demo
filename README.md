# ENV0 — a demonstration packet

Source: ECB statistics.

On scorekey.ai these are called: Extract the figures (T4); the full build from the brief
(full-chain-from-T1); the full build from the plan (mid-start-from-T3).

Three tasks from ENV0, an evaluation of how a model works with published payment statistics, put
here so that a lab can run its own model against them: **T4**, the station that extracts the
figures, and two spans of the chain — **the full chain from T1** and **the build from the plan,
mid-start-from-T3**.

This repository is the packet exactly as a lab receives it: the three prompt pages with their
menus and `CHAIN_DELIVERY_README.md`, which says what each chain span is given and what it is
scored on, and the data landscape — the thirteen ECB payment-statistics dumps of the 10 July 2026
snapshot, and the three ECB SPACE respondent files (waves 2019, 2022, 2024) with their codebooks.
`landscape/ATTRIBUTION.txt` names the ECB's terms of reuse and publishes every data file's md5.
There are no answer keys here; scoring is done by the service below.

## The scorer

    https://scorekey-env0.fly.dev

    POST /score/T4
    POST /score/full-chain-from-T1
    POST /score/mid-start-from-T3

Send the submission JSON as the request body and your token in the `X-ENV0-Key` header:

    curl -X POST -H "X-ENV0-Key: <your token>" --data-binary @T4.json https://scorekey-env0.fly.dev/score/T4

Each token may make **5 submissions per task**; a submission the scorer rejects counts. The
sixth returns `{"capped": true}`.

## Getting a token

Email contact@scorekey.ai from your work address.

## Run it in two commands

The reference runner is the ENV0 harness used for the runs on the Research page, cut down to these
three tasks and to this repository alone. A lab that runs it gives its model what every model in
those runs was given.

    git clone https://github.com/Scorekey/env0-demo.git && cd env0-demo

    export SCOREKEY_MODEL_KEY=<your model API key>
    python3 run_demo.py --packet . --model <name> --out runs/<name>
        # gpt models: add --transport responses; see the transport table

    export SCOREKEY_TOKEN=<your scorer token>
    python3 submit_demo.py --answers runs/<name> --url https://scorekey-env0.fly.dev

**Requirements.** Linux, run as root: the model's Python runs in a mount and PID namespace holding
only its own task and the data, and the runner refuses to start where it cannot make one. Python 3
standard library only; tested on 3.11.

**Where that works, and where it does not.** A VM works: WSL2, a cloud VM, a Fly machine. Hosted
agent sandboxes (Codex's cloud sandbox among them) and most CI runners cannot create the namespaces,
and the runner refuses there rather than scoring in a weaker sandbox. A container works only if it
is started privileged:

    docker run --privileged --rm -it -v "$PWD":/env0 -w /env0 \
      -e SCOREKEY_MODEL_KEY -e SCOREKEY_TOKEN python:3.12-slim \
      python3 run_demo.py --packet . --model <name> --out runs/<name>
        # gpt models: add --transport responses; see the transport table

(`-e VAR` with no value passes the variable through from your shell, so the key is never in the
command line.)

**What the runner does.** One conversation per task, in the order T4, full chain, mid-start; the
system message, the task page, then the menu; four tools (`list_dir`, `read_file`, `run_python`,
`submit_answer`); tool results cut at 24,000 characters; a cap of **120 turns** per task
(`--max-turns`). Transport errors are retried. A conversation the provider refuses with an HTTP 4xx
is re-run once as a fresh conversation (the first is kept as `<task>__attempt1`); a second 4xx
stands as no submission. No temperature, seed or reasoning parameter is sent; on the Anthropic API,
which requires `max_tokens`, the model's documented maximum is sent (the runner lists each figure
with its source page). For a Claude model it holds no figure for, pass `--max-tokens N` with the
model's documented maximum; RUN.json records it as operator-supplied. It refuses to run if the packet does
not check against `MD5SUMS.txt`, if `SCOREKEY_MODEL_KEY` is unset, or if the sandbox would hold more
than one task. The key is read from that variable only and is never written.

**The model gets the interpreter that runs the runner, and no packages of its own.** The sandbox
holds this task's files, the data and that interpreter; the runner installs nothing. The host of the
runs on the Research page carried the standard library only, so every model did the work with `csv`,
`gzip` and `json`, and a model that reaches for pandas there gets an ImportError. ★A host with
pandas, numpy or openpyxl already installed lends them to the model through the same interpreter,
and the run is then not the run those figures came from. To match them, run on a bare interpreter —
the `python:3.12-slim` container above, or a VM with nothing added to the system Python.

It writes `runs/<name>/T4.json`, `full-chain-from-T1.json` and `mid-start-from-T3.json` (the model's
`submit_answer` bodies, exactly), `RUN.json` (model, endpoint host, transport, the md5s below, turns,
how each task finished, token usage), and the full response of every turn.

`submit_demo.py` checks each answer is one JSON object carrying the key its own task's answer
template asks for — `commitments` for all three tasks in this packet — before sending it, because
every submission the scorer takes, scored or rejected, counts against your five per task. It prints
each response and saves it as `<task>.response.json`.

**Transport.** `--transport chat` (default) is an OpenAI-compatible `/v1/chat/completions`;
`--transport responses` is OpenAI's `/v1/responses`; `--transport anthropic` is Anthropic's
Messages API (`/v1/messages`, key in `x-api-key`). `--base-url` points any of them at another
endpoint. A `claude-` model must use `anthropic`, and `anthropic` only takes `claude-` models. The
runs on the Research page used, per model:

| model            | transport                                         |
|------------------|---------------------------------------------------|
| gpt-5.6-luna     | `responses`                                       |
| gpt-5.6-sol      | `responses`                                       |
| gpt-6-astra      | `responses`                                       |
| gemini-3.8-flash | `chat` (Google's OpenAI-compatible endpoint)      |
| claude-fable-5-1 | `anthropic`                                       |

The gpt-5.6 models refuse function tools on chat completions; use `--transport responses` for them.

**The harness, by md5** — match these to the Research page:

    run_env0_campaign.py      da47a0e373b9494233aa4f28ab9ac8fa   the harness those runs used
    tool loop (fenced region) 39504313a53c61b7a559002738ea9303   re-hashed at every start-up
    sandbox_exec_env1.py      7802cb28466280e9a84a8e651b6d88cd   the isolated runner, unchanged
    run_demo.py               7786dcab11fda473e6586a957cd7cd61
    submit_demo.py            14ce9dd0392606935c70eebd869bc856

`TOOLS_MD5SUMS.txt` lists this README and the three scripts, and `md5sum -c TOOLS_MD5SUMS.txt`
checks them as it stands. `MD5SUMS.txt` is this packet's own manifest — it is recut whenever the
tasks change — and it lists the packet's **63 files: 55 data files and 8 task files** (the three
task pages, their menus and `CHAIN_DELIVERY_README.md`) under a `packet/` prefix while they sit here
at the repository root: `md5sum -c MD5SUMS.txt` therefore fails on every line until the prefix is stripped. Check it
with

    grep '  packet/' MD5SUMS.txt | sed 's#  packet/#  #' | md5sum -c -     # 63 OK

`run_demo.py` does this check itself, against the same manifest, before it makes any call.

**What differs from the runs on the Research page.** The data folder carries
`landscape/ATTRIBUTION.txt` and one added line in `landscape/README.txt` (the ECB's terms of reuse,
added for publication). Each transport follows the harness its own models ran on:

| transport   | empty turn re-requested once | timed-out call stops, not retried | as the harness of   |
|-------------|------------------------------|-----------------------------------|---------------------|
| `anthropic` | yes                          | yes                               | claude-fable-5-1    |
| `chat`      | yes                          | no                                | gemini-3.8-flash    |
| `responses` | no                           | no                                | the gpt models      |

An empty turn is an assistant turn with no text and no tool call; the re-request is the identical
request, with nothing added.
