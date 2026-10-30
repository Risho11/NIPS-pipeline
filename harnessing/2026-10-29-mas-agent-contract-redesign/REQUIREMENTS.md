# MAS agent-contract redesign requirements

This is the accepted planning objective distilled from the current user conversation, not proof of implementation.

## Authorized now

Configure a development Harness by external reference to junhyeong-custom-agent-setting, without a submodule. Select STANDARD_CONTROLLER_WRITER. The plan was independently reviewed; on 2026-10-30 the user authorized Goal execution of that plan. Preserve the existing implementation. Product ownership requires verified Writer identity and a literal step handoff. The user subsequently selected ordinary Git commits instead of the automatic manager; retain the Harness plan, Controller/Writer, independent QA and final DCP under MANUAL_GIT_TRANSITIONS.

## Scientific operating model

- One persistent experiment main thread follows data, artifacts, reports and outstanding questions.
- Observation/analysis precedes hypothesis maintenance and main selection; prediction precedes experimental design and final decision.
- The inquiry may return upstream. Keep existing hypotheses where justified; do not force a new hypothesis or choose explore/optimize before identifying the evidence need.
- Analyst, hypothesis updater and designer each have an independent scientific QA role. Development QA is a separate workflow.
- Main chooses the hypothesis and next experiment. Specialists receive meaningful questions and can request missing evidence or follow-up through main.
- Allow calculations, scripts, tables and question-specific figures in the experiment work area. No predetermined figure list; inspect actual columns and units.
- Shared context should be supplied sensibly, without requiring unchanged documents to be reread on every turn. Fresh subagents still need the necessary role/context instructions.
- Four accepted Markdown records remain: analysis, hypothesis update, experiment design, final decision. Flexible report layout; preserve previous judgments and explain revisions.
- Main follows report/artifact locations. Do not require whole-report JSON echoes, all-report hash gates, cryptographic parentage checks, or a separate duplicate result.json.
- Protect measured inputs and operator material/stock settings. Agents do not create measurements or directly execute devices.
- SS curve processing produces the pore-fraction estimate automatically. The current aggregate field is Pore Fraction Mean. The old MAS figure reader's Changepoint Mean mismatch does not mean a missing measurement.
- Execution adopts the exact scientifically reviewed feasible conditions, or records hold/stop. Hold permits reconsideration when the evidence gap is resolved.
- A performance decline can still provide useful evidence. Do not claim a global optimum or forecast verified performance at an unexecuted point.

## Agent documentation quality

AGENTS.md must directly explain mission, decision rights, inputs, useful actions, collaboration, uncertainty and completion/handoff criteria. A pointer-only role file is insufficient.
Role docs must explain methods and choices with meaningful worked examples, not repeat generic prohibitions. Put shared domain facts in common guides; keep role-specific reasoning and QA methods distinct.
Reviewers examine source evidence and reasoning, not only wording or formatting. Distinguish independent syntheses, specimens, processing variants, campaign identity and warm-start provenance.
No blanket static-template mandates, artificial document quotas, or full shared-skill copies.

## Evidence of usefulness

Use actual existing data in an isolated report-only Codex pilot. Judge how evidence led to a hypothesis and a defensible next point, why explore/optimize/repeat was chosen, how figures helped, and whether independent QA changed or qualified the decision.
Mocked SDK responses prove only local plumbing. A good-looking report or feasible point alone does not establish useful scientific reasoning.
Do not require a wide benchmark or prove future physical performance. Retain uncertainty and missing evaluation coverage.

## Scope boundaries

This Harness owns agent contracts, their minimal isolated pilot and its evaluation. Rewriting production codex_context.py, mas_records.py, mas_schema.py, mas_analysis.py or run_loop.py is a separately reviewed follow-up after the contracts are useful.
Legacy single/double/explore/double_explore modes, measured CSVs, robot/server code and existing operator settings stay untouched by this Harness.
No global custom-agent installation, shared-repository change, submodule/gitlink change, new worktree, remote issue/PR/push/merge, or physical experiment is authorized by this plan.
Technical artifacts are English; user communication is Korean.
