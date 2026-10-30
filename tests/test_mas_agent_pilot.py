"""Offline isolation and handoff checks, not evidence of scientific reasoning."""
import csv
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mas_agent_pilot", ROOT / "scripts/mas_agent_pilot.py")
pilot = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pilot
spec.loader.exec_module(pilot)


def context():
    return {
        "objective": "Investigate reproducible modulus/pore-fraction tradeoffs",
        "question": "Which next contrast is justified by these observations?",
        "operator_context_basis": "Explicit offline test inputs; not physical confirmation",
        "materials": {"polymer_type": "Polysulfone", "solvent_type": "PolarClean",
                      "cosolvent_type": "none", "nips_bath_solvent": "PolarClean",
                      "nips_bath_solvent_wt_percent": 10.0},
        "stocks": {"stock_mode": "two_bottle", "polymer_stock_wt_percent": 17.0,
                   "additive_stock_polymer_wt_percent": 17.0,
                   "additive_stock_additive_wt_percent": 4.0},
        "locked_additive_wt": 0.0,
    }


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.source = self.base / "source"
        self.source.mkdir()
        files = [*pilot.SOURCE_FILES, "docs/mas/data-contract.md",
                 "docs/mas/analysis-methods.md", "docs/mas/workflow.md"]
        for role in ("campaign-main", *pilot.ROLES):
            files.extend(str(p.relative_to(ROOT)) for p in (ROOT / "subagents" / role).rglob("*.md"))
        files.extend(f".codex/agents/{role}.toml" for role in pilot.ROLES)
        for relative in files:
            target = self.source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        self.campaign = Path("data/results/test_campaign")
        for table, names in {
            "llm": ["case_a", "case_a_run2", "future"],
            "agg": ["case_a_preDiscard", "case_a_postDiscard", "case_a_run2", "future"],
            "reps": ["case_a | rep 1", "case_a_run2 | rep 1", "future | rep 1"],
        }.items():
            target = self.source / self.campaign / f"{table}.csv"
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["name", "Pore Fraction Mean", "LLM_suggestion"])
                writer.writeheader()
                writer.writerows({"name": name, "Pore Fraction Mean": "0.4567890123",
                                  "LLM_suggestion": "unperformed future proposal"} for name in names)
        self.scratch = self.base / "scratch"

    def prepare(self, ctx=None):
        return pilot.prepare(self.campaign, "case_a", ctx or context(), self.scratch, repo_root=self.source)

    def decision(self, action="hold", params=None):
        (self.scratch / "work/index.md").write_text("Mock inquiry; no scientific QA was performed.\n")
        return {"action": action, "next_params": params, "reason": "Offline test only", "index_path": "index.md"}

    def test_prefix_filters_future_and_preserves_source_bytes(self):
        originals = {p: p.read_bytes() for p in (self.source / self.campaign).glob("*.csv")}
        self.prepare()
        for table, count in [("llm", 1), ("agg", 2), ("reps", 1)]:
            target = self.scratch / self.campaign / f"{table}.csv"
            with target.open(newline="") as stream:
                reader = csv.DictReader(stream)
                self.assertNotIn("LLM_suggestion", reader.fieldnames)
                rows = list(reader)
            self.assertEqual(len(rows), count)
            self.assertTrue(all(r["Pore Fraction Mean"] == "0.4567890123" for r in rows))
            self.assertNotIn("case_a_run2", target.read_text())
            self.assertNotIn("future", target.read_text())
        self.assertEqual(originals, {p: p.read_bytes() for p in originals})
        self.assertFalse(any(p.is_symlink() for p in self.scratch.rglob("*")))
        self.assertFalse((self.scratch / ".venv").exists())
        instructions = (self.scratch / "work/AGENTS.md").read_text()
        self.assertIn("explicitly assigned experiment campaign main", instructions)
        self.assertIn("This is not development Harness execution", instructions)
        self.assertEqual(json.loads((self.scratch / "execution.json").read_text())["status"], "NOT_RUN")

    def test_rejects_unsafe_output_and_symlinked_input(self):
        with self.assertRaises(ValueError):
            pilot.prepare(self.campaign, "case_a", context(), self.source / "scratch", repo_root=self.source)
        llm = self.source / self.campaign / "llm.csv"
        other = self.base / "external.csv"
        llm.rename(other)
        llm.symlink_to(other)
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.scratch.exists())

    def test_missing_operator_context_and_duplicate_cutoff_fail_before_output(self):
        ctx = context()
        del ctx["stocks"]["polymer_stock_wt_percent"]
        with self.assertRaises(ValueError):
            self.prepare(ctx)
        with self.assertRaises(ValueError):
            pilot.prepare(self.campaign, "missing", context(), self.scratch, repo_root=self.source)
        self.assertFalse(self.scratch.exists())

    def test_mock_sdk_uses_one_main_and_only_scratch_writes(self):
        self.prepare()
        original = (self.source / self.campaign / "llm.csv").read_bytes()
        factory = Mock()
        codex = Mock()
        # Use an ordinary context manager mock; it never starts an SDK process.
        manager = Mock()
        manager.__enter__ = Mock(return_value=codex)
        manager.__exit__ = Mock(return_value=False)
        factory.return_value = manager
        thread = codex.thread_start.return_value
        thread.id = "mock-main"
        thread.run.side_effect = lambda *a, **kw: SimpleNamespace(
            final_response=json.dumps(self.decision()), status="completed", items=[], usage=None)
        with patch.object(pilot.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="[]")) as inspect_cli:
            pilot.run_inquiry(self.scratch, codex_factory=factory)
        self.assertEqual(inspect_cli.call_count, 2)
        config = factory.call_args.args[0]
        self.assertEqual(Path(config.cwd), self.scratch / "work")
        for setting in ('sandbox_workspace_write.writable_roots=[]',
                        'sandbox_workspace_write.exclude_slash_tmp=true',
                        'sandbox_workspace_write.exclude_tmpdir_env_var=true',
                        'sandbox_workspace_write.network_access=false'):
            self.assertIn(setting, config.config_overrides)
        self.assertEqual(config.env["PILOT_ROOT"], str(self.scratch))
        trust = next(value for value in config.config_overrides if value.startswith("projects="))
        self.assertEqual(tomllib.loads(trust), {"projects": {str(self.scratch / "work"): {"trust_level": "trusted"}}})
        self.assertEqual(codex.thread_start.call_args.kwargs["approval_mode"].value, "deny_all")
        self.assertEqual(codex.thread_start.call_args.kwargs["sandbox"].value, "workspace-write")
        self.assertNotIn("model", codex.thread_start.call_args.kwargs)
        self.assertEqual(thread.run.call_count, 1)
        state = json.loads((self.scratch / "execution.json").read_text())
        self.assertEqual(state["status"], "COMPLETED_UNREVIEWED")
        self.assertEqual(state["thread_id"], "mock-main")
        self.assertEqual(original, (self.source / self.campaign / "llm.csv").read_bytes())
        self.assertFalse(any(name in sys.modules for name in ("run_loop", "url_29", "codex_context", "mas_records")))

    def test_inherited_mcp_is_disabled_by_name_not_by_empty_table(self):
        from openai_codex import CodexConfig
        config = CodexConfig(codex_bin="pinned-codex", cwd=str(self.base),
                             config_overrides=('mcp_servers={}',), env={"PILOT_ROOT": str(self.base)})
        # A new/dotted name must work without a machine-specific allowlist.
        before = [{"name": "inherited.extra", "enabled": True, "env": {"SECRET": "never-copy"}}]
        after = [{"name": "inherited.extra", "enabled": False, "url": "never-copy"}]
        with patch.object(pilot.subprocess, "run", side_effect=[
            SimpleNamespace(returncode=0, stdout=json.dumps(before)),
            SimpleNamespace(returncode=0, stdout=json.dumps(after)),
        ]) as inspect_cli:
            states = pilot.disable_effective_mcp(config)
        self.assertEqual(states, {"before": {"inherited.extra": True}, "after": {"inherited.extra": False}})
        override = config.config_overrides[-1]
        self.assertEqual(tomllib.loads(override), {"mcp_servers": {"inherited.extra": {"enabled": False}}})
        self.assertIn(override, inspect_cli.call_args.args[0])
        self.assertEqual(inspect_cli.call_args.kwargs["cwd"], config.cwd)
        self.assertEqual(inspect_cli.call_args.kwargs["env"]["PILOT_ROOT"], str(self.base))
        self.assertNotIn("never-copy", json.dumps(states))

    def test_mcp_failure_aborts_before_sdk_and_does_not_leak_raw_config(self):
        self.prepare()
        unchanged = [{"name": "unseen-server", "enabled": True}]
        for responses in (
            [SimpleNamespace(returncode=0, stdout=json.dumps(unchanged))] * 2,
            [SimpleNamespace(returncode=1, stdout="SECRET", stderr="secret-endpoint")],
            [SimpleNamespace(returncode=0, stdout='[{"name":"x","env":{"TOKEN":"SECRET"}}]')],
        ):
            factory = Mock()
            with self.subTest(responses=len(responses)), patch.object(pilot.subprocess, "run", side_effect=responses):
                with self.assertRaises(RuntimeError) as error:
                    pilot.run_inquiry(self.scratch, codex_factory=factory)
            factory.assert_not_called()
            self.assertNotIn("SECRET", str(error.exception))
            self.assertNotIn("secret-endpoint", str(error.exception))
            self.assertFalse((self.scratch / "mcp-preflight.json").exists())

    def test_decision_rejects_escaping_artifacts_and_invalid_conditions(self):
        self.prepare()
        decision = self.decision()
        decision["index_path"] = "../context.json"
        with self.assertRaises(ValueError):
            pilot.validate_decision(decision, self.scratch)
        params = {"mixing_temp": 25.0, "bath_temp": 15.0, "pullcast_speed": 10.0,
                  "nitrogen": True, "coupon_to_bath_wait_time": 120.0,
                  "nips_bath_wait_time": 1250.0, "polymer_wt": 14.0, "additive_wt": 0.0}
        pilot.validate_decision(self.decision("run", params), self.scratch)
        # macOS /var and /private/var aliases must not trigger false containment failures.
        pilot.validate_decision(self.decision("run", params), Path(self.temp.name) / "scratch")
        for changes in ({"additive_wt": 1.0}, {"bath_temp": float("nan")},
                        {"nitrogen": 1}, {"polymer_wt": 17.0, "mixing_temp": 30.0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                pilot.validate_decision(self.decision("run", {**params, **changes}), self.scratch)
        with self.assertRaises(ValueError):
            pilot.validate_decision(self.decision("hold", params), self.scratch)

    def test_wall_timeout_stops_group_and_preserves_nonpass(self):
        self.prepare()
        process = Mock(pid=12345)
        process.wait.side_effect = [subprocess.TimeoutExpired("mock", 1), 0]
        with patch.object(pilot.subprocess, "Popen", return_value=process) as popen, patch.object(pilot.os, "killpg") as kill:
            with self.assertRaises(RuntimeError):
                pilot.run_bounded(self.scratch, 1)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertIn("--live", popen.call_args.args[0])
        self.assertEqual(kill.call_args_list[0].args, (12345, pilot.signal.SIGTERM))
        self.assertEqual(kill.call_args_list[-1].args, (12345, pilot.signal.SIGKILL))
        self.assertEqual(json.loads((self.scratch / "execution.json").read_text())["status"], "INTERRUPTED_NON_PASS")

    def test_explicit_case_stocks_override_source_defaults(self):
        ctx = context()
        ctx["stocks"] = {"stock_mode": "two_bottle", "polymer_stock_wt_percent": 12.0,
                         "additive_stock_polymer_wt_percent": 12.0,
                         "additive_stock_additive_wt_percent": 3.0}
        ctx["locked_additive_wt"] = None
        self.prepare(ctx)
        params = {"mixing_temp": 25.0, "bath_temp": 15.0, "pullcast_speed": 10.0,
                  "nitrogen": True, "coupon_to_bath_wait_time": 120.0,
                  "nips_bath_wait_time": 1250.0, "polymer_wt": 10.0, "additive_wt": 1.0}
        pilot.validate_decision(self.decision("run", params), self.scratch)
        with self.assertRaises(ValueError):
            pilot.validate_decision(self.decision("run", {**params, "polymer_wt": 14.0}), self.scratch)

    def test_cli_default_never_starts_model_and_internal_worker_requires_live(self):
        ctx = self.base / "context.json"
        ctx.write_text(json.dumps(context()))
        with patch.object(pilot, "prepare", return_value=self.scratch), patch.object(pilot, "run_bounded") as run:
            pilot.main(["--campaign", str(self.campaign), "--through-name", "case_a",
                        "--context", str(ctx), "--output", str(self.scratch)])
            run.assert_not_called()
        with patch.object(pilot, "run_inquiry") as inquiry, patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                pilot.main(["--worker", str(self.scratch)])
            inquiry.assert_not_called()


if __name__ == "__main__":
    unittest.main()
