# Adaptive Python campaign runtime

This foundation exposes a report-only API and CLI. The existing operational loop
still uses its older adapter until the separate integration/cleanup step. This
runtime never imports the operational loop or request client and never submits
experiments. Mocked tests establish software boundaries, not scientific usefulness,
actual SDK connectivity, sandbox enforcement, Windows execution or device readiness.

## Public API and explicit binding

The three owners are [mas_contract.py](../../src/pipeline/mas_contract.py) for small
operational types, [mas_workspace.py](../../src/pipeline/mas_workspace.py) for files,
independent Git and recovery, and [mas_runtime.py](../../src/pipeline/mas_runtime.py)
for persistent Main and native review validation.

```python
from pathlib import Path
import sys

# Replace these paths with approved invocation bindings. Run this code using
# uv run --locked --no-sync python from the already prepared project checkout.
project = Path('/absolute/path/to/NIPS-pipeline').resolve()
sys.path.insert(0, str(project / 'src/pipeline'))
from mas_contract import Context
from mas_workspace import Workspace
from mas_runtime import CampaignRuntime

context = Context.model_validate_json(
    Path('/private/tmp/mas-runtime-synthetic-context.json').read_text(encoding='utf-8'))
workspace = Workspace('/private/tmp/mas-runtime-synthetic-output', project, 'synthetic',
                      protected_roots=[Path('/absolute/protected-measurement-root')])
runtime = CampaignRuntime(workspace, context)
# Construction above is read-only. Only an authorized model invocation calls:
# result = runtime.run()  # theory bootstrap or a bounded HOLD/STOP
```

