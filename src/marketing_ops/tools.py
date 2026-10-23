"""Transparent marketing arithmetic, reconciliation and experiment review."""

import math
from datetime import date
from decimal import Decimal
from statistics import NormalDist
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class FunnelInput(Input):
    spend: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    revenue: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    visitors: int = Field(ge=0, le=1_000_000_000_000, strict=True)
    leads: int = Field(ge=0, le=1_000_000_000_000, strict=True)
    customers: int = Field(ge=0, le=1_000_000_000_000, strict=True)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    cohort_confirmed: bool

    @model_validator(mode="after")
    def nested(self):
        if not self.cohort_confirmed:
            raise ValueError("Confirm all stages describe the same nested cohort")
        if not self.customers <= self.leads <= self.visitors:
            raise ValueError("Nested funnel requires customers <= leads <= visitors")
        return self


def ratio(a, b):
    return float(a / b) if b else None


def funnel(p: FunnelInput) -> dict:
    return {
        "kind": "funnel_metrics",
        "currency": p.currency,
        "metrics": [
            {"metric": name, "value": value, "definition": definition}
            for name, value, definition in [
                ("visitor_to_lead", ratio(p.leads, p.visitors), "leads / visitors"),
                ("lead_to_customer", ratio(p.customers, p.leads), "customers / leads"),
                ("cost_per_lead", ratio(p.spend, p.leads), "supplied spend / leads"),
                (
                    "media_cost_per_customer",
                    ratio(p.spend, p.customers),
                    "supplied spend / customers; not fully loaded CAC",
                ),
                ("roas", ratio(p.revenue, p.spend), "attributed revenue / supplied spend"),
                (
                    "average_revenue_per_customer",
                    ratio(p.revenue, p.customers),
                    "revenue / customers",
                ),
            ]
        ],
        "limitations": [
            "Null means undefined because the denominator is zero.",
            "ROAS is not profit, incrementality or ROI.",
            "Fully loaded CAC requires all acquisition costs; media spend alone is insufficient.",
            "No attribution or causal inference is performed.",
        ],
    }


class Scope(Input):
    start: date
    end: date
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    timezone: str = Field(min_length=1, max_length=100)
    attribution_model: str = Field(min_length=1, max_length=100)
    lookback_days: int = Field(ge=0, le=365)
    date_basis: Literal["conversion", "interaction"]

    @model_validator(mode="after")
    def ordered(self):
        if self.end < self.start:
            raise ValueError("End precedes start")
        return self


class Transaction(Input):
    id: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(max_digits=18, decimal_places=2)


class ReconcileInput(Input):
    left_scope: Scope
    right_scope: Scope
    left: list[Transaction] = Field(max_length=20000)
    right: list[Transaction] = Field(max_length=20000)
    tolerance: Decimal = Field(default=Decimal("0.01"), ge=0, max_digits=12, decimal_places=2)

    @model_validator(mode="after")
    def unique(self):
        for rows in [self.left, self.right]:
            if len({r.id for r in rows}) != len(rows):
                raise ValueError("Duplicate transaction IDs; reconcile deduplication before totals")
        return self


def reconcile(p: ReconcileInput) -> dict:
    mismatches = [
        key
        for key in Scope.model_fields
        if getattr(p.left_scope, key) != getattr(p.right_scope, key)
    ]
    if mismatches:
        return {
            "kind": "reconciliation",
            "status": "incomparable",
            "scope_mismatches": mismatches,
            "limitations": [
                "Align scope before interpreting differences. No discrepancy totals were calculated."
            ],
        }
    left, right = {r.id: r.amount for r in p.left}, {r.id: r.amount for r in p.right}
    metrics = []
    for key in sorted(left.keys() | right.keys()):
        a, b = left.get(key), right.get(key)
        delta = b - a if a is not None and b is not None else None
        status = (
            "right_only"
            if a is None
            else "left_only"
            if b is None
            else "matched"
            if abs(delta) <= p.tolerance
            else "amount_mismatch"
        )
        metrics.append(
            {
                "transaction_id": key,
                "left": str(a) if a is not None else None,
                "right": str(b) if b is not None else None,
                "delta": str(delta) if delta is not None else None,
                "status": status,
            }
        )
    a, b = sum(left.values(), Decimal(0)), sum(right.values(), Decimal(0))
    return {
        "kind": "reconciliation",
        "status": "compared",
        "metrics": metrics,
        "totals": {"left": str(a), "right": str(b), "right_minus_left": str(b - a)},
        "limitations": [
            "Exact supplied ID matching only; no identity resolution or causal attribution.",
            "Scope labels are user declarations and must be verified against source exports.",
            "Negative amounts are allowed for refunds; missing transactions remain null.",
        ],
    }


class DesignInput(Input):
    baseline_rate: float = Field(gt=0, lt=1)
    absolute_mde: float = Field(ge=0.000001, lt=1)
    alpha: float = Field(default=0.05, ge=0.001, le=0.1)
    power: float = Field(default=0.8, ge=0.5, le=0.99)

    @model_validator(mode="after")
    def possible(self):
        if self.baseline_rate + self.absolute_mde >= 1:
            raise ValueError("Baseline plus MDE must be below 1")
        return self


