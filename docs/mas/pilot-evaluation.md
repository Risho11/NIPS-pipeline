# Isolated agent-contract pilot and evaluation

## Status and purpose

Live scientific evaluation: **NOT_RUN** in Phase 3 Step 1. Offline checks exercise
isolation, output/condition validation and interruption using mocks. They do not
establish that agents reason usefully, delegate correctly in a real runtime,
inspect evidence or conduct independent scientific QA. Phase 3 Step 2 owns the
actual case-bound execution and human/independent evaluation.

[mas_agent_pilot.py](../../scripts/mas_agent_pilot.py) prepares copied evidence
outside the repository and, only with `--live`, starts one native Codex main
thread/turn. Main chooses questions, delegates to the six scientific author/QA
roles, may return upstream and writes research artifacts. It does not use the
old fixed-four-request production adapter. No robot/client/export module is
imported or called. Run is a scientific recommendation only; there is no equipment
submission path. Production modes, settings and adapters remain unchanged.

Use the accepted [workflow](workflow.md), [data contract](data-contract.md),
[analysis methods](analysis-methods.md) and
[campaign-main contract](../../subagents/campaign-main/AGENTS.md). Reports remain
flexible research records, not four irreversible file-existence gates.

## Cases and cutoff

The first live case proposed for Controller review is the full current October
campaign prefix through this exact condition:

`16-0add-5deg-cosolv-none-bathSolv-PolarClean-10wt-250s-N2-1600s`

Source: `data/results/begins_2026-10-15/`. At this planning snapshot the prefix
contains 58 promoted rows, 64 corresponding aggregate rows and 232 specimen rows.
It includes later 10 wt% bath-solvent observations as well as earlier 0 wt% bath
history; restricting the case to the first 32 rows would omit the later context.
The script permits up to 64 unique promoted conditions and records the exact
selected identities/counts in `inputs.json`. Matching aggregate variants and
specimens retain their source numerical values; `_runN` is not stripped or
automatically treated as independence.

The cutoff is promoted row order, not a timestamp cutoff or blinded prospective
backtest. Acquisition dates span multiple days despite the folder name. Generated
`initial_report`, `final_report`, `LLM_suggestion` and `mas_report_path` columns
are excluded from copied tables to avoid replaying prior agent decisions as new
reasoning. Quality context and measurements remain. No warm-start export or raw
curves are copied automatically. Agents must disclose absent sources rather than
claim those were inspected. The copied source code can explain measurement
semantics; it cannot supply missing empirical curves or physical context.

A later optional contrast case can use the same campaign through
`15-0add-8deg-cosolv-none-bathSolv-none-0wt-200s-N2-1500s` (12 promoted rows), with
an explicit 10 wt% current bath scenario to examine whether main qualifies
historical extrapolation or holds. This is a separate case requiring its own
reviewed context/run decision, not a second automatic live run. No broad benchmark
or guarantee of future measured performance is required.

## Explicit case context

The CLI requires a JSON file with objective, scientific question, operator-context
basis, all five material/bath fields, every composition field for the selected
stock layout and an explicit additive lock or null. Source defaults never silently
fill missing settings. The following is a reviewable report-only scenario based
on the source snapshot; it does **not** confirm installed physical materials:

```json
{
  "objective": "Improve reproducible elastic modulus and compression-estimated pore fraction within feasible conditions and acceptable quality; explain tradeoffs without invented weights.",
  "question": "Using the supplied observations, identify the evidence gap, maintain testable hypotheses and recommend one defensible next condition or hold/stop. Distinguish historical 0 wt% and current-scenario 10 wt% bath context, justify explore/optimize/repeat, and preserve uncertainty and actual QA findings.",
  "operator_context_basis": "Report-only source-settings scenario reviewed for the pilot; not confirmation of installed bottles or prepared bath.",
  "materials": {
    "polymer_type": "Polysulfone",
    "solvent_type": "PolarClean",
    "cosolvent_type": "none",
    "nips_bath_solvent": "PolarClean",
    "nips_bath_solvent_wt_percent": 10.0
  },
  "stocks": {
    "stock_mode": "two_bottle",
    "polymer_stock_wt_percent": 17.0,
    "additive_stock_polymer_wt_percent": 17.0,
    "additive_stock_additive_wt_percent": 4.0
  },
  "locked_additive_wt": 0.0
}
```

For a later real operator-context claim, use operator-confirmed inputs and record
their basis. A historical condition need not be executable under current stocks.
Null/hold is legitimate if the evidence or constraints do not justify a point.

## Preparation, live invocation and stop controls

From the repository root, save the reviewed context to a chosen scratch-input
path. Use a new output directory outside, and not an ancestor of, the repository.
The following **prepares only** and does not initialize/start the SDK:

```sh
uv run --locked python scripts/mas_agent_pilot.py \
  --campaign data/results/begins_2026-10-15 \
  --through-name 16-0add-5deg-cosolv-none-bathSolv-PolarClean-10wt-250s-N2-1600s \
  --context /private/tmp/nips-mas-pilot-context.json \
  --output /private/tmp/nips-mas-pilot-review
```

After independent P3S1 acceptance and Controller's literal P3S2 execution handoff,
the same command with a **different new output directory**, `--live` and
`--max-seconds 1200` performs the actual case. Record the complete actual command,
context, cutoff and outcome in the evaluation report. Existing output directories
are never overwritten/resumed by this entry point. Retain interrupted/failed runs
and select a new directory for an authorized retry.

