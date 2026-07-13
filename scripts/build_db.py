"""Build the DuckDB database from raw source files and the SQL scripts in sql/.

Usage: uv run python scripts/build_db.py
"""

from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "processed" / "capital_delivery_risk.duckdb"
SYIP_CSV = ROOT / "data" / "raw" / "syip_approved_projects.csv"
DASHBOARD_XLSX = ROOT / "data" / "raw" / "vdot_performance_dashboard.xlsx"
SQL_DIR = ROOT / "sql"

SQL_FILES_IN_ORDER = [
    "01_stage_syip.sql",
    "02_stage_dashboard.sql",
    "03_build_projects.sql",
    "04_stage_contracts.sql",
    "05_kpi_summary.sql",
    "06_model_features.sql",
]


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))

    # DuckDB's CSV sniffer misdetects this file's dialect (embedded quoted commas in free-text
    # description fields collapse it to one column) — pandas' parser handles it correctly, so
    # ingest through pandas for both raw sources rather than read_csv_auto.
    syip_df = pd.read_csv(SYIP_CSV)
    con.register("syip_df", syip_df)
    con.execute("CREATE OR REPLACE TABLE raw_syip AS SELECT * FROM syip_df")

    dashboard_df = pd.read_excel(DASHBOARD_XLSX, sheet_name="Project_Development (UPC)")
    con.register("dashboard_df", dashboard_df)
    con.execute("CREATE OR REPLACE TABLE raw_dashboard AS SELECT * FROM dashboard_df")

    contracts_df = pd.read_excel(DASHBOARD_XLSX, sheet_name="Project_Delivery (Contract,UPC)")
    con.register("contracts_df", contracts_df)
    con.execute("CREATE OR REPLACE TABLE raw_contracts AS SELECT * FROM contracts_df")

    for filename in SQL_FILES_IN_ORDER:
        sql_text = (SQL_DIR / filename).read_text()
        con.execute(sql_text)
        print(f"ran {filename}")

    for table in [
        "raw_syip", "raw_dashboard", "raw_contracts",
        "stg_syip", "stg_dashboard", "projects",
        "stg_contracts", "stg_contracts_distinct",
        "kpi_rates", "kpi_cost_variance", "kpi_schedule_variance_overall", "kpi_schedule_variance_by_cut",
        "model_features",
    ]:
        count = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count} rows")

    con.close()


if __name__ == "__main__":
    main()
