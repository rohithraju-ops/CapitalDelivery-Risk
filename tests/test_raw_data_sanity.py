"""Sanity checks on the raw source files pulled from VDOT.

Rerun whenever the raw files are refreshed (source data updates annually) to catch
schema drift or a broken/truncated download before it reaches the cleaning step.
"""

from pathlib import Path

import pandas as pd
import pytest

DATA_RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
SYIP_PATH = DATA_RAW / "syip_approved_projects.csv"
DASHBOARD_PATH = DATA_RAW / "vdot_performance_dashboard.xlsx"

SYIP_REQUIRED_COLUMNS = {
    "UPC",
    "DISTRICT_CODE_DESC",
    "STATE_HIGHWAY_DESC",
    "SCOPE_OF_WORK_DESC",
    "POOL_PRJ_STATUS_DSC",
    "HAS_PE",
    "HAS_RW",
    "HAS_CN",
    "PE_START_DATE",
    "CN_START_DATE",
    "CN_END_DATE",
    "TOTAL_ALLOCATIONS_CURRENT",
    "Y1_Y6_ALLOCATIONS",
    "CURRENT_PE_ESTIMATE",
    "CURRENT_RW_ESTIMATE",
    "CURRENT_CN_ESTIMATE",
    "TOTAL_EST_CURRENT",
}

DASHBOARD_REQUIRED_SHEETS = {
    "Project_Development (UPC)",
    "Project_Delivery (Contract,UPC)",
    "Project_Delivery (Contract)",
}

DASHBOARD_DEV_REQUIRED_COLUMNS = {
    "UPC",
    "DISTRICT",
    "PROJECT_STATUS",
    "BUDGET",
    "ESTIMATE",
    "ON_TIME_STATUS",
    "ON_BUDGET_STATUS",
}


@pytest.fixture(scope="module")
def syip_df():
    assert SYIP_PATH.exists(), f"missing {SYIP_PATH} — re-download the SYIP export first"
    return pd.read_csv(SYIP_PATH)


@pytest.fixture(scope="module")
def dashboard_sheets():
    assert DASHBOARD_PATH.exists(), f"missing {DASHBOARD_PATH} — re-download the dashboard export first"
    return pd.ExcelFile(DASHBOARD_PATH)


@pytest.fixture(scope="module")
def dashboard_dev_df(dashboard_sheets):
    return dashboard_sheets.parse("Project_Development (UPC)")


def test_syip_not_empty(syip_df):
    assert len(syip_df) > 0


def test_syip_row_count_in_expected_ballpark(syip_df):
    # Real count observed 2026-07-12 was 2,853. Floor set below that with headroom for
    # annual refreshes; ceiling guards against accidentally loading a duplicated/corrupt file.
    assert 2000 <= len(syip_df) <= 10000


def test_syip_has_required_columns(syip_df):
    missing = SYIP_REQUIRED_COLUMNS - set(syip_df.columns)
    assert not missing, f"SYIP export is missing expected columns: {missing}"


def test_syip_upc_is_unique_key(syip_df):
    assert syip_df["UPC"].notna().all(), "UPC has null values"
    assert syip_df["UPC"].is_unique, "UPC has duplicate values — no longer a clean project key"


def test_syip_cost_fields_are_numeric_and_mostly_populated(syip_df):
    for col in ["TOTAL_ALLOCATIONS_CURRENT", "TOTAL_EST_CURRENT"]:
        assert pd.api.types.is_numeric_dtype(syip_df[col]), f"{col} did not parse as numeric"
        non_null_rate = syip_df[col].notna().mean()
        assert non_null_rate > 0.9, f"{col} is null for more than 10% of rows ({non_null_rate:.1%})"


def test_syip_duplicate_row_rate_is_low(syip_df):
    dup_rate = syip_df.duplicated().mean()
    assert dup_rate < 0.01, f"unexpectedly high full-row duplicate rate: {dup_rate:.1%}"


def test_dashboard_has_required_sheets(dashboard_sheets):
    missing = DASHBOARD_REQUIRED_SHEETS - set(dashboard_sheets.sheet_names)
    assert not missing, f"dashboard workbook is missing expected sheets: {missing}"


def test_dashboard_dev_row_count_in_expected_ballpark(dashboard_dev_df):
    # Real count observed 2026-07-12 was 4,743.
    assert 3000 <= len(dashboard_dev_df) <= 10000


def test_dashboard_dev_has_required_columns(dashboard_dev_df):
    missing = DASHBOARD_DEV_REQUIRED_COLUMNS - set(dashboard_dev_df.columns)
    assert not missing, f"dashboard 'Project_Development' sheet is missing columns: {missing}"


def test_dashboard_dev_upc_is_unique_key(dashboard_dev_df):
    assert dashboard_dev_df["UPC"].notna().all(), "UPC has null values"
    assert dashboard_dev_df["UPC"].is_unique, "UPC has duplicate values in the dashboard export"


def test_dashboard_status_flags_use_expected_categories(dashboard_dev_df):
    expected = {"G", "Y", "R"}
    for col in ["ON_TIME_STATUS", "ON_BUDGET_STATUS"]:
        seen = set(dashboard_dev_df[col].dropna().unique())
        assert seen <= expected, f"{col} has unexpected values: {seen - expected}"


def test_upc_overlaps_between_syip_and_dashboard(syip_df, dashboard_dev_df):
    overlap = set(syip_df["UPC"]) & set(dashboard_dev_df["UPC"])
    # Real overlap observed 2026-07-12 was 2,090 of 2,853 SYIP UPCs. Floor is loose since the
    # active SYIP window and dashboard tracking window will drift independently year to year.
    assert len(overlap) > 1000, "join key between SYIP and dashboard has collapsed"
