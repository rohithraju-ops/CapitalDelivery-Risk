"""Score every currently-active project and write results + explanations to DuckDB.

Usage: uv run python scripts/score_projects.py

Scores data_source IN ('both', 'syip_only') — i.e. projects still in the current SYIP
program — not the full model_features table, since dashboard_only rows have rolled off
the active program and there's nothing to act on for them.
"""

from pathlib import Path

import duckdb

from risk_model_lib import ALL_FEATURES, load_model, score_and_explain

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "processed" / "capital_delivery_risk.duckdb"

# Fixed, documented cutoff rather than a recomputed percentile each refresh — see
# docs/risk_model.md. Observed 2026-07-12: this was exactly the 75th percentile of
# currently-active project risk scores (n=2,853).
ELEVATED_RISK_THRESHOLD = 60


def main() -> None:
    con = duckdb.connect(str(DB_PATH))
    active = con.execute(
        "SELECT upc, allocated_budget FROM model_features WHERE is_currently_active"
    ).df()
    features = con.execute(
        f"SELECT upc, {', '.join(ALL_FEATURES)} FROM model_features WHERE is_currently_active"
    ).df()

    model = load_model()
    scored = score_and_explain(model, features)
    scored = scored.merge(active[["upc", "allocated_budget"]], on="upc")
    scored["elevated_risk"] = scored["risk_score"] >= ELEVATED_RISK_THRESHOLD

    con.register("scored_df", scored)
    con.execute("CREATE OR REPLACE TABLE risk_scores AS SELECT * FROM scored_df")
    con.close()

    print(f"scored {len(scored)} currently-active projects")
    print(scored.sort_values("risk_score", ascending=False).head(5).to_string())

    n_elevated = scored["elevated_risk"].sum()
    dollars_elevated = scored.loc[scored["elevated_risk"], "allocated_budget"].sum()
    print(
        f"\nelevated-risk (score >= {ELEVATED_RISK_THRESHOLD}): {n_elevated} of {len(scored)} "
        f"active projects ({n_elevated / len(scored):.1%}), ${dollars_elevated:,.0f} allocated"
    )


if __name__ == "__main__":
    main()
