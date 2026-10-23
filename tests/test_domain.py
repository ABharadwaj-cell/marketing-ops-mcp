import pytest
from pydantic import ValidationError
from marketing_ops.tools import (
    FunnelInput,
    ReconcileInput,
    DesignInput,
    ExperimentInput,
    UTMInput,
    funnel,
    reconcile,
    design_experiment,
    analyze_experiment,
    build_utm,
)


def test_zero_denominators_are_null():
    r = funnel(
        FunnelInput(
            spend=0,
            revenue=0,
            visitors=0,
            leads=0,
            customers=0,
            currency="USD",
            cohort_confirmed=True,
        )
    )
    assert all(m["value"] is None for m in r["metrics"])


def test_invalid_nested_cohort_rejected():
    with pytest.raises(ValidationError):
        FunnelInput(
            spend=1,
            revenue=2,
            visitors=1,
            leads=2,
            customers=0,
            currency="USD",
            cohort_confirmed=True,
        )


def scope():
    return {
        "start": "2026-01-01",
        "end": "2026-01-31",
        "currency": "USD",
        "timezone": "UTC",
        "attribution_model": "last_click",
        "lookback_days": 30,
        "date_basis": "conversion",
    }


def test_reconciliation_outer_join_and_exact_decimals():
    r = reconcile(
        ReconcileInput(
            left_scope=scope(),
            right_scope=scope(),
            left=[{"id": "a", "amount": "0.10"}, {"id": "b", "amount": "0.20"}],
            right=[{"id": "a", "amount": "0.11"}, {"id": "c", "amount": "1.00"}],
        )
    )
    assert r["totals"]["right_minus_left"] == "0.81"
    assert [m["status"] for m in r["metrics"]] == ["matched", "left_only", "right_only"]
    assert r["metrics"][1]["right"] is None


def test_scope_mismatch_prevents_misleading_totals():
    other = scope()
    other["lookback_days"] = 7
    r = reconcile(ReconcileInput(left_scope=scope(), right_scope=other, left=[], right=[]))
    assert r["status"] == "incomparable"
    assert "totals" not in r


def test_duplicate_transactions_rejected():
    with pytest.raises(ValidationError):
        ReconcileInput(
            left_scope=scope(), right_scope=scope(), left=[{"id": "a", "amount": 1}] * 2, right=[]
        )


def test_experiment_design_known_approximation():
    r = design_experiment(DesignInput(baseline_rate=0.1, absolute_mde=0.02))
    assert 3800 < r["per_arm_sample"] < 3900


def test_experiment_result_and_early_stopping_gate():
    p = ExperimentInput(
        control_n=1000,
        control_conversions=100,
        treatment_n=1000,
        treatment_conversions=150,
        fixed_horizon_complete=True,
    )
    r = analyze_experiment(p)
    assert r["decision"] == "evidence_of_increase"
    assert r["p_value"] < 0.001
    assert r["difference_interval"]["low"] > 0
    p.fixed_horizon_complete = False
    assert analyze_experiment(p)["p_value"] is None


def test_srm_blocks_conclusion():
    p = ExperimentInput(
        control_n=1000,
        control_conversions=100,
        treatment_n=2000,
        treatment_conversions=500,
        fixed_horizon_complete=True,
    )
    r = analyze_experiment(p)
    assert r["decision"] == "investigate_sample_ratio_mismatch"
    assert r["p_value"] is None


def test_utm_preserves_query_and_requires_replacement():
    p = UTMInput(
        url="https://example.com/?x=1#section",
        source="newsletter",
        medium="email",
        campaign="launch",
    )
    assert "x=1&utm_source=" in build_utm(p)["url"]
    p.url = "https://example.com/?utm_source=old"
    with pytest.raises(ValueError):
        build_utm(p)
