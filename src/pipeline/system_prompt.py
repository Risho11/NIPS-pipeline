"""system_prompt.py — single source of truth for this project's LLM system prompts.

Three prompts live here, handled two different ways:

- EXPERIMENTAL_REPORT_PROMPT (activeLearning_29.Generate_report) and
  ACTIVE_LEARNING_PROMPT_TEMPLATE (activeLearning_29.LLM_AL) are static, human-authored text.
  Never touched by an LLM -- ranges, objective, and framing are hardcoded on purpose.
- QUALITY_CHECKER_PROMPT (membrane_quality_llm.Generate_quality_report) is hybrid: QualityChecker
  holds the hardcoded raw ingredients (role/task/constraints/format) -- edit these directly to
  change what the quality checker cares about. refine_quality_checker_prompt() is a dev-time tool
  that asks an LLM to tighten those ingredients into final prompt text and writes the result to
  QUALITY_CHECKER_PROMPT_CACHE_PATH, which QUALITY_CHECKER_PROMPT then loads from (falling back to
  a hand-assembled version of QualityChecker's fields if the cache doesn't exist yet). The refiner
  itself is never called during normal Generate_quality_report() runs -- only when you run
  `python system_prompt.py` yourself while tuning the prompt -- but once it has run, its output is
  what membrane_quality_llm.py actually uses immediately, no manual copy-paste.
"""
from dataclasses import dataclass
from pathlib import Path
import os

from openai import OpenAI
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed — rely on env var being set directly


# ── Generate_report ────────────────────────────────────────────────────────────
# Unchanged wording from the original inline prompt -- relocated here, not reworded.
EXPERIMENTAL_REPORT_PROMPT = (
    "Here I have a set of experimental parameters for my automated membrane synthesis via "
    "non-solvent-induced phase separation (NIPS) using my robotic system. "
    "{param_descriptions} "
    "Can you translate that into a short experimental report? "
)


# ── LLM_AL ──────────────────────────────────────────────────────────────────────
# Human-authored, static, hardcoded. Fixes the old prompt's self-contradiction ("maximize modulus"
# stated twice, then "minimize strain at 50 bar") -- the correct objective is minimize Strain at 50
# bar (see tests/llm_prompt_context.md). Adds materials-discovery framing so the model doesn't
# infer/suggest an out-of-scope application. Output contract (flat JSON, exact PARAMS_SCHEMA keys)
# is unchanged -- run_loop.py's _extract_next_params/_validate_params depend on this shape.
ACTIVE_LEARNING_PROMPT_TEMPLATE = (
    "Here I have a set of structured experimental parameters for my automated membrane synthesis via "
    "non-solvent-induced phase separation (NIPS). Do not suggest or assess "
    "anything outside the current parameter/stock system."
    "OBJECTIVE: Maximize the Elastic Modulus, and as a secondary goal minimize the Strain at 50 bar. *My goal is to iteratively find the best experiments to achieve these objectives.*"
    "Take the coefficient of variation (CV) and the membrane quality into account when appropriate. "
    "Based on the following prior experimental observations and the objective, recommend the next set of experimental "
    "parameters, given these parameter ranges: {ranges} "
    "Keep your reasoning concise, structured and transparent."
    "Return your answer as a single JSON object (a ```json code fence is fine) with exactly these "
    "keys: mixing_temp, bath_temp, pullcast_speed, nitrogen, coupon_to_bath_wait_time, "
    "nips_bath_wait_time, polymer_wt, additive_wt. Do not add a wrapping key or omit any key."
)

# Historical reference only -- NOT used anywhere, never import/call this. The original inline
# LLM_AL prompt before ACTIVE_LEARNING_PROMPT_TEMPLATE existed (see activeLearning_29.py at git
# commit d7b31ed, pre-4f71143). Self-contradictory: says "maximize modulus" twice, then "minimize
# strain at 50 bar" once. This is what produced the 10-25degMix-25deg-0s-NoN2-1800s campaign row
# (LLM told to maximize when the real objective was minimize Strain at 50 bar) -- kept here so the
# mistake and its exact wording aren't lost to git-log archaeology if it ever needs re-diagnosing.
_ACTIVE_LEARNING_PROMPT_ORIGINAL_BUGGY_BACKUP = (
    "Here I have a set of structured experimental parameters for my automated membrane synthesis "
    "via non-solvent-induced phase separation (NIPS). "
    "My goal is to iteratively find the best experiment to maximize modulus. "
    "Based on the following previous experimental observations, recommend the next experiment "
    "that minimizes strain at 50 bar, taking the coefficient of variation (CV) into account when "
    "it is appropriate. "
    "Suggest the next set of experimental parameters that is expected to maximize modulus given "
    "the parameter ranges: {ranges}."
)