def design_experiment(p: DesignInput) -> dict:
    a, b = p.baseline_rate, p.baseline_rate + p.absolute_mde
    mean = (a + b) / 2
    z_alpha, z_power = NormalDist().inv_cdf(1 - p.alpha / 2), NormalDist().inv_cdf(p.power)
    n = math.ceil(
        (
            z_alpha * math.sqrt(2 * mean * (1 - mean))
            + z_power * math.sqrt(a * (1 - a) + b * (1 - b))
        )
        ** 2
        / p.absolute_mde**2
    )
    return {
        "kind": "experiment_design",
        "per_arm_sample": n,
        "total_sample": 2 * n,
        "allocation": "1:1",
        "absolute_mde": p.absolute_mde,
        "relative_mde": p.absolute_mde / p.baseline_rate,
        "limitations": [
            "Normal approximation for two independent proportions, two-sided test, fixed horizon.",
            "Assumes independent randomized units, no clustering or repeated-user contamination.",
            "Pre-register one primary metric and stopping rule; account for multiple comparisons separately.",
            "No duration forecast without eligible daily traffic. Small/rare-event settings need an exact or simulation-based design.",
        ],
    }


class ExperimentInput(Input):
    control_n: int = Field(gt=0, le=1_000_000_000_000, strict=True)
    control_conversions: int = Field(ge=0, le=1_000_000_000_000, strict=True)
    treatment_n: int = Field(gt=0, le=1_000_000_000_000, strict=True)
    treatment_conversions: int = Field(ge=0, le=1_000_000_000_000, strict=True)
    expected_treatment_share: float = Field(default=0.5, gt=0, lt=1)
    alpha: float = Field(default=0.05, ge=0.001, le=0.1)
    fixed_horizon_complete: bool

    @model_validator(mode="after")
    def consistent(self):
        if (
            self.control_conversions > self.control_n
            or self.treatment_conversions > self.treatment_n
        ):
            raise ValueError("Conversions cannot exceed randomized units")
        return self


def analyze_experiment(p: ExperimentInput) -> dict:
    a, b = p.control_conversions / p.control_n, p.treatment_conversions / p.treatment_n
    total = p.control_n + p.treatment_n
    expected_b = total * p.expected_treatment_share
    expected_a = total - expected_b
    chi = (p.control_n - expected_a) ** 2 / expected_a + (
        p.treatment_n - expected_b
    ) ** 2 / expected_b
    srm_p = math.erfc(math.sqrt(chi / 2))
    result = {
        "kind": "experiment_result",
        "control_rate": a,
        "treatment_rate": b,
        "absolute_difference": b - a,
        "relative_lift": (b - a) / a if a else None,
        "sample_ratio_p_value": srm_p,
        "p_value": None,
        "difference_interval": None,
        "decision": "inconclusive",
        "limitations": [
            "Fixed-horizon independent-unit two-proportion normal approximation.",
            "Sample-ratio test uses a chi-square approximation; expected allocation cells should be at least 5.",
            "No sequential monitoring or multiplicity correction. Statistical evidence is not business value.",
            "Confidence interval is an unpooled Wald interval and can be inaccurate near boundaries.",
        ],
    }
    if min(expected_a, expected_b) < 5:
        result["decision"] = "allocation_sample_too_small"
    elif srm_p < 0.001:
        result["decision"] = "investigate_sample_ratio_mismatch"
    elif not p.fixed_horizon_complete:
        result["decision"] = "wait_for_registered_horizon"
    elif (
        min(
            p.control_conversions,
            p.control_n - p.control_conversions,
            p.treatment_conversions,
            p.treatment_n - p.treatment_conversions,
        )
        < 10
    ):
        result["decision"] = "insufficient_normal_approximation"
    else:
        pooled = (p.control_conversions + p.treatment_conversions) / total
        se_null = math.sqrt(pooled * (1 - pooled) * (1 / p.control_n + 1 / p.treatment_n))
        z = (b - a) / se_null
        result["p_value"] = math.erfc(abs(z) / math.sqrt(2))
        se = math.sqrt(a * (1 - a) / p.control_n + b * (1 - b) / p.treatment_n)
        margin = NormalDist().inv_cdf(1 - p.alpha / 2) * se
        result["difference_interval"] = {
            "low": max(-1, b - a - margin),
            "high": min(1, b - a + margin),
            "confidence": 1 - p.alpha,
        }
        if result["p_value"] < p.alpha:
            result["decision"] = "evidence_of_increase" if b > a else "evidence_of_decrease"
    return result


class UTMInput(Input):
    url: str = Field(max_length=2048)
    source: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    medium: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    campaign: str = Field(min_length=1, max_length=150, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    replace_existing: bool = False


def build_utm(p: UTMInput) -> dict:
    parts = urlsplit(p.url)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        raise ValueError("Absolute HTTP(S) URL without credentials required")
    query = parse_qsl(parts.query, keep_blank_values=True)
    existing = [k for k, v in query if k.lower().startswith("utm_")]
    if existing and not p.replace_existing:
        raise ValueError("Existing UTM parameters found; explicitly choose replacement")
    query = [(k, v) for k, v in query if not k.lower().startswith("utm_")]
    query += [("utm_source", p.source), ("utm_medium", p.medium), ("utm_campaign", p.campaign)]
    return {
        "kind": "campaign_url",
        "url": urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        ),
        "replaced_parameters": existing,
        "limitations": [
            "No network request or campaign publication performed.",
            "Do not put personal information or secrets in campaign names or URL parameters.",
        ],
    }


REGISTRY = {
    "calculate_funnel": (
        FunnelInput,
        funnel,
        "Calculate explicit-denominator conversion and acquisition metrics for one cohort.",
    ),
    "reconcile_transactions": (
        ReconcileInput,
        reconcile,
        "Compare exact transaction IDs only when declared attribution scopes match.",
    ),
    "design_experiment": (
        DesignInput,
        design_experiment,
        "Estimate a fixed-horizon two-proportion experiment sample size.",
    ),
    "analyze_experiment": (
        ExperimentInput,
        analyze_experiment,
        "Review a completed fixed-horizon experiment with sample-ratio and approximation gates.",
    ),
    "build_campaign_url": (
        UTMInput,
        build_utm,
        "Build a normalized UTM URL while preserving unrelated parameters.",
    ),
}
