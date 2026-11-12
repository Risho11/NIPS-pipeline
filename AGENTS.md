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
- For a `dynamic` campaign, Codex CLI reads the campaign's configured warm-start
  CSV and its companion metadata when available before drafting its first
  recommendation guidance. Read saved campaign results for later updates.
  Keep measured observations, inferred chemistry, selection limits and current
  operator settings explicit.
- Keep applicable hypotheses and evidence in `data/knowledge/<material>/`.
  Use the campaign's `mas/rounds/<operation>/attempt-<n>/inquiry.md` for the
  comparisons, remaining uncertainty and next question, and `decision.md` for
  the provisional experiment choice and its reasoning. Use the scientific
  reasoning and data guidance in `docs/mas/workflow.md` and
  `docs/mas/data-contract.md` as reference. The SDK publication and submission
  procedures described there are historical.
- Keep `data/results/<actual-campaign-key>/dynamic_prompt.jinja` aligned with
  those records. Put the relevant hypotheses, supporting and contrary evidence,
  evidence limits, provisional choice and next question directly in the Jinja
  body so OpenRouter can use them. Update the template when the applicable
  judgment changes. Save it as UTF-8 by replacing it from a temporary file in
  the same directory. When its content changes, commit just the template to
  record its revision. Python reads the saved template for each recommendation.
- The campaign supervisor owns template updates and their commits. Delegated
  scientific agents write only in their current attempt and scratch space.
  Use the existing repository for version history.
- Preserve original measurements and operator settings. Do not edit or use
  native authentication or session files as scientific evidence.
- Do not run the hardware loop, contact the robot, or launch a physical experiment
  as part of development validation. Use mocked clients and temporary data.
