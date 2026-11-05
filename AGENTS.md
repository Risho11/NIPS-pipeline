# NIPS pipeline guidance

- Use `uv` for Python dependencies and `uv run` for project commands.
- Preserve measured data and existing legacy search modes. Never substitute an
  inferred value for a measurement or silently change operator material settings.
- Repository development and the experiment MAS are separate workflows.
- Python MAS development uses the external-reference Harness
  `harnessing/2026-11-04-mas-python-runtime/README.md` with
  `STANDARD_CONTROLLER_WRITER`, its requirements, plan and external-source binding.
  The earlier `harnessing/2026-10-29-mas-agent-contract-redesign/` remains historical
  scientific-contract development evidence, not the current implementation ledger. Resolve shared skills through
  `NIPS_SHARED_AGENT_ROOT`; do not add a submodule or copy shared skill bodies.
- The user has authorized Goal execution of the reviewed Harness plan. Product
  execution requires a verified independent persistent top-level Writer in this exact Worktree and
  controller-approved literal step ownership. A generic subagent is not a Writer.
- The user selected ordinary Git commits instead of the shared automatic commit
  manager. Keep the plan, Controller/Writer ownership, independent QA and final
  DCP; use explicit-file Git staging and commit verification. Do not run the
  canonical manager or create its progress.json/fingerprint records for this task.
- The controller records progress in the selected workspace's EXECUTION_STATUS.md.
- Preserve pre-existing uncommitted implementation. Planning files do not prove
  Harness initialization, QA acceptance, production support or step completion.
- Dynamic experiment turns use `docs/mas/workflow.md` and
  `docs/mas/data-contract.md`. Its explicit delegation instructions apply only to
  those turns, not to every code-development task.
- An authorized MAS invocation uses this existing repository: shared material
  topics live at `data/knowledge/<material>/`, and campaign work/state at
  `data/results/<actual-campaign-key>/mas/`. Scientific agents write only their
  current `rounds/<operation>/attempt-<n>/` and scratch; source, original data,
  canonical topics, Git, checkpoints and native/auth state are host-owned.
  Python alone publishes exact reviewed adoptions and a stable checkpoint through
  a private Git index and compare-and-swap; never initialize a nested/output Git.
  This bounded runtime publication does not grant development Writer ownership.
- Only SDK children use this root as `CODEX_HOME`; the desktop app keeps its own
  home. Runtime suppresses automatic AGENTS discovery and explicitly supplies
  scientific role owners. Do not edit/read native authentication or session files
  as scientific evidence. Home/profile/auth behavior needs separate live evidence;
  cloning tracked checkpoints does not recreate native sessions or grant login.
- Do not run the hardware loop, contact the robot, or launch a physical experiment
  as part of development validation. Use mocked clients and temporary data.