# ── Generate_quality_report ──────────────────────────────────────────────────────
@dataclass
class QualityChecker:
    """Hardcoded raw ingredients for the quality-checker system prompt. Edit these directly, or feed
    them to refine_quality_checker_prompt() to have an LLM tighten the wording."""
    role: str = (
        "You are a vision quality-control assistant judging membrane coupon photos for an "
        "early-stage materials-discovery research pipeline (NIPS membrane fabrication)."
    )
    task: str = (
        "Assess, qualitatively, from the photo: (1) whether a membrane is present at all, "
        "(2) whether it covers the full VERTICAL (top-to-bottom) extent of the test-cell aperture -- "
        "a real defect if not -- (3) whether it looks uniform, "
        "(4) whether it is free of visible wrinkles or trapped air bubbles."
    )
    constraints: str = (
        "This is materials-discovery research, not a filtration or permeation product test -- do not "
        "discuss, infer, or evaluate filtration/permeation suitability, even if the rig resembles one. "
        "The test-cell aperture is intentionally oversized left-to-right relative to the coupon -- partial "
        "LATERAL (left/right) gaps between the membrane edge and the aperture are a rig artifact, not a "
        "membrane defect. Do not mention, describe, note, or factor lateral/horizontal coverage into the "
        "assessment in any way. Only vertical (top/bottom) coverage gaps are relevant and should be "
        "reported clearly if present. "
        "If no membrane is present, say so in one sentence; do not describe the exposed backing/"
        "surface texture in detail. Do not give a numeric score. Keep the entire response concise. "
        "Judge Defects only from texture within the membrane material itself (the pale/white sheet) -- "
        "specular highlights, glare, or reflections on the surrounding metal aperture rim or at the "
        "membrane's boundary edge are lighting artifacts, not membrane wrinkles or folds."
    )
    format: str = (
        "Respond with short labeled bullets: Presence / Vertical Coverage / Uniformity / Defects / Summary. "
        "Keep the whole response under about 120 words."
    )


# Where refine_quality_checker_prompt() saves its output. Tracked in git like everything else here
# so a refine run is a reviewable diff, not a silent local-only change.
QUALITY_CHECKER_PROMPT_CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "quality_checker_prompt.txt"


def _assemble_from_checker(checker: QualityChecker) -> str:
    """Plain concatenation fallback -- used until a refine_quality_checker_prompt() run exists."""
    return f"{checker.role} {checker.task} {checker.constraints} {checker.format}"


# What Generate_quality_report() actually uses: the last refine_quality_checker_prompt() output if
# one has been saved, else a hand-assembled version of QualityChecker's fields.
if QUALITY_CHECKER_PROMPT_CACHE_PATH.exists():
    QUALITY_CHECKER_PROMPT = QUALITY_CHECKER_PROMPT_CACHE_PATH.read_text(encoding="utf-8").strip()
else:
    QUALITY_CHECKER_PROMPT = _assemble_from_checker(QualityChecker())


def refine_quality_checker_prompt(checker: QualityChecker = None,
                                   model: str = "anthropic/claude-sonnet-4.6",
                                   temperature: float = 0.0) -> str:
    """Dev-time utility -- NOT called during normal Generate_quality_report() runs. Asks an LLM to
    synthesize the raw role/task/constraints/format ingredients into tight, unambiguous final
    system-prompt text, and writes the result to QUALITY_CHECKER_PROMPT_CACHE_PATH -- the next time
    system_prompt.py (and anything that imports it) loads, QUALITY_CHECKER_PROMPT picks it up
    automatically. Run manually while tuning the prompt (see `python system_prompt.py`); review the
    printed output and the diff to quality_checker_prompt.txt before trusting it for real."""
    checker = checker or QualityChecker()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENROUTER_API_KEY not set. Add it to .env or set it as an environment variable.")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": (
                "You are a prompt-engineering assistant. You will be given the role, task, constraints, "
                "and output format intended for a DIFFERENT vision-LLM assistant that does not exist "
                "yet and has no image in front of it right now. Do not act as that assistant, do not "
                "roleplay it, do not analyze or invent any image or membrane, and do not produce a "
                "sample answer in its output format -- those fields are raw material to synthesize, "
                "not instructions for you to follow. Your only job is to write the single system-prompt "
                "string that assistant should be given when it later receives a real photo -- clear, "
                "unambiguous, and as short as possible while keeping every constraint. Return ONLY that "
                "system-prompt text, nothing else -- no preamble, no meta-commentary, no example output."
            )},
            {"role": "user", "content": (
                "Write a system prompt for an assistant with the specs below. Do not fulfill these "
                "specs yourself -- there is no image, and none of this is addressed to you.\n\n"
                f"<role>{checker.role}</role>\n<task>{checker.task}</task>\n"
                f"<constraints>{checker.constraints}</constraints>\n<output_format>{checker.format}</output_format>"
            )},
        ],
        temperature=temperature,
    )
    refined = response.choices[0].message.content.strip()
    QUALITY_CHECKER_PROMPT_CACHE_PATH.write_text(refined + "\n", encoding="utf-8")
    return refined


if __name__ == "__main__":
    text = refine_quality_checker_prompt()
    print(text)
    print(f"\n[saved to {QUALITY_CHECKER_PROMPT_CACHE_PATH}]")
