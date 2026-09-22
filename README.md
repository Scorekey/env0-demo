# ENV0 — a demonstration packet

Source: ECB statistics.

Three papers from ENV0, an evaluation of how a model works with published payment statistics, put
here so that a lab can run its own model against them: **T3**, **T4** and **the full chain from
T1**.

This repository is the packet exactly as a lab receives it: the three prompt pages with their
menus, and the data landscape — the thirteen ECB payment-statistics dumps of the 10 July 2026
snapshot, and the three ECB SPACE respondent files (waves 2019, 2022, 2024) with their codebooks.
`landscape/ATTRIBUTION.txt` names the ECB's terms of reuse and publishes every data file's md5.
There are no answer keys here; scoring is done by the service below.

## The scorer

    https://scorekey-env0.fly.dev

    POST /score/T3
    POST /score/T4
    POST /score/full-chain-from-T1

Send the submission JSON as the request body and your token in the `X-ENV0-Key` header:

    curl -X POST -H "X-ENV0-Key: <your token>" --data-binary @T3.json https://scorekey-env0.fly.dev/score/T3

Each token may make **5 submissions per task**; a submission the scorer rejects counts. The
sixth returns `{"capped": true}`.

## Getting a token

Email vm@scorekey.ai with the name of your lab.

## Run it in two commands

The reference runner is the ENV0 campaign harness, cut down to these three papers and to this
repository alone. A lab that runs it gives its model what every model in the campaign was given.

    git clone https://github.com/Scorekey/env0-demo.git && cd env0-demo

    export SCOREKEY_MODEL_KEY=<your model API key>
    python3 run_demo.py --packet . --model <name> --out runs/<name>

    export SCOREKEY_TOKEN=<your scorer token>
    python3 submit_demo.py --answers runs/<name> --url https://scorekey-env0.fly.dev

**Requirements.** Linux, run as root (a VM or a privileged container): the model's Python runs in a
mount and PID namespace holding only its own paper and the data, and the runner refuses to start
where it cannot make one. Python 3 standard library only; tested on 3.11.

**What the runner does.** One conversation per paper, in the order T3, T4, full chain; the system
message, the paper, then the menu; four tools (`list_dir`, `read_file`, `run_python`,
`submit_answer`); tool results cut at 24,000 characters; a cap of **120 turns** per paper
(`--max-turns`). Transport errors are retried; a model answer is never re-requested. No
temperature, seed, reasoning or token-limit parameter is sent. It refuses to run if the packet does
not check against `MD5SUMS.txt`, if `SCOREKEY_MODEL_KEY` is unset, or if the sandbox would hold more
than one paper. The key is read from that variable only and is never written.

It writes `runs/<name>/T3.json`, `T4.json` and `full-chain-from-T1.json` (the model's
`submit_answer` bodies, exactly), `RUN.json` (model, endpoint host, transport, the md5s below, turns,
how each paper finished, token usage), and the full response of every turn.

`submit_demo.py` checks each answer is one JSON object with a `commitments` list before sending it,
because every submission the scorer takes, scored or rejected, counts against your five per paper.
It prints each response and saves it as `<paper>.response.json`.

**Transport.** `--transport chat` (default) is an OpenAI-compatible `/v1/chat/completions`;
`--transport responses` is OpenAI's `/v1/responses`. `--base-url` points either at another
endpoint. The campaign ran each model on:

| model            | transport                                         |
|------------------|---------------------------------------------------|
| gpt-5.6-luna     | `responses`                                       |
| gpt-5.6-sol      | `responses`                                       |
| gpt-6-astra      | `responses`                                       |
| gemini-3.8-flash | `chat` (Google's OpenAI-compatible endpoint)      |
| claude-fable-5-1 | Anthropic Messages API, which this runner does not speak |

The gpt-5.6 models refuse function tools on chat completions; use `--transport responses` for them.

**The harness, by md5** — match these to the Research page:

    run_env0_campaign.py      da47a0e373b9494233aa4f28ab9ac8fa   the campaign harness it is cut from
    tool loop (fenced region) 39504313a53c61b7a559002738ea9303   re-hashed at every start-up
    sandbox_exec_env1.py      7802cb28466280e9a84a8e651b6d88cd   the isolated runner, unchanged
    run_demo.py               557622a1a7512f0c5a6fa42078292611
    submit_demo.py            e52bed001ff3965cc41661a30458136a

`TOOLS_MD5SUMS.txt` lists this README and the three scripts; `MD5SUMS.txt` is the packet's own.

**What differs from the campaign runs.** The data folder carries `landscape/ATTRIBUTION.txt` and
one added line in `landscape/README.txt` (the ECB's terms of reuse, added for publication). The
campaign re-ran a conversation once if the provider refused it with a 4xx; this runner does not.