Budget: initially one live case, one main turn, at most two concurrently open
native specialists, and a prompt instruction to aim for at most 12 specialist
activations/follow-ups including repair. That instruction is not an enforced
count of internal model calls or a financial/token cap. Inherit the configured
default model/reasoning settings; no per-role overrides are set. A 1200-second
wall deadline (CLI maximum 1800) stops the local SDK process group. Ctrl-C also
interrupts it. Time/budget exhaustion must remain incomplete/hold evidence, never
be reported as scientific success or a fabricated QA pass. Main's SDK usage is
recorded when supplied; it is not an aggregate accounting of all child usage.

The worker is internal and also requires explicit `--live`. No live SDK constructor
is reached by default preparation or offline tests. Authentication uses the
existing configured Codex login; this tool does not change credentials. The worker
requires SDK version 0.163.0 and explicitly uses that installed dependency's bundled
CLI for both offline configuration probes and the SDK itself, not a different
runtime executable.

## Scratch boundary and inspectable outputs

The scratch root contains selected tables at their original relative paths,
copied domain/role guides, numeric/source context, `context.json` and `inputs.json`.
Source copies include measurement/bounds/adapter-schema reference code, including
`run_loop.py` for reading only; agents must never import or execute that file.
No venv, robot client, production adapter or export implementation is copied.

`work/` is the SDK CWD and configured writable scientific workspace. Its root
AGENTS explicitly activates scientific main and distinguishes specialists from
development Controller/Writer. Six copied project bindings resolve role paths
against `PILOT_ROOT`. Inputs/reference code sit outside CWD. Parent SDK settings
request workspace-write only, no additional writable roots, no generic `/tmp` or
external TMPDIR write grant, no command network, no approval escalation and no
app/plugin exposure. An empty `mcp_servers={}` table does not disable inherited
MCP definitions. Before SDK construction, the worker uses the same bundled CLI,
CWD, literal overrides and environment to run offline `mcp list --json`. It adds
an explicit `enabled=false` for every effective server name in a merged TOML
server table (`mcp_servers={"name"={enabled=false},...}`), then runs the same
inspection again. Keys are quoted inside the TOML value rather than inside the
CLI's dotted override path. An active server, changed name set,
failed probe or incomplete listing aborts before main starts. The supported
per-server setting is documented in the
[official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
No hardcoded machine server allowlist is used. Raw MCP configuration, commands,
endpoints and environment values are discarded; only name/enabled pairs appear
in `mcp-preflight.json`, and probe failures return generic errors.
The dynamic trust entry also uses a top-level `projects={"absolute/path"={...}}`
table, so quotes or dots in a scratch path do not bind a different project key.
Read-only CLI checks can verify trusted project-config loading before any SDK
construction; they do not themselves establish live custom-agent discovery.

Specialists inherit parent permissions; their instructions do not create a
separate OS sandbox. Managed runtime policy can refuse settings; there is no
full-access fallback. Offline effective-MCP verification does not start an MCP
server, app-server or model. Actual sandbox enforcement and role discovery remain
unverified until the live step. The preflight verifies the configuration visible
at launch, not immunity to later external configuration changes.

Analysis/review subdirectories under `work/` hold authored artifacts and separate
reviewer notes. Reviewers preserve author candidates. Main keeps a readable index
linking the four records, scripts/figures, actual scientific reviewer results,
revisions and missing evidence. Use the existing repo interpreter for scientific
libraries without copying/symlinking its environment:

```sh
uv run --offline --no-project --python /absolute/repository/.venv/bin/python python analysis.py
```

The generated instruction supplies the actual absolute interpreter path. Cache,
Matplotlib configuration and temporary command files are redirected into `work/`;
bytecode writes are disabled. Preserve source measurements and operator settings.

SDK transport evidence outside `work/`: `sdk-final-response.txt`, `sdk-items.jsonl`,
`sdk-process.log` and `execution.json` retain ordinary response/items, thread ID,
available usage and execution status. Items can expose actual reviewer messages
and artifacts without a new parentage verifier. The small final action schema
contains action, eight tunables or null, reason and relative index path. Python
checks output placement, finite ranges, stock polygon, lock and undiluted stock.
It does not parse report prose, independently match design-QA conditions, verify
reviewer independence or certify scientific usefulness. Those require inspection
of actual reports/reviewer results. `COMPLETED_UNREVIEWED` is therefore deliberately
not a scientific PASS; `FAILED_NON_PASS`/`INTERRUPTED_NON_PASS` stay non-passing.

## Evaluation after actual execution

Follow original inputs, calculations/figures and review findings, not just main's
final summary. Judge whether evidence led to an appropriate hypothesis and next
point or justified hold/stop; whether alternatives and unknown provenance/quality
were handled; why explore/optimize/repeat was chosen; whether artifacts resolved
the question; and whether independent QA found, repaired or qualified reasoning.
Inspect that the final recommended conditions equal the reviewed design and
respect the explicit case constraints. Do not infer QA from filenames alone.

Record accept/revise with concrete evidence and limits in the planned
`harnessing/2026-10-29-mas-agent-contract-redesign/reports/PILOT_EVALUATION.md`.
No previous prediction, absent raw curves, missing independent replication,
unexercised upstream returns and untested cases remain explicit coverage gaps.
Do not equate a polished report, valid point, mock SDK outcome or completed local
turn with real scientific acceptance or production support.
