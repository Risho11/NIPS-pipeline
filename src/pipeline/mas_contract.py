"""Small operational MAS contracts; scientific reasoning stays in Markdown."""
import math
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

import polymer_additive_bounds as stocks

Text = Annotated[str, Field(min_length=1, pattern=r"\S")]
TOPICS = ("concentration.md", "prebath_exposure.md", "bath_temperature.md", "bath_residence.md")


class Record(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, allow_inf_nan=False)


class Conditions(Record):
    mixing_temp: float = Field(ge=25, le=80)
    bath_temp: float = Field(ge=5, le=25)
    pullcast_speed: float = Field(ge=1, le=20)
    nitrogen: bool
    coupon_to_bath_wait_time: float = Field(ge=0, le=600)
    nips_bath_wait_time: float = Field(ge=1200, le=1800)
    polymer_wt: float = Field(ge=0, le=100)
    additive_wt: float = Field(ge=0, le=100)


class Materials(Record):
    polymer_type: Text
    solvent_type: Text
    cosolvent_type: Text
    nips_bath_solvent: Text
    nips_bath_solvent_wt_percent: float = Field(ge=0, le=100)


class Context(Record):
    """Caller-supplied operator context; there are no installed-stock defaults."""
    campaign: Text
    objective: Text
    materials: Materials
    stock_metadata: dict[str, float | str]
    locked_additive_wt: float | None

    @model_validator(mode="after")
    def check_stocks(self) -> Self:
        installed_stocks(self.stock_metadata)
        if self.locked_additive_wt is not None and not 0 <= self.locked_additive_wt <= 100:
            raise ValueError("Invalid additive lock")
        return self


def installed_stocks(metadata):
    """Use the existing pure stock geometry with every stock value explicit."""
    values = dict(metadata)
    mode = values.pop("stock_mode", None)
    cls = {"two_bottle": stocks.OldStockStruct, "four_bottle": stocks.StockParameters}.get(mode)
    if cls is None or set(values) != set(cls.__dataclass_fields__):
        raise ValueError("Complete explicit stock metadata required")
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 100
           for v in values.values()):
        raise ValueError("Stock percentages must be finite numbers")
    total = (values['additive_stock_polymer_wt_percent'] + values['additive_stock_additive_wt_percent']
             if mode == 'two_bottle' else values['all_mix_pwt'] + values['all_mix_cswt'])
    if total > 100:
        raise ValueError("Stock components exceed 100 wt%")
    return cls(**values)


def composition_member(point, vertices):
    """Convex-mixture membership, including repeated, point and segment stocks.

    Build the actual hull: arbitrary installed stocks need not have the winding
    assumed by the legacy projection helper. Tolerance is in wt%, not hull area.
    """
    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    points = sorted(set(vertices))
    chains = []
    for ordered in (points, list(reversed(points))):
        chain = []
        for value in ordered:
            while len(chain) >= 2 and cross(chain[-2], chain[-1], value) <= 0:
                chain.pop()
            chain.append(value)
        chains.append(chain)
    hull = chains[0][:-1] + chains[1][:-1] if len(points) > 1 else points
    tolerance = 1e-8
    if any(point[i] < min(p[i] for p in hull) - tolerance
           or point[i] > max(p[i] for p in hull) + tolerance for i in (0, 1)):
        return False
    if len(hull) == 1:
        return math.dist(point, hull[0]) <= tolerance
    if len(hull) == 2:
        return abs(cross(*hull, point)) <= tolerance * math.dist(*hull)
    return all(cross(a, b, point) >= -tolerance * math.dist(a, b)
               for a, b in zip(hull, hull[1:] + hull[:1]))


def validate_conditions(params, context):
    """Reject drift, never snap a reviewed condition or change operator context."""
    params = Conditions.model_validate(params)
    if context.locked_additive_wt is not None and params.additive_wt != context.locked_additive_wt:
        raise ValueError("Additive lock changed")
    supplied = installed_stocks(context.stock_metadata)
    p, a = params.polymer_wt, params.additive_wt
    if not composition_member((p, a), stocks.get_composition_bounds(supplied)['vertices']):
        raise ValueError("Outside stock composition polygon")
    if stocks.is_undiluted_polymer_stock(p, a, supplied) and params.mixing_temp != 25:
        raise ValueError("Undiluted polymer stock requires mixing_temp=25")
    return params


class Decision(Record):
    action: Literal["run", "hold", "stop"]
    reason: Text
    next_params: Conditions | None
    knowledge_commit: Text | None

    @model_validator(mode="after")
    def check_action(self) -> Self:
        if (self.action == "run") != (self.next_params is not None):
            raise ValueError("Only run carries executable conditions")
        if self.action == 'run' and self.knowledge_commit is None:
            raise ValueError("Run requires committed reviewed knowledge")
        return self


class Contribution(Record):
    """Native author/reviewer completion payload: references, not report bodies."""
    operation_id: Text
    kind: Literal["knowledge", "design"]
    files: dict[str, Text]
    conditions: Conditions | None
    knowledge_commit: str | None
    report_path: Text


class Review(Contribution):
    verdict: Literal["pass", "fail"]
    author_thread_id: Text


class Adoption(Record):
    author_thread_id: Text
    reviewer_thread_id: Text


class MainReply(Record):
    """Main either requests knowledge publication or returns a final decision."""
    knowledge: Adoption | None
    design: Adoption | None
    decision: Decision | None
    records: list[Text]

    @model_validator(mode="after")
    def check_reply(self) -> Self:
        if self.knowledge is not None:
            if self.design is not None or self.decision is not None:
                raise ValueError("Publish knowledge before binding a design to its commit")
        elif self.decision is None:
            raise ValueError("A publication or decision is required")
        if self.decision and (self.decision.action == "run") != (self.design is not None):
            raise ValueError("Run requires an independently reviewed design")
        return self
