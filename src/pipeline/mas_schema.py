"""Typed experiment records; scientific and stock checks remain explicit code."""
import json
import math
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

Text = Annotated[str, Field(min_length=1, pattern=r"\S")]


class RecordModel(BaseModel):
    """Reject unknown fields, coercion, and non-finite numeric values."""
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, allow_inf_nan=False)


class ExperimentParameters(RecordModel):
    """The eight tunables the robot can execute."""
    mixing_temp: float = Field(ge=25, le=80)
    bath_temp: float = Field(ge=5, le=25)
    pullcast_speed: float = Field(ge=1, le=20)
    nitrogen: bool
    coupon_to_bath_wait_time: float = Field(ge=0, le=600)
    nips_bath_wait_time: float = Field(ge=1200, le=1800)
    polymer_wt: float = Field(ge=0, le=100)
    additive_wt: float = Field(ge=0, le=100)


class MaterialContext(RecordModel):
    """Operator-prepared materials and bath, never agent-selected tunables."""
    polymer_type: Text
    solvent_type: Text
    cosolvent_type: Text
    nips_bath_solvent: Text
    nips_bath_solvent_wt_percent: float = Field(ge=0, le=100)


class Hypothesis(RecordModel):
    """A stable, evidence-linked scientific claim."""
    id: Text
    statement: Text
    status: Literal["proposed", "supported", "refuted", "inconclusive"]
    evidence: list[Text]


class AnalysisReport(RecordModel):
    """Accepted observations and interpretation, with independent review identity."""
    report: Text
    author_thread_id: Text
    reviewer_thread_id: Text


class HypothesisUpdate(RecordModel):
    """Reviewed hypothesis list and main's subsequent selection."""
    report: Text
    hypotheses: list[Hypothesis]
    selected_hypothesis_id: Text | None
    selection_reason: Text
    author_thread_id: Text
    reviewer_thread_id: Text

    @model_validator(mode="after")
    def check_selection(self) -> Self:
        ids = [hypothesis.id for hypothesis in self.hypotheses]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate hypothesis IDs")
        if self.selected_hypothesis_id is not None:
            if not any(h.id == self.selected_hypothesis_id and h.status != "refuted"
                       for h in self.hypotheses):
                raise ValueError("Selected hypothesis is missing or refuted")
        return self


class ExperimentPlan(RecordModel):
    """One feasible test, with a prediction and criteria fixed before execution."""
    hypothesis_id: Text
    purpose: Literal["explore", "optimize", "repeat"]
    prediction: Text
    comparator: Text
    criteria: Text
    next_params: ExperimentParameters


class ExperimentDesign(RecordModel):
    """Reviewed design; a null plan explicitly records that no test is justified."""
    report: Text
    experiment: ExperimentPlan | None
    author_thread_id: Text
    reviewer_thread_id: Text


class ExperimentDecision(RecordModel):
    """Main's final decision; only run carries executable conditions."""
    report: Text
    action: Literal["run", "hold", "stop"]
    reason: Text
    next_params: ExperimentParameters | None

    @model_validator(mode="after")
    def check_execution(self) -> Self:
        if self.action == "run" and self.next_params is None:
            raise ValueError("run requires executable conditions")
        if self.action != "run" and self.next_params is not None:
            raise ValueError("hold/stop cannot contain executable conditions")
        return self


class QAReview(RecordModel):
    """Native reviewer completion, bound to the exact author JSON."""
    verdict: Literal["pass", "fail"]
    reviewed_content: dict[str, JsonValue]
    findings: list[Text]


def validate_conditions(params, bounds, material_context, locked_additive_wt=None):
    """Check the current physical constraints without modifying reviewed values."""
    materials = MaterialContext.model_validate(material_context)
    tunables = ExperimentParameters.model_validate(
        {key: value for key, value in params.items() if key not in MaterialContext.model_fields}
    )
    for key, value in materials.model_dump().items():
        if key in params and params[key] != value:
            raise ValueError(f"Operator material setting changed: {key}")
    if locked_additive_wt is not None and tunables.additive_wt != locked_additive_wt:
        raise ValueError("Reviewed design violates additive lock")
    p, a = bounds.test_target(tunables.polymer_wt, tunables.additive_wt)
    if not (math.isclose(p, tunables.polymer_wt, abs_tol=1e-8)
            and math.isclose(a, tunables.additive_wt, abs_tol=1e-8)):
        raise ValueError("Reviewed design is outside the feasible stock polygon")
    if bounds.is_undiluted_polymer_stock(p, a) and tunables.mixing_temp != 25:
        raise ValueError("Undiluted polymer stock requires mixing_temp=25")
    return {**tunables.model_dump(), **materials.model_dump()}


def validate_review(result, report, main_thread_id):
    """Verify native author/QA completions; this does not establish scientific truth."""
    author, reviewer = report.author_thread_id, report.reviewer_thread_id
    if len({author, reviewer, main_thread_id}) != 3:
        raise ValueError("Author, QA and main must be separate threads")
    messages = {}
    for item in result.items:
        item = getattr(item, "root", item)
        if getattr(item, "type", None) == "collabAgentToolCall":
            for thread_id, state in item.agents_states.items():
                if getattr(state.status, "value", state.status) == "completed" and state.message:
                    messages[thread_id] = state.message
    try:
        authored = json.loads(messages[author])
        review = QAReview.model_validate_json(messages[reviewer])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Missing or invalid SDK-observed author/QA JSON completion") from exc
    expected = report.model_dump(mode="json", exclude={
        "author_thread_id", "reviewer_thread_id", "selected_hypothesis_id", "selection_reason",
    })
    if authored != expected:
        raise ValueError("Final content differs from the author's completed payload")
    # Validate specialist values too: Python equality alone treats True as 1.
    operational = {key: value for key, value in report.model_dump().items()
                   if key not in expected}
    type(report).model_validate({**authored, **operational})
    type(report).model_validate({**review.reviewed_content, **operational})
    if review.verdict != "pass" or review.reviewed_content != authored:
        raise ValueError("QA did not pass this exact content")
    return review
