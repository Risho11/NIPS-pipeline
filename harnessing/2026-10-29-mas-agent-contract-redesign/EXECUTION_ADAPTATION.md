# User-selected execution adaptation

## Observed constraint

The repository has 16,150 tracked files totaling 10,662,289,554 working-tree bytes.
The pinned manager retains tracked WorktreeCapture.content in status evidence and
keeps an initial snapshot while constructing its second preview generation
(harness_manager.py tracked_worktree_status and reviewed_lifecycle_preview).
Two raw generations alone total 21,324,579,108 bytes (19.86 GiB), before copies,
normalization, probes and Python overhead.
Read-only sysctl reports physical RAM 19,327,352,832 bytes (18 GiB).
Execution would therefore depend on compression/swap or exceed practical memory;
the source/resource investigation is not an observed OOM or successful preview.
No new actual-checkout manager preview has been launched.

## Work already completed

An independent persistent top-level Writer verified the human authorization,
same Worktree and governing source. It is quiescent and has no product mutation
ownership while activation is unresolved.
Fresh independent QA accepted exact preservation of 33 scoped files, excluding
measured data and Harness plans. On codex/261030-mas-agent-contracts, commit
7c69df0a preserves that unaccepted baseline; it does not accept old MAS behavior.
The original source parent remains in history. No submodule, shared-source edit,
model call, robot call or physical experiment occurred.

## Recommended bounded alternative

Retain the existing eight-step plan, external shared instructions, explicit
Controller/Writer separation, literal ownership, original-data protection,
fresh independent semantic QA, meaningful validation and mandatory-last DCP.
Use controller-reviewed native Git commits with explicit file staging and
post-commit receipts instead of the canonical manager's full-worktree snapshot
transactions for this task.

Track status honestly in a human-readable EXECUTION_STATUS.md: pending step,
actual commit, applicable validation, QA verdict and outstanding limitations.
Do not create or simulate the canonical progress.json, transaction fingerprints
or manager PASS. Keep a separate explicit MANUAL_GIT_TRANSITIONS mode annotation
so future sessions cannot mistake this for canonical runtime adoption.
Use ordinary Git's change detection plus reviewed changed-file contents and
the literal staged set. Do not copy all archived measurements into Python.
Leave the external source/governor untouched; this is a user-approved local
execution exception, not a changed shared rule or a silent compatibility layer.

The acceptance objective is unchanged: substantive main/specialist AGENTS/docs,
adaptive question-led analysis, three scientific QA roles, four flexible reports
and a small isolated real-data next-point pilot. Production adapter integration
remains outside this Harness.

## Alternative requiring broader scope

Improve resource behavior of the shared manager in its own repository with
independent review and tests, then explicitly adopt a new governor version
before this work resumes. That changes a separate repository and is not covered
by the current target-worktree file ownership. No shared code has been edited.

## Decision boundary

The current pinned harness-runtime rule requires separately reviewed canonical
previews/fingerprints for every manager mutation. The user answered the execution-choice question with “커밋은 하네스 시스템을 안쓰고 작업할 순 없니”. In the context of the approved Goal and Controller/Writer plan, this selects ordinary Git commits. MANUAL_GIT_TRANSITIONS is now the local execution method; the shared manager remains inactive. Literal Writer handoff and independent QA still gate each product step.
