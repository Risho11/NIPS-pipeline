# NIPS pipeline guidance

- Use `uv` for Python dependencies and `uv run` for project commands.
- Preserve measured data and existing legacy search modes. Never substitute an
  inferred value for a measurement or silently change operator material settings.
- Repository development and the experiment MAS are separate workflows.
- Repository development uses the current checkout and local validation. The
  documents under `harnessing/` are historical development records, not active
  execution requirements. External shared skills, `NIPS_SHARED_AGENT_ROOT`, a
  separate Controller/Writer arrangement and final DCP are not prerequisites.
- Preserve historical Harness files, including `EXECUTION_STATUS.md`, as evidence
  of earlier work. Their instructions, ownership records and pending statuses do
  not govern current Goals. Do not rewrite them to track new work; record current
  progress separately when needed.
- Use ordinary Git with explicit-file staging and commit verification. Do not
  run the historical automatic commit manager or create its progress/fingerprint
  records.
- Preserve pre-existing uncommitted implementation. Report actual validation
  results and remaining limitations; plans and mocked tests do not establish
  live SDK, sandbox, provider or physical readiness.
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
  This bounded runtime publication does not authorize scientific agents to edit
  development source.
- Only SDK children use this root as `CODEX_HOME`; the desktop app keeps its own
  home. Runtime suppresses automatic AGENTS discovery and explicitly supplies
  scientific role owners. Do not edit/read native authentication or session files
  as scientific evidence. Home/profile/auth behavior needs separate live evidence;
  cloning tracked checkpoints does not recreate native sessions or grant login.
- Do not run the hardware loop, contact the robot, or launch a physical experiment
  as part of development validation. Use mocked clients and temporary data.