The context JSON contains `campaign`, `objective`, `materials`, `stock_metadata`
and `locked_additive_wt` (explicit number or null). `materials` contains the five
operator polymer/solvent/cosolvent/bath fields from the
[data contract](data-contract.md#conditions-operator-authority-and-decisions).
Stock metadata must explicitly specify `stock_mode` and every corresponding
`OldStockStruct` or `StockParameters` percentage. There are no installed-stock or
operator-material defaults. Component totals cannot exceed 100 wt%. Preserve
endpoint preferences/constraints separately from uncertain forecasts and weights
in the supplied objective. `material_key` and campaign names are portable simple
identifiers; they cannot contain separators or Windows reserved device names.

Bind one independent output root outside source, other repositories and protected
original-data roots. Source and observations stay read-only; put disposable test
outputs outside the checkout too. Constructor and CLI preparation do not create
an SDK client. `protected_roots` is an explicit API argument: supply every original
measurement/protected root whose overlap must be rejected. There is no automatic
discovery of those roots. The CLI has **no protected-root option** and does not
derive them from context or `--input`. It checks source/repository separation;
the operator must additionally establish output separation from all protected data
before using it. Use the API above when programmatic protected-root enforcement
is required. Later input binding rejects input files inside output, but that is
not a preflight check for every data root. The five role bindings are copied to the output
root's `.codex/agents/`, while `PILOT_ROOT` resolves their documents to source.
No shared skill bodies, source tree, environment or original measurements are copied.

## Main, knowledge and native review

Main follows the current [workflow](workflow.md), [knowledge](knowledge.md) and
[analysis](analysis-methods.md) contracts. It chooses methods, artifacts, questions,
revisions and actual analyst split triggers. Python does not run a fixed scientific
stage list, require hypothesis IDs, generate a figure roster or grade causal claims.
Main can reuse registered author/reviewer sessions; identities must stay distinct.

Knowledge is stored in `data/knowledge/<material>/concentration.md`,
`prebath_exposure.md`, `bath_temperature.md` and `bath_residence.md`. Before any
observation binding is read or revealed, a bootstrap must publish all four reviewed
theory/provenance topics. Actual automatic exposure must be disclosed; a new thread
is not a guarantee of blindness. A bootstrap HOLD/STOP has null knowledge commit,
no executable conditions and does not unlock observations. It survives restart;
explicit reconsideration can attempt initialization again when its reason is supplied.

After bootstrap:

```python
result = runtime.run(observation_id=measurement_event_id,
                     inputs={"selected": selected_csv, "aggregate": aggregate_csv})
```

Use only approved observation files. Python records paths and streaming input
digests, without altering inputs or putting them in Git. An existing observation
ID cannot silently acquire different inputs/context. A no-ID restart may supply
only the exact existing label/path/digest binding (including `{}` only when the
existing binding is empty); new/different/emptied bindings require an observation
ID or explicit reconsideration. A no-argument call reuses the previous result.
A second named campaign supplies its new context and distinct observation ID,
and reuses the same material bank/Main without another theory bootstrap.
The registered integrated
author is `hypothesis-updater`, with independent `hypothesis-qa`; design uses
`experiment-designer` and distinct `experiment-design-qa`. `experiment-analyst`
is optional under actual split triggers, not a prerequisite stage or an extra QA.

Native specialist final answers carry only operational `Contribution`/`Review`
receipts: operation ID, knowledge/design kind, proposal path mapping, exact design
conditions when relevant, knowledge commit and own Markdown report path. Review
also carries pass/fail and author thread ID. Authored reasoning and findings stay
in separate current-round Markdown files. The host checks actual SDK-observed
completion, actual child role/parent metadata and final messages. A Main assertion,
prose PASS, wrong role, self-review, incomplete review or stale operation cannot
authorize publication. Only small operational path/condition receipts are compared;
there is no report-body JSON echo, equality or report-hash acceptance gate.

`MainReply` selects a knowledge adoption or a final decision/design adoption.
`records` explicitly names additional relevant current-round Markdown to preserve.
Native author/review reports and adopted topic proposals are included automatically.
After review, candidates must remain preserved; edits require renewed native
completions. This is a task boundary, not a claim of per-role OS isolation.
Native evidence does not establish the scientific truth of a Markdown claim.

Python publishes exact Main-adopted files on Main's behalf; agents neither edit
canonical knowledge/state nor stage/commit. Topic publication returns `None` and
records an actual knowledge commit. Call `run()` again to continue the same pending
question using that commit. This operational publication boundary lets design name
the committed understanding it actually uses. It imposes no scientific revision quota.

`Decision` contains action, reason, `next_params` and `knowledge_commit`. RUN must
equal the actual independent design-QA conditions and knowledge version. The host
validates finite strict types, numeric bounds, the actual convex hull of supplied
stock compositions and additive lock,
including undiluted-stock mixing temperature; it never snaps a condition. Operator
stocks may coincide or form a point/segment; membership is still bounded by the
available stocks. Arbitrary four-stock layouts need not arrive in polygon winding
order. Membership uses a 1e-8 wt% distance tolerance, without changing the returned
conditions or operator stocks. Operator
fields are not executable agent choices. HOLD/STOP have null parameters. A caller
can combine accepted tunables with the original supplied operator context at its
existing execution boundary, after its own request/journal checks. A report-only
RUN is not authority to call a device.

## Output history and Git

The output root contains `.mas-state.json`, a persistent `.mas.lock`, untracked
role configuration/scratch and `data/results/<campaign>/mas/rounds/<operation>/`.
Round drafts/reviews/artifacts are writable there. Native contributions use a new
`attempt-<number>/` area for each continuation; earlier authored/review paths remain
preserved across retries. Only four canonical topics, actual relevant round
Markdown and the host's `adoption.json` enter accepted Git
history. Paths are individually staged; raw/input/media/cache/secret paths,
escaping paths, symlinks and hard-linked outputs are rejected. Other artifacts
remain untracked; there are no dummy-report quotas or full-bank snapshots per round.

Git runs only in that independent root, with inherited `GIT_*` redirection removed,
global/system configuration disabled and command-local Main identity, disabled
hooks/templates and signing. No remote, branch management, broad staging, reset,
deletion or source-repository Git operation is performed. Direct workspace commits
use `YYMMDD-HH-MM docs adopt MAS knowledge|decision <transaction>` (UTC timestamp).
One stored subject/token survives recovery. Publication is Main adoption carried
out by Python, not independent author/reviewer Git authority.

Unknown staged files, unpublished tracked edits, foreign commits/repositories,
missing history or retired checkpoints fail closed without cleanup. Publication
first persists accepted files and a pending transaction, then writes/stages only
those paths. Failed Git work remains pending. After a lost commit acknowledgement,
recovery checks the actual parent, subject, complete expected file paths, Git blob
contents and regular-file modes before reusing a commit. Before committing, each
accepted path/index entry must still be its original or accepted value; conflicting
edits are preserved and rejected. Missing expected committed files, changed bytes,
mode drift, partial commits or changed recovery payloads cannot advance knowledge
or clear pending evidence. These checks bind a Git transaction to its adopted
payload; they do not grade or hash scientific reports into author/QA receipts.
Ordinary Git preserves adopted versions;
there is no parallel report-cache acceptance system.

## Restart and deliberate reconsideration

`run()` on ordinary restart resumes pending native work on the same Main. It
records the Main ID before work and turn ID before consuming completion. The
operation token in native history covers interruption between turn start and
local ID persistence. A running turn is joined even with `retry=True`. Terminal
failed/interrupted or rejected turns require explicit `retry=True` to request a
new continuation, preserving prior turns/failures. Completed decisions, including
HOLD/STOP, are reused without another model call. Input/context drift is rejected.

```python
result = runtime.run(reconsideration="New evidence changes the question",
                     inputs={"selected": corrected_csv})
```

A substantive reason creates a new operation and preserves old records. An
incomplete operation can be marked superseded only after native history establishes
there is no running turn. Changed evidence after a terminal failure can therefore
be reconsidered without completing an impossible old digest. A genuinely running
or unidentifiable turn is not silently abandoned. Runtime reconsideration does
not resolve an ambiguous physical request: the later caller integration must
preserve its existing request/journal identity before any new device submission.

Workspace writers are serialized using POSIX `flock` or Windows `msvcrt.locking`.
Kernel release handles process exit; lock files are not deleted as stale. Other
platforms fail explicitly. Paths are compared as resolved Path identities, not
Git's raw slash spelling. Actual Windows execution remains separate validation.

## Report-only CLI and validation

Use an **already prepared** project `.venv` with the locked dependencies, including
`openai-codex==0.163.0`, pandas and scipy, and an existing `uv` executable. Launch
from the source checkout with `uv run --locked --no-sync`; do not sync/install,
copy an environment, or allow a Python download to make an invocation work.
The model path also requires pre-existing Codex authentication, service access
and role/project trust appropriate to the bound workspace. Preparation does not
check those prerequisites. This runbook neither performs login/setup nor grants
model-call authority; unavailable prerequisites remain NOT_RUN/error.

Startup binds analysis to the launching interpreter (`sys.executable`/`sys.prefix`)
and existing environment. `UV_NO_PROJECT=1`, `UV_NO_SYNC=1`, `UV_OFFLINE=1` and
`UV_PYTHON_DOWNLOADS=never` prohibit analysis project discovery/sync/download;
use `uv run --no-sync python ...` inside output. Runtime binds `UV_CACHE_DIR`,
`XDG_CACHE_HOME`, `MPLCONFIGDIR` and `TMPDIR`/`TMP`/`TEMP` under output `.scratch/`,
overriding inherited external write targets. Additional libraries that need other
caches must be bound there before use. No cache belongs in the read-only source
or original measurements. Offline scientific-import tests verify this prepared
environment path; they do not verify a live SDK sandbox.

The following **entirely synthetic preparation example** starts no model and no
device. The material names, percentages and objective are illustrative fixtures,
never defaults or suggested settings for an actual experiment. Replace the source
path, choose unused scratch filenames/output, and verify the protected-root
separation described above before using the CLI.

Save this exact JSON as `/private/tmp/mas-runtime-synthetic-context.json`:

```json
{
  "campaign": "synthetic-demo",
  "objective": "SIMULATED demonstration only; no experiment is authorized",
  "materials": {
    "polymer_type": "synthetic-polymer",
    "solvent_type": "synthetic-solvent",
    "cosolvent_type": "synthetic-cosolvent",
    "nips_bath_solvent": "synthetic-bath-solvent",
    "nips_bath_solvent_wt_percent": 10
  },
  "stock_metadata": {
    "stock_mode": "two_bottle",
    "polymer_stock_wt_percent": 17,
    "additive_stock_polymer_wt_percent": 17,
    "additive_stock_additive_wt_percent": 4
  },
  "locked_additive_wt": 0
}
```

```sh
cd /absolute/path/to/NIPS-pipeline
uv run --locked --no-sync python src/pipeline/mas_runtime.py --help
UV_NO_CACHE=1 UV_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 \
uv run --locked --no-sync python src/pipeline/mas_runtime.py \
  --workspace /private/tmp/mas-runtime-synthetic-output \
  --source "$PWD" --material synthetic \
  --context /private/tmp/mas-runtime-synthetic-context.json
```

Required arguments are `--workspace`, `--source`, `--material`, `--context`.
`--context` is the path to a UTF-8 **JSON file**, not inline JSON. The complete
required keys/types are demonstrated above; `locked_additive_wt` must be an explicit
number or null, `nitrogen` in later conditions is a JSON Boolean. There are no
operator-material or stock defaults. Preparation parses context/bindings and prints
`NOT_RUN`; it is not a dependency/auth/connectivity or all-data-root readiness check.
Preparation is the default and creates no output/client.
`--live` explicitly starts/resumes model work within the invocation's authority;
it never starts hardware. Later observations use `--observation-id` and repeatable
`--input LABEL=PATH`; `--reconsider REASON` and `--retry` expose recovery semantics.
For example, after an independently reviewed bootstrap, an authorized later
synthetic observation invocation may add `--observation-id synthetic-event-1
--input table=/private/tmp/mas-runtime-synthetic.csv`. That file must already exist,
be approved for transfer, remain outside output and contain only the intended
synthetic inputs, for example `name,E,F` followed by `SYNTHETIC,1,0.5`. Do not pass
observations to the first bootstrap call. Supplying inputs without a new ID means
exact-binding restart only; it does not create a new observation implicitly.
The existing installed pinned SDK is 0.163.0. Public start/resume/turn/read methods
and generated native models are used without model/reasoning overrides. SDK startup
requests workspace-write at output CWD, denied approvals, network/web/apps/plugins/
memory disabled and verifies each inherited MCP server disabled by name before
constructing a client. Configuration requests are not proof of live enforcement;
the separately authorized synthetic-only SDK smoke remains required.

Offline checks use the existing environment:

```sh
uv run --locked --no-sync python -m unittest discover -s tests -p 'test_mas_contract.py'
uv run --locked --no-sync python -m unittest discover -s tests -p 'test_mas_workspace.py'
uv run --locked --no-sync python -m unittest discover -s tests -p 'test_mas_runtime.py'
```

They use synthetic data, actual temporary Git and SDK-shaped mocks only. This
foundation does not yet remove the older adapter, route run_loop, replace its
tests/CI or establish production/physical acceptance; those are the next bounded step.
