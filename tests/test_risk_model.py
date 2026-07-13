"""Validate the risk-scoring model and its outputs.

Rerun after retraining: uv run python scripts/train_risk_model.py && uv run python
scripts/score_projects.py && uv run pytest tests/test_risk_model.py -v
"""

import sys
from pathlib import Path

import duckdb
import joblib
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "processed" / "capital_delivery_risk.duckdb"
MODEL_PATH = ROOT / "data" / "processed" / "risk_model.joblib"
COMPARISON_CSV = ROOT / "reports" / "figures" / "model_comparison_metrics.csv"

sys.path.insert(0, str(ROOT / "scripts"))
from risk_model_lib import global_feature_table  # noqa: E402


@pytest.fixture(scope="module")
def con():
    assert DB_PATH.exists(), f"missing {DB_PATH} — run `uv run python scripts/build_db.py` first"
    connection = duckdb.connect(str(DB_PATH), read_only=True)
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def model():
    assert MODEL_PATH.exists(), f"missing {MODEL_PATH} — run `uv run python scripts/train_risk_model.py` first"
    return joblib.load(MODEL_PATH)


def test_risk_scores_cover_all_active_projects(con):
    n_scored = con.execute("SELECT count(*) FROM risk_scores").fetchone()[0]
    n_active = con.execute("SELECT count(*) FROM model_features WHERE is_currently_active").fetchone()[0]
    assert n_scored == n_active


def test_risk_scores_are_valid_range(con):
    row = con.execute("SELECT min(risk_score), max(risk_score) FROM risk_scores").fetchone()
    assert 0 <= row[0] and row[1] <= 100
    row = con.execute("SELECT min(risk_probability), max(risk_probability) FROM risk_scores").fetchone()
    assert 0.0 <= row[0] and row[1] <= 1.0


def test_every_project_has_a_nonempty_explanation(con):
    empty_count = con.execute(
        "SELECT count(*) FROM risk_scores WHERE top_factors IS NULL OR trim(top_factors) = ''"
    ).fetchone()[0]
    assert empty_count == 0


def test_elevated_risk_flag_matches_threshold(con):
    mismatches = con.execute(
        "SELECT count(*) FROM risk_scores WHERE elevated_risk != (risk_score >= 60)"
    ).fetchone()[0]
    assert mismatches == 0


def test_comparison_csv_shows_logistic_regression_beats_random():
    assert COMPARISON_CSV.exists(), f"missing {COMPARISON_CSV} — run scripts/compare_models.py first"
    df = pd.read_csv(COMPARISON_CSV, index_col="model")
    assert df.loc["logistic_regression", "roc_auc_mean"] > 0.65


def test_project_type_coefficients_correlate_with_observed_rates(con, model):
    feature_table = global_feature_table(model)
    project_type_coefs = feature_table[feature_table["column"] == "project_type_bucketed"][["category", "coef"]]

    rates = con.execute(
        "SELECT cut_value AS category, (on_time_r_rate + on_budget_r_rate) / 2 AS avg_r_rate "
        "FROM kpi_rates WHERE cut_type = 'project_type'"
    ).df()

    merged = project_type_coefs.merge(rates, on="category", how="inner")
    correlation = merged["coef"].corr(merged["avg_r_rate"])
    assert correlation > 0.5


def test_resurfacing_and_pedestrian_facilities_directionality(model):
    # Anchor regression test for the two specific categories called out in docs/risk_model.md
    # and docs/kpi_definitions.md (Resurfacing 4.2% observed not-on-time vs. Facilities For
    # Pedestrians And Bicycles 36.9%) — the model must agree on which way each one points.
    feature_table = global_feature_table(model).set_index("category")
    assert feature_table.loc["Resurfacing", "coef"] < 0
    assert feature_table.loc["Facilities For Pedestrians And Bicycles", "coef"] > 0
