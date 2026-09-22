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
