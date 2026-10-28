# Campaign connection recovery

Deploy both sides together while the campaign is stopped:

- OT-2: copy `OT2_Server_2026-06-11/protocol-multithreaded.py` and
  `OT2_Server_2026-06-11/lib/request_server.py` to their corresponding robot locations.
- Windows: use the updated `src/pipeline/url_29.py`, `run_loop.py`, and
  `membrane_quality_llm.py`.

Keep `opentrons-robot-server` stopped while the standalone campaign controls hardware.
Start the robot campaign normally (startup initializes hardware and homes the robot).
Keep its terminal open and preserve its logs. These changes do not restart a crashed
robot process or repair Ethernet/DNS failures.

## Health check

`GET http://169.254.46.48:8000/health` is read-only: it does not move hardware or
change experiment state. It identifies the server and its persistent request journal.
It confirms the HTTP service is available, not that every hardware device is healthy.
Windows checks it before submission, with up to five attempts (60-second network
timeouts and 375-second waits between attempts, approximately 30 minutes if all
five connection attempts time out). Immediate connection failures finish sooner;
success proceeds immediately. Old servers without this endpoint are rejected;
there is no fallback to unprotected POSTs.

## Submission and duplicate protection

Every logical submission uses a UUID in `X-Request-ID`, with `X-Journal-ID` binding
it to the robot's journal. Retries reuse those values. The robot saves the request
ID and parameter digest to `request_journal.json` beside the protocol **before**
starting its worker, and starts the worker before acknowledging acceptance.
An acknowledgement means accepted, not that fabrication finished.

The robot handles duplicate IDs without starting another worker. Reusing an ID
with different parameters returns HTTP 409. The journal is updated atomically and
flushed to disk. Do not delete, replace, or restore an older copy of this journal
to clear an error: it is the record preventing duplicate physical experiments.

Connection refusal/name-resolution failures are logged as `before-send`; generic
timeouts and broken connections are conservatively `outcome-unknown`. Both get
at most three POST attempts (30-second network timeouts, 1- and 2-second backoffs),
with a health check before every attempt. Ambiguous retries are permitted only
against the same verified journal and request ID. HTTP rejection is not retried.

For next-experiment submissions from processed conditions, the Windows
`.pipeline_state.json` stores `submission_request_id` and `submission_journal_id`
before the POST. Restart the same campaign to reuse these IDs and completed work.
Initial/manual `run_test()` callers also get bounded, protected retries within that
call, but must supply a persisted request ID and journal ID for recovery across
process restarts. Do not blindly restart an ambiguous initial/manual submission.

If the robot restarts with an unfinished request, that ID is blocked for manual
inspection; it is never automatically rerun. Failed workers are also blocked.
A completed request remains deduplicated across robot restarts. A new journal
identity is rejected by saved Windows checkpoints. Persistence errors stop further
acceptance until investigated. This provides at-most-once dispatch, not automatic
completion after a robot crash.

Old checkpoints containing `submission_started` without a request ID still require
manual verification; the software cannot retroactively determine whether the old
server accepted them. No existing checkpoint is migrated or cleared automatically.

## Quality reports

Experimental text reports and active-learning recommendations use a separate
five-attempt connection retry policy: 60-second SDK network timeouts and 375-second
waits between attempts (about 30 minutes if all five time out; immediate DNS errors
finish sooner). Only the failing API call repeats, with the same model and prompt;
curve processing and robot submission are not part of this retry loop. SDK retries
are disabled for these calls. Authentication and other HTTP errors fail immediately.
Connection retries can repeat provider work/charges after an ambiguous timeout.
Restart the Windows pipeline to load this policy. Test it without API calls using
`python tests/test_llm_retry.py`.

OpenRouter quality-report connection/timeouts get three attempts with 1- and
2-second backoffs and a 60-second SDK network timeout. SDK built-in retries are
disabled to prevent multiplying attempts. Authentication, validation, and other
HTTP errors are not retried by this loop. Timeouts can duplicate provider work or
charges even though they cannot duplicate robot actions. On exhaustion, processing
stops with its checkpoint retained; restore internet/DNS/proxy connectivity and
resume the same campaign. No API credentials or images are printed by retry logs.

## Verification

Run `python tests/test_network_recovery.py` on Windows or Linux. Tests use loopback
HTTP and mocked robot/API calls; they never connect to the OT-2 or OpenRouter.
