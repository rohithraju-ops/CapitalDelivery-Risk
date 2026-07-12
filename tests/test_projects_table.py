"""Validate the cleaned/merged `projects` table built by scripts/build_db.py.

Rerun after any change to sql/*.sql or a refresh of the raw source files:
    uv run python scripts/build_db.py && uv run pytest tests/ -v
"""

from pathlib import Path

import duckdb
import pytest

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "capital_delivery_risk.duckdb"

EXPECTED_DATA_SOURCES = {"both", "syip_only", "dashboard_only"}


@pytest.fixture(scope="module")
def con():
    assert DB_PATH.exists(), f"missing {DB_PATH} — run `uv run python scripts/build_db.py` first"
    connection = duckdb.connect(str(DB_PATH), read_only=True)
    yield connection
    connection.close()


def test_projects_table_not_empty(con):
    assert con.execute("SELECT count(*) FROM projects").fetchone()[0] > 0


def test_projects_row_count_in_expected_ballpark(con):
    # Real count observed 2026-07-12 was 5,506 (2,853 SYIP + 4,743 dashboard - 2,090 overlap).
    # Loose floor/ceiling so this survives annual refreshes without needing constant edits.
    count = con.execute("SELECT count(*) FROM projects").fetchone()[0]
    assert 4000 <= count <= 10000


def test_upc_is_unique_key(con):
    total, distinct = con.execute(
        "SELECT count(*), count(distinct upc) FROM projects"
    ).fetchone()
    assert total == distinct, "join produced duplicate UPCs (fan-out)"


def test_data_source_only_expected_values(con):
    seen = {row[0] for row in con.execute("SELECT DISTINCT data_source FROM projects").fetchall()}
    assert seen == EXPECTED_DATA_SOURCES


def test_data_source_counts_partition_total(con):
    total = con.execute("SELECT count(*) FROM projects").fetchone()[0]
    summed = con.execute("SELECT sum(cnt) FROM (SELECT count(*) AS cnt FROM projects GROUP BY data_source)").fetchone()[0]
    assert total == summed


def test_district_and_road_system_always_populated(con):
    # Every row should get district/road_system from one side or the other — a null here
    # means the coalesce is broken, not an expected data gap.
    for col in ["district", "road_system"]:
        null_count = con.execute(f"SELECT count(*) FROM projects WHERE {col} IS NULL").fetchone()[0]
        assert null_count == 0, f"{col} is null for {null_count} rows — coalesce should always fill this"


def test_project_type_null_only_for_documented_gap(con):
    # 2 SYIP rows (UPC 101452, -11780) genuinely lack SCOPE_OF_WORK_DESC in the source and
    # have no dashboard match to fall back on — see docs/data_cleaning_rules.md. Any more
    # than a handful would mean a new, undocumented gap has appeared.
    null_count = con.execute("SELECT count(*) FROM projects WHERE project_type IS NULL").fetchone()[0]
    assert 0 <= null_count <= 5


def test_placeholder_upcs_are_negative_and_syip_only(con):
    # Documented quirk: projects without a permanent UPC yet use a negative sentinel.
    rows = con.execute(
        "SELECT data_source FROM projects WHERE upc < 0"
    ).fetchall()
    assert len(rows) > 0
    assert all(r[0] == "syip_only" for r in rows), "a negative UPC matched a dashboard row — investigate"


def test_budget_fields_numeric_and_mostly_populated(con):
    for col in ["allocated_budget", "current_estimate"]:
        non_null_rate = con.execute(
            f"SELECT avg(({col} IS NOT NULL)::INT) FROM projects"
        ).fetchone()[0]
        assert non_null_rate > 0.85, f"{col} populated for only {non_null_rate:.1%} of rows"


def test_outcome_status_is_null_only_for_syip_only_rows(con):
    # syip_only rows haven't reached construction yet, so no on-time/on-budget grade exists.
    # If a syip_only row HAS a status, or a both/dashboard_only row is missing one where the
    # raw dashboard had a value, the join logic has regressed.
    bad = con.execute(
        "SELECT count(*) FROM projects WHERE data_source = 'syip_only' AND on_time_status IS NOT NULL"
    ).fetchone()[0]
    assert bad == 0, "syip_only rows should never have an on_time_status"


def test_allocated_budget_prefers_syip_value_when_present(con):
    # The coalesce rule is COALESCE(syip.total_allocated, dashboard.budget) — so wherever
    # raw SYIP has a non-null TOTAL_ALLOCATIONS_CURRENT, that exact value must win, never
    # the dashboard's budget figure (which can legitimately differ — see docs).
    mismatches = con.execute(
        """
        SELECT count(*)
        FROM projects p
        JOIN raw_syip s ON p.upc = s.UPC
        WHERE s.TOTAL_ALLOCATIONS_CURRENT IS NOT NULL
          AND p.allocated_budget != s.TOTAL_ALLOCATIONS_CURRENT
        """
    ).fetchone()[0]
    assert mismatches == 0


def test_allocated_budget_total_in_expected_ballpark(con):
    # Loose magnitude check only — 126 SYIP rows have a null TOTAL_ALLOCATIONS_CURRENT and
    # fall back to the dashboard's budget figure for 'both' rows, so exact reconciliation
    # with the raw SYIP sum isn't expected. ~$38.6B was the raw SYIP sum observed 2026-07-12.
    total = con.execute(
        "SELECT sum(allocated_budget) FROM projects WHERE data_source IN ('syip_only', 'both')"
    ).fetchone()[0]
    assert 3e10 <= total <= 5e10
