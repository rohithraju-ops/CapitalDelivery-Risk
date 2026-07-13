"""Validate the KPI tables built by sql/05_kpi_summary.sql.

Rerun after any change to sql/*.sql or a refresh of the raw source files:
    uv run python scripts/build_db.py && uv run pytest tests/ -v
"""

from pathlib import Path

import duckdb
import pytest

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "capital_delivery_risk.duckdb"


@pytest.fixture(scope="module")
def con():
    assert DB_PATH.exists(), f"missing {DB_PATH} — run `uv run python scripts/build_db.py` first"
    connection = duckdb.connect(str(DB_PATH), read_only=True)
    yield connection
    connection.close()


def test_kpi_rates_are_valid_proportions(con):
    rows = con.execute(
        "SELECT on_time_g_rate, on_time_y_rate, on_time_r_rate, on_budget_g_rate, on_budget_y_rate, on_budget_r_rate FROM kpi_rates"
    ).fetchall()
    assert len(rows) > 0
    for row in rows:
        for value in row:
            assert 0.0 <= value <= 1.0


def test_kpi_rates_gyr_shares_sum_to_one(con):
    rows = con.execute(
        "SELECT on_time_g_rate + on_time_y_rate + on_time_r_rate, on_budget_g_rate + on_budget_y_rate + on_budget_r_rate FROM kpi_rates"
    ).fetchall()
    for on_time_sum, on_budget_sum in rows:
        assert on_time_sum == pytest.approx(1.0, abs=1e-9)
        assert on_budget_sum == pytest.approx(1.0, abs=1e-9)


def test_kpi_rates_overall_n_matches_rated_projects(con):
    kpi_n = con.execute("SELECT n_rated FROM kpi_rates WHERE cut_type='overall'").fetchone()[0]
    raw_n = con.execute(
        "SELECT count(*) FROM projects WHERE data_source IN ('both', 'dashboard_only')"
    ).fetchone()[0]
    assert kpi_n == raw_n


def test_kpi_cost_variance_median_and_mean_diverge_as_documented(con):
    # Regression test for the metric-trap finding in docs/kpi_definitions.md: some early-stage
    # projects have a tiny allocated_budget against a much larger full-cost estimate, which
    # should keep the mean well above the median. If this ever collapsed to roughly equal,
    # the underlying data or join logic changed in a way worth re-investigating.
    row = con.execute(
        "SELECT median_variance_pct, avg_variance_pct FROM kpi_cost_variance WHERE cut_type='overall'"
    ).fetchone()
    median_pct, avg_pct = row
    assert avg_pct > median_pct + 0.5


def test_kpi_schedule_variance_overall_uses_contract_grain(con):
    kpi_n = con.execute("SELECT n_completed FROM kpi_schedule_variance_overall").fetchone()[0]
    raw_n = con.execute(
        "SELECT count(*) FROM stg_contracts_distinct WHERE schedule_variance_days_actual IS NOT NULL"
    ).fetchone()[0]
    assert kpi_n == raw_n


def test_small_subgroups_are_flagged_below_threshold(con):
    # Regression test for the n>=30 modeling threshold documented in docs/kpi_definitions.md.
    statewide_n = con.execute(
        "SELECT n_rated FROM kpi_rates WHERE cut_type='district' AND cut_value='Statewide'"
    ).fetchone()[0]
    assert statewide_n < 30

    transit_n = con.execute(
        "SELECT n_rated FROM kpi_rates WHERE cut_type='road_system' AND cut_value='Public Transportation'"
    ).fetchone()[0]
    assert transit_n < 30

    below_threshold_project_types = con.execute(
        "SELECT count(*) FROM kpi_rates WHERE cut_type='project_type' AND n_rated < 30"
    ).fetchone()[0]
    at_or_above_project_types = con.execute(
        "SELECT count(*) FROM kpi_rates WHERE cut_type='project_type' AND n_rated >= 30"
    ).fetchone()[0]
    assert below_threshold_project_types > at_or_above_project_types
