# MAS development Harness — ordinary Git commits

Mode: MANUAL_GIT_TRANSITIONS, selected by the human after Goal approval.
Topology: STANDARD_CONTROLLER_WRITER. Controller owns planning, review, progress
and ordinary Git transitions. One verified independent persistent top-level
Writer in this exact Worktree owns only its current literal product paths.
Independent development QA stays read-only.

## External source and local exception

Configure NIPS_SHARED_AGENT_ROOT to the existing external shared checkout.
EXTERNAL_SOURCE.json pins the guidance version; do not copy shared skill bodies,
edit shared source or add a submodule. The user's exception replaces automatic
manager commits with native Git. Retain planning, ownership, independent QA and
mandatory-last DCP guidance. Do not run canonical init/update/get or simulate
its progress.json/fingerprints. init-input.json and canonical-fixture checks
are historical planning evidence, not active execution instructions.

## Active execution procedure

1. Controller binds the pending step to verified Writer identity, current
   branch/HEAD and literal product paths. Writer verifies human authority.
2. Writer implements only those paths, validates and becomes quiescent. It
   returns evidence and a proposed payload, never stages/commits or edits status.
3. Fresh independent QA reviews the entire changed contract, source evidence,
   useful scientific behavior and relevant dependencies. Repair requires bounded
   ownership return and fresh acceptance of the repaired candidate.
4. Controller freezes accepted files, checks Git status, stages only literal
   paths plus its scoped receipt, and inspects git diff --cached --name-only
   and git diff --cached --check. No broad staging/reset/stash.
5. Controller commits with YYMMDD-HH-MM feat/test/fix/docs, verifies actual commit
   paths and bytes, and preserves unrelated work. No remote/hardware action.
6. EXECUTION_STATUS.md records evidence. QA_ACCEPTED means independent review
   passed; completion additionally requires the listed native Git receipt.
   Receipt subjects identify actual history without a self-referential hash.
7. Final DCP reconciles accepted contracts, actual pilot evidence and limitations
   after all predecessors, independent QA and a verified ordinary Git commit.

## Sources and limits

Read REQUIREMENTS.md, IMPLEMENTATION_PLAN.md and the pending prompt. Read
ACTIVATION_REVIEW.md and EXECUTION_ADAPTATION.md for local authority.
PLANNING_REVIEW.md is historical planning QA, not product/pilot acceptance.
No full-application docs skeleton, unrelated hooks/scaffold, .env or
.worktreeinclude is needed. Use uv for Python. Ground domain guidance in real
source/data. The pilot is isolated/report-only; production migration is separate.

## Bootstrap

Branch codex/261030-mas-agent-contracts; preservation commit 7c69df0a retains the
33 independently checked old WIP/routing files, not acceptance of old MAS behavior.
Measured data and Harness plans were excluded. Writer identity/authority and
same-Worktree preflight passed; product writing awaits the literal step handoff.
