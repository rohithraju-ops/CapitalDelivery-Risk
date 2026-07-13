# Capital Delivery Risk Dashboard (VDOT Edition)

Public-data version of the capital project cost/schedule delivery-risk problem, built on
VDOT's Six-Year Improvement Program (SYIP) data and VDOT's Performance Dashboard. See
`PRD_VDOT_Capital_Delivery_Risk_Dashboard.md` for full background, scope, and the build plan.

Status: data layer, KPI layer, and risk-scoring model built; dashboards in progress.

## Setup

```
uv sync
```

## Get the data and build the database

Raw data files and the built DuckDB database are **not** committed to this repo — both are
public and cheap to regenerate, so the repo just holds the code that produces them.

```
uv run python scripts/fetch_raw_data.py   # downloads to data/raw/ (~8MB total)
uv run python scripts/build_db.py         # builds data/processed/capital_delivery_risk.duckdb
```

`fetch_raw_data.py` pulls two public, no-auth sources:
- VDOT's Six-Year Improvement Program (SYIP) export, via virginiaroads.org's ArcGIS Hub
  download API. That API generates the export on demand, so the script polls until it's
  ready (usually well under a minute).
- VDOT's Performance Dashboard "Projects" export (on-time/on-budget outcomes), a direct
  download from dashboard.vdot.virginia.gov.

`build_db.py` loads both into DuckDB and runs the SQL in `sql/` (in order) to produce a
cleaned, merged `projects` table, contract-level schedule/cost variance, KPI summary tables,
and the model-ready feature table. See `docs/data_cleaning_rules.md` for exactly how the two
sources are combined and every null-handling/merge decision made along the way, and
`docs/kpi_definitions.md` for how every KPI is defined and why.

## Train and run the risk-scoring model

```
uv run python scripts/compare_models.py     # optional: re-run the 4-model comparison + plots
uv run python scripts/train_risk_model.py   # fits + persists data/processed/risk_model.joblib
uv run python scripts/score_projects.py     # scores active projects into the risk_scores table
uv run python scripts/explain_model.py      # prints global top-features-driving-risk
```

Like the database, the fitted model file is not committed — regenerate it with the commands
above. `reports/figures/` (committed) has the model comparison plots and metrics from
`compare_models.py`. See `docs/risk_model.md` for the target definition, feature set, why
logistic regression was chosen over the alternatives tested, and the headline
dollar-denominated risk stat.

## Query the database

```
uv run python -c "
import duckdb
con = duckdb.connect('data/processed/capital_delivery_risk.duckdb')
print(con.execute('SELECT data_source, count(*) FROM projects GROUP BY 1').df())
"
```

or open it directly with the DuckDB CLI: `duckdb data/processed/capital_delivery_risk.duckdb`.

## Run the tests

```
uv run pytest tests/ -v
```

`tests/test_raw_data_sanity.py` validates the raw downloads; `tests/test_projects_table.py`
validates the cleaned/merged table; `tests/test_kpi_summary.py` validates the KPI tables;
`tests/test_risk_model.py` validates the trained model and its scored output. All need the
data fetched, the database built, and (for the last one) the model trained and projects
scored first (see above).

## Data sources & attribution

- VDOT Six-Year Improvement Program (SYIP), via Virginia's open data portal
  ([virginiaroads.org](https://www.virginiaroads.org))
- VDOT Performance Dashboard ([dashboard.vdot.virginia.gov](https://dashboard.vdot.virginia.gov))

Both are public datasets produced and owned by the Virginia Department of Transportation.
This project is independent analysis built on that public data — it does not use or claim
access to any WSP-internal data or systems.
