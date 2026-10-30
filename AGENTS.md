# NIPS pipeline guidance

- Use `uv` for Python dependencies and `uv run` for project commands.
- Preserve measured data and existing legacy search modes. Never substitute an
  inferred value for a measurement or silently change operator material settings.
- Repository development and the experiment MAS are separate workflows.
- The MAS agent-contract redesign uses an external-reference development Harness
  with `STANDARD_CONTROLLER_WRITER`; see
  `harnessing/2026-10-29-mas-agent-contract-redesign/README.md` and its requirements,
  plan and external-source binding. Resolve shared skills through
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
- Do not run the hardware loop, contact the robot, or launch a physical experiment
  as part of development validation. Use mocked clients and temporary data.
